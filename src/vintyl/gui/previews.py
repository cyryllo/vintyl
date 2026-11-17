"""
Pictures of a shape and of the fill patterns, for the windows (UI v2):

    ShapePreview     the selected shape with its pattern of shapes or its
                     fill, 200 x 200 px, drawn again at every change of a
                     field (the sheet's dashed preview stays as well)
    pattern_icon()   a small picture of a fill pattern for its button,
                     drawn by the same code that fills the shapes

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame

from vintyl.gui import icons, theme


def polyline_path(polylines):
    """QPainterPath of polylines [[(x, y), ...], ...] (a fill's lines)."""
    path = QPainterPath()
    for line in polylines:
        if len(line) < 2:
            continue
        path.moveTo(QPointF(*line[0]))
        for x, y in line[1:]:
            path.lineTo(x, y)
    return path


class ShapePreview(QFrame):
    """The outline drawn thicker, the pattern (or fill) thinner, both in the
    accent colour, fitted into the box with a margin. Its ground is the
    sheet's (light in both looks), as the shape on the sheet."""

    PAD = 14

    def __init__(self, size=200, parent=None):
        super().__init__(parent)
        self.setObjectName("preview_box")
        self.setFixedSize(size, size)
        self._outline = QPainterPath()
        self._pattern = QPainterPath()

    def set_paths(self, outline, pattern=None):
        """outline, pattern: QPainterPaths in mm (pattern None: just the outline)."""
        self._outline = outline
        self._pattern = pattern if pattern is not None else QPainterPath()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        r = self._outline.boundingRect().united(self._pattern.boundingRect())
        if r.isEmpty() and r.width() <= 0 and r.height() <= 0:
            return
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            side = min(self.width(), self.height()) - 2 * self.PAD
            k = side / max(r.width(), r.height(), 1e-6)
            p.translate(self.width() / 2.0, self.height() / 2.0)
            p.scale(k, k)
            p.translate(-r.center().x(), -r.center().y())
            color = QColor(theme.token("accent"))
            # widths in pixels whatever the scale (divided by it)
            p.setPen(QPen(color, 1.0 / k))
            p.drawPath(self._pattern)
            p.setPen(QPen(color, 2.0 / k))
            p.drawPath(self._outline)
        finally:
            p.end()


# a sample of each pattern: (spacing, angle) on a square of SAMPLE_MM, so the
# picture shows a few repeats of the real pattern
SAMPLE_MM = 12.0
SAMPLES = {"lines": (2.6, 60.0), "cross": (3.2, 45.0), "waves": (4.0, 0.0), "zigzag": (4.0, 0.0),
           "circles": (2.2, 0.0), "honeycomb": (4.4, 0.0), "diamonds": (4.4, 0.0), "bricks": (3.4, 0.0),
           "concentric": (1.9, 0.0)}
_icons = {}


def pattern_icon(code, size=30):
    """The pattern's picture: the theme's ink, the accent ink when chosen.
    Remembered: the honeycomb takes a moment to work out."""
    on_color, off_color = icons._state_colors()
    key = (code, size, icons.INK, on_color, off_color)
    if key in _icons:
        return _icons[key]
    from vintyl.core.patterns import pattern_lines
    spacing, angle = SAMPLES.get(code, (3.0, 0.0))
    s = SAMPLE_MM
    square = [[(0.0, 0.0), (s, 0.0), (s, s), (0.0, s), (0.0, 0.0)]]
    try:
        path = polyline_path(pattern_lines(code, square, spacing, angle))
    except ValueError:
        path = QPainterPath()
    icon = QIcon()
    for ink, mode, state in ((icons.INK, QIcon.Normal, QIcon.Off), (on_color, QIcon.Normal, QIcon.On),
                             (on_color, QIcon.Active, QIcon.On), (off_color, QIcon.Disabled, QIcon.Off)):
        if ink is None:
            continue
        for px in (size, size * 2):          # sharp on a screen scaled 2x too
            pm = QPixmap(px, px)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing, True)
            k = (px - 2) / s
            p.translate(1, 1)
            p.scale(k, k)
            p.setClipRect(QRectF(0, 0, s, s))
            p.setPen(QPen(QColor(ink), 1.6 * px / size / k))
            p.drawPath(path)
            p.end()
            icon.addPixmap(pm, mode, state)
    _icons[key] = icon
    return icon
