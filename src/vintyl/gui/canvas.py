"""
The working area: the strip of material with the design on it.

Scene units are millimetres, x along the material (right), y DOWN, the
origin (the cutter's Origin) at (0, 0) in the lower-left corner of the
strip. The strip spans y from -width to 0 and runs on to the right with
no end, like a roll.

Navigation as in Kerfly: the wheel zooms about the pointer, the middle
button drags the view.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView)

from vintyl.core import curves
from vintyl.gui import _

COLORS = {
    "background": QColor("#5b6270"),
    "material": QColor("#f4f5f7"),
    "material_edge": QColor("#9ca3af"),
    "grid": QColor("#e3e6ea"),
    "label": QColor("#e5e7eb"),
    "cut": QColor("#be185d"),
    "skip": QColor("#9ca3af"),
    "selection": QColor("#2563eb"),
    "origin": QColor("#f59e0b"),
    "off": QColor("#dc2626"),
}
MIN_STRIP_LENGTH = 1000.0        # mm of strip always shown, more when the design is longer
GRID_MM = 50.0


def cosmetic_pen(color, width=1.0, style=Qt.SolidLine):
    """A pen whose width is in screen pixels, whatever the zoom."""
    pen = QPen(QColor(color), width, style)
    pen.setCosmetic(True)
    return pen


def painter_path(subpaths):
    """QPainterPath of curves subpaths (view mm)."""
    path = QPainterPath()
    for sub in subpaths:
        nodes = sub["nodes"]
        if not nodes:
            continue
        path.moveTo(nodes[0][0], nodes[0][1])
        for p0, c1, c2, p3 in curves.segments_of(sub):
            if c1 is None:
                path.lineTo(p3[0], p3[1])
            else:
                path.cubicTo(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
        if sub["closed"]:
            path.closeSubpath()
    return path


class CanvasSignals(QObject):
    selected = Signal(object)                 # element or None
    moved = Signal(object, float, float)      # element, dx, dy (view mm)
    drawn = Signal(str, QRectF)               # tool, rectangle dragged (view mm, normalised)
    line_drawn = Signal(QPointF, QPointF)     # line tool: start, end (view mm)
    cursor = Signal(float, float)             # pointer in material coordinates (x along, y across)


class ElementItem(QGraphicsPathItem):
    """One element. Its paths are already in scene coordinates; a drag moves
    the item and, when the mouse is released, the element's nodes."""

    def __init__(self, element, view):
        super().__init__(painter_path(element.paths))
        self.element = element
        self.view = view
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setPen(cosmetic_pen(COLORS["cut"] if element.cut else COLORS["skip"], 1.6,
                                 Qt.SolidLine if element.cut else Qt.DashLine))
        self._press = None

    def shape(self):
        # pick by the whole bounding box: thin outlines are hard to hit
        p = QPainterPath()
        p.addRect(self.path().boundingRect().adjusted(-1, -1, 1, 1))
        return p

    def paint(self, painter, option, widget=None):
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())
        r = self.path().boundingRect()
        if self.view.off_material(self.sceneBoundingRect()) and self.element.cut:
            tint = QColor(COLORS["off"])
            tint.setAlpha(40)
            painter.setPen(cosmetic_pen(COLORS["off"], 1.5))
            painter.setBrush(QBrush(tint))
            painter.drawRect(r)
        elif self.isSelected():
            painter.setPen(cosmetic_pen(COLORS["selection"], 1.2, Qt.DashLine))
            painter.drawRect(r)

    def mousePressEvent(self, event):
        self._press = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._press is None:
            return
        moved = self.pos() - self._press
        self._press = None
        if abs(moved.x()) > 1e-6 or abs(moved.y()) > 1e-6:
            self.view.signals.moved.emit(self.element, moved.x(), moved.y())


class MaterialView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setBackgroundBrush(COLORS["background"])
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setMouseTracking(True)
        self.signals = CanvasSignals()
        self.width_mm = 600.0
        self.tool = "select"
        self._items = []
        self._draw_start = None
        self._draw_item = None
        self._panning = None
        self._user_zoomed = False
        self.scene().selectionChanged.connect(self._selection_changed)

    # ---- content --------------------------------------------------------------
    def material_rect(self, length):
        return QRectF(0.0, -self.width_mm, length, self.width_mm)

    def off_material(self, rect):
        tol = 0.05
        return rect.top() < -self.width_mm - tol or rect.bottom() > tol or rect.left() < -tol

    def show_design(self, design, width_mm, selected=None):
        """Draw the material and every element; keep the zoom unless asked to fit."""
        self.width_mm = float(width_mm)
        scene = self.scene()
        scene.blockSignals(True)
        scene.clear()
        self._items = []
        self._knife_items = []          # cleared with the scene; the window draws them again
        box = design.bounds()
        length = max(MIN_STRIP_LENGTH, (box[1] + 200.0) if box else 0.0)
        strip = self.material_rect(length)

        scene.addRect(strip, QPen(Qt.NoPen), QBrush(COLORS["material"]))
        grid = cosmetic_pen(COLORS["grid"], 1)
        x = GRID_MM
        while x < length:
            scene.addLine(x, -self.width_mm, x, 0, grid)
            x += GRID_MM
        y = -GRID_MM
        while y > -self.width_mm:
            scene.addLine(0, y, length, y, grid)
            y -= GRID_MM
        edge = cosmetic_pen(COLORS["material_edge"], 1.5)
        scene.addLine(0, -self.width_mm, length, -self.width_mm, edge)
        scene.addLine(0, 0, length, 0, edge)
        scene.addLine(0, -self.width_mm, 0, 0, edge)
        self._label(_("Material: cutting width %g mm, no length limit") % self.width_mm,
                    QPointF(2, -self.width_mm - 3), above=True)
        self._label(_("feed →"), QPointF(length - 4, -self.width_mm - 3), above=True, right=True)
        self._origin_marker()
        self._label(_("Origin"), QPointF(6, 3))

        for e in design.elements:
            item = ElementItem(e, self)
            scene.addItem(item)
            item.setFlag(QGraphicsItem.ItemIsMovable, self.tool == "select")
            self._items.append(item)
            if e is selected:
                item.setSelected(True)
        scene.setSceneRect(strip.adjusted(-60, -60, 60, 60))
        scene.blockSignals(False)
        if not self._user_zoomed:
            self.fit_all()

    def _label(self, text, pos, above=False, right=False):
        item = QGraphicsSimpleTextItem(text)
        item.setBrush(COLORS["label"])
        f = QFont()
        f.setPointSizeF(9)
        item.setFont(f)
        item.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        r = item.boundingRect()
        item.setPos(pos)
        dx = -r.width() if right else 0
        dy = -r.height() if above else 0
        item.setTransform(item.transform().translate(dx, dy))
        self.scene().addItem(item)
        return item

    def _origin_marker(self):
        pen = cosmetic_pen(COLORS["origin"], 2.2)
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), 4, 4)
        path.moveTo(-9, 0)
        path.lineTo(9, 0)
        path.moveTo(0, -9)
        path.lineTo(0, 9)
        item = QGraphicsPathItem(path)
        item.setPen(pen)
        item.setZValue(10)
        self.scene().addItem(item)

    # ---- knife path preview ------------------------------------------------------
    def show_knife(self, paths):
        """Draw what the knife does over the design (paths in material mm,
        in cutting order), or remove that drawing (paths None).

        Cuts are solid, travels (knife up) dashed, from the origin through
        every path and back; a numbered dot marks where each path starts."""
        for item in getattr(self, "_knife_items", []):
            if item.scene() is self.scene():
                self.scene().removeItem(item)
        self._knife_items = []
        if not paths:
            return
        cut, travel = QPainterPath(), QPainterPath()
        pos = QPointF(0, 0)
        for poly in paths:
            start = QPointF(poly[0][0], -poly[0][1])
            travel.moveTo(pos)
            travel.lineTo(start)
            cut.moveTo(start)
            for x, y in poly[1:]:
                cut.lineTo(x, -y)
            pos = QPointF(poly[-1][0], -poly[-1][1])
        travel.moveTo(pos)
        travel.lineTo(0, 0)
        for path, pen in ((travel, cosmetic_pen(COLORS["selection"], 1.2, Qt.DashLine)),
                          (cut, cosmetic_pen(COLORS["cut"], 2.4))):
            item = QGraphicsPathItem(path)
            item.setPen(pen)
            item.setZValue(20)
            item.setAcceptedMouseButtons(Qt.NoButton)
            self.scene().addItem(item)
            self._knife_items.append(item)
        for k, poly in enumerate(paths, 1):
            self._knife_items.append(self._order_dot(k, QPointF(poly[0][0], -poly[0][1])))

    def _order_dot(self, number, at):
        """A small numbered dot that keeps its size on screen."""
        dot = QGraphicsPathItem()
        p = QPainterPath()
        p.addEllipse(QPointF(0, 0), 8, 8)
        dot.setPath(p)
        dot.setBrush(QBrush(QColor("#1f2937")))
        dot.setPen(QPen(Qt.NoPen))
        dot.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        dot.setPos(at)
        dot.setZValue(21)
        dot.setAcceptedMouseButtons(Qt.NoButton)
        text = QGraphicsSimpleTextItem(str(number), dot)
        f = QFont()
        f.setPointSizeF(7)
        text.setFont(f)
        text.setBrush(QColor("white"))
        r = text.boundingRect()
        text.setPos(-r.width() / 2, -r.height() / 2)
        self.scene().addItem(dot)
        return dot

    # ---- selection ------------------------------------------------------------
    def _selection_changed(self):
        sel = [i for i in self.scene().selectedItems() if isinstance(i, ElementItem)]
        self.signals.selected.emit(sel[0].element if sel else None)

    def select(self, element):
        for item in self._items:
            item.setSelected(item.element is element)

    # ---- tools ----------------------------------------------------------------
    def set_tool(self, tool):
        self.tool = tool
        for item in self._items:
            item.setFlag(QGraphicsItem.ItemIsMovable, tool == "select")
        self.setDragMode(QGraphicsView.RubberBandDrag if tool == "select" else QGraphicsView.NoDrag)
        self.viewport().setCursor(Qt.ArrowCursor if tool == "select" else Qt.CrossCursor)

    def _rubber(self, a, b):
        r = QRectF(a, b).normalized()
        path = QPainterPath()
        if self.tool == "ellipse":
            path.addEllipse(r)
        elif self.tool == "line":
            path.moveTo(a)
            path.lineTo(b)
        else:
            path.addRect(r)
        if self._draw_item is None:
            self._draw_item = QGraphicsPathItem()
            self._draw_item.setPen(cosmetic_pen(COLORS["selection"], 1.2, Qt.DashLine))
            self.scene().addItem(self._draw_item)
        self._draw_item.setPath(path)

    # ---- mouse and wheel ------------------------------------------------------
    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 1 / 1.25
        if 0.02 < self.transform().m11() * factor < 400:
            self._user_zoomed = True
            self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = event.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        if self.tool != "select" and event.button() == Qt.LeftButton:
            self._draw_start = self.mapToScene(event.position().toPoint())
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        p = self.mapToScene(event.position().toPoint())
        self.signals.cursor.emit(p.x(), -p.y())
        if self._panning is not None:
            d = event.position() - self._panning
            self._panning = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(d.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(d.y()))
            return
        if self._draw_start is not None:
            self._rubber(self._draw_start, p)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._panning is not None:
            self._panning = None
            self.set_tool(self.tool)
            return
        if self._draw_start is not None and event.button() == Qt.LeftButton:
            a, b = self._draw_start, self.mapToScene(event.position().toPoint())
            self._draw_start = None
            if self._draw_item is not None:
                self.scene().removeItem(self._draw_item)
                self._draw_item = None
            if (b - a).manhattanLength() > 0.5:
                if self.tool == "line":
                    self.signals.line_drawn.emit(a, b)
                else:
                    self.signals.drawn.emit(self.tool, QRectF(a, b).normalized())
            return
        super().mouseReleaseEvent(event)

    def fit_all(self):
        rect = self.material_rect(MIN_STRIP_LENGTH)
        for item in self._items:
            rect = rect.united(item.sceneBoundingRect())
        self.fitInView(rect.adjusted(-30, -30, 30, 30), Qt.KeepAspectRatio)

    def fit_requested(self):
        self._user_zoomed = False
        self.fit_all()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._user_zoomed:
            self.fit_all()
