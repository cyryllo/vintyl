"""
Perforated cuts: a line cut in dashes (a cut, a gap, a cut...) so the
material holds together and is folded (card) or torn off (paper) along it.
With a pen the same makes a dashed line.

Each polyline is walked along its length from its start: CUT mm cut, GAP mm
left, and again; a closed outline is dashed as it goes round. The dashes
are open polylines, so the knife's offset bends them as any line and no
overcut is added.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

DEFAULT = {"cut": 3.0, "gap": 1.0}          # mm: card folds well along it (a tear-off line: 1 and 1)
SMALLEST_MM = 0.2                           # a cut or a gap shorter than this is not made


def valid(spec):
    """The perforation spec {"cut": mm, "gap": mm}, checked (ValueError), or None."""
    if not spec:
        return None
    cut, gap = float(spec["cut"]), float(spec["gap"])
    if not (cut >= SMALLEST_MM and gap >= SMALLEST_MM):
        raise ValueError("a perforation's cut and gap must be at least %g mm" % SMALLEST_MM)
    return {"cut": cut, "gap": gap}


def dashes(poly, cut, gap):
    """The cut pieces of a polyline [(x, y), ...]: from its start, cut mm
    down, gap mm up, and again. Returns a list of polylines."""
    out, piece = [], [poly[0]] if poly else []
    down, left = True, cut                     # cutting now; how much of this cut (or gap) is left
    for (x0, y0), (x1, y1) in zip(poly, poly[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        done = 0.0
        while seg - done > 1e-9:
            step = min(left, seg - done)
            done += step
            left -= step
            t = done / seg
            p = (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
            if down:
                piece.append(p)
            if left <= 1e-9:                   # this cut (or gap) is over: the other one starts here
                if down and len(piece) > 1:
                    out.append(piece)
                down = not down
                left = cut if down else gap
                piece = [p] if down else []
    if down and len(piece) > 1:
        out.append(piece)
    return out
