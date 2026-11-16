# PyInstaller build of Vintyl: one folder with the program and all its
# libraries. Run from the repository root:
#
#     pyinstaller packaging/vintyl.spec --noconfirm
#
# Result: dist/Vintyl/ with "vintyl" (the program). The AppImage
# (packaging/linux/build-appimage.sh) is made from that folder.
# After Kerfly's packaging/kerfly.spec (https://github.com/cyryllo/Kerfly,
# commit cf48565), without its Windows, macOS and USB-driver parts.
#
# Copyright (C) 2026 Kerfly contributors, Vintyl contributors
# Licensed under the GNU General Public License v3 or later. See LICENSE.
import glob
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
SRC = os.path.join(ROOT, "src")


def files(pattern):
    """(source, folder in the package) for every file matching the pattern:
    the same folder as under src/, where the program looks for it."""
    return [(path, os.path.dirname(os.path.relpath(path, SRC)))
            for path in glob.glob(os.path.join(SRC, pattern))]


datas = (files("vintyl/locale/*/LC_MESSAGES/*.mo")
         + files("vintyl/core/profiles/*.toml")
         + files("vintyl/gui/icons/*.svg")
         + files("vintyl/gui/icons/tabler/*.svg")
         + files("vintyl/gui/icons/tabler/LICENSE")
         + [(os.path.join(ROOT, name), ".") for name in ("LICENSE", "THIRD-PARTY-NOTICES.md")]
         + [(os.path.join(ROOT, "packaging", "licenses", "LGPL-3.0.txt"), "licenses")])   # Qt, PySide6

# the licence texts of the bundled libraries travel with them (their package metadata)
from PyInstaller.utils.hooks import copy_metadata
for dist in ("PySide6_Essentials", "shiboken6", "pyserial", "pyclipper", "segno", "svgelements"):
    datas += copy_metadata(dist)

a = Analysis(
    [os.path.join(ROOT, "packaging", "vintyl_start.py")],
    pathex=[SRC],
    datas=datas,
    hiddenimports=["PySide6.QtSvg", "serial", "serial.tools.list_ports", "segno", "svgelements", "pyclipper",
                   "vintyl.selftest"],
    excludes=["tkinter", "_tkinter",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="vintyl", console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Vintyl")
