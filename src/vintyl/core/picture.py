"""
A picture drawn with a pen: its light and dark made of lines, in three styles.

- waves: rows of lines that wobble like a seismograph's trace, more and
  faster where the picture is darker ("squiggle" drawings);
- spiral: one line from the middle outwards, wobbling the same way;
- hatching: parallel lines, as an engraving: light parts stay empty, darker
  ones get lines in one direction, darker still a second and a third across.

The picture comes in as a Grey: rows of darkness (0 white .. 1 black), so
this module needs no Qt; the window reads the file and scales it to about
two pixels per line spacing (the averaging blurs the grain away). The lines
come out in mm, x to the right and y down from the picture's top-left
corner, as polylines ready for curves.from_polylines.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math

from . import curves

STYLES = ("waves", "spiral", "hatching")
STEP_MM = 0.2                  # how far apart the points along a line are worked out
SIMPLIFY_MM = 0.02             # points closer than this to a straight line are dropped
HATCH_LEVELS = (0.2, 0.45, 0.7)        # darkness from which the 1st, 2nd and 3rd direction is drawn
HATCH_ANGLES = (0.0, 90.0, -45.0)      # the directions: the base angle, across it, between


class Grey:
    """A picture as darkness: rows (lists) of values 0 (white) .. 1 (black),
    all of the same length."""

    def __init__(self, rows):
        if not rows or not rows[0]:
            raise ValueError("an empty picture")
        self.rows = rows
        self.height = len(rows)
        self.width = len(rows[0])

    def adjusted(self, contrast=1.0, brightness=0.0, invert=False):
        """A copy with the contrast (1: as it is, 2: twice) about the middle
        grey, brighter (brightness > 0: lighter, -1..1) and the light turned
        round (invert)."""
        def f(v):
            if invert:
                v = 1.0 - v
            v = (v - 0.5) * contrast + 0.5 - brightness
            return min(1.0, max(0.0, v))
        return Grey([[f(v) for v in row] for row in self.rows])

    def at(self, u, v):
        """The darkness at (u, v), 0..1 across and down the picture, between
        the pixels (bilinear); outside the picture: white."""
        if not (0.0 <= u <= 1.0 and 0.0 <= v <= 1.0):
            return 0.0
        x = u * self.width - 0.5
        y = v * self.height - 0.5
        x0 = min(max(int(math.floor(x)), 0), self.width - 1)
        y0 = min(max(int(math.floor(y)), 0), self.height - 1)
        x1, y1 = min(x0 + 1, self.width - 1), min(y0 + 1, self.height - 1)
        fx = min(max(x - x0, 0.0), 1.0)
        fy = min(max(y - y0, 0.0), 1.0)
        r0, r1 = self.rows[y0], self.rows[y1]
        top = r0[x0] + (r0[x1] - r0[x0]) * fx
        bottom = r1[x0] + (r1[x1] - r1[x0]) * fx
        return top + (bottom - top) * fy


def size_of(grey, width_mm):
    """(width, height) in mm of the picture drawn width_mm wide."""
    return width_mm, width_mm * grey.height / grey.width


def _finish(polys):
    """The polylines simplified (fewer points, the same line) and without
    the ones too short to draw."""
    out = []
    for p in polys:
        if len(p) < 2:
            continue
        p = curves.simplify(p, SIMPLIFY_MM)
        if len(p) >= 2 and _length(p) >= 2 * STEP_MM:
            out.append(p)
    return out


def _length(p):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(p, p[1:]))


class _Wobble:
    """A line's wobble as it goes along: the phase grows faster where it is
    dark (so the waves stay smooth from light to dark), the height grows
    with the darkness."""

    def __init__(self, amplitude, frequency):
        self.amplitude = amplitude           # mm at full black
        self.frequency = frequency           # waves per mm at full black
        self.phase = 0.0

    def step(self, dark, ds):
        # a little wobble even where it is light, so the line is not dead straight
        # next to a dark part; none at all on white
        self.phase += 2 * math.pi * self.frequency * (0.25 + 0.75 * dark) * ds if dark > 0 else 0.0
        return self.amplitude * dark * math.sin(self.phase)


def waves(grey, width_mm, spacing=1.5, amplitude=None, frequency=1.0, skip_light=0.0, joined=False):
    """Rows of wobbling lines, spacing mm apart; amplitude: the wobble's
    height at full black (default: half the spacing, so neighbours just
    touch); frequency: waves per mm at full black. skip_light: the pen is
    lifted where the picture is lighter than this (0: never). joined: the
    rows go back and forth as one line (the pen hardly lifts; a short
    stroke joins them at the edges). Returns polylines in mm."""
    w, h = size_of(grey, width_mm)
    if amplitude is None:
        amplitude = spacing / 2.0
    rows = max(1, int(h / spacing))
    top = (h - (rows - 1) * spacing) / 2.0          # the rows in the middle of the picture
    n = max(2, int(w / STEP_MM))
    polys = []
    for k in range(rows):
        y = top + k * spacing
        xs = [w * i / n for i in range(n + 1)]
        if k % 2:
            xs.reverse()                             # back and forth: no long travel
        wobble = _Wobble(amplitude, frequency)
        line = []
        for x in xs:
            dark = grey.at(x / w, y / h)
            if dark < skip_light:
                if len(line) > 1:
                    polys.append(line)
                line = []
                continue
            line.append((x, y + wobble.step(dark, w / n)))
        if len(line) > 1:
            polys.append(line)
    if joined and not skip_light:
        whole = []
        for p in polys:
            whole.extend(p)
        polys = [whole]
    return _finish(polys)


def spiral(grey, width_mm, spacing=1.5, amplitude=None, frequency=1.0, skip_light=0.0):
    """One line from the middle outwards, its turns spacing mm apart,
    wobbling across its way as waves do; only inside the picture (it is cut
    where it leaves it). Returns polylines in mm."""
    w, h = size_of(grey, width_mm)
    if amplitude is None:
        amplitude = spacing / 2.0
    cx, cy = w / 2.0, h / 2.0
    reach = math.hypot(cx, cy)                       # to the corners
    wobble = _Wobble(amplitude, frequency)
    polys, line = [], []
    theta = 0.0
    while True:
        r = spacing * theta / (2 * math.pi)
        if r > reach:
            break
        x, y = cx + r * math.cos(theta), cy + r * math.sin(theta)
        inside = 0.0 <= x <= w and 0.0 <= y <= h
        dark = grey.at(x / w, y / h) if inside else 0.0
        # the next point STEP_MM further along (the first turns are small: no more than 10 degrees)
        turn = min(STEP_MM / max(r, 1e-6), math.radians(10))
        if not inside or dark < skip_light:
            if len(line) > 1:
                polys.append(line)
            line = []
        else:
            off = wobble.step(dark, max(r * turn, 1e-6))
            line.append((x + off * math.cos(theta), y + off * math.sin(theta)))   # across the way: outwards
        theta += turn
    if len(line) > 1:
        polys.append(line)
    return _finish(polys)


def hatching(grey, width_mm, spacing=1.0, angle=45.0, levels=HATCH_LEVELS):
    """Engraving: lines spacing mm apart at angle degrees where the picture
    is darker than levels[0], a second direction across them where darker
    than levels[1], a third where darker than levels[2]. Returns polylines in
    mm (each direction's lines back and forth)."""
    w, h = size_of(grey, width_mm)
    cx, cy = w / 2.0, h / 2.0
    half = math.hypot(w, h) / 2.0
    polys = []
    for level, turn in zip(levels, HATCH_ANGLES):
        a = math.radians(angle + turn)
        dx, dy = math.cos(a), math.sin(a)            # along the lines
        nx, ny = -dy, dx                             # from one line to the next
        count = int(2 * half / spacing)
        for k in range(count + 1):
            off = -half + k * spacing
            ox, oy = cx + nx * off, cy + ny * off
            span = _inside(ox, oy, dx, dy, w, h)
            if span is None:
                continue
            t0, t1 = span
            ts = [t0 + i * STEP_MM for i in range(int((t1 - t0) / STEP_MM) + 1)]
            if k % 2:
                ts.reverse()
            line = []
            for t in ts:
                x, y = ox + dx * t, oy + dy * t
                if grey.at(x / w, y / h) >= level:
                    line.append((x, y))
                    continue
                if len(line) > 1:
                    polys.append(line)
                line = []
            if len(line) > 1:
                polys.append(line)
    return _finish(polys)


def _inside(ox, oy, dx, dy, w, h):
    """(t0, t1): where the line (ox, oy) + t (dx, dy) is inside the picture
    0..w x 0..h (Liang-Barsky), None when it misses it."""
    t0, t1 = -1e9, 1e9
    for p, d, lo, hi in ((ox, dx, 0.0, w), (oy, dy, 0.0, h)):
        if abs(d) < 1e-12:
            if not lo <= p <= hi:
                return None
            continue
        a, b = (lo - p) / d, (hi - p) / d
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
    return (t0, t1) if t1 - t0 > STEP_MM else None


def draw(style, grey, width_mm, **values):
    """The lines of a picture in a style (STYLES), with its values."""
    if style == "waves":
        keys = ("spacing", "amplitude", "frequency", "skip_light", "joined")
        return waves(grey, width_mm, **{k: values[k] for k in keys if k in values})
    if style == "spiral":
        keys = ("spacing", "amplitude", "frequency", "skip_light")
        return spiral(grey, width_mm, **{k: values[k] for k in keys if k in values})
    if style == "hatching":
        keys = ("spacing", "angle")
        return hatching(grey, width_mm, **{k: values[k] for k in keys if k in values})
    raise ValueError("no such style: %r" % (style,))
