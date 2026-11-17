"""
Colour layers (vintyl.core.layers): colours, similar ones merged, their
names; layers in the design and in the project file.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import json

import pytest

from vintyl.core import project, shapes
from vintyl.core.design import Design, Element
from vintyl.core.layers import (Layer, color_name, default_layer, delta_e, merge_similar, new_id, parse_color)


def test_colours_are_read_and_compared_as_the_eye_sees_them():
    assert parse_color("#FF8000") == (255, 128, 0) and parse_color("00ff00") == (0, 255, 0)
    with pytest.raises(ValueError):
        parse_color("red")
    assert delta_e("#ff0000", "#ff0000") == 0
    assert delta_e("#ff0000", "#fa0505") < 5            # hardly another red
    assert delta_e("#ff0000", "#0000ff") > 100          # another colour


def test_similar_colours_are_merged_into_the_most_used():
    counts = {"#e11d48": 5, "#e0204a": 2, "#1f2430": 7, "#222632": 1, "#fde047": 3}
    groups = merge_similar(counts)
    assert [kept for kept, _members in groups] == ["#1f2430", "#e11d48", "#fde047"]
    assert dict(groups)["#e11d48"] == ["#e11d48", "#e0204a"]
    assert len(merge_similar(counts, limit=0.5)) == 5    # nothing is that close: all kept


@pytest.mark.parametrize("color,name", [("#000000", "Black"), ("#ffffff", "White"), ("#808080", "Grey"),
                                        ("#ff0000", "Red"), ("#ff8000", "Orange"), ("#ffd700", "Yellow"),
                                        ("#22aa22", "Green"), ("#38bdf8", "Light blue"), ("#1d4ed8", "Blue"),
                                        ("#7e22ce", "Purple"), ("#ec4899", "Pink"), ("#8b4513", "Brown"),
                                        ("#be185d", "Pink"), ("#1f2430", "Black")])
def test_a_colour_has_a_name_in_words(color, name):
    assert color_name(color) == name


def test_an_element_without_a_layer_is_in_the_first():
    d = Design()
    assert [layer.id for layer in d.layers] == ["black"]
    red = Layer("c1", "Red", "#ff0000")
    d.layers.append(red)
    a = Element("a", shapes.rounded_rectangle(-30, -30, -10, -10, 0.0))
    b = Element("b", shapes.ellipse(-60, -60, -40, -40), layer="c1")
    gone = Element("c", shapes.ellipse(-90, -60, -70, -40), layer="nothing")
    d.elements += [a, b, gone]
    assert d.layer_of(a).id == "black" and d.layer_of(b) is red and d.layer_of(gone).id == "black"
    assert d.elements_of(red) == [b] and b.copy().layer == "c1"
    # one layer's shapes alone, for one pen (or one colour of vinyl)
    polys, groups = d.material_paths(layer=red)
    assert groups and set(groups) == {1}
    assert new_id(d.layers) == "c2"


def test_layers_are_saved_and_read_back(tmp_path):
    d = Design()
    d.layers.append(Layer("c1", "Red", "#ff0000", enabled=False, pen_width_mm=0.8, pen_place="outside",
                          fill={"pattern": "cross", "spacing": 1.0, "angle": 45.0, "margin": 0.0}))
    d.elements.append(Element("b", shapes.ellipse(-60, -60, -40, -40), layer="c1"))
    path = str(tmp_path / "p.vintyl")
    project.save(path, d)
    again, _settings = project.load(path)
    red = again.layers[1]
    assert (red.id, red.name, red.color, red.enabled, red.pen_width_mm, red.pen_place) == \
        ("c1", "Red", "#ff0000", False, 0.8, "outside")
    assert red.fill["pattern"] == "cross" and again.elements[0].layer == "c1"


def test_a_project_without_layers_opens_with_one_black_layer(tmp_path):
    data = project.to_dict(Design())
    del data["layers"]
    for e in data["elements"]:
        e.pop("layer", None)
    data["elements"].append({"name": "x", "paths": shapes.ellipse(-60, -60, -40, -40)})
    path = tmp_path / "old.vintyl"
    path.write_text(json.dumps(data))
    d, _s = project.load(str(path))
    assert [layer.id for layer in d.layers] == [default_layer().id] and d.layer_of(d.elements[0]).id == "black"


def test_a_damaged_layer_says_so(tmp_path):
    data = project.to_dict(Design())
    data["layers"] = [{"id": "a", "color": "red"}]
    path = tmp_path / "bad.vintyl"
    path.write_text(json.dumps(data))
    with pytest.raises(project.ProjectError, match="colour layer"):
        project.load(str(path))
