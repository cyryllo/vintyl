"""
Test set-up: the window's settings go to a file of their own, never to the
user's (~/.config/Vintyl).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os
import tempfile

import pytest

_DIR = tempfile.mkdtemp(prefix="vintyl-test-settings-")


@pytest.fixture(autouse=True)
def own_settings(monkeypatch, tmp_path):
    """Every test starts with empty settings of its own."""
    monkeypatch.setenv("VINTYL_SETTINGS", str(tmp_path / "settings.ini"))


os.environ.setdefault("VINTYL_SETTINGS", os.path.join(_DIR, "settings.ini"))
