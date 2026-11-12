#!/usr/bin/env python3
"""passgen - secure password & passphrase generator.

Every random choice comes from the secrets module (OS CSPRNG). Password mode
draws from lower/upper/digits/symbols with per-class toggles and guarantees at
least one character from each enabled class when the length permits.
Passphrase mode joins random words from an embedded 256-word list. Single
file, standard library only, no network; secrets are printed to stdout and
never written to disk.
"""

import argparse
import json
import math
import os
import secrets
import string
import sys

__version__ = "1.0.0"

LOWER = string.ascii_lowercase
UPPER = string.ascii_uppercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?/"
AMBIGUOUS = "Il1O0"

# 256 common, easy-to-read words (8 bits of entropy per word). The list is
# public; passphrase strength comes from the random selection, not secrecy.
WORDS_TEXT = """
able acid aged also area army away baby back ball band bank base bath bear beat
bell belt best bird blue boat body bone book boom born boss both bowl bulk burn
bush busy call calm came camp card care case cash cast cell chat chip city club
coal coat code cold come cook cool cope copy core cost crew crop dark data date
dawn dead deal dear debt deep deny desk dial diet dirt dish disk dock dome done
door dose down drag draw drew drop drum dual duck dust duty each earn ease east
easy edge else even ever exam exit face fact fade fail fair fall fame farm fast
fate fear feed feel feet fell felt file fill film find fine fire firm fish fist
five flag flat flee flew flow fold folk fond font food fool foot fork form fort
four free frog from fuel full fund gain game gate gave gear gene gift girl give
glad goal goat goes gold golf gone good gray grew grey grid grin grow gulf hair
half hall hand hang hard harm hate have head hear heat held help herb hero hide
high hill hire hold hole holy home hope host hour huge hung hunt hurt idea inch
into iron item jazz join joke jump jury just keen keep kept kick kind king knee
knew know lack lady laid lake land lane last late lawn lead leaf lean left less
life lift like line link list live load loan lock long look lord lose loss lost
"""
WORDLIST = tuple(WORDS_TEXT.split())

_RNG = secrets.SystemRandom()


def build_classes(no_lower=False, no_upper=False, no_digits=False,
                  no_symbols=False, exclude_ambiguous=False):
    """Return the enabled character classes as a list of disjoint strings."""
    classes = []
    for enabled, chars in ((not no_lower, LOWER), (not no_upper, UPPER),
                           (not no_digits, DIGITS), (not no_symbols, SYMBOLS)):
        if not enabled:
            continue
        if exclude_ambiguous:
            chars = "".join(c for c in chars if c not in AMBIGUOUS)
        if chars:
            classes.append(chars)
    return classes


def generate_password(length, classes):
    """One random password; >=1 char per enabled class when length permits."""
    charset = "".join(classes)
    chars = [secrets.choice(cls) for cls in classes[:length]]
    chars.extend(secrets.choice(charset) for _ in range(length - len(chars)))
    _RNG.shuffle(chars)
    return "".join(chars)


def generate_passphrase(words, separator="-"):
    return separator.join(secrets.choice(WORDLIST) for _ in range(words))


def password_entropy(length, charset_size):
    """Estimated bits: length * log2(charset_size), uniform independent draws."""
    return length * math.log2(charset_size)


def passphrase_entropy(words):
    """Estimated bits: words * log2(wordlist_size)."""
    return words * math.log2(len(WORDLIST))


def colorize(text, color, enabled):
    if not enabled:
        return text
    codes = {"red": "31", "green": "32", "yellow": "33", "bold": "1"}
    return "\x1b[%sm%s\x1b[0m" % (codes[color], text)


def report(items, bits, color, as_json, passphrase=False):
    if as_json:
        return json.dumps({"passwords": items, "entropy_bits": bits}, indent=2)
    kind = "passphrase" if passphrase else "password"
    lines = [colorize("%sS (%d)" % (kind.upper(), len(items)), "bold", color)]
    for item in items:
        lines.append("  " + colorize(item, "green", color))
    if bits is not None:
        lines.append(colorize("ENTROPY (estimate)", "bold", color))
        lines.append("  ~%.2f bits per %s" % (bits, kind))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="passgen",
        description="Secure password & passphrase generator (secrets CSPRNG, stdlib only).")
    parser.add_argument("--length", type=int, default=16, metavar="N",
                        help="password length (default 16; ignored with --words)")
    parser.add_argument("--count", type=int, default=1, metavar="N",
                        help="how many passwords/passphrases to generate (default 1)")
    parser.add_argument("--no-symbols", action="store_true",
                        help="disable the symbol class")
    parser.add_argument("--no-digits", action="store_true",
                        help="disable the digit class")
    parser.add_argument("--no-upper", action="store_true",
                        help="disable the uppercase class")
    parser.add_argument("--no-lower", action="store_true",
                        help="disable the lowercase class")
    parser.add_argument("--exclude-ambiguous", action="store_true",
                        help="drop look-alike characters (I l 1 O 0)")
    parser.add_argument("--words", type=int, default=None, metavar="N",
                        help="passphrase mode: N random words from the embedded list")
    parser.add_argument("--separator", default="-", metavar="STR",
                        help="passphrase separator (default '-')")
    parser.add_argument("--entropy", action="store_true",
                        help="print estimated entropy bits (always included in --json)")
    parser.add_argument("--json", action="store_true",
                        help="emit {passwords: [...], entropy_bits: ...}")
    parser.add_argument("--no-color", action="store_true",
                        help="disable ANSI colors (also honors NO_COLOR)")
    parser.add_argument("--version", action="version", version="passgen " + __version__)
    opts = parser.parse_args(argv)
    color = not opts.no_color and not os.environ.get("NO_COLOR") and sys.stdout.isatty()

    if opts.count < 1:
        sys.stderr.write("passgen: --count must be >= 1\n")
        return 2
    passphrase = opts.words is not None
    if passphrase:
        if opts.words < 1:
            sys.stderr.write("passgen: --words must be >= 1\n")
            return 2
        items = [generate_passphrase(opts.words, opts.separator) for _ in range(opts.count)]
        bits = round(passphrase_entropy(opts.words), 2)
    else:
        if opts.length < 1:
            sys.stderr.write("passgen: --length must be >= 1\n")
            return 2
        classes = build_classes(opts.no_lower, opts.no_upper, opts.no_digits,
                                opts.no_symbols, opts.exclude_ambiguous)
        if not classes:
            sys.stderr.write("passgen: impossible charset: all character classes are disabled\n")
            return 2
        items = [generate_password(opts.length, classes) for _ in range(opts.count)]
        bits = round(password_entropy(opts.length, sum(len(c) for c in classes)), 2)
    print(report(items, bits if (opts.entropy or opts.json) else None,
                 color, opts.json, passphrase))
    return 0


if __name__ == "__main__":
    sys.exit(main())