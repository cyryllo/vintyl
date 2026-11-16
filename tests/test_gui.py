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
  <circle cx="45" cy="20" r="8" fill="none" stroke="#123456"/>
  <rect x="0" y="0" width="5" height="5" fill="none" stroke="none"/>
  <rect x="50" y="30" width="5" height="5" fill="#000" style="display:none"/>
</svg>
"""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def messages(monkeypatch):
    """Message boxes wait for a click, which never comes offscreen: record them instead."""
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text, *a: shown.append(text))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
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
    # the panel shows the profile's knife values from the start
    assert win.knife.value() == pytest.approx(0.25) and win.overcut.value() == pytest.approx(0.5)


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
    win.knife.setValue(0)           # a pen: no knife offset, no overcut
    win.overcut.setValue(0)
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
    assert win.job_profile().speed_cm_s is None
    # both built-in cutters take speed and force from their panel only (checked 16.11.2026)
    assert not win.profile.send_speed_force
    assert win.speed_label.text() == "Speed on the panel" and not win.force.isVisibleTo(win)
    win.speed.setValue(20)
    assert "VS" not in win.build().text                # not sent ...
    assert "min at 20 cm/s" in win.job_label.text()     # ... but used for the time estimate
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
    win.knife.setValue(0.3)                       # a change redraws it, no stale items
    assert len(win.view._knife_items) == 2 + len(win.last_job.knife_paths)
    win.opt_x.setValue(50)                        # so does a move (the scene is rebuilt)
    assert len(win.view._knife_items) == 2 + len(win.last_job.knife_paths)
    win.act_knife.setChecked(False)
    assert win.view._knife_items == []


def test_knife_values_reach_the_job(win, svg_file):
    win.import_svg(svg_file)
    win.knife.setValue(0)
    win.overcut.setValue(0)
    plain = win.build().text
    win.knife.setValue(0.25)
    win.overcut.setValue(0.5)
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
    win.port_box.setEditText(fifo)
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
    win.port_box.setEditText(str(tmp_path / "lp9"))
    w = win.start()
    assert w.wait(5000)
    QApplication.processEvents()
    assert messages and "not there" in messages[-1]
    assert win.btn_start.isEnabled()



def test_what_is_on_screen_is_cut_the_same_way_round(win, tmp_path):
    """The view is the cutter seen from the front: a shape drawn up and to the
    left of the origin is cut further along (X) and further across (Y)."""
    win.knife.setValue(0)
    win.overcut.setValue(0)
    # a 10 mm line going UP the screen, 30 mm left of the origin, from 20 to 30 mm up
    win._on_line_drawn(QPointF(-30, -20), QPointF(-30, -30))
    text = win.build().text
    assert "PU800,1200;PD1200,1200;" in text          # X 20 -> 30 mm, Y 30 mm
    # the material: an upright sheet (at least 500 mm and 1.414 x the width), longer when needed
    assert win.view.length_mm == pytest.approx(max(500.0, 1.414 * win.profile.width_mm))
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
    assert win.show_category("text") is None and win.view.tool == "text"
    win.set_tool("select")
    assert win.category_buttons["pick"].isChecked()


def test_ready_shapes_are_offered_and_inserted(win):
    from vintyl.core import ready
    popup = win.show_category("ready")
    assert len(popup.findChildren(QToolButton)) == len(ready.READY) == 8
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


def test_the_last_cutter_and_its_port_are_remembered(app, tmp_path, monkeypatch):
    monkeypatch.setenv("VINTYL_SETTINGS", str(tmp_path / "remember.ini"))
    w = MainWindow()
    assert w.profile.name == "Seiki SK-870T"              # nothing remembered yet: the first
    w.profile_box.setCurrentIndex(w.profile_names.index("vevor-ki-375a"))
    w.port_box.setEditText("/dev/usb/lp3")
    w.settings.sync()
    w.close()
    w2 = MainWindow()                                     # the next start
    assert w2.profile.name == "VEVOR KI-375A"
    assert w2.port_box.currentText() == "/dev/usb/lp3"
    w2.close()


def test_the_sheet_stands_upright_for_every_cutter_and_grows(win):
    for name in win.profile_names:
        win.profile_box.setCurrentIndex(win.profile_names.index(name))
        w = win.profile.width_mm
        assert win.view.length_mm >= max(500.0, 1.4 * w)        # taller than wide
    win._on_drawn("rectangle", QRectF(-60, -1500, 20, 20))      # something higher up
    assert win.view.length_mm >= 1500.0


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
