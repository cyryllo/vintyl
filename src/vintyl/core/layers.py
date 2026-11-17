"""
Colour layers: every element belongs to one, and a layer is drawn (or cut)
as a whole, one after another.

With a pen a layer is one pen: its colour, its width, where its stroke lies
against the line, a fill pattern for the closed shapes that have none of
their own. With the knife a layer is one colour of vinyl: cut one colour,
change the vinyl, cut the next. The cutter has one holder, so between
layers the user changes the pen (or the vinyl) and goes on.

The order of the layers is the order they are drawn in (light colours first,
the black outline last, usually). A layer can be left out ("enabled" off).

Also here, without Qt: colours from "#rrggbb", how far apart two colours
look (CIE76 delta E in the Lab space: about 2 is hardly seen, over 20 is
another colour), similar colours merged, and a colour's name in words, for
"Put in the pen: Red".

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math
import re
from dataclasses import dataclass

from ..i18n import N_

DEFAULT_ID = "black"
DEFAULT_COLOR = "#000000"
PEN_PLACES = ("on", "outside", "inside")
# colours closer than this (delta E) are "similar" and merged on import
SIMILAR_DELTA_E = 15.0


@dataclass(eq=False)          # a layer is itself: two layers alike are still two
class Layer:
    id: str                         # stable within the project ("black", "c2", ...)
    name: str                       # what the user sees ("Red"; editable)
    color: str = DEFAULT_COLOR      # "#rrggbb"
    enabled: bool = True            # False: left out when drawing or cutting
    pen_width_mm: float = None      # None: the window's pen width
    pen_place: str = None           # None: the window's ("on", "outside", "inside")
    fill: dict = None               # the fill for its closed shapes without one of their own

    def copy(self):
        return Layer(self.id, self.name, self.color, self.enabled, self.pen_width_mm, self.pen_place,
                     dict(self.fill) if self.fill else None)


def default_layer():
    """The layer of a design without colours (old projects, new drawings)."""
    return Layer(DEFAULT_ID, N_("Black"), DEFAULT_COLOR)


def new_id(layers):
    """An id no layer in `layers` has."""
    taken = {layer.id for layer in layers}
    n = 1
    while "c%d" % n in taken:
        n += 1
    return "c%d" % n


def unique_name(base, layers):
    """base, or "base 2", "base 3"... when a layer has that name."""
    names = {layer.name for layer in layers}
    label, n = base, 2
    while label in names:
        label, n = "%s %d" % (base, n), n + 1
    return label


# ---- colours ---------------------------------------------------------------------------------
_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def parse_color(text):
    """'#rrggbb' (or 'rrggbb') as (r, g, b) 0..255; ValueError otherwise."""
    m = _HEX.match(str(text).strip())
    if not m:
        raise ValueError("not a colour: %r" % (text,))
    h = m.group(1)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hex_color(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def to_lab(rgb):
    """sRGB (0..255) to CIE Lab (D65)."""
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a, b):
    """How far apart two colours ('#rrggbb') look: CIE76 delta E."""
    la, lb = to_lab(parse_color(a)), to_lab(parse_color(b))
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(la, lb)))


def merge_similar(counts, limit=SIMILAR_DELTA_E):
    """Group similar colours. counts: {colour: how many shapes have it}.
    Returns [(kept colour, [colours merged into it])], the groups with the
    most shapes first; each group is kept as its most used colour."""
    groups = []
    for color in sorted(counts, key=lambda c: (-counts[c], c)):
        for kept, members in groups:
            if delta_e(kept, color) < limit:
                members.append(color)
                break
        else:
            groups.append((color, [color]))
    groups.sort(key=lambda g: -sum(counts[c] for c in g[1]))      # stable: ties keep their order
    return groups


def assign(colors, layers, merge=True, name=None, limit=SIMILAR_DELTA_E):
    """Each colour of an imported file to a layer: {colour: layer}. colors:
    {colour: how many shapes have it}. A colour goes to an existing layer of
    the same colour, or with merge to one of a similar colour (also to one
    made for a similar colour of this file); else a new layer is appended to
    `layers`, named name(colour) (default: color_name), with a number when
    that name is taken."""
    out = {}
    groups = merge_similar(colors, limit) if merge else [(c, [c]) for c in sorted(colors, key=lambda c: (-colors[c], c))]
    for kept, members in groups:
        target = None
        for layer in layers:
            if layer.color == kept or (merge and delta_e(layer.color, kept) < limit):
                target = layer
                break
        if target is None:
            target = Layer(new_id(layers), unique_name((name or color_name)(kept), layers), kept)
            layers.append(target)
        for color in members:
            out[color] = target
    return out


def plan(colors, existing, name=None, limit=SIMILAR_DELTA_E):
    """What an import offers: (candidates, merged, separate).
    candidates: the existing layers, then one new layer for each colour of
    the file that has no layer of the same colour (named, numbered);
    merged and separate: {colour: candidate}, similar colours to one (the
    group's most used colour's, or an existing layer of a similar colour),
    or each to its own. Nothing is changed in `existing`: the caller adds
    the new layers it uses."""
    pool = list(existing)
    own = assign(colors, pool, merge=False, name=name, limit=limit)
    chosen = {}
    for kept, members in merge_similar(colors, limit):
        target = own[kept]
        if target not in existing:
            for layer in existing:
                if delta_e(layer.color, kept) < limit:
                    target = layer
                    break
        for color in members:
            chosen[color] = target
    return pool, chosen, dict(own)


# a colour's name in words: (name, hue from, hue to) for the colourful ones
COLOR_NAMES = (N_("Black"), N_("White"), N_("Grey"), N_("Dark grey"), N_("Light grey"), N_("Red"), N_("Orange"),
               N_("Yellow"), N_("Green"), N_("Light blue"), N_("Blue"), N_("Purple"), N_("Pink"), N_("Brown"))
_HUES = ((15, N_("Red")), (40, N_("Orange")), (70, N_("Yellow")), (165, N_("Green")), (200, N_("Light blue")),
         (255, N_("Blue")), (290, N_("Purple")), (340, N_("Pink")), (360, N_("Red")))


def color_name(color):
    """The name of a colour in words (English, to be translated with _()):
    black, white, grey, or its hue; dark orange is brown."""
    r, g, b = (c / 255.0 for c in parse_color(color))
    hi, lo = max(r, g, b), min(r, g, b)
    light = (hi + lo) / 2
    chroma = hi - lo
    if chroma < 0.12:                            # no clear hue: black, a grey or white
        if light < 0.2:
            return "Black"
        if light > 0.85:
            return "White"
        if light < 0.45:
            return "Dark grey"
        return "Light grey" if light > 0.65 else "Grey"
    if hi == r:
        hue = (60 * ((g - b) / chroma)) % 360
    elif hi == g:
        hue = 60 * ((b - r) / chroma) + 120
    else:
        hue = 60 * ((r - g) / chroma) + 240
    if light < 0.1:
        return "Black"
    for top, name in _HUES:
        if hue < top:
            if name in ("Orange", "Red") and light < 0.35 and hue >= 10:
                return "Brown"                   # a dark orange (or a dark orange-red)
            return name
    return "Red"
