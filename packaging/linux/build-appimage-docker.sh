#!/bin/sh
# Build and check the AppImage and the .deb package on this computer, in an
# Ubuntu 22.04 container, the way the release workflow does on GitHub. Ubuntu 22.04 keeps
# the AppImage running on older systems; built straight on a newer system it
# would not start there.
#
#   packaging/linux/build-appimage-docker.sh [tag or commit, default: HEAD]
#   packaging/linux/build-appimage-docker.sh .      (the working tree, not yet committed)
#
# Needs Docker. Builds from a clean copy of that version (git archive), runs
# the AppImage's --self-test, and writes it to dist/.
# After Kerfly's packaging/linux/build-appimage-docker.sh (commit cf48565).
#
# Copyright (C) 2026 Kerfly contributors, Vintyl contributors
# Licensed under the GNU General Public License v3 or later. See LICENSE.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF="${1:-HEAD}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/vintyl-appimage-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/src"
if [ "$REF" = "." ]; then
    # the files git knows or would add (not the ignored ones: .venv, build, dist)
    (cd "$ROOT" && git ls-files -co --exclude-standard -z | xargs -0 tar -c) | tar -x -C "$WORK/src"
else
    git -C "$ROOT" archive "$REF" | tar -x -C "$WORK/src"
fi
cat > "$WORK/inside.sh" <<'INSIDE'
#!/bin/bash
# inside ubuntu:22.04
set -eux
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends software-properties-common gpg-agent curl ca-certificates \
    binutils file libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 \
    libglib2.0-0 fonts-dejavu-core libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 \
    libxcb-xinerama0 libxcb-randr0 libxcb-render-util0 libxcb-image0
add-apt-repository -y ppa:deadsnakes/ppa          # Python 3.13, as on GitHub
apt-get update
apt-get install -y --no-install-recommends python3.13 python3.13-venv python3.13-dev
cd /work/src
python3.13 -m venv /venv
/venv/bin/python -m pip install --upgrade pip
/venv/bin/python -m pip install ".[gui]" pyinstaller
curl -fsSL -o /work/appimagetool \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x /work/appimagetool
PYTHON=/venv/bin/python APPIMAGETOOL=/work/appimagetool packaging/linux/build-appimage.sh
chmod +x dist/*.AppImage
QT_QPA_PLATFORM=offscreen dist/Vintyl-*-x86_64.AppImage --appimage-extract-and-run --self-test
PYTHON=/venv/bin/python packaging/linux/build-deb.sh          # the same program as a .deb
cp dist/Vintyl-*-x86_64.AppImage dist/vintyl_*_amd64.deb /work/
chown -R "$HOST_UID:$HOST_GID" /work          # everything back to the user (the container runs as root)
INSIDE
chmod +x "$WORK/inside.sh"
docker run --rm -v "$WORK:/work" -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" ubuntu:22.04 /work/inside.sh
mkdir -p "$ROOT/dist"
cp "$WORK"/Vintyl-*-x86_64.AppImage "$WORK"/vintyl_*_amd64.deb "$ROOT/dist/"
echo "Written: $(ls "$ROOT"/dist/Vintyl-*-x86_64.AppImage | tail -1)"
echo "Written: $(ls "$ROOT"/dist/vintyl_*_amd64.deb | tail -1)"
