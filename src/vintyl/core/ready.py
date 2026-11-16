"""
Ready-made shapes: star, heart, ring, rounded rectangle, arrow, gear, cross,
drop. Each returns curves subpaths (vintyl.core.curves) in view mm, x right,
y down, the top left of the shape at (0, 0). No GUI toolkit.

READY lists them with their parameters (key, label, default, minimum,
maximum, step), so the window can ask for them without knowing each shape.

The gear's involute teeth follow Kerfly's gear generator
(kerfly/core/generators.py, commit cf48565).

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

from . import curves
from .curves import KAPPA, node
from ..i18n import N_


def _to_origin(subpaths):
    """Move so the top left of the outline is at (0, 0)."""
    path, _d = curves.normalized(subpaths)
    return path


def _poly(points):
    return {"closed": True, "nodes": [node(x, y) for x, y in points]}


def star(points=5, size=50.0, inner=45.0):
    """A star of `points` arms whose longer side is `size` mm; inner: the inner
    corners' distance from the centre as a percentage of the tips' (smaller =
    sharper arms)."""
    n = max(3, int(points))
    r_out = size / 2.0
    r_in = r_out * max(5.0, min(inner, 95.0)) / 100.0
    pts = []
    for k in range(2 * n):
        r = r_out if k % 2 == 0 else r_in
        a = -math.pi / 2 + math.pi * k / n
        pts.append((r * math.cos(a), r * math.sin(a)))
    # the tips of an odd star do not span its full circle: scale it so the
    # longer side is exactly `size`
    xs, ys = [x for x, _y in pts], [y for _x, y in pts]
    k = size / max(max(xs) - min(xs), max(ys) - min(ys))
    return _to_origin([_poly([(x * k, y * k) for x, y in pts])])


def heart(width=60.0, height=52.0):
    """A heart, as the one cut on the KI-375A on 16.11.2026 (tests/a4/serce.svg)."""
    sx, sy = width / 60.0, height / 52.0

    def p(x, y):
        return (x * sx, y * sy)
    # the curve, segment by segment: (start, control 1, control 2, end), from the tip round to the tip
    segs = [((30, 52), (12, 38), (0, 28), (0, 15)), ((0, 15), (0, 6), (7, 0), (15, 0)),
            ((15, 0), (22, 0), (27, 4), (30, 10)), ((30, 10), (33, 4), (38, 0), (45, 0)),
            ((45, 0), (53, 0), (60, 6), (60, 15)), ((60, 15), (60, 28), (48, 38), (30, 52))]
    nodes = []
    for a, c1, c2, b in segs:
        if nodes:
            nodes[-1][4], nodes[-1][5] = p(*c1)
        else:
            nodes.append(node(*p(*a), hout=p(*c1)))
        nodes.append(node(*p(*b), hin=p(*c2)))
    last = nodes.pop()                        # back at the tip: one node there, both handles
    nodes[0][2], nodes[0][3] = last[2], last[3]
    return _to_origin([{"closed": True, "nodes": nodes}])


def _ellipse(cx, cy, rx, ry):
    kx, ky = KAPPA * rx, KAPPA * ry
    return {"closed": True, "nodes": [
        node(cx + rx, cy, hin=(cx + rx, cy - ky), hout=(cx + rx, cy + ky)),
        node(cx, cy + ry, hin=(cx + kx, cy + ry), hout=(cx - kx, cy + ry)),
        node(cx - rx, cy, hin=(cx - rx, cy + ky), hout=(cx - rx, cy - ky)),
        node(cx, cy - ry, hin=(cx - kx, cy - ry), hout=(cx + kx, cy - ry))]}


def ring(outer=50.0, hole=30.0):
    """A ring: a circle with a round hole in the middle."""
    r = outer / 2.0
    paths = [_ellipse(r, r, r, r)]
    if 0 < hole < outer:
        paths.append(_ellipse(r, r, hole / 2.0, hole / 2.0))
    return paths


def rounded_rectangle(width=60.0, height=40.0, radius=8.0):
    """A rectangle with round corners (radius at most half the shorter side)."""
    w, h = width, height
    r = max(0.0, min(radius, w / 2.0, h / 2.0))
    if r <= 0:
        return [_poly([(0, 0), (w, 0), (w, h), (0, h)])]
    k = KAPPA * r
    nodes = [
        node(r, 0, hin=(r - k, 0)), node(w - r, 0, hout=(w - r + k, 0)),
        node(w, r, hin=(w, r - k)), node(w, h - r, hout=(w, h - r + k)),
        node(w - r, h, hin=(w - r + k, h)), node(r, h, hout=(r - k, h)),
        node(0, h - r, hin=(0, h - r + k)), node(0, r, hout=(0, r - k)),
    ]
    return [{"closed": True, "nodes": nodes}]


def arrow(length=80.0, width=40.0, head=40.0, shaft=40.0):
    """An arrow pointing right: head = the head's length, shaft = the shaft's
    thickness, both as a percentage of the arrow's length and width."""
    L, W = length, width
    hl = L * max(5.0, min(head, 95.0)) / 100.0
    st = W * max(5.0, min(shaft, 95.0)) / 100.0
    y0, y1 = (W - st) / 2.0, (W + st) / 2.0
    return [_poly([(0, y0), (L - hl, y0), (L - hl, 0), (L, W / 2.0), (L - hl, W), (L - hl, y1), (0, y1)])]


def cross(size=40.0, thickness=33.0):
    """A plus sign; thickness of its bars as a percentage of its size."""
    s = size
    t = s * max(5.0, min(thickness, 95.0)) / 100.0
    a, b = (s - t) / 2.0, (s + t) / 2.0
    return [_poly([(a, 0), (b, 0), (b, a), (s, a), (s, b), (b, b), (b, s), (a, s), (a, b), (0, b), (0, a), (a, a)])]


def drop(width=30.0, height=45.0):
    """A drop: a point on top, round at the bottom."""
    w, h = width, height
    r = w / 2.0
    cy = h - r
    k = KAPPA * r
    nodes = [node(r, 0, hout=(r + r * 0.35, cy * 0.45)),
             node(w, cy, hin=(w, cy - k), hout=(w, cy + k)),
             node(r, h, hin=(r + k, h), hout=(r - k, h)),
             node(0, cy, hin=(0, cy + k), hout=(0, cy - k))]
    nodes[0][2], nodes[0][3] = r - r * 0.35, cy * 0.45
    return [{"closed": True, "nodes": nodes}]


def gear(teeth=20, module=2.0, bore=5.0, pressure_angle=20.0, points_per_flank=8):
    """A spur gear with involute teeth (pitch diameter = module x teeth) and a
    round hole for the axle (0: none). After Kerfly's gear generator."""
    z = max(6, min(int(teeth), 200))
    m = float(module)
    alpha = math.radians(pressure_angle)
    r = m * z / 2.0
    rb = r * math.cos(alpha)
    ra = r + m
    rf = max(r - 1.25 * m, 0.5)

    def inv(a):
        return math.tan(a) - a
    half_base = math.pi / (2 * z) + inv(alpha)
    pts = []
    r_start = max(rb, rf)
    for k in range(z):
        centre = 2 * math.pi * k / z
        flank = []
        for i in range(points_per_flank + 1):
            rr = r_start + (ra - r_start) * i / points_per_flank
            phi = math.acos(min(1.0, rb / rr))
            flank.append((rr, half_base - inv(phi)))
        left = [(rr, centre - a) for rr, a in flank]
        right = [(rr, centre + a) for rr, a in reversed(flank)]
        pts += [(rf, centre - half_base - (math.pi / z - half_base) * 0.5)] + left + right + \
            [(rf, centre + half_base + (math.pi / z - half_base) * 0.5)]
    paths = [_poly([(ra + rr * math.cos(a), ra + rr * math.sin(a)) for rr, a in pts])]
    if 0 < bore < 2 * rf:
        paths.append(_ellipse(ra, ra, bore / 2.0, bore / 2.0))
    return _to_origin(paths)


# key -> (name, function, [(parameter, label, default, minimum, maximum, step)])
READY = {
    "star": (N_("Star"), star, [("points", N_("Arms"), 5, 3, 50, 1), ("size", N_("Size (mm)"), 50.0, 1, 2000, 1),
                                ("inner", N_("Inner corners (%)"), 45.0, 5, 95, 1)]),
    "heart": (N_("Heart"), heart, [("width", N_("Width (mm)"), 60.0, 1, 2000, 1),
                                   ("height", N_("Height (mm)"), 52.0, 1, 2000, 1)]),
    "ring": (N_("Ring"), ring, [("outer", N_("Outer size (mm)"), 50.0, 1, 2000, 1),
                                ("hole", N_("Hole (mm)"), 30.0, 0, 2000, 1)]),
    "rounded": (N_("Rounded rectangle"), rounded_rectangle,
                [("width", N_("Width (mm)"), 60.0, 1, 2000, 1), ("height", N_("Height (mm)"), 40.0, 1, 2000, 1),
                 ("radius", N_("Corner radius (mm)"), 8.0, 0, 1000, 0.5)]),
    "arrow": (N_("Arrow"), arrow, [("length", N_("Length (mm)"), 80.0, 1, 2000, 1),
                                   ("width", N_("Width (mm)"), 40.0, 1, 2000, 1),
                                   ("head", N_("Head (% of length)"), 40.0, 5, 95, 1),
                                   ("shaft", N_("Shaft (% of width)"), 40.0, 5, 95, 1)]),
    "cross": (N_("Cross"), cross, [("size", N_("Size (mm)"), 40.0, 1, 2000, 1),
                                   ("thickness", N_("Bars (% of size)"), 33.0, 5, 95, 1)]),
    "drop": (N_("Drop"), drop, [("width", N_("Width (mm)"), 30.0, 1, 2000, 1),
                                ("height", N_("Height (mm)"), 45.0, 1, 2000, 1)]),
    "gear": (N_("Gear"), gear, [("teeth", N_("Teeth"), 20, 6, 200, 1), ("module", N_("Module (mm)"), 2.0, 0.2, 50, 0.1),
                                ("bore", N_("Axle hole (mm)"), 5.0, 0, 500, 0.5)]),
}


def make(key, **params):
    """The shape `key` (see READY) with the given parameters (the rest: defaults)."""
    _name, func, spec = READY[key]
    values = {p[0]: p[2] for p in spec}
    values.update(params)
    return func(**values)
