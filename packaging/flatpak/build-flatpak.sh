#!/bin/sh
# Build dist/Vintyl-<version>-x86_64.flatpak (one file to install with
# `flatpak install --user Vintyl-...flatpak`) from io.github.cyryllo.Vintyl.yml.
#
#   packaging/flatpak/build-flatpak.sh
#
# Runs where flatpak and flatpak-builder are: Flathub's builder image
# (ghcr.io/flathub-infra/flatpak-github-actions:kde-6.11, as root, privileged),
# as the release workflow does. What the manifest builds on is installed when
# missing, never updated in place: an update fails in a container's file
# system ("Invalid cross-device link"). rofiles-fuse is not used: a container
# has no FUSE.
#
# Copyright (C) 2026 Vintyl contributors
# Licensed under the GNU General Public License v3 or later. See LICENSE.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
MANIFEST=packaging/flatpak/io.github.cyryllo.Vintyl.yml
QT="$(sed -n "s/^runtime-version: '\(.*\)'/\1/p" "$MANIFEST")"          # 6.11, as the manifest says
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)"

flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
for ref in "org.kde.Platform//$QT" "org.kde.Sdk//$QT" "io.qt.PySide.BaseApp//$QT"; do
    flatpak info "$ref" >/dev/null 2>&1 || flatpak install -y --noninteractive flathub "$ref"
done
flatpak-builder --disable-rofiles-fuse --force-clean --repo=build/flatpak-repo build/flatpak "$MANIFEST"
mkdir -p dist
OUT="dist/Vintyl-$VERSION-x86_64.flatpak"
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo build/flatpak-repo "$OUT" \
    io.github.cyryllo.Vintyl
echo "Written: $OUT"
