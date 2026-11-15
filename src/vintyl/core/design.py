"""
The design: elements placed on the material.

Each element holds its own paths in the curves format (vintyl.core.curves),
in VIEW coordinates: millimetres, x along the material (right), y DOWN,
with the origin at (0, 0). The material lies at y from -width to 0, so a
point's material y (across, up) is simply -y. Moving, scaling and turning
an element change its nodes directly: there is no separate transform to
keep in step, and what is drawn is what is cut.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math
from dataclasses import dataclass, field

from . import curves


@dataclass
class Element:
    name: str
    paths: list                       # curves subpaths, view mm (y down)
    cut: bool = True                  # False: shown, but not sent to the cutter
    source: str = ""                  # file it came from, if any

    def copy(self):
        return Element(self.name, curves.copy_path(self.paths), self.cut, self.source)

    @property
    def bounds(self):
        """(xmin, xmax, ymin, ymax) in view mm."""
        return curves.bounds(self.paths)

    @property
    def size(self):
        xmin, xmax, ymin, ymax = self.bounds
        return xmax - xmin, ymax - ymin

    def move_by(self, dx, dy):
        self.paths = curves.translate(self.paths, dx, dy)

    def move_to(self, left, top):
        xmin, _xmax, ymin, _ymax = self.bounds
        self.move_by(left - xmin, top - ymin)

    def transform(self, f):
        """Apply f(x, y) -> (x, y) to every node and handle."""
        out = []
        for sub in self.paths:
            nodes = []
            for n in sub["nodes"]:
                x, y = f(n[0], n[1])
                m = [x, y, None, None, None, None]
                if n[2] is not None:
                    m[2], m[3] = f(n[2], n[3])
                if n[4] is not None:
                    m[4], m[5] = f(n[4], n[5])
                nodes.append(m)
            out.append({"closed": sub["closed"], "nodes": nodes})
        self.paths = out

    def set_size(self, width, height):
        """Scale about the top-left corner of the bounding box. A side that
        is 0 (a level or upright line) keeps its size."""
        xmin, xmax, ymin, ymax = self.bounds
        w0, h0 = xmax - xmin, ymax - ymin
        sx = width / w0 if w0 > 1e-9 else 1.0
        sy = height / h0 if h0 > 1e-9 else 1.0
        self.transform(lambda x, y: (xmin + (x - xmin) * sx, ymin + (y - ymin) * sy))

    def rotate(self, degrees):
        """Turn counter-clockwise (as seen on screen) about the bounding-box centre."""
        xmin, xmax, ymin, ymax = self.bounds
        cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
        a = math.radians(degrees)
        c, s = math.cos(a), math.sin(a)
        # y is down on screen, so counter-clockwise on screen is -a in these coordinates
        self.transform(lambda x, y: (cx + (x - cx) * c + (y - cy) * s,
                                     cy - (x - cx) * s + (y - cy) * c))


@dataclass
class Design:
    elements: list = field(default_factory=list)

    def bounds(self, only_cut=False):
        els = [e for e in self.elements if e.cut or not only_cut]
        boxes = [e.bounds for e in els if e.paths]
        if not boxes:
            return None
        return (min(b[0] for b in boxes), max(b[1] for b in boxes),
                min(b[2] for b in boxes), max(b[3] for b in boxes))

    def material_polylines(self, tol=curves.FLATNESS_MM):
        """What goes to the cutter: the elements marked "cut", in list order,
        as polylines in material coordinates (x along, y across = -view y)."""
        out = []
        for e in self.elements:
            if not e.cut:
                continue
            for poly in curves.flatten(e.paths, tol):
                out.append([(x, -y) for x, y in poly])
        return out
