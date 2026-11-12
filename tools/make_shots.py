#!/usr/bin/env python3
"""Regenerate docs/passwords.png and docs/passphrase.png from real CLI output.

Run: python tools/make_shots.py   (requires Pillow)
The passwords shown are freshly generated throwaway examples; nothing is
stored except the rendered demo images.
"""
import contextlib
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import passgen as pg
import render_terminal as rt


class TtyOut(io.StringIO):
    """The CLI colors output on a tty; claim to be one so shots show real ANSI."""

    def isatty(self):
        return True


def cli_output(args):
    out = TtyOut()
    with contextlib.redirect_stdout(out):
        code = pg.main(args)
    if code != 0:
        raise SystemExit("passgen %r exited %d" % (args, code))
    return out.getvalue().rstrip("\n")


def render(name, ansi, cmd, title):
    rt.render(rt.parse_ansi(ansi), title, cmd, os.path.join(ROOT, "docs", name + ".png"))


def main():
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    os.environ.pop("NO_COLOR", None)
    render("passwords", cli_output(["--count", "3", "--length", "20", "--entropy"]),
           "python passgen.py --count 3 --length 20 --entropy", "passgen — passwords")
    render("passphrase", cli_output(["--words", "5", "--count", "2", "--entropy"]),
           "python passgen.py --words 5 --count 2 --entropy", "passgen — passphrases")


if __name__ == "__main__":
    main()