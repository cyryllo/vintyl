"""
Reading designs from files.

    load_svg(path) -> Element    every visible shape, in view mm (y down)
    load_dxf(path) -> Element    every visible entity of a DXF drawing, in view mm

For a vinyl cutter every visible outline is a cut, whatever its colour:
a shape is taken when it has a stroke or a fill (designs for vinyl are
often filled shapes or text turned into paths, with no stroke at all).
Hidden shapes (visibility:hidden, display:none) are left out.

svgelements reads the file; its curves become the curves format of
vintyl.core.curves (Bezier curves stay curves until they are cut).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os

from . import curves
from .design import Element
from ..i18n import _

SVG_PPI = 96.0               # CSS pixels per inch, as in Inkscape
MM_PER_PX = 25.4 / SVG_PPI


class LoadError(ValueError):
    """The file cannot be used; the message is safe to show the user."""


def _painted(el):
    for paint in (el.stroke, el.fill):
        if paint is not None and getattr(paint, "value", None) is not None:
            return True
    return False


def _hidden(el):
    v = el.values
    return v.get("visibility") in ("hidden", "collapse") or v.get("display") == "none"


def svg_subpaths(path):
    """All visible painted shapes of an SVG as curves subpaths, in mm, y down
    from the top of the page."""
    import svgelements as se
    try:
        svg = se.SVG.parse(path, ppi=SVG_PPI)
    except Exception as e:                      # svgelements raises many kinds
        raise LoadError(_("Cannot read %s: %s") % (os.path.basename(path), e)) from None
    out = []
    for el in svg.elements():
        if not isinstance(el, se.Shape) or _hidden(el) or not _painted(el):
            continue
        shape = abs(se.Path(el))              # transforms applied
        segments = []

        def flush():
            if segments:
                out.extend(curves.join_segments(segments))
                segments.clear()

        def pt(p):
            return (p.x * MM_PER_PX, p.y * MM_PER_PX)
        for seg in shape:
            if isinstance(seg, se.Move):
                flush()                         # a new subpath starts
                continue
            if seg.start is None or seg.end is None:
                continue
            if isinstance(seg, (se.Line, se.Close)):
                if seg.start != seg.end:
                    segments.append((pt(seg.start), None, None, pt(seg.end)))
            elif isinstance(seg, se.CubicBezier):
                segments.append((pt(seg.start), pt(seg.control1), pt(seg.control2), pt(seg.end)))
            elif isinstance(seg, se.QuadraticBezier):
                s, c, e = pt(seg.start), pt(seg.control), pt(seg.end)
                c1 = (s[0] + 2.0 / 3.0 * (c[0] - s[0]), s[1] + 2.0 / 3.0 * (c[1] - s[1]))
                c2 = (e[0] + 2.0 / 3.0 * (c[0] - e[0]), e[1] + 2.0 / 3.0 * (c[1] - e[1]))
                segments.append((s, c1, c2, e))
            elif isinstance(seg, se.Arc):
                for cb in seg.as_cubic_curves():
                    segments.append((pt(cb.start), pt(cb.control1), pt(cb.control2), pt(cb.end)))
        flush()
    return out


def load_svg(path):
    """One element with every visible shape of the file."""
    paths = svg_subpaths(path)
    if not paths:
        raise LoadError(_("%s has no visible shapes to cut.") % os.path.basename(path))
    name = os.path.splitext(os.path.basename(path))[0]
    return Element(name=name, paths=paths, source=path)


# ---- DXF ----------------------------------------------------------------------------------
# millimetres per DXF unit ($INSUNITS); "Unitless" drawings ask (ask_units)
DXF_MM_PER_UNIT = {
    "Inches": 25.4, "Feet": 304.8, "Miles": 1609344.0, "Millimeters": 1.0, "Centimeters": 10.0,
    "Meters": 1000.0, "Kilometers": 1000000.0, "Microinches": 25.4e-6, "Mils": 0.0254,
}
DXF_UNITS = list(DXF_MM_PER_UNIT)
DXF_TOLERANCE_MM = 0.01          # how far arcs and splines, made of straight pieces, may stray


class LoadCancelled(Exception):
    """The user did not say the drawing's units."""


def load_dxf(path, ask_units=None):
    """One element with every visible entity of the DXF drawing, in view mm.
    The reader (vintyl.core.dxf_reader, from K40 Whisperer through Kerfly)
    gives straight pieces; they are joined end to end into outlines, and an
    outline that comes back to its start is closed. ask_units() is called for
    a drawing without units and returns one of DXF_UNITS (None: cancel)."""
    from .dxf_reader import DXF_CLASS
    from .patterns import _without_straight_points, chain_polylines
    name = os.path.splitext(os.path.basename(path))[0]
    reader = DXF_CLASS()
    try:
        # a text in another encoding must not stop the drawing from loading
        with open(path, errors="replace") as fd:
            reader.GET_DXF_DATA(fd, lin_tol=0.001, get_units=True)
            units = reader.units
            if units == "Unitless":
                units = ask_units() if ask_units is not None else "Millimeters"
            if units is None:
                raise LoadCancelled()
            if units not in DXF_MM_PER_UNIT:
                raise LoadError(_("%s: unknown units %s.") % (os.path.basename(path), units))
            mm = DXF_MM_PER_UNIT[units]
            fd.seek(0)
            reader = DXF_CLASS()
            reader.GET_DXF_DATA(fd, lin_tol=DXF_TOLERANCE_MM / mm, get_units=False)
    except OSError as e:
        raise LoadError(_("Cannot open %s: %s") % (os.path.basename(path), e.strerror or e)) from None
    # DXF y runs up; the view's y runs down
    pieces = [[(x0 * mm, -y0 * mm), (x1 * mm, -y1 * mm)] for x0, y0, x1, y1 in reader.coords
              if abs(x0 - x1) + abs(y0 - y1) > 1e-12]
    if not pieces:
        raise LoadError(_("%s has no visible shapes to cut.") % os.path.basename(path))
    lines = chain_polylines(pieces, tol=1e-4)
    polys, closed = [], []
    for line in lines:
        pts = _without_straight_points(line, 1e-9) if len(line) > 2 else line
        shut = len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) < 1e-4 and abs(pts[0][1] - pts[-1][1]) < 1e-4
        if shut:
            pts = pts[:-1]
        polys.append(pts)
        closed.append(shut)
    element = Element(name=name, paths=curves.from_polylines(polys, closed), source=path)
    element.dxf_messages = reader.dxf_messages.strip()
    return element
