#!/bin/sh
# Build Vintyl-<version>-x86_64.AppImage: one file that runs on most Linux
# systems without installing anything (the program, Python and Qt inside).
#
#   APPIMAGETOOL=/path/to/appimagetool packaging/linux/build-appimage.sh
#
# Needs a Python environment with Vintyl's libraries and PyInstaller
# (PYTHON, default .venv/bin/python) and appimagetool
# (https://github.com/AppImage/appimagetool). Build it on an old system
# (Ubuntu 22.04: build-appimage-docker.sh, or the release workflow), so the
# AppImage also runs on older systems.
# After Kerfly's packaging/linux/build-appimage.sh (commit cf48565).
#
# Copyright (C) 2026 Kerfly contributors, Vintyl contributors
# Licensed under the GNU General Public License v3 or later. See LICENSE.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-.venv/bin/python}"
TOOL="${APPIMAGETOOL:-appimagetool}"
VERSION="$(PYTHONPATH=src "$PYTHON" -c 'import vintyl; print(vintyl.__version__)')"

"$PYTHON" -m PyInstaller packaging/vintyl.spec --noconfirm --distpath build/pyinstaller/dist \
    --workpath build/pyinstaller/work

APPDIR=build/Vintyl.AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
    "$APPDIR/usr/share/mime/packages"
cp -a build/pyinstaller/dist/Vintyl "$APPDIR/usr/lib/vintyl"
cp packaging/linux/vintyl.desktop "$APPDIR/vintyl.desktop"
cp packaging/linux/vintyl.desktop "$APPDIR/usr/share/applications/vintyl.desktop"
cp packaging/linux/vintyl-mime.xml "$APPDIR/usr/share/mime/packages/vintyl.xml"
cp assets/ikona/vintyl-256.png "$APPDIR/vintyl.png"
cp assets/ikona/vintyl-256.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/vintyl.png"
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
# start Vintyl from inside the AppImage
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/vintyl/vintyl" "$@"
RUN
chmod +x "$APPDIR/AppRun"

mkdir -p dist
OUT="dist/Vintyl-$VERSION-x86_64.AppImage"
# --appimage-extract-and-run: works without FUSE (containers, CI)
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT"
echo "Written: $OUT"
