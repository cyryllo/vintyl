"""
The window that opens an SVG of several colours (0.9): each colour of the
file, how many shapes have it, and the colour layer it goes to (an existing
one, or a new one). The program's proposal comes first: similar colours
merged ("automatic", the default in the Settings) or each on its own
("ask"); "Merge similar" and "Each on its own" switch between them, "All in
one colour" puts everything into the most used one. A picture of the
drawing shows the colours as they will be.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, \
    QWidget

from vintyl.gui import _, ngettext, theme, widgets


def swatch(color, size=16):
    """A round swatch of a colour as a pixmap (a thin edge: white shows on white)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QPen(QColor(theme.token("field_border")), 1))
    p.setBrush(QColor(color))
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return pm


def _picture(groups, colour_of, size=260):
    """The drawing with each colour of the file drawn in the colour of the
    layer it goes to, fitted into a square: the outlines, and the filled
    shapes tinted with their fill's colour."""
    from vintyl.gui.canvas import painter_path, screen_color
    paths = []
    for (color, kind), subs in groups.items():
        fill = colour_of(kind) if isinstance(kind, str) else (colour_of(color) if kind else None)
        paths.append((painter_path(subs), colour_of(color), fill))
    box = QRectF()
    for path, _c, _f in paths:
        box = box.united(path.boundingRect())
    pm = QPixmap(size, size)
    pm.fill(QColor(theme.token("sheet")))
    if box.isEmpty():
        return pm
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    pad = 14
    k = (size - 2 * pad) / max(box.width(), box.height(), 1e-6)
    p.translate(size / 2.0, size / 2.0)
    p.scale(k, k)
    p.translate(-box.center().x(), -box.center().y())
    for path, _c, fill in paths:                 # the fills under every outline
        if fill:
            tint = QColor(screen_color(fill))
            tint.setAlpha(110)
            p.fillPath(path, tint)
    for path, color, _f in paths:
        p.setPen(QPen(screen_color(color), 1.6 / k))
        p.drawPath(path)
    p.end()
    return pm


def colour_dialog(parent, groups, candidates, chosen, merged, separate, show=True):
    """groups: {(colour, filled): subpaths} of the file; candidates: the
    layers offered (existing, then new); chosen / merged / separate:
    {colour: candidate} as proposed, merged, each on its own. Returns the
    chosen {colour: candidate}, or None (cancelled). show=False returns
    the dialog, not run (tests), with .combos {colour: combo box}."""
    from vintyl.core.loaders import colour_counts
    counts = colour_counts(groups)
    colours = sorted(counts, key=lambda c: (-counts[c], c))
    dlg, outer, body = widgets.plain_dialog(parent, _("Colours of the drawing"), 780)
    intro = QLabel(ngettext("The drawing has %d colour. Each goes to a colour of the design: check what the "
                            "program chose, and change it if you like.",
                            "The drawing has %d colours. Each goes to a colour of the design: check what the "
                            "program chose, and change it if you like.", len(colours)) % len(colours))
    intro.setWordWrap(True)
    body.addWidget(intro)
    row = QHBoxLayout()
    row.setSpacing(16)
    picture = QLabel()
    picture.setObjectName("preview_box")
    picture.setFixedSize(262, 262)
    picture.setAlignment(Qt.AlignCenter)
    row.addWidget(picture, 0, Qt.AlignTop)
    card = widgets.Card(_("Colours in the file"))
    combos = {}
    # many colours scroll, so the window still fits a 768 px screen
    rows_box = QWidget()
    rows_lay = QVBoxLayout(rows_box)
    rows_lay.setContentsMargins(0, 0, 0, 0)
    rows_lay.setSpacing(card.body.spacing())
    if len(colours) > 9:
        area = QScrollArea()
        area.setObjectName("plain_scroll")
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setFixedHeight(380)
        rows_box.setObjectName("plain_scroll_inner")
        area.setWidget(rows_box)
        card.body.addWidget(area)
    else:
        card.body.addWidget(rows_box)
    for color in colours:
        line = QHBoxLayout()
        line.setSpacing(8)
        dot = QLabel()
        dot.setPixmap(swatch(color, 18))
        name = QLabel("%s  ·  %s" % (color, ngettext("%d shape", "%d shapes", counts[color]) % counts[color]))
        name.setObjectName("muted")
        combo = QComboBox()
        for layer in candidates:
            combo.addItem(swatch(layer.color), layer.name)
        combo.setFixedWidth(190)
        line.addWidget(dot)
        line.addWidget(name, 1)
        line.addWidget(QLabel("→"))
        line.addWidget(combo)
        rows_lay.addLayout(line)
        combos[color] = combo
    buttons = QHBoxLayout()
    merge_button = QPushButton(_("Merge similar"))
    separate_button = QPushButton(_("Each on its own"))
    buttons.addWidget(merge_button)
    buttons.addWidget(separate_button)
    buttons.addStretch(1)
    card.body.addLayout(buttons)
    card.add_hint(_("Similar colours (two pinks, two greys) are drawn with one pen: merged, they go to one "
                    "colour. The order of drawing is in the Colours panel."))
    row.addWidget(card, 1)
    body.addLayout(row)

    def now():
        return {c: candidates[combos[c].currentIndex()] for c in colours}

    def redraw(*_a):
        picked = now()
        picture.setPixmap(_picture(groups, lambda c: picked[c].color))

    def put(mapping):
        for c in colours:
            combos[c].blockSignals(True)
            combos[c].setCurrentIndex(candidates.index(mapping[c]))
            combos[c].blockSignals(False)
        redraw()

    def one():
        first = now()[colours[0]]
        put({c: first for c in colours})
    for combo in combos.values():
        combo.currentIndexChanged.connect(redraw)
    merge_button.clicked.connect(lambda: put(merged))
    separate_button.clicked.connect(lambda: put(separate))
    put(chosen)
    all_one = QPushButton(_("All in one colour"))
    all_one.clicked.connect(one)
    cancel = QPushButton(_("Cancel"))
    cancel.clicked.connect(dlg.reject)
    go = QPushButton(_("Open"))
    go.setObjectName("primary")
    go.setDefault(True)
    go.clicked.connect(dlg.accept)
    widgets.footer(outer, [cancel, go], [all_one])
    # the height for the window's real width (Qt guesses wrapped text's height
    # from a narrow width and leaves the hint cut)
    outer.activate()
    dlg.resize(dlg.minimumWidth(), outer.totalHeightForWidth(dlg.minimumWidth()))
    dlg.combos, dlg.chosen_now, dlg.picture = combos, now, picture
    dlg.merge_button, dlg.separate_button, dlg.all_one_button = merge_button, separate_button, all_one
    if not show:
        return dlg
    if dlg.exec() != QDialog.Accepted:
        return None
    return now()
