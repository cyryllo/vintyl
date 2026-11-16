"""
Tests of the cutter core (plan step 1): profiles, HPGL / DMPL, the job
checks and the file output. No cutter and no GUI toolkit needed.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math
import os
import re
import subprocess
import sys

import pytest

from vintyl.core import profile as prof
from vintyl.core.job import JobError, build_job
from vintyl.core.profile import Profile, ProfileError

HERE = os.path.dirname(os.path.abspath(__file__))


def square(x0, y0, side=20.0):
    """A closed square, counter-clockwise from its lower-left corner."""
    return [(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side), (x0, y0)]


def commands(text):
    return [c for c in text.split(";") if c]


# ---- units and HPGL ------------------------------------------------------------

def test_20_mm_is_800_hpgl_units():
    job = build_job([square(10, 10)], Profile(width_mm=100))
    assert job.text == ("IN;SP1;PU400,400;PD1200,400;PD1200,1200;PD400,1200;PD400,400;"
                        "PU400,400;PU0,0;")
    assert job.cut_mm == pytest.approx(80.0)
    assert job.paths == 1


def test_same_as_the_monday_test_file():
    """The A4 test square (tests/a4) is what the generator makes for it."""
    mark = [(10, 35), (20, 35)]           # the 10 mm X mark above the square
    job = build_job([square(10, 10), mark], Profile(width_mm=100))
    with open(os.path.join(HERE, "a4", "kwadrat_20mm.hpgl")) as f:
        assert job.text == f.read()


def test_knife_up_before_the_travel_home_and_at_the_end():
    for paths in ([square(5, 5)], [[(1, 1), (30, 1)]], [square(5, 5), [(40, 2), (50, 9)]]):
        cmds = commands(build_job(paths, Profile(width_mm=100)).text)
        assert cmds[-1] == "PU0,0"
        # the command before the travel home lifts the knife where it is
        assert cmds[-2].startswith("PU") and cmds[-3].startswith("PD")
        assert cmds[-2][2:] == cmds[-3][2:]


def test_knife_lifted_in_place_before_each_travel():
    """Between paths: lift where the knife stands, then travel to the next start."""
    cmds = commands(build_job([square(5, 5), square(40, 5)], Profile(width_mm=100)).text)
    i = cmds.index("PU1600,200")                  # the start of the second square
    assert cmds[i - 2] == "PD200,200"             # end of the first square
    assert cmds[i - 1] == "PU200,200"             # lifted in place
    # no cutting move ever directly follows another path's end without a lift
    for a, b in zip(cmds, cmds[1:]):
        if a.startswith("PD") and b.startswith("PU"):
            assert a[2:] == b[2:]


def test_speed_and_force_only_when_set():
    assert "VS" not in build_job([square(5, 5)], Profile(width_mm=100)).text
    text = build_job([square(5, 5)], Profile(width_mm=100, speed_cm_s=20, force_g=80)).text
    assert text.startswith("IN;SP1;VS20;FS80;PU")
    text = build_job([square(5, 5)], Profile(width_mm=100, speed_cm_s=12.5)).text
    assert "VS12.5;" in text


def test_no_negative_numbers_ever_sent():
    text = build_job([square(0, 0), [(0, 0), (99.99, 0)]], Profile(width_mm=100)).text
    assert not re.search(r"-\d", text)


def test_points_closer_than_one_step_are_merged():
    job = build_job([[(1, 1), (1.001, 1.001), (2, 1)]], Profile(width_mm=100))
    assert job.text == "IN;SP1;PU40,40;PD80,40;PU80,40;PU0,0;"


# ---- DMPL ----------------------------------------------------------------------

def test_dmpl_mode_3_uses_the_profile_units():
    p = Profile(width_mm=100, language="dmpl", dmpl_mode=3)
    assert build_job([square(10, 10)], p).text == (
        " ;:H A L0 U400,400 D1200,400 D1200,1200 D400,1200 D400,400 U400,400 U0,0 ")


def test_dmpl_mode_1_is_always_1000_units_per_inch():
    """EC1 sets 0.001 inch; Inkcut keeps its HPGL scale here (20.4 mm)."""
    p = Profile(width_mm=100, language="dmpl", dmpl_mode=1, units_per_mm=40)
    text = build_job([[(0, 1), (25.4, 1)]], p).text
    assert text.startswith(";:HAEC1 U0,39 D1000,39 ")


def test_dmpl_matches_the_monday_test_file():
    mark = [(10, 35), (20, 35)]
    p = Profile(width_mm=100, language="dmpl", dmpl_mode=3)
    with open(os.path.join(HERE, "a4", "kwadrat_20mm_dmpl3.dmpl")) as f:
        assert build_job([square(10, 10), mark], p).text == f.read()


# ---- the same square as Inkcut ----------------------------------------------------

def test_same_moves_as_inkcut_with_its_scale_and_margin():
    """Inkcut 2.1.8, SK-870T profile, 20 mm square (tests/wzorce_inkcut):
    with Inkcut's scale (1021 per inch) and its 10 px margin at 90 dpi
    our moves are the same; only the frame around them differs
    (we add SP1 and lift before going home, Inkcut ends with IN;)."""
    with open(os.path.join(HERE, "wzorce_inkcut", "hpgl_podstawowy.hpgl")) as f:
        theirs = [c for c in commands(f.read()) if c[:2] in ("PU", "PD")]
    m = 10 * 25.4 / 90                        # Inkcut's margin, mm
    path = [(m, m + 20), (m + 20, m + 20), (m + 20, m), (m, m), (m, m + 20)]
    ours = [c for c in commands(build_job([path], Profile(width_mm=860, units_per_mm=1021 / 25.4)).text)
            if c[:2] in ("PU", "PD")]
    assert ours[:5] == theirs[:5]             # the square itself
    assert ours[-1] == theirs[-1] == "PU0,0"  # home


# ---- working area -------------------------------------------------------------------

@pytest.mark.parametrize("path, words", [
    ([(10, 90), (10, 105.5)], "past the cutting width of 100 mm by 5.5 mm"),
    ([(10, -2), (10, 50)], "below 0 by 2.0 mm"),
    ([(-3, 10), (10, 10)], "before the origin (along the material) by 3.0 mm"),
])
def test_design_off_the_material_is_refused(path, words):
    with pytest.raises(JobError) as e:
        build_job([path], Profile(width_mm=100))
    assert words in str(e.value)


def test_length_limit_only_when_set():
    build_job([[(0, 1), (5000, 1)]], Profile(width_mm=100))          # a roll: fine
    with pytest.raises(JobError, match="past the length of 300 mm by 10.0 mm"):
        build_job([[(0, 1), (310, 1)]], Profile(width_mm=100, length_mm=300))


def test_exactly_on_the_edge_is_fine():
    build_job([[(0, 0), (0, 100)]], Profile(width_mm=100))


def test_nothing_to_cut():
    with pytest.raises(JobError, match="nothing to cut"):
        build_job([[(1, 1)], []], Profile(width_mm=100))


# ---- machine axes ---------------------------------------------------------------------

def first_point(text):
    return tuple(int(v) for v in re.search(r"PU(\d+),(\d+);PD", text).groups())


def test_swap_xy():
    p = Profile(width_mm=100, swap_xy=True)
    assert first_point(build_job([[(30, 5), (40, 5)]], p).text) == (200, 1200)


def test_invert_across_is_mirrored_within_the_cutting_width():
    p = Profile(width_mm=100, invert_y=True)        # machine Y = across, reversed
    # y = 5 mm from one edge is 95 mm from the other
    assert first_point(build_job([[(30, 5), (40, 5)]], p).text) == (1200, 3800)


def test_invert_along_stays_at_the_origin_on_a_roll():
    p = Profile(width_mm=100, invert_x=True)        # machine X = along, reversed
    text = build_job([[(30, 5), (40, 5)]], p).text
    # mirrored within the design's own length: 30..40 stays 30..40, direction flipped
    assert first_point(text) == (1600, 200)
    assert "PD1200,200;" in text


def test_axes_never_give_negative_coordinates():
    for swap in (False, True):
        for ix in (False, True):
            for iy in (False, True):
                p = Profile(width_mm=100, swap_xy=swap, invert_x=ix, invert_y=iy)
                text = build_job([square(0, 0), [(70, 99), (90, 100)]], p).text
                assert not re.search(r"-\d", text), (swap, ix, iy)


# ---- file output ---------------------------------------------------------------------

def test_save_writes_exactly_the_commands(tmp_path):
    job = build_job([square(10, 10)], Profile(width_mm=100))
    out = tmp_path / ("test" + job.extension)
    job.save(out)
    assert out.read_bytes() == job.text.encode("ascii")
    assert job.extension == ".hpgl"


# ---- profiles ----------------------------------------------------------------------

def test_builtin_profiles_load():
    assert prof.builtin_names() == ["seiki-sk-870t", "vevor-870", "vevor-ki-375a"]
    sk = prof.load_builtin("seiki-sk-870t")
    assert sk.width_mm == 780.0 and sk.language == "hpgl" and sk.units_per_mm == 40.0
    assert prof.load_builtin("vevor-ki-375a").width_mm == 285.0


def test_profile_round_trip(tmp_path):
    p = Profile(name='My "cutter"', width_mm=600, speed_cm_s=20, flow="rtscts", swap_xy=True)
    path = tmp_path / "p.toml"
    prof.save(p, path)
    assert prof.load(path) == p


def test_missing_keys_get_defaults_and_unknown_keys_are_refused():
    p = prof.from_dict({"name": "x", "width_mm": 300})
    assert p.width_mm == 300.0 and p.language == "hpgl" and p.speed_cm_s is None
    with pytest.raises(ProfileError, match="unknown keys: widht_mm"):
        prof.from_dict({"name": "x", "widht_mm": 300})


def test_bad_values_are_listed_in_one_message():
    with pytest.raises(ProfileError) as e:
        prof.from_dict({"name": "x", "width_mm": -1, "language": "gpgl", "flow": "cts"})
    text = str(e.value)
    assert "width_mm" in text and "language" in text and "flow" in text


def test_unknown_builtin_names_the_ones_there_are():
    with pytest.raises(ProfileError, match="seiki-sk-870t"):
        prof.load_builtin("nope")


# ---- no GUI toolkit in the core ------------------------------------------------------

def test_core_imports_no_gui_toolkit():
    code = ("import sys, vintyl.core.job, vintyl.core.profile, vintyl.core.protocols; "
            "bad = [m for m in sys.modules if m.split('.')[0] in ('PySide6', 'PyQt5', 'PyQt6', 'tkinter')]; "
            "print(bad); sys.exit(1 if bad else 0)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ---- the user's cutter profiles ---------------------------------------------------------------
def test_three_built_in_cutters():
    from vintyl.core import profile
    names = {e["id"]: e["profile"] for e in profile.catalogue()}
    assert set(names) >= {"seiki-sk-870t", "vevor-ki-375a", "vevor-870"}
    assert names["vevor-870"].width_mm == 780.0 and names["vevor-870"].connection == "usb-printer"


def test_a_changed_built_in_cutter_is_the_users_copy_and_can_be_restored(tmp_path, monkeypatch):
    import dataclasses
    from vintyl.core import profile
    monkeypatch.setenv("VINTYL_PROFILES", str(tmp_path / "profiles"))
    entry = {e["id"]: e for e in profile.catalogue()}["vevor-ki-375a"]
    assert entry["builtin"] and not entry["changed"]
    profile.save_user("vevor-ki-375a", dataclasses.replace(entry["profile"], port="/dev/usb/lp7"))
    entry = {e["id"]: e for e in profile.catalogue()}["vevor-ki-375a"]
    assert entry["changed"] and entry["profile"].port == "/dev/usb/lp7"
    profile.delete_user("vevor-ki-375a")                       # restore: the built-in one again
    entry = {e["id"]: e for e in profile.catalogue()}["vevor-ki-375a"]
    assert not entry["changed"] and entry["profile"].port == "/dev/usb/lp1"


def test_a_new_cutter_gets_its_own_file_and_a_broken_one_is_reported(tmp_path, monkeypatch):
    import dataclasses
    from vintyl.core import profile
    monkeypatch.setenv("VINTYL_PROFILES", str(tmp_path / "profiles"))
    base = profile.load_builtin("vevor-ki-375a")
    pid = profile.new_id("My big cutter")
    assert pid == "my-big-cutter"
    profile.save_user(pid, dataclasses.replace(base, name="My big cutter", width_mm=1260.0))
    assert profile.new_id("My big cutter") == "my-big-cutter-2"
    (tmp_path / "profiles" / "broken.toml").write_text("width_mm = \"wide\"\n")
    entries = {e["id"]: e for e in profile.catalogue()}
    assert entries["my-big-cutter"]["profile"].width_mm == 1260.0 and not entries["my-big-cutter"]["builtin"]
    assert entries["broken"]["profile"] is None and entries["broken"]["error"]
