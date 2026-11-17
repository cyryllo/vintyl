"""
Tests of the shared widgets (Switch, Segmented, Card, form_dialog) and of the
theme's colours (UI v2).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QDoubleSpinBox, QLineEdit

from vintyl.gui import theme
from vintyl.gui.widgets import Card, Segmented, Switch, form_dialog, value_of


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ---- colours ---------------------------------------------------------------------------------
def _luminance(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (text, background) pairs that must read: text of 13 px needs 4.5:1
PAIRS = [("ink", "panel"), ("ink", "window"), ("ink", "bar"), ("ink_2", "panel"), ("muted", "panel"),
         ("muted", "window"), ("accent_ink", "accent_soft"), ("accent_ink", "panel"), ("on_accent", "accent"),
         ("on_accent", "stop"), ("on_accent", "danger"), ("info_ink", "info_bg"), ("warn_ink", "warn_bg"),
         ("ink", "stat"), ("ink_2", "well"), ("disabled_text", "panel"), ("ok", "ok_bg"),
         ("code_ink", "code_bg")]


@pytest.mark.parametrize("look", ["light", "dark"])
@pytest.mark.parametrize("text,ground", PAIRS)
def test_every_text_colour_reads_on_its_background(look, text, ground):
    t = theme.TOKENS[look]
    assert contrast(t[text], t[ground]) >= 4.5, (look, text, ground, contrast(t[text], t[ground]))


def test_both_looks_have_the_same_tokens():
    assert set(theme.TOKENS["light"]) == set(theme.TOKENS["dark"])
    assert theme.TOKENS["light"]["accent"] == "#be185d" and theme.TOKENS["dark"]["sheet"] == "#f7f8fa"


# ---- Switch ----------------------------------------------------------------------------------
def test_a_switch_is_a_checkbox_with_a_switch_drawn(app):
    s = Switch("Mirror")
    s.resize(260, 30)
    seen = []
    s.toggled.connect(seen.append)
    QTest.mouseClick(s, Qt.LeftButton, Qt.NoModifier, s.rect().center())   # the whole row is clickable
    assert s.isChecked() and seen == [True]
    s.setFocus()
    QTest.keyClick(s, Qt.Key_Space)                                        # the keyboard works
    assert not s.isChecked()
    assert not s.grab().isNull()                                           # it draws, on and off
    s.setChecked(True)
    assert not s.grab().isNull() and value_of(s) is True
    assert s.sizeHint().width() > Switch.TRACK_W


# ---- Segmented -------------------------------------------------------------------------------
def test_segmented_works_as_a_combo_box(app):
    seg = Segmented()
    seg.addItem("Knife", "knife")
    seg.addItem("Pen", "pen")
    assert seg.count() == 2 and seg.currentIndex() == 0 and seg.currentData() == "knife"
    seen = []
    seg.currentIndexChanged.connect(seen.append)
    seg.setCurrentIndex(seg.findData("pen"))
    assert seg.currentData() == "pen" and seg.currentText() == "Pen" and seen == [1]
    seg.button(0).click()
    assert seg.currentData() == "knife" and seen == [1, 0]
    assert seg.findData("nothing") == -1 and value_of(seg) == "knife"


def test_segmented_in_a_grid(app):
    from vintyl.gui import icons
    seg = Segmented(columns=3)
    for k in range(9):
        seg.addItem("P%d" % k, k, icons.tabler("square"))
    lay = seg.layout()
    assert lay.rowCount() == 3 and lay.columnCount() == 3
    seg.setCurrentIndex(8)
    assert seg.currentData() == 8


# ---- Card and form_dialog --------------------------------------------------------------------
def test_a_card_has_a_title_and_rows(app):
    c = Card("Knife")
    spin = QDoubleSpinBox()
    row = c.add_row("Offset", spin)
    c.add_hint("Empty: from the cutter's settings.")
    assert c.title_label.text() == "Knife" and row.isAncestorOf(spin)


def test_form_dialog_returns_the_values_or_none(app):
    def fields():
        name = QLineEdit("My cutter")
        way = Segmented()
        way.addItem("out", "out")
        way.addItem("in", "in")
        size = QDoubleSpinBox()
        size.setValue(3.0)
        keep = Switch("Keep")
        return [("name", "Name", name), ("way", "Way", way), ("size", "Size", size), ("keep", None, keep)]

    rows = fields()
    dlg = form_dialog(None, "Test", rows, action="Create", hint="A hint", show=False)
    assert dlg.main_button.text() == "Create" and dlg.main_button.objectName() == "primary"

    def answer(accept, change):
        def go():
            for w in QApplication.topLevelWidgets():
                if w.isVisible() and w.windowTitle() == "Test":
                    change()
                    w.accept() if accept else w.reject()
                    return
            QTimer.singleShot(20, go)
        QTimer.singleShot(20, go)

    rows = fields()
    answer(True, lambda: (rows[1][2].setCurrentIndex(1), rows[3][2].setChecked(True)))
    got = form_dialog(None, "Test", rows)
    assert got == {"name": "My cutter", "way": "in", "size": 3.0, "keep": True}
    rows = fields()
    answer(False, lambda: None)
    assert form_dialog(None, "Test", rows) is None


def test_value_of_a_combo_box(app):
    c = QComboBox()
    c.addItem("A", "a")
    assert value_of(c) == "a"
    with pytest.raises(TypeError):
        value_of(object())


def test_a_question_returns_the_buttons_action(app):
    from PySide6.QtWidgets import QPushButton
    from vintyl.gui.widgets import ask

    def press(label):
        def go():
            for w in QApplication.topLevelWidgets():
                if w.isVisible() and w.windowTitle() == "Delete this cutter":
                    [b for b in w.findChildren(QPushButton) if b.text() == label][0].click()
                    return
            QTimer.singleShot(20, go)
        QTimer.singleShot(20, go)

    buttons = [("cancel", "Cancel", "cancel"), ("delete", "Delete", "danger")]
    press("Delete")
    assert ask(None, "Delete this cutter", "Delete it?", buttons) == "delete"
    press("Cancel")
    assert ask(None, "Delete this cutter", "Delete it?", buttons) is None
    dlg = ask(None, "Delete this cutter", "Delete it?", buttons, warning=True, show=False)
    assert [b.objectName() for b in dlg.findChildren(QPushButton)] == ["", "danger"]


def test_switches_and_segments_work_from_the_keyboard(app):
    """UI v2, 8: Tab reaches every switch and every segment; space changes them."""
    from PySide6.QtWidgets import QWidget, QVBoxLayout
    box = QWidget()
    lay = QVBoxLayout(box)
    sw = Switch("Mirror")
    seg = Segmented()
    seg.addItem("Out", "out")
    seg.addItem("In", "in")
    lay.addWidget(sw)
    lay.addWidget(seg)
    box.show()
    for w in [sw] + [seg.button(i) for i in range(seg.count())]:
        assert w.focusPolicy() & Qt.TabFocus, w
    sw.setFocus()
    QTest.keyClick(sw, Qt.Key_Space)
    assert sw.isChecked()
    seg.button(1).setFocus()
    QTest.keyClick(seg.button(1), Qt.Key_Space)
    assert seg.currentData() == "in"
    box.close()


def _wheel(widget, steps=-1):
    """One turn of the mouse wheel over the middle of `widget` (minus = down)."""
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    pos = QPointF(widget.rect().center())
    event = QWheelEvent(pos, QPointF(widget.mapToGlobal(widget.rect().center())), QPoint(0, 0),
                        QPoint(0, 120 * steps), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)


def test_the_wheel_changes_a_field_only_once_it_is_clicked(app):
    """Scrolling a panel must not change the lists and numbers passing under
    the mouse: the wheel goes on to the panel; a clicked field takes it."""
    from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget
    theme.apply(app, "light")
    inner = QWidget()
    lay = QVBoxLayout(inner)
    combo = QComboBox()
    for k in range(5):
        combo.addItem("item %d" % k)
    combo.setCurrentIndex(2)
    spin = QDoubleSpinBox()
    spin.setValue(5.0)
    lay.addWidget(combo)
    lay.addWidget(spin)
    edits = [QLineEdit() for _k in range(30)]               # something to scroll
    for e in edits:
        lay.addWidget(e)
    area = QScrollArea()
    area.setWidget(inner)
    area.resize(300, 200)
    area.show()
    QTest.qWait(20)
    edits[0].setFocus()                                     # the focus is elsewhere (Qt gave it to the list)
    QTest.qWait(10)
    assert combo.focusPolicy() == Qt.StrongFocus and spin.focusPolicy() == Qt.StrongFocus
    _wheel(combo)
    _wheel(spin)
    assert combo.currentIndex() == 2 and spin.value() == 5.0             # nothing changed ...
    assert area.verticalScrollBar().value() > 0                           # ... the panel scrolled
    spin.setFocus()
    QTest.qWait(10)
    _wheel(spin, 1)
    assert spin.value() == 6.0                                            # a clicked field takes the wheel
    area.close()
