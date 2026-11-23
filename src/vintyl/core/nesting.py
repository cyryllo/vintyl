"""
Nesting: parts laid out on the material as tightly as their bounding
rectangles allow (MaxRects), turned by 90 degrees where that helps, so the
vinyl taken off the roll is as short as it can be.

The material is a strip: as wide as the cutter cuts, as long as needed.
Each part (its size across and along) goes into the free space nearest to
the start of the material (then nearest to its edge), bigger parts first;
a part wider than the strip also when turned is left out.

Source: Kerfly (https://github.com/cyryllo/Kerfly), branch 2.0,
kerfly/core/nesting.py at commit 0d58f11: pack() (MaxRects, the free
rectangles split and pruned as there). Changed for Vintyl: one strip of
fixed width and open length instead of the laser bed's sheets, so the
place of a part is chosen bottom-left (the lowest end along the material,
then the nearest to its edge) instead of best short side fit; the parts by
their outlines (sparrow) are left out (no extra library).

Copyright (C) 2026 Kerfly contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
OPEN_LENGTH = 1.0e7             # mm: the strip's length, longer than any roll


def pack_strip(sizes, width, spacing=0.0, turn=True):
    """Places parts (across, along) in mm in one strip `width` mm across:
    ([(x, y, turned) or None], length) in the order given: x across from the
    strip's edge, y along from its start (the part's corner nearest to
    both), turned by 90 degrees (across and along swapped); None for a part
    that does not fit across, also turned. length: how much of the strip
    the parts take along. spacing: the room between two parts."""
    bw = float(width) + spacing                    # a part's room includes the spacing after it
    free = [(0.0, 0.0, bw, OPEN_LENGTH)]

    def find(w, h):
        best = None
        for fx, fy, fw, fh in free:
            for turned, (pw, ph) in ((False, (w, h)), (True, (h, w)))[:2 if turn else 1]:
                if pw <= fw + 1e-9 and ph <= fh + 1e-9:
                    # bottom-left: the lowest end along the material, then the nearest to its edge
                    score = (fy + ph, fx, turned)
                    if best is None or score < best[0]:
                        best = (score, fx, fy, turned, pw, ph)
        return best

    def place(x, y, w, h):
        out = []
        for fx, fy, fw, fh in free:
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                out.append((fx, fy, fw, fh))
                continue
            if x > fx:
                out.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                out.append((x + w, fy, fx + fw - x - w, fh))
            if y > fy:
                out.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                out.append((fx, y + h, fw, fy + fh - y - h))
        pruned = []
        for i, a in enumerate(out):
            inside = any(j != i and b[0] <= a[0] and b[1] <= a[1] and a[0] + a[2] <= b[0] + b[2]
                         and a[1] + a[3] <= b[1] + b[3] and (b != a or j < i) for j, b in enumerate(out))
            if not inside and a[2] > 1e-6 and a[3] > 1e-6:
                pruned.append(a)
        free[:] = pruned

    # bigger parts first (the longest side, then the area), as Kerfly
    order = sorted(range(len(sizes)), key=lambda i: (-max(sizes[i]), -sizes[i][0] * sizes[i][1], i))
    result = [None] * len(sizes)
    length = 0.0
    for i in order:
        w, h = sizes[i][0] + spacing, sizes[i][1] + spacing
        found = find(w, h)
        if found is None:
            continue                                   # wider than the strip, also turned
        _score, x, y, turned, pw, ph = found
        place(x, y, pw, ph)
        result[i] = (x, y, turned)
        length = max(length, y + ph - spacing)
    return result, length
