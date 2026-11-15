"""
Translations (gettext). English is the language of the source; other
languages come from vintyl/locale/<lang>/LC_MESSAGES/vintyl.po (+ .mo).

Usage in any module (the core too: gettext is in the standard library):
    from vintyl.i18n import _, N_, ngettext
    label = _("Knife offset")
    NAMES = [N_("Rectangle")]               # marked now, translated later with _()
    text = ngettext("%d element", "%d elements", n) % n

After changing texts:  python tools/i18n.py

Source: adapted from Kerfly (kerfly/i18n.py, commit cf48565): the same
functions, without Kerfly's messages of the K40 laser modules.

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import gettext
import locale
import os

DOMAIN = "vintyl"
LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale")

# code -> name shown in the language list (in that language)
LANGUAGES = {
    "en": "English",
    "pl": "Polski",
}

_translation = gettext.NullTranslations()
_current = "en"


def _(message):
    return _translation.gettext(message)


def ngettext(singular, plural, n):
    return _translation.ngettext(singular, plural, n)


def N_(message):
    """Mark a string for translation without translating it yet."""
    return message


def system_language():
    """Two-letter code of the system language if Vintyl has it, else 'en'."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            code = value.split(":")[0][:2].lower()
            return code if code in LANGUAGES else "en"
    try:
        code = (locale.getlocale()[0] or "en")[:2].lower()
    except ValueError:
        code = "en"
    return code if code in LANGUAGES else "en"


def setup(language=""):
    """Activate a language ('' = the system language). Returns the code used."""
    global _translation, _current
    code = language if language in LANGUAGES else system_language()
    _translation = gettext.translation(DOMAIN, LOCALE_DIR, languages=[code], fallback=True)
    _current = code
    return code


def current_language():
    return _current
