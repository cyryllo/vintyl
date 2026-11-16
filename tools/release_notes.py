"""
The notes of one version from CHANGELOG.md, for its GitHub release:

    python3 tools/release_notes.py v0.1.0a1 > notes.md

Prints the section "## 0.1.0a1 ..." up to the next "## " heading. Fails when
the version has no section, so a release is never published without notes.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os
import sys


def notes(version, text):
    version = version.lstrip("v")
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].split()[0].lstrip("v") == version if line[3:].split() else False
            continue
        if inside:
            out.append(line)
    if not inside and not out:
        raise SystemExit("CHANGELOG.md has no section for %s" % version)
    return "\n".join(out).strip() + "\n"


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8") as f:
        sys.stdout.write(notes(sys.argv[1], f.read()))
