"""
Tests of the materials (vintyl.core.material).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import dataclasses

import pytest

from vintyl.core import material as mat


def test_built_in_materials_have_starting_values_for_the_xili_cutters():
    entries = {e["id"]: e["material"] for e in mat.catalogue()}
    assert set(entries) >= {"vinyl", "htv", "reflective", "paper", "card"}
    assert entries["htv"].mirror and entries["htv"].tool == "knife"
    assert entries["paper"].tool == "pen" and entries["card"].tool == "pen"
    xili = {"seiki-sk-870t", "vevor-870", "vevor-ki-375a", "xili-usb"}
    for mid, m in entries.items():
        # force and speed for every cutter with the XILI board, inside its range
        # (10-500 g, 1-80 cm/s); offsets stay the cutter's own
        assert set(m.per_cutter) == xili and m.knife_offset_mm is None, mid
        for force, speed in (m.for_cutter(pid) for pid in xili):
            assert 10 <= force <= 500 and 1 <= speed <= 80, mid
    # VEVOR's manual: 100 g, 300 mm/s; the Seiki user: 70-90 g; pens: the owner's 70 g
    assert entries["vinyl"].for_cutter("vevor-ki-375a") == (100.0, 30.0)
    assert entries["vinyl"].for_cutter("seiki-sk-870t") == (80.0, 30.0)
    assert entries["paper"].for_cutter("seiki-sk-870t") == (70.0, 30.0)
    tools = [e["material"].tool for e in mat.catalogue()]
    assert tools == sorted(tools, key=lambda t: t != "knife")         # knife ones first


def test_a_material_is_saved_and_read_back_with_its_values_per_cutter(tmp_path, monkeypatch):
    monkeypatch.setenv("VINTYL_MATERIALS", str(tmp_path / "materials"))
    m = mat.Material(name="Oracal 641", tool="knife", blade="45", knife_offset_mm=0.3, overcut_mm=None,
                     per_cutter={"vevor-ki-375a": {"force_g": 90.0, "speed_cm_s": 30.0}},
                     weed_frame=True, note='Peel "slowly".\nThen check.')
    mid = mat.new_id(m.name)
    assert mid == "oracal-641"
    mat.save_user(mid, m)
    back = {e["id"]: e for e in mat.catalogue()}[mid]
    assert back["material"] == m and not back["builtin"]
    assert back["material"].for_cutter("vevor-ki-375a") == (90.0, 30.0)
    assert back["material"].for_cutter("seiki-sk-870t") == (None, None)
    mat.delete_user(mid)
    assert mid not in {e["id"] for e in mat.catalogue()}


def test_a_changed_built_in_material_is_the_users_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("VINTYL_MATERIALS", str(tmp_path / "materials"))
    vinyl = mat.load_builtin("vinyl")
    mat.save_user("vinyl", dataclasses.replace(vinyl, per_cutter={"x": {"force_g": 80.0}}))
    e = {e["id"]: e for e in mat.catalogue()}["vinyl"]
    assert e["changed"] and e["material"].for_cutter("x") == (80.0, None)
    mat.delete_user("vinyl")
    assert not {e["id"]: e for e in mat.catalogue()}["vinyl"]["changed"]


@pytest.mark.parametrize("bad", [{"tool": "laser"}, {"blade": "90"}, {"knife_offset_mm": -1.0},
                                 {"per_cutter": {"a": {"force_g": 0}}}, {"per_cutter": {"a": {"push": 1}}},
                                 {"name": " "}])
def test_a_wrong_material_is_refused(bad):
    with pytest.raises(mat.MaterialError):
        mat.from_dict(dict({"name": "M"}, **bad))
