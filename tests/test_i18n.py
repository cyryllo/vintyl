"""
Translations: every text shown is translated, placeholders match, the
catalogue is up to date with the code, and the window really speaks Polish.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pytest.importorskip("babel")


def test_every_translation_complete_with_the_same_placeholders():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "i18n.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_catalogue_matches_the_code(tmp_path):
    """No text in the code is missing from vintyl.pot (run tools/i18n.py after changing texts)."""
    from babel.messages.pofile import read_po
    pybabel = os.path.join(os.path.dirname(sys.executable), "pybabel")
    fresh = tmp_path / "fresh.pot"
    subprocess.run([pybabel, "-q", "extract", "-k", "_", "-k", "N_", "-k", "ngettext:1,2", "-k", "pgettext:1c,2",
                    "-k", "NP_:1c,2", "--no-location", "-o", str(fresh), os.path.join("src", "vintyl")],
                   check=True, cwd=ROOT)
    # a text with its context: the ribbon's and the tool strip's words are their own
    with open(fresh, "rb") as f:
        new = {(m.context, m.id) for m in read_po(f) if m.id}
    with open(os.path.join(ROOT, "src", "vintyl", "locale", "vintyl.pot"), "rb") as f:
        old = {(m.context, m.id) for m in read_po(f) if m.id}
    assert new == old, "run: python tools/i18n.py  (new: %s, gone: %s)" % (new - old, old - new)


def test_polish_plurals_and_core_messages():
    from vintyl import i18n
    from vintyl.core.job import JobError, build_job
    from vintyl.core.profile import Profile
    try:
        assert i18n.setup("pl") == "pl"
        assert [i18n.ngettext("%d element", "%d elements", n) % n for n in (1, 3, 5, 22)] == \
            ["1 element", "3 elementy", "5 elementów", "22 elementy"]
        with pytest.raises(JobError, match="nie mieści się na folii"):
            build_job([[(0, 0), (0, 120)]], Profile(width_mm=100))
    finally:
        i18n.setup("en")


def test_window_in_polish():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from vintyl import i18n
    QApplication.instance() or QApplication([])
    try:
        i18n.setup("pl")
        from vintyl.gui.main_window import MainWindow
        w = MainWindow()
        assert w.btn_save.text() == "Zapisz .hpgl"
        assert w.inside_first.text() == "Najpierw kształty wewnętrzne"
        assert w.summary.text().startswith("Pusto")
        w.close()
    finally:
        i18n.setup("en")


@pytest.mark.parametrize("lang,word", [("de", "Messertest"), ("es", "Prueba de cuchilla"), ("fr", "Test de lame"),
                                       ("pt_BR", "Teste da lâmina"), ("pl", "Test noża")])
def test_every_language_loads_and_translates(lang, word):
    from vintyl import i18n
    try:
        assert i18n.setup(lang) == lang
        assert i18n._("Knife test") == word
    finally:
        i18n.setup("en")


def test_the_system_language_and_the_decimal_comma(monkeypatch):
    from vintyl import i18n
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES"):
        monkeypatch.delenv(var, raising=False)
    for value, code in (("pt_PT.UTF-8", "pt_BR"), ("pt_BR.UTF-8", "pt_BR"), ("de_DE.UTF-8", "de"),
                        ("fr_CA.UTF-8", "fr"), ("ja_JP.UTF-8", "en"), ("pl_PL.UTF-8", "pl")):
        monkeypatch.setenv("LANG", value)
        assert i18n.system_language() == code, value
    try:
        for lang, text in (("de", "1,5 mm"), ("pt_BR", "1,5 mm"), ("en", "1.5 mm")):
            i18n.setup(lang)
            assert i18n.decimal("1.5 mm") == text
    finally:
        i18n.setup("en")
