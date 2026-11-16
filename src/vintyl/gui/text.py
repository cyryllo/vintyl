"""
Text to outlines with the fonts installed on the system (through Qt).

The outlines keep the font's curves (vintyl.core.curves format, mm, y down),
so letters are cut smoothly and their nodes can be edited. The idea of
making the outlines at a large reference size and scaling them down, for
smooth small text, comes from Kerfly (kerfly/gui/text_shapes.py, commit
cf48565); the conversion to curves is Vintyl's.

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
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
    return text_paths(spec["text"], spec["family"], spec["size"], spec["bold"], spec["italic"], spec["spacing"])
