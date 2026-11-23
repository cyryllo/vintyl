"""
A picture drawn with a pen (vintyl.core.picture): waves, a spiral and
hatching follow the picture's light and dark and stay inside it.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math
import time

import pytest

from vintyl.core import picture
from vintyl.core.picture import Grey


def half_dark(width=40, height=20):
    """White on the left half, black on the right."""
    return Grey([[0.0 if x < width // 2 else 1.0 for x in range(width)] for _y in range(height)])


def inside(polys, w, h, room=0.0):
    return all(-room <= x <= w + room and -room <= y <= h + room for p in polys for x, y in p)


def test_a_grey_is_read_between_its_pixels_and_adjusted():
    g = Grey([[0.0, 1.0]])
    assert g.at(0.0, 0.5) == 0.0 and g.at(1.0, 0.5) == 1.0 and 0.4 < g.at(0.5, 0.5) < 0.6
    assert g.at(1.5, 0.5) == 0.0                                   # outside: white
    assert g.adjusted(invert=True).rows == [[1.0, 0.0]]
    assert g.adjusted(contrast=2.0).at(0.5, 0.5) == pytest.approx(0.5)
    assert g.adjusted(brightness=0.3).rows[0][1] == pytest.approx(0.7)
    with pytest.raises(ValueError):
        Grey([])


def test_waves_wobble_only_where_it_is_dark():
    g = half_dark()
    polys = picture.waves(g, 100.0, spacing=2.0)
    w, h = picture.size_of(g, 100.0)
    assert (w, h) == (100.0, 50.0) and len(polys) == 25            # a row every 2 mm
    assert inside(polys, w, h, room=1.0)                          # the wobble: half the spacing at most

    def spread(lo, hi):                                            # how far a row strays in x lo..hi
        ys = [y for p in polys[:1] for x, y in p if lo < x < hi]
        return max(ys) - min(ys) if ys else 0.0
    assert spread(5, 45) < 0.01 and spread(55, 95) > 1.5          # straight on white, waves on black
    # the rows go back and forth, so the next one starts where this one ended
    assert polys[0][0][0] < 1 and polys[1][0][0] > 99
    # the pen lifted on white
    lifted = picture.waves(g, 100.0, spacing=2.0, skip_light=0.1)
    assert all(min(x for x, _y in p) >= 49 for p in lifted)
    assert len(picture.waves(g, 100.0, spacing=2.0, joined=True)) == 1      # one line


def test_a_spiral_starts_in_the_middle_and_stays_in_the_picture():
    g = Grey([[0.6] * 30 for _ in range(30)])
    polys = picture.spiral(g, 60.0, spacing=3.0)
    assert inside(polys, 60.0, 60.0, room=1.6)
    x, y = polys[0][0]
    assert math.hypot(x - 30, y - 30) < 3                          # from the middle
    far = max(math.hypot(x - 30, y - 30) for p in polys for x, y in p)
    assert far > 29                                                # out to the edges


def test_hatching_has_more_directions_where_it_is_darker():
    def directions(value):
        polys = picture.hatching(Grey([[value] * 20 for _ in range(20)]), 40.0, spacing=2.0)
        return {round(math.degrees(math.atan2(p[-1][1] - p[0][1], p[-1][0] - p[0][0]))) % 180 for p in polys}
    assert directions(0.1) == set()
    assert directions(0.3) == {45} and directions(0.5) == {45, 135} and directions(0.9) == {45, 135, 0}
    polys = picture.hatching(half_dark(), 100.0, spacing=2.0)
    assert inside(polys, 100.0, 50.0) and all(max(x for x, _y in p) >= 49 for p in polys)


def test_every_style_is_quick_enough_for_a_live_preview():
    g = Grey([[(x + y) % 7 / 7.0 for x in range(150)] for y in range(100)])
    for style in picture.STYLES:
        t = time.perf_counter()
        polys = picture.draw(style, g, 150.0, spacing=1.5)
        assert polys and time.perf_counter() - t < 6.0, style
    with pytest.raises(ValueError):
        picture.draw("dots", g, 10.0)
