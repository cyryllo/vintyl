"""
Drawing with a pen (or a pencil) in the cutter instead of the knife.

A pen draws a stroke as wide as its tip, centred on the path it follows. So
where the stroke lies against the design's line is a choice:
    "on"       the middle of the stroke on the line (the path as drawn)
    "outside"  the stroke just outside the line: closed shapes are moved out
               by half the pen's width, so the stroke's inner edge is the line
               (a shape drawn this way keeps its exact size inside)
    "inside"   the stroke just inside the line (the shape's outer edge is the line)
Open lines have no inside: they are always drawn on the line.

With a pen there is no blade trailing behind, so no knife compensation, no
overcut and no inside-first order (nothing can come loose); the job is drawn
in the user's element order with short moves between paths.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from . import offset
from .knife import is_closed

PLACES = ("on", "outside", "inside")
DEFAULT_WIDTH_MM = 0.5


def place(polys, groups, width_mm, where="on"):
    """(polys, groups) with the closed outlines of each element moved half
    the pen's width out ("outside") or in ("inside"); "on", a zero width or
    no offset library: unchanged. Holes move the other way (an "outside"
    stroke stays outside the letter's ink, also round the hole of an "O").
    A shape thinner than the stroke drawn "inside" disappears."""
    if where not in PLACES:
        raise ValueError("where must be one of %s" % (PLACES,))
    if where == "on" or width_mm <= 0 or not offset.available():
        return list(polys), list(groups)
    d = width_mm / 2.0 if where == "outside" else -width_mm / 2.0
    out, out_groups = [], []
    order = []                                     # the element numbers, in their first order
    for g in groups:
        if g not in order:
            order.append(g)
    for g in order:
        mine = [p for p, pg in zip(polys, groups) if pg == g]
        closed = [p for p in mine if is_closed(p)]
        for p in mine:
            if not is_closed(p):
                out.append(list(p))
                out_groups.append(g)
        for ring in offset.offset_polygons(closed, d, "round") if closed else []:
            out.append(ring)
            out_groups.append(g)
    return out, out_groups


def merge(fills, fill_groups, outlines, outline_groups):
    """One list in the user's element order: each element's fill lines first,
    then its outlines (drawn last, the outline gives the shape a clean edge)."""
    order = []
    for g in list(fill_groups) + list(outline_groups):
        if g not in order:
            order.append(g)
    order.sort()
    out, groups = [], []
    for g in order:
        for polys, gs in ((fills, fill_groups), (outlines, outline_groups)):
            for p, pg in zip(polys, gs):
                if pg == g:
                    out.append(p)
                    groups.append(g)
    return out, groups
