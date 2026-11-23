#!/bin/sh
# Build vintyl_<version>_amd64.deb for Debian, Ubuntu, Mint and the like:
# the same program as the AppImage (its Python and Qt inside, made by
# PyInstaller), installed in /opt/vintyl with the command vintyl, the
# applications menu entry, the icons and the .vintyl file type.
#
#   packaging/linux/build-deb.sh
#
# Uses build/pyinstaller/dist/Vintyl when build-appimage.sh made it before
# (the release workflow), else runs PyInstaller (PYTHON, default
# .venv/bin/python). Needs dpkg-deb. Build it on Ubuntu 22.04
# (build-appimage-docker.sh does both): the package then runs on Ubuntu
# 22.04 and newer, Mint 21 and newer, Debian 12 and newer.
#
# Copyright (C) 2026 Vintyl contributors
# Licensed under the GNU General Public License v3 or later. See LICENSE.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-.venv/bin/python}"
VERSION="$(PYTHONPATH=src "$PYTHON" -c 'import vintyl; print(vintyl.__version__)')"
APP=build/pyinstaller/dist/Vintyl
if [ ! -x "$APP/vintyl" ]; then
    "$PYTHON" -m PyInstaller packaging/vintyl.spec --noconfirm --distpath build/pyinstaller/dist \
        --workpath build/pyinstaller/work
fi

PKG="build/deb/vintyl_${VERSION}_amd64"
rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share/applications" \
    "$PKG/usr/share/mime/packages" "$PKG/usr/share/doc/vintyl" "$PKG/usr/share/icons/hicolor/scalable/apps"
cp -a "$APP" "$PKG/opt/vintyl"
ln -s ../../opt/vintyl/vintyl "$PKG/usr/bin/vintyl"
cp packaging/linux/vintyl.desktop "$PKG/usr/share/applications/vintyl.desktop"
cp packaging/linux/vintyl-mime.xml "$PKG/usr/share/mime/packages/vintyl.xml"
for s in 16 32 48 64 128 256 512; do
    mkdir -p "$PKG/usr/share/icons/hicolor/${s}x${s}/apps"
    cp "assets/ikona/vintyl-$s.png" "$PKG/usr/share/icons/hicolor/${s}x${s}/apps/vintyl.png"
done
cp assets/ikona/vintyl.svg "$PKG/usr/share/icons/hicolor/scalable/apps/vintyl.svg"
cat > "$PKG/usr/share/doc/vintyl/copyright" <<EOF
Vintyl $VERSION: software to cut and draw with vinyl cutters.
https://github.com/cyryllo/vintyl

Copyright (C) 2026 Vintyl contributors (parts from Kerfly, Kerfly contributors).
Licensed under the GNU General Public License v3 or later:
/usr/share/common-licenses/GPL-3. The libraries inside /opt/vintyl and their
licences: /opt/vintyl/_internal/licenses and THIRD-PARTY-NOTICES.md in the
source.
EOF

# the menu, the file types and the icons are taken in by the system's own
# triggers (desktop-file-utils, shared-mime-info, hicolor-icon-theme)
SIZE="$(du -sk "$PKG" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<EOF
Package: vintyl
Version: $VERSION
Architecture: amd64
Maintainer: Vintyl contributors <https://github.com/cyryllo/vintyl/issues>
Installed-Size: $SIZE
Depends: libc6 (>= 2.35), libegl1, libgl1, libfontconfig1, libdbus-1-3, libxkbcommon0, libxkbcommon-x11-0,
 libxcb-cursor0, libglib2.0-0 | libglib2.0-0t64
Recommends: fonts-noto-core | fonts-dejavu-core
Section: graphics
Priority: optional
Homepage: https://cyryllo.github.io/vintyl/
Description: software to cut and draw with vinyl cutters
 Vintyl drives drag-knife vinyl cutters (VEVOR, Seiki and the many models
 on the same board): draw a design or open an SVG, DXF or picture, lay it
 out on the sheet as the material lies in the cutter, and cut it with the
 knife or draw it with a pen, straight from the window.
EOF

mkdir -p dist
OUT="dist/vintyl_${VERSION}_amd64.deb"
dpkg-deb --root-owner-group --build "$PKG" "$OUT"
echo "Written: $OUT"
