"""
Tests of cutting order, overcut and knife compensation (plan step 3).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

import pytest

from vintyl.core import knife
from vintyl.core.job import JobError, build_job
from vintyl.core.profile import Profile


def square(x0, y0, side=20.0):
    return [(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side), (x0, y0)]


def length(poly):
    return sum(math.dist(a, b) for a, b in zip(poly, poly[1:]))


# ---- order -------------------------------------------------------------------------

def test_hole_before_its_outline():
    outer, hole = square(10, 10, 40), square(25, 25, 10)
    out = knife.order([outer, hole])
    assert set(out[0]) == set(hole) and set(out[1]) == set(outer)


def test_nested_three_deep_innermost_first():
    a, b, c = square(0, 0, 60), square(10, 10, 40), square(20, 20, 20)
    out = knife.order([a, b, c])
    assert [set(p) for p in out] == [set(c), set(b), set(a)]


def test_letter_o_counter_before_the_outside():
    """Like the letter O: an inner ring (the counter) inside an outer ring."""
    def ring(r, n=36):
        pts = [(50 + r * math.cos(2 * math.pi * k / n), 50 + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
        return pts + [pts[0]]
    out = knife.order([ring(20), ring(12)])
    assert max(math.dist(p, (50, 50)) for p in out[0]) < 13


def test_element_order_kept_where_nothing_is_inside():
    far, near = square(200, 10), square(5, 5)
    # element 0 is far away, element 1 near the origin: the user's order wins
    out = knife.order([far, near], groups=[0, 1])
    assert set(out[0]) == set(far)
    # in one element, the nearer one goes first
    out = knife.order([far, near], groups=[0, 0])
    assert set(out[0]) == set(near)


def test_hole_in_a_later_element_still_cut_first():
    outer, hole = square(10, 10, 40), square(25, 25, 10)
    out = knife.order([outer, hole], groups=[0, 1])
    assert set(out[0]) == set(hole)


def test_closed_shape_starts_at_its_nearest_corner_open_line_at_its_nearest_end():
    out = knife.order([square(10, 10)], start=(31, 31))
    assert out[0][0] == (30, 30) and out[0][-1] == (30, 30) and len(out[0]) == 5
    out = knife.order([[(0, 5), (50, 5)]], start=(60, 5))
    assert out[0] == [(50, 5), (0, 5)]


def test_identical_outlines_do_not_deadlock():
    out = knife.order([square(0, 0), square(0, 0)])
    assert len(out) == 2


# ---- overcut -----------------------------------------------------------------------

def test_overcut_follows_the_outline():
    out = knife.overcut(square(0, 0), 0.5)
    assert out[:5] == square(0, 0)
    assert out[5] == pytest.approx((0.5, 0.0))         # along the first side, not off the shape


def test_overcut_round_a_corner():
    out = knife.overcut(square(0, 0, 1.0), 1.5)
    assert out[-2] == (1.0, 0.0) and out[-1] == pytest.approx((1.0, 0.5))


def test_no_overcut_on_open_lines_or_when_zero():
    line = [(0, 0), (10, 0)]
    assert knife.overcut(line, 0.5) == line
    assert knife.overcut(square(0, 0), 0) == square(0, 0)


# ---- knife compensation --------------------------------------------------------

def test_offset_zero_is_a_pen():
    polys = [square(0, 0), [(1, 1), (5, 9)]]
    assert knife.compensate(polys, 0.0) == polys


def test_straight_line_is_pushed_forward_by_the_offset():
    out = knife.compensate([[(0, 0), (10, 0)]], 0.25)
    assert out == [[(0.25, 0.0), (10.25, 0.0)]]


def test_square_corners_get_a_swivel_arc_round_the_corner_point():
    r = 0.25
    out = knife.compensate([square(0, 0)], r)[0]
    # every point is the offset away from a corner point or on the pushed sides
    corners = [(0, 0), (20, 0), (20, 20), (0, 20)]
    for p in out:
        near = min(math.dist(p, c) for c in corners)
        on_side = any(abs(p[1] - y) < 1e-9 for y in (0.0, 20.0)) or any(abs(p[0] - x) < 1e-9 for x in (0.0, 20.0))
        assert abs(near - r) < 1e-6 or on_side
    # the arc at (20, 0) goes from heading +x to heading +y: from (20.25, 0) to (20, 0.25)
    i = out.index((20.25, 0.0))
    assert out[i + 1:i + 10][-1] == pytest.approx((20.0, 0.25))
    assert all(abs(math.dist(p, (20, 0)) - r) < 1e-9 for p in out[i:i + 10])


def test_gentle_curves_get_no_arcs():
    """Turns smaller than corner_deg (a flattened curve) are just pushed forward."""
    pts = [(math.cos(math.radians(a)) * 50, math.sin(math.radians(a)) * 50) for a in range(0, 91, 3)]
    # the blade already points the way the arc starts (+y), so no swivel at the start either
    out = knife.compensate([pts], 0.25, corner_deg=5.0, heading=(0.0, 1.0))[0]
    assert len(out) == len(pts)
    # from the default heading (+x) the blade first turns on the spot: an arc at the start
    assert len(knife.compensate([pts], 0.25, corner_deg=5.0)[0]) > len(pts)


def test_heading_carries_over_to_the_next_path():
    out = knife.compensate([[(0, 0), (0, 10)], [(5, 10), (5, 20)]], 0.25)
    # the second path starts with the blade still heading +y (from the first)
    assert out[1][0] == pytest.approx((5.0, 10.25))


# ---- in the job ----------------------------------------------------------------------

P = Profile(width_mm=200, knife_offset_mm=0.25, overcut_mm=0.5)


def test_overcut_is_kept_with_knife_compensation():
    """Inkcut drops the overcut when the knife offset is on; Vintyl must not."""
    plain = build_job([square(10, 10)], Profile(width_mm=200, knife_offset_mm=0.25)).knife_paths[0]
    both = build_job([square(10, 10)], P).knife_paths[0]
    # 0.5 mm further along the first side, plus the blade turning once more
    # at the start corner (a quarter circle of the offset's radius)
    extra = 0.5 + 0.25 * math.pi / 2
    assert length(both) == pytest.approx(length(plain) + extra, abs=0.01)
    assert both[-1] == pytest.approx((10.75, 10.0))     # ends 0.5 mm past the start, pushed 0.25


def test_travel_home_is_not_compensated():
    text = build_job([square(10, 10)], P).text
    assert text.endswith("PU0,0;")


def test_knife_needs_room_at_the_edge():
    with pytest.raises(JobError, match="need 0.75 mm of room"):
        build_job([square(0, 10)], P)
    build_job([square(1, 10)], P)


def test_inside_first_in_the_job():
    outer, hole = square(10, 10, 40), square(25, 25, 10)
    job = build_job([outer, hole], Profile(width_mm=200), inside_first=True)
    assert set(job.knife_paths[0]) == set(hole)
    job = build_job([outer, hole], Profile(width_mm=200), inside_first=False)
    assert set(job.knife_paths[0]) == set(outer)
