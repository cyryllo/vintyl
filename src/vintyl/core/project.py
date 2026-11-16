"""
Vintyl project files (.vintyl): the whole design and the job's settings.

A project is JSON text (readable, and easy to repair by hand):
    {"format": "vintyl", "version": 1,
     "elements": [{"name", "paths", "cut", "source", "spec", "group", "fill"}, ...],
     "settings": {"profile": ..., "knife_offset_mm": ..., ...}}
paths are curves subpaths (vintyl.core.curves) in view mm. "settings" holds
what the window wants to keep with the design; this module does not look
inside it.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import json
import os

from .design import Design, Element
from ..i18n import _

FORMAT = "vintyl"
VERSION = 1
EXTENSION = ".vintyl"


class ProjectError(ValueError):
    """The file cannot be opened; the message is safe to show the user."""


def to_dict(design, settings=None):
    return {
        "format": FORMAT,
        "version": VERSION,
        "elements": [{"name": e.name, "paths": e.paths, "cut": e.cut, "source": e.source,
                      "spec": e.spec, "group": e.group, "fill": e.fill} for e in design.elements],
        "settings": dict(settings or {}),
    }


def save(path, design, settings=None):
    """Write the project; written to a temporary file first and then renamed,
    so a crash while saving never leaves half a project."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(to_dict(design, settings), f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _node(n):
    if not isinstance(n, list) or len(n) != 6:
        raise ValueError
    x, y = float(n[0]), float(n[1])
    out = [x, y, None, None, None, None]
    for k in (2, 4):
        if n[k] is not None:
            out[k], out[k + 1] = float(n[k]), float(n[k + 1])
    return out


def _fill(f):
    """A fill pattern from the file (None when there is none)."""
    if not f:
        return None
    from .patterns import PATTERN_CODES
    if not isinstance(f, dict) or f.get("pattern") not in PATTERN_CODES or float(f.get("spacing", 0)) <= 0:
        raise ValueError
    return {"pattern": f["pattern"], "spacing": float(f["spacing"]), "angle": float(f.get("angle", 0.0)),
            "margin": float(f.get("margin", 0.0))}


def from_dict(data, name="project"):
    """(Design, settings) from the JSON data; ProjectError when it is not a
    Vintyl project or is damaged."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ProjectError(_("%s is not a Vintyl project.") % name)
    if int(data.get("version", 0)) > VERSION:
        raise ProjectError(_("%s was saved by a newer Vintyl; please update Vintyl to open it.") % name)
    design = Design()
    try:
        for e in data.get("elements", []):
            paths = [{"closed": bool(sub["closed"]), "nodes": [_node(n) for n in sub["nodes"]]}
                     for sub in e["paths"]]
            design.elements.append(Element(str(e.get("name", "")), paths, bool(e.get("cut", True)),
                                           str(e.get("source", "")), e.get("spec") or None,
                                           str(e.get("group", "")), _fill(e.get("fill"))))
    except (KeyError, TypeError, ValueError, IndexError):
        raise ProjectError(_("%s is damaged: an element cannot be read.") % name) from None
    settings = data.get("settings") or {}
    return design, settings if isinstance(settings, dict) else {}


def load(path):
    name = os.path.basename(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, UnicodeDecodeError) as e:
        raise ProjectError(_("Cannot open %s: %s") % (name, getattr(e, "strerror", None) or e)) from None
    except json.JSONDecodeError:
        raise ProjectError(_("%s is damaged: it is not readable as a project.") % name) from None
    return from_dict(data, name)
