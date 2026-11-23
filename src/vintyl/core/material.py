"""
Materials: how to cut (or draw) one kind of material.

A material holds what changes with the material, not with the machine:
the tool (knife or pen), the force and the speed for each cutter (a cutter
set on its panel only gets them shown before Start, see vintyl.gui), the
blade and the knife offset and overcut (empty: the cutter's own values), the
pen's width and where its stroke lies, whether the job is mirrored (heat
transfer vinyl) and framed for weeding, and a note shown before Start.

Like the cutter profiles (vintyl.core.profile): built-in materials live in
vintyl/core/materials/ (starting forces and speeds for the cutters with
the XILI board, each with its source in the file's comment),
the user's own in user_dir() (by default ~/.config/vintyl/materials); a
user's file with a built-in one's name is that material as the user changed
it, and deleting it brings the built-in one back.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math
import os
import re
import tomllib
from dataclasses import dataclass, field, fields
from importlib import resources

from ..i18n import N_

# the built-in materials' names and notes, so they are translated in the window
BUILTIN_NAMES = (N_("Vinyl film"), N_("Heat transfer vinyl (flex)"), N_("Reflective vinyl"),
                 N_("Card for cutting"), N_("Paper for cutting"),
                 N_("Paper, fineliner"), N_("Card, marker"),
                 N_("Shiny side (the carrier) down, the matt side up to the knife."),
                 N_("Starting values: check them with the knife test."),
                 N_("Set the force and speed with the knife test: start low and add until it cuts through."))

BUILTIN_ORDER = ("vinyl", "htv", "reflective", "card-cut", "paper-cut", "paper", "card")
# built-in materials without a force and speed yet (no source gives them for the
# XILI cutters): set with the knife test, written in when the owner has tested them
BUILTIN_UNTESTED = ("card-cut", "paper-cut")

TOOLS = ("knife", "pen")
BLADES = ("", "45", "30", "60")       # "" = not said
PEN_PLACES = ("on", "outside", "inside")


class MaterialError(ValueError):
    """A material that cannot be used; the message is safe to show the user."""


@dataclass
class Material:
    name: str = "Material"
    tool: str = "knife"
    # cutter profile id -> {"force_g": number or None, "speed_cm_s": number or None}
    per_cutter: dict = field(default_factory=dict)
    blade: str = ""
    knife_offset_mm: float | None = None    # None: the cutter's own value
    overcut_mm: float | None = None
    pen_width_mm: float | None = None       # None: as the window has it
    pen_place: str = "on"
    mirror: bool = False
    weed_frame: bool = False
    note: str = ""

    def validate(self):
        """Raise MaterialError listing every problem, or return self."""
        problems = []

        def need(ok, text):
            if not ok:
                problems.append(text)

        need(isinstance(self.name, str) and self.name.strip(), "name must not be empty")
        need(self.tool in TOOLS, "tool must be one of: " + ", ".join(TOOLS))
        need(self.blade in BLADES, "blade must be one of: 45, 30, 60 or empty")
        need(self.pen_place in PEN_PLACES, "pen_place must be one of: " + ", ".join(PEN_PLACES))
        for key in ("knife_offset_mm", "overcut_mm"):
            v = getattr(self, key)
            need(v is None or (_number(v) and v >= 0), key + " must be 0 or more, or left out")
        need(self.pen_width_mm is None or (_number(self.pen_width_mm) and self.pen_width_mm > 0),
             "pen_width_mm must be above 0, or left out")
        for key in ("mirror", "weed_frame"):
            need(isinstance(getattr(self, key), bool), key + " must be true or false")
        need(isinstance(self.note, str), "note must be text")
        need(isinstance(self.per_cutter, dict), "per_cutter must be a table")
        for pid, values in (self.per_cutter or {}).items():
            if not isinstance(values, dict):
                problems.append("per_cutter.%s must be a table" % pid)
                continue
            for key in values:
                need(key in ("force_g", "speed_cm_s"), "per_cutter.%s: unknown key %s" % (pid, key))
            for key in ("force_g", "speed_cm_s"):
                v = values.get(key)
                need(v is None or (_number(v) and v > 0), "per_cutter.%s.%s must be above 0" % (pid, key))
        if problems:
            raise MaterialError("Material \"%s\": %s." % (self.name, "; ".join(problems)))
        return self

    def for_cutter(self, pid):
        """(force_g, speed_cm_s) for the cutter `pid`, each None when not set."""
        values = (self.per_cutter or {}).get(pid) or {}
        return values.get("force_g"), values.get("speed_cm_s")


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


_FIELDS = {f.name: f for f in fields(Material)}


def from_dict(data, source="material"):
    unknown = sorted(set(data) - set(_FIELDS))
    if unknown:
        raise MaterialError("%s: unknown keys: %s." % (source, ", ".join(unknown)))
    values = dict(data)
    for key in ("knife_offset_mm", "overcut_mm", "pen_width_mm"):
        if values.get(key) == "":
            values[key] = None
        elif isinstance(values.get(key), int) and not isinstance(values.get(key), bool):
            values[key] = float(values[key])
    if "blade" in values:
        values["blade"] = str(values["blade"])
    per = {}
    for pid, v in (values.get("per_cutter") or {}).items():
        per[str(pid)] = {k: (float(x) if isinstance(x, int) and not isinstance(x, bool) else x)
                         for k, x in (v or {}).items()} if isinstance(v, dict) else v
    values["per_cutter"] = per
    try:
        return Material(**values).validate()
    except TypeError as e:
        raise MaterialError("%s: %s" % (source, e)) from None


def load(path):
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise MaterialError("%s: %s" % (path, e)) from None
    return from_dict(data, str(path))


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return '"%s"' % str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def to_toml(material):
    """The material as TOML text: the keys, then a table per cutter. Values
    that are not set are left out."""
    material.validate()
    lines = []
    for key in _FIELDS:
        if key == "per_cutter":
            continue
        v = getattr(material, key)
        if v is None:
            continue
        lines.append("%s = %s" % (key, _toml_value(v)))
    for pid in sorted(material.per_cutter or {}):
        values = {k: v for k, v in material.per_cutter[pid].items() if v is not None}
        if not values:
            continue
        lines.append("")
        lines.append('[per_cutter."%s"]' % pid.replace('"', ''))
        for k in sorted(values):
            lines.append("%s = %s" % (k, _toml_value(values[k])))
    return "\n".join(lines) + "\n"


def save(material, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_toml(material))


# ---- built-in and the user's own -----------------------------------------------------------

def builtin_names():
    folder = resources.files("vintyl.core") / "materials"
    return sorted(p.name[:-5] for p in folder.iterdir() if p.name.endswith(".toml"))


def load_builtin(name):
    res = resources.files("vintyl.core") / "materials" / (name + ".toml")
    if not res.is_file():
        raise MaterialError("No built-in material \"%s\"." % name)
    return from_dict(tomllib.loads(res.read_text(encoding="utf-8")), name)


def user_dir():
    """Where the user's materials are: VINTYL_MATERIALS, else a "materials"
    folder next to the user's cutter profiles."""
    if os.environ.get("VINTYL_MATERIALS"):
        return os.environ["VINTYL_MATERIALS"]
    from .profile import user_dir as profiles_dir
    return os.path.join(os.path.dirname(profiles_dir()), "materials")


def catalogue():
    """Every material, knife ones first, then by name: dicts {"id",
    "material", "builtin", "changed", "error"} as profile.catalogue()."""
    entries = {}
    for name in builtin_names():
        entries[name] = {"id": name, "material": load_builtin(name), "builtin": True, "changed": False,
                         "error": None}
    folder = user_dir()
    if os.path.isdir(folder):
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith(".toml"):
                continue
            mid = fname[:-5]
            builtin = mid in entries
            try:
                m = load(os.path.join(folder, fname))
                entries[mid] = {"id": mid, "material": m, "builtin": builtin, "changed": builtin, "error": None}
            except (MaterialError, OSError, ValueError) as e:
                if not builtin:
                    entries[mid] = {"id": mid, "material": None, "builtin": False, "changed": False,
                                    "error": str(e)}

    # knife ones first; the built-in ones in a fixed order (plain vinyl first,
    # as it is chosen by default), then the user's by name
    rank = {mid: n for n, mid in enumerate(BUILTIN_ORDER)}

    def order(e):
        m = e["material"]
        return (0 if m is None or m.tool == "knife" else 1, rank.get(e["id"], len(rank)),
                (m.name if m else e["id"]).lower())
    return sorted(entries.values(), key=order)


def save_user(mid, material):
    folder = user_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, mid + ".toml")
    tmp = path + ".tmp"
    save(material, tmp)
    os.replace(tmp, path)
    return path


def delete_user(mid):
    path = os.path.join(user_dir(), mid + ".toml")
    if os.path.exists(path):
        os.remove(path)


def new_id(name):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "material"
    taken = set(builtin_names())
    folder = user_dir()
    if os.path.isdir(folder):
        taken |= {f[:-5] for f in os.listdir(folder) if f.endswith(".toml")}
    mid, n = base, 2
    while mid in taken:
        mid, n = "%s-%d" % (base, n), n + 1
    return mid
