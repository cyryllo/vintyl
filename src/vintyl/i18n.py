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
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "pt_BR": "Português (Brasil)",
}
# a system in Portuguese gets the Brazilian translation (the only Portuguese one)
_SAME = {"pt": "pt_BR"}
# languages that write a decimal comma (1,5 mm)
DECIMAL_COMMA = ("pl", "de", "es", "fr", "pt_BR")

_translation = gettext.NullTranslations()
_current = "en"


def _(message):
    return _translation.gettext(message)


def ngettext(singular, plural, n):
    return _translation.ngettext(singular, plural, n)


def pgettext(context, message):
    """A text in a context, translated on its own: pgettext("ribbon",
    "Save .hpgl") may be shorter than the menu's "Save .hpgl" (the ribbon
    must fit a 1366 px screen in every language)."""
    return _translation.pgettext(context, message)


def N_(message):
    """Mark a string for translation without translating it yet."""
    return message


def NP_(context, message):
    """Mark a string in a context, translated later with pgettext(context, ...)."""
    return message


def _known(value):
    """The code of a locale name ("de_DE.UTF-8", "pt_BR", "fr") that Vintyl
    has, else 'en': the full code first (pt_BR), then the two letters."""
    name = value.split(":")[0].split(".")[0]
    if name in LANGUAGES:
        return name
    code = name[:2].lower()
    code = _SAME.get(code, code)
    return code if code in LANGUAGES else "en"


def system_language():
    """The code of the system language if Vintyl has it, else 'en'."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return _known(value)
    try:
        return _known(locale.getlocale()[0] or "en")
    except ValueError:
        return "en"


def setup(language=""):
    """Activate a language ('' = the system language). Returns the code used."""
    global _translation, _current
    code = language if language in LANGUAGES else system_language()
    _translation = gettext.translation(DOMAIN, LOCALE_DIR, languages=[code], fallback=True)
    _current = code
    return code


def current_language():
    return _current


def decimal(text):
    """A number written as the language does: 1,5 in Polish, German..."""
    return text.replace(".", ",") if _current in DECIMAL_COMMA else text
