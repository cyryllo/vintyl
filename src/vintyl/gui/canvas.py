"""
The working area: the strip of material with the design on it.

Scene units are millimetres, x along the material (right), y DOWN, the
origin (the cutter's Origin) at (0, 0) in the lower-left corner of the
strip. The strip spans y from -width to 0 and runs on to the right with
no end, like a roll.

As in Kerfly: the wheel zooms about the pointer, the middle button drags
the view; elements snap to corners, centres, middles and lines of other
elements and of the material (Alt held: no snapping); a double click on an
element edits its nodes (vintyl.gui.node_editor). The snapping methods are
adapted from Kerfly's bed view (kerfly/gui/preview.py, commit cf48565).

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QGraphicsItem, QGraphicsPathItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView)

from vintyl.core import curves, shapes
from vintyl.core import snap as snapping
from vintyl.gui import N_, _
from vintyl.gui.node_editor import KEYS as NODE_KEYS
from vintyl.gui.node_editor import HandleMark, NodeEditor, NodeMark

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
    "snap": QColor("#c026d3"),
}
MIN_STRIP_LENGTH = 1000.0        # mm of strip always shown, more when the design is longer
GRID_MM = 50.0
SNAP_PIXELS = 10                 # snap distance on screen
SNAP_LABELS = {snapping.CORNER: N_("corner"), snapping.CENTRE: N_("centre"),
               snapping.MIDDLE: N_("middle"), snapping.EDGE: N_("on line"),
               snapping.ALIGNED: N_("in line")}
DRAW_TOOLS = ("rectangle", "ellipse", "polygon", "line")


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
    nudged = Signal(object, float, float)     # element, dx, dy (view mm), arrow keys
    drawn = Signal(str, QRectF)               # tool, rectangle dragged (view mm, normalised)
    line_drawn = Signal(QPointF, QPointF)     # line tool: start, end (view mm)
    cursor = Signal(float, float)             # pointer in material coordinates (x along, y across)
    nodes_changed = Signal(object, list, bool)  # element, its new paths (view mm), unused
    node_selection = Signal(int)              # number of selected nodes in the node tool
    edit_nodes = Signal(object)               # element double-clicked with the select tool
    cancel_tool = Signal()                    # Escape in a drawing tool


class ElementItem(QGraphicsPathItem):
    """One element. Its paths are already in scene coordinates; a drag moves
    the item and, when the mouse is released, the element's nodes."""

    def __init__(self, element, view):
        super().__init__(painter_path(element.paths))
        self.element = element
        self.view = view
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setPen(cosmetic_pen(COLORS["cut"] if element.cut else COLORS["skip"], 1.6,
                                 Qt.SolidLine if element.cut else Qt.DashLine))
        self._press = None
        self._dragging = False
        self._snap_cache = None
        self.polys = curves.flatten(element.paths, tol=0.1)

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
        elif self.isSelected() and self.view.tool != "nodes":
            painter.setPen(cosmetic_pen(COLORS["selection"], 1.2, Qt.DashLine))
            painter.drawRect(r)

    def snap_shape(self):
        """Snap targets of this element in scene coordinates (cached until it moves)."""
        t = self.sceneTransform()
        key = (t.dx(), t.dy())
        if self._snap_cache is None or self._snap_cache[0] != key:
            polys = [[(x + t.dx(), y + t.dy()) for x, y in poly] for poly in self.polys]
            r = self.sceneBoundingRect()
            self._snap_cache = (key, snapping.SnapShape(polys, (r.left(), r.top(), r.right(), r.bottom())))
        return self._snap_cache[1]

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self._dragging:
            return self.view.snap_drag(self, value)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self._press = self.pos()
        self._dragging = event.button() == Qt.LeftButton
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self.view.hide_snap_marker()
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
        self.polygon_sides = 6
        self.snap_objects = True
        self.grid_mm = 0.0               # snap to a grid of this step when no object is near (0: off)
        self.node_editor = NodeEditor(self)
        self._items = []
        self._knife_items = []
        self._snap_marker = None
        self._guides = None
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
        self.node_editor.forget_graphics()      # its marks went with the scene
        self._items = []
        self._knife_items = []          # cleared with the scene; the window draws them again
        self._snap_marker = None
        self._guides = None
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

        chosen = None
        for e in design.elements:
            item = ElementItem(e, self)
            scene.addItem(item)
            item.setFlag(QGraphicsItem.ItemIsMovable, self.tool == "select")
            self._items.append(item)
            if e is selected:
                item.setSelected(True)
                chosen = item
        scene.setSceneRect(strip.adjusted(-60, -60, 60, 60))
        scene.blockSignals(False)
        if self.tool == "nodes":
            self._place_nodes(chosen)
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
        for item in self._knife_items:
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

    # ---- snapping (adapted from Kerfly) -------------------------------------------------
    @staticmethod
    def snap_suspended():
        """Alt held down: no snapping at all for a moment."""
        return bool(QApplication.keyboardModifiers() & Qt.AltModifier)

    def _snap_tolerance(self):
        return SNAP_PIXELS / max(abs(self.transform().m11()), 1e-9)

    def _snap_shapes(self, exclude=()):
        shapes_ = [i.snap_shape() for i in self._items if i not in exclude]
        # the material: its corners, edges and their middles (length: the visible strip)
        strip = self.material_rect(max(MIN_STRIP_LENGTH, self.sceneRect().right()))
        shapes_.append(snapping.SnapShape([[(strip.left(), strip.bottom()), (strip.left(), strip.top())],
                                           [(strip.left(), strip.top()), (strip.right(), strip.top())],
                                           [(strip.left(), strip.bottom()), (strip.right(), strip.bottom())]],
                                          (0.0, -self.width_mm, 0.0, 0.0)))
        return shapes_

    def hide_snap_marker(self):
        if self._snap_marker is not None:
            if self._snap_marker.scene() is not None:
                self.scene().removeItem(self._snap_marker)
            self._snap_marker = None

    def show_snap_marker(self, x, y, kind):
        self.hide_snap_marker()
        path = QPainterPath()
        if kind == snapping.CORNER:
            path.addRect(-5, -5, 10, 10)
        elif kind == snapping.CENTRE:
            path.addEllipse(-5, -5, 10, 10)
            path.moveTo(-7, 0)
            path.lineTo(7, 0)
            path.moveTo(0, -7)
            path.lineTo(0, 7)
        elif kind == snapping.MIDDLE:
            path.moveTo(0, -6)
            path.lineTo(6, 5)
            path.lineTo(-6, 5)
            path.closeSubpath()
        elif kind == snapping.ALIGNED:
            path.moveTo(-7, 0)
            path.lineTo(7, 0)
            path.moveTo(0, -7)
            path.lineTo(0, 7)
        else:
            path.moveTo(-5, -5)
            path.lineTo(5, 5)
            path.moveTo(-5, 5)
            path.lineTo(5, -5)
        marker = QGraphicsPathItem(path)
        marker.setPen(cosmetic_pen(COLORS["snap"], 2))
        marker.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        marker.setPos(QPointF(x, y))
        marker.setZValue(50)
        marker.setAcceptedMouseButtons(Qt.NoButton)
        label = QGraphicsSimpleTextItem(_(SNAP_LABELS[kind]), marker)
        label.setBrush(QBrush(COLORS["snap"]))
        label.setPos(8, 4)
        self.scene().addItem(marker)
        self._snap_marker = marker

    def _show_guides(self, guides):
        self._remove_guides()
        path = QPainterPath()
        for x1, y1, x2, y2 in guides:
            path.moveTo(x1, y1)
            path.lineTo(x2, y2)
        self._guides = self.scene().addPath(path, cosmetic_pen(COLORS["snap"], 1, Qt.DashLine))
        self._guides.setZValue(44)

    def _remove_guides(self):
        g = self._guides
        if g is not None and g.scene() is not None:
            self.scene().removeItem(g)
        self._guides = None

    def snap_point(self, p, exclude=()):
        """A point the user clicks or drags to, snapped to other elements and
        the material (when object snapping is on) or else to the grid."""
        if self.snap_suspended():
            self.hide_snap_marker()
            return p
        if self.snap_objects:
            hit = snapping.find_snap(p.x(), p.y(), self._snap_shapes(exclude), self._snap_tolerance())
            if hit is not None:
                self.show_snap_marker(*hit)
                return QPointF(hit[0], hit[1])
        self.hide_snap_marker()
        if self.grid_mm > 0:
            g = self.grid_mm
            return QPointF(round(p.x() / g) * g, round(p.y() / g) * g)
        return p

    def snap_drag(self, item, new_pos):
        """While an element is dragged: move it so one of its corners, middles or
        its centre lands on a target of another element or of the material."""
        if not self.snap_objects or len(self._selected_items()) > 1 or self.snap_suspended():
            self.hide_snap_marker()
            return new_pos
        delta = new_pos - item.pos()
        r = item.sceneBoundingRect().translated(delta)
        refs = [(r.left(), r.top()), (r.right(), r.top()), (r.right(), r.bottom()), (r.left(), r.bottom()),
                (r.center().x(), r.center().y()), (r.center().x(), r.top()), (r.right(), r.center().y()),
                (r.center().x(), r.bottom()), (r.left(), r.center().y())]
        off = snapping.snap_offset(refs, self._snap_shapes(exclude=(item,)), self._snap_tolerance())
        if off is None:
            self.hide_snap_marker()
            return new_pos
        dx, dy, x, y, kind = off
        self.show_snap_marker(x, y, kind)
        return new_pos + QPointF(dx, dy)

    # ---- selection ------------------------------------------------------------
    def _selected_items(self):
        return [i for i in self.scene().selectedItems() if isinstance(i, ElementItem)]

    def _selection_changed(self):
        sel = self._selected_items()
        if self.tool == "nodes":
            self._place_nodes(sel[0] if sel else None)
        self.signals.selected.emit(sel[0].element if sel else None)

    def select(self, element):
        for item in self._items:
            item.setSelected(item.element is element)

    def item_of(self, element):
        for item in self._items:
            if item.element is element:
                return item
        return None

    # ---- node tool (vintyl.gui.node_editor) ------------------------------------------
    def _place_nodes(self, item):
        if item is None or not item.element.paths:
            self.node_editor.detach()
            return
        # the element's paths are in scene coordinates, the item sits at (0, 0)
        self.node_editor.attach(item, item.element.paths)

    # ---- tools ----------------------------------------------------------------
    def set_tool(self, tool):
        self._cancel_drawing()
        self.hide_snap_marker()
        self.tool = tool
        for item in self._items:
            item.setFlag(QGraphicsItem.ItemIsMovable, tool == "select")
            item.update()
        if tool == "nodes":
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.ArrowCursor)
            sel = self._selected_items()
            self._place_nodes(sel[0] if sel else None)
            return
        self.node_editor.detach()
        self.setDragMode(QGraphicsView.RubberBandDrag if tool == "select" else QGraphicsView.NoDrag)
        self.viewport().setCursor(Qt.ArrowCursor if tool == "select" else Qt.CrossCursor)

    def _cancel_drawing(self):
        self._draw_start = None
        if self._draw_item is not None:
            if self._draw_item.scene() is self.scene():
                self.scene().removeItem(self._draw_item)
            self._draw_item = None

    def _rubber(self, a, b):
        r = QRectF(a, b).normalized()
        path = QPainterPath()
        if self.tool == "ellipse":
            path.addEllipse(r)
        elif self.tool == "line":
            path.moveTo(a)
            path.lineTo(b)
        elif self.tool == "polygon":
            path = painter_path(shapes.polygon(r.left(), r.top(), r.right(), r.bottom(), self.polygon_sides))
        else:
            path.addRect(r)
        if self._draw_item is None:
            self._draw_item = QGraphicsPathItem()
            self._draw_item.setPen(cosmetic_pen(COLORS["selection"], 1.2, Qt.DashLine))
            self.scene().addItem(self._draw_item)
        self._draw_item.setPath(path)

    # ---- mouse, keys and wheel ------------------------------------------------------
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
        if self.tool in DRAW_TOOLS and event.button() == Qt.LeftButton:
            self._draw_start = self.snap_point(self.mapToScene(event.position().toPoint()))
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
            self._rubber(self._draw_start, self.snap_point(p))
            return
        if self.tool in DRAW_TOOLS:
            self.snap_point(p)                  # show where a click would land
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._panning is not None:
            self._panning = None
            self.viewport().setCursor(Qt.ArrowCursor if self.tool in ("select", "nodes") else Qt.CrossCursor)
            return
        if self._draw_start is not None and event.button() == Qt.LeftButton:
            a = self._draw_start
            b = self.snap_point(self.mapToScene(event.position().toPoint()))
            self._cancel_drawing()
            self.hide_snap_marker()
            if (b - a).manhattanLength() > 0.5:
                if self.tool == "line":
                    self.signals.line_drawn.emit(a, b)
                else:
                    self.signals.drawn.emit(self.tool, QRectF(a, b).normalized())
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.tool == "select":
            hit = self.itemAt(event.position().toPoint())
            if isinstance(hit, ElementItem):
                self.signals.edit_nodes.emit(hit.element)
                event.accept()
                return
        if event.button() == Qt.LeftButton and self.tool == "nodes" and self.node_editor.item is not None:
            hit = self.itemAt(event.position().toPoint())
            if not isinstance(hit, (NodeMark, HandleMark)):
                self.node_editor.insert_at(self.mapToScene(event.position().toPoint()))
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def event(self, event):
        # in the node tool its letter keys and Delete go to the nodes, not to menu shortcuts
        if (event.type() == QEvent.ShortcutOverride and self.tool == "nodes"
                and self.node_editor.item is not None and event.key() in NODE_KEYS
                and not event.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        """Node keys in the node tool; Escape leaves a tool or the selection;
        arrows move the selected element 1 mm (Shift: 10 mm)."""
        if self.tool == "nodes" and self.node_editor.item is not None and self.node_editor.key(event):
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            if self.tool != "select":
                self.signals.cancel_tool.emit()
            else:
                self.scene().clearSelection()
            event.accept()
            return
        steps = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
        items = self._selected_items()
        if event.key() in steps and items and self.tool == "select":
            step = 10.0 if event.modifiers() & Qt.ShiftModifier else 1.0
            dx, dy = steps[event.key()]
            self.signals.nudged.emit(items[0].element, dx * step, dy * step)
            event.accept()
            return
        super().keyPressEvent(event)

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
