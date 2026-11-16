"""
Tests of opening DXF drawings (the reader comes from K40 Whisperer through Kerfly).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

import pytest

from vintyl.core import curves
from vintyl.core.loaders import LoadCancelled, LoadError, load_dxf


def _dxf(entities, units=4):
    head = ["0", "SECTION", "2", "HEADER"]
    if units is not None:
        head += ["9", "$INSUNITS", "70", str(units)]
    head += ["0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    return "\n".join(head + entities + ["0", "ENDSEC", "0", "EOF"]) + "\n"


CIRCLE = ["0", "CIRCLE", "8", "0", "10", "50", "20", "20", "30", "0", "40", "10"]
SQUARE = ["0", "LWPOLYLINE", "8", "0", "90", "4", "70", "1",
          "10", "0", "20", "0", "10", "20", "20", "0", "10", "20", "20", "10", "10", "0", "20", "10"]
LINE = ["0", "LINE", "8", "0", "10", "0", "20", "30", "30", "0", "11", "30", "21", "30", "31", "0"]


def test_a_dxf_in_millimetres_keeps_its_sizes_and_closes_its_shapes(tmp_path):
    path = tmp_path / "parts.dxf"
    path.write_text(_dxf(CIRCLE + SQUARE + LINE))
    e = load_dxf(str(path))
    closed = [s for s in e.paths if s["closed"]]
    open_ = [s for s in e.paths if not s["closed"]]
    assert len(closed) == 2 and len(open_) == 1
    sizes = sorted((b[1] - b[0], b[3] - b[2]) for b in (curves.bounds([s]) for s in closed))
    # the square, the circle (r 10, straight pieces within 0.01 mm)
    assert sizes[0] == pytest.approx((20.0, 10.0)) and sizes[1] == pytest.approx((20.0, 20.0), abs=0.05)
    circle = max(closed, key=lambda s: len(s["nodes"]))
    pts = [(n[0], n[1]) for n in circle["nodes"]]
    assert all(abs(math.hypot(x - 50, y + 20) - 10) < 0.02 for x, y in pts)     # y turned down
    assert curves.bounds(open_)[1] - curves.bounds(open_)[0] == pytest.approx(30.0)


def test_inches_are_turned_into_millimetres(tmp_path):
    path = tmp_path / "inch.dxf"
    path.write_text(_dxf(LINE, units=1))
    e = load_dxf(str(path))
    xmin, xmax, _y0, _y1 = e.bounds
    assert xmax - xmin == pytest.approx(30 * 25.4)


def test_a_drawing_without_units_asks(tmp_path):
    path = tmp_path / "nounits.dxf"
    path.write_text(_dxf(LINE, units=None))
    asked = []
    e = load_dxf(str(path), lambda: asked.append(1) or "Centimeters")
    assert asked and e.bounds[1] - e.bounds[0] == pytest.approx(300.0)
    with pytest.raises(LoadCancelled):
        load_dxf(str(path), lambda: None)


def test_an_empty_or_missing_dxf_says_so(tmp_path):
    path = tmp_path / "empty.dxf"
    path.write_text(_dxf([]))
    with pytest.raises(LoadError, match="no visible shapes"):
        load_dxf(str(path))
    with pytest.raises(LoadError, match="Cannot open"):
        load_dxf(str(tmp_path / "nothing.dxf"))
