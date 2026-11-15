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
from PySide6.QtWidgets import QApplication

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
    assert xmin == pytest.approx(10.0) and ymax == pytest.approx(-10.0)   # 10 mm from the origin
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
    # view mm: x 20..40 along, y -50..-30 (y down) = 30..50 mm across
    win.knife.setValue(0)           # a pen: no knife offset, no overcut
    win.overcut.setValue(0)
    win._on_drawn("rectangle", QRectF(QPointF(20, -50), QPointF(40, -30)))
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
    win.opt_x.setValue(100.0)
    win.opt_y.setValue(50.0)
    xmin, xmax, ymin, ymax = e.bounds
    assert xmin == pytest.approx(100.0) and -ymax == pytest.approx(50.0)
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


def test_speed_from_the_panel_or_set(win, svg_file):
    win.import_svg(svg_file)
    assert win.job_profile().speed_cm_s is None
    win.speed.setValue(20)
    assert "VS20;" in win.build().text
    assert "min at 20 cm/s" in win.job_label.text()


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
    win.btn_preview.setChecked(True)
    assert win.act_knife.isChecked()
    n_paths = len(win.last_job.knife_paths)
    # one item for the cuts, one for the travels, one numbered dot per path
    assert len(win.view._knife_items) == 2 + n_paths
    win.knife.setValue(0.3)                       # a change redraws it, no stale items
    assert len(win.view._knife_items) == 2 + len(win.last_job.knife_paths)
    win.opt_x.setValue(50)                        # so does a move (the scene is rebuilt)
    assert len(win.view._knife_items) == 2 + len(win.last_job.knife_paths)
    win.act_knife.setChecked(False)
    assert win.view._knife_items == [] and not win.btn_preview.isChecked()


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
    x0 = e.bounds[0]
    win.opt_x.setValue(x0 + 30)
    assert win.design.elements[0].bounds[0] == pytest.approx(x0 + 30)
    win.undo()
    assert win.design.elements[0].bounds[0] == pytest.approx(x0)
    win.redo()
    assert win.design.elements[0].bounds[0] == pytest.approx(x0 + 30)
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
