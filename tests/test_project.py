"""
Tests of the project files (.vintyl).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import json

import pytest

from vintyl.core import project, ready, shapes
from vintyl.core.design import Design, Element


def test_round_trip_keeps_everything(tmp_path):
    d = Design()
    d.elements.append(Element("Box", shapes.rectangle(-50, -40, -10, -10), True, "", None, "g1"))
    d.elements.append(Element("Heart", ready.make("heart"), False, "/tmp/x.svg",
                              {"kind": "ready", "shape": "heart", "width": 60.0}, "g1"))
    path = str(tmp_path / "a.vintyl")
    project.save(path, d, {"profile": "vevor-ki-375a", "knife_offset_mm": 0.25})
    d2, st = project.load(path)
    assert [(e.name, e.cut, e.source, e.spec, e.group) for e in d2.elements] == \
        [(e.name, e.cut, e.source, e.spec, e.group) for e in d.elements]
    assert d2.elements[1].paths == d.elements[1].paths              # the curves, handles too
    assert st == {"profile": "vevor-ki-375a", "knife_offset_mm": 0.25}
    assert not (tmp_path / "a.vintyl.tmp").exists()


@pytest.mark.parametrize("content, words", [
    ("not json at all", "damaged"),
    (json.dumps({"format": "kerfly"}), "not a Vintyl project"),
    (json.dumps({"format": "vintyl", "version": 99}), "newer Vintyl"),
    (json.dumps({"format": "vintyl", "version": 1, "elements": [{"name": "x", "paths": [{"nodes": [[1]]}]}]}),
     "damaged"),
])
def test_bad_files_say_what_is_wrong(tmp_path, content, words):
    path = tmp_path / "bad.vintyl"
    path.write_text(content)
    with pytest.raises(project.ProjectError, match=words):
        project.load(str(path))
