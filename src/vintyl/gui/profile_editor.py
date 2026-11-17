"""
The cutter's settings window: everything about one machine (its port, the
way it connects, its command language, axes, knife, speed). In the main
window the user only chooses the machine.

A built-in profile changed here is saved as the user's copy (see
vintyl.core.profile.catalogue); "Restore factory settings" deletes that
copy. "New cutter" starts a profile of the user's own from the one shown.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from vintyl.core import profile as profiles
from vintyl.core import transport
from vintyl.gui import _, icons
from vintyl.gui import theme
from vintyl.gui import widgets


def _dspin(maximum, decimals=2, suffix=" mm", minimum=0.0, step=None):
    w = QDoubleSpinBox()
    w.setRange(minimum, maximum)
    w.setDecimals(decimals)
    w.setSuffix(suffix)
    if step:
        w.setSingleStep(step)
    return w


class _ProfileRow(QStyledItemDelegate):
    """A row of the cutter list: the name, and "built-in" / "own" on the right;
    the chosen one on the accent's soft background."""

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 42)

    def paint(self, p, option, index):
        p.save()
        try:
            r = option.rect
            name, kind = (index.data(Qt.DisplayRole) or "").split("\t", 1)
            chosen = bool(option.state & QStyle.State_Selected)
            if chosen:
                p.setRenderHint(QPainter.Antialiasing, True)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(theme.token("accent_soft")))
                p.drawRoundedRect(QRectF(r).adjusted(2, 2, -2, -2), 8, 8)
            font = p.font()
            font.setBold(chosen)
            p.setFont(font)
            p.setPen(QColor(theme.token("accent_ink") if chosen else theme.token("ink")))
            from PySide6.QtGui import QFontMetrics
            room = r.adjusted(12, 0, -96, 0)
            p.drawText(room, Qt.AlignVCenter | Qt.AlignLeft,
                       QFontMetrics(font).elidedText(name, Qt.ElideRight, room.width()))
            font.setBold(False)
            p.setFont(font)
            p.setPen(QColor(theme.token("muted")))
            p.drawText(r.adjusted(0, 0, -12, 0), Qt.AlignVCenter | Qt.AlignRight, kind)
        finally:
            p.restore()


class ProfileEditor(QDialog):
    """The cutters' settings (UI v2): on the left every cutter (built-in or
    the user's own), on the right the chosen one's fields in cards, in two
    columns. Opens on `entry` (an entry of profiles.catalogue()); `entries`:
    the list on the left (default: the catalogue). After exec(): self.chosen
    is the id to use now (a new profile's id, or the one saved), "" when one
    was deleted, None when nothing was saved."""

    def __init__(self, entry, parent=None, entries=None):
        super().__init__(parent)
        self.entry = entry
        self.chosen = None
        self.setWindowTitle(_("Cutter settings"))
        self.resize(1000, 700)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        outer.addLayout(middle, 1)

        # -- the cutters on the left
        side = QWidget()
        side.setObjectName("dialog_side")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(250)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 14, 10, 14)
        sl.setSpacing(8)
        head = QLabel(_("Cutters"))
        head.setObjectName("muted")
        sl.addWidget(head)
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        self.list = QListWidget()
        self.list.setObjectName("profile_list")
        self.list.setFrameShape(self.list.Shape.NoFrame)
        self.entries = entries if entries is not None else [e for e in profiles.catalogue() if e["profile"]]
        for e in self.entries:
            item = QListWidgetItem("%s\t%s" % (e["profile"].name, _("built-in") if e["builtin"] else _("own")))
            item.setData(Qt.UserRole, e["id"])
            self.list.addItem(item)
        self.list.setItemDelegate(_ProfileRow(self.list))
        sl.addWidget(self.list, 1)
        self.btn_new = QPushButton(icons.tabler("copy-plus"), _("New cutter (a copy)"))
        self.btn_new.setToolTip(_("A profile of your own, starting from these settings"))
        self.btn_new.clicked.connect(self.save_new)
        sl.addWidget(self.btn_new)
        middle.addWidget(side)

        # -- the chosen cutter's fields, in two columns of cards
        body = QVBoxLayout()
        body.setContentsMargins(16, 14, 16, 14)
        body.setSpacing(12)
        self.note = QLabel()
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        body.addWidget(self.note)
        cols = QHBoxLayout()
        cols.setSpacing(12)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(12)
        right.setSpacing(12)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        cols.setStretch(0, 1)
        cols.setStretch(1, 1)
        body.addLayout(cols, 1)
        middle.addLayout(body, 1)

        card = widgets.Card(_("Machine"))
        self.name = QLineEdit()
        self.width = _dspin(10000.0, 1, minimum=10.0)
        self.width.setToolTip(_("How wide the knife can cut (not how wide the material may be: "
                                "an \"870 mm\" cutter cuts about 780 mm)"))
        self.length = _dspin(100000.0, 0)
        self.length.setSpecialValueText(_("no limit (roll)"))
        card.add_row(_("Name"), self.name)
        card.add_row(_("Cutting width"), self.width)
        card.add_row(_("Length"), self.length)
        left.addWidget(card)

        card = widgets.Card(_("Connection"))
        self.connection = QComboBox()
        self.connection.addItem(_("USB printer (/dev/usb/lp…)"), "usb-printer")
        self.connection.addItem(_("serial port (/dev/ttyUSB…, /dev/ttyACM…)"), "serial")
        # long choices must not widen the column: the two columns stay equal
        for box in (self.connection,):
            box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(10)
        self.port = QComboBox()
        self.port.setEditable(True)
        self.port.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.port.setMinimumContentsLength(8)
        port_row = QWidget()
        pr = QHBoxLayout(port_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.setSpacing(8)
        pr.addWidget(self.port, 1)
        find = QPushButton(_("Find"))
        find.setToolTip(_("Look again for cutters plugged in"))
        find.clicked.connect(self._fill_ports)
        pr.addWidget(find)
        self.port_note = QLabel()
        self.port_note.setWordWrap(True)
        self.port_note.setTextFormat(Qt.RichText)
        self.port_note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.baud = QComboBox()
        self.baud.setEditable(True)
        for b in (9600, 19200, 38400, 57600, 115200):
            self.baud.addItem(str(b))
        self.flow = QComboBox()
        for code, label in (("none", _("none")), ("rtscts", _("hardware (RTS/CTS)")),
                            ("xonxoff", _("software (XON/XOFF)"))):
            self.flow.addItem(label, code)
        card.add_row(_("Connects as"), self.connection)
        card.add_row(_("Port"), port_row)
        card.add_row(None, self.port_note)
        self.baud_row = card.add_row(_("Port speed (baud)"), self.baud)
        self.flow_row = card.add_row(_("Flow control"), self.flow)
        left.addWidget(card)

        card = widgets.Card(_("Speed and force"))
        self.send_sf = widgets.Switch(_("sent by the computer"))
        self.speed = _dspin(200.0, 1, " cm/s")
        self.speed.setSpecialValueText(_("from the panel"))
        self.force = QSpinBox()
        self.force.setRange(0, 2000)
        self.force.setSuffix(" g")
        self.force.setSpecialValueText(_("from the panel"))
        self.pacing = QComboBox()
        self.pacing.addItem(_("everything at once"), "none")
        self.pacing.addItem(_("as fast as it cuts"), "time")
        self.pacing.setToolTip(_("Everything at once: the cutter keeps the job in its memory (the KI-375A). "
                                 "As fast as it cuts: for cutters with a small memory"))
        card.add_row(None, self.send_sf)
        self.sf_hint = card.add_hint(_("Off: the cutter takes them from its panel only; Vintyl reminds you "
                                       "of the material's values before Start."))
        self.speed_row = card.add_row(_("Speed"), self.speed)
        self.force_row = card.add_row(_("Force"), self.force)
        card.add_row(_("Sending"), self.pacing)
        left.addWidget(card)
        left.addStretch(1)

        card = widgets.Card(_("Commands"))
        self.language = QComboBox()
        self.language.addItem("HPGL", "hpgl")
        self.language.addItem("DMPL", "dmpl")
        self.dmpl_mode = QComboBox()
        for m in profiles.DMPL_MODES:
            self.dmpl_mode.addItem(str(m), m)
        self.units = _dspin(1000.0, 3, "", minimum=1.0)
        self.units.setToolTip(_("HPGL: 40 units per mm on most cutters. Check with a 20 mm square."))
        self.swap = widgets.Switch(_("swap X and Y"))
        self.inv_x = widgets.Switch(_("X the other way"))
        self.inv_y = widgets.Switch(_("Y the other way"))
        card.add_row(_("Language"), self.language)
        self.dmpl_row = card.add_row(_("DMPL mode"), self.dmpl_mode)
        card.add_row(_("Units per mm"), self.units)
        axes = QLabel(_("Axes"))
        axes.setObjectName("muted")
        card.add_row(None, axes)
        for w in (self.swap, self.inv_x, self.inv_y):
            card.add_row(None, w)
        right.addWidget(card)

        card = widgets.Card(_("Knife"))
        self.knife = _dspin(5.0, 2, step=0.05)
        self.knife.setToolTip(_("How far the blade tip trails the holder's axis. "
                                "A 45° blade: usually 0.20–0.30 mm."))
        self.overcut = _dspin(5.0, 2, step=0.1)
        self.overcut.setToolTip(_("Closed shapes are cut this far past their start, "
                                  "so the cut closes cleanly"))
        self.corner = _dspin(89.0, 0, "°")
        self.corner.setToolTip(_("Turns smaller than this count as straight: the knife is turned "
                                 "only at sharper corners, so curves are cut smoothly"))
        card.add_row(_("Knife offset"), self.knife)
        card.add_row(_("Overcut"), self.overcut)
        card.add_row(_("Corner from"), self.corner)
        card.add_hint(_("This cutter's own values. A material can have its own offset and overcut."))
        right.addWidget(card)
        right.addStretch(1)

        # -- the footer: restore (or delete) on the left; cancel and save on the right
        self.btn_reset = QPushButton()
        self.btn_reset.clicked.connect(self._reset_clicked)
        cancel = QPushButton(_("Cancel"))
        cancel.clicked.connect(self.reject)
        save = QPushButton(_("Save"))
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self.save)
        widgets.footer(outer, [cancel, save], [self.btn_reset])

        for w in (self.connection, self.language):
            w.currentIndexChanged.connect(self._update)
        self.send_sf.toggled.connect(self._update)
        self.port.currentTextChanged.connect(self._update)
        self._load(entry)
        self.list.setCurrentRow(next((i for i, e in enumerate(self.entries) if e["id"] == entry["id"]), -1))
        self.list.currentRowChanged.connect(self._switch)

    def _load(self, entry):
        """Fill the fields from a cutter's profile."""
        self.entry = entry
        p = entry["profile"]
        self.note.setText(_("Built-in profile: your changes are kept as your own copy; "
                            "\"Restore factory settings\" brings back the original.") if entry["builtin"]
                          else _("Your own cutter profile."))
        self.name.setText(p.name)
        self.width.setValue(p.width_mm)
        self.length.setValue(p.length_mm)
        self.connection.setCurrentIndex(max(0, self.connection.findData(p.connection)))
        self._fill_ports(p.port)
        self.baud.setCurrentText(str(p.baud))
        self.flow.setCurrentIndex(max(0, self.flow.findData(p.flow)))
        self.language.setCurrentIndex(max(0, self.language.findData(p.language)))
        self.dmpl_mode.setCurrentIndex(max(0, self.dmpl_mode.findData(p.dmpl_mode)))
        self.units.setValue(p.units_per_mm)
        self.swap.setChecked(p.swap_xy)
        self.inv_x.setChecked(p.invert_x)
        self.inv_y.setChecked(p.invert_y)
        self.knife.setValue(p.knife_offset_mm)
        self.overcut.setValue(p.overcut_mm)
        self.corner.setValue(p.corner_deg)
        self.send_sf.setChecked(p.send_speed_force)
        self.speed.setValue(p.speed_cm_s or 0.0)
        self.force.setValue(int(p.force_g or 0))
        self.pacing.setCurrentIndex(max(0, self.pacing.findData(p.pacing)))
        if entry["builtin"]:
            self.btn_reset.setText(_("Restore factory settings"))
            self.btn_reset.setEnabled(entry["changed"])
        else:
            self.btn_reset.setText(_("Delete this cutter"))
            self.btn_reset.setEnabled(True)
        self._update()

    def _changed(self):
        """The fields differ from the cutter they show (or cannot be read)."""
        try:
            return self.profile() != self.entry["profile"]
        except profiles.ProfileError:
            return True

    def _switch(self, row):
        """Another cutter chosen in the list: ask about changes, then show it."""
        if not 0 <= row < len(self.entries) or self.entries[row]["id"] == self.entry["id"]:
            return
        if self._changed():
            answer = widgets.ask(self, _("Unsaved changes"),
                                 _("Save the changes to \"%s\" first?") % self.entry["profile"].name,
                                 [("discard", _("Don't save"), "left"), ("cancel", _("Cancel"), "cancel"),
                                  ("save", _("Save"), "main")])
            if answer is None:                           # stay on this cutter
                back = next(i for i, e in enumerate(self.entries) if e["id"] == self.entry["id"])
                self.list.blockSignals(True)
                self.list.setCurrentRow(back)
                self.list.blockSignals(False)
                return
            if answer == "save" and self._write(self.entry["id"]):
                # the saved copy is now the cutter's entry
                fresh = {e["id"]: e for e in profiles.catalogue() if e["profile"]}
                self.entries = [fresh.get(e["id"], e) for e in self.entries]
        self._load(self.entries[row])

    def _reset_clicked(self):
        self.restore() if self.entry["builtin"] else self.delete()

    # ---- helpers -------------------------------------------------------------------------
    def _fill_ports(self, keep=None):
        current = keep if isinstance(keep, str) else self.port.currentText()
        self.port.blockSignals(True)
        self.port.clear()
        ports = transport.find_ports()
        if current and current not in ports:
            ports = [current] + ports
        self.port.addItems(ports)
        self.port.setCurrentText(current or (ports[0] if ports else ""))
        self.port.blockSignals(False)
        if hasattr(self, "port_note"):
            self._update()

    def _update(self, *_a):
        serial = self.connection.currentData() == "serial"
        self.baud_row.setVisible(serial)
        self.flow_row.setVisible(serial)
        self.dmpl_row.setVisible(self.language.currentData() == "dmpl")
        self.force_row.setVisible(self.send_sf.isChecked())
        self.sf_hint.setVisible(not self.send_sf.isChecked())
        port = self.port.currentText().strip()
        import os
        problem = transport.access_problem(port)
        if problem:
            text, color = problem, theme.token("warn_ink")
        elif port and not os.path.exists(port):
            text, color = _("Not plugged in now (or switched off)."), theme.token("muted")
        elif port:
            found = transport.device_name(port)
            text, color = ((_("Found: %s; you may use it.") % found) if found
                           else _("Found, and you may use it.")), theme.token("ok")
        else:
            text, color = "", theme.token("muted")
        # the port's state: a dot and a line, in the state's colour
        self.port_note.setText('<span style="color:%s">&#9679;</span>&nbsp; <span style="color:%s">%s</span>'
                               % (color, color, text.replace("<", "&lt;").replace("\n", "<br>")) if text else "")
        self.port_note.setVisible(bool(text))

    def profile(self):
        """The profile as the fields say (ProfileError when it cannot be used)."""
        p = self.entry["profile"]
        try:
            baud = int(self.baud.currentText())
        except ValueError:
            raise profiles.ProfileError(_("The port speed must be a whole number.")) from None
        new = dataclasses.replace(
            p, name=self.name.text().strip(), width_mm=self.width.value(), length_mm=self.length.value(),
            connection=self.connection.currentData(), port=self.port.currentText().strip(), baud=baud,
            flow=self.flow.currentData(), language=self.language.currentData(),
            dmpl_mode=self.dmpl_mode.currentData(), units_per_mm=self.units.value(),
            swap_xy=self.swap.isChecked(), invert_x=self.inv_x.isChecked(), invert_y=self.inv_y.isChecked(),
            knife_offset_mm=self.knife.value(), overcut_mm=self.overcut.value(), corner_deg=self.corner.value(),
            send_speed_force=self.send_sf.isChecked(), speed_cm_s=self.speed.value() or None,
            force_g=float(self.force.value()) if self.force.value() else None, pacing=self.pacing.currentData())
        if not new.name:
            raise profiles.ProfileError(_("Give the cutter a name."))
        return new.validate()

    def _write(self, pid):
        try:
            profiles.save_user(pid, self.profile())
        except (profiles.ProfileError, OSError) as e:
            widgets.warn(self, _("Cutter settings"), str(e))
            return False
        self.chosen = pid
        return True

    # ---- the buttons ---------------------------------------------------------------------
    def save(self):
        if self._write(self.entry["id"]):
            self.accept()

    def save_new(self, name=None):
        if not isinstance(name, str):
            field = QLineEdit(_("%s (mine)") % self.name.text().strip())
            field.setMinimumWidth(320)
            got = widgets.form_dialog(self, _("New cutter"), [("name", None, field)], action=_("Create"),
                                      hint=_("Name of the new cutter:"))
            name = (got or {}).get("name", "")
            if not name.strip():
                return
        self.name.setText(name.strip())
        if self._write(profiles.new_id(name.strip())):
            self.accept()

    def restore(self):
        if widgets.ask(self, _("Restore factory settings"),
                       _("Forget your changes of \"%s\" and use the settings it came with?")
                       % self.entry["profile"].name,
                       [("cancel", _("Cancel"), "cancel"), ("restore", _("Restore"), "main")]) != "restore":
            return
        profiles.delete_user(self.entry["id"])
        self.chosen = self.entry["id"]
        self.accept()

    def delete(self):
        if widgets.ask(self, _("Delete this cutter"),
                       _("Delete the cutter profile \"%s\"?") % self.entry["profile"].name,
                       [("cancel", _("Cancel"), "cancel"), ("delete", _("Delete"), "danger")]) != "delete":
            return
        profiles.delete_user(self.entry["id"])
        self.chosen = ""                       # the window chooses another one
        self.accept()
