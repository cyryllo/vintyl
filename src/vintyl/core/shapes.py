"""
Basic drawn shapes as curves subpaths (view mm, y down): rectangle, ellipse
and line. The full set from Kerfly (polygon, text, text on a path, ...)
comes in a later step.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

from .curves import KAPPA, node


def rectangle(x0, y0, x1, y1):
    xa, xb = sorted((x0, x1))
    ya, yb = sorted((y0, y1))
    return [{"closed": True, "nodes": [node(xa, ya), node(xb, ya), node(xb, yb), node(xa, yb)]}]


def ellipse(x0, y0, x1, y1):
    """Ellipse inside the rectangle, as four cubic Bezier quarters."""
    xa, xb = sorted((x0, x1))
    ya, yb = sorted((y0, y1))
    cx, cy = (xa + xb) / 2.0, (ya + yb) / 2.0
    rx, ry = (xb - xa) / 2.0, (yb - ya) / 2.0
    kx, ky = KAPPA * rx, KAPPA * ry
    nodes = [
        node(cx + rx, cy, hin=(cx + rx, cy - ky), hout=(cx + rx, cy + ky)),
        node(cx, cy + ry, hin=(cx + kx, cy + ry), hout=(cx - kx, cy + ry)),
        node(cx - rx, cy, hin=(cx - rx, cy + ky), hout=(cx - rx, cy - ky)),
        node(cx, cy - ry, hin=(cx - kx, cy - ry), hout=(cx + kx, cy - ry)),
    ]
    return [{"closed": True, "nodes": nodes}]


def polygon(x0, y0, x1, y1, sides=6):
    """Regular polygon with its corners on the ellipse inside the rectangle,
    the first corner at the top (y is down: the smallest y)."""
    sides = max(3, int(sides))
    xa, xb = sorted((x0, x1))
    ya, yb = sorted((y0, y1))
    cx, cy = (xa + xb) / 2.0, (ya + yb) / 2.0
    rx, ry = (xb - xa) / 2.0, (yb - ya) / 2.0
    nodes = []
    for k in range(sides):
        a = -math.pi / 2 + 2 * math.pi * k / sides
        nodes.append(node(cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return [{"closed": True, "nodes": nodes}]


def line(x0, y0, x1, y1):
    return [{"closed": False, "nodes": [node(x0, y0), node(x1, y1)]}]
