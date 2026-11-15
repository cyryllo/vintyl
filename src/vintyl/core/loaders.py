"""
Reading designs from files.

    load_svg(path) -> Element    every visible shape, in view mm (y down)

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
        raise LoadError("Cannot read %s: %s" % (os.path.basename(path), e)) from None
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
        raise LoadError("%s has no visible shapes to cut." % os.path.basename(path))
    name = os.path.splitext(os.path.basename(path))[0]
    return Element(name=name, paths=paths, source=path)
