"""
Device profiles: everything Vintyl needs to know about one cutter.

A profile is a small TOML file (readable, with comments). Built-in profiles
live in vintyl/core/profiles/; the user's own are in user_dir() (by default
~/.config/vintyl/profiles). A user's file with the same name as a built-in
one is that built-in profile as the user changed it: it is used instead,
and deleting it brings the built-in one back (catalogue(), save_user(),
delete_user()). Reading uses tomllib from the standard library; writing uses
to_toml() below, which is enough for a flat list of keys.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math
import os
import re
import tomllib
from dataclasses import dataclass, fields
from importlib import resources

LANGUAGES = ("hpgl", "dmpl")
DMPL_MODES = (1, 3)
FLOW_CONTROLS = ("none", "rtscts", "xonxoff")
CONNECTIONS = ("serial", "usb-printer")
PACINGS = ("none", "time")


class ProfileError(ValueError):
    """A profile that cannot be used; the message is safe to show the user."""


@dataclass
class Profile:
    name: str = "Unnamed cutter"

    # working area, material coordinates (see vintyl.core)
    width_mm: float = 600.0          # cutting width, across the material (y)
    length_mm: float = 0.0           # along the material (x); 0 = no limit (roll)

    # connection: "usb-printer" (Linux /dev/usb/lpN) or "serial" (/dev/ttyUSB0, /dev/ttyACM0)
    connection: str = "serial"
    port: str = ""
    baud: int = 9600
    flow: str = "none"               # none / rtscts / xonxoff

    # command language
    language: str = "hpgl"           # hpgl / dmpl
    dmpl_mode: int = 3               # only for dmpl
    units_per_mm: float = 40.0       # HPGL: 40 (0.025 mm); DMPL mode 1 always uses 1000 per inch

    # machine axes: how material coordinates map onto the cutter's own axes
    swap_xy: bool = False            # machine X = material y
    invert_x: bool = False           # machine X runs the other way
    invert_y: bool = False           # machine Y runs the other way

    # knife (used from step 3 of the plan on)
    knife_offset_mm: float = 0.0     # 0 = pen, no compensation
    overcut_mm: float = 0.0          # closed shapes are cut this far past their start
    corner_deg: float = 30.0         # smaller turns count as straight (no swivel arc), see knife.CORNER_DEG
    lift_below_deg: float = 0.0      # 0 = off; lift the knife at corners sharper than this

    # speed and force: sent (HPGL VS / FS, DMPL V / BP) only when set and when
    # the cutter takes them from the computer (send_speed_force). Cutters set
    # only on their panel: speed_cm_s is then just what the panel says, used
    # for the time estimate and the pacing.
    send_speed_force: bool = True
    speed_cm_s: float | None = None
    force_g: float | None = None
    pen: int = 1                     # HPGL SP

    # sending (used from step 2 of the plan on)
    chunk_bytes: int = 64
    pacing: str = "time"             # none / time (wait for the estimated move time)
    lookahead_s: float = 0.3         # how much movement the cutter may have queued

    def validate(self):
        """Raise ProfileError listing every problem, or return self."""
        problems = []

        def need(ok, text):
            if not ok:
                problems.append(text)

        need(isinstance(self.name, str) and self.name.strip(), "name must not be empty")
        need(_positive(self.width_mm), "width_mm must be a number above 0")
        need(_number(self.length_mm) and self.length_mm >= 0, "length_mm must be 0 (no limit) or more")
        need(isinstance(self.baud, int) and self.baud > 0, "baud must be a whole number above 0")
        need(self.flow in FLOW_CONTROLS, "flow must be one of: " + ", ".join(FLOW_CONTROLS))
        need(self.connection in CONNECTIONS, "connection must be one of: " + ", ".join(CONNECTIONS))
        need(isinstance(self.port, str), "port must be text")
        need(self.language in LANGUAGES, "language must be one of: " + ", ".join(LANGUAGES))
        need(self.dmpl_mode in DMPL_MODES, "dmpl_mode must be one of: " + ", ".join(map(str, DMPL_MODES)))
        need(_positive(self.units_per_mm), "units_per_mm must be a number above 0")
        for key in ("swap_xy", "invert_x", "invert_y", "send_speed_force"):
            need(isinstance(getattr(self, key), bool), key + " must be true or false")
        for key in ("knife_offset_mm", "overcut_mm", "lift_below_deg"):
            v = getattr(self, key)
            need(_number(v) and v >= 0, key + " must be 0 or more")
        need(_number(self.corner_deg) and 0 <= self.corner_deg < 90, "corner_deg must be from 0 to 90")
        need(self.speed_cm_s is None or _positive(self.speed_cm_s), "speed_cm_s must be above 0 or left out")
        need(self.force_g is None or _positive(self.force_g), "force_g must be above 0 or left out")
        need(isinstance(self.pen, int) and self.pen >= 0, "pen must be a whole number, 0 or more")
        need(isinstance(self.chunk_bytes, int) and self.chunk_bytes > 0, "chunk_bytes must be a whole number above 0")
        need(self.pacing in PACINGS, "pacing must be one of: " + ", ".join(PACINGS))
        need(_number(self.lookahead_s) and self.lookahead_s >= 0, "lookahead_s must be 0 or more")
        if problems:
            raise ProfileError("Profile \"%s\": %s." % (self.name, "; ".join(problems)))
        return self


def _number(v):
    # bool is an int in Python, but "true" is never a valid size
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _positive(v):
    return _number(v) and v > 0


_FIELDS = {f.name: f for f in fields(Profile)}


def from_dict(data, source="profile"):
    """Profile from a dict (as read from TOML). Missing keys get the defaults;
    unknown keys are an error, so a typo does not silently do nothing."""
    unknown = sorted(set(data) - set(_FIELDS))
    if unknown:
        raise ProfileError("%s: unknown keys: %s." % (source, ", ".join(unknown)))
    values = dict(data)
    # TOML has no "nothing"; an empty string means "not set" for the optional numbers
    for key in ("speed_cm_s", "force_g"):
        if values.get(key) == "":
            values[key] = None
    # whole numbers written as 780 are fine for the float fields
    for key, f in _FIELDS.items():
        if key in values and f.type is float and isinstance(values[key], int) and not isinstance(values[key], bool):
            values[key] = float(values[key])
    return Profile(**values).validate()


def load(path):
    """Read a profile file."""
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ProfileError("%s: %s" % (path, e)) from None
    return from_dict(data, str(path))


def builtin_names():
    """File names (without .toml) of the profiles that come with Vintyl."""
    folder = resources.files("vintyl.core") / "profiles"
    return sorted(p.name[:-5] for p in folder.iterdir() if p.name.endswith(".toml"))


def load_builtin(name):
    """A profile that comes with Vintyl, e.g. load_builtin("seiki-sk-870t")."""
    res = resources.files("vintyl.core") / "profiles" / (name + ".toml")
    if not res.is_file():
        raise ProfileError("No built-in profile \"%s\". There are: %s." % (name, ", ".join(builtin_names())))
    return from_dict(tomllib.loads(res.read_text(encoding="utf-8")), name)


def to_toml(profile):
    """Write a profile as TOML text. Every key is written; optional numbers
    that are not set are written as "" (empty)."""
    profile.validate()
    lines = []
    for key in _FIELDS:
        v = getattr(profile, key)
        if v is None:
            text = '""'
        elif isinstance(v, bool):
            text = "true" if v else "false"
        elif isinstance(v, (int, float)):
            text = repr(v)
        else:
            text = '"%s"' % str(v).replace("\\", "\\\\").replace('"', '\\"')
        lines.append("%s = %s" % (key, text))
    return "\n".join(lines) + "\n"


def save(profile, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_toml(profile))


# ---- the user's profiles ---------------------------------------------------------------

def user_dir():
    """Where the user's profiles are: VINTYL_PROFILES, else a "profiles"
    folder next to VINTYL_SETTINGS (the tests), else ~/.config/vintyl/profiles."""
    if os.environ.get("VINTYL_PROFILES"):
        return os.environ["VINTYL_PROFILES"]
    if os.environ.get("VINTYL_SETTINGS"):
        return os.path.join(os.path.dirname(os.path.abspath(os.environ["VINTYL_SETTINGS"])), "profiles")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "vintyl", "profiles")


def catalogue():
    """Every cutter the user can choose, sorted by name: a list of dicts
    {"id", "profile", "builtin" (comes with Vintyl), "changed" (a built-in
    one the user changed), "error" (a user file that cannot be read: its
    message; "profile" is then None)}."""
    entries = {}
    for name in builtin_names():
        entries[name] = {"id": name, "profile": load_builtin(name), "builtin": True, "changed": False,
                         "error": None}
    folder = user_dir()
    if os.path.isdir(folder):
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith(".toml"):
                continue
            pid = fname[:-5]
            builtin = pid in entries
            try:
                prof = load(os.path.join(folder, fname))
                entries[pid] = {"id": pid, "profile": prof, "builtin": builtin, "changed": builtin, "error": None}
            except (ProfileError, OSError, TypeError, ValueError) as e:
                if not builtin:                        # a broken change of a built-in one: the built-in stays
                    entries[pid] = {"id": pid, "profile": None, "builtin": False, "changed": False,
                                    "error": str(e)}
    return sorted(entries.values(), key=lambda e: (e["profile"].name if e["profile"] else e["id"]).lower())


def save_user(pid, profile):
    """Save the user's profile (or their change of a built-in one) as pid.toml."""
    folder = user_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, pid + ".toml")
    tmp = path + ".tmp"
    save(profile, tmp)
    os.replace(tmp, path)
    return path


def delete_user(pid):
    """Delete the user's profile pid; for a built-in one: back to as it came."""
    path = os.path.join(user_dir(), pid + ".toml")
    if os.path.exists(path):
        os.remove(path)


def new_id(name):
    """A file name for a new profile named `name`, not used yet."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "cutter"
    taken = set(builtin_names())
    folder = user_dir()
    if os.path.isdir(folder):
        taken |= {f[:-5] for f in os.listdir(folder) if f.endswith(".toml")}
    pid, n = base, 2
    while pid in taken:
        pid, n = "%s-%d" % (base, n), n + 1
    return pid
