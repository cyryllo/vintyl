"""
A cutting job: paths in material coordinates -> checked -> cutter commands.

    build_job(polylines, profile) -> Job
    job.save(path)                   the commands to a file (the dry run)

Steps, in this order:
    1. tidy:    drop empty paths and repeated points
    2. check:   the design lies on the material (cutting width, length)
    3. order:   inside shapes first, the user's element order, short travel
    4. overcut: closed shapes are cut a little further along themselves
    5. knife:   drag-knife compensation (the path of the holder's axis)
    6. check:   the knife's path still lies on the material
    7. axes:    material coordinates -> the cutter's own axes (profile)
    8. units:   millimetres -> whole machine units
    9. safety:  no negative coordinate reaches the cutter
   10. encode:  HPGL / DMPL text, knife always up before every travel

Overcut comes BEFORE the knife compensation: compensated, a closed shape
no longer ends exactly where it starts, and Inkcut, which does it the
other way round, silently drops the overcut. The travel home is a separate
move and is never compensated.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math
from dataclasses import dataclass

from . import knife
from ..i18n import _
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
    knife_paths: list = None  # what the knife does, in order, material mm (for the preview)

    def save(self, path):
        # ASCII only: these languages have no other characters, and the
        # cutter must get exactly these bytes
        with open(path, "w", encoding="ascii", newline="") as f:
            f.write(self.text)


def _tidy(polylines, groups):
    """Copies as lists of (x, y) floats; paths shorter than 2 points dropped,
    a point equal to the one before dropped. Returns (paths, their groups)."""
    out, out_groups = [], []
    for poly, group in zip(polylines, groups):
        pts = []
        for p in poly:
            x, y = float(p[0]), float(p[1])
            if not (math.isfinite(x) and math.isfinite(y)):
                raise JobError(_("A path has a point that is not a number."))
            if not pts or (x, y) != pts[-1]:
                pts.append((x, y))
        if len(pts) >= 2:
            out.append(pts)
            out_groups.append(group)
    return out, out_groups


def _bounds(polylines):
    xs = [x for poly in polylines for x, _ in poly]
    ys = [y for poly in polylines for _, y in poly]
    return min(xs), max(xs), min(ys), max(ys)


def check_on_material(bounds, profile):
    """Raise JobError naming the worst overrun in mm, or return None."""
    xmin, xmax, ymin, ymax = bounds
    over = [(_("before the origin (along the material)"), -xmin),
            (_("across the material, below 0"), -ymin),
            (_("across the material, past the cutting width of %g mm") % profile.width_mm,
             ymax - profile.width_mm)]
    if profile.length_mm > 0:
        over.append((_("past the length of %g mm") % profile.length_mm, xmax - profile.length_mm))
    where, mm = max(over, key=lambda o: o[1])
    if mm > EDGE_TOLERANCE_MM:
        raise JobError(_("The design does not fit on the material: it sticks out %s by %.1f mm.")
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


def build_job(polylines, profile, groups=None, inside_first=False, align_bounds=None):
    """Turn paths (lists of (x, y) in material mm) into a Job. Raises
    JobError when there is nothing to cut or the design does not fit.

    groups: the element number of each path (the user's cutting order);
    inside_first: reorder (see knife.order). Without it the paths are cut
    exactly in the order given. align_bounds: the box an axis along the
    material is turned within (to_machine); several jobs of one design (its
    colours, one after another) give the whole design's, so they still fall
    on each other. None: this job's own."""
    profile.validate()
    groups = list(groups) if groups is not None else [0] * len(polylines)
    if len(groups) != len(polylines):
        raise ValueError("groups must have one entry per path")
    polys, groups = _tidy(polylines, groups)
    if not polys:
        raise JobError(_("There is nothing to cut."))
    bounds = _bounds(polys)
    check_on_material(bounds, profile)

    if inside_first:
        polys = knife.order(polys, groups)
    polys = [knife.overcut(p, profile.overcut_mm) for p in polys]
    polys = knife.compensate(polys, profile.knife_offset_mm, profile.corner_deg)
    if profile.knife_offset_mm > 0 or profile.overcut_mm > 0:
        try:
            check_on_material(_bounds(polys), profile)
        except JobError as e:
            raise JobError(_("%s The knife offset and the overcut need %.2f mm of room; "
                             "move the design that far from the edge.")
                           % (e, profile.knife_offset_mm + profile.overcut_mm)) from None

    enc = encoder_for(profile)
    scale = enc.units_per_mm
    # mirror within the box of what the knife really does (after compensation)
    machine = to_machine(polys, profile, align_bounds or _bounds(polys))

    # units, and the safety check on what really goes out
    unit_polys = []
    for poly in machine:
        pts = []
        for x, y in poly:
            ux, uy = _round(x * scale), _round(y * scale)
            if ux < 0 or uy < 0:
                raise JobError(_("A point would go to the cutter at %d,%d (below zero). "
                                 "Check the axis settings of the profile.") % (ux, uy))
            if not pts or (ux, uy) != pts[-1]:
                pts.append((ux, uy))
        if len(pts) >= 2:
            unit_polys.append(pts)
    if not unit_polys:
        raise JobError(_("There is nothing to cut: every path is shorter than one cutter step."))

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
               cut_mm=cut / scale, travel_mm=travel / scale, paths=len(unit_polys),
               knife_paths=polys)
