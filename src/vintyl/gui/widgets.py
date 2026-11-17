"""
Shared widgets of the window and the dialogs (UI v2, "Vintyl - projekt okna",
page "Wersja 2"):

    Switch        an on/off switch (a QCheckBox drawn as a switch)
    Segmented     one of 2-9 choices as buttons side by side (or in a grid),
                  with the API of a QComboBox
    Card          a white card with a title, for a group of fields
    form_dialog() a dialog of fields: labels on the left, a hint, a footer
                  with the buttons on the right and the main one named by
                  what it does

Colours come from the theme's tokens (vintyl.gui.theme), so the dark look
works too.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QAbstractSpinBox, QButtonGroup, QCheckBox, QComboBox, QDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QToolButton,
                               QVBoxLayout, QWidget)

from vintyl.gui import _, theme

LABEL_WIDTH = 132           # the column of field labels in cards and dialogs


class Switch(QCheckBox):
    """An on/off switch: the label on the left, the switch on the right.

    A QCheckBox underneath, so isChecked(), toggled, setChecked() and the
    keyboard (Tab, space) work as before; only the drawing is new: a track
    of 36 x 20 px, a knob of 16 px, the accent colour when on."""

    TRACK_W, TRACK_H, KNOB = 36, 20, 16
    GAP = 12

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(30)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        w = (fm.horizontalAdvance(self.text()) + self.GAP if self.text() else 0) + self.TRACK_W + 4
        return QSize(w, max(30, fm.height() + 6))

    def minimumSizeHint(self):
        return QSize(self.TRACK_W + 4, 30)

    def hitButton(self, pos):
        # the whole row is clickable, not only a small box
        return self.rect().contains(pos)

    def _track_rect(self):
        r = self.rect()
        return QRectF(r.right() - self.TRACK_W - 1, r.center().y() - self.TRACK_H / 2 + 0.5,
                      self.TRACK_W, self.TRACK_H)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        track = self._track_rect()
        if self.text():
            p.setPen(QColor(theme.token("ink") if self.isEnabled() else theme.token("disabled_text")))
            text_rect = self.rect().adjusted(0, 0, -(self.TRACK_W + self.GAP), 0)
            p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap, self.text())
        on = self.isChecked()
        color = QColor(theme.token("accent") if on else theme.token("switch_off"))
        if not self.isEnabled():
            color.setAlpha(110)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(track, self.TRACK_H / 2, self.TRACK_H / 2)
        if self.hasFocus():                      # the keyboard's place: a ring round the track
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(theme.token("accent")), 1.5, Qt.DotLine))
            p.drawRoundedRect(track.adjusted(-3, -3, 3, 3), self.TRACK_H / 2 + 3, self.TRACK_H / 2 + 3)
        m = (self.TRACK_H - self.KNOB) / 2
        x = track.right() - m - self.KNOB if on else track.left() + m
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, track.top() + m, self.KNOB, self.KNOB))
        p.end()


class Segmented(QWidget):
    """One of a few choices as buttons side by side (columns=0) or in a grid
    of `columns`. The API of a QComboBox: addItem(text, data, icon),
    currentData(), currentIndex(), setCurrentIndex(), findData(), count(),
    itemData(), currentText(), and currentIndexChanged(int)."""

    currentIndexChanged = Signal(int)

    def __init__(self, parent=None, columns=0, icon_size=18):
        super().__init__(parent)
        self.setObjectName("segmented")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._columns = columns
        self._icon_size = icon_size
        self._data = []
        self._buttons = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idToggled.connect(self._toggled)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(3, 3, 3, 3)
        self._grid.setSpacing(4)

    def addItem(self, text, data=None, icon=None):
        b = QToolButton(self)
        b.setText(text)
        b.setCheckable(True)
        b.setAutoRaise(False)
        b.setFocusPolicy(Qt.StrongFocus)
        b.setSizePolicy(b.sizePolicy().horizontalPolicy().Expanding, b.sizePolicy().verticalPolicy())
        if icon is not None:
            b.setIcon(icon)
            b.setIconSize(QSize(self._icon_size, self._icon_size))
            # a grid of pictures (the fill patterns): the picture above its name
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if self._columns else Qt.ToolButtonTextBesideIcon)
        else:
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
        index = len(self._buttons)
        self._group.addButton(b, index)
        self._buttons.append(b)
        self._data.append(data)
        if self._columns:
            self._grid.addWidget(b, index // self._columns, index % self._columns)
        else:
            self._grid.addWidget(b, 0, index)
        if index == 0:
            b.setChecked(True)
        return b

    def _toggled(self, index, on):
        if on:
            self.currentIndexChanged.emit(index)

    def count(self):
        return len(self._buttons)

    def currentIndex(self):
        return self._group.checkedId()

    def setCurrentIndex(self, index):
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def currentData(self):
        i = self.currentIndex()
        return self._data[i] if 0 <= i < len(self._data) else None

    def itemData(self, index):
        return self._data[index]

    def currentText(self):
        i = self.currentIndex()
        return self._buttons[i].text() if i >= 0 else ""

    def itemText(self, index):
        return self._buttons[index].text()

    def findData(self, data):
        try:
            return self._data.index(data)
        except ValueError:
            return -1

    def button(self, index):
        return self._buttons[index]


class Card(QFrame):
    """A white card with a title (13 px, bold) and a column of rows."""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        self.title_label = None
        if title:
            self.title_label = QLabel(title)
            self.title_label.setObjectName("card_title")
            lay.addWidget(self.title_label)
        self.body = lay

    def add_row(self, label, widget):
        """A field with its label on the left (LABEL_WIDTH px); label None:
        the widget across the whole card. Returns the row (to hide it)."""
        if label is None:
            self.body.addWidget(widget)
            return widget
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        lab = QLabel(label)
        lab.setObjectName("field_label")
        lab.setFixedWidth(LABEL_WIDTH)
        lab.setBuddy(widget)
        h.addWidget(lab)
        h.addWidget(widget, 1)
        self.body.addWidget(row)
        return row

    def add_hint(self, text):
        hint = QLabel(text)
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        self.body.addWidget(hint)
        return hint


def footer(parent_layout, buttons_right, buttons_left=()):
    """The dialog's footer: a white strip with a line on top, buttons on the
    right (the last one is the main one) and optionally on the left."""
    bar = QFrame()
    bar.setObjectName("footer")
    h = QHBoxLayout(bar)
    h.setContentsMargins(16, 12, 16, 12)
    h.setSpacing(8)
    for b in buttons_left:
        h.addWidget(b)
    h.addStretch(1)
    for b in buttons_right:
        h.addWidget(b)
    parent_layout.addWidget(bar)
    return bar


def value_of(widget):
    """The value of a field, whatever its kind."""
    if isinstance(widget, (QComboBox, Segmented)):
        return widget.currentData()
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QLineEdit):
        return widget.text()
    if isinstance(widget, QAbstractSpinBox):
        return widget.value()
    raise TypeError("no value for %r" % (widget,))


def form_dialog(parent, title, rows, action=None, hint=None, extra=None, left=None, show=True):
    """A dialog of fields. rows: [(key, label, widget)], label None = the
    widget across the dialog; action: the main button's text (what it does;
    default "OK"); hint: a line under the fields; extra(layout): more widgets
    under the fields; left: a widget left of the fields (a preview).
    Returns {key: value} or None (cancelled). show=False returns the dialog
    instead, not run (for tests and for callers that run it themselves)."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    middle = QHBoxLayout()
    middle.setContentsMargins(16, 16, 16, 16)
    middle.setSpacing(16)
    if left is not None:
        middle.addWidget(left, 0, Qt.AlignTop)
    card = Card()
    for key, label, widget in rows:
        card.add_row(label, widget)
    if hint:
        card.add_hint(hint)
    if extra is not None:
        extra(card.body)
    middle.addWidget(card, 1)
    outer.addLayout(middle, 1)
    cancel = QPushButton(_("Cancel"))
    main = QPushButton(action or _("OK"))
    main.setObjectName("primary")
    main.setDefault(True)
    cancel.clicked.connect(dlg.reject)
    main.clicked.connect(dlg.accept)
    footer(outer, [cancel, main])
    dlg.main_button = main
    dlg.rows = rows
    if not show:
        return dlg
    if dlg.exec() != QDialog.Accepted:
        return None
    return {key: value_of(widget) for key, _label, widget in rows if key}
