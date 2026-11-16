"""
Basic drawn shapes as curves subpaths (view mm, y down): rectangle (with
round corners or not), ellipse, polygon and line.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

from .curves import KAPPA, node


def rectangle(x0, y0, x1, y1):
    xa, xb = sorted((x0, x1))
    ya, yb = sorted((y0, y1))
    return [{"closed": True, "nodes": [node(xa, ya), node(xb, ya), node(xb, yb), node(xa, yb)]}]


def rounded_rectangle(x0, y0, x1, y1, radius):
    """A rectangle with round corners (true quarter circles); the radius is
    at most half the shorter side; 0 = sharp corners."""
    xa, xb = sorted((x0, x1))
    ya, yb = sorted((y0, y1))
    r = max(0.0, min(radius, (xb - xa) / 2.0, (yb - ya) / 2.0))
    if r <= 1e-9:
        return rectangle(xa, ya, xb, yb)
    k = KAPPA * r
    nodes = [
        node(xa + r, ya, hin=(xa + r - k, ya)), node(xb - r, ya, hout=(xb - r + k, ya)),
        node(xb, ya + r, hin=(xb, ya + r - k)), node(xb, yb - r, hout=(xb, yb - r + k)),
        node(xb - r, yb, hin=(xb - r + k, yb)), node(xa + r, yb, hout=(xa + r - k, yb)),
        node(xa, yb - r, hin=(xa, yb - r + k)), node(xa, ya + r, hout=(xa, ya + r - k)),
    ]
    return [{"closed": True, "nodes": nodes}]


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
