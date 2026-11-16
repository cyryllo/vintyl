"""
Tests of drawing with a pen: where the stroke lies against the line, and
the fill patterns (copied from Kerfly).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import pytest

from vintyl.core import pen, project
from vintyl.core.design import Design, Element
from vintyl.core.shapes import rectangle

SQUARE = [(0, 0), (20, 0), (20, 20), (0, 20), (0, 0)]
LINE = [(0, 30), (20, 30)]


def _size(poly):
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return max(xs) - min(xs), max(ys) - min(ys)


def test_on_the_line_changes_nothing():
    polys, groups = pen.place([SQUARE, LINE], [0, 0], 0.5, "on")
    assert polys == [SQUARE, LINE] and groups == [0, 0]


def test_outside_and_inside_move_closed_shapes_half_the_pen_width():
    pytest.importorskip("pyclipper")
    out, g = pen.place([SQUARE, LINE], [0, 0], 1.0, "outside")
    square = [p for p in out if len(p) > 2]
    assert _size(square[0])[0] == pytest.approx(21.0, abs=0.01)      # 0.5 mm all round
    assert LINE in out                                                  # open lines stay on the line
    inside, _g = pen.place([SQUARE], [0], 1.0, "inside")
    assert _size(inside[0])[0] == pytest.approx(19.0, abs=0.01)


def test_merge_puts_each_fill_before_its_outline_in_element_order():
    polys, groups = pen.merge([["f1"], ["f0"]], [1, 0], [["o0"], ["o1"]], [0, 1])
    assert polys == [["f0"], ["o0"], ["f1"], ["o1"]] and groups == [0, 0, 1, 1]


def test_an_element_fill_gives_lines_inside_and_survives_a_project(tmp_path):
    e = Element("Box", rectangle(-50, -50, -30, -40),
                fill={"pattern": "lines", "spacing": 1.0, "angle": 0.0, "margin": 0.0})
    lines = e.fill_lines()
    assert len(lines) == 10                                           # 10 mm tall, every 1 mm
    for line in lines:
        for x, y in line:
            assert -50 - 1e-6 <= x <= -30 + 1e-6 and -50 <= y <= -40
    d = Design([e, Element("Plain", rectangle(0, 0, 5, 5))])
    fills, groups = d.material_fills()
    assert len(fills) == 10 and set(groups) == {0}
    path = str(tmp_path / "a.vintyl")
    project.save(path, d)
    back, _st = project.load(path)
    assert back.elements[0].fill == e.fill and back.elements[1].fill is None


@pytest.mark.parametrize("pattern", ["lines", "cross", "waves", "zigzag", "circles", "honeycomb",
                                     "diamonds", "bricks", "concentric"])
def test_every_fill_pattern_stays_inside(pattern):
    if pattern == "concentric":
        pytest.importorskip("pyclipper")
    e = Element("Box", rectangle(0, 0, 30, 20), fill={"pattern": pattern, "spacing": 3.0, "angle": 30.0,
                                                       "margin": 0.5})
    lines = e.fill_lines()
    assert lines
    for line in lines:
        for x, y in line:
            assert -0.01 <= x <= 30.01 and -0.01 <= y <= 20.01


def test_a_damaged_fill_is_refused():
    data = project.to_dict(Design([Element("A", rectangle(0, 0, 5, 5))]))
    data["elements"][0]["fill"] = {"pattern": "nonsense", "spacing": 1}
    with pytest.raises(project.ProjectError):
        project.from_dict(data)


@pytest.mark.parametrize("code", __import__("vintyl.core.tile", fromlist=["MOTIFS"]).MOTIFS)
def test_every_motif_tiles_whole_inside_with_its_margin(code):
    from vintyl.core import curves, tile
    from vintyl.core.knife import point_in_polygon
    circle = __import__("vintyl.core.shapes", fromlist=["ellipse"]).ellipse(0, 0, 80, 80)
    paths, n = tile.tile(circle, tile.motif(code), 6.0, 2.0, True, 1.5)
    assert n > 10
    ring = curves.flatten(circle, 0.01)[0]
    for poly in curves.flatten(paths, 0.05):
        for x, y in poly:
            assert point_in_polygon((x, y), ring)
            assert (x - 40) ** 2 + (y - 40) ** 2 <= (40 - 1.5 + 0.05) ** 2      # the margin kept


def test_a_hole_in_the_outline_stays_free():
    from vintyl.core import curves, shapes, tile
    outline = shapes.rectangle(0, 0, 60, 60) + shapes.rectangle(20, 20, 40, 40)
    paths, n = tile.tile(outline, tile.motif("circle"), 4.0, 2.0, False, 1.0)
    assert n > 0
    for poly in curves.flatten(paths, 0.05):
        for x, y in poly:
            assert not (19.0 < x < 41.0 and 19.0 < y < 41.0)
