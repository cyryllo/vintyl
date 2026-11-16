"""
Icons: Tabler outline icons (MIT, see icons/tabler/LICENSE) drawn in the
theme's colour, Vintyl's own icons in the same style (icons/*.svg, GPL, as
the drag knife: Tabler has no cutter's knife), and the program icon.

tabler() is adapted from Kerfly (kerfly/gui/icons/__init__.py, commit
cf48565): the same idea, without Kerfly's jog-pad drawings.

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
INK = "#2b2f36"
_cache = {}


def set_ink(color):
    """The colour icons are drawn in (the theme's); drawn again from now on."""
    global INK
    INK = color
    _cache.clear()


def tabler(name, color=None):
    """QIcon for a Tabler icon in the given colour (default: the theme's ink)."""
    return _drawn(os.path.join(HERE, "tabler", name + ".svg"), color)


def own(name, color=None):
    """QIcon for one of Vintyl's own icons drawn in the Tabler style (icons/<name>.svg)."""
    return _drawn(os.path.join(HERE, name + ".svg"), color)


def _drawn(path, color=None):
    from PySide6.QtSvg import QSvgRenderer
    color = color or INK
    key = (path, color)
    if key in _cache:
        return _cache[key]
    with open(path, encoding="utf-8") as f:
        svg = f.read().replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    icon = QIcon()
    for size in (24, 32, 48, 64):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        renderer.render(p, QRectF(0, 0, size, size))
        p.end()
        icon.addPixmap(pm)
    _cache[key] = icon
    return icon


def app_icon():
    return QIcon(os.path.join(HERE, "vintyl.svg"))
