#!/usr/bin/env python3
"""
Pliki do kroku A4.10 (nóż na folii): te same kształty bez kompensacji noża
(zestaw A) i z kompensacją 0,25 mm + nadcięciem 0,5 mm (zestaw B).
Generuje je rdzeń Vintyl, tak jak zrobiłby to program.

    .venv/bin/python tools/a4_noz.py      -> tests/a4/noz_A_bez.hpgl, noz_B_z.hpgl

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import dataclasses
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from vintyl.core import curves, profile, shapes  # noqa: E402
from vintyl.core.job import build_job  # noqa: E402


def star(cx, cy, r_out, r_in, points=5):
    pts = []
    for k in range(points * 2):
        r = r_out if k % 2 == 0 else r_in
        a = math.pi / 2 + math.pi * k / points
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return [{"closed": True, "nodes": [curves.node(x, y) for x, y in pts]}]


LEFT = 50.0     # wszystko 50 mm dalej w lewo (w poprzek folii), z dala od kwadratów testowych


def set_at(x0, y0=LEFT):
    """Kształty jednego zestawu w milimetrach materiału (x wzdłuż, y w poprzek)."""
    parts = [
        shapes.rectangle(x0, y0 + 20, x0 + 20, y0 + 40),                  # kwadrat 20 mm
        shapes.ellipse(x0, y0 + 50, x0 + 25, y0 + 75)
        + shapes.ellipse(x0 + 7.5, y0 + 57.5, x0 + 17.5, y0 + 67.5),      # kółko z otworem
        star(x0 + 15, y0 + 100, 15, 6),                                    # gwiazda: ostre ramiona
    ]
    polys, groups = [], []
    for g, paths in enumerate(parts):
        for poly in curves.flatten(paths):
            polys.append(poly)
            groups.append(g)
    return polys, groups


def main():
    base = profile.load_builtin("vevor-ki-375a")
    out = {}
    sets = (("noz_A_bez.hpgl", 60.0, 0.0, 0.0), ("noz_B_z.hpgl", 120.0, 0.25, 0.5))
    for name, x0, knife, over in sets:
        p = dataclasses.replace(base, knife_offset_mm=knife, overcut_mm=over)
        polys, groups = set_at(x0)
        job = build_job(polys, p, groups, inside_first=True)
        path = os.path.join(ROOT, "tests", "a4", name)
        # pliki już wysłane do plotera zostają takie, jakie poszły (zapis z testu)
        if os.path.exists(path) and "--nadpisz" not in sys.argv:
            print("%-22s już jest, nie nadpisuję (--nadpisz, żeby utworzyć od nowa)" % name)
            continue
        job.save(path)
        out[name] = job
        print("%-22s %5d bajtów, cięcie %.0f mm, kształtów %d, zakres %s mm"
              % (name, len(job.text), job.cut_mm, job.paths, tuple(round(v, 1) for v in job.bounds_mm)))
    return out


if __name__ == "__main__":
    main()
