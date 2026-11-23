"""
Trace (vintyl.core.trace, from Kerfly): the dark areas of a picture become
closed outlines in mm, holes too; specks are dropped.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from vintyl.core import curves
from vintyl.core.trace import trace


def picture(w, h, dark):
    """Rows of lightness: 0 where dark(x, y), else 255."""
    return [bytes(0 if dark(x, y) else 255 for x in range(w)) for y in range(h)]


def test_a_dark_square_becomes_its_outline_in_mm():
    rows = picture(100, 60, lambda x, y: 20 <= x < 60 and 10 <= y < 50)
    subs = trace(rows, smooth=False, mm_per_px=0.5)
    assert len(subs) == 1 and subs[0]["closed"]
    x0, x1, y0, y1 = curves.bounds(subs)
    assert (x0, x1, y0, y1) == (10.0, 30.0, 5.0, 25.0)            # 40 px = 20 mm, at 0.5 mm a pixel
    assert len(subs[0]["nodes"]) == 4                              # a square: four corners


def test_a_ring_has_its_hole_and_specks_go():
    ring = lambda x, y: 100 <= (x - 30) ** 2 + (y - 30) ** 2 <= 400   # noqa: E731
    rows = picture(80, 60, lambda x, y: ring(x, y) or (69 <= x < 72 and 4 <= y < 7))
    subs = trace(rows, specks=16)
    assert len(subs) == 2                                          # outside and hole; the 3 x 3 px speck gone
    assert len(trace(rows, specks=4)) == 3
    # smoothed: curves, inside the ring's box
    assert any(n[4] is not None for sub in subs for n in sub["nodes"])
    x0, x1, y0, y1 = curves.bounds(subs)
    assert 9 < x0 < 11 and 49 < x1 < 51


def test_invert_and_threshold():
    grey = [bytes([100] * 20) for _ in range(20)]                  # mid grey all over
    assert len(trace(grey, threshold=128)) == 1 and trace(grey, threshold=90) == []
    assert trace(grey, threshold=128, invert=True) == []
