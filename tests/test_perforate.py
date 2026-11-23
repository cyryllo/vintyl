"""
Perforated cuts (vintyl.core.perforate): a line cut in dashes; an element
perforated goes to the cutter so, and its project keeps it.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

import pytest

from vintyl.core import perforate, project, shapes
from vintyl.core.design import Design, Element


def length(p):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(p, p[1:]))


def test_a_line_is_cut_in_dashes():
    d = perforate.dashes([(0, 0), (10, 0)], 3.0, 1.0)
    assert [round(length(p), 6) for p in d] == [3.0, 3.0, 2.0]       # 3 cut, 1 gap, 3, 1, then the last 2
    assert d[0][0] == (0, 0) and d[1][0] == (4.0, 0.0) and d[2][-1] == (10.0, 0.0)
    # round a corner: the dash goes on round it
    d = perforate.dashes([(0, 0), (2, 0), (2, 2)], 3.0, 1.0)
    assert len(d) == 1 and d[0] == [(0, 0), (2, 0), (2.0, 1.0)]


def test_a_perforated_element_goes_to_the_cutter_in_dashes(tmp_path):
    d = Design()
    e = Element("box", shapes.rounded_rectangle(-60, -60, -20, -20, 0.0), perforate={"cut": 3.0, "gap": 1.0})
    d.elements.append(e)
    polys, groups = d.material_paths()
    total = sum(length(p) for p in polys)
    assert len(polys) == 40 and total == pytest.approx(120.0, abs=0.01)      # 160 mm round: 40 x 3 mm
    assert set(groups) == {0}
    path = str(tmp_path / "p.vintyl")
    project.save(path, d)
    again, _s = project.load(path)
    assert again.elements[0].perforate == {"cut": 3.0, "gap": 1.0} and again.elements[0].copy().perforate
    with pytest.raises(ValueError):
        perforate.valid({"cut": 0.0, "gap": 1.0})
