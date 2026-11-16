"""
What the knife needs: cutting order, overcut and drag-knife compensation.
All on polylines in material millimetres, no GUI toolkit.

    order(polys, groups)            inside shapes first, short travel
    overcut(poly, mm)               a closed shape is cut further along itself
    compensate(polys, offset_mm)    the path of the knife holder's axis

Written for Vintyl. The ideas come from Inkcut's blade offset and overcut
filters (Jairus Martin and contributors) and CutScape's port of them
(jetpax); the inside-first order is the idea of K40 Whisperer (Scorch)
as kept in Kerfly. No code was copied from them.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

CLOSED_TOLERANCE_MM = 0.01       # first and last point this close: a closed shape
# The swivel arc is drawn in steps of at most ARC_STEP_DEG, but no piece
# shorter than ARC_MIN_PIECE_MM. On the cutter (VEVOR KI-375A, 16.11.2026)
# 10 degree steps gave ideal corners on vinyl, but each 0.04 mm piece is a
# move the cutter stops and starts on, and with many of them (corners, and
# every bend of a curve with the old 5 degree threshold) the cut went in
# jerks; without the compensation it was smooth.
ARC_STEP_DEG = 10.0
ARC_MIN_PIECE_MM = 0.1
# Turns of the path up to this are not corners: no swivel arc, the points
# are only pushed forward (the bends between the pieces of a curve).
CORNER_DEG = 30.0


def is_closed(poly):
    return len(poly) > 2 and math.dist(poly[0], poly[-1]) <= CLOSED_TOLERANCE_MM


def _bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def point_in_polygon(pt, poly):
    """Ray casting; the polygon may repeat its first point at the end."""
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _inside(inner, inner_box, outer, outer_box):
    """inner lies inside the closed shape outer (box test, then its first point)."""
    eps = 1e-9
    return (outer_box[0] - eps <= inner_box[0] and outer_box[1] - eps <= inner_box[1]
            and inner_box[2] <= outer_box[2] + eps and inner_box[3] <= outer_box[3] + eps
            and point_in_polygon(inner[0], outer))


def _best_start(poly, pos):
    """(distance, path) with the start moved nearest to pos: any corner of a
    closed shape, either end of an open line."""
    if is_closed(poly):
        body = poly[:-1]
        i = min(range(len(body)), key=lambda k: math.dist(pos, body[k]))
        turned = body[i:] + body[:i]
        return math.dist(pos, body[i]), turned + [turned[0]]
    if math.dist(pos, poly[-1]) < math.dist(pos, poly[0]):
        return math.dist(pos, poly[-1]), poly[::-1]
    return math.dist(pos, poly[0]), list(poly)


def order(polys, groups=None, start=(0.0, 0.0)):
    """Cutting order.

    Rules, strongest first:
      1. a shape lying inside a closed shape is cut BEFORE it, so a piece is
         never cut free while its holes are still to be cut (it could shift);
      2. the user's element order (groups: element number per path) is kept;
      3. within that, the nearest next path (short travel), starting it at
         its corner or end nearest to the knife.
    Returns new lists; the input is not changed."""
    n = len(polys)
    if n == 0:
        return []
    groups = list(groups) if groups is not None else [0] * n
    boxes = [_bbox(p) for p in polys]
    closed = [is_closed(p) for p in polys]
    must_wait = [set() for _ in range(n)]          # must_wait[i]: paths cut before i
    for i in range(n):
        if not closed[i]:
            continue
        for j in range(n):
            if i == j or not _inside(polys[j], boxes[j], polys[i], boxes[i]):
                continue
            # two identical outlines contain each other: keep their own order
            if closed[j] and _inside(polys[i], boxes[i], polys[j], boxes[j]) and j > i:
                continue
            must_wait[i].add(j)

    done, out, pos = set(), [], start
    while len(done) < n:
        ready = [i for i in range(n) if i not in done and must_wait[i] <= done]
        if not ready:                                # a loop of "inside" (cannot happen
            ready = [i for i in range(n) if i not in done]   # with real shapes): no deadlock
        group = min(groups[i] for i in ready)
        best = None
        for i in ready:
            if groups[i] != group:
                continue
            d, path = _best_start(polys[i], pos)
            if best is None or d < best[0]:
                best = (d, i, path)
        _d, i, path = best
        done.add(i)
        out.append(path)
        pos = path[-1]
    return out


def overcut(poly, mm):
    """A closed shape is cut further than its start by mm, along its own
    outline, so the end of the cut meets its beginning cleanly. Open lines
    are returned unchanged."""
    if mm <= 0 or not is_closed(poly):
        return list(poly)
    out = list(poly)
    left = mm
    for a, b in zip(poly, poly[1:]):
        seg = math.dist(a, b)
        if seg <= 0:
            continue
        if seg >= left:
            t = left / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            return out
        out.append(b)
        left -= seg
    return out                               # overcut longer than the shape: once round


def _unit(a, b):
    d = math.dist(a, b)
    if d <= 1e-9:
        return None
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def _swivel(centre, r, u_from, u_to):
    """Points of the axis swinging round the blade tip (centre) from heading
    u_from to u_to, the short way, the last point excluded."""
    a0 = math.atan2(u_from[1], u_from[0])
    turn = math.atan2(u_from[0] * u_to[1] - u_from[1] * u_to[0], u_from[0] * u_to[0] + u_from[1] * u_to[1])
    by_angle = int(math.ceil(abs(math.degrees(turn)) / ARC_STEP_DEG))
    by_length = int(r * abs(turn) / ARC_MIN_PIECE_MM)
    steps = max(1, min(by_angle, by_length))
    return [(centre[0] + r * math.cos(a0 + turn * k / steps), centre[1] + r * math.sin(a0 + turn * k / steps))
            for k in range(steps)]


def _turn(u, v):
    """Signed angle (radians) from heading u to heading v."""
    return math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])


def compensate(polys, offset_mm, corner_deg=CORNER_DEG, heading=(1.0, 0.0)):
    """The path for the knife holder's axis, so the blade tip, which trails
    the axis by offset_mm, cuts sharp corners.

    Only CORNERS are changed (turns of more than corner_deg), as the owner
    asked on 16.11.2026: on circles and arcs a drag knife follows the path
    by itself, and changing every point there made the cut jerky.
    - at a corner the axis goes on past it by the offset (so the tip reaches
      the corner), swings round the corner point on a short arc (the blade
      turns on the spot) and goes on in the new direction;
    - at the start of a path the axis stands the offset ahead of the start,
      in the blade's last heading (carried from the path before; before the
      first cut: `heading`), and turns there if the path starts another way;
    - at the end of an open path the axis goes on by the offset, so the tip
      cuts to the very end.
    Every other point stays where it is. Offset 0 (a pen) returns the paths
    unchanged."""
    if offset_mm <= 0:
        return [list(p) for p in polys]
    r = offset_mm
    limit = math.radians(corner_deg)
    last = heading
    out = []
    for poly in polys:
        pts = [p for k, p in enumerate(poly) if k == 0 or math.dist(p, poly[k - 1]) > 1e-9]
        if len(pts) < 2:
            continue
        closed = is_closed(pts)
        dirs = [_unit(a, b) for a, b in zip(pts, pts[1:])]
        p0, u0 = pts[0], dirs[0]
        res = [(p0[0] + r * last[0], p0[1] + r * last[1])]
        if abs(_turn(last, u0)) > limit:
            res.extend(_swivel(p0, r, last, u0)[1:])
            res.append((p0[0] + r * u0[0], p0[1] + r * u0[1]))
        for i in range(1, len(pts)):
            b, u = pts[i], dirs[i - 1]
            if i < len(pts) - 1:
                nxt = dirs[i]
            elif closed:
                nxt = None                       # back at the start: the path ends here
            else:
                nxt = "end"
            if nxt == "end":
                res.append((b[0] + r * u[0], b[1] + r * u[1]))       # the tip cuts to the end
            elif nxt is not None and abs(_turn(u, nxt)) > limit:
                res.append((b[0] + r * u[0], b[1] + r * u[1]))       # past the corner by the offset
                res.extend(_swivel(b, r, u, nxt)[1:])                 # turn on the spot
                res.append((b[0] + r * nxt[0], b[1] + r * nxt[1]))
            elif nxt is None and abs(_turn(u, u0)) > limit:
                res.append((b[0] + r * u[0], b[1] + r * u[1]))       # the closing corner
            else:
                res.append(b)                                         # a bend of a curve: as drawn
        last = dirs[-1]
        out.append(res)
    return out
