"""
Is there a newer Vintyl? One request to GitHub's public list of releases.
Nothing about the user or the work is sent: only the usual request with the
program's name and version (so GitHub sees the computer's address, as with
any web page).

A pre-release (0.1.0a1, 0.2.0rc1) is offered only to someone who already
runs a pre-release; a released version only gets released ones.

Adapted from Kerfly (kerfly/core/updates.py, commit cf48565): Vintyl's
repository, pre-releases, versions such as 0.1.0a1.

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import json
import os
import re
import ssl
import urllib.request

RELEASES_API = "https://api.github.com/repos/cyryllo/vintyl/releases?per_page=20"
RELEASES_URL = "https://github.com/cyryllo/vintyl/releases"
CHECK_EVERY_S = 24 * 3600            # at most once a day at start

# certificate bundles of the usual systems: the AppImage carries an OpenSSL
# built on Ubuntu, which looks for them only where Ubuntu keeps them
CA_FILES = ("/etc/ssl/certs/ca-certificates.crt",      # Debian, Ubuntu, Arch, Gentoo
            "/etc/pki/tls/certs/ca-bundle.crt",         # Fedora, RHEL
            "/etc/ssl/ca-bundle.pem",                   # openSUSE
            "/etc/ssl/cert.pem")                        # Alpine

_STAGES = {"a": -3, "alpha": -3, "b": -2, "beta": -2, "rc": -1, "c": -1}


class Release:
    def __init__(self, version, url, name="", prerelease=False):
        self.version = version           # "0.1.0a2"
        self.url = url                   # its page
        self.name = name or "Vintyl " + version
        self.prerelease = prerelease


def version_key(text):
    """A comparable key: 'v0.1.0a1' < '0.1.0b2' < '0.1.0rc1' < '0.1.0' < '0.1.1'."""
    m = re.match(r"v?(\d+(?:\.\d+)*)(?:[-.]?(a|alpha|b|beta|rc|c)\.?(\d*))?", str(text).strip().lower())
    if not m:
        raise ValueError("not a version: %r" % (text,))
    numbers = tuple(int(p) for p in m.group(1).split("."))
    numbers += (0,) * (4 - len(numbers))
    stage = (_STAGES[m.group(2)], int(m.group(3) or 0)) if m.group(2) else (0, 0)
    return numbers + stage


def is_prerelease(text):
    return version_key(text)[-2] < 0


def is_newer(candidate, current):
    return version_key(candidate) > version_key(current)


def pick(releases, current):
    """The newest release from GitHub's JSON list that this user should be
    offered (see the module notes), newer than current; or None."""
    allow_pre = is_prerelease(current)
    best = None
    for data in releases or []:
        if not isinstance(data, dict) or data.get("draft"):
            continue
        tag = data.get("tag_name") or ""
        try:
            key = version_key(tag)
        except ValueError:
            continue
        pre = bool(data.get("prerelease")) or key[-2] < 0
        if pre and not allow_pre:
            continue
        if best is None or key > best[0]:
            best = (key, Release(tag.lstrip("v"), data.get("html_url") or RELEASES_URL, data.get("name") or "",
                                 pre))
    if best is None or not is_newer(best[1].version, current):
        return None
    return best[1]


def _context():
    ctx = ssl.create_default_context()
    if not ctx.get_ca_certs():
        for path in CA_FILES:
            if os.path.isfile(path):
                ctx.load_verify_locations(cafile=path)
                break
    return ctx


def fetch_releases(current_version, timeout=6.0):
    """GitHub's list of releases (raises OSError / ValueError: no internet,
    GitHub not answering, an unexpected answer)."""
    request = urllib.request.Request(RELEASES_API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "Vintyl/%s (update check)" % current_version})
    with urllib.request.urlopen(request, timeout=timeout, context=_context()) as answer:
        data = json.loads(answer.read().decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("unexpected answer from GitHub")
    return data


def newer_release(current_version, skipped="", timeout=6.0, fetch=None):
    """The release to tell the user about, or None (up to date, or the user
    skipped that version). fetch replaces fetch_releases (tests)."""
    release = pick((fetch or fetch_releases)(current_version, timeout=timeout), current_version)
    if release is None:
        return None
    if skipped and not is_newer(release.version, skipped):
        return None
    return release
