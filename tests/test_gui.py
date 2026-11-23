"""
Tests of the window (plan step 4, first part), offscreen: no screen needed.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

PySide6 = pytest.importorskip("PySide6")
pytest.importorskip("svgelements")

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QApplication, QToolButton

from vintyl.core.job import build_job
from vintyl.gui.main_window import MainWindow

SQUARE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="40mm" viewBox="0 0 60 40">
  <rect x="10" y="10" width="20" height="20" fill="#000"/>
  <circle cx="45" cy="20" r="8" fill="none" stroke="#000"/>
  <rect x="0" y="0" width="5" height="5" fill="none" stroke="none"/>
  <rect x="50" y="30" width="5" height="5" fill="#000" style="display:none"/>
</svg>
"""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# the real windows before sending, kept before the fixture below answers them
from vintyl.gui import start_dialogs as _start_dialogs  # noqa: E402
REAL_START_DIALOGS = (_start_dialogs.confirm_start, _start_dialogs.confirm_knife_test, _start_dialogs.confirm_colour)


@pytest.fixture(autouse=True)
def messages(monkeypatch):
    """Message boxes wait for a click, which never comes offscreen: record them instead."""
    from PySide6.QtWidgets import QMessageBox
    from vintyl.gui import widgets
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text, *a: shown.append(text))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)

    def answer(parent, title, text, buttons, warning=False, show=True):
        # a question: the main button (what the dialog offers to do); unsaved
        # changes when a window closes: not saved (no file dialog in the tests)
        if any(key == "discard" for key, _l, _r in buttons):
            return "discard"
        for key, _label, role in buttons:
            if role in ("main", "danger"):
                return key
        return None
    monkeypatch.setattr(widgets, "ask", answer)
    monkeypatch.setattr(widgets, "warn", lambda parent, title, text: shown.append(text))
    monkeypatch.setattr(widgets, "inform", lambda parent, title, text: None)
    from vintyl.gui import start_dialogs
    # the windows before sending say yes; their own tests use REAL_START_DIALOGS
    monkeypatch.setattr(start_dialogs, "confirm_start", lambda *a, **k: True)
    monkeypatch.setattr(start_dialogs, "confirm_knife_test", lambda *a, **k: True)
    monkeypatch.setattr(start_dialogs, "confirm_colour", lambda *a, **k: "go")
    return shown


@pytest.fixture
def win(app):
    w = MainWindow()
    yield w
    w.close()


@pytest.fixture
def svg_file(tmp_path):
    p = tmp_path / "squares.svg"
    p.write_text(SQUARE_SVG)
    return str(p)


def test_window_opens_empty(win):
    assert win.design.elements == []
    assert "Empty" in win.summary.text()
    assert win.profile.name == "Seiki SK-870T"
    assert not win.btn_start.isEnabled() and not win.btn_stop.isEnabled()
    # the panel shows only the machine; its port and width in one line
    assert win.job_profile().knife_offset_mm == pytest.approx(0.25)
    assert "780" in win.cutter_info.text() and "/dev/usb/lp1" in win.cutter_info.text()


def test_open_svg_places_it_near_the_origin(win, svg_file):
    e = win.import_svg(svg_file)
    assert e is not None and win.selected is e
    xmin, xmax, ymin, ymax = e.bounds
    # visible painted shapes only: the filled square and the circle (no hidden, no unpainted)
    assert len(e.paths) == 2
    # 10 mm from the origin (the lower right corner) both ways
    assert xmax == pytest.approx(-10.0) and ymax == pytest.approx(-10.0)
    assert xmax - xmin == pytest.approx(43.0, abs=0.01)                   # 10..53 mm in the file
    assert win.element_list.count() == 1
    assert win.element_list.item(0).checkState() == Qt.Checked


def test_save_gives_the_same_bytes_as_the_core(win, svg_file, tmp_path):
    win.import_svg(svg_file)
    out = tmp_path / "out.hpgl"
    assert win.save_cutter_file(str(out)) == str(out)
    expected = win.build().text
    assert out.read_text() == expected
    assert expected.startswith("IN;SP1;PU") and expected.endswith("PU0,0;")


def test_drawn_rectangle_is_cut_where_it_was_drawn(win, tmp_path):
    # view mm: x -50..-30 = 30..50 mm across (to the left), y -40..-20 = 20..40 mm along (up)
    win.use_profile_values(knife_offset_mm=0.0, overcut_mm=0.0)     # no knife offset, no overcut
    win._on_drawn("rectangle", QRectF(QPointF(-50, -40), QPointF(-30, -20)))
    out = tmp_path / "r.hpgl"
    win.save_cutter_file(str(out))
    text = out.read_text()
    for corner in ("800,1200", "1600,1200", "1600,2000", "800,2000"):
        assert corner in text
    assert win.tool_actions["select"].isChecked()


def test_unticked_element_is_not_cut(win, svg_file, tmp_path):
    win.import_svg(svg_file)
    win._on_drawn("ellipse", QRectF(100, -60, 30, 30))
    assert len(win.design.material_polylines()) > 2
    win.element_list.item(0).setCheckState(Qt.Unchecked)
    assert win.design.elements[0].cut is False
    # only the ellipse is left (one closed path)
    assert len(win.design.material_polylines()) == 1


def test_options_bar_moves_and_resizes(win, svg_file):
    e = win.import_svg(svg_file)
    win.opt_x.setValue(100.0)            # bottom edge 100 mm up from the origin
    win.opt_y.setValue(50.0)             # right edge 50 mm to the left of it
    xmin, xmax, ymin, ymax = e.bounds
    assert -ymax == pytest.approx(100.0) and -xmax == pytest.approx(50.0)
    win.opt_w.setValue(86.0)
    assert e.size[0] == pytest.approx(86.0, abs=0.01)


def test_off_the_material_blocks_saving(win, svg_file, messages):
    win.import_svg(svg_file)
    win.opt_y.setValue(770.0)            # 780 mm cutting width, the design is 20 mm high
    assert not win.btn_save.isEnabled()
    assert "does not fit" in win.job_label.text()
    assert win.save_cutter_file("/nonexistent/should-not-be-written.hpgl") is None
    assert messages and "past the cutting width of 780 mm" in messages[-1]


def test_profile_change_moves_the_material_edge(win, svg_file):
    win.import_svg(svg_file)
    win.opt_y.setValue(300.0)            # fits on 780 mm, not on 285 mm
    assert win.btn_save.isEnabled()
    win.profile_box.setCurrentIndex(win.profile_names.index("vevor-ki-375a"))
    assert win.profile.width_mm == 285.0
    assert not win.btn_save.isEnabled()


def test_speed_on_the_panel_only_or_sent(win, svg_file):
    import dataclasses
    win.import_svg(svg_file)
    # the material's starting speed (vinyl: 300 mm/s on the XILI cutters)
    assert win.job_profile().speed_cm_s == 30.0
    # both built-in cutters take speed and force from their panel only (checked 16.11.2026)
    assert not win.profile.send_speed_force
    assert "VS" not in win.build().text                # not sent ...
    assert "min at 300 mm/s" in win.job_label.text()    # ... but used for the time estimate (in mm/s)
    # without a material's speed: the panel's speed, written in the cutter's settings
    win.material_box.setCurrentIndex(-1)
    win.use_profile_values(speed_cm_s=20.0)
    assert win.job_profile().speed_cm_s == 20.0 and "min at 200 mm/s" in win.job_label.text()
    # a cutter that takes them from the computer gets them
    win.profile = dataclasses.replace(win.profile, send_speed_force=True)
    assert "VS20;" in win.build().text


def test_delete_and_reorder(win, svg_file):
    a = win.import_svg(svg_file)
    win._on_line_drawn(QPointF(5, -5), QPointF(50, -5))
    b = win.design.elements[1]
    win.move_selected(-1)
    assert win.design.elements == [b, a]
    win.delete_selected()
    assert win.design.elements == [a]


def test_knife_path_preview_follows_the_job(win, svg_file):
    win.import_svg(svg_file)
    assert win.view._knife_items == []
    win.act_knife.setChecked(True)
    n_paths = len(win.last_job.knife_paths)
    # one item for the cuts, one for the travels, one numbered dot per path
    assert len(win.view._knife_items) == 2 + n_paths
    win.use_profile_values(knife_offset_mm=0.3)    # a change redraws it, no stale items
    assert len(win.view._knife_items) == 2 + len(win.last_job.knife_paths)
    win.opt_x.setValue(50)                        # so does a move (the scene is rebuilt)
    assert len(win.view._knife_items) == 2 + len(win.last_job.knife_paths)
    win.act_knife.setChecked(False)
    assert win.view._knife_items == []


def test_knife_values_reach_the_job(win, svg_file):
    win.import_svg(svg_file)
    win.use_profile_values(knife_offset_mm=0.0, overcut_mm=0.0)
    plain = win.build().text
    win.use_profile_values(knife_offset_mm=0.25, overcut_mm=0.5)
    assert win.build().text != plain
    assert win.build().cut_mm > win.last_job.cut_mm - 1e-9


# ---- drawing from Kerfly: undo, polygon, nodes, snapping, keys ----------------------

def test_undo_and_redo(win, svg_file):
    e = win.import_svg(svg_file)
    up = -e.bounds[3]                                   # how far up the bottom edge is
    win.opt_x.setValue(up + 30)
    assert -win.design.elements[0].bounds[3] == pytest.approx(up + 30)
    win.undo()
    assert -win.design.elements[0].bounds[3] == pytest.approx(up)
    win.redo()
    assert -win.design.elements[0].bounds[3] == pytest.approx(up + 30)
    win.undo()
    win.undo()                                        # before the file was opened
    assert win.design.elements == []
    assert not win.act_undo.isEnabled() and win.act_redo.isEnabled()


def test_polygon_with_the_sides_set(win):
    win.set_tool("polygon")
    assert win.opt_sides.isVisible() or not win.isVisible()   # shown with the polygon tool
    win.opt_sides.setValue(5)
    win._on_drawn("polygon", QRectF(20, -60, 40, 40))
    e = win.design.elements[-1]
    assert len(e.paths[0]["nodes"]) == 5 and e.paths[0]["closed"]
    assert e.name.startswith("Polygon")


def test_arrow_keys_nudge_the_selected_element(win, svg_file):
    from PySide6.QtTest import QTest
    e = win.import_svg(svg_file)
    x0, _x1, _y0, y1 = e.bounds
    win.view.setFocus()
    QTest.keyClick(win.view.viewport(), Qt.Key_Right)
    QTest.keyClick(win.view.viewport(), Qt.Key_Up, Qt.ShiftModifier)
    e = win.design.elements[0]
    assert e.bounds[0] == pytest.approx(x0 + 1.0)
    assert e.bounds[3] == pytest.approx(y1 - 10.0)          # up on screen: 10 mm further across


def test_double_click_edits_nodes_and_a_node_can_be_deleted(win):
    win._on_drawn("rectangle", QRectF(20, -60, 40, 40))
    e = win.design.elements[-1]
    win.view.signals.edit_nodes.emit(e)
    assert win.view.tool == "nodes" and win.tool_actions["nodes"].isChecked()
    ed = win.view.node_editor
    assert ed.item is not None and len(ed._marks) == 4
    ed.select({(0, 0)})
    assert ed.action("delete")
    e = win.design.elements[-1]
    assert len(e.paths[0]["nodes"]) == 3                # a triangle now
    assert len(win.view.node_editor._marks) == 3        # the editor follows the rebuilt scene
    win.undo()
    assert len(win.design.elements[-1].paths[0]["nodes"]) == 4


def test_escape_leaves_a_drawing_tool(win):
    from PySide6.QtTest import QTest
    win.set_tool("ellipse")
    QTest.keyClick(win.view.viewport(), Qt.Key_Escape)
    assert win.view.tool == "select" and win.tool_actions["select"].isChecked()


def test_snapping_to_the_origin_and_alt_turns_it_off(win, monkeypatch):
    v = win.view
    tol = v._snap_tolerance()
    p = v.snap_point(QPointF(tol / 3, -tol / 3))
    assert (p.x(), p.y()) == (0.0, 0.0)
    monkeypatch.setattr(type(v), "snap_suspended", staticmethod(lambda: True))
    p = v.snap_point(QPointF(tol / 3, -tol / 3))
    assert p.x() == pytest.approx(tol / 3)


def test_node_tool_hint_does_not_widen_the_window(win):
    win.set_tool("nodes")
    assert win.minimumSizeHint().width() <= 1440


# ---- Start and Stop --------------------------------------------------------------------

def _cut_to_fifo(win, svg_file, tmp_path):
    """Set the window up to cut to a FIFO standing in for the KI-375A."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from test_transport import FifoReader
    fifo = str(tmp_path / "lp0")
    os.mkfifo(fifo)
    win.profile_box.setCurrentIndex(win.profile_names.index("vevor-ki-375a"))
    win.import_svg(svg_file)
    win.use_profile_values(port=fifo)
    return FifoReader(fifo)


def test_start_cuts_exactly_the_job(win, svg_file, tmp_path, messages):
    reader = _cut_to_fifo(win, svg_file, tmp_path)
    expected = win.build().text
    w = win.start()
    assert w is not None and win.btn_stop.isEnabled() and not win.btn_start.isEnabled()
    assert w.wait(5000)
    QApplication.processEvents()
    assert reader.join() == expected.encode("ascii")
    assert win.btn_start.isEnabled() and not win.btn_stop.isEnabled()
    assert "Sent %d bytes" % len(expected) in win.statusBar().currentMessage()
    assert messages == []


def test_stop_lifts_and_says_how_to_stop_the_cutter(win, svg_file, tmp_path, messages):
    reader = _cut_to_fifo(win, svg_file, tmp_path)
    w = win.start()
    w.request_stop()            # as if Stop came at once (before or while sending)
    assert w.wait(5000)
    QApplication.processEvents()
    got = reader.join().decode("ascii")
    assert got.endswith(";") and got.rsplit(";", 2)[-2].startswith("PU")
    if messages:                # it may have finished before the stop was seen
        assert "Test" in messages[-1] and "Reset" in messages[-1]


def test_start_without_a_cutter_explains(win, svg_file, tmp_path, messages):
    win.profile_box.setCurrentIndex(win.profile_names.index("vevor-ki-375a"))
    win.import_svg(svg_file)
    win.use_profile_values(port=str(tmp_path / "lp9"))
    w = win.start()
    assert w.wait(5000)
    QApplication.processEvents()
    assert messages and "not there" in messages[-1]
    assert win.btn_start.isEnabled()



def test_what_is_on_screen_is_cut_the_same_way_round(win, tmp_path):
    """The view is the cutter seen from the front: a shape drawn up and to the
    left of the origin is cut further along (X) and further across (Y)."""
    win.use_profile_values(knife_offset_mm=0.0, overcut_mm=0.0)
    # a 10 mm line going UP the screen, 30 mm left of the origin, from 20 to 30 mm up
    win._on_line_drawn(QPointF(-30, -20), QPointF(-30, -30))
    text = win.build().text
    assert "PU800,1200;PD1200,1200;" in text          # X 20 -> 30 mm, Y 30 mm
    # the material: as long as fills the window, longer when needed
    assert win.view.length_mm == pytest.approx(win.view.window_length())
    win._on_drawn("rectangle", QRectF(-60, -1300, 20, 20))
    assert win.view.length_mm >= 1300.0


# ---- transforms, align, duplicate, polyline -----------------------------------------------

def test_rotate_keeps_the_lower_right_corner(win):
    win._on_drawn("rectangle", QRectF(-60, -40, 40, 20))          # 40 wide, 20 high
    e = win.design.elements[-1]
    win.transform_selected("rot", 90)
    e = win.design.elements[-1]
    w, h = e.size
    assert (round(w, 6), round(h, 6)) == (20.0, 40.0)
    assert e.bounds[1] == pytest.approx(-20.0) and e.bounds[3] == pytest.approx(-20.0)
    win.undo()
    assert tuple(round(v, 6) for v in win.design.elements[-1].size) == (40.0, 20.0)


def test_mirror_turns_a_shape_over(win, svg_file):
    e = win.import_svg(svg_file)
    before = [n[0] for n in e.paths[0]["nodes"]]
    win.transform_selected("mirror", True)
    after = [n[0] for n in win.design.elements[-1].paths[0]["nodes"]]
    xmin, xmax = e.bounds[0], e.bounds[1]
    assert after == pytest.approx([xmin + xmax - x for x in before])


def test_align_shapes_to_each_other(win, messages):
    win._on_drawn("rectangle", QRectF(-100, -60, 20, 20))
    win._on_drawn("ellipse", QRectF(-60, -100, 30, 30))
    a, b = win.design.elements
    win.view.select(a)
    win.align_selected("left")                                  # one shape: nothing to align with
    assert win.design.elements[0].bounds[0] == pytest.approx(-100)
    win.view.select_many([a, b])
    win.align_selected("left")
    a, b = win.design.elements
    assert a.bounds[0] == pytest.approx(-100) and b.bounds[0] == pytest.approx(-100)
    win.view.select_many([a, b])
    win.align_selected("bottom")
    a, b = win.design.elements
    assert a.bounds[3] == pytest.approx(b.bounds[3]) == pytest.approx(-40)
    win.view.select_many([a, b])
    win.align_selected("centre")
    a, b = win.design.elements
    assert (a.bounds[0] + a.bounds[1]) / 2 == pytest.approx((b.bounds[0] + b.bounds[1]) / 2)
    win.view.select_many([a, b])
    win.align_selected("middle")
    a, b = win.design.elements
    assert (a.bounds[2] + a.bounds[3]) / 2 == pytest.approx((b.bounds[2] + b.bounds[3]) / 2)


def test_duplicate_goes_beside_it(win, svg_file):
    e = win.import_svg(svg_file)
    win.duplicate()
    a, b = win.design.elements
    assert b is win.selected and b.paths is not a.paths
    assert b.bounds[1] == pytest.approx(a.bounds[0] - 5.0)       # 5 mm to the left of it
    assert b.size == pytest.approx(a.size)


def test_polyline_clicks_close_on_the_first_corner(win):
    from PySide6.QtTest import QTest
    v = win.view
    win.set_tool("polyline")
    v.snap_objects = False
    pts = [QPointF(-80, -20), QPointF(-30, -20), QPointF(-30, -60)]
    for p in pts + [pts[0]]:                                        # back to the start closes it
        QTest.mouseClick(v.viewport(), Qt.LeftButton, Qt.NoModifier, v.mapFromScene(p))
    e = win.design.elements[-1]
    assert e.paths[0]["closed"] and len(e.paths[0]["nodes"]) == 3
    assert win.view.tool == "select"


def test_polyline_enter_leaves_it_open_backspace_drops_a_corner(win):
    from PySide6.QtTest import QTest
    v = win.view
    win.set_tool("polyline")
    v.snap_objects = False
    for p in (QPointF(-80, -20), QPointF(-30, -20), QPointF(-30, -60), QPointF(-90, -90)):
        QTest.mouseClick(v.viewport(), Qt.LeftButton, Qt.NoModifier, v.mapFromScene(p))
    QTest.keyClick(v.viewport(), Qt.Key_Backspace)
    QTest.keyClick(v.viewport(), Qt.Key_Return)
    e = win.design.elements[-1]
    assert not e.paths[0]["closed"] and len(e.paths[0]["nodes"]) == 3


def test_pen_click_corner_drag_curve_and_close(win):
    """Pen (from Kerfly): a click is a corner, press and drag makes a smooth node; the first node closes it."""
    from PySide6.QtTest import QTest
    v = win.view
    win.set_tool("pen")
    v.snap_objects = False
    at = v.mapFromScene
    QTest.mouseClick(v.viewport(), Qt.LeftButton, Qt.NoModifier, at(QPointF(-80, -20)))
    # press, drag, release: a smooth node with mirrored handles
    QTest.mousePress(v.viewport(), Qt.LeftButton, Qt.NoModifier, at(QPointF(-30, -20)))
    from PySide6.QtGui import QMouseEvent
    pos = at(QPointF(-30, -50))
    v.mouseMoveEvent(QMouseEvent(QMouseEvent.MouseMove, QPointF(pos), QPointF(v.viewport().mapToGlobal(pos)),
                                 Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    QTest.mouseRelease(v.viewport(), Qt.LeftButton, Qt.NoModifier, at(QPointF(-30, -50)))
    QTest.mouseClick(v.viewport(), Qt.LeftButton, Qt.NoModifier, at(QPointF(-55, -70)))
    QTest.mouseClick(v.viewport(), Qt.LeftButton, Qt.NoModifier, at(QPointF(-80, -20)))      # the first node
    e = win.design.elements[-1]
    sub = e.paths[0]
    assert sub["closed"] and len(sub["nodes"]) == 3
    smooth = sub["nodes"][1]
    assert smooth[4] == pytest.approx(-30, abs=1.5) and smooth[5] == pytest.approx(-50, abs=1.5)
    assert smooth[3] == pytest.approx(10, abs=1.5)                     # the in handle mirrored
    assert sub["nodes"][0][4] is None                                  # a click: a corner
    assert win.view.tool == "select"


def test_pen_enter_leaves_it_open(win):
    from PySide6.QtTest import QTest
    v = win.view
    win.set_tool("pen")
    v.snap_objects = False
    for p in (QPointF(-80, -20), QPointF(-30, -20), QPointF(-30, -60)):
        QTest.mouseClick(v.viewport(), Qt.LeftButton, Qt.NoModifier, v.mapFromScene(p))
    QTest.keyClick(v.viewport(), Qt.Key_Backspace)
    QTest.keyClick(v.viewport(), Qt.Key_Return)
    sub = win.design.elements[-1].paths[0]
    assert not sub["closed"] and len(sub["nodes"]) == 2


def test_freehand_simplifies_and_closes_at_the_start(win):
    import math
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    v = win.view
    win.set_tool("freehand")
    centre, r = QPointF(-60, -60), 25.0
    pts = [centre + QPointF(r * math.cos(a / 40.0 * 2 * math.pi), r * math.sin(a / 40.0 * 2 * math.pi))
           for a in range(41)]
    QTest.mousePress(v.viewport(), Qt.LeftButton, Qt.NoModifier, v.mapFromScene(pts[0]))
    for p in pts[1:]:
        pos = v.mapFromScene(p)
        v.mouseMoveEvent(QMouseEvent(QMouseEvent.MouseMove, QPointF(pos), QPointF(v.viewport().mapToGlobal(pos)),
                                     Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    QTest.mouseRelease(v.viewport(), Qt.LeftButton, Qt.NoModifier, v.mapFromScene(pts[-1]))
    e = win.design.elements[-1]
    assert e.paths[0]["closed"]
    assert len(e.paths[0]["nodes"]) < 40                      # simplified
    assert any(n[4] is not None for n in e.paths[0]["nodes"])   # and smooth
    w, h = e.size
    assert w == pytest.approx(50, abs=3) and h == pytest.approx(50, abs=3)


def test_ruler_measures_a_drag(win):
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    v = win.view
    win.set_tool("measure")
    v.snap_objects = False
    got = []
    v.signals.measured.connect(lambda dx, dy: got.append((dx, dy)))
    a, b = v.mapFromScene(QPointF(-100, -20)), v.mapFromScene(QPointF(-70, -60))
    QTest.mousePress(v.viewport(), Qt.LeftButton, Qt.NoModifier, a)
    v.mouseMoveEvent(QMouseEvent(QMouseEvent.MouseMove, QPointF(b), QPointF(v.viewport().mapToGlobal(b)),
                                 Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    QTest.mouseRelease(v.viewport(), Qt.LeftButton, Qt.NoModifier, b)
    assert len(got) == 1 and math_hypot(*got[0]) == pytest.approx(50, abs=1)
    assert ("%.2f mm" % math_hypot(*got[0])) in win.statusBar().currentMessage()
    assert not win.design.elements                                   # measuring adds nothing
    # the result is in the selection bar too, while the ruler is the tool
    assert win.sel_name.text() == "Ruler" and not win.sel_hint.isHidden()
    assert "Length <b>%.1f mm</b>" % math_hypot(*got[0]) in win.sel_hint.text()
    win.set_tool("select")
    assert v._measure_item is None                                   # the line goes with the tool
    assert win.sel_hint.text() == "Select an element to change its place and size" and win.sel_name.isHidden()


def math_hypot(dx, dy):
    import math
    return math.hypot(dx, dy)


def test_selection_actions_need_a_selection(win):
    assert not win.act_rot_left.isEnabled() and not win.act_duplicate.isEnabled()
    win._on_drawn("ellipse", QRectF(-60, -40, 20, 20))
    assert win.act_rot_left.isEnabled() and win.act_align["left"].isEnabled()


def test_right_bar_category_opens_a_square_of_icons(win):
    """As in SignMaster: a category opens a square of icons; a choice takes the tool."""
    popup = win.show_category("shapes")
    buttons = popup.findChildren(QToolButton)
    assert [b.text() for b in buttons] == ["Rectangle", "Ellipse", "Polygon"]
    assert win.view.tool == "select"                       # looking is not choosing
    buttons[2].click()
    assert win.view.tool == "polygon" and win.category_buttons["shapes"].isChecked()
    assert not popup.isVisible()
    # a category with one tool takes it at once
    assert win.show_category("measure") is None and win.view.tool == "measure"
    win.set_tool("select")
    assert win.category_buttons["pick"].isChecked()


def test_ready_shapes_are_offered_and_inserted(win):
    from vintyl.core import ready
    popup = win.show_category("ready")
    assert len(popup.findChildren(QToolButton)) == len(ready.READY) + 1 == 9      # and the QR code
    popup.close()
    e = win.insert_ready("star", {"points": 6, "size": 40.0, "inner": 50.0})
    assert e is win.selected and e.spec["shape"] == "star" and e.spec["points"] == 6
    assert len(e.paths[0]["nodes"]) == 12 and e.paths[0]["closed"]
    assert max(e.size) == pytest.approx(40.0)
    assert e.bounds[1] == pytest.approx(-10.0) and e.bounds[3] == pytest.approx(-10.0)   # 10 mm from the origin
    g = win.insert_ready("gear", {"teeth": 12, "module": 2.0, "bore": 6.0})
    assert len(g.paths) == 2                              # the gear and its axle hole
    job = win.build()                                     # the hole is cut before the gear
    assert max(p[0] for p in job.knife_paths[0]) - min(p[0] for p in job.knife_paths[0]) < 7


# ---- text --------------------------------------------------------------------------------

def test_text_tool_places_an_editable_text(win):
    win.set_tool("text")
    assert win.opt_text.isVisibleTo(win) and win.opt_font.isVisibleTo(win)
    win.opt_text.setText("OKO")
    win._on_text_clicked(QPointF(-150, -80))
    e = win.design.elements[-1]
    assert e.spec["kind"] == "text" and e.spec["text"] == "OKO" and e.name == "OKO"
    assert all(s["closed"] for s in e.paths)
    assert len(e.paths) == 5                       # O and O with their counters, and K
    assert e.bounds[0] == pytest.approx(-150, abs=3) and e.bounds[2] == pytest.approx(-80, abs=10)
    assert win.view.tool == "select"


def test_editing_the_text_keeps_its_lower_left_corner(win):
    win.opt_text.setText("A")
    win._on_text_clicked(QPointF(-150, -80))
    e = win.design.elements[-1]
    x0, y1 = e.bounds[0], e.bounds[3]
    win.opt_text.setText("ABC")
    win._text_changed()
    e = win.design.elements[-1]
    assert e.spec["text"] == "ABC" and e.name == "ABC"
    assert e.bounds[0] == pytest.approx(x0) and e.bounds[3] == pytest.approx(y1)
    win.opt_size.setValue(60)
    assert win.design.elements[-1].size[1] > 35
    win.undo()
    assert win.design.elements[-1].spec["size"] == 30.0


def test_turned_text_is_a_shape_and_cuts_counters_first(win):
    win.opt_text.setText("O")
    win._on_text_clicked(QPointF(-150, -80))
    job = win.build()
    # the counter (the smaller ring) is cut before the outside of the O
    first, second = job.knife_paths[0], job.knife_paths[1]
    span = lambda poly: max(p[0] for p in poly) - min(p[0] for p in poly)
    assert span(first) < span(second)
    win.transform_selected("rot", 90)
    assert win.design.elements[-1].spec is None and not win.opt_text.isVisibleTo(win)


def test_weed_frame_round_the_design_is_cut_last(win, svg_file):
    e = win.import_svg(svg_file)
    win.opt_x.setValue(30)
    win.opt_y.setValue(30)
    plain = win.build()
    win.weed_frame.setChecked(True)
    win.weed_margin.setValue(5.0)
    job = win.build()
    assert job.paths == plain.paths + 1
    frame = job.knife_paths[-1]                        # cut last
    xs = [p[0] for p in frame]
    ys = [p[1] for p in frame]
    along = [p[0] for poly in plain.knife_paths for p in poly]
    across = [p[1] for poly in plain.knife_paths for p in poly]
    assert min(xs) == pytest.approx(min(along) - 5.0, abs=0.6)
    assert max(ys) == pytest.approx(max(across) + 5.0, abs=0.6)
    # no room for the frame at the origin: a clear message
    win.opt_x.setValue(2)
    assert "does not fit" in win.job_label.text()
    win.weed_frame.setChecked(False)
    assert "does not fit" not in win.job_label.text()



def test_select_and_nodes_are_buttons_of_their_own(win):
    assert win.show_category("nodes") is None and win.view.tool == "nodes"
    assert win.category_buttons["nodes"].isChecked()
    assert win.show_category("pick") is None and win.view.tool == "select"
    assert win.category_buttons["pick"].isChecked()



def test_a_drawn_polygon_keeps_its_number_of_sides_to_change(win):
    win.set_tool("polygon")
    win.opt_sides.setValue(5)
    win._on_drawn("polygon", QRectF(-80, -80, 40, 40))
    e = win.selected
    assert e.spec["sides"] == 5 and len(e.paths[0]["nodes"]) == 5
    assert win.opt_sides.isVisibleTo(win) and win.opt_sides.value() == 5      # shown when selected
    win.opt_sides.setValue(8)
    e = win.selected
    assert len(e.paths[0]["nodes"]) == 8 and e.spec["sides"] == 8
    # still in the rectangle it was drawn in
    assert e.bounds[0] >= -80 - 1e-6 and e.bounds[1] <= -40 + 1e-6
    win.undo()
    assert len(win.selected.paths[0]["nodes"]) == 5
    win.transform_selected("rot", 90)              # turned: a shape now, no sides field
    assert win.selected.spec is None and not win.opt_sides.isVisibleTo(win)


def test_the_last_cutter_is_remembered(app, tmp_path, monkeypatch):
    monkeypatch.setenv("VINTYL_SETTINGS", str(tmp_path / "remember.ini"))
    w = MainWindow()
    assert w.profile.name == "Seiki SK-870T"              # nothing remembered yet: the first
    w.profile_box.setCurrentIndex(w.profile_names.index("vevor-ki-375a"))
    w.settings.sync()
    w.close()
    w2 = MainWindow()                                     # the next start
    assert w2.profile.name == "VEVOR KI-375A"
    w2.close()


def test_the_sheet_fills_the_window_for_every_cutter_and_grows_upwards(win, app):
    """The sheet is the cutting width across and reaches the window's top and
    bottom when fitted; something drawn higher up makes it longer, upwards."""
    from PySide6.QtTest import QTest
    win.resize(1400, 900)
    win.show()
    QTest.qWait(200)                      # the sheet follows the window after a short pause
    v = win.view
    for name in win.profile_names:
        win.profile_box.setCurrentIndex(win.profile_names.index(name))
        app.processEvents()
        v.fit_requested()
        sheet = v.mapFromScene(v.material_rect(v.length_mm)).boundingRect()
        vp = v.viewport().rect()
        from vintyl.gui import canvas as cv
        # no grey band beyond the room left for the titles, the rulers and the zoom box
        assert abs(sheet.top() - vp.top()) <= cv.FIT_TOP_PX + 6
        assert abs(vp.bottom() - sheet.bottom()) <= cv.FIT_BOTTOM_PX + 6
        assert abs(sheet.left() - vp.left()) <= cv.FIT_LEFT_PX + 6
    before = v.length_mm
    win._on_drawn("rectangle", QRectF(-60, -1500, 20, 20))      # something higher up
    assert v.length_mm >= 1500.0 > before
    # a taller window: a longer sheet, without touching the design
    win.design.elements.clear()
    win.refresh()
    flat = v.length_mm
    win.resize(900, 1100)
    QTest.qWait(200)
    assert v.length_mm == pytest.approx(v.window_length()) and v.length_mm > flat


# ---- several elements: group, ungroup, union / difference ... ------------------------

def _two_rects(win):
    win._on_drawn("rectangle", QRectF(-100, -100, 40, 40))
    win._on_drawn("rectangle", QRectF(-80, -80, 40, 40))     # overlaps the first
    a, b = win.design.elements[-2:]
    win.view.select_many([a, b])
    return a, b


def test_group_is_selected_and_moved_as_one(win):
    a, b = _two_rects(win)
    assert len(win.selection) == 2
    win.group_selected()
    a, b = win.design.elements[-2:]
    assert a.group and a.group == b.group
    win.view.select(a)                                      # a click on one member ...
    assert len(win.selection) == 2                           # ... selects the whole group
    xa, xb = a.bounds[0], b.bounds[0]
    win._on_moved(win.selection, -10.0, 0.0)
    a, b = win.design.elements[-2:]
    assert a.bounds[0] == pytest.approx(xa - 10) and b.bounds[0] == pytest.approx(xb - 10)
    win.ungroup_selected()
    assert not any(e.group for e in win.design.elements)


def test_ungroup_splits_an_element_into_its_outlines(win):
    ring = win.insert_ready("ring", {"outer": 40.0, "hole": 20.0})
    n = len(win.design.elements)
    win.ungroup_selected()
    assert len(win.design.elements) == n + 1
    assert all(len(e.paths) == 1 for e in win.design.elements[-2:])


def test_union_and_difference_stay_smooth(win):
    _two_rects(win)
    win.boolean_selected("union")
    u = win.design.elements[-1]
    assert len(win.design.elements) == 1 and len(u.paths) == 1 and u.paths[0]["closed"]
    assert u.bounds[0] == pytest.approx(-100, abs=0.01) and u.bounds[1] == pytest.approx(-40, abs=0.01)
    # a round hole well inside the shape: it stays round
    win._on_drawn("ellipse", QRectF(-95, -95, 20, 20))           # centre (-85, -85), radius 10
    disc = win.design.elements[-1]
    win.view.select_many([u, disc])
    win.boolean_selected("difference")
    d = win.design.elements[-1]
    assert len(d.paths) == 2                                      # the outline and the round hole
    import math
    hole = min(d.paths, key=lambda sp: max(n[0] for n in sp["nodes"]))
    ns = hole["nodes"]
    assert len(ns) > 30
    worst = max(abs(10 - math.hypot((ns[i][0] + ns[i - 1][0]) / 2 + 85, (ns[i][1] + ns[i - 1][1]) / 2 + 85))
                for i in range(len(ns)))
    assert worst < 0.01                                            # round to a hundredth of a mm
    win.undo()
    assert len(win.design.elements) == 2


def test_delete_removes_every_selected_element(win):
    _two_rects(win)
    win.delete_selected()
    assert win.design.elements == []


# ---- size handles and the proportion lock ---------------------------------------------

def test_size_handles_round_the_selection(win):
    win._on_drawn("rectangle", QRectF(-100, -80, 40, 20))
    assert len(win.view._handles) == 8
    win.set_tool("nodes")
    assert win.view._handles == []                         # not in the node tool
    win.set_tool("select")
    assert len(win.view._handles) == 8


def _drag_handle(win, place, to):
    from PySide6.QtCore import QPointF
    h = [h for h in win.view._handles if h.place == place][0]
    h._box = QRectF(win.view.selection_box())
    h._items = win.view._selected_items()
    new = h.new_box(to, win.view.keep_ratio)
    for item in h._items:
        item.setTransform(__import__("PySide6.QtGui", fromlist=["QTransform"]).QTransform())
    win.view.signals.resized.emit([i.element for i in h._items], h._box, new)


def test_corner_handle_with_the_lock_keeps_proportions(win):
    win.opt_lock.setChecked(True)
    win._on_drawn("rectangle", QRectF(-100, -80, 40, 20))   # 40 x 20, lower right at (-60, -60)
    _drag_handle(win, (0, 0), QPointF(-140, -90))             # top left corner pulled out
    e = win.design.elements[-1]
    w, h = e.size
    assert w / h == pytest.approx(2.0) and w == pytest.approx(80.0)
    assert e.bounds[1] == pytest.approx(-60) and e.bounds[3] == pytest.approx(-60)   # the anchor stayed


def test_side_handle_without_the_lock_changes_one_side(win):
    win.opt_lock.setChecked(False)
    win._on_drawn("rectangle", QRectF(-100, -80, 40, 20))
    _drag_handle(win, (1, 0.5), QPointF(-30, -70))            # the right side pulled right
    w, h = win.design.elements[-1].size
    assert (round(w, 6), round(h, 6)) == (70.0, 20.0)
    win.undo()
    assert tuple(round(v, 6) for v in win.design.elements[-1].size) == (40.0, 20.0)


def test_lock_in_the_fields(win):
    win.opt_lock.setChecked(True)
    win._on_drawn("rectangle", QRectF(-100, -80, 40, 20))
    win.opt_w.setValue(60.0)
    assert tuple(round(v, 4) for v in win.design.elements[-1].size) == (60.0, 30.0)
    win.opt_lock.setChecked(False)
    win.opt_h.setValue(50.0)
    assert tuple(round(v, 4) for v in win.design.elements[-1].size) == (60.0, 50.0)


# ---- keyboard shortcuts ----------------------------------------------------------------

def test_no_two_actions_share_a_key(win):
    from PySide6.QtGui import QAction
    seen = {}
    for a in win.findChildren(QAction):
        for k in a.shortcuts():
            if k.isEmpty():
                continue
            key = k.toString()
            assert key not in seen or seen[key] is a, "%s: %s and %s" % (key, seen[key].text(), a.text())
            seen[key] = a
    for key in ("Ctrl+Z", "Ctrl+Shift+Z", "Ctrl+Y", "Ctrl+A", "Ctrl+C", "Ctrl+X", "Ctrl+V", "Ctrl+S", "V", "T"):
        assert key in seen, key


def test_select_all_copy_paste_cut(win):
    win._on_drawn("rectangle", QRectF(-100, -80, 20, 20))
    win._on_drawn("ellipse", QRectF(-60, -80, 20, 20))
    win.select_all()
    assert len(win.selection) == 2
    win.copy_selected()
    win.paste()
    assert len(win.design.elements) == 4
    assert win.design.elements[2].bounds[0] == pytest.approx(win.design.elements[0].bounds[0] - 5.0)
    win.paste()                                            # again: 5 mm further
    assert win.design.elements[4].bounds[0] == pytest.approx(win.design.elements[0].bounds[0] - 10.0)
    win.view.select(win.design.elements[0])
    win.cut_selected()
    assert len(win.design.elements) == 5
    win.undo()
    assert len(win.design.elements) == 6


def test_tool_letters_and_the_list_of_shortcuts(win):
    # (offscreen the window is never "active", so Qt does not deliver shortcuts:
    # check the key on the action and what the action does)
    from PySide6.QtGui import QKeySequence
    r = win.tool_actions["rectangle"]
    assert r.shortcut() == QKeySequence("R") and r in win.actions()
    r.trigger()
    assert win.view.tool == "rectangle"
    win.tool_actions["select"].trigger()
    assert win.view.tool == "select"
    rows = win.shortcut_list()
    assert ("Ctrl+A", "Select all", "Select every element") in rows
    keys = {r[0]: r for r in rows}
    assert keys["T"][1] == "Text" and keys["T"][2].startswith("Click where it should start")


def test_weed_frame_is_shown_dashed_while_ticked(win, svg_file):
    win.import_svg(svg_file)
    assert win.view._frame_item is None
    win.weed_frame.setChecked(True)
    item = win.view._frame_item
    assert item is not None and item.pen().style() == Qt.DashLine
    r = item.path().boundingRect()
    xmin, xmax, ymin, ymax = win.design.elements[0].bounds
    assert r.left() < xmin and r.right() > xmax and r.top() < ymin and r.bottom() > ymax
    win.weed_margin.setValue(10.0)                    # follows the margin
    assert win.view._frame_item.path().boundingRect().width() > r.width()
    win.weed_frame.setChecked(False)
    assert win.view._frame_item is None


# ---- offset ------------------------------------------------------------------------------

def test_offset_outwards_keeps_the_original(win):
    win._on_drawn("rectangle", QRectF(-100, -80, 40, 20))
    made = win.offset_selected({"distance": 3.0, "outward": True, "round": False, "keep": True})
    assert len(win.design.elements) == 2 and made[0] is win.selected
    o = win.design.elements[1]
    assert o.size == pytest.approx((46.0, 26.0), abs=0.01)          # sharp corners: 3 mm all round
    assert o.name.startswith("Offset")


def test_offset_inwards_of_a_ring_and_replace(win):
    win.insert_ready("ring", {"outer": 40.0, "hole": 20.0})
    win.offset_selected({"distance": 2.0, "outward": False, "round": True, "keep": False})
    assert len(win.design.elements) == 1
    o = win.design.elements[0]
    w, _h = o.size
    assert w == pytest.approx(36.0, abs=0.05)                         # the outside 2 mm in ...
    assert len(o.paths) == 2                                          # ... and the hole 2 mm bigger
    win.undo()
    assert win.design.elements[0].size[0] == pytest.approx(40.0, abs=0.01)


def test_offset_needs_a_closed_shape(win):
    win._on_line_drawn(QPointF(-80, -20), QPointF(-30, -20))
    assert win.offset_selected({"distance": 2.0}) == []


# ---- project files ------------------------------------------------------------------------

def test_save_and_open_a_project_with_its_settings(win, tmp_path, app):
    win.profile_box.setCurrentIndex(win.profile_names.index("vevor-ki-375a"))
    win.opt_text.setText("AB")
    win._on_text_clicked(QPointF(-150, -80))
    win.weed_frame.setChecked(True)
    assert win.modified and win.windowTitle().startswith("new project *")
    path = win.save_project(str(tmp_path / "test.vintyl"))
    assert path and not win.modified and win.windowTitle().startswith("test.vintyl –")
    w2 = MainWindow()
    assert w2.open_file(path) is not None
    assert w2.profile.name == "VEVOR KI-375A"
    assert w2.weed_frame.isChecked()
    e = w2.design.elements[0]
    assert e.spec["text"] == "AB" and w2.build().text == win.build().text
    w2.close()


def test_a_damaged_project_is_refused_with_a_message(win, tmp_path, messages):
    bad = tmp_path / "bad.vintyl"
    bad.write_text("{")
    assert win.open_file(str(bad)) is None
    assert messages and "damaged" in messages[-1]


# ---- grid and settings ---------------------------------------------------------------------

def test_grid_step_in_the_settings_and_snapping_to_it(win):
    win.show_settings({"grid_step": 5.0, "snap_objects": False})
    win.act_grid.setChecked(True)
    assert win.view.grid_mm == 5.0
    p = win.view.snap_point(QPointF(-12.4, -21.6))
    assert (p.x(), p.y()) == (-10.0, -20.0)
    win.act_grid.setChecked(False)
    assert win.view.grid_mm == 0.0
    p = win.view.snap_point(QPointF(-12.4, -21.6))
    assert (round(p.x(), 3), round(p.y(), 3)) == (-12.4, -21.6)


def test_grid_and_settings_are_remembered(app, tmp_path, monkeypatch):
    monkeypatch.setenv("VINTYL_SETTINGS", str(tmp_path / "grid.ini"))
    w = MainWindow()
    w.show_settings({"grid_step": 2.5, "snap_objects": False})
    w.act_grid.setChecked(True)
    w.settings.sync()
    w.close()
    w2 = MainWindow()
    assert w2.grid_step == 2.5 and w2.act_grid.isChecked() and w2.view.grid_mm == 2.5
    assert not w2.view.snap_objects
    w2.close()


def test_offset_without_the_holes_inside(win):
    win.opt_text.setText("O")
    win._on_text_clicked(QPointF(-150, -80))
    with_holes = win.offset_selected({"distance": 1.0, "outward": True, "round": True, "keep": True})[0]
    assert len(with_holes.paths) == 2                          # the O's outline and its counter
    win.view.select(win.design.elements[0])
    solid = win.offset_selected({"distance": 1.0, "outward": True, "round": True, "keep": True,
                                 "no_holes": True})[0]
    assert len(solid.paths) == 1                               # only the outside: a solid backing


def test_spread_three_shapes_evenly(win):
    for x in (-150, -120, -50):
        win._on_drawn("rectangle", QRectF(x, -60, 10, 10))
    win.view.select_many(win.design.elements)
    win.distribute_selected(True)
    xs = sorted(e.bounds[0] for e in win.design.elements)
    assert xs == pytest.approx([-150, -100, -50])                  # equal gaps, the outer two stayed


def test_qr_code_is_inserted_as_cut_outlines(win):
    e = win.insert_qr("https://github.com/cyryllo/vintyl", 25.0, "m")
    assert e is win.selected and e.spec["shape"] == "qr"
    assert max(e.size) == pytest.approx(25.0)
    assert len(e.paths) > 10 and all(sp["closed"] for sp in e.paths)


# ---- knife or pen ------------------------------------------------------------------------------------
def test_the_pen_switch_shows_its_own_settings_and_hides_the_knifes(win):
    assert win.pen_fields.isHidden() and not win.inside_first.isHidden()
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    assert win.is_pen()
    assert win.inside_first.isHidden()
    assert not win.pen_fields.isHidden() and not win.pen_note.isHidden()
    assert win.frame_row.isHidden()
    assert win.job_profile().knife_offset_mm == 0 and win.job_profile().overcut_mm == 0
    win.tool_box.setCurrentIndex(win.tool_box.findData("knife"))
    assert not win.frame_row.isHidden()
    assert win.job_profile().knife_offset_mm == pytest.approx(win.profile.knife_offset_mm)   # kept meanwhile


def test_a_pen_job_has_no_offset_no_overcut_no_frame(win):
    win._on_drawn("rectangle", QRectF(-60, -40, 20, 20))
    win.weed_frame.setChecked(True)
    knife_job = win.build()
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win.pen_place.setCurrentIndex(win.pen_place.findData("on"))
    job = win.build()
    # just the square: 4 sides, no overcut, no swivel arcs, no frame
    assert job.cut_mm == pytest.approx(80.0, abs=0.01)
    assert knife_job.cut_mm > 160.0                                   # the knife: the frame too
    win.pen_width.setValue(1.0)
    win.pen_place.setCurrentIndex(win.pen_place.findData("outside"))
    import math                                                     # half the pen width out,
    assert win.build().cut_mm == pytest.approx(80.0 + math.pi * 1.0, abs=0.1)   # round corners
    assert "Drawn length" in win.stat_cut_title.text() or "rysowania" in win.stat_cut_title.text()


def test_the_tool_is_remembered_for_each_cutter(win):
    names = win.profile_names
    win.profile_box.setCurrentIndex(0)
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win.pen_width.setValue(0.8)
    win.profile_box.setCurrentIndex(1)
    assert not win.is_pen()                                            # the other cutter keeps its knife
    win.profile_box.setCurrentIndex(0)
    assert win.is_pen() and win.pen_width.value() == pytest.approx(0.8)
    assert len(names) >= 2


def test_a_fill_is_offered_and_drawn_only_with_the_pen(win):
    win._on_drawn("rectangle", QRectF(-60, -40, 20, 10))
    lines = {"pattern": "lines", "spacing": 1.0, "angle": 0.0, "margin": 0.0}
    # the knife: no fill tool (it would cut the vinyl into strips)
    assert not win.act_fill.isVisible()
    assert win.fill_selected(lines) == [] and win.design.elements[0].fill is None
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    assert win.act_fill.isVisible()
    assert not win.pen_note.isHidden()
    filled = win.fill_selected(lines)
    assert filled and filled[0].fill["pattern"] == "lines"
    win.tool_box.setCurrentIndex(win.tool_box.findData("knife"))
    knife_len = win.build().cut_mm                                    # the knife skips a fill
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win.pen_place.setCurrentIndex(win.pen_place.findData("on"))
    job = win.build()
    assert job.cut_mm == pytest.approx(60.0 + 10 * 20.0, abs=0.5)     # the outline and 10 lines
    assert knife_len < job.cut_mm
    win.undo()
    assert win.design.elements[0].fill is None
    win.fill_selected({"pattern": None})
    assert win.design.elements[0].fill is None


def test_a_pattern_of_shapes_is_cut_with_the_knife_before_its_outline(win):
    """Stars inside a rectangle: whole ones only, a margin from the outline,
    grouped with it, cut before it."""
    win._on_drawn("rectangle", QRectF(-120, -80, 100, 60))
    box = win.selected
    # with the knife the Fill category offers only the pattern of shapes (no popup, it asks at once)
    asked = []
    win._ask_tile = lambda *a: asked.append(True) or None
    assert win.show_category("fill") is None and asked
    new = win.tile_selected({"motif": "star", "size": 8.0, "gap": 3.0, "margin": 2.0, "stagger": True})
    assert new is not None and new.group and new.group == box.group
    assert win.design.elements.index(new) < win.design.elements.index(box)
    assert len(new.paths) > 20
    xmin, xmax, ymin, ymax = new.bounds
    assert xmin >= -120 + 2 - 1e-6 and xmax <= -20 - 2 + 1e-6
    assert ymin >= -80 + 2 - 1e-6 and ymax <= -20 - 2 + 1e-6
    job = win.build()
    assert job.cut_mm > 200
    # in the pen mode the square offers both
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    popup = win.show_category("fill")
    # (a long name is on two lines)
    assert [b.text().replace("\n", " ") for b in popup.findChildren(QToolButton)] == ["Pattern of shapes", "Fill"]
    popup.close()


def test_a_pattern_needs_room(win, messages):
    win._on_drawn("rectangle", QRectF(-60, -40, 10, 10))
    assert win.tile_selected({"motif": "circle", "size": 20.0, "gap": 2.0, "margin": 1.0,
                              "stagger": False}) is None
    assert len(win.design.elements) == 1


def _in_dialog(app, steps):
    """Run steps(dialog) once the dialog opened by the next exec() is shown."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog

    def go():
        dlg = [w for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]
        if not dlg:
            QTimer.singleShot(20, go)
            return
        try:
            steps(dlg[0])
        except BaseException as e:                     # reported after the dialog is closed
            failed.append(e)
        finally:
            if dlg[0].isVisible():
                dlg[0].reject()
    failed = []
    _in_dialog.failed = failed
    QTimer.singleShot(20, go)


def _wait_for(cond, ms=5000):
    from PySide6.QtTest import QTest
    for _i in range(ms // 20):
        if cond():
            return True
        QTest.qWait(20)
    return False


def test_the_pattern_of_shapes_is_previewed_and_cancel_leaves_nothing(win, app):
    from PySide6.QtWidgets import QDoubleSpinBox
    win._on_drawn("rectangle", QRectF(-120, -80, 100, 60))
    seen = {}

    def steps(dlg):
        assert _wait_for(lambda: win.view._preview_item is not None)
        first = win.view._preview_item.path().elementCount()
        dlg.findChildren(QDoubleSpinBox)[0].setValue(12.0)                    # bigger shapes: fewer
        assert _wait_for(lambda: win.view._preview_item is not None
                         and win.view._preview_item.path().elementCount() < first)
        seen["ok"] = True
        dlg.reject()
    _in_dialog(app, steps)
    result = win.tile_selected()
    if _in_dialog.failed:
        raise _in_dialog.failed[0]
    assert result is None
    assert seen.get("ok") and len(win.design.elements) == 1 and win.view._preview_item is None


def test_the_fill_is_previewed_and_cancel_puts_it_back(win, app):
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win._on_drawn("rectangle", QRectF(-120, -80, 100, 60))
    box = win.selected
    seen = {}

    def steps(dlg):
        dlg.pattern.setCurrentIndex(dlg.pattern.findData("honeycomb"))     # the 3 x 3 grid of pictures
        assert _wait_for(lambda: box.fill is not None and box.fill["pattern"] == "honeycomb")
        seen["ok"] = True
        dlg.reject()
    undo_before = len(win._undo)
    _in_dialog(app, steps)
    result = win.fill_selected()
    if _in_dialog.failed:
        raise _in_dialog.failed[0]
    assert result == []
    assert seen.get("ok") and box.fill is None                    # cancelled: no fill, as before
    assert len(win._undo) == undo_before                         # and nothing to undo


def test_a_moved_fill_is_not_worked_out_again():
    from vintyl.core import design, shapes
    e = design.Element("x", shapes.ellipse(0, 0, 100, 100),
                       fill={"pattern": "honeycomb", "spacing": 2.0, "angle": 10.0, "margin": 0.0})
    a = e.fill_lines()
    n = len(design._FILL_CACHE)
    e.move_by(12.5, -7.25)
    b = e.fill_lines()
    assert len(design._FILL_CACHE) == n                           # found, not worked out
    assert b[0][0][0] == pytest.approx(a[0][0][0] + 12.5) and b[0][0][1] == pytest.approx(a[0][0][1] - 7.25)


def test_the_left_panel_never_squeezes_its_boxes_into_each_other(win):
    """A low window: the project list gives way, the Cutter and Job boxes keep
    their rows; lower still, the panel scrolls (it once overlapped)."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QWidget
    win.show()
    win._on_drawn("rectangle", QRectF(-60, -40, 20, 20))
    boxes = [w for w in win.left_scroll.widget().findChildren(QWidget)
             if w.objectName() == "panel_section" and not w.isHidden()]      # Colours: only with several
    assert len(boxes) == 3
    for tool in ("knife", "pen"):
        win.tool_box.setCurrentIndex(win.tool_box.findData(tool))
        for h in (1000, 900, 700):
            win.resize(1400, h)
            QTest.qWait(60)
            r = [b.geometry() for b in boxes]
            assert all(r[i].bottom() < r[i + 1].top() for i in range(len(r) - 1)), (tool, h, r)
            assert all(b.height() >= b.minimumSizeHint().height() for b in boxes), (tool, h)


def test_the_settings_menu_opens_its_window(win, app):
    """The menu's action passes "checked" (False) to its slot: the window must
    still open (it once failed, taking False for the values)."""
    from PySide6.QtWidgets import QDoubleSpinBox
    seen = {}

    def steps(dlg):
        spin = dlg.findChildren(QDoubleSpinBox)[0]
        spin.setValue(7.5)
        seen["ok"] = True
        dlg.accept()
    _in_dialog(app, steps)
    win.act_settings.trigger()
    if _in_dialog.failed:
        raise _in_dialog.failed[0]
    assert seen.get("ok") and win.grid_step == pytest.approx(7.5)


def test_ready_shape_sizes_keep_their_proportions_by_default(win, app):
    """The heart's width and height change together (the lock is on by
    default); unlocked, they change alone."""
    seen = {}

    def steps(dlg):
        f = win._ready_fields
        assert win.ready_lock.isChecked()                          # on by default
        f["width"].setValue(120.0)                                 # twice as wide
        seen["h"] = f["height"].value()
        win.ready_lock.setChecked(False)
        f["width"].setValue(60.0)
        seen["h_free"] = f["height"].value()
        win.ready_lock.setChecked(True)                            # back on for the next tests
        dlg.accept()
    _in_dialog(app, steps)
    e = win.insert_ready("heart")
    if _in_dialog.failed:
        raise _in_dialog.failed[0]
    assert seen["h"] == pytest.approx(104.0) and seen["h_free"] == pytest.approx(104.0)
    assert e.spec["width"] == pytest.approx(60.0) and e.spec["height"] == pytest.approx(104.0)


# ---- cutter profiles ------------------------------------------------------------------------------
def test_the_cutter_settings_window_saves_a_copy_and_restores(win, app):
    """Change the KI-375A's port in its settings: the machine list marks it
    changed (*) and the job uses the new port; Restore brings the original."""
    from vintyl.gui.profile_editor import ProfileEditor
    win.profile_box.setCurrentIndex(win.profile_names.index("vevor-ki-375a"))
    entry = win.profile_entries["vevor-ki-375a"]
    dlg = ProfileEditor(entry, win)
    assert not dlg.btn_reset.isEnabled()                           # nothing to restore yet
    dlg.port.setCurrentText("/dev/usb/lp5")
    dlg.knife.setValue(0.3)
    dlg.save()
    assert dlg.chosen == "vevor-ki-375a"
    win.reload_profiles(dlg.chosen)
    assert win.profile.port == "/dev/usb/lp5" and win.job_profile().knife_offset_mm == pytest.approx(0.3)
    assert win.profile_box.currentText().endswith("*") and "/dev/usb/lp5" in win.cutter_info.text()
    dlg = ProfileEditor(win.profile_entries["vevor-ki-375a"], win)
    assert dlg.btn_reset.isEnabled()
    dlg.restore()                                                  # (the question is answered Yes)
    win.reload_profiles(dlg.chosen)
    assert win.profile.port == "/dev/usb/lp1" and not win.profile_box.currentText().endswith("*")


def test_a_new_cutter_appears_in_the_list_and_can_be_deleted(win):
    from vintyl.gui.profile_editor import ProfileEditor
    dlg = ProfileEditor(win.profile_entries["vevor-870"], win)
    dlg.width.setValue(630.0)
    dlg.save_new("VEVOR KI-720A (mine)")
    win.reload_profiles(dlg.chosen)
    assert win.profile.name == "VEVOR KI-720A (mine)" and win.profile.width_mm == 630.0
    assert "vevor-870" in win.profile_names                        # the built-in one is still there
    dlg = ProfileEditor(win.profile_entries[dlg.chosen], win)
    dlg.delete()
    win.reload_profiles(dlg.chosen or None)
    assert "VEVOR KI-720A (mine)" not in [win.profile_entries[i]["profile"].name for i in win.profile_names]


def test_the_machine_line_says_when_the_port_is_missing(win, tmp_path):
    win.use_profile_values(port=str(tmp_path / "lp9"))
    win.refresh_job()
    assert not win.port_warning.isHidden() and "not there" in win.port_problem.text()


# ---- text on a path, rounded rectangles, any angle, the right-click menu -------------------------------
def test_a_text_runs_round_a_circle_and_keeps_its_path_when_moved(win):
    import math
    from vintyl.core import curves
    win.opt_text.setText("VINTYL")
    win.opt_size.setValue(8.0)
    win._on_text_clicked(QPointF(-150, -100))
    t = win.design.elements[-1]
    win._on_drawn("ellipse", QRectF(-120, -120, 100, 100))         # a circle, centre (-70, -70), r 50
    circle = win.design.elements[-1]
    win.view.select_many([t, circle])
    win.selection = [t, circle]
    assert win.put_text_on_path() is t
    assert t.spec["path"] and not circle.cut                        # the circle stays, as a guide
    # every letter on the circle's top half, standing outside it (r about 50..60 mm)
    for sub in t.paths:
        for n in sub["nodes"]:
            r = math.hypot(n[0] + 70, n[1] + 70)
            assert 48 < r < 62 and n[1] < -70 + 5
    xmin, xmax, _y0, _y1 = t.bounds
    assert abs((xmin + xmax) / 2.0 + 70) < 4                        # centred at the top
    # moved: the path goes with it; a change of the text keeps it there
    t.move_by(30.0, 0.0)
    win.opt_text.setText("VINTYL CUT")
    win._text_changed()
    xmin, xmax, _y0, _y1 = t.bounds
    assert abs((xmin + xmax) / 2.0 + 40) < 6
    # the other side: inside the circle
    win.opt_path_flip.setChecked(True)
    inside = [math.hypot(n[0] + 40, n[1] + 70) for sub in t.paths for n in sub["nodes"]]
    assert max(inside) < 51


def test_a_rectangle_with_round_corners_stays_round_when_resized(win):
    from vintyl.core import curves
    win.set_tool("rectangle")
    win.opt_radius.setValue(5.0)
    win._on_drawn("rectangle", QRectF(-100, -60, 40, 20))
    e = win.selected
    assert e.spec == {"kind": "rectangle", "radius": 5.0} and len(e.paths[0]["nodes"]) == 8
    win.opt_radius.setValue(8.0)                                   # the selected one follows
    assert e.spec["radius"] == 8.0
    win.opt_w.setValue(80.0)                                       # resized: corners stay round
    assert e.spec["radius"] == 8.0
    n = e.paths[0]["nodes"][0]
    assert n[2] is not None and abs(n[2] - n[0]) == pytest.approx(curves.KAPPA * 8.0)
    win.opt_radius.setValue(0.0)
    assert len(e.paths[0]["nodes"]) == 4


def test_any_angle_turns_the_selection_together(win):
    import math
    win._on_drawn("rectangle", QRectF(-100, -60, 40, 20))
    e = win.selected
    w0, h0 = e.size
    win.opt_angle.setValue(30.0)
    win.btn_rotate.click()
    w, h = e.size
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    assert w == pytest.approx(w0 * c + h0 * s, abs=0.01) and h == pytest.approx(w0 * s + h0 * c, abs=0.01)
    win.undo()
    assert e.size != (w, h) or win.design.elements[0].size == pytest.approx((w0, h0))


def test_the_right_click_menu_for_an_element_and_for_the_sheet(win):
    win._on_drawn("rectangle", QRectF(-100, -60, 40, 20))
    win._on_drawn("ellipse", QRectF(-50, -60, 20, 20))
    a, b = win.design.elements
    menu = win.show_context_menu(b, None, show=False)
    texts = [x.text().replace("&", "") for x in menu.actions()]
    assert "Copy" in texts and "Delete" in texts and "Group" in texts and "Cut this element" in texts
    order = [x for x in menu.actions() if x.menu() is not None][0].menu()
    win.selected = b
    [x for x in order.actions() if x.text() == "Cut first"][0].trigger()
    assert win.design.elements[0] is b                              # now cut first
    cut = [x for x in menu.actions() if x.text() == "Cut this element"][0]
    cut.setChecked(False)
    assert not b.cut
    empty = win.show_context_menu(None, None, show=False)
    assert [x.text().replace("&", "") for x in empty.actions()] == ["Paste", "Select all", "Move to the origin"]


def test_open_a_dxf_from_the_window(win, tmp_path):
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from test_dxf import CIRCLE, SQUARE, _dxf
    path = tmp_path / "parts.dxf"
    path.write_text(_dxf(CIRCLE + SQUARE))
    e = win.open_file(str(path))
    assert e is not None and len(e.paths) == 2 and win.selected is e
    xmin, xmax, ymin, ymax = e.bounds
    assert xmax <= 0 and ymax <= 0                                  # on the material, near the origin


# ---- settings, new versions, diagnostics -------------------------------------------------------------
def test_language_and_look_are_saved_for_the_next_start(win):
    win.show_settings({"grid_step": 5.0, "snap_objects": True, "language": "pl", "theme": "dark",
                       "check_updates": False})
    assert win.settings.value("view/language") == "pl" and win.settings.value("view/theme") == "dark"
    assert win.settings.value("updates/check") == "false"
    assert "next start" in win.statusBar().currentMessage()


def test_a_new_version_shows_the_bar(win):
    import time
    from PySide6.QtTest import QTest
    fetch = lambda current, timeout: [{"tag_name": "v99.0.0", "prerelease": False, "draft": False,
                                       "html_url": "https://example.org", "name": "Vintyl 99.0.0"}]
    check = win.check_for_updates(auto=False, fetch=fetch)
    for _i in range(100):
        if not win.update_bar.isHidden():
            break
        QTest.qWait(20)
    assert check.wait(2000) and not win.update_bar.isHidden() and "99.0.0" in win.update_bar.text.text()
    win.update_bar.skip_button.click()
    assert win.settings.value("updates/skip") == "99.0.0" and win.update_bar.isHidden()
    # at start: not again on the same day
    assert win.check_for_updates(auto=True, fetch=fetch) is None
    assert float(win.settings.value("updates/last")) > time.time() - 60


def test_the_diagnostic_report_window(win):
    dlg = win.show_diagnostics(show=False)
    from PySide6.QtWidgets import QPlainTextEdit
    text = dlg.findChildren(QPlainTextEdit)[0].toPlainText()
    assert "Vintyl diagnostic report" in text and win.profile.name in text and "== Checks" in text
    assert "FAIL" not in text


def test_the_dark_look_paints_the_window_dark(app):
    from vintyl.gui import icons, theme
    try:
        assert theme.apply(app, "dark") == "dark"
        assert app.palette().window().color().lightness() < 100 and icons.INK == theme.TOKENS["dark"]["ink"]
    finally:
        theme.apply(app, "light")
    assert icons.INK == theme.TOKENS["light"]["ink"]


# ---- mirror, knife test, copies, weeding lines, strips ------------------------------------------------
def test_mirror_for_heat_transfer_vinyl_mirrors_only_the_job(win):
    win.use_profile_values(knife_offset_mm=0.0, overcut_mm=0.0)
    # an L: a long bar on the right (near the origin) and a short foot on the left
    win._on_drawn("rectangle", QRectF(-40, -60, 10, 40))
    win._on_drawn("rectangle", QRectF(-70, -30, 30, 10))
    view_before = [list(map(tuple, (n[:2] for n in e.paths[0]["nodes"]))) for e in win.design.elements]
    plain = win.build()
    win.mirror_job.setChecked(True)
    mirrored = win.build()
    assert "MIRRORED" in win.job_label.text()
    # the screen is unchanged; the job's box is the same, its content turned left to right
    assert [list(map(tuple, (n[:2] for n in e.paths[0]["nodes"]))) for e in win.design.elements] == view_before
    assert plain.bounds_mm == pytest.approx(mirrored.bounds_mm)
    assert plain.text != mirrored.text
    assert win.project_settings()["mirror"] is True


def test_the_knife_test_is_a_square_with_a_triangle_near_the_origin(win, messages):
    job = win.knife_test_job()
    assert job.paths == 2                                            # the square and the triangle
    xmin, xmax, ymin, ymax = job.bounds_mm
    assert xmin >= 5 - 1 and xmax <= 20 + 1 and ymin >= 5 - 1 and ymax <= 20 + 1    # mm from the origin


def test_copies_in_rows_and_columns(win):
    win._on_drawn("rectangle", QRectF(-30, -30, 20, 10))
    made = win.copies_selected({"rows": 2, "columns": 3, "gap": 5.0})
    assert len(made) == 5 and len(win.design.elements) == 6
    xs = sorted({round(e.bounds[1], 3) for e in win.design.elements})
    ys = sorted({round(e.bounds[3], 3) for e in win.design.elements})
    assert xs == [-60.0, -35.0, -10.0] and ys == [-35.0, -20.0]    # 20+5 across, 10+5 along
    win.undo()
    assert len(win.design.elements) == 1


def test_weeding_lines_reach_the_frame_and_keep_off_the_shapes(win):
    from vintyl.core import curves
    win._on_drawn("rectangle", QRectF(-100, -60, 20, 20))
    win._on_drawn("ellipse", QRectF(-60, -60, 20, 20))
    e = win.add_weeding_lines({"direction": "upright", "spacing": 10.0, "margin": 1.5})
    assert e is not None and win.weed_frame.isChecked() and win.design.elements[-1] is e
    frame = win.weed_frame_polyline(win._frame_polys(*win.design.material_paths()))
    along = [p[0] for p in frame]
    lines = curves.flatten(e.paths, 0.05)
    # a line through a gap runs the whole frame; lines never come within the margin of a shape
    tops = {round(-max(y for _x, y in l), 3) for l in lines}
    assert round(min(along), 3) in tops
    for l in lines:
        for x, y in l:
            assert not (-101.4 < x < -78.6 and -61.4 < y < -38.6)
    again = win.add_weeding_lines({"direction": "both", "spacing": 10.0, "margin": 1.5})
    assert [x for x in win.design.elements if x.spec and x.spec.get("kind") == "weeding"] == [again]


def test_a_wide_design_is_split_into_strips_along_the_material(win):
    win.use_profile_values(width_mm=300.0)
    win._on_drawn("rectangle", QRectF(-700, -100, 680, 60))        # 680 mm wide on a 300 mm cutter
    strips = win.split_into_strips({"direction": "across", "size": 280.0, "overlap": 10.0, "gap": 20.0})
    assert len(strips) == 3
    widths = [s.size[0] for s in strips]
    assert sum(widths) == pytest.approx(680 + 2 * 10, abs=0.5)      # every overlap counted twice
    for s in strips:
        xmin, xmax, ymin, ymax = s.bounds
        assert xmin >= -300 and xmax <= 0                            # each fits the cutting width
    ys = sorted((s.bounds[2], s.bounds[3]) for s in strips)
    assert all(a[1] < b[0] for a, b in zip(ys, ys[1:]))              # one after another, not on top
    assert len(win.design.elements) == 3                             # the strips replace the design


# ---- the sheet: rulers, the size of the selection, zoom (UI v2) ------------------------------------
def test_the_sheet_has_rulers_and_shows_the_size_of_the_selection(win):
    from PySide6.QtWidgets import QGraphicsSimpleTextItem
    texts = {i.text() for i in win.view.scene().items() if isinstance(i, QGraphicsSimpleTextItem)}
    assert {"0", "100", "700"} <= texts                         # under the front edge, 780 mm wide
    win._on_drawn("rectangle", QRectF(-100, -80, 40, 25))
    sizes = [l.text() for l in win.view._size_labels]
    assert sorted(sizes) in (["25.0", "40.0"], ["25,0", "40,0"])


def test_the_zoom_box_zooms_and_fits_again(win):
    win.show()
    win.view.fit_requested()
    assert win.view.zoom_percent() == 100 and win.view.zoom_label.text() == "100%"
    win.view.zoom_by(1.25)
    assert win.view.zoom_percent() == 125
    win.view.zoom_label.click()                                 # a click on the percentage: fit again
    assert win.view.zoom_percent() == 100


def test_zoom_out_stops_at_the_whole_sheet(win):
    """In as close as you like; out no further than the whole sheet, which
    then sits where Fit puts it (the wheel and the buttons alike)."""
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    win.show()
    view = win.view
    view.fit_requested()
    fitted = view.mapFromScene(QPointF(0, 0))
    for _i in range(5):
        view.zoom_by(1 / 1.25)
    assert view.zoom_percent() == 100 and not view._user_zoomed
    for _i in range(3):
        view.zoom_by(1.25)
    assert view.zoom_percent() == 195 and view._user_zoomed
    view.horizontalScrollBar().setValue(view.horizontalScrollBar().value() + 80)    # moved aside
    for _i in range(6):                                                          # the wheel, away from you
        view.wheelEvent(QWheelEvent(QPointF(200, 200), QPointF(200, 200), QPoint(0, 0), QPoint(0, -120),
                                    Qt.NoButton, Qt.NoModifier, Qt.ScrollEnd, False))
    assert view.zoom_percent() == 100 and not view._user_zoomed
    assert view.mapFromScene(QPointF(0, 0)) == fitted                           # back in its place


def test_the_cutter_settings_list_switches_and_asks_about_changes(win, monkeypatch):
    """Every cutter on the left; a change and then another cutter: asked
    (here: Save); the saved copy is marked changed."""
    from vintyl.gui import widgets
    from vintyl.gui.profile_editor import ProfileEditor
    dlg = ProfileEditor(win.profile_entries["vevor-ki-375a"], win)
    names = [dlg.list.item(i).text().split("\t")[0] for i in range(dlg.list.count())]
    assert "VEVOR KI-375A" in names and "Seiki SK-870T" in names
    assert dlg.list.currentItem().data(0x0100) == "vevor-ki-375a"
    dlg.knife.setValue(0.3)
    asked = []
    monkeypatch.setattr(widgets, "ask", lambda *a, **k: asked.append(a[2]) or "save")
    dlg.list.setCurrentRow(names.index("Seiki SK-870T"))
    assert asked and dlg.entry["id"] == "seiki-sk-870t" and dlg.name.text() == "Seiki SK-870T"
    from vintyl.core import profile as profiles
    saved = {e["id"]: e for e in profiles.catalogue()}["vevor-ki-375a"]
    assert saved["changed"] and saved["profile"].knife_offset_mm == pytest.approx(0.3)
    # no change: no question
    asked.clear()
    dlg.list.setCurrentRow(names.index("VEVOR KI-375A"))
    assert not asked and dlg.knife.value() == pytest.approx(0.3)


# ---- materials (UI v2, 6.1) --------------------------------------------------------------------------
def _choose_material(win, mid):
    win.material_box.setCurrentIndex(win.material_box.findData(mid))


def test_choosing_a_material_sets_the_tool_and_the_switches(win):
    _choose_material(win, "vinyl")
    win.weed_frame.setChecked(False)
    _choose_material(win, "htv")
    assert not win.is_pen() and win.mirror_job.isChecked() and win.weed_frame.isChecked()
    _choose_material(win, "paper")
    assert win.is_pen() and win.pen_width.value() == pytest.approx(0.4) and not win.mirror_job.isChecked()
    assert win.settings.value("cutter/material/" + win.profile_box.currentData()) == "paper"
    win.mirror_job.setChecked(True)                                  # changed by hand afterwards: kept
    assert win.mirror_job.isChecked()


def test_a_materials_values_come_before_the_cutters(win, tmp_path, monkeypatch):
    import dataclasses
    from vintyl.core import material as mats
    monkeypatch.setenv("VINTYL_MATERIALS", str(tmp_path / "m"))
    pid = win.profile_box.currentData()
    m = dataclasses.replace(mats.load_builtin("vinyl"), name="Thick", knife_offset_mm=0.4,
                            per_cutter={pid: {"force_g": 120.0, "speed_cm_s": 20.0}})
    mats.save_user("thick", m)
    win.reload_materials("thick")
    p = win.job_profile()
    assert p.knife_offset_mm == pytest.approx(0.4) and p.overcut_mm == pytest.approx(win.profile.overcut_mm)
    assert p.force_g == 120.0 and p.speed_cm_s == 20.0
    # a cutter set on its panel: shown, not sent
    assert not win.profile.send_speed_force
    assert "120" in win.material_hint.text() and not win.material_hint.isHidden()
    win._on_drawn("rectangle", QRectF(-60, -40, 20, 20))
    assert "FS" not in win.build().text and "VS" not in win.build().text
    win.use_profile_values(send_speed_force=True)
    assert "VS20" in win.build().text and "FS120" in win.build().text


def test_a_project_keeps_its_material_and_an_old_one_opens(win, tmp_path, app):
    _choose_material(win, "reflective")
    win._on_drawn("rectangle", QRectF(-60, -40, 20, 20))
    path = win.save_project(str(tmp_path / "m.vintyl"))
    from vintyl.core import project
    _design, st = project.load(path)
    assert st["material"] == "reflective"
    w2 = MainWindow()
    _choose_material(w2, "vinyl")
    assert w2.open_file(path) is not None and w2.material_box.currentData() == "reflective"
    # an older project, without a material: the current one stays
    st.pop("material")
    project.save(str(tmp_path / "old.vintyl"), _design, st)
    _choose_material(w2, "vinyl")
    assert w2.open_file(str(tmp_path / "old.vintyl")) is not None and w2.material_box.currentData() == "vinyl"
    w2.modified = False
    w2.close()


def test_the_materials_window_keeps_values_for_each_cutter(win, tmp_path, monkeypatch):
    from vintyl.core import material as mats
    from vintyl.gui.material_editor import MaterialEditor
    monkeypatch.setenv("VINTYL_MATERIALS", str(tmp_path / "m"))
    dlg = MaterialEditor(win, "vinyl", "vevor-ki-375a")
    dlg.force.setValue(90)
    dlg.speed.setValue(300.0)                                        # mm/s on screen: 30 cm/s kept
    dlg.for_cutter.setCurrentIndex(dlg.for_cutter.findData("seiki-sk-870t"))
    assert dlg.force.value() == 80                                   # the other (big) cutter: its own value
    dlg.force.setValue(110)
    assert not dlg.panel_note.isHidden()                              # it takes them from its panel
    dlg.save()
    m = {e["id"]: e for e in mats.catalogue()}["vinyl"]
    assert m["changed"] and m["material"].for_cutter("vevor-ki-375a") == (90.0, 30.0)
    assert m["material"].for_cutter("seiki-sk-870t") == (110.0, 30.0)
    assert dlg.chosen == "vinyl"


def test_speeds_are_shown_in_mm_per_second(win):
    """mm/s on screen; the profile keeps cm/s (the cutters' VS command)."""
    from vintyl.core import profile as profiles
    from vintyl.gui.profile_editor import ProfileEditor
    dlg = ProfileEditor(win.profile_entries["vevor-ki-375a"], win)
    assert dlg.speed.suffix() == " mm/s"
    dlg.speed.setValue(300.0)
    dlg.save()
    saved = {e["id"]: e for e in profiles.catalogue()}["vevor-ki-375a"]["profile"]
    assert saved.speed_cm_s == pytest.approx(30.0)
    assert ProfileEditor({**win.profile_entries["vevor-ki-375a"], "profile": saved}, win).speed.value() == 300.0


# ---- the windows before sending (UI v2, 5.4 and 5.5) ---------------------------------------------------
def test_the_check_list_shows_the_materials_values_and_the_mirror(win):
    from PySide6.QtWidgets import QLabel
    dlg = REAL_START_DIALOGS[0](win, "VEVOR KI-375A", "/dev/usb/lp1", False, "Vinyl film",
                                      ("Set on the cutter's panel", "90 g", "300 mm/s"), True, True,
                                      "Slowly.", show=False)
    texts = " ".join(l.text() for l in dlg.findChildren(QLabel))
    assert "90 g" in texts and "300 mm/s" in texts and "Slowly." in texts and "Mirror on" in texts
    assert "The knife is in the holder" in texts and "Speed and force are set" not in texts
    assert dlg.windowTitle() == "Cut now?" and dlg.go_button.text() == "Cut it"
    # a pen, no values: the panel point, no mirror warning
    dlg = REAL_START_DIALOGS[0](win, "X", "", True, "Paper", None, True, False, "", show=False)
    texts = " ".join(l.text() for l in dlg.findChildren(QLabel))
    assert dlg.windowTitle() == "Draw now?" and dlg.go_button.text() == "Draw"
    assert "Speed and force are set on the cutter's panel" in texts and "Mirror on" not in texts


def test_the_knife_test_window_has_the_tests_picture(win):
    from PySide6.QtWidgets import QLabel
    from vintyl.core import weeding
    dlg = REAL_START_DIALOGS[1](win, "Seiki SK-870T", 15, weeding.knife_test(15), show=False)
    labels = dlg.findChildren(QLabel)
    assert any(l.pixmap() is not None and not l.pixmap().isNull() for l in labels)
    # a value the material has not got: still there, as a dash with a note
    dlg = REAL_START_DIALOGS[1](win, "Seiki SK-870T", 15, weeding.knife_test(15),
                                ("Set on the cutter's panel", "90 g", None), show=False)
    texts = [l.text() for l in dlg.findChildren(QLabel)]
    assert "90 g" in texts and "–" in texts and any(t.startswith("not in the material") for t in texts)
    assert "Seiki SK-870T" in " ".join(l.text() for l in labels) and dlg.go_button.text() == "Cut the test"


# ---- the pattern windows' own preview (UI v2, 5.8) -----------------------------------------------------
def test_the_pattern_window_draws_the_shapes_in_its_preview(win):
    from PySide6.QtWidgets import QDoubleSpinBox
    from vintyl.gui.widgets import Switch
    win._on_drawn("ellipse", QRectF(-120, -110, 100, 100))
    dlg = win._ask_tile([win.selected], show=False)
    assert dlg.main_button.text() == "Insert the pattern" and dlg.preview.width() == 200
    assert dlg.findChildren(Switch)                                        # "every second row" is a switch
    assert _wait_for(lambda: not dlg.preview._pattern.isEmpty())
    first = dlg.preview._pattern.elementCount()
    assert "shapes fit" in dlg.status.text()
    dlg.findChildren(QDoubleSpinBox)[0].setValue(15.0)                    # bigger shapes: fewer
    assert _wait_for(lambda: dlg.preview._pattern.elementCount() < first)
    assert not dlg.preview.grab().isNull()
    dlg.previewer.wait()
    win.view.show_preview(None)


def test_the_fill_window_has_nine_pictures_and_a_preview(win):
    from PySide6.QtGui import QIcon
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win._on_drawn("rectangle", QRectF(-120, -80, 100, 60))
    box = win.selected
    dlg = win._ask_fill([box], show=False)
    seg = dlg.pattern
    assert seg.count() == 9 and seg.layout().rowCount() == 3 and seg.layout().columnCount() == 3
    for i in range(9):
        icon = seg.button(i).icon()
        assert not icon.isNull()
        assert icon.pixmap(30, 30, QIcon.Normal, QIcon.Off).toImage() != icon.pixmap(
            30, 30, QIcon.Normal, QIcon.On).toImage()                    # chosen: in the accent
    assert dlg.main_button.text() == "Fill it" and not dlg.remove_button.isEnabled()   # nothing to remove yet
    seg.setCurrentIndex(seg.findData("cross"))
    assert _wait_for(lambda: not dlg.preview._pattern.isEmpty() and box.fill and box.fill["pattern"] == "cross")
    dlg.previewer.wait()
    box.fill = {"pattern": "lines", "spacing": 2.0, "angle": 0.0, "margin": 0.0}
    dlg = win._ask_fill([box], show=False)
    assert dlg.remove_button.isEnabled() and dlg.pattern.currentData() == "lines"
    dlg.previewer.wait()


def test_the_fill_window_chooses_the_colour_that_draws_the_fill(win, monkeypatch):
    """Colour: As the shape, the design's colours, New colour… (chosen in the
    colour picker; the layer is made when the fill is accepted, before the
    outline's colour, so the outline is drawn last)."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win._on_drawn("rectangle", QRectF(-120, -80, 100, 60))
    box = win.selected
    dlg = win._ask_fill([box], show=False)
    combo = dlg.colour
    assert [combo.itemText(i) for i in range(combo.count())] == ["As the shape", "Black", "New colour…"]
    assert combo.currentData() == ""
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor("#ec4899")))
    combo.setCurrentIndex(combo.findData(win.NEW_COLOUR))
    assert combo.currentText() == "Pink" and len(win.design.layers) == 1         # not made yet
    values = dlg.values_now()
    dlg.previewer.wait()
    assert values["layer"] == values["new_layer"].id
    win._fill_these([box], values)
    pink = win.design.layers[0]
    assert [layer.name for layer in win.design.layers] == ["Pink", "Black"] and box.fill["layer"] == pink.id
    assert win.design.fill_layer_of(box) is pink and win.design.layer_of(box).name == "Black"
    # its own colour chosen: stored as "as the shape"
    win._fill_these([box], {"pattern": "lines", "spacing": 1.0, "layer": win.design.layers[1].id})
    assert "layer" not in box.fill
    # cancelled picker: the box goes back to what it showed
    dlg = win._ask_fill([box], show=False)
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor()))
    dlg.colour.setCurrentIndex(dlg.colour.findData(pink.id))
    dlg.colour.setCurrentIndex(dlg.colour.findData(win.NEW_COLOUR))
    assert dlg.colour.currentData() == pink.id
    dlg.previewer.wait()


def _gradient_png(path, w=120, h=80, alpha=False):
    """A picture: white on the left to black on the right."""
    from PySide6.QtGui import QColor, QImage
    img = QImage(w, h, QImage.Format_ARGB32)
    for x in range(w):
        v = int(255 * (1 - x / (w - 1)))
        for y in range(h):
            img.setPixelColor(x, y, QColor(v, v, v, 0 if alpha and x > w // 2 else 255))
    img.save(str(path))
    return str(path)


def test_a_picture_opens_as_a_pen_drawing(win, tmp_path, monkeypatch):
    """Open a picture: the knife is offered the pen; the lines go in as one
    element of open lines, the picture's box 10 mm from the origin."""
    from vintyl.gui import widgets
    path = _gradient_png(tmp_path / "g.png")
    asked = []
    monkeypatch.setattr(widgets, "ask", lambda *a, **k: asked.append(a[2]) or "pen")
    values = {"style": "waves", "width": 60.0, "spacing": 2.0, "strength": 100.0, "waves": 10.0,
              "contrast": 100.0, "brightness": 0.0, "invert": False, "lift": False, "joined": False}
    e = win.import_picture(path, values)
    assert asked and "pen" in asked[0] and win.is_pen()
    assert e in win.design.elements and e.name == "g" and not any(s["closed"] for s in e.paths)
    x0, x1, y0, y1 = e.bounds
    assert -71.5 < x0 < -69 and -11 < x1 < -9.5                    # 60 mm wide, 10 mm from the origin
    assert len(e.paths) == 20                                     # 40 mm high, a row every 2 mm
    win.undo()
    assert e not in win.design.elements
    # each style; transparent is paper
    for style in ("spiral", "hatching"):
        assert win.import_picture(_gradient_png(tmp_path / "a.png", alpha=True), dict(values, style=style))
    # a file that is no picture
    bad = tmp_path / "bad.png"
    bad.write_text("no")
    warned = []
    monkeypatch.setattr(widgets, "warn", lambda *a: warned.append(a[2]))
    assert win.import_picture(str(bad), values) is None and "Cannot read" in warned[0]


def test_a_big_drawing_works_its_job_out_after_the_clicks(win, tmp_path, monkeypatch):
    """A design of many points (a photo as lines): the job is worked out a
    moment after the last change, the sheet draws the element line by line
    with a hairline; a small design still at once."""
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    values = {"style": "waves", "width": 60.0, "spacing": 2.0, "strength": 100.0, "waves": 10.0,
              "contrast": 100.0, "brightness": 0.0, "invert": False, "lift": False, "joined": False}
    monkeypatch.setattr(type(win), "JOB_LATER_POINTS", 100)
    from vintyl.gui.canvas import ElementItem
    monkeypatch.setattr(ElementItem, "MANY_POINTS", 100)
    win.last_job = None
    e = win.import_picture(_gradient_png(tmp_path / "g.png"), values)
    item = [i for i in win.view._items if i.element is e][0]
    assert item._lines is not None and len(item._lines) == len(e.paths)     # drawn line by line
    assert not win.view.grab().isNull()
    assert win.last_job is None                                    # not yet
    assert _wait_for(lambda: win.last_job is not None and win.last_job.cut_mm > 0)


def _square_png(path):
    """A dark 40 x 40 px square with a hole of 10 x 10 px, in a 100 x 60 px white picture."""
    from PySide6.QtGui import QColor, QImage
    img = QImage(100, 60, QImage.Format_RGB32)
    img.fill(QColor("white"))
    for x in range(20, 60):
        for y in range(10, 50):
            if not (35 <= x < 45 and 25 <= y < 35):
                img.setPixelColor(x, y, QColor("black"))
    img.save(str(path))
    return str(path)


def test_a_picture_is_traced_into_shapes_to_cut(win, tmp_path, monkeypatch):
    """Trace: the dark square and its hole become two closed outlines, in
    mm where they are in the picture, the picture's box 10 mm from the
    origin; Open takes a picture so with the knife, as lines with the pen."""
    path = _square_png(tmp_path / "logo.png")
    values = {"width": 50.0, "threshold": 50.0, "specks": 1.0, "detail": 0.15, "invert": False, "smooth": False}
    e = win.trace_picture(path, values)
    assert e in win.design.elements and len(e.paths) == 2 and all(s["closed"] for s in e.paths)
    x0, x1, y0, y1 = e.bounds
    # the picture is 50 x 30 mm (0.5 mm a pixel), its top-left at (-60, -40); the square 20 mm from the left
    assert abs(x0 - (-60 + 10)) < 0.6 and abs(x1 - (-60 + 30)) < 0.6 and abs(y0 - (-40 + 5)) < 0.6
    win.undo()
    assert e not in win.design.elements
    # Open: with the knife a picture is traced, with the pen it is drawn
    called = []
    monkeypatch.setattr(type(win), "trace_picture", lambda self, p=None, v=None: called.append("trace"))
    monkeypatch.setattr(type(win), "import_picture", lambda self, p=None, v=None: called.append("draw"))
    win.open_file(path)
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win.open_file(path)
    assert called == ["trace", "draw"]


def test_the_knife_can_trace_instead_of_drawing(win, tmp_path, monkeypatch):
    from vintyl.gui import widgets
    monkeypatch.setattr(widgets, "ask", lambda *a, **k: "trace")
    traced = []
    monkeypatch.setattr(type(win), "trace_picture", lambda self, p=None, v=None: traced.append(p) or "shape")
    path = _square_png(tmp_path / "logo.png")
    assert win.import_picture(path, {"style": "waves", "width": 50.0, "spacing": 2.0}) == "shape"
    assert traced == [path] and not win.is_pen()


def test_the_trace_window_previews_the_outlines(win, tmp_path):
    from vintyl.gui import picture_import, trace_import
    img = picture_import.load_image(_square_png(tmp_path / "logo.png"))
    dlg = trace_import.trace_dialog(win, img, show=False)
    dlg.show()
    assert _wait_for(lambda: "2 outlines" in dlg.status.text())
    assert not dlg.preview._outline.isEmpty() and dlg.values_now()["width"] > 0
    dlg.previewer.wait()
    dlg.close()


def test_weld_joins_the_letters_and_the_text_stays_editable(win):
    """Weld (the text's union button): overlapping letters become one
    outline, the holes stay; the text is welded again when it changes; it
    is kept in the text's spec."""
    from PySide6.QtCore import QPointF
    from vintyl.gui import text as texts
    win.opt_text.setText("Vintyl")
    win.opt_spacing.setValue(-2.0)                       # letters into each other
    win._on_text_clicked(QPointF(-200, -100))
    e = win.selected
    apart = len(e.paths)
    win.opt_weld.setChecked(True)
    assert e.spec.get("weld") is True and len(e.paths) < apart
    # holes stay: "oo" welded still has two holes
    holes = texts.weld(texts.text_paths("oo", e.spec["family"], 20.0, False, False, 0.0))
    assert len(holes) == 4
    # edited: welded again, still where it was
    x0 = e.bounds[0]
    win.opt_text.setText("Vintyl Vintyl")
    win._text_changed()
    assert e.spec["text"] == "Vintyl Vintyl" and e.spec.get("weld") and abs(e.bounds[0] - x0) < 0.01
    welded = len(e.paths)
    win.opt_weld.setChecked(False)
    assert "weld" not in e.spec and len(e.paths) > welded
    # another text selected shows its own state
    win.opt_weld.setChecked(True)
    win.selected, win.selection = e, [e]
    win._show_text_options()
    assert win.opt_weld.isChecked()


def test_files_given_at_the_start_open_once_the_window_is_up(tmp_path, monkeypatch):
    """python -m vintyl photo.jpg drawing.svg: each opens (a picture too),
    after the window is shown; other files are left alone."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from vintyl import i18n
    from vintyl.core import diag
    from vintyl.gui import app as vintyl_app
    from vintyl.gui import theme
    from vintyl.gui.main_window import MainWindow
    # main() sets the language, the look and the log of the user's system: kept as the tests have them
    real_setup = i18n.setup
    monkeypatch.setattr(i18n, "setup", lambda language="": real_setup("en"))
    monkeypatch.setattr(theme, "apply", lambda *a, **k: None)
    monkeypatch.setattr(diag, "setup", lambda *a, **k: None)
    opened = []
    monkeypatch.setattr(MainWindow, "open_file", lambda self, p: opened.append((p, self.isVisible())))
    monkeypatch.setattr(MainWindow, "check_for_updates", lambda self, auto=False: None)
    monkeypatch.setattr(MainWindow, "install_menu_entry", lambda self, ask=False: None)
    monkeypatch.setattr(QApplication, "exec", lambda self: QTest.qWait(50) or 0)
    photo, svg = str(tmp_path / "photo.JPG"), str(tmp_path / "logo.svg")
    assert vintyl_app.main(["vintyl", photo, svg, str(tmp_path / "notes.txt")]) == 0
    assert opened == [(photo, True), (svg, True)]


def test_the_picture_window_shows_the_fields_of_its_style_and_a_preview(win, tmp_path):
    from vintyl.gui import picture_import
    img = picture_import.load_image(_gradient_png(tmp_path / "g.png"))
    dlg = picture_import.picture_dialog(win, img, show=False)
    rows = {key: w for key, _l, w in dlg.rows}
    shown = lambda key: not (rows[key] if key in ("lift", "joined", "invert") else rows[key].parentWidget()).isHidden()  # noqa: E731
    dlg.show()
    assert shown("strength") and shown("joined") and not shown("angle")
    dlg.style.setCurrentIndex(dlg.style.findData("hatching"))
    assert shown("angle") and not shown("strength") and not shown("joined") and not shown("lift")
    dlg.style.setCurrentIndex(dlg.style.findData("spiral"))
    assert shown("lift") and not shown("joined")
    assert _wait_for(lambda: not dlg.preview._pattern.isEmpty() and "mm" in dlg.status.text())
    assert dlg.values_now()["style"] == "spiral"
    dlg.previewer.wait()
    dlg.close()


def test_every_pattern_has_a_picture():
    from vintyl.gui.main_window import MainWindow
    from vintyl.gui.previews import pattern_icon
    for code, _label in MainWindow.FILL_PATTERNS:
        if code == "concentric":
            from vintyl.core import offset
            if not offset.available():
                continue
        img = pattern_icon(code, 30).pixmap(30, 30).toImage()
        inked = sum(1 for x in range(30) for y in range(30) if img.pixelColor(x, y).alpha() > 0)
        assert inked > 30, code


# ---- the Help menu's windows (UI v2, 5.9 to 5.11) ------------------------------------------------------
def test_the_shortcuts_are_in_groups_and_can_be_searched(win):
    groups = dict(win.shortcut_groups())
    assert list(groups)[:4] == ["Tools", "File", "Edit", "Object"] and "View and program" in groups
    tools = {name: keys for name, keys, _about in groups["Tools"]}
    assert tools["Rectangle"] == ["R"] and tools["Fill"] == ["Shift+F"] and tools["Pattern of shapes"]
    assert ("New", ["Ctrl+N"]) in [(n, k) for n, k, _a in groups["File"]]
    names = [n for _g, rows in win.shortcut_groups() for n, _k, _a in rows]
    assert len(names) == len(set(names))                                # each key once
    dlg = win.show_shortcuts(show=False)
    assert len(dlg.cards) == len(groups)
    dlg.search.setText("ctrl+n")
    assert [c.isHidden() for c in dlg.cards].count(False) == 1          # only File has it
    dlg.search.setText("nothing like this")
    assert all(c.isHidden() for c in dlg.cards)
    dlg.search.setText("")
    assert not any(c.isHidden() for c in dlg.cards)


def test_key_parts_keep_the_plus_key():
    from vintyl.gui.info_dialogs import key_parts
    assert key_parts("Ctrl+Shift+G") == ["Ctrl", "Shift", "G"]
    assert key_parts("Ctrl++") == ["Ctrl", "+"] and key_parts("+") == ["+"]


def test_the_about_window(win):
    from PySide6.QtWidgets import QLabel
    from vintyl import __version__
    from vintyl.gui import info_dialogs
    dlg = win.about(show=False)
    texts = " ".join(l.text() for l in dlg.findChildren(QLabel))
    assert __version__ in texts and "GPL-3.0-or-later" in texts and "github.com/cyryllo/vintyl" in texts
    notices = info_dialogs.notices_dialog(dlg, show=False)
    assert "Third-party software in Vintyl" in notices.text.toPlainText()


def test_the_access_window_says_the_state_and_copies_the_commands(win):
    from PySide6.QtGui import QGuiApplication
    from vintyl.gui import info_dialogs
    dlg = info_dialogs.access_dialog(win, "/dev/usb/lp1", None, show=False)
    assert dlg.state.objectName() == "state_ok"
    dlg.copy_button.click()
    assert QGuiApplication.clipboard().text() == "sudo usermod -aG lp $USER\nsudo usermod -aG dialout $USER"
    dlg = info_dialogs.access_dialog(win, "/dev/usb/lp1", "you are not in the group lp", show=False)
    assert dlg.state.objectName() == "warn"
    assert win.show_access_help(show=False).windowTitle() == "Access to the cutter"


def test_the_window_fits_a_1366_screen_in_every_state_of_the_bar(win):
    """UI v2, 8: the selection bar never makes the window wider than 1366 px:
    a rectangle, a polygon, a text, a text on a path (and nothing selected)."""
    from PySide6.QtTest import QTest
    win.resize(1366, 768)
    win.show()
    QTest.qWait(30)

    def fits():
        QTest.qWait(20)
        return win.width() == 1366 and win.minimumSizeHint().width() <= 1366 - 24
    assert fits()
    win._on_drawn("rectangle", QRectF(-160, -120, 90, 60))
    assert fits()
    win._on_drawn("polygon", QRectF(-280, -120, 70, 70))
    assert fits()
    win._on_text_clicked(QPointF(-260, -260))
    text = win.selected
    assert fits()
    win._on_drawn("ellipse", QRectF(-200, -330, 120, 120))
    win.selection, win.selected = [text, win.selected], text
    win.put_text_on_path()
    win.selection = [win.selected]
    win._show_options()
    assert fits() and not win.opt_path_flip.isHidden()
    win.set_tool("nodes")
    assert fits() and not win.node_hint.isHidden()


def test_start_save_and_the_knife_test_are_pinned_under_the_panel(win):
    """They are not in the scrolling panel: always in sight, also on a low screen."""
    from PySide6.QtTest import QTest
    win.resize(1366, 600)
    win.show()
    QTest.qWait(30)
    panel = win.left_scroll.widget()
    for b in (win.btn_start, win.btn_save, win.btn_test, win.progress):
        assert not panel.isAncestorOf(b) and win.send_footer.isAncestorOf(b)
    bottom = win.send_footer.mapTo(win, win.send_footer.rect().bottomLeft()).y()
    assert win.btn_start.isVisible() and bottom <= win.height()


def test_the_check_list_always_shows_the_cutting_values(win):
    """A built-in material has no force or speed: the card is still there,
    with dashes, where to write them, and the knife's own values."""
    from PySide6.QtWidgets import QLabel
    from vintyl.core.material import Material
    bare = Material(name="Own vinyl", blade="45")                   # the user's own, no values yet
    values = win.material_values(bare)
    assert values is not None and values[1] is None and values[2] is None
    lines = dict(win.cut_details(bare))
    assert dict(lines["In the holder"])["Blade"] == "45° (standard)"   # the blade: put in, not sent
    vintyl = dict(lines["Worked into the knife's path by Vintyl"])      # offset and overcut: in the path
    assert vintyl["Knife offset"].endswith(" mm") and "Overcut" in vintyl
    dlg = REAL_START_DIALOGS[0](win, "VEVOR KI-375A", "/dev/usb/lp1", False, "Own vinyl", values, True,
                                False, "", show=False, details=win.cut_details(bare))
    texts = " ".join(l.text() for l in dlg.findChildren(QLabel))
    assert "–" in texts and "has no force or speed" in texts and "Knife offset <b>" in texts
    assert "In the holder: Blade <b>" in texts and "Worked into the knife's path by Vintyl: " in texts
    assert "not in the material" not in texts                     # one hint, not one under each dash
    # the pen: its width and where its stroke lies
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    assert [label for label, _v in dict(win.cut_details())["Worked into the pen's path by Vintyl"]] == \
        ["Pen width", "Draw"]
    # the knife test shows the knife's values, also from the pen mode
    assert "Knife offset" in dict(dict(win.cut_details(pen=False))["Worked into the knife's path by Vintyl"])


def _drag(view, start, end, steps=5):
    """Press at start, move in steps, let go at end (view pixels), as a hand does."""
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    vp = view.viewport()
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, start)
    for k in range(1, steps + 1):
        p = start + (end - start) * k / steps
        QApplication.sendEvent(vp, QMouseEvent(QMouseEvent.MouseMove, QPointF(p), QPointF(vp.mapToGlobal(p)),
                                               Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QTest.qWait(10)
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, end)
    QTest.qWait(20)


def test_a_square_dragged_with_the_mouse_makes_the_shape_smaller(win):
    """The square under the mouse keeps the drag to the end (it was made
    again at the first move and the shape went back to its size), also when
    the sheet is drawn again meanwhile."""
    win.resize(1366, 768)
    win.show()
    win._on_drawn("rectangle", QRectF(-300, -200, 100, 60))
    e = win.selected
    v = win.view
    corner = [h for h in v._handles if h.place == (0, 0)][0]
    a = v.mapFromScene(corner.scenePos())
    b = v.mapFromScene(corner.scenePos() + QPointF(30, 20))
    v._sheet_timer.start()                               # the window changes size while dragging
    _drag(v, a, b)
    w, h = e.size
    assert w < 80 and h < 50 and w / h == pytest.approx(100 / 60, rel=0.02)
    # and back bigger, by a side's square, the proportions unlocked
    win.opt_lock.setChecked(False)
    side = [h for h in v._handles if h.place == (0, 0.5)][0]
    a = v.mapFromScene(side.scenePos())
    _drag(v, a, v.mapFromScene(side.scenePos() + QPointF(-40, 0)))
    assert e.size[0] > w + 30 and e.size[1] == pytest.approx(h, abs=0.01)


def test_the_wheel_over_the_left_panel_does_not_change_its_fields(win):
    """Scrolling the left panel with the wheel leaves the material and the
    pen's width as they were (they take the wheel only once clicked)."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtTest import QTest
    from vintyl.gui import theme
    theme.apply(QApplication.instance(), "light")
    win.resize(1366, 600)
    win.show()
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win.view.setFocus()
    QTest.qWait(20)
    material, width = win.material_box.currentIndex(), win.pen_width.value()
    for w in (win.material_box, win.pen_width):
        c = w.rect().center()
        QApplication.sendEvent(w, QWheelEvent(QPointF(c), QPointF(w.mapToGlobal(c)), QPoint(0, 0), QPoint(0, -120),
                                              Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
    assert win.material_box.currentIndex() == material and win.pen_width.value() == width


# ---- to the origin (as Kerfly's "design to the head") --------------------------------------------------
def test_the_whole_design_moves_to_the_origin_as_it_is_laid_out(win):
    win._on_drawn("ellipse", QRectF(-300, -250, 60, 40))
    win._on_drawn("rectangle", QRectF(-420, -330, 50, 50))
    a, b = win.design.elements
    gap_before = (a.bounds[0] - b.bounds[0], a.bounds[2] - b.bounds[2])
    win.view.select_many([])
    win.selected, win.selection = None, []
    undo = len(win._undo)
    assert win.move_to_origin() == 0.0                          # no frame: right up to the origin
    boxes = [e.bounds for e in win.design.elements]
    assert max(bx[1] for bx in boxes) == pytest.approx(0.0) and max(bx[3] for bx in boxes) == pytest.approx(0.0)
    assert (a.bounds[0] - b.bounds[0], a.bounds[2] - b.bounds[2]) == pytest.approx(gap_before)   # laid out as before
    assert len(win._undo) == undo + 1 and win.build().cut_mm > 0  # one step to undo; it cuts


def test_only_the_selected_go_to_the_origin_and_room_is_left_for_the_frame(win):
    win._on_drawn("ellipse", QRectF(-300, -250, 60, 40))
    stays = win.selected
    where = stays.bounds
    win._on_drawn("rectangle", QRectF(-420, -330, 50, 50))
    goes = win.selected
    win.weed_frame.setChecked(True)
    win.weed_margin.setValue(5.0)
    moved = win.move_to_origin()
    assert stays.bounds == pytest.approx(where)                 # not selected: stays
    assert 5.0 <= moved <= 5.0 + 1.5                            # the frame's margin and the knife's room
    assert goes.bounds[1] == pytest.approx(-moved) and goes.bounds[3] == pytest.approx(-moved)
    win.build()                                                  # the job can be made (nothing below zero)


def test_to_the_origin_is_in_the_menus_and_on_the_ribbon(win):
    from PySide6.QtGui import QKeySequence
    assert win.act_to_origin.shortcut() == QKeySequence("Ctrl+Home")
    assert win.act_to_origin in win.show_context_menu(None, None, show=False).actions()
    win._on_drawn("rectangle", QRectF(-420, -330, 50, 50))
    assert win.act_to_origin in win.show_context_menu(win.selected, None, show=False).actions()
    assert any(win.act_to_origin in [b.defaultAction() for b in g.findChildren(QToolButton)]
               for g in win.ribbon_groups.values())
    win.design.elements.clear()
    win.refresh()
    assert win.move_to_origin() is None                         # an empty design: nothing to move


def test_the_element_list_has_the_right_click_menu(win):
    """Right button on a row: that element is selected and the menu offers
    Duplicate and Delete (as on the sheet); they act on it."""
    win.show()
    win._on_drawn("rectangle", QRectF(-100, -60, 40, 20))
    win._on_drawn("ellipse", QRectF(-50, -60, 20, 20))
    first = win.design.elements[0]
    lst = win.element_list
    pos = lst.visualItemRect(lst.item(0)).center()
    menu = win.list_context_menu(pos, show=False)
    assert win.selected is first
    texts = [a.text().replace("&", "") for a in menu.actions()]
    assert "Duplicate" in texts and "Delete" in texts
    [a for a in menu.actions() if a.text().replace("&", "") == "Duplicate"][0].trigger()
    assert len(win.design.elements) == 3
    win.selected, win.selection = first, [first]
    menu = win.list_context_menu(lst.visualItemRect(lst.item(0)).center(), show=False)
    [a for a in menu.actions() if a.text().replace("&", "") == "Delete"][0].trigger()
    assert first not in win.design.elements and len(win.design.elements) == 2


def test_the_set_triangle_only_where_a_set_opens(win):
    """With the knife Fill opens no set (it goes to the pattern of shapes):
    no triangle there; with the pen it opens one: the triangle is back."""
    b = win.category_buttons
    win.tool_box.setCurrentIndex(win.tool_box.findData("knife"))
    assert not b["fill"].has_set and b["shapes"].has_set and not b["pick"].has_set
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    assert b["fill"].has_set


def test_the_help_menu_opens_its_windows(win, monkeypatch):
    """Every Help menu item opens its window: Qt passes "checked" (False)
    to a triggered action's slot, which windows with show=True took for
    show=False (built, never opened)."""
    from PySide6.QtWidgets import QDialog
    opened = []
    monkeypatch.setattr(QDialog, "exec", lambda dlg: opened.append(dlg.windowTitle()) or 0)
    help_menu = win.menus["help"]
    for a in help_menu.actions():
        if a.isSeparator() or not a.isVisible() or a.text().startswith("Check for a new"):
            continue
        before = len(opened)
        a.trigger()
        assert len(opened) == before + 1, a.text()                # a window was opened (run)
    assert {"About Vintyl", "Keyboard shortcuts", "Access to the cutter", "Diagnostic report"} <= set(opened)


def test_the_settings_windows_scroll_instead_of_squeezing_their_cards(win):
    """Made low, the cutter settings and the materials windows scroll their
    cards; the cards never lie over each other, nor are cut at the side."""
    from PySide6.QtTest import QTest
    from vintyl.core import profile
    from vintyl.gui.material_editor import MaterialEditor
    from vintyl.gui.profile_editor import ProfileEditor
    from vintyl.gui.widgets import Card
    entry = [e for e in profile.catalogue() if e["profile"]][0]
    for dlg in (ProfileEditor(entry, win), MaterialEditor(win, "vinyl", None)):
        dlg.resize(1000, 420)
        dlg.show()
        QTest.qWait(30)
        cards = [c for c in dlg.findChildren(Card) if c.isVisible()]
        rects = [c.geometry().translated(c.parentWidget().mapTo(dlg, c.parentWidget().rect().topLeft()))
                 for c in cards]
        for i, a in enumerate(rects):
            assert cards[i].height() >= cards[i].minimumSizeHint().height() - 1, cards[i].title_label.text()
            for b in rects[i + 1:]:
                assert not a.intersects(b)
        from PySide6.QtWidgets import QWidget
        inner = dlg.findChild(QWidget, "plain_scroll_inner")
        area = inner.parentWidget().parentWidget()
        assert inner.width() <= area.viewport().width()          # nothing cut at the side
        dlg.close()


@pytest.mark.parametrize("lang", ["en", "pl", "de", "es", "fr", "pt_BR"])
def test_the_window_fits_a_1366_screen_in_every_language(app, lang):
    """Longer words must not widen the selection bar past a 1366 px screen
    (Spanish and Portuguese did, with a text on a path), nor the ribbon
    (German needed 1549 px: it was squeezed and its labels cut), nor cut
    the names in the tool strip ("Desplazamiento" in a 66 px tile)."""
    from PySide6.QtGui import QFont, QFontMetrics
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QToolBar
    from vintyl import i18n
    i18n.setup(lang)
    w = MainWindow()
    try:
        w.resize(1366, 768)
        w.show()
        assert w.findChild(QToolBar).sizeHint().width() <= 1366 - 10, "ribbon"
        for cat, b in w.category_buttons.items():
            font = QFont(b.font())                       # the tile's own (10 px, or 9 when its name is long)
            if any(e[0] == "tool" for e in w.category_entries[cat]):
                font.setWeight(QFont.DemiBold)           # bold when chosen
            assert QFontMetrics(font).horizontalAdvance(b.text()) <= b.width() - 6, b.text()

        def fits():
            QTest.qWait(20)
            return w.width() == 1366 and w.minimumSizeHint().width() <= 1366 - 24
        w._on_drawn("rectangle", QRectF(-160, -120, 90, 60))
        assert fits(), "rectangle"
        w._on_text_clicked(QPointF(-260, -260))
        text = w.selected
        w._on_drawn("ellipse", QRectF(-200, -330, 120, 120))
        w.selection, w.selected = [text, w.selected], text
        w.put_text_on_path()
        w.selection = [w.selected]
        w._show_options()
        assert fits(), "text on a path"
    finally:
        w.close()
        i18n.setup("en")


# ---- colour layers (0.9) ------------------------------------------------------------------------------
DEMO_SVG = os.path.join(os.path.dirname(__file__), "..", "docs", "demo", "vintyl-demo.svg")
from vintyl.gui.widgets import COLOR_ROLE as COLOR_ROLE_FOR_TESTS  # noqa: E402


def test_a_colour_drawing_is_imported_by_colour(win):
    """Vintyl's demo logo: its colours become layers (similar ones merged),
    one element per colour and kind, grouped; filled shapes get a fill for
    the pen; undo takes the layers back too."""
    first = win.import_svg(DEMO_SVG, "auto")
    d = win.design
    names = [layer.name for layer in d.layers]
    assert names[:2] == ["Black", "Pink"] and "Green" in names and "Black 2" not in names   # no empty black left
    assert len(d.layers) == 5
    assert len({e.group for e in d.elements}) == 1 and first in d.elements                 # moved as one
    pink = d.layers[1]
    kinds = {(d.layer_of(e) is pink, e.fill is not None) for e in d.elements if d.layer_of(e) is pink}
    assert kinds == {(True, True), (True, False)}            # the filled V and the underline (a stroke only)
    # the sheet draws each element in its layer's colour
    item = [i for i in win.view._items if i.element.fill is not None and d.layer_of(i.element) is pink][0]
    assert item.color.name() == pink.color
    win.undo()
    assert d is win.design and not win.design.elements and [layer.id for layer in win.design.layers] == ["black"]


def test_the_colours_section_lists_the_layers_and_changes_them(win):
    win.show()
    assert win.colours_box.isHidden()                                  # one colour: no section
    win.import_svg(DEMO_SVG, "auto")
    d = win.design
    assert not win.colours_box.isHidden() and win.layer_list.count() == len(d.layers)
    assert win.layer_list.item(1).text().startswith("Pink")
    assert win.element_list.model().index(0, 0).data(COLOR_ROLE_FOR_TESTS) == d.layer_of(d.elements[0]).color
    # untick a colour: it is left out
    win.layer_list.item(1).setCheckState(Qt.Unchecked)
    assert not d.layers[1].enabled
    # a click selects its elements
    win._layer_clicked(win.layer_list.item(2))
    assert set(map(id, win.selection)) == set(map(id, d.elements_of(d.layers[2])))
    # the order of drawing
    win.layer_list.setCurrentRow(2)
    third = d.layers[2]
    win.move_layer(-1)
    assert d.layers[1] is third and win.layer_list.currentRow() == 1
    # a colour's name, colour and pen
    win.edit_layer(third, {"name": "Steel", "color": "#445566", "pen_width_mm": 0.8, "pen_place": "outside"})
    assert (third.name, third.color, third.pen_width_mm, third.pen_place) == ("Steel", "#445566", 0.8, "outside")
    # elements into another colour, or a new one
    e = d.elements[0]
    win.selected, win.selection = e, [e]
    win.move_to_layer(third)
    assert d.layer_of(e) is third
    new = win.new_layer_for_selection("#00aa00")
    assert d.layer_of(e) is new and new.name == "Green 2"
    menu = win.show_context_menu(e, None, show=False)
    colour = [a.menu() for a in menu.actions() if a.menu() is not None and a.text() == "Colour"][0]
    assert [a.text() for a in colour.actions() if a.text()][:2] == [d.layers[0].name, d.layers[1].name]


def test_the_colours_window_proposes_and_can_be_changed(win, monkeypatch):
    """Opening a drawing of several colours: the window shows the proposal
    (merged by default; each on its own when the Settings say so), and what
    it returns is what opens."""
    from vintyl.gui import colour_import
    real = colour_import.colour_dialog
    seen = {}

    def fake(parent, groups, candidates, chosen, merged, separate, show=True):
        dlg = real(parent, groups, candidates, chosen, merged, separate, show=False)
        seen["start"] = {c: layer.name for c, layer in dlg.chosen_now().items()}
        assert not dlg.picture.pixmap().isNull()
        dlg.separate_button.click()
        seen["separate"] = len(set(dlg.chosen_now().values()))
        dlg.all_one_button.click()                    # all in one colour: what opens
        return dlg.chosen_now()
    monkeypatch.setattr(colour_import, "colour_dialog", fake)
    win.import_svg(DEMO_SVG)
    assert seen["start"]["#c21a63"] == seen["start"]["#be185d"] == "Pink"     # merged
    assert seen["separate"] == 9                                                 # each its own
    assert len(win.design.layers) == 1 and win.colours_box.isHidden()        # all in one
    # the Settings: each on its own first
    win.new_design()
    win.show_settings({"grid_step": 10.0, "snap_objects": True, "import_colours": "ask"})
    win.import_svg(DEMO_SVG)
    assert seen["start"]["#c21a63"] != seen["start"]["#be185d"]
    # cancelled: nothing opens
    monkeypatch.setattr(colour_import, "colour_dialog", lambda *a, **k: None)
    win.new_design()
    assert win.import_svg(DEMO_SVG) is None and not win.design.elements


def test_a_drawing_of_many_colours_scrolls_its_list(win, tmp_path):
    from vintyl.gui import colour_import
    from vintyl.core.loaders import load_svg_colors
    rects = "".join('<rect x="%d" y="5" width="4" height="4" fill="#%02x%02x%02x"/>' % (6 * k, 12 * k, 200 - 9 * k, 40)
                    for k in range(20))
    p = tmp_path / "many.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="130mm" height="20mm" viewBox="0 0 130 20">%s</svg>'
                 % rects)
    groups = load_svg_colors(str(p))
    _e, candidates, chosen, merged, separate = win._colour_plan(groups)
    dlg = colour_import.colour_dialog(win, groups, candidates, chosen, merged, separate, show=False)
    assert len(dlg.combos) == 20 and dlg.height() < 768


def test_each_colour_is_a_job_of_its_own_and_they_fall_on_each_other(win):
    """The colours' jobs, one after another: each only its colour's paths;
    together the same paths as the whole design's job; mirrored, each within
    the whole design's box (so the colours still fall on each other)."""
    win.import_svg(DEMO_SVG, "auto")
    d = win.design
    jobs = win.layer_jobs()
    assert [layer for layer, _j in jobs] == [ly for ly in d.layers if d.elements_of(ly)]
    whole = win.build()
    assert sum(len(j.knife_paths) for _l, j in jobs) == len(whole.knife_paths) - (1 if win.weed_frame.isChecked() else 0) \
        or not win.weed_frame.isChecked()
    def box(job):
        xs = [x for p in job.knife_paths for x, _y in p]
        ys = [y for p in job.knife_paths for _x, y in p]
        return min(xs), max(xs), min(ys), max(ys)
    # mirrored: the pink V is mirrored within the whole design's width, not its own
    # (so it stays where it belongs against the black text); 1 mm: the knife's compensation
    win.mirror_job.setChecked(True)
    pink_layer = d.layers[1]
    pink = [j for layer, j in win.layer_jobs() if layer is pink_layer][0]
    every = [a for p in d.material_paths()[0] for _x, a in p]
    lo, hi = min(every), max(every)
    own = [a for p in d.material_paths(layer=pink_layer)[0] for _x, a in p]
    expected = (lo + hi - max(own), lo + hi - min(own))
    got = box(pink)[2:]
    assert got[0] == pytest.approx(expected[0], abs=1.0) and got[1] == pytest.approx(expected[1], abs=1.0)
    # a colour left out is not cut, and alone it is "nothing to cut"
    d.layers[1].enabled = False
    assert d.layers[1] not in [layer for layer, _j in win.layer_jobs()]
    with pytest.raises(Exception):
        win.build(d.layers[1])


def test_start_draws_colour_after_colour_with_a_pause(win, monkeypatch, messages):
    """Start with several colours: the check list once, then before each
    colour its window (put in that pen); the next colour goes once the one
    before is sent; a colour can be skipped, and Finish stops the rest."""
    from vintyl.gui import start_dialogs
    win.import_svg(DEMO_SVG, "auto")
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    jobs = win.layer_jobs()
    asked, sent = [], []
    answers = ["go", "skip", "go", None]

    def colour(parent, index, total, name, color, pen, width, show=True):
        asked.append((index, total, name, pen))
        return answers[len(asked) - 1]
    monkeypatch.setattr(start_dialogs, "confirm_colour", colour)
    monkeypatch.setattr(win, "_send", lambda job, p, what: sent.append(job.text) or "worker")
    assert win.start() == "worker"
    assert asked == [(1, len(jobs), jobs[0][0].name, True)] and sent == [jobs[0][1].text]
    win._send_finished(True, "Sent")                  # the first colour is sent: the next window
    from PySide6.QtTest import QTest
    QTest.qWait(30)
    assert [a[0] for a in asked] == [1, 2, 3] and sent == [jobs[0][1].text, jobs[2][1].text]   # 2 skipped
    win._send_finished(True, "Sent")
    QTest.qWait(30)
    assert len(asked) == 4 and len(sent) == 2 and not win._colour_queue                     # finished
    # a stop (or a failure) leaves the other colours
    asked.clear()
    answers[:] = ["go"] * 9
    sent.clear()
    win.start()
    win._send_finished(False, "Stopped")
    QTest.qWait(30)
    assert len(sent) == 1 and not win._colour_queue


def test_the_colour_window_says_what_to_put_in(win):
    dlg = REAL_START_DIALOGS[2](win, 2, 3, "Pink", "#be185d", True, "0,4 mm", show=False)
    from PySide6.QtWidgets import QLabel
    texts = " ".join(l.text() for l in dlg.findChildren(QLabel))
    assert dlg.windowTitle() == "Colour 2 of 3: Pink" and "Put in the pen: <b>Pink</b> (0,4 mm)" in texts
    assert dlg.go_button.text() == "Draw" and dlg.skip_button.text() == "Skip this colour"
    dlg = REAL_START_DIALOGS[2](win, 1, 2, "Black", "#1f2430", False, show=False)
    assert "Put in the vinyl: <b>Black</b>" in " ".join(l.text() for l in dlg.findChildren(QLabel))


def test_a_colour_gets_a_fill_of_its_own(win):
    """The bucket in the Colours head: every closed shape of the chosen
    colour gets the pattern, also an outline (the green ring); pen only."""
    win.show()
    win.import_svg(DEMO_SVG, "auto")
    d = win.design
    green = [layer for layer in d.layers if layer.name == "Green"][0]
    # the knife: no fill, and no button
    assert win.btn_layer_fill.isHidden() and win.fill_layer(green, {"pattern": "cross", "spacing": 1.0}) == []
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    assert not win.btn_layer_fill.isHidden()
    assert all(e.fill is None for e in d.elements_of(green))            # a stroke in the file: no fill yet
    done = win.fill_layer(green, {"pattern": "cross", "spacing": 1.0, "angle": 0.0, "margin": 0.0})
    assert done and set(map(id, done)) == set(map(id, d.elements_of(green)))
    assert all(e.fill["pattern"] == "cross" for e in done) and green.fill["pattern"] == "cross"
    assert win.layer_list.item(d.layers.index(green)).text().endswith("Cross-hatch")
    # the other colours keep theirs
    pink = d.layers[1]
    assert {(e.fill or {}).get("pattern") for e in d.elements_of(pink)} <= {"lines", None}
    # removed, and undone
    win.fill_layer(green, {"pattern": None})
    assert all(e.fill is None for e in d.elements_of(green)) and green.fill is None
    win.undo()
    back = [layer for layer in win.design.layers if layer.id == green.id][0]     # undo gives copies
    assert back.fill["pattern"] == "cross" and all(e.fill["pattern"] == "cross"
                                                   for e in win.design.elements_of(back))


def test_a_fill_in_another_colour_goes_with_that_colour(win):
    """A black outline, a pink fill: the black job draws the outline only, the
    pink one the fill only; the sheet shows the fill in pink, and the Colours
    list counts the shape under both."""
    from vintyl.core.layers import Layer
    win.show()
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win._on_drawn("ellipse", QRectF(-100, -100, 60, 60))
    e = win.design.elements[0]
    pink = Layer("c1", "Pink", "#ec4899")
    win.design.layers.append(pink)
    e.fill = {"pattern": "lines", "spacing": 2.0, "angle": 0.0, "margin": 0.0, "layer": "c1"}
    win.refresh()
    jobs = dict((layer.id, job) for layer, job in win.layer_jobs())
    outline, fill = jobs["black"].knife_paths, jobs["c1"].knife_paths
    assert len(outline) == 1 and len(fill) > 5                    # the circle; its fill's lines
    item = [i for i in win.view._items if i.element is e][0]
    assert item.fill_color.name() != item.color.name()
    assert [win.layer_list.item(i).text() for i in range(2)] == ["Black  ·  1", "Pink  ·  1  ·  Lines"]


def test_moving_the_first_colour_keeps_the_elements_colours(win):
    """A shape drawn before the colours (it names no layer: the first one's)
    keeps its colour when the first colour moves down."""
    win._on_drawn("rectangle", QRectF(-300, -100, 60, 40))
    drawn = win.design.elements[0]
    win.import_svg(DEMO_SVG, "auto")
    d = win.design
    black = d.layer_of(drawn)
    assert black is d.layers[0]
    win.layer_list.setCurrentRow(0)
    win.move_layer(1)
    assert d.layer_of(drawn) is black and d.layers[1] is black


def test_an_svg_outline_with_a_fill_of_another_colour_opens_as_two_pens(win, tmp_path):
    """A pink square with a black stroke: its outline in black, its fill in
    pink; the pink (a fill only) is drawn before the black."""
    from tests.test_layers import OUTLINED
    p = tmp_path / "o.svg"
    p.write_text(OUTLINED)
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win.import_svg(str(p), "auto")
    d = win.design
    assert [layer.name for layer in d.layers] == ["Pink", "Black", "White"]
    pink, black = d.layers[0], d.layers[1]
    square = [e for e in d.elements if e.fill and e.fill.get("layer") == pink.id]
    assert len(square) == 1 and d.layer_of(square[0]) is black and square[0].name.endswith("filled with Pink")
    jobs = dict((layer.id, job) for layer, job in win.layer_jobs())
    assert set(jobs) == {pink.id, black.id, d.layers[2].id}
    # the window shows the pink as a colour of the file, with its one shape
    from vintyl.gui.colour_import import colour_dialog
    groups = __import__("vintyl.core.loaders", fromlist=["x"]).load_svg_colors(str(p))
    _e, candidates, chosen, merged, separate = win._colour_plan(groups)
    dlg = colour_dialog(win, groups, candidates, chosen, merged, separate, show=False)
    assert set(dlg.combos) == {"#000000", "#ec4899", "#ffffff"}


def test_a_colour_can_be_removed(win):
    """Remove this colour (the Colours list's right button): its elements go
    to the first other colour, the fills it drew to their shapes' colour;
    undone with Ctrl+Z; the last colour stays."""
    win.show()
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win.import_svg(DEMO_SVG, "auto")
    d = win.design
    assert win.layer_list.height() < 5 * win.layer_list.sizeHintForRow(0)     # 5 colours: 4 rows in sight
    pink, black = d.layers[1], d.layers[0]
    ring = d.elements_of([ly for ly in d.layers if ly.name == "Green"][0])[0]
    ring.fill = {"pattern": "lines", "spacing": 1.0, "angle": 0.0, "margin": 0.0, "layer": pink.id}
    pinks = d.elements_of(pink)
    menu = win.layer_context_menu(win.layer_list.visualItemRect(win.layer_list.item(1)).center(), show=False)
    assert [a.text() for a in menu.actions() if a.text()][-1] == "Remove this colour"
    assert win._layer() is pink
    assert win.remove_layer() is black
    assert pink not in d.layers and all(d.layer_of(e) is black for e in pinks) and "layer" not in ring.fill
    assert len(d.layers) == 4 and "Pink" not in [win.layer_list.item(i).text().split()[0] for i in range(4)]
    win.undo()
    assert [ly.name for ly in win.design.layers][1] == "Pink"
    # down to one colour: it stays
    while len(win.design.layers) > 1:
        win.remove_layer(win.design.layers[-1])
    assert win.remove_layer(win.design.layers[0]) is None and len(win.design.layers) == 1


def test_the_fill_in_a_new_colour_is_previewed_in_it(win, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog
    win.show()
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win._on_drawn("rectangle", QRectF(-120, -80, 100, 60))
    box = win.selected
    dlg = win._ask_fill([box], show=False)
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor("#22aa22")))
    dlg.colour.setCurrentIndex(dlg.colour.findData(win.NEW_COLOUR))
    item = lambda: [i for i in win.view._items if i.element is box][0]          # noqa: E731
    assert _wait_for(lambda: box.fill and box.fill.get("layer") and item().fill_color.name() == "#22aa22")
    dlg.previewer.wait()


def test_save_hpgl_writes_a_file_per_colour(win, tmp_path):
    win.import_svg(DEMO_SVG, "auto")
    first = win.save_cutter_file(str(tmp_path / "logo.hpgl"))
    jobs = win.layer_jobs()
    files = sorted(os.listdir(tmp_path))
    assert first.endswith("logo-1-%s.hpgl" % jobs[0][0].name) and len(files) == len(jobs)
    for n, (layer, job) in enumerate(jobs, 1):
        assert (tmp_path / ("logo-%d-%s.hpgl" % (n, layer.name.replace(" ", "_")))).read_text() == job.text
