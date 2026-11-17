"""
The working area: the strip of material with the design on it.

The material is shown as you see it from the front of the cutter: scene
units are millimetres, x right, y down; the origin (the cutter's Origin)
at (0, 0) in the lower right corner; the cutting width to the left (x from
-width to 0); the material running away from you upwards (y negative),
as long as fills the window when the sheet is fitted to it, and longer
when the design reaches further. See
vintyl.core.design for the material coordinates.

As in Kerfly: the wheel zooms about the pointer, the middle button drags
the view; elements snap to corners, centres, middles and lines of other
elements and of the material (Alt held: no snapping); a double click on an
element edits its nodes (vintyl.gui.node_editor). The snapping methods are
adapted from Kerfly's bed view (kerfly/gui/preview.py, commit cf48565).

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import (QApplication, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem,
                               QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView)

from vintyl.core import curves, shapes
from vintyl.core.design import material_to_view
from vintyl.core import snap as snapping
from vintyl.gui import N_, _
from vintyl.gui.node_editor import KEYS as NODE_KEYS
from vintyl.gui.node_editor import HandleMark, NodeEditor, NodeMark

COLORS = {
    "background": QColor("#5b6270"),
    "material": QColor("#f4f5f7"),
    "material_edge": QColor("#9ca3af"),
    "grid": QColor("#e3e6ea"),
    "grid_on": QColor("#cfd5dd"),
    "label": QColor("#e5e7eb"),
    "cut": QColor("#be185d"),
    "skip": QColor("#9ca3af"),
    "selection": QColor("#2563eb"),
    "origin": QColor("#f59e0b"),
    "off": QColor("#dc2626"),
    "snap": QColor("#c026d3"),
}
MIN_STRIP_LENGTH = 100.0         # mm of material shown at the least (a very flat window)
# room round the sheet when it is fitted to the window, in screen px (UI v2):
# its titles on top, the X ruler's numbers on the right, the Y ruler, its
# caption and the zoom box under it
FIT_LEFT_PX, FIT_TOP_PX, FIT_RIGHT_PX, FIT_BOTTOM_PX = 28, 34, 52, 84
DESIGN_ROOM_MM = 100.0           # material shown above the highest element
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
    selected = Signal(object)                 # the first selected element, or None
    selection = Signal(list)                  # every selected element
    moved = Signal(list, float, float)        # elements moved together, dx, dy (view mm)
    nudged = Signal(list, float, float)       # elements, dx, dy (view mm), arrow keys
    drawn = Signal(str, QRectF)               # tool, rectangle dragged (view mm, normalised)
    line_drawn = Signal(QPointF, QPointF)     # line tool: start, end (view mm)
    polyline_drawn = Signal(list, bool)       # polyline tool: corner points (view mm), closed
    text_clicked = Signal(QPointF)            # text tool: where the text starts (top left, view mm)
    pen_drawn = Signal(list)                  # pen or freehand: the drawn path (curves subpaths, view mm)
    measured = Signal(float, float)
    sheet_changed = Signal()                  # the window changed shape: draw the sheet again
    context = Signal(object, QPoint)          # right click: the element under the pointer (or None), screen point           # the ruler: dx, dy in mm (screen right / down)
    cursor = Signal(float, float)             # pointer in material coordinates (along, across)
    nodes_changed = Signal(object, list, bool)  # element, its new paths (view mm), unused
    node_selection = Signal(int)              # number of selected nodes in the node tool
    edit_nodes = Signal(object)               # element double-clicked with the select tool
    cancel_tool = Signal()                    # Escape in a drawing tool
    resized = Signal(list, QRectF, QRectF)    # elements, their box before and after (view mm)


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
        # the fill pattern (drawn by a pen; with the knife it is not shown)
        self.fill_path = QPainterPath()
        for line in element.fill_lines():           # the same as the job's: worked out once (cached)
            self.fill_path.moveTo(QPointF(*line[0]))
            for q in line[1:]:
                self.fill_path.lineTo(QPointF(*q))

    def boundingRect(self):
        return super().boundingRect().united(self.fill_path.boundingRect())

    def shape(self):
        # pick by the whole bounding box: thin outlines are hard to hit
        p = QPainterPath()
        p.addRect(self.path().boundingRect().adjusted(-1, -1, 1, 1))
        return p

    def paint(self, painter, option, widget=None):
        painter.setBrush(Qt.NoBrush)
        if not self.fill_path.isEmpty() and self.view.pen_mode:      # a knife has no fill: not shown
            color = QColor(COLORS["cut"] if self.element.cut else COLORS["skip"])
            color.setAlpha(170)
            painter.setPen(cosmetic_pen(color, 1.0))
            painter.drawPath(self.fill_path)
        painter.setPen(self.pen())
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

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        for h in self.view._handles:             # the squares come back where the shapes end up
            h.setVisible(False)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self.view.hide_snap_marker()
        super().mouseReleaseEvent(event)
        if self._press is None:
            return
        moved = self.pos() - self._press
        self._press = None
        if abs(moved.x()) > 1e-6 or abs(moved.y()) > 1e-6:
            # every selected element moved with this one (Qt drags them together)
            moved_els = [i.element for i in self.view._selected_items()] or [self.element]
            self.view.signals.moved.emit(moved_els, moved.x(), moved.y())


class SizeHandle(QGraphicsRectItem):
    """A small square on the selection's box: drag it to change the size.
    The opposite corner (or side) stays where it is; with the proportions
    locked (view.keep_ratio) both sides change together. The idea and the
    look come from Kerfly's bed view (kerfly/gui/preview.py, Handle)."""

    # where on the box: (fx, fy), 0 = left / top, 1 = right / bottom, 0.5 = the middle of a side
    PLACES = ((0, 0), (0.5, 0), (1, 0), (1, 0.5), (1, 1), (0.5, 1), (0, 1), (0, 0.5))
    CURSORS = {(0, 0): Qt.SizeFDiagCursor, (1, 1): Qt.SizeFDiagCursor, (1, 0): Qt.SizeBDiagCursor,
               (0, 1): Qt.SizeBDiagCursor, (0.5, 0): Qt.SizeVerCursor, (0.5, 1): Qt.SizeVerCursor,
               (0, 0.5): Qt.SizeHorCursor, (1, 0.5): Qt.SizeHorCursor}

    def __init__(self, view, place):
        super().__init__(-4.5, -4.5, 9, 9)
        self.view = view
        self.place = place
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setZValue(40)
        self.setPen(cosmetic_pen(COLORS["selection"], 1.5))
        self.setBrush(QBrush(QColor("white")))
        self.setCursor(self.CURSORS[place])
        self._box = None

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._box = QRectF(self.view.selection_box())
        self._items = self.view._selected_items()
        event.accept()

    def new_box(self, p, keep_ratio):
        """The box after dragging this handle to p (scene mm)."""
        b = self._box
        fx, fy = self.place
        x0, x1, y0, y1 = b.left(), b.right(), b.top(), b.bottom()
        if fx == 0:
            x0 = min(p.x(), x1 - 0.1)
        elif fx == 1:
            x1 = max(p.x(), x0 + 0.1)
        if fy == 0:
            y0 = min(p.y(), y1 - 0.1)
        elif fy == 1:
            y1 = max(p.y(), y0 + 0.1)
        if keep_ratio and b.width() > 1e-9 and b.height() > 1e-9:
            # the same scale both ways; a side handle drives its own direction
            if fx == 0.5:
                k = (y1 - y0) / b.height()
            elif fy == 0.5:
                k = (x1 - x0) / b.width()
            else:
                k = max((x1 - x0) / b.width(), (y1 - y0) / b.height())
            w, h = b.width() * k, b.height() * k
            if fx == 0:
                x0 = x1 - w
            elif fx == 1:
                x1 = x0 + w
            else:
                cx = b.center().x()
                x0, x1 = cx - w / 2, cx + w / 2
            if fy == 0:
                y0 = y1 - h
            elif fy == 1:
                y1 = y0 + h
            else:
                cy = b.center().y()
                y0, y1 = cy - h / 2, cy + h / 2
        return QRectF(QPointF(x0, y0), QPointF(x1, y1))

    def mouseMoveEvent(self, event):
        if self._box is None:
            return
        new = self.new_box(event.scenePos(), self.view.keep_ratio)
        t = box_transform(self._box, new)
        for item in self._items:          # live preview: the shapes follow the handle
            item.setTransform(t)
        self.view.place_handles(new)

    def mouseReleaseEvent(self, event):
        if self._box is None:
            return
        new = self.new_box(event.scenePos(), self.view.keep_ratio)
        old, self._box = self._box, None
        for item in self._items:
            item.setTransform(QTransform())
        if abs(new.width() - old.width()) > 1e-6 or abs(new.height() - old.height()) > 1e-6 \
                or abs(new.left() - old.left()) > 1e-6 or abs(new.top() - old.top()) > 1e-6:
            self.view.signals.resized.emit([i.element for i in self._items], old, new)


def box_transform(old, new):
    """QTransform taking the box `old` onto the box `new`."""
    sx = new.width() / old.width() if old.width() > 1e-9 else 1.0
    sy = new.height() / old.height() if old.height() > 1e-9 else 1.0
    t = QTransform()
    t.translate(new.left(), new.top())
    t.scale(sx, sy)
    t.translate(-old.left(), -old.top())
    return t


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
        self.keep_ratio = True           # size handles keep the proportions (the lock in the options bar)
        self._handles = []
        self._size_labels = []          # the size beside the selection (cleared with the scene)
        self._items = []
        self._knife_items = []
        self._snap_marker = None
        self._guides = None
        self._draw_start = None
        self._draw_item = None
        self._poly_points = []           # polyline being drawn (view mm)
        self._pen = None                 # pen path being drawn: {"nodes": [...], "pressed": bool}
        self._freehand = None            # points of a freehand line being drawn
        self._measure_start = None
        self._measure_item = None
        self._panning = None
        self._user_zoomed = False
        self._fit_scale = 1.0
        self.zoom_box = None
        self.zoom_label = None
        self._design_box = None
        self.pen_mode = False            # the cutter holds a pen: fills are drawn, not skipped
        self._preview_item = None        # a dashed preview of shapes about to be added
        from PySide6.QtCore import QTimer
        self._sheet_timer = QTimer(self)
        self._sheet_timer.setSingleShot(True)
        self._sheet_timer.setInterval(60)
        self._sheet_timer.timeout.connect(self._sheet_due)
        self.scene().selectionChanged.connect(self._selection_changed)
        self._make_zoom_box()

    # ---- content --------------------------------------------------------------
    def material_rect(self, length):
        return QRectF(-self.width_mm, -length, self.width_mm, length)

    def off_material(self, rect):
        tol = 0.05
        return rect.left() < -self.width_mm - tol or rect.right() > tol or rect.bottom() > tol

    def show_design(self, design, width_mm, selected=None):
        """Draw the material and every element; keep the zoom unless asked to fit."""
        self.width_mm = float(width_mm)
        scene = self.scene()
        scene.blockSignals(True)
        scene.clear()
        self.node_editor.forget_graphics()      # its marks went with the scene
        self._handles = []
        self._size_labels = []          # the size beside the selection (cleared with the scene)
        self._items = []
        self._knife_items = []          # cleared with the scene; the window draws them again
        self._frame_item = None
        self._preview_item = None       # cleared with the scene
        self._snap_marker = None
        self._guides = None
        box = design.bounds()
        self._design_box = box
        # the sheet: the cutting width across, and long enough to fill the
        # window from top to bottom; longer (upwards) when the design reaches
        # further (y up is negative)
        length = max(self.window_length(), (-box[2] + DESIGN_ROOM_MM) if box else 0.0)
        self.length_mm = length
        strip = self.material_rect(length)
        w = self.width_mm

        scene.addRect(strip, QPen(Qt.NoPen), QBrush(COLORS["material"]))
        # the grid: with the grid on, its step (and snapping to it); else light lines every 50 mm
        step = self.grid_mm if self.grid_mm > 0 else GRID_MM
        grid = cosmetic_pen(COLORS["grid_on"] if self.grid_mm > 0 else COLORS["grid"], 1)
        if (w / step) * (length / step) < 40000:       # not thousands of lines at a tiny step
            x = -step
            while x > -w:
                scene.addLine(x, -length, x, 0, grid)
                x -= step
            y = -step
            while y > -length:
                scene.addLine(-w, y, 0, y, grid)
                y -= step
        edge = cosmetic_pen(COLORS["material_edge"], 1.5)
        scene.addLine(-w, 0, -w, -length, edge)          # the edges the knife cannot pass
        scene.addLine(0, 0, 0, -length, edge)
        scene.addLine(-w, 0, 0, 0, edge)
        self._label(_("Cutting width %g mm") % w,
                    QPointF(-w, -length - 3), above=True)
        self._label(_("X ↑ along the material"), QPointF(0, -length - 3), above=True, right=True)
        self._rulers(w, length)
        self._origin_marker()

        chosen = None
        wanted = selected if isinstance(selected, (list, tuple)) else ([selected] if selected is not None else [])
        for e in design.elements:
            item = ElementItem(e, self)
            scene.addItem(item)
            item.setFlag(QGraphicsItem.ItemIsMovable, self.tool == "select")
            self._items.append(item)
            if any(e is w for w in wanted):
                item.setSelected(True)
                chosen = chosen or item
        # room round the sheet, so it can be placed off-centre (fit_all) and panned
        scene.setSceneRect(strip.adjusted(-400, -400, 400, 400))
        scene.blockSignals(False)
        if self.tool == "nodes":
            self._place_nodes(chosen)
        self.place_handles()
        if not self._user_zoomed:
            self.fit_all()

    RULER_STEP_MM = 100.0                # a mark and a number every this many mm
    TICK_PX = 6

    def _rulers(self, w, length):
        """Rulers in mm from the origin (UI v2): under the front edge (Y, from
        right to left) and beside the right edge (X, upwards), a number every
        100 mm; the marks keep their size on screen whatever the zoom."""
        from PySide6.QtWidgets import QGraphicsLineItem
        pen = cosmetic_pen(COLORS["label"], 1.0)
        k = 0.0
        while k <= w + 1e-6:                              # across: under the front edge
            tick = QGraphicsLineItem(0, 0, 0, self.TICK_PX)
            tick.setPen(pen)
            tick.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            tick.setPos(-k, 0)
            self.scene().addItem(tick)
            self._label("%g" % k, QPointF(-k, 0), centre=True, below_px=self.TICK_PX + 1)
            k += self.RULER_STEP_MM
        k = self.RULER_STEP_MM
        while k <= length + 1e-6:                         # along: beside the right edge
            tick = QGraphicsLineItem(0, 0, self.TICK_PX, 0)
            tick.setPen(pen)
            tick.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            tick.setPos(0, -k)
            self.scene().addItem(tick)
            self._label("%g" % k, QPointF(0, -k), beside_px=self.TICK_PX + 3)
            k += self.RULER_STEP_MM
        self._label(_("← Y across, mm"), QPointF(-w, 0), below_px=self.TICK_PX + 16)

    def _label(self, text, pos, above=False, right=False, centre=False, below_px=0, beside_px=0):
        """A small light label on the dark round the sheet; offsets in screen px."""
        item = QGraphicsSimpleTextItem(text)
        item.setBrush(COLORS["label"])
        f = QFont()
        f.setPointSizeF(9)
        item.setFont(f)
        item.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        r = item.boundingRect()
        item.setPos(pos)
        dx = -r.width() if right else (-r.width() / 2.0 if centre else beside_px)
        dy = -r.height() if above else (below_px if below_px else (-r.height() / 2.0 if beside_px else 0))
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

    # ---- the weeding frame ------------------------------------------------------------
    def show_frame(self, poly):
        """A light dashed outline where the weeding frame will be cut (poly in
        material mm), or nothing (None)."""
        item = getattr(self, "_frame_item", None)
        if item is not None and item.scene() is self.scene():
            self.scene().removeItem(item)
        self._frame_item = None
        if not poly:
            return
        path = QPainterPath(QPointF(*material_to_view(*poly[0])))
        for p in poly[1:]:
            path.lineTo(QPointF(*material_to_view(*p)))
        item = QGraphicsPathItem(path)
        pen = cosmetic_pen(COLORS["cut"], 1.2, Qt.DashLine)
        c = QColor(COLORS["cut"])
        c.setAlpha(140)
        pen.setColor(c)
        item.setPen(pen)
        item.setZValue(5)
        item.setAcceptedMouseButtons(Qt.NoButton)
        self.scene().addItem(item)
        self._frame_item = item

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
            start = QPointF(*material_to_view(*poly[0]))
            travel.moveTo(pos)
            travel.lineTo(start)
            cut.moveTo(start)
            for p in poly[1:]:
                cut.lineTo(QPointF(*material_to_view(*p)))
            pos = QPointF(*material_to_view(*poly[-1]))
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
            self._knife_items.append(self._order_dot(k, QPointF(*material_to_view(*poly[0]))))

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
        # the material: the origin, the far edge of the width, the middle of the
        # front edge, and the side edges and front edge as lines
        L = getattr(self, "length_mm", MIN_STRIP_LENGTH)
        w = self.width_mm
        shapes_.append(snapping.SnapShape([[(-w, 0.0), (-w, -L)], [(0.0, 0.0), (0.0, -L)], [(-w, 0.0), (0.0, 0.0)]],
                                          (-w, 0.0, 0.0, 0.0)))
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
        if getattr(self, "_expanding", False):
            return
        # a group is selected as a whole: pick up the other members
        groups = {i.element.group for i in self._selected_items() if i.element.group}
        if groups:
            self._expanding = True
            for item in self._items:
                if item.element.group in groups and not item.isSelected():
                    item.setSelected(True)
            self._expanding = False
        sel = self._selected_items()
        if self.tool == "nodes":
            self._place_nodes(sel[0] if len(sel) == 1 else None)
        self.place_handles()
        self.signals.selection.emit([i.element for i in sel])
        self.signals.selected.emit(sel[0].element if sel else None)

    def select(self, element):
        self.select_many([element] if element is not None else [])

    def select_many(self, elements):
        self._expanding = True
        for item in self._items:
            item.setSelected(any(item.element is e for e in elements))
        self._expanding = False
        self._selection_changed()

    def item_of(self, element):
        for item in self._items:
            if item.element is element:
                return item
        return None

    # ---- size handles -----------------------------------------------------------------
    def selection_box(self):
        """The box round the selected shapes themselves (their geometry, not
        the drawn line's width on screen), where they are now."""
        box = QRectF()
        for item in self._selected_items():
            x0, x1, y0, y1 = item.element.bounds
            r = QRectF(x0, y0, x1 - x0, y1 - y0).translated(item.pos())
            box = r if box.isNull() else box.united(r)
        return box

    def place_handles(self, box=None):
        """The eight small squares round the selection (select tool only).
        box: while a square is dragged, the box it makes."""
        for label in getattr(self, "_size_labels", []):
            if label.scene() is self.scene():
                self.scene().removeItem(label)
        self._size_labels = []
        dragged = box is not None and len(self._handles) == len(SizeHandle.PLACES) \
            and all(h.scene() is self.scene() for h in self._handles)
        if not dragged:
            for h in self._handles:
                if h.scene() is self.scene():
                    self.scene().removeItem(h)
            self._handles = []
            if self.tool != "select" or not self._selected_items():
                return
        box = box if box is not None else self.selection_box()
        if dragged:
            # the squares are moved, not made again: the one under the mouse
            # holds the drag, and taken off the scene it lost it (the shape
            # moved a little, then stayed as it was)
            for h in self._handles:
                h.setPos(box.left() + h.place[0] * box.width(), box.top() + h.place[1] * box.height())
        else:
            for place in SizeHandle.PLACES:
                h = SizeHandle(self, place)
                h.setPos(box.left() + place[0] * box.width(), box.top() + place[1] * box.height())
                self.scene().addItem(h)
                self._handles.append(h)
        # the size beside the frame (UI v2): the width under it, the height at its side
        for text, pos, under in ((self._mm(box.width()), QPointF(box.center().x(), box.bottom()), True),
                                 (self._mm(box.height()), QPointF(box.right(), box.center().y()), False)):
            label = QGraphicsSimpleTextItem(text)
            label.setBrush(COLORS["selection"])
            f = QFont()
            f.setPointSizeF(9)
            label.setFont(f)
            label.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            label.setZValue(60)
            r = label.boundingRect()
            label.setPos(pos)
            label.setTransform(QTransform.fromTranslate(-r.width() / 2.0, 10) if under
                               else QTransform.fromTranslate(10, -r.height() / 2.0))
            self.scene().addItem(label)
            self._size_labels.append(label)

    @staticmethod
    def _mm(value):
        """A size as the window writes numbers: one decimal, a decimal comma
        in the languages that write one."""
        from vintyl import i18n
        return i18n.decimal("%.1f" % value)

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
        self._clear_measure()
        self.hide_snap_marker()
        self.tool = tool
        for item in self._items:
            item.setFlag(QGraphicsItem.ItemIsMovable, tool == "select")
            item.update()
        if tool == "nodes":
            self.place_handles()
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.ArrowCursor)
            sel = self._selected_items()
            self._place_nodes(sel[0] if sel else None)
            return
        self.node_editor.detach()
        self.place_handles()
        self.setDragMode(QGraphicsView.RubberBandDrag if tool == "select" else QGraphicsView.NoDrag)
        self.viewport().setCursor(Qt.ArrowCursor if tool == "select" else Qt.CrossCursor)

    # ---- polyline: click = corner, click the first corner = closed shape,
    # double-click or Enter = open line, Backspace = drop the last corner,
    # Escape = drop the line, Shift = 45 degree steps (adapted from Kerfly)
    def _poly_constrained(self, p, shift):
        if not shift or not self._poly_points:
            return p
        last = self._poly_points[-1]
        dx, dy = p.x() - last.x(), p.y() - last.y()
        angle = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
        length = math.hypot(dx, dy)
        return QPointF(last.x() + length * math.cos(angle), last.y() + length * math.sin(angle))

    def _near_first_point(self, p):
        if len(self._poly_points) < 3:
            return False
        a = self.mapFromScene(self._poly_points[0])
        b = self.mapFromScene(p)
        return abs(a.x() - b.x()) <= 8 and abs(a.y() - b.y()) <= 8

    def _draw_polyline_item(self, cursor=None):
        if self._draw_item is not None and self._draw_item.scene() is self.scene():
            self.scene().removeItem(self._draw_item)
        self._draw_item = None
        pts = list(self._poly_points) + ([cursor] if cursor is not None else [])
        if not pts:
            return
        path = QPainterPath(pts[0])
        for q in pts[1:]:
            path.lineTo(q)
        closing = cursor is not None and self._near_first_point(cursor)
        pen = cosmetic_pen(COLORS["cut"] if closing else COLORS["selection"], 1.4 if closing else 1.2,
                           Qt.SolidLine if closing else Qt.DashLine)
        self._draw_item = self.scene().addPath(path, pen)
        self._draw_item.setZValue(30)
        dot = QGraphicsEllipseItem(-4, -4, 8, 8, self._draw_item)     # the start: click it to close
        dot.setPen(pen)
        dot.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        dot.setPos(pts[0])

    def _finish_polyline(self, closed):
        pts = []
        for q in self._poly_points:
            if not pts or abs(q.x() - pts[-1].x()) > 1e-6 or abs(q.y() - pts[-1].y()) > 1e-6:
                pts.append(q)
        self._poly_points = []
        self._cancel_drawing()
        if len(pts) >= (3 if closed else 2):
            self.signals.polyline_drawn.emit([(q.x(), q.y()) for q in pts], closed)

    # ---- pen, freehand and ruler: adapted from Kerfly's bed view (kerfly/gui/preview.py) ----
    # pen: click = corner, press and drag = smooth node with handles; click the
    # first node to close; double-click or Enter finishes; Backspace; Esc; Shift 45 degrees
    def _pen_path(self, cursor=None):
        nodes = [list(n) for n in self._pen["nodes"]]
        if cursor is not None and nodes:
            nodes.append(curves.node(cursor.x(), cursor.y()))
        return [{"closed": False, "nodes": nodes}]

    def _remove_draw_item(self):
        if self._draw_item is not None and self._draw_item.scene() is self.scene():
            self.scene().removeItem(self._draw_item)
        self._draw_item = None

    def _draw_pen(self, cursor=None):
        self._remove_draw_item()
        if not self._pen or not self._pen["nodes"]:
            return
        qp = QPainterPath()
        for poly in curves.flatten(self._pen_path(cursor), tol=0.05):
            qp.moveTo(QPointF(*poly[0]))
            for q in poly[1:]:
                qp.lineTo(QPointF(*q))
        last = self._pen["nodes"][-1]
        for k in (2, 4):                                   # the handles of the last node
            if last[k] is not None:
                qp.moveTo(QPointF(last[0], last[1]))
                qp.lineTo(QPointF(last[k], last[k + 1]))
        closing = cursor is not None and self._pen_near_first(cursor)
        pen = cosmetic_pen(COLORS["cut"] if closing else COLORS["selection"], 1.3,
                           Qt.SolidLine if closing else Qt.DashLine)
        self._draw_item = self.scene().addPath(qp, pen)
        self._draw_item.setZValue(30)
        first = self._pen["nodes"][0]
        dot = QGraphicsEllipseItem(-4, -4, 8, 8, self._draw_item)
        dot.setPen(pen)
        dot.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        dot.setPos(QPointF(first[0], first[1]))

    def _pen_near_first(self, p):
        if not self._pen or len(self._pen["nodes"]) < 2:
            return False
        a = self.mapFromScene(QPointF(self._pen["nodes"][0][0], self._pen["nodes"][0][1]))
        b = self.mapFromScene(p)
        return abs(a.x() - b.x()) <= 8 and abs(a.y() - b.y()) <= 8

    def _pen_point(self, event):
        p = self.snap_point(self.mapToScene(event.position().toPoint()))
        if event.modifiers() & Qt.ShiftModifier and self._pen and self._pen["nodes"]:
            last = self._pen["nodes"][-1]
            dx, dy = p.x() - last[0], p.y() - last[1]
            angle = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
            length = math.hypot(dx, dy)
            p = QPointF(last[0] + length * math.cos(angle), last[1] + length * math.sin(angle))
        return p

    def _finish_pen(self, closed):
        if not self._pen:
            return
        nodes = []
        for n in self._pen["nodes"]:
            if not nodes or abs(n[0] - nodes[-1][0]) > 1e-6 or abs(n[1] - nodes[-1][1]) > 1e-6:
                nodes.append(n)
        self._pen = None
        self._remove_draw_item()
        if len(nodes) >= (3 if closed else 2) or (closed and len(nodes) == 2 and nodes[0][4] is not None):
            self.signals.pen_drawn.emit([{"closed": closed, "nodes": nodes}])

    # freehand: draw with the button held; ending near the start closes the shape
    def _draw_freehand(self):
        self._remove_draw_item()
        qp = QPainterPath(QPointF(*self._freehand[0]))
        for p in self._freehand[1:]:
            qp.lineTo(QPointF(*p))
        self._draw_item = self.scene().addPath(qp, cosmetic_pen(COLORS["selection"], 1.3))
        self._draw_item.setZValue(30)

    def _finish_freehand(self, end_view_pos):
        pts, self._freehand = self._freehand, None
        self._remove_draw_item()
        if not pts or len(pts) < 2:
            return
        start = self.mapFromScene(QPointF(*pts[0]))
        closed = len(pts) > 10 and abs(start.x() - end_view_pos.x()) <= 10 and abs(start.y() - end_view_pos.y()) <= 10
        tol = 1.5 / max(abs(self.transform().m11()), 1e-9)          # 1.5 screen pixels, in mm
        simple = curves.simplify(pts, tol)
        if closed and len(simple) > 3:
            simple = simple[:-1]
        if len(simple) < 2:
            return
        self.signals.pen_drawn.emit(curves.smooth_path(simple, closed and len(simple) >= 3))

    # the ruler: drag between two points (snapping works)
    def _clear_measure(self):
        self._measure_start = None
        if self._measure_item is not None and self._measure_item.scene() is self.scene():
            self.scene().removeItem(self._measure_item)
        self._measure_item = None

    def _draw_measure(self, a, b):
        if self._measure_item is not None and self._measure_item.scene() is self.scene():
            self.scene().removeItem(self._measure_item)
        qp = QPainterPath(a)
        qp.lineTo(b)
        pen = cosmetic_pen(COLORS["origin"], 1.5)
        item = self.scene().addPath(qp, pen)
        item.setZValue(48)
        for p in (a, b):
            tick = QGraphicsEllipseItem(-3, -3, 6, 6, item)
            tick.setPen(pen)
            tick.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            tick.setPos(p)
        dx, dy = b.x() - a.x(), b.y() - a.y()
        text = "%.2f mm   (%.2f × %.2f, %.1f°)" % (math.hypot(dx, dy), abs(dx), abs(dy),
                                                    math.degrees(math.atan2(-dy, dx)))
        # the text on a light box, so it reads on the sheet and beside it alike
        box = QGraphicsRectItem(item)
        box.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        box.setPos(QPointF((a.x() + b.x()) / 2.0, (a.y() + b.y()) / 2.0))
        label = QGraphicsSimpleTextItem(text, box)
        label.setBrush(QBrush(QColor("#92400e")))
        label.setPos(6, 4)
        r = label.boundingRect()
        box.setRect(QRectF(2, 1, r.width() + 8, r.height() + 6))
        box.setBrush(QBrush(QColor(255, 251, 235, 235)))
        box.setPen(cosmetic_pen(COLORS["origin"], 1.0))
        self._measure_item = item
        return text

    def _cancel_drawing(self):
        self._pen = None
        self._freehand = None
        if self.tool != "measure":
            self._clear_measure()
        self._poly_points = []
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
            self._show_zoom()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = event.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        if self.tool == "polyline" and event.button() == Qt.LeftButton:
            shift = bool(event.modifiers() & Qt.ShiftModifier)
            p = self._poly_constrained(self.snap_point(self.mapToScene(event.position().toPoint())), shift)
            if self._near_first_point(p):
                self._finish_polyline(True)
                return
            self._poly_points.append(p)
            self._draw_polyline_item()
            return
        if self.tool == "measure" and event.button() == Qt.LeftButton:
            self._clear_measure()
            self._measure_start = self.snap_point(self.mapToScene(event.position().toPoint()))
            return
        if self.tool == "freehand" and event.button() == Qt.LeftButton:
            p = self.mapToScene(event.position().toPoint())
            self._freehand = [(p.x(), p.y())]
            return
        if self.tool == "pen" and event.button() == Qt.LeftButton:
            p = self._pen_point(event)
            if self._pen_near_first(p):
                self._finish_pen(True)
            else:
                if self._pen is None:
                    self._pen = {"nodes": [], "pressed": False}
                self._pen["nodes"].append(curves.node(p.x(), p.y()))
                self._pen["pressed"] = True
                self._draw_pen()
            return
        if self.tool == "text" and event.button() == Qt.LeftButton:
            self.hide_snap_marker()
            self.signals.text_clicked.emit(self.snap_point(self.mapToScene(event.position().toPoint())))
            self.hide_snap_marker()
            return
        if self.tool in DRAW_TOOLS and event.button() == Qt.LeftButton:
            self._draw_start = self.snap_point(self.mapToScene(event.position().toPoint()))
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        p = self.mapToScene(event.position().toPoint())
        self.signals.cursor.emit(-p.y(), -p.x())
        if self._panning is not None:
            d = event.position() - self._panning
            self._panning = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(d.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(d.y()))
            return
        if self._draw_start is not None:
            self._rubber(self._draw_start, self.snap_point(p))
            return
        if self.tool == "measure" and self._measure_start is not None:
            self._draw_measure(self._measure_start, self.snap_point(p))
            return
        if self.tool == "freehand" and self._freehand is not None:
            last = self._freehand[-1]
            if math.hypot(p.x() - last[0], p.y() - last[1]) > 0.5 / max(abs(self.transform().m11()), 1e-9):
                self._freehand.append((p.x(), p.y()))
                self._draw_freehand()
            return
        if self.tool == "pen" and self._pen:
            if self._pen["pressed"]:                      # dragging out the handles of the new node
                n = self._pen["nodes"][-1]
                if math.hypot(p.x() - n[0], p.y() - n[1]) > 0.5 * self._snap_tolerance():
                    n[4], n[5] = p.x(), p.y()
                    n[2], n[3] = 2 * n[0] - p.x(), 2 * n[1] - p.y()
                self._draw_pen()
            else:
                self._draw_pen(self._pen_point(event))
            return
        if self.tool == "polyline" and self._poly_points:
            shift = bool(event.modifiers() & Qt.ShiftModifier)
            self._draw_polyline_item(self._poly_constrained(self.snap_point(p), shift))
            return
        if self.tool in DRAW_TOOLS or self.tool in ("polyline", "text", "pen", "measure"):
            self.snap_point(p)                  # show where a click would land
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._panning is not None:
            self._panning = None
            self.viewport().setCursor(Qt.ArrowCursor if self.tool in ("select", "nodes") else Qt.CrossCursor)
            return
        if self.tool == "measure" and event.button() == Qt.LeftButton and self._measure_start is not None:
            end = self.snap_point(self.mapToScene(event.position().toPoint()))
            self.hide_snap_marker()
            a, b = self.mapFromScene(self._measure_start), self.mapFromScene(end)
            if abs(a.x() - b.x()) + abs(a.y() - b.y()) < 3:      # a click, not a drag: nothing measured
                self._clear_measure()
            else:
                self._draw_measure(self._measure_start, end)
                self.signals.measured.emit(end.x() - self._measure_start.x(), end.y() - self._measure_start.y())
            self._measure_start = None
            return
        if self.tool == "freehand" and event.button() == Qt.LeftButton and self._freehand is not None:
            self._finish_freehand(event.position())
            return
        if self.tool == "pen" and event.button() == Qt.LeftButton:
            if self._pen:
                self._pen["pressed"] = False
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

    def contextMenuEvent(self, event):
        """Right click with the select tool: the window's menu for the element
        under the pointer (it gets selected first, unless it already is)."""
        if self.tool != "select":
            event.ignore()
            return
        hit = self.itemAt(event.pos())
        element = hit.element if isinstance(hit, ElementItem) else None
        if element is not None and not hit.isSelected():
            self.select(element)
        self.signals.context.emit(element, event.globalPos())
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.tool == "select":
            hit = self.itemAt(event.position().toPoint())
            if isinstance(hit, ElementItem):
                self.signals.edit_nodes.emit(hit.element)
                event.accept()
                return
        if event.button() == Qt.LeftButton and self.tool == "pen" and self._pen:
            # the first press of the double click put the last node here: finish an open path
            self._finish_pen(False)
            event.accept()
            return
        if event.button() == Qt.LeftButton and self.tool == "polyline":
            # the press of the double click already added a corner here: finish an open line
            if len(self._poly_points) >= 2:
                self._poly_points.pop()
            self._finish_polyline(False)
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
        if self.tool == "pen" and self._pen:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._finish_pen(False)
                event.accept()
                return
            if event.key() == Qt.Key_Backspace:
                self._pen["nodes"].pop()
                if not self._pen["nodes"]:
                    self._pen = None
                    self._remove_draw_item()
                else:
                    self._draw_pen()
                event.accept()
                return
            if event.key() == Qt.Key_Escape:
                self._pen = None
                self._remove_draw_item()
                event.accept()
                return
        if self.tool == "polyline" and self._poly_points:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._finish_polyline(False)
                event.accept()
                return
            if event.key() == Qt.Key_Backspace:
                self._poly_points.pop()
                self._draw_polyline_item()
                event.accept()
                return
            if event.key() == Qt.Key_Escape:            # first Escape drops the unfinished line
                self._cancel_drawing()
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
            self.signals.nudged.emit([i.element for i in items], dx * step, dy * step)
            event.accept()
            return
        super().keyPressEvent(event)

    def zoom_by(self, factor):
        """Zoom about the middle of the view (keys + and -)."""
        if 0.02 < self.transform().m11() * factor < 400:
            self._user_zoomed = True
            self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
            self.scale(factor, factor)
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            self._show_zoom()

    def show_preview(self, paths):
        """A dashed preview of shapes about to be added (curves subpaths, view
        mm); None removes it."""
        item = self._preview_item
        if item is not None and item.scene() is self.scene():
            self.scene().removeItem(item)
        self._preview_item = None
        if paths:
            self._preview_item = self.scene().addPath(painter_path(paths),
                                                      cosmetic_pen(COLORS["selection"], 1.2, Qt.DashLine))
            self._preview_item.setZValue(45)

    def window_length(self):
        """The sheet length that, with the sheet fitted to the window by its
        width, reaches the window's top and bottom: no grey bands beside it."""
        vw, vh = self.viewport().width(), self.viewport().height()
        w = getattr(self, "width_mm", 0.0) or 0.0
        if vw < 50 or vh < 50 or w <= 0:                 # not laid out yet
            return max(MIN_STRIP_LENGTH, w)
        mh, mv = FIT_LEFT_PX + FIT_RIGHT_PX, FIT_TOP_PX + FIT_BOTTOM_PX
        return max(MIN_STRIP_LENGTH, w * (vh - mv) / max(vw - mh, 1))

    def _make_zoom_box(self):
        """Zoom out, the zoom in percent (a click fits the sheet again), zoom
        in: in the lower right corner of the view (UI v2). 100 % = the whole
        sheet in the window."""
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton
        from vintyl.gui import icons
        box = QFrame(self)
        box.setObjectName("zoom_box")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(2)
        out = QToolButton()
        out.setIcon(icons.tabler("minus", "#ffffff"))
        out.setToolTip(_("Zoom out"))
        out.clicked.connect(lambda: self.zoom_by(1 / 1.25))
        self.zoom_label = QToolButton()
        self.zoom_label.setObjectName("zoom_label")
        self.zoom_label.setToolTip(_("Fit the sheet in the window"))
        self.zoom_label.clicked.connect(self.fit_requested)
        into = QToolButton()
        into.setIcon(icons.tabler("plus", "#ffffff"))
        into.setToolTip(_("Zoom in"))
        into.clicked.connect(lambda: self.zoom_by(1.25))
        for b in (out, self.zoom_label, into):
            b.setAutoRaise(True)
            lay.addWidget(b)
        self.zoom_box = box
        self._fit_scale = 1.0
        self._place_zoom_box()

    def _place_zoom_box(self):
        box = getattr(self, "zoom_box", None)
        if box is None:
            return
        box.adjustSize()
        vp = self.viewport().geometry()
        box.move(vp.right() - box.width() - 12, vp.bottom() - box.height() - 12)
        box.raise_()

    def zoom_percent(self):
        return round(100.0 * abs(self.transform().m11()) / max(self._fit_scale, 1e-9))

    def _show_zoom(self):
        if getattr(self, "zoom_label", None) is not None:
            self.zoom_label.setText("%d%%" % self.zoom_percent())
            self._place_zoom_box()

    def fit_all(self):
        rect = self.material_rect(getattr(self, "length_mm", MIN_STRIP_LENGTH))
        for item in self._items:
            rect = rect.united(item.sceneBoundingRect())
        # as fitInView, but the room round it is in screen pixels, so a narrow
        # sheet still reaches the window's edges
        mh, mv = FIT_LEFT_PX + FIT_RIGHT_PX, FIT_TOP_PX + FIT_BOTTOM_PX
        vw, vh = self.viewport().width(), self.viewport().height()
        if rect.width() <= 0 or rect.height() <= 0 or vw <= mh or vh <= mv:
            return
        k = min((vw - mh) / rect.width(), (vh - mv) / rect.height())
        self.setTransform(QTransform.fromScale(k, k))
        # the margins are not the same on each side: the sheet's middle goes to
        # the middle of the room the margins leave
        self.centerOn(rect.center().x() + (FIT_RIGHT_PX - FIT_LEFT_PX) / (2 * k),
                      rect.center().y() + (FIT_BOTTOM_PX - FIT_TOP_PX) / (2 * k))
        self._fit_scale = k
        self._show_zoom()

    def fit_requested(self):
        self._user_zoomed = False
        self.fit_all()

    def _sheet_due(self):
        """Draw the sheet again for the new size, but not in the middle of a
        drag: the scene is made again then, and the square or the shape
        under the mouse lost the drag (it moved a little, then stayed)."""
        if self.scene().mouseGrabberItem() is not None:
            self._sheet_timer.start()                 # once the button is let go
            return
        self.signals.sheet_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # the window changed shape: the sheet follows it (the window draws it
        # again; a timer, so dragging the window edge does not redraw at every pixel)
        box = self._design_box
        wanted = max(self.window_length(), (-box[2] + DESIGN_ROOM_MM) if box else 0.0)
        if abs(wanted - getattr(self, "length_mm", wanted)) > 0.5:
            self._sheet_timer.start()
        if not self._user_zoomed:
            self.fit_all()
        self._place_zoom_box()


def shape_icon(subpaths, size=48, color=None):
    """An icon drawn from a shape itself (for the ready shapes)."""
    if color is None:                        # the theme's ink (light or dark)
        from vintyl.gui import icons
        color = icons.INK
    from PySide6.QtGui import QIcon, QPixmap
    path = painter_path(subpaths)
    r = path.boundingRect()
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    k = (size - 8) / max(r.width(), r.height(), 1e-6)
    p.translate(size / 2.0, size / 2.0)
    p.scale(k, k)
    p.translate(-r.center().x(), -r.center().y())
    pen = QPen(QColor(color), 2.6 / k)
    p.setPen(pen)
    p.drawPath(path)
    p.end()
    return QIcon(pm)
