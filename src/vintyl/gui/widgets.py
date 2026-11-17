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
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPen
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


# ---- the element list's rows ---------------------------------------------------------------------
from PySide6.QtWidgets import QStyle, QStyledItemDelegate  # noqa: E402

ICON_ROLE = Qt.UserRole + 1           # an item's type icon (a QIcon)


class ElementRowDelegate(QStyledItemDelegate):
    """A row of the element list (UI v2): the cutting order's number, the
    type's icon, the name, and scissors on the right. The cut / not cut state
    is still the item's check state (so the list works as before); the
    scissors show it and a click on them changes it. A row not cut is grey
    and its name crossed out."""

    ROW_H = 40
    SCISSORS = 28

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.ROW_H)

    def _scissors_rect(self, rect):
        return QRectF(rect.right() - self.SCISSORS - 6, rect.center().y() - self.SCISSORS / 2 + 1,
                      self.SCISSORS, self.SCISSORS)

    @staticmethod
    def is_cut(index):
        # the check state comes back as a number from the model
        state = index.data(Qt.CheckStateRole)
        return state is not None and Qt.CheckState(state) == Qt.Checked

    def paint(self, p, option, index):
        # drawn between save() and restore() whatever happens: an error half-way
        # through must not leave the painter unbalanced (Qt then crashes)
        p.save()
        try:
            self._paint(p, option, index)
        finally:
            p.restore()

    def _paint(self, p, option, index):
        from vintyl.gui import icons
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        cut = self.is_cut(index)
        if selected:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.token("accent_soft")))
            p.drawRoundedRect(QRectF(r).adjusted(2, 2, -2, -2), 8, 8)
        muted = QColor(theme.token("muted"))
        ink = QColor(theme.token("ink") if cut else theme.token("disabled_text"))
        p.setPen(muted)
        p.drawText(QRectF(r.left() + 8, r.top(), 22, r.height()), Qt.AlignVCenter | Qt.AlignRight,
                   str(index.row() + 1))
        icon = index.data(ICON_ROLE)
        if icon is not None:
            mode = QIcon.Mode.Normal if cut else QIcon.Mode.Disabled
            icon.paint(p, r.left() + 38, r.top() + (r.height() - 20) // 2, 20, 20, Qt.AlignCenter, mode)
        font = p.font()
        font.setBold(selected)
        font.setStrikeOut(not cut)
        p.setFont(font)
        p.setPen(QColor(theme.token("accent_ink")) if selected and cut else ink)
        name_rect = QRectF(r.left() + 66, r.top(), r.width() - 66 - self.SCISSORS - 14, r.height())
        p.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft,
                   QFontMetrics(font).elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight,
                                                 int(name_rect.width())))
        icons.tabler("scissors", theme.token("accent") if cut else theme.token("disabled_icon")).paint(
            p, self._scissors_rect(r).adjusted(4, 4, -4, -4).toRect())

    def editorEvent(self, event, model, option, index):
        # a click on the scissors: cut / not cut (the item's check state, as before)
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton \
                and self._scissors_rect(option.rect).contains(event.position()):
            state = Qt.Unchecked if self.is_cut(index) else Qt.Checked
            model.setData(index, state, Qt.CheckStateRole)
            return True
        return super().editorEvent(event, model, option, index)


class ToolTile(QToolButton):
    """A button of the tool strip and of a tool set (UI v2): the icon over the
    name; `has_set` draws a small triangle in the lower left corner (the
    category opens a set), `hint` a shortcut in small type under the name."""

    def __init__(self, parent=None, has_set=False, hint=""):
        super().__init__(parent)
        self.has_set = has_set
        self.hint = hint
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setAutoRaise(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not (self.has_set or self.hint):
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        color = QColor(theme.token("accent_ink") if self.isChecked() else theme.token("muted"))
        if self.has_set:
            from PySide6.QtGui import QPolygonF
            from PySide6.QtCore import QPointF
            r = self.rect()
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawPolygon(QPolygonF([QPointF(r.left() + 5, r.bottom() - 4), QPointF(r.left() + 10, r.bottom() - 4),
                                     QPointF(r.left() + 5, r.bottom() - 9)]))
        if self.hint:
            font = self.font()
            font.setPointSizeF(max(6.0, font.pointSizeF() * 0.8))
            p.setFont(font)
            p.setPen(color)
            p.drawText(self.rect().adjusted(0, 0, 0, -4), Qt.AlignHCenter | Qt.AlignBottom, self.hint)
        p.end()
