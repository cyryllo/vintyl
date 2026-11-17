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
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

from vintyl.core import profile as profiles
from vintyl.core import transport
from vintyl.gui import _
from vintyl.gui import theme


def _dspin(maximum, decimals=2, suffix=" mm", minimum=0.0, step=None):
    w = QDoubleSpinBox()
    w.setRange(minimum, maximum)
    w.setDecimals(decimals)
    w.setSuffix(suffix)
    if step:
        w.setSingleStep(step)
    return w


class ProfileEditor(QDialog):
    """Edit the profile `pid` (an entry of profiles.catalogue()). After exec():
    self.chosen is the id to use now (a new profile's id, or the same), or
    None when nothing was saved."""

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.chosen = None
        self.setWindowTitle(_("Cutter settings"))
        lay = QVBoxLayout(self)
        p = entry["profile"]
        note = QLabel(_("Built-in profile: your changes are kept as your own copy; "
                        "\"Restore factory settings\" brings back the original.") if entry["builtin"]
                      else _("Your own cutter profile."))
        note.setWordWrap(True)
        lay.addWidget(note)

        cols = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        cols.addLayout(left)
        cols.addLayout(right)
        lay.addLayout(cols)

        # -- the machine
        box = QGroupBox(_("Machine"))
        f = QFormLayout(box)
        self.name = QLineEdit(p.name)
        self.width = _dspin(10000.0, 1, minimum=10.0)
        self.width.setValue(p.width_mm)
        self.width.setToolTip(_("How wide the knife can cut (not how wide the material may be: "
                                "an \"870 mm\" cutter cuts about 780 mm)"))
        self.length = _dspin(100000.0, 0)
        self.length.setValue(p.length_mm)
        self.length.setSpecialValueText(_("no limit (roll)"))
        f.addRow(_("Name"), self.name)
        f.addRow(_("Cutting width"), self.width)
        f.addRow(_("Length"), self.length)
        left.addWidget(box)

        # -- the connection
        box = QGroupBox(_("Connection"))
        f = QFormLayout(box)
        self.connection = QComboBox()
        self.connection.addItem(_("USB printer (/dev/usb/lp…)"), "usb-printer")
        self.connection.addItem(_("serial port (/dev/ttyUSB…, /dev/ttyACM…)"), "serial")
        self.connection.setCurrentIndex(max(0, self.connection.findData(p.connection)))
        self.port = QComboBox()
        self.port.setEditable(True)
        port_row = QWidget()
        pr = QHBoxLayout(port_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.addWidget(self.port, 1)
        find = QPushButton(_("Find"))
        find.setToolTip(_("Look again for cutters plugged in"))
        find.clicked.connect(self._fill_ports)
        pr.addWidget(find)
        self._fill_ports(p.port)
        self.port_note = QLabel()
        self.port_note.setWordWrap(True)
        self.port_note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.baud = QComboBox()
        self.baud.setEditable(True)
        for b in (9600, 19200, 38400, 57600, 115200):
            self.baud.addItem(str(b))
        self.baud.setCurrentText(str(p.baud))
        self.flow = QComboBox()
        for code, label in (("none", _("none")), ("rtscts", _("hardware (RTS/CTS)")),
                            ("xonxoff", _("software (XON/XOFF)"))):
            self.flow.addItem(label, code)
        self.flow.setCurrentIndex(max(0, self.flow.findData(p.flow)))
        f.addRow(_("Connects as"), self.connection)
        f.addRow(_("Port"), port_row)
        f.addRow(self.port_note)
        f.addRow(_("Port speed (baud)"), self.baud)
        f.addRow(_("Flow control"), self.flow)
        self.conn_form = f
        left.addWidget(box)

        # -- the commands
        box = QGroupBox(_("Commands"))
        f = QFormLayout(box)
        self.language = QComboBox()
        self.language.addItem("HPGL", "hpgl")
        self.language.addItem("DMPL", "dmpl")
        self.language.setCurrentIndex(max(0, self.language.findData(p.language)))
        self.dmpl_mode = QComboBox()
        for m in profiles.DMPL_MODES:
            self.dmpl_mode.addItem(str(m), m)
        self.dmpl_mode.setCurrentIndex(max(0, self.dmpl_mode.findData(p.dmpl_mode)))
        self.units = _dspin(1000.0, 3, "", minimum=1.0)
        self.units.setValue(p.units_per_mm)
        self.units.setToolTip(_("HPGL: 40 units per mm on most cutters. Check with a 20 mm square."))
        self.swap = QCheckBox(_("swap X and Y"))
        self.swap.setChecked(p.swap_xy)
        self.inv_x = QCheckBox(_("X the other way"))
        self.inv_x.setChecked(p.invert_x)
        self.inv_y = QCheckBox(_("Y the other way"))
        self.inv_y.setChecked(p.invert_y)
        axes = QWidget()
        al = QHBoxLayout(axes)
        al.setContentsMargins(0, 0, 0, 0)
        for w in (self.swap, self.inv_x, self.inv_y):
            al.addWidget(w)
        f.addRow(_("Language"), self.language)
        f.addRow(_("DMPL mode"), self.dmpl_mode)
        f.addRow(_("Units per mm"), self.units)
        f.addRow(_("Axes"), axes)
        self.cmd_form = f
        right.addWidget(box)

        # -- the knife
        box = QGroupBox(_("Knife"))
        f = QFormLayout(box)
        self.knife = _dspin(5.0, 2, step=0.05)
        self.knife.setValue(p.knife_offset_mm)
        self.knife.setToolTip(_("How far the blade tip trails the holder's axis. "
                                "A 45° blade: usually 0.20–0.30 mm."))
        self.overcut = _dspin(5.0, 2, step=0.1)
        self.overcut.setValue(p.overcut_mm)
        self.overcut.setToolTip(_("Closed shapes are cut this far past their start, "
                                  "so the cut closes cleanly"))
        self.corner = _dspin(89.0, 0, "°")
        self.corner.setValue(p.corner_deg)
        self.corner.setToolTip(_("Turns smaller than this count as straight: the knife is turned "
                                 "only at sharper corners, so curves are cut smoothly"))
        f.addRow(_("Knife offset"), self.knife)
        f.addRow(_("Overcut"), self.overcut)
        f.addRow(_("Corner from"), self.corner)
        right.addWidget(box)

        # -- speed and force
        box = QGroupBox(_("Speed and force"))
        f = QFormLayout(box)
        self.send_sf = QCheckBox(_("sent by the computer"))
        self.send_sf.setChecked(p.send_speed_force)
        self.send_sf.setToolTip(_("Off: the cutter takes them from its panel only (as the VEVOR "
                                  "KI-375A); the speed is then just for the time estimate"))
        self.speed = _dspin(200.0, 1, " cm/s")
        self.speed.setValue(p.speed_cm_s or 0.0)
        self.speed.setSpecialValueText(_("from the panel"))
        self.force = QSpinBox()
        self.force.setRange(0, 2000)
        self.force.setSuffix(" g")
        self.force.setValue(int(p.force_g or 0))
        self.force.setSpecialValueText(_("from the panel"))
        self.pacing = QComboBox()
        self.pacing.addItem(_("everything at once"), "none")
        self.pacing.addItem(_("as fast as it cuts"), "time")
        self.pacing.setCurrentIndex(max(0, self.pacing.findData(p.pacing)))
        self.pacing.setToolTip(_("Everything at once: the cutter keeps the job in its memory (the KI-375A). "
                                 "As fast as it cuts: for cutters with a small memory"))
        f.addRow(self.send_sf)
        f.addRow(_("Speed"), self.speed)
        f.addRow(_("Force"), self.force)
        f.addRow(_("Sending"), self.pacing)
        self.sf_form = f
        right.addWidget(box)
        right.addStretch(1)

        # -- the buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.btn_new = buttons.addButton(_("New cutter (a copy)"), QDialogButtonBox.ActionRole)
        self.btn_new.setToolTip(_("A profile of your own, starting from these settings"))
        if entry["builtin"]:
            self.btn_reset = buttons.addButton(_("Restore factory settings"), QDialogButtonBox.ResetRole)
            self.btn_reset.setEnabled(entry["changed"])
            self.btn_reset.clicked.connect(self.restore)
        else:
            self.btn_reset = buttons.addButton(_("Delete this cutter"), QDialogButtonBox.DestructiveRole)
            self.btn_reset.clicked.connect(self.delete)
        self.btn_new.clicked.connect(self.save_new)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        for w in (self.connection, self.language):
            w.currentIndexChanged.connect(self._update)
        self.send_sf.toggled.connect(self._update)
        self.port.currentTextChanged.connect(self._update)
        self._update()

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
        self.conn_form.setRowVisible(self.baud, serial)
        self.conn_form.setRowVisible(self.flow, serial)
        self.cmd_form.setRowVisible(self.dmpl_mode, self.language.currentData() == "dmpl")
        self.sf_form.setRowVisible(self.force, self.send_sf.isChecked())
        port = self.port.currentText().strip()
        import os
        problem = transport.access_problem(port)
        if problem:
            text, color = problem, theme.token("error")
        elif port and not os.path.exists(port):
            text, color = _("Not plugged in now (or switched off)."), theme.token("muted")
        elif port:
            found = transport.device_name(port)
            text, color = ((_("Found: %s; you may use it.") % found) if found
                           else _("Found, and you may use it.")), theme.token("ok")
        else:
            text, color = "", theme.token("muted")
        self.port_note.setText(text)
        self.port_note.setStyleSheet("color: %s" % color)
        self.conn_form.setRowVisible(self.port_note, bool(text))

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
            QMessageBox.warning(self, _("Cutter settings"), str(e))
            return False
        self.chosen = pid
        return True

    # ---- the buttons ---------------------------------------------------------------------
    def save(self):
        if self._write(self.entry["id"]):
            self.accept()

    def save_new(self, name=None):
        if not isinstance(name, str):
            name, ok = QInputDialog.getText(self, _("New cutter"), _("Name of the new cutter:"),
                                            text=_("%s (mine)") % self.name.text().strip())
            if not ok or not name.strip():
                return
        self.name.setText(name.strip())
        if self._write(profiles.new_id(name.strip())):
            self.accept()

    def restore(self):
        if QMessageBox.question(self, _("Restore factory settings"),
                                _("Forget your changes of \"%s\" and use the settings it came with?")
                                % self.entry["profile"].name) != QMessageBox.Yes:
            return
        profiles.delete_user(self.entry["id"])
        self.chosen = self.entry["id"]
        self.accept()

    def delete(self):
        if QMessageBox.question(self, _("Delete this cutter"),
                                _("Delete the cutter profile \"%s\"?") % self.entry["profile"].name) \
                != QMessageBox.Yes:
            return
        profiles.delete_user(self.entry["id"])
        self.chosen = ""                       # the window chooses another one
        self.accept()
