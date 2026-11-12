import contextlib
import io
import json
import math
import os
import unittest
from unittest import mock

import passgen as pg


class TtyOut(io.StringIO):
    """StringIO that claims to be a terminal, so the CLI enables colors."""

    def isatty(self):
        return True


def run_cli(args, tty=False, env=None):
    out = TtyOut() if tty else io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        if env is None:
            code = pg.main(args)
        else:
            with mock.patch.dict(os.environ, env):
                code = pg.main(args)
    return code, out.getvalue(), err.getvalue()


def items_from(out):
    """Password/passphrase lines from plain-text output (no --no-color needed
    only when colors are off; callers pass --no-color)."""
    items = []
    for line in out.splitlines()[1:]:
        if line.startswith("ENTROPY"):
            break
        items.append(line.strip())
    return items


class Charsets(unittest.TestCase):
    def test_default_classes(self):
        self.assertEqual(pg.build_classes(), [pg.LOWER, pg.UPPER, pg.DIGITS, pg.SYMBOLS])

    def test_toggles_drop_classes(self):
        self.assertEqual(pg.build_classes(no_upper=True, no_digits=True, no_symbols=True),
                         [pg.LOWER])
        self.assertEqual(pg.build_classes(no_lower=True, no_symbols=True),
                         [pg.UPPER, pg.DIGITS])

    def test_exclude_ambiguous_filters(self):
        classes = pg.build_classes(exclude_ambiguous=True)
        joined = "".join(classes)
        for ch in pg.AMBIGUOUS:
            self.assertNotIn(ch, joined)
        self.assertIn("a", classes[0])
        self.assertIn("A", classes[1])
        self.assertIn("2", classes[2])

    def test_all_disabled_is_empty(self):
        self.assertEqual(pg.build_classes(True, True, True, True), [])


class Passwords(unittest.TestCase):
    def setUp(self):
        self.classes = pg.build_classes()
        self.charset = "".join(self.classes)

    def test_default_length(self):
        self.assertEqual(len(pg.generate_password(16, self.classes)), 16)

    def test_various_lengths(self):
        for n in (1, 2, 3, 4, 8, 32, 64, 128):
            self.assertEqual(len(pg.generate_password(n, self.classes)), n)

    def test_charset_membership(self):
        for _ in range(20):
            pw = pg.generate_password(24, self.classes)
            self.assertTrue(set(pw) <= set(self.charset))

    def test_one_char_per_class_when_length_permits(self):
        for _ in range(30):
            pw = pg.generate_password(16, self.classes)
            for cls in self.classes:
                self.assertTrue(any(c in cls for c in pw))

    def test_exact_length_four_classes(self):
        pw = pg.generate_password(4, self.classes)
        self.assertEqual(len(pw), 4)
        for cls in self.classes:
            self.assertEqual(sum(c in cls for c in pw), 1)

    def test_short_length_still_valid(self):
        pw = pg.generate_password(2, self.classes)
        self.assertEqual(len(pw), 2)
        self.assertTrue(set(pw) <= set(self.charset))

    def test_lower_only(self):
        pw = pg.generate_password(32, pg.build_classes(no_upper=True, no_digits=True,
                                                       no_symbols=True))
        self.assertTrue(set(pw) <= set(pg.LOWER))

    def test_digits_only(self):
        pw = pg.generate_password(32, pg.build_classes(no_lower=True, no_upper=True,
                                                       no_symbols=True))
        self.assertTrue(set(pw) <= set(pg.DIGITS))

    def test_no_symbols(self):
        classes = pg.build_classes(no_symbols=True)
        pw = pg.generate_password(64, classes)
        self.assertTrue(set(pw) <= set(pg.LOWER + pg.UPPER + pg.DIGITS))

    def test_exclude_ambiguous_output(self):
        classes = pg.build_classes(exclude_ambiguous=True)
        sample = "".join(pg.generate_password(40, classes) for _ in range(10))
        for ch in pg.AMBIGUOUS:
            self.assertNotIn(ch, sample)

    def test_passwords_are_distinct(self):
        pws = {pg.generate_password(16, self.classes) for _ in range(25)}
        self.assertEqual(len(pws), 25)


class Passphrases(unittest.TestCase):
    def test_word_count_and_membership(self):
        phrase = pg.generate_passphrase(6)
        words = phrase.split("-")
        self.assertEqual(len(words), 6)
        for w in words:
            self.assertIn(w, pg.WORDLIST)

    def test_custom_separators(self):
        for sep in (".", "_", " "):
            phrase = pg.generate_passphrase(4, sep)
            words = phrase.split(sep)
            self.assertEqual(len(words), 4)
            for w in words:
                self.assertIn(w, pg.WORDLIST)

    def test_empty_separator(self):
        phrase = pg.generate_passphrase(4, "")
        self.assertTrue(phrase.isalpha())
        self.assertGreaterEqual(len(phrase), 4 * min(map(len, pg.WORDLIST)))
        self.assertLessEqual(len(phrase), 4 * max(map(len, pg.WORDLIST)))

    def test_wordlist_quality(self):
        self.assertGreaterEqual(len(pg.WORDLIST), 200)
        self.assertEqual(len(set(pg.WORDLIST)), len(pg.WORDLIST))
        for w in pg.WORDLIST:
            self.assertTrue(w.isalpha() and w.islower(), w)

    def test_passphrases_are_distinct(self):
        phrases = {pg.generate_passphrase(6) for _ in range(20)}
        self.assertEqual(len(phrases), 20)


class Entropy(unittest.TestCase):
    def test_password_formula(self):
        size = sum(len(c) for c in pg.build_classes())
        self.assertAlmostEqual(pg.password_entropy(16, size), 16 * math.log2(size))

    def test_passphrase_formula(self):
        self.assertAlmostEqual(pg.passphrase_entropy(5), 5 * math.log2(len(pg.WORDLIST)))

    def test_entropy_grows_with_length(self):
        self.assertLess(pg.password_entropy(8, 88), pg.password_entropy(16, 88))
        self.assertLess(pg.passphrase_entropy(3), pg.passphrase_entropy(6))

    def test_smaller_charset_less_entropy(self):
        self.assertLess(pg.password_entropy(16, 26), pg.password_entropy(16, 88))


class Cli(unittest.TestCase):
    def test_default_run(self):
        code, out, _ = run_cli(["--no-color"])
        self.assertEqual(code, 0)
        items = items_from(out)
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0]), 16)

    def test_count_and_length(self):
        code, out, _ = run_cli(["--count", "5", "--length", "24", "--no-color"])
        self.assertEqual(code, 0)
        items = items_from(out)
        self.assertEqual(len(items), 5)
        self.assertTrue(all(len(p) == 24 for p in items))

    def test_json_shape_and_entropy(self):
        code, out, _ = run_cli(["--count", "3", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(set(data), {"passwords", "entropy_bits"})
        self.assertEqual(len(data["passwords"]), 3)
        size = sum(len(c) for c in pg.build_classes())
        self.assertEqual(data["entropy_bits"], round(16 * math.log2(size), 2))

    def test_json_passphrase(self):
        code, out, _ = run_cli(["--words", "4", "--count", "2", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(len(data["passwords"]), 2)
        self.assertEqual(data["entropy_bits"], round(4 * math.log2(len(pg.WORDLIST)), 2))
        for phrase in data["passwords"]:
            self.assertEqual(len(phrase.split("-")), 4)

    def test_entropy_flag_text(self):
        code, out, _ = run_cli(["--entropy", "--no-color"])
        self.assertEqual(code, 0)
        self.assertIn("ENTROPY", out)
        self.assertIn("bits per password", out)
        _, plain, _ = run_cli(["--no-color"])
        self.assertNotIn("ENTROPY", plain)

    def test_passphrase_mode(self):
        code, out, _ = run_cli(["--words", "5", "--no-color"])
        self.assertEqual(code, 0)
        items = items_from(out)
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0].split("-")), 5)

    def test_separator_flag(self):
        code, out, _ = run_cli(["--words", "3", "--separator", ".", "--no-color"])
        self.assertEqual(code, 0)
        self.assertEqual(items_from(out)[0].count("."), 2)

    def test_exclude_ambiguous_cli(self):
        code, out, _ = run_cli(["--length", "40", "--exclude-ambiguous", "--no-color"])
        self.assertEqual(code, 0)
        for ch in pg.AMBIGUOUS:
            self.assertNotIn(ch, items_from(out)[0])

    def test_no_color_flag(self):
        code, out, _ = run_cli(["--no-color"], tty=True, env={"NO_COLOR": ""})
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out)

    def test_color_on_tty(self):
        code, out, _ = run_cli([], tty=True, env={"NO_COLOR": ""})
        self.assertEqual(code, 0)
        self.assertIn("\x1b[", out)

    def test_no_color_env(self):
        code, out, _ = run_cli([], tty=True, env={"NO_COLOR": "1"})
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out)

    def test_no_color_when_piped(self):
        code, out, _ = run_cli([], tty=False, env={"NO_COLOR": ""})
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out)

    def test_version(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            pg.main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("passgen " + pg.__version__, out.getvalue())

    def test_length_zero_rejected(self):
        code, _, err = run_cli(["--length", "0"])
        self.assertEqual(code, 2)
        self.assertIn("--length", err)

    def test_length_negative_rejected(self):
        self.assertEqual(run_cli(["--length", "-3"])[0], 2)

    def test_count_zero_rejected(self):
        code, _, err = run_cli(["--count", "0"])
        self.assertEqual(code, 2)
        self.assertIn("--count", err)

    def test_words_zero_rejected(self):
        code, _, err = run_cli(["--words", "0"])
        self.assertEqual(code, 2)
        self.assertIn("--words", err)

    def test_words_negative_rejected(self):
        self.assertEqual(run_cli(["--words", "-2"])[0], 2)

    def test_all_charsets_disabled_rejected(self):
        code, _, err = run_cli(["--no-lower", "--no-upper", "--no-digits", "--no-symbols"])
        self.assertEqual(code, 2)
        self.assertIn("charset", err)

    def test_non_numeric_length_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            pg.main(["--length", "abc"])
        self.assertEqual(ctx.exception.code, 2)

    def test_json_errors_still_exit_2(self):
        code, out, _ = run_cli(["--length", "0", "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()