"""
Helping the weeding and the setting of the knife.

weeding_lines(): straight cuts through the waste vinyl between the shapes,
from one side of the weeding frame to the other, stopping a margin short of
every shape: the waste then comes off in strips instead of one big sheet
that tears and lifts the small letters with it.

knife_test(): the usual test cut (a square with a triangle inside), cut
before the job to check the knife's depth and force: the triangle must peel
off cleanly, the backing must not be cut through.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from .curves import node
from .patterns import clip_polylines

DIRECTIONS = ("upright", "level", "both")


def weeding_lines(frame, outlines, spacing, direction="upright", margin=1.5):
    """Polylines (view mm) of weeding cuts inside frame = (xmin, xmax, ymin,
    ymax), every `spacing` mm, "upright" (up and down the screen), "level"
    or "both"; they stay `margin` mm away from the outlines (closed
    polylines: the shapes, only their outermost outlines matter) and reach
    the frame. Nothing when the frame is too small for one line."""
    if spacing <= 0:
        raise ValueError("spacing must be positive")
    if direction not in DIRECTIONS:
        raise ValueError("direction must be one of %s" % (DIRECTIONS,))
    x0, x1, y0, y1 = frame
    # the region: inside the frame (widened by the margin, so the cuts reach
    # the frame itself) and outside the shapes (even-odd)
    m = margin
    region = [[(x0 - m, y0 - m), (x1 + m, y0 - m), (x1 + m, y1 + m), (x0 - m, y1 + m), (x0 - m, y0 - m)]]
    for ring in outlines:
        pts = [tuple(p) for p in ring]
        if len(pts) >= 3:
            region.append(pts if pts[0] == pts[-1] else pts + [pts[0]])
    lines = []
    if direction in ("upright", "both"):
        n = int((x1 - x0) / spacing)
        first = x0 + ((x1 - x0) - n * spacing) / 2.0          # spread evenly in the frame
        lines += [[(first + k * spacing, y0), (first + k * spacing, y1)] for k in range(n + 1)
                  if x0 < first + k * spacing < x1]
    if direction in ("level", "both"):
        n = int((y1 - y0) / spacing)
        first = y0 + ((y1 - y0) - n * spacing) / 2.0
        lines += [[(x0, first + k * spacing), (x1, first + k * spacing)] for k in range(n + 1)
                  if y0 < first + k * spacing < y1]
    return [line for line in clip_polylines(lines, region, margin)
            if abs(line[0][0] - line[-1][0]) + abs(line[0][1] - line[-1][1]) > 2 * margin]


def knife_test(size=15.0, right=0.0, bottom=0.0):
    """The test cut: a square `size` mm with a triangle inside, its lower
    right corner at (right, bottom) in view mm (y down). Curves subpaths."""
    s = float(size)
    x1, y1 = right, bottom
    x0, y0 = x1 - s, y1 - s
    square = {"closed": True, "nodes": [node(x0, y0), node(x1, y0), node(x1, y1), node(x0, y1)]}
    a = 0.2 * s                                          # the triangle: 3 mm in from the square's sides
    tri = {"closed": True, "nodes": [node(x0 + s / 2.0, y0 + a), node(x1 - a, y1 - a), node(x0 + a, y1 - a)]}
    return [square, tri]
