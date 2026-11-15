#!/usr/bin/env python3
"""
Update Vintyl translations.

    python tools/i18n.py            extract texts, update every .po, compile .mo
    python tools/i18n.py --check    fail if a translation is missing or broken

Needs Babel (pip install -e '.[dev]'). Translators edit
src/vintyl/locale/<lang>/LC_MESSAGES/vintyl.po (e.g. with Poedit), then run
this script to compile the .mo files that Vintyl loads.

Source: adapted from Kerfly (tools/i18n.py, commit cf48565).

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
LOCALE = os.path.join(SRC, "vintyl", "locale")
POT = os.path.join(LOCALE, "vintyl.pot")
sys.path.insert(0, SRC)
from vintyl.i18n import LANGUAGES  # noqa: E402

PYBABEL = os.path.join(os.path.dirname(sys.executable), "pybabel")


def run(*args):
    subprocess.run([PYBABEL, "-q"] + list(args), check=True, cwd=ROOT)


def extract():
    os.makedirs(LOCALE, exist_ok=True)
    run("extract", "-k", "_", "-k", "N_", "-k", "ngettext:1,2", "--no-location", "--sort-output",
        "--project", "Vintyl", "--copyright-holder", "Vintyl contributors",
        "--msgid-bugs-address", "https://github.com/cyryllo/vintyl/issues",
        "-o", POT, os.path.join("src", "vintyl"))


def update():
    for lang in LANGUAGES:
        if lang == "en":
            continue
        po = os.path.join(LOCALE, lang, "LC_MESSAGES", "vintyl.po")
        if os.path.exists(po):
            run("update", "--no-fuzzy-matching", "-D", "vintyl", "-i", POT, "-d", LOCALE, "-l", lang)
        else:
            run("init", "-D", "vintyl", "-i", POT, "-d", LOCALE, "-l", lang)


def compile_all():
    run("compile", "-D", "vintyl", "-d", LOCALE, "--statistics")


def check():
    """Every message translated, same %-placeholders as the English text."""
    from babel.messages.pofile import read_po
    placeholder = re.compile(r"%(?:\([^)]*\))?[-#0 +]*\d*(?:\.\d+)?[sdrfgx%]")
    problems = 0
    for lang in LANGUAGES:
        if lang == "en":
            continue
        with open(os.path.join(LOCALE, lang, "LC_MESSAGES", "vintyl.po"), "rb") as f:
            catalog = read_po(f)
        for msg in catalog:
            if not msg.id:
                continue
            ids = msg.id if isinstance(msg.id, tuple) else (msg.id,)
            strings = msg.string if isinstance(msg.string, tuple) else (msg.string,)
            if msg.fuzzy or not all(strings) or (len(ids) > 1 and len(strings) != catalog.num_plurals):
                print("%s: missing translation: %r" % (lang, ids[0]))
                problems += 1
                continue
            expected = sorted(placeholder.findall(ids[-1]))
            for text in strings:
                if sorted(placeholder.findall(text)) != expected:
                    print("%s: placeholders differ: %r -> %r" % (lang, ids[0], text))
                    problems += 1
    print("%d problem(s)" % problems if problems else "All translations complete.")
    return problems


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(1 if check() else 0)
    extract()
    update()
    compile_all()
