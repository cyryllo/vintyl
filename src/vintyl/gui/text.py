"""
Text to outlines with the fonts installed on the system (through Qt).

The outlines keep the font's curves (vintyl.core.curves format, mm, y down),
so letters are cut smoothly and their nodes can be edited. The idea of
making the outlines at a large reference size and scaling them down, for
smooth small text, comes from Kerfly (kerfly/gui/text_shapes.py, commit
cf48565); the conversion to curves is Vintyl's.

Text on a path (a line, a curve, a circle): every letter stands on the path
at its place, turned along it. path_walker() and prepare_path() are adapted
from Kerfly's _path_walker and prepare_path (same file and commit); Vintyl
keeps each letter's curves (moved and turned, not flattened).

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QFont, QFontMetricsF, QPainterPath

from vintyl.core.curves import node

REFERENCE_PX = 1000      # outlines are made at this size, then scaled (smooth small text)
DEFAULTS = {"text": "Vintyl", "family": "Noto Sans", "size": 30.0, "bold": True, "italic": False,
            "spacing": 0.0}


def _font(family, size_mm, bold, italic, spacing_mm=0.0):
    font = QFont(family)
    font.setPixelSize(REFERENCE_PX)
    font.setBold(bold)
    font.setItalic(italic)
    if spacing_mm:
        font.setLetterSpacing(QFont.AbsoluteSpacing, spacing_mm * REFERENCE_PX / max(size_mm, 1e-6))
    return font


def painter_path_to_curves(path, scale=1.0):
    """curves subpaths of a QPainterPath (moves, lines and cubic curves)."""
    subs = []
    nodes = None
    i, n = 0, path.elementCount()

    def finish():
        if nodes and len(nodes) >= 2:
            first, last = nodes[0], nodes[-1]
            closed = abs(first[0] - last[0]) < 1e-9 and abs(first[1] - last[1]) < 1e-9
            if closed:
                # the outline returns to its start: one node there, with both handles
                first[2], first[3] = last[2], last[3]
                nodes.pop()
            if len(nodes) >= 2:
                subs.append({"closed": closed, "nodes": nodes})
    while i < n:
        e = path.elementAt(i)
        x, y = e.x * scale, e.y * scale
        if e.type == QPainterPath.MoveToElement:
            finish()
            nodes = [node(x, y)]
        elif e.type == QPainterPath.LineToElement:
            nodes.append(node(x, y))
        elif e.type == QPainterPath.CurveToElement:
            c2 = path.elementAt(i + 1)
            end = path.elementAt(i + 2)
            nodes[-1][4], nodes[-1][5] = x, y
            nodes.append(node(end.x * scale, end.y * scale, hin=(c2.x * scale, c2.y * scale)))
            i += 2
        i += 1
    finish()
    return subs


def text_paths(text, family=DEFAULTS["family"], size_mm=DEFAULTS["size"], bold=DEFAULTS["bold"],
               italic=DEFAULTS["italic"], spacing_mm=DEFAULTS["spacing"]):
    """Outlines of the text, top left of the first line at (0, 0); size_mm is
    the font's em height; several lines are separated by newlines."""
    font = _font(family, size_mm, bold, italic, spacing_mm)
    metrics = QFontMetricsF(font)
    path = QPainterPath()
    y = metrics.ascent()
    for line in (text or "").split("\n"):
        path.addText(QPointF(0, y), font, line)
        y += metrics.lineSpacing()
    return painter_path_to_curves(path, size_mm / float(REFERENCE_PX))


def spec_paths(spec):
    """The outlines of a text spec: in a line from (0, 0), or along its path
    (spec["path"], in view mm, where it is on the sheet)."""
    if spec.get("path"):
        return path_text_paths(spec["text"], spec["family"], spec["size"], spec["bold"], spec["italic"],
                               spec["path"], spec.get("offset", 0.0), spec.get("flip", False),
                               spec.get("distance", 0.0), spec["spacing"])
    return text_paths(spec["text"], spec["family"], spec["size"], spec["bold"], spec["italic"], spec["spacing"])


# ---- text on a path -------------------------------------------------------------------------------
def _is_ring(points):
    return len(points) > 3 and math.hypot(points[0][0] - points[-1][0], points[0][1] - points[-1][1]) < 1e-6


def path_walker(points):
    """(length, at(s)) for a polyline: at(s) gives the point and the direction
    (radians, y down) at distance s from the start. On a closed path (last
    point = first) s goes round and round; on an open one the line is
    continued straight before the start and past the end."""
    ring = _is_ring(points)
    pts = [(float(x), float(y)) for x, y in points]
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    segs = []
    total = 0.0
    for a, b in zip(pts, pts[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        segs.append((total, length, a, b))
        total += length

    def at(s):
        if not segs:
            return (pts[0] if pts else (0.0, 0.0)), 0.0
        if ring and total > 0:
            s = s % total
        if s <= 0:
            start, _length, a, b = segs[0]
        elif s >= total:
            start, _length, a, b = segs[-1]
        else:
            lo, hi = 0, len(segs) - 1                  # the segment holding s
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if segs[mid][0] <= s:
                    lo = mid
                else:
                    hi = mid - 1
            start, _length, a, b = segs[lo]
        angle = math.atan2(b[1] - a[1], b[0] - a[0])
        t = s - start
        return (a[0] + math.cos(angle) * t, a[1] + math.sin(angle) * t), angle
    return total, at


def text_length(text, family, size_mm, bold, italic, spacing_mm=0.0):
    """How long the text is (mm) along its line."""
    font = _font(family, size_mm, bold, italic, spacing_mm)
    return QFontMetricsF(font).horizontalAdvance((text or "").replace("\n", " ")) * size_mm / float(REFERENCE_PX)


def prepare_path(points, closed, text_len):
    """A guide path for a text, and the offset to start at: an open path gets
    the text in its middle; a closed one (circle, ellipse, ...) runs clockwise
    with the text centred at its top."""
    pts = [(float(x), float(y)) for x, y in points]
    total, at = path_walker(pts)
    if not closed or len(pts) < 3:
        return pts, max(0.0, (total - text_len) / 2.0)
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    if area < 0:                                       # y down: positive area runs clockwise on screen
        pts.reverse()
    ring = pts + [pts[0]]
    total, at = path_walker(ring)
    acc, top_s, top_y = 0.0, 0.0, None                 # how far along the topmost point is
    for a, b in zip(ring, ring[1:]):
        if top_y is None or a[1] < top_y:
            top_s, top_y = acc, a[1]
        acc += math.hypot(b[0] - a[0], b[1] - a[1])
    return ring, ((top_s - text_len / 2.0) % total if total else 0.0)


def path_text_paths(text, family, size_mm, bold, italic, path, offset=0.0, flip=False, distance=0.0,
                    spacing_mm=0.0):
    """curves subpaths (view mm) of the text set along the polyline `path`:
    every letter stands on the path at its place (with the font's kerning and
    `spacing_mm` between letters), turned along it, starting `offset` mm from
    the start of the path, its foot `distance` mm away from the line. flip
    runs the text the other way along the same stretch of the path, so it
    stands on the other side of the line (inside a circle, readable)."""
    font = _font(family, size_mm, bold, italic, spacing_mm)
    metrics = QFontMetricsF(font)
    k = size_mm / float(REFERENCE_PX)
    line = (text or "").replace("\n", " ")
    if flip:
        total, _at = path_walker(path)
        path = list(reversed(path))
        offset = total - offset - metrics.horizontalAdvance(line) * k
    _length, at = path_walker(path)
    out = []
    for i, ch in enumerate(line):
        x0 = metrics.horizontalAdvance(line[:i])             # includes kerning with the letters before
        w = metrics.horizontalAdvance(line[:i + 1]) - x0
        if ch.isspace():
            continue
        (px, py), angle = at(offset + (x0 + w / 2.0) * k)
        c, s_ = math.cos(angle), math.sin(angle)
        glyph = QPainterPath()
        glyph.addText(QPointF(-w / 2.0, 0.0), font, ch)      # centred on its place, baseline on the path

        def place(x, y):
            u, v = x, y - distance                           # y down: letters stand above (v < 0)
            return px + u * c - v * s_, py + u * s_ + v * c
        for sub in painter_path_to_curves(glyph, k):
            nodes = []
            for n in sub["nodes"]:
                m = list(place(n[0], n[1])) + [None] * 4
                for j in (2, 4):
                    if n[j] is not None:
                        m[j], m[j + 1] = place(n[j], n[j + 1])
                nodes.append(m)
            out.append({"closed": sub["closed"], "nodes": nodes})
    return out
