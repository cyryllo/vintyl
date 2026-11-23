"""
Nesting on a strip of material (vinyl.core.nesting): parts side by side
across, as short a strip as can be, never overlapping, turned when it
helps, a part too wide left out.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import random

from vintyl.core.nesting import pack_strip


def boxes(sizes, places, spacing=0.0):
    out = []
    for (w, h), p in zip(sizes, places):
        if p is None:
            continue
        x, y, turned = p
        if turned:
            w, h = h, w
        out.append((x, y, x + w + spacing, y + h + spacing))
    return out


def overlap(a, b):
    return a[0] < b[2] - 1e-9 and b[0] < a[2] - 1e-9 and a[1] < b[3] - 1e-9 and b[1] < a[3] - 1e-9


def test_parts_go_side_by_side_across_the_strip():
    sizes = [(100, 50)] * 6
    places, length = pack_strip(sizes, 300.0, 0.0, turn=False)
    assert length == 100.0                                     # three across, two rows
    assert all(not overlap(a, b) for i, a in enumerate(boxes(sizes, places)) for b in boxes(sizes, places)[i + 1:])
    assert all(x + 100 <= 300 + 1e-9 for x, _y, _t in places)


def test_turning_makes_the_strip_shorter():
    sizes = [(40, 100)] * 4                                  # tall parts on a 100 mm wide strip
    _p, straight = pack_strip(sizes, 100.0, 0.0, turn=False)
    places, turned = pack_strip(sizes, 100.0, 0.0, turn=True)
    assert straight == 200.0 and turned < straight and any(t for _x, _y, t in places)


def test_the_spacing_is_kept_and_a_part_too_wide_is_left_out():
    sizes = [(50, 50), (50, 50), (500, 200)]
    places, length = pack_strip(sizes, 104.0, 3.0)
    assert places[2] is None                                 # wider than the strip, also turned
    a, b = boxes(sizes[:2], places[:2], 3.0)
    assert not overlap(a, b) and length == 50.0              # both across, 3 mm apart
    places, length = pack_strip([(500, 20)], 104.0, 3.0)
    assert places[0][2] and length == 500.0                  # turned it fits: 20 across, 500 along


def test_many_random_parts_never_overlap():
    rnd = random.Random(7)
    sizes = [(rnd.uniform(5, 80), rnd.uniform(5, 80)) for _ in range(60)]
    places, length = pack_strip(sizes, 300.0, 2.0)
    bs = boxes(sizes, places, 2.0)
    assert len(bs) == 60
    assert all(not overlap(a, b) for i, a in enumerate(bs) for b in bs[i + 1:])
    assert all(b[2] <= 302.0 + 1e-6 for b in bs) and max(b[3] for b in bs) - 2.0 == length
    # tighter than a shelf of the parts one after another
    assert length < sum(h for _w, h in sizes) / 3
