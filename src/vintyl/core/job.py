"""
A cutting job: paths in material coordinates -> checked -> cutter commands.

    build_job(polylines, profile) -> Job
    job.save(path)                   the commands to a file (the dry run)

Steps, in this order:
    1. tidy:    drop empty paths and repeated points
    2. check:   everything lies on the material (cutting width, length)
    3. axes:    material coordinates -> the cutter's own axes (profile)
    4. units:   millimetres -> whole machine units
    5. safety:  no negative coordinate reaches the cutter
    6. encode:  HPGL / DMPL text, knife always up before the travel home

Path order, overcut and knife compensation come between 2 and 3 in later
steps of the plan.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math
from dataclasses import dataclass

from .protocols import encoder_for

#: a point counts as on the material up to this far outside (rounding)
EDGE_TOLERANCE_MM = 0.01


class JobError(ValueError):
    """The job cannot be sent; the message is safe to show the user."""


@dataclass
class Job:
    text: str                 # the commands, exactly as they go to the cutter
    extension: str            # ".hpgl" / ".dmpl"
    bounds_mm: tuple          # (xmin, xmax, ymin, ymax) in material coordinates
    cut_mm: float             # knife down
    travel_mm: float          # knife up, from the origin and back
    paths: int

    def save(self, path):
        # ASCII only: these languages have no other characters, and the
        # cutter must get exactly these bytes
        with open(path, "w", encoding="ascii", newline="") as f:
            f.write(self.text)


def _tidy(polylines):
    """Copies as lists of (x, y) floats; paths shorter than 2 points dropped,
    a point equal to the one before dropped."""
    out = []
    for poly in polylines:
        pts = []
        for p in poly:
            x, y = float(p[0]), float(p[1])
            if not (math.isfinite(x) and math.isfinite(y)):
                raise JobError("A path has a point that is not a number.")
            if not pts or (x, y) != pts[-1]:
                pts.append((x, y))
        if len(pts) >= 2:
            out.append(pts)
    return out


def _bounds(polylines):
    xs = [x for poly in polylines for x, _ in poly]
    ys = [y for poly in polylines for _, y in poly]
    return min(xs), max(xs), min(ys), max(ys)


def check_on_material(bounds, profile):
    """Raise JobError naming the worst overrun in mm, or return None."""
    xmin, xmax, ymin, ymax = bounds
    over = [("before the origin (along the material)", -xmin),
            ("across the material, below 0", -ymin),
            ("across the material, past the cutting width of %g mm" % profile.width_mm,
             ymax - profile.width_mm)]
    if profile.length_mm > 0:
        over.append(("past the length of %g mm" % profile.length_mm, xmax - profile.length_mm))
    where, mm = max(over, key=lambda o: o[1])
    if mm > EDGE_TOLERANCE_MM:
        raise JobError("The design does not fit on the material: it sticks out %s by %.1f mm."
                       % (where, mm))


def to_machine(polylines, profile, bounds):
    """Material coordinates -> the cutter's axes, still in mm.

    swap_xy: the cutter's X axis runs across the material.
    invert_x / invert_y: that machine axis runs the other way. An axis
    across the material is mirrored within the cutting width (the design
    stays where it is on the material); an axis along the material has no
    far edge on a roll, so the design is mirrored within its own length."""
    xmin, xmax, ymin, ymax = bounds

    def flip_along(v):          # along the material
        far = profile.length_mm if profile.length_mm > 0 else xmax + xmin
        return far - v

    def flip_across(v):         # across the material
        return profile.width_mm - v

    out = []
    for poly in polylines:
        pts = []
        for x, y in poly:
            if profile.swap_xy:
                mx, my = y, x
                if profile.invert_x:
                    mx = flip_across(mx)
                if profile.invert_y:
                    my = flip_along(my)
            else:
                mx, my = x, y
                if profile.invert_x:
                    mx = flip_along(mx)
                if profile.invert_y:
                    my = flip_across(my)
            pts.append((mx, my))
        out.append(pts)
    return out


def _round(v):
    # half away from zero, the same for every cutter; Python's round()
    # rounds halves to even
    return int(math.floor(v + 0.5)) if v >= 0 else -int(math.floor(-v + 0.5))


def build_job(polylines, profile):
    """Turn paths (lists of (x, y) in material mm) into a Job. Raises
    JobError when there is nothing to cut or the design does not fit."""
    profile.validate()
    polys = _tidy(polylines)
    if not polys:
        raise JobError("There is nothing to cut.")
    bounds = _bounds(polys)
    check_on_material(bounds, profile)

    enc = encoder_for(profile)
    scale = enc.units_per_mm
    machine = to_machine(polys, profile, bounds)

    # units, and the safety check on what really goes out
    unit_polys = []
    for poly in machine:
        pts = []
        for x, y in poly:
            ux, uy = _round(x * scale), _round(y * scale)
            if ux < 0 or uy < 0:
                raise JobError("A point would go to the cutter at %d,%d (below zero). "
                               "Check the axis settings of the profile." % (ux, uy))
            if not pts or (ux, uy) != pts[-1]:
                pts.append((ux, uy))
        if len(pts) >= 2:
            unit_polys.append(pts)
    if not unit_polys:
        raise JobError("There is nothing to cut: every path is shorter than one cutter step.")

    # encode; lengths are measured on what is sent
    parts = [enc.begin()]
    pos = (0, 0)
    cut = travel = 0.0
    for i, pts in enumerate(unit_polys):
        if i:
            # lift the knife where it is before travelling to the next path.
            # "PU x,y" alone also lifts first, but RedsailCut found Redsail
            # firmware unreliable with that in long streams; a lift in place
            # costs one short command and is the same move on every cutter.
            parts.append(enc.move(pos[0], pos[1], False))
        travel += math.dist(pos, pts[0])
        parts.append(enc.move(pts[0][0], pts[0][1], False))
        for a, b in zip(pts, pts[1:]):
            cut += math.dist(a, b)
            parts.append(enc.move(b[0], b[1], True))
        pos = pts[-1]
    travel += math.dist(pos, (0, 0))
    parts.append(enc.end(pos[0], pos[1]))

    return Job(text="".join(parts), extension=enc.extension, bounds_mm=bounds,
               cut_mm=cut / scale, travel_mm=travel / scale, paths=len(unit_polys))
