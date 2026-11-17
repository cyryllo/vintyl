"""
The materials window (UI v2): on the left every material, in two groups
(knife and pen); on the right the chosen one: its name and tool, the force
and speed for each cutter, the knife's (or the pen's) values, the job's
switches it sets, and a note shown before Start.

Built-in materials changed here are kept as the user's copy (see
vintyl.core.material); the bin on a built-in one brings it back as it came.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import dataclasses

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QSpinBox, QStyle,
                               QStyledItemDelegate, QToolButton, QVBoxLayout, QWidget)

from vintyl.core import material as mats
from vintyl.core import profile as profiles
from vintyl.gui import N_, _, icons, theme, widgets

HEADER_ROLE = Qt.UserRole + 2           # a group's title row (Knife, Pen), not a material
BLADE_NAMES = {"": "–", "45": N_("45° (standard)"), "30": N_("30° (thin materials)"),
               "60": N_("60° (thick materials)")}


def display_name(entry):
    """A built-in material's name in the window's language; the user's as written."""
    m = entry["material"]
    return _(m.name) if entry["builtin"] else m.name


class _MaterialRow(QStyledItemDelegate):
    """A row of the list: the tool's icon and the name; a group title in grey."""

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 30 if index.data(HEADER_ROLE) else 42)

    def paint(self, p, option, index):
        p.save()
        try:
            r = option.rect
            if index.data(HEADER_ROLE):
                p.setPen(QColor(theme.token("muted")))
                p.drawText(r.adjusted(12, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, index.data(Qt.DisplayRole))
                return
            chosen = bool(option.state & QStyle.State_Selected)
            if chosen:
                p.setRenderHint(QPainter.Antialiasing, True)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(theme.token("accent_soft")))
                p.drawRoundedRect(QRectF(r).adjusted(2, 2, -2, -2), 8, 8)
            icon = index.data(Qt.DecorationRole)
            if icon is not None:
                icon.paint(p, r.left() + 12, r.top() + (r.height() - 20) // 2, 20, 20)
            font = p.font()
            font.setBold(chosen)
            p.setFont(font)
            p.setPen(QColor(theme.token("accent_ink") if chosen else theme.token("ink")))
            room = r.adjusted(42, 0, -8, 0)
            p.drawText(room, Qt.AlignVCenter | Qt.AlignLeft,
                       QFontMetrics(font).elidedText(index.data(Qt.DisplayRole), Qt.ElideRight, room.width()))
        finally:
            p.restore()


def _spin(maximum, decimals, suffix, empty_text, step=None):
    """A field that can be empty: its lowest value shows `empty_text` (None)."""
    w = QDoubleSpinBox()
    w.setRange(-1.0 / 10 ** decimals, maximum)
    w.setDecimals(decimals)
    w.setSuffix(suffix)
    w.setSpecialValueText(empty_text)
    if step:
        w.setSingleStep(step)
    return w


def _get(spin):
    return None if spin.value() < 0 or spin.text() == spin.specialValueText() else spin.value()


def _set(spin, value):
    spin.setValue(spin.minimum() if value is None else value)


class MaterialEditor(QDialog):
    """The materials. Opens on the material `mid` (or the first one), with the
    force and speed shown for the cutter `pid`. After exec(): self.chosen is
    the id of the material to use now (or None when nothing was saved);
    self.test_material is set when "Knife test with these values" was
    pressed (the window then cuts the test with it)."""

    def __init__(self, parent=None, mid=None, pid=None):
        super().__init__(parent)
        self.setWindowTitle(_("Materials: cutting and drawing settings"))
        self.resize(1000, 700)
        self.chosen = None
        self.test_material = None
        self.entries = [e for e in mats.catalogue() if e["material"] is not None]
        self.cutters = [e for e in profiles.catalogue() if e["profile"] is not None]
        self.pid = pid if any(c["id"] == pid for c in self.cutters) else (self.cutters[0]["id"] if self.cutters
                                                                           else "")
        self.entry = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        middle = QHBoxLayout()
        middle.setSpacing(0)
        outer.addLayout(middle, 1)

        # -- the materials, knife ones and pen ones
        side = QWidget()
        side.setObjectName("dialog_side")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(270)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 14, 10, 14)
        sl.setSpacing(8)
        self.list = QListWidget()
        self.list.setObjectName("profile_list")
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setItemDelegate(_MaterialRow(self.list))
        sl.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.btn_new = QPushButton(icons.tabler("copy-plus"), _("New material"))
        self.btn_new.clicked.connect(lambda: self.save_new())
        self.btn_delete = QToolButton()
        self.btn_delete.setObjectName("square")
        self.btn_delete.setIcon(icons.tabler("trash"))
        self.btn_delete.clicked.connect(lambda: self.delete())
        row.addWidget(self.btn_new, 1)
        row.addWidget(self.btn_delete)
        sl.addLayout(row)
        middle.addWidget(side)

        # -- the chosen material (scrolling in a small window)
        body = widgets.scrolling_body(middle)
        body.setContentsMargins(16, 14, 16, 14)
        body.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(10)
        lab = QLabel(_("Name"))
        lab.setObjectName("field_label")
        self.name = QLineEdit()
        self.tool = widgets.Segmented()
        self.tool.addItem(_("Knife"), "knife", icons.own("drag-knife"))
        self.tool.addItem(_("Marker pen"), "pen", icons.tabler("pencil"))
        top.addWidget(lab)
        top.addWidget(self.name, 1)
        top.addWidget(self.tool)
        body.addLayout(top)
        cols = QHBoxLayout()
        cols.setSpacing(12)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(12)
        right.setSpacing(12)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        body.addLayout(cols, 1)

        # force and speed, for one cutter at a time
        card = widgets.Card()
        head = QHBoxLayout()
        title = QLabel(_("Force and speed"))
        title.setObjectName("card_title")
        self.for_cutter = QComboBox()
        for c in self.cutters:
            self.for_cutter.addItem(_("for: %s") % c["profile"].name, c["id"])
        self.for_cutter.setCurrentIndex(max(0, self.for_cutter.findData(self.pid)))
        head.addWidget(title)
        head.addWidget(self.for_cutter, 1)
        card.body.addLayout(head)
        self.force = QSpinBox()
        self.force.setRange(0, 2000)
        self.force.setSuffix(" g")
        self.force.setSpecialValueText(_("not set"))
        # speeds are shown in mm/s; kept in cm/s (the cutters' HPGL VS and the profile files)
        self.speed = _spin(2000.0, 0, " mm/s", _("not set"))
        card.add_row(_("Force"), self.force)
        card.add_row(_("Speed"), self.speed)
        self.panel_note = QFrame()
        self.panel_note.setObjectName("info")
        nl = QHBoxLayout(self.panel_note)
        nl.setContentsMargins(12, 10, 12, 10)
        note = QLabel(_("This cutter takes force and speed from its own panel only. Vintyl shows these "
                        "values before Start, to set them there."))
        note.setWordWrap(True)
        nl.addWidget(note)
        card.body.addWidget(self.panel_note)
        left.addWidget(card)
        self._per_cutter = {}
        self.for_cutter.currentIndexChanged.connect(self._cutter_changed)

        card = widgets.Card(_("Job"))
        self.mirror = widgets.Switch(_("Mirror (heat transfer vinyl)"))
        self.weed_frame = widgets.Switch(_("Frame round the design"))
        card.add_row(None, self.mirror)
        card.add_row(None, self.weed_frame)
        card.add_hint(_("Choosing this material sets these switches in the Job panel."))
        left.addWidget(card)
        left.addStretch(1)

        # the knife, or the pen
        self.knife_card = widgets.Card(_("Knife"))
        self.blade = QComboBox()
        for code in mats.BLADES:
            self.blade.addItem(_(BLADE_NAMES[code]) if code else "–", code)
        self.offset = _spin(5.0, 2, " mm", _("from the cutter"), 0.05)
        self.overcut = _spin(5.0, 2, " mm", _("from the cutter"), 0.1)
        self.knife_card.add_row(_("Blade"), self.blade)
        self.knife_card.add_row(_("Knife offset"), self.offset)
        self.knife_card.add_row(_("Overcut"), self.overcut)
        self.knife_card.add_hint(_("An empty field means the value from the cutter's settings."))
        right.addWidget(self.knife_card)
        self.pen_card = widgets.Card(_("Marker pen"))
        self.pen_width = _spin(5.0, 2, " mm", _("as in the window"), 0.05)
        self.pen_place = QComboBox()
        for code, label in (("on", _("on the line")), ("outside", _("outside the line")),
                            ("inside", _("inside the line"))):
            self.pen_place.addItem(label, code)
        self.pen_card.add_row(_("Pen width"), self.pen_width)
        self.pen_card.add_row(_("Draw"), self.pen_place)
        right.addWidget(self.pen_card)
        card = widgets.Card(_("Note"))
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText(_("E.g. how far the blade sticks out, which roll, what to check before "
                                       "cutting"))
        self.note.setFixedHeight(90)
        card.body.addWidget(self.note)
        card.add_hint(_("The note shows on the check list before Start."))
        right.addWidget(card)
        right.addStretch(1)
        self.tool.currentIndexChanged.connect(self._tool_changed)

        # -- the footer
        test = QPushButton(icons.own("drag-knife"), _("Knife test with these values"))
        test.clicked.connect(self._test)
        self.btn_test = test
        cancel = QPushButton(_("Cancel"))
        cancel.clicked.connect(self.reject)
        save = QPushButton(_("Save"))
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self.save)
        widgets.footer(outer, [cancel, save], [test])

        self._fill_list()
        start = mid if any(e["id"] == mid for e in self.entries) else (self.entries[0]["id"] if self.entries
                                                                         else None)
        if start is not None:
            self._load(next(e for e in self.entries if e["id"] == start))
            self._select(start)
        self.list.currentRowChanged.connect(self._switch)

    # ---- the list ------------------------------------------------------------------------------
    def _fill_list(self):
        self.list.blockSignals(True)
        self.list.clear()
        for tool, title in (("knife", _("Knife")), ("pen", _("Marker pen"))):
            group = [e for e in self.entries if e["material"].tool == tool]
            if not group:
                continue
            head = QListWidgetItem(title)
            head.setData(HEADER_ROLE, True)
            head.setFlags(Qt.NoItemFlags)
            self.list.addItem(head)
            for e in group:
                item = QListWidgetItem(icons.own("drag-knife") if tool == "knife" else icons.tabler("pencil"),
                                       display_name(e))
                item.setData(Qt.UserRole, e["id"])
                self.list.addItem(item)
        self.list.blockSignals(False)

    def _select(self, mid):
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == mid:
                self.list.setCurrentRow(i)
        self.list.blockSignals(False)

    def _switch(self, row):
        item = self.list.item(row)
        mid = item.data(Qt.UserRole) if item is not None else None
        if mid is None or self.entry is None or mid == self.entry["id"]:
            return
        if self._changed():
            answer = widgets.ask(self, _("Unsaved changes"),
                                 _("Save the changes to \"%s\" first?") % display_name(self.entry),
                                 [("discard", _("Don't save"), "left"), ("cancel", _("Cancel"), "cancel"),
                                  ("save", _("Save"), "main")])
            if answer is None:
                self._select(self.entry["id"])
                return
            if answer == "save" and not self._write(self.entry["id"]):
                self._select(self.entry["id"])
                return
        self._load(next(e for e in self.entries if e["id"] == mid))

    # ---- the fields ----------------------------------------------------------------------------
    def _load(self, entry):
        self.entry = entry
        m = entry["material"]
        self.name.setText(display_name(entry))
        self.tool.setCurrentIndex(self.tool.findData(m.tool))
        self._per_cutter = {k: dict(v) for k, v in (m.per_cutter or {}).items()}
        self._show_cutter_values()
        self.blade.setCurrentIndex(max(0, self.blade.findData(m.blade)))
        _set(self.offset, m.knife_offset_mm)
        _set(self.overcut, m.overcut_mm)
        _set(self.pen_width, m.pen_width_mm)
        self.pen_place.setCurrentIndex(max(0, self.pen_place.findData(m.pen_place)))
        self.mirror.setChecked(m.mirror)
        self.weed_frame.setChecked(m.weed_frame)
        self.note.setPlainText(_(m.note) if entry["builtin"] and m.note else m.note)
        self._tool_changed()
        self.btn_delete.setEnabled(not entry["builtin"] or entry["changed"])
        self.btn_delete.setToolTip(_("Restore factory settings") if entry["builtin"] else _("Delete material"))

    def _keep_cutter_values(self):
        """The force and speed fields into the per-cutter table (before another cutter is shown)."""
        pid = getattr(self, "_shown_pid", None)
        if pid is None:
            return
        force = float(self.force.value()) if self.force.value() > 0 else None
        speed = _get(self.speed)
        speed = speed / 10.0 if speed is not None else None          # mm/s on screen, cm/s kept
        values = {k: v for k, v in (("force_g", force), ("speed_cm_s", speed)) if v is not None}
        if values:
            self._per_cutter[pid] = values
        else:
            self._per_cutter.pop(pid, None)

    def _show_cutter_values(self):
        pid = self.for_cutter.currentData()
        self._shown_pid = None
        values = self._per_cutter.get(pid, {})
        self.force.setValue(int(values.get("force_g") or 0))
        cm = values.get("speed_cm_s")
        _set(self.speed, cm * 10.0 if cm is not None else None)
        self._shown_pid = pid
        cutter = next((c["profile"] for c in self.cutters if c["id"] == pid), None)
        self.panel_note.setVisible(cutter is not None and not cutter.send_speed_force)

    def _cutter_changed(self, _i):
        # the values typed for the cutter shown until now are kept, then the new one's shown
        self._keep_cutter_values()
        self._show_cutter_values()

    def _tool_changed(self, *_a):
        pen = self.tool.currentData() == "pen"
        self.knife_card.setVisible(not pen)
        self.pen_card.setVisible(pen)
        self.btn_test.setVisible(not pen)

    def material(self):
        """The material as the fields say (MaterialError when it cannot be used)."""
        self._keep_cutter_values()
        name = self.name.text().strip()
        base = self.entry["material"]
        # a built-in material's name stays as it came while it is not renamed
        if self.entry["builtin"] and name == _(base.name):
            name = base.name
        note = self.note.toPlainText()
        if self.entry["builtin"] and base.note and note == _(base.note):
            note = base.note
        return dataclasses.replace(
            base, name=name, tool=self.tool.currentData(), per_cutter=dict(self._per_cutter),
            blade=self.blade.currentData(), knife_offset_mm=_get(self.offset), overcut_mm=_get(self.overcut),
            pen_width_mm=_get(self.pen_width), pen_place=self.pen_place.currentData(),
            mirror=self.mirror.isChecked(), weed_frame=self.weed_frame.isChecked(), note=note).validate()

    def _changed(self):
        try:
            return self.material() != self.entry["material"]
        except mats.MaterialError:
            return True

    def _write(self, mid):
        try:
            mats.save_user(mid, self.material())
        except (mats.MaterialError, OSError) as e:
            widgets.warn(self, _("Materials"), str(e))
            return False
        self.chosen = mid
        fresh = {e["id"]: e for e in mats.catalogue() if e["material"] is not None}
        self.entries = list(fresh.values())
        self.entry = fresh[mid]
        self._fill_list()
        self._select(mid)
        return True

    # ---- the buttons ---------------------------------------------------------------------------
    def save(self):
        if self.entry is not None and self._write(self.entry["id"]):
            self.accept()

    def save_new(self, name=None):
        if not isinstance(name, str):
            field = QLineEdit(_("%s (mine)") % self.name.text().strip())
            field.setMinimumWidth(320)
            got = widgets.form_dialog(self, _("New material"), [("name", None, field)], action=_("Create"),
                                      hint=_("Name of the new material:"))
            name = (got or {}).get("name", "")
        if not name.strip():
            return None
        self.name.setText(name.strip())
        mid = mats.new_id(name.strip())
        self.entry = {"id": mid, "material": self.entry["material"], "builtin": False, "changed": False,
                      "error": None}
        if self._write(mid):
            self._load(self.entry)
            return mid
        return None

    def delete(self):
        e = self.entry
        if e is None or (e["builtin"] and not e["changed"]):
            return
        if e["builtin"]:
            question = (_("Restore factory settings"),
                        _("Forget your changes of \"%s\" and use the settings it came with?") % display_name(e),
                        [("cancel", _("Cancel"), "cancel"), ("go", _("Restore"), "main")])
        else:
            question = (_("Delete material"), _("Delete the material \"%s\"?") % display_name(e),
                        [("cancel", _("Cancel"), "cancel"), ("go", _("Delete"), "danger")])
        if widgets.ask(self, *question) != "go":
            return
        mats.delete_user(e["id"])
        self.entries = [x for x in mats.catalogue() if x["material"] is not None]
        self._fill_list()
        keep = e["id"] if e["builtin"] else (self.entries[0]["id"] if self.entries else None)
        if keep is not None:
            self._load(next(x for x in self.entries if x["id"] == keep))
            self._select(keep)
        self.chosen = keep

    def _test(self):
        try:
            self.test_material = self.material()
        except mats.MaterialError as e:
            widgets.warn(self, _("Materials"), str(e))
            return
        self.accept()
