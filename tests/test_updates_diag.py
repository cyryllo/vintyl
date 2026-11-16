"""
Tests of the new-version check, the applications menu entry and the
diagnostic report (no network: GitHub's answer is given by the test).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os

import pytest

from vintyl.core import diag, updates


def _rel(tag, pre=False, draft=False):
    return {"tag_name": tag, "prerelease": pre, "draft": draft, "html_url": "https://example.org/" + tag,
            "name": "Vintyl " + tag.lstrip("v")}


def test_versions_compare_with_pre_releases():
    order = ["0.1.0a1", "0.1.0a2", "0.1.0b1", "0.1.0rc1", "0.1.0", "0.1.1", "0.2.0a1", "1.0"]
    keys = [updates.version_key(v) for v in order]
    assert keys == sorted(keys)
    assert updates.is_prerelease("v0.1.0a1") and not updates.is_prerelease("0.1.0")
    with pytest.raises(ValueError):
        updates.version_key("nightly")


def test_a_pre_release_is_offered_only_to_pre_release_users():
    releases = [_rel("v0.1.0a1", True), _rel("v0.1.0a2", True), _rel("v0.0.9"), _rel("v0.3.0", draft=True)]
    got = updates.pick(releases, "0.1.0a1")
    assert got.version == "0.1.0a2" and got.prerelease
    assert updates.pick(releases, "0.1.0a2") is None                  # up to date
    assert updates.pick(releases, "0.0.9") is None                    # a released version: no alphas
    assert updates.pick(releases + [_rel("v0.1.0")], "0.0.9").version == "0.1.0"


def test_a_skipped_version_is_not_shown_again():
    fetch = lambda current, timeout: [_rel("v0.1.0a2", True)]
    assert updates.newer_release("0.1.0a1", fetch=fetch).version == "0.1.0a2"
    assert updates.newer_release("0.1.0a1", skipped="0.1.0a2", fetch=fetch) is None


def test_the_menu_entry_goes_into_the_users_folders(tmp_path, monkeypatch):
    from vintyl.gui import desktop_entry
    app = tmp_path / "Vintyl-0.1.0a1-x86_64.AppImage"
    app.write_text("")
    monkeypatch.setenv("APPIMAGE", str(app))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    assert desktop_entry.applies()
    ran = []
    written = desktop_entry.install(run=lambda cmd, **kw: ran.append(cmd[0]))
    names = {os.path.basename(p) for p in written}
    assert names == {"vintyl.desktop", "vintyl.xml", "vintyl.png"}
    assert desktop_entry.installed_for() == str(app)
    text = (tmp_path / "share" / "applications" / "vintyl.desktop").read_text()
    assert "Exec=%s %%F" % app in text and "application/x-vintyl" in text


def test_the_report_has_the_cutter_and_no_home_folder(monkeypatch, tmp_path):
    from vintyl.core import profile
    p = profile.load_builtin("vevor-ki-375a")
    text = diag.build_report("9.9", [("OK", "libraries", "fine")], p, {"view/theme": "dark"})
    assert "Vintyl 9.9" in text and "VEVOR KI-375A" in text and "/dev/usb/lp1" in text
    assert "OK    libraries" in text and "view/theme = dark" in text and "groups: lp " in text
    import grp, pwd
    me = pwd.getpwuid(os.getuid()).pw_name
    assert ("groups: lp" in text) and (" %s " % me not in text.split("groups:")[1].splitlines()[0] + " ")
    home = os.path.expanduser("~")
    if home not in ("/", ""):
        assert home not in text
    url = diag.issue_url("cutter", "9.9", "VEVOR KI-375A")
    assert url.startswith(diag.ISSUES_URL) and "cutter_report.yml" in url and "VEVOR+KI-375A" in url


def test_the_log_records_and_is_read_back(tmp_path, monkeypatch):
    monkeypatch.setattr(diag, "_handler", None)
    path = diag.setup("9.9")
    try:
        assert path and path.startswith(os.path.dirname(os.environ["VINTYL_SETTINGS"]))
        diag.log.info("a test line")
        for h in diag.log.handlers:
            h.flush()
        assert "a test line" in diag.read_log() and "Vintyl 9.9 started" in diag.read_log()
    finally:
        for h in list(diag.log.handlers):
            if isinstance(h, __import__("logging").handlers.RotatingFileHandler):
                diag.log.removeHandler(h)
                h.close()
        import sys
        import threading
        sys.excepthook = sys.__excepthook__
        threading.excepthook = threading.__excepthook__
