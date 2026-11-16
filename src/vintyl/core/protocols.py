"""
Cutter command languages: HPGL and DMPL.

An encoder turns moves in whole machine units into the text the cutter
reads. It knows nothing about millimetres or the working area; job.py does
that and asks the encoder for its units per millimetre.

Written for Vintyl; the command sets follow the HP-GL reference and the
DMPL dialects as used by Inkcut (Jairus Martin and contributors) and
CutScape (jetpax). No code was copied from them.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from .profile import ProfileError


def _num(v):
    """A speed or force as the cutter reads it: a whole number when it is one."""
    v = float(v)
    return "%d" % v if v == int(v) else ("%.1f" % v)


class Encoder:
    """Base class. Subclasses fill in the command text."""

    #: file extension for "save to file"
    extension = ".plt"

    def __init__(self, profile):
        self.profile = profile

    @property
    def units_per_mm(self):
        return self.profile.units_per_mm

    def begin(self):
        """Commands before the first move."""
        raise NotImplementedError

    def move(self, x, y, down):
        """Move to (x, y) machine units; down=True cuts, False travels."""
        raise NotImplementedError

    def end(self, x, y):
        """Commands after the last cut; (x, y) is where the knife is now.

        The knife is ALWAYS lifted where it stands before the travel home,
        and the job ends at the origin with the knife up. Lifting first
        matters: a travel home sent while the knife is down would cut a
        line straight across the material."""
        raise NotImplementedError


class HPGL(Encoder):
    extension = ".hpgl"

    def begin(self):
        # IN; resets the cutter to known defaults (absolute coordinates,
        # knife up). SP selects the tool; VS and FS only when the profile
        # sets them, otherwise the values on the cutter's panel stay.
        p = self.profile
        out = "IN;"
        if p.pen:
            out += "SP%d;" % p.pen
        if p.send_speed_force and p.speed_cm_s is not None:
            out += "VS%s;" % _num(p.speed_cm_s)
        if p.send_speed_force and p.force_g is not None:
            out += "FS%s;" % _num(p.force_g)
        return out

    def move(self, x, y, down):
        return "%s%d,%d;" % ("PD" if down else "PU", x, y)

    def end(self, x, y):
        # "PU x,y;" at the current point lifts the knife without moving.
        # A bare "PU;" would too, but some cutters misread it in long
        # streams (RedsailCut notes this for Redsail firmware), so the
        # coordinates are always given.
        return "PU%d,%d;PU0,0;" % (x, y)


class DMPL(Encoder):
    """Houston Instrument DMPL, as used by many vinyl cutters.

    Mode 1 starts with ";:HAEC1": EC1 sets the unit to 0.001 inch, so the
    units are fixed at 1000 per inch whatever the profile says (Inkcut
    keeps its HPGL scale here and cuts 2% too big). Mode 3 starts with
    " ;:H A L0 " and leaves the cutter's own unit, taken from the profile.
    """
    extension = ".dmpl"

    INIT = {1: ";:HAEC1 ", 3: " ;:H A L0 "}

    @property
    def units_per_mm(self):
        if self.profile.dmpl_mode == 1:
            return 1000.0 / 25.4
        return self.profile.units_per_mm

    def begin(self):
        p = self.profile
        out = self.INIT[p.dmpl_mode]
        if p.pen and p.pen != 1:
            out += "P%d " % p.pen
        if p.send_speed_force and p.speed_cm_s is not None:
            out += "V%s " % _num(p.speed_cm_s)
        if p.send_speed_force and p.force_g is not None:
            out += "BP%s " % _num(p.force_g)
        return out

    def move(self, x, y, down):
        return "%s%d,%d " % ("D" if down else "U", x, y)

    def end(self, x, y):
        return "U%d,%d U0,0 " % (x, y)


ENCODERS = {"hpgl": HPGL, "dmpl": DMPL}


def encoder_for(profile):
    try:
        return ENCODERS[profile.language](profile)
    except KeyError:
        raise ProfileError("Unknown language \"%s\"." % profile.language) from None
