"""
A pattern of shapes inside a shape (for the knife): rows of small circles,
stars, hearts... placed inside a closed outline, every one whole and kept a
margin away from the outline, so each is cut as a clean hole (a sticker with
cut-out dots, a heart full of stars).

Only shapes that fit completely are kept: a shape cut by the outline would
leave a thin sliver of vinyl that tears when weeding.

The shapes keep their curves (vintyl.core.curves format), only scaled and
moved. The test whether one fits uses Kerfly's region helper
(vintyl.core.patterns, copied from Kerfly).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from . import curves, ready, shapes
from ..i18n import N_
from .patterns import _Region

# motif code -> (English name, translated in the window; the shape at about 10 mm); the ready shapes follow
BASIC = {
    "circle": (N_("Circle"), lambda: shapes.ellipse(-5, -5, 5, 5)),
    "square": (N_("Square"), lambda: shapes.rectangle(-5, -5, 5, 5)),
    "hexagon": (N_("Hexagon"), lambda: shapes.polygon(-5, -5, 5, 5, 6)),
    "triangle": (N_("Triangle"), lambda: shapes.polygon(-5, -5, 5, 5, 3)),
}
MOTIFS = list(BASIC) + [k for k in ready.READY if k not in ("ring", "arrow", "gear")] + ["ring"]


def motif(code):
    """The motif's curves subpaths, any size (tile() scales them)."""
    if code in BASIC:
        return BASIC[code][1]()
    if code in ready.READY:
        return ready.make(code)
    raise ValueError("unknown motif: %r" % (code,))


def _fitted(paths, size):
    """The motif scaled so its longer side is `size`, its box centred on (0, 0)."""
    xmin, xmax, ymin, ymax = curves.bounds(paths)
    k = size / max(xmax - xmin, ymax - ymin, 1e-9)
    cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
    return _transform(paths, lambda x, y: ((x - cx) * k, (y - cy) * k))


def _transform(paths, f):
    out = []
    for sub in paths:
        nodes = []
        for n in sub["nodes"]:
            m = list(f(n[0], n[1])) + [None] * 4
            for j in (2, 4):
                if n[j] is not None:
                    m[j], m[j + 1] = f(n[j], n[j + 1])
            nodes.append(m)
        out.append({"closed": sub["closed"], "nodes": nodes})
    return out


def tile(outline, motif_paths, size, gap, stagger=True, margin=1.0, limit=20000):
    """Copies of the motif (curves subpaths) inside the closed outline
    (curves subpaths; holes count as outside), `size` mm across, `gap` mm
    apart, in rows; stagger shifts every second row by half a step (as
    bricks in a wall). Every copy is whole and at least `margin` mm
    from the outline. Returns (subpaths, count)."""
    if size <= 0 or gap < 0 or margin < 0:
        raise ValueError("size must be positive, gap and margin not negative")
    rings = curves.flatten([sub for sub in outline if sub["closed"]], 0.05)
    if not rings:
        return [], 0
    region = _Region(rings)
    shape = _fitted(motif_paths, size)
    pieces = curves.flatten(shape, 0.05)
    pts = [p for poly in pieces for p in poly]
    xmin, xmax, ymin, ymax = curves.bounds(shape)
    w, h = xmax - xmin, ymax - ymin
    # rows the shape's height plus the gap apart: copies never touch, whatever the shape
    step_x, step_y = w + gap, h + gap
    # the rows are centred on the outline's box, so the pattern sits evenly in it
    cx, cy = (region.xmin + region.xmax) / 2.0, (region.ymin + region.ymax) / 2.0
    nx = int((region.xmax - region.xmin) / step_x / 2.0) + 2
    ny = int((region.ymax - region.ymin) / step_y / 2.0) + 2
    reach = margin + 1e-6
    out, count = [], 0
    for j in range(-ny, ny + 1):
        shift = step_x / 2.0 if stagger and j % 2 else 0.0
        for i in range(-nx, nx + 1):
            ox, oy = cx + i * step_x + shift, cy + j * step_y
            if not (region.xmin <= ox <= region.xmax and region.ymin <= oy <= region.ymax):
                continue
            if not _fits(region, pieces, pts, ox, oy, reach, margin):
                continue
            out += _transform(shape, lambda x, y: (x + ox, y + oy))
            count += 1
            if count >= limit:
                return out, count
    return out, count


def _fits(region, pieces, pts, ox, oy, reach, margin):
    for x, y in pts:
        if not region.inside(x + ox, y + oy):
            return False
        if margin > 0 and region.distance(x + ox, y + oy, reach) < margin:
            return False
    for poly in pieces:                  # no outline line passes through the copy
        for a, b in zip(poly, poly[1:]):
            if region.crossings((a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)):
                return False
    return True
