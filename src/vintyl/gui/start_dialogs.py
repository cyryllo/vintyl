"""
The windows before something is sent to the cutter (UI v2):

    confirm_start()       the check list before Start: the cutter, the tool,
                          the material; the force and speed to set on the
                          cutter's panel (or that Vintyl sends); the points to
                          check; the mirror's warning; the material's note
    confirm_knife_test()  the knife test: its picture, the question, what to
                          read from it after cutting

Both return True to go on. They are module functions, so the tests can
answer them without a window.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from vintyl.gui import _, icons, theme, widgets


def _checks(card, items):
    """Rows with a green check mark before each point."""
    mark = icons.tabler("check", theme.token("ok")).pixmap(18, 18)
    for text in items:
        row = QHBoxLayout()
        row.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(mark)
        label = QLabel(text)
        label.setWordWrap(True)
        row.addWidget(icon, 0, Qt.AlignTop)
        row.addWidget(label, 1)
        card.body.addLayout(row)


def _values_card(values):
    """The force and speed in large type, on the information colour."""
    title, force, speed = values
    box = QFrame()
    box.setObjectName("info")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(6)
    head = QLabel(title)
    head.setObjectName("info_title")
    lay.addWidget(head)
    grid = QGridLayout()
    grid.setHorizontalSpacing(24)
    # both are always shown: a value the material has not got for this cutter
    # is a dash and a note, so it does not look forgotten by the program
    for col, (name, value) in enumerate(((_("Force"), force), (_("Speed"), speed))):
        small = QLabel(name)
        big = QLabel(value if value is not None else "–")
        big.setObjectName("big_value")
        grid.addWidget(small, 0, col)
        grid.addWidget(big, 1, col)
        if value is None:
            missing = QLabel(_("not in the material: as the cutter has it now"))
            missing.setWordWrap(True)
            grid.addWidget(missing, 2, col)
    lay.addLayout(grid)
    return box


def _dialog(parent, title):
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(560)
    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    body = QVBoxLayout()
    body.setContentsMargins(18, 16, 18, 16)
    body.setSpacing(12)
    outer.addLayout(body, 1)
    return dlg, outer, body


def _footer(dlg, outer, go_text, go_icon):
    # spare height goes below the content, not between a card's lines
    outer.itemAt(0).layout().addStretch(1)
    cancel = QPushButton(_("Cancel"))
    cancel.clicked.connect(dlg.reject)
    go = QPushButton(go_icon, go_text)
    go.setObjectName("primary")
    go.setDefault(True)
    go.clicked.connect(dlg.accept)
    widgets.footer(outer, [cancel, go])
    dlg.go_button = go
    # the height for the window's real width: Qt guesses wrapped text's
    # height from a narrow width and leaves the window too tall
    outer.activate()
    dlg.resize(dlg.minimumWidth(), outer.totalHeightForWidth(dlg.minimumWidth()))


def confirm_start(parent, cutter, port, pen, material_name, values, panel_only, mirror, note, show=True):
    """The check list before Start. values: (title, force text, speed text)
    or None; panel_only: the cutter takes force and speed from its panel;
    True = go on. show=False returns the dialog, not run (for tests)."""
    dlg, outer, body = _dialog(parent, _("Draw now?") if pen else _("Cut now?"))
    # what is going to happen: which cutter, which tool, which material
    facts = QLabel(_("Cutter: <b>%(cutter)s</b> (%(port)s) &nbsp;&nbsp; Tool: <b>%(tool)s</b>"
                     " &nbsp;&nbsp; Material: <b>%(material)s</b>")
                   % {"cutter": cutter, "port": port or _("no port"),
                      "tool": _("Marker pen") if pen else _("Knife"), "material": material_name or "–"})
    facts.setWordWrap(True)
    body.addWidget(facts)
    if values is not None:
        body.addWidget(_values_card(values))
    card = widgets.Card(_("Check before you go on"))
    if pen:
        items = [_("The pen (not the knife) is in the holder, its tip just above the paper"),
                 _("The force on the cutter's panel is low, for a pen"),
                 _("The paper is under the pinch rollers"),
                 _("The origin is set (Origin key) where the drawing should start")]
    else:
        items = [_("The knife is in the holder"),
                 _("The material is under the pinch rollers"),
                 _("The origin is set (Origin key) where the design should start")]
    if values is None and panel_only:
        items.append(_("Speed and force are set on the cutter's panel"))
    _checks(card, items)
    body.addWidget(card)
    if mirror:
        warn = QFrame()
        warn.setObjectName("warn")
        wl = QHBoxLayout(warn)
        wl.setContentsMargins(12, 10, 12, 10)
        icon = QLabel()
        icon.setPixmap(icons.tabler("alert-triangle", theme.token("warn_ink")).pixmap(20, 20))
        text = QLabel(_("<b>Mirror on.</b> The vinyl's shiny side (the carrier) down, the matt side up to "
                        "the knife."))
        text.setWordWrap(True)
        wl.addWidget(icon, 0, Qt.AlignTop)
        wl.addWidget(text, 1)
        body.addWidget(warn)
    if note:
        n = QLabel(_("Note of the material: %s") % note)
        n.setObjectName("muted")
        n.setWordWrap(True)
        body.addWidget(n)
    hint = QLabel(_("To stop the cutter at once: Test (pause) or Reset on its panel."))
    hint.setObjectName("muted")
    hint.setWordWrap(True)
    body.addWidget(hint)
    # "Cut it", not "Cut": the button's own word ("Cut" is a menu's word, "Wytnij")
    _footer(dlg, outer, _("Draw") if pen else _("Cut it"), icons.tabler("player-play", "#ffffff"))
    if not show:
        return dlg
    return dlg.exec() == QDialog.Accepted


def confirm_knife_test(parent, cutter, size_mm, test_paths, values=None, show=True):
    """The knife test: its picture, the question, what to look at after
    cutting. values as in confirm_start (or None). True = cut it."""
    from vintyl.gui.canvas import shape_icon
    dlg, outer, body = _dialog(parent, _("Knife test"))
    top = QHBoxLayout()
    top.setSpacing(16)
    picture = QLabel()
    picture.setPixmap(shape_icon(test_paths, 88, theme.token("accent")).pixmap(88, 88))
    question = QLabel(_("Cut the knife test on <b>%(cutter)s</b>: a %(size)g mm square with a triangle, "
                        "near the origin?") % {"cutter": cutter, "size": size_mm})
    question.setWordWrap(True)
    top.addWidget(picture)
    top.addWidget(question, 1)
    body.addLayout(top)
    if values is not None:
        body.addWidget(_values_card(values))
    card = widgets.Card(_("After cutting"))
    _checks(card, [_("Peel the triangle off: it should come away cleanly, and the backing must not be cut through"),
                   _("Too shallow: more force on the cutter's panel. Marks in the backing: less"),
                   _("Move the origin on, so the design is not cut over the test")])
    body.addWidget(card)
    _footer(dlg, outer, _("Cut the test"), icons.own("drag-knife", "#ffffff"))
    if not show:
        return dlg
    return dlg.exec() == QDialog.Accepted
