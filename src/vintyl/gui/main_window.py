"""
The Vintyl main window: ribbon on top, options of the selected element under
it, the job panel on the left, the material in the middle, drawing tools on
the right (the layout of the design proposal of 15.11.2026).

This step: open SVG files, draw rectangles, ellipses and lines, move and
resize elements, choose which are cut, pick the cutter profile and save the
cutter file (.hpgl / .dmpl). Sending to the cutter, the knife preview, knife
offset and overcut come in later steps; their controls are shown greyed out.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import dataclasses
import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSizePolicy,
                               QToolBar, QVBoxLayout, QWidget)

from vintyl import __version__
from vintyl.core import profile as profiles
from vintyl.core import shapes
from vintyl.core.design import Design, Element
from vintyl.core.job import JobError, build_job
from vintyl.core.loaders import LoadError, load_svg
from vintyl.core.profile import ProfileError
from vintyl.gui import _
from vintyl.gui import icons
from vintyl.gui.canvas import MaterialView

LATER = _("Comes in a later step of Vintyl")
PLACE_MARGIN_MM = 10.0        # a new file is placed this far from the origin


def _spin(maximum=10000.0, decimals=2, suffix=" mm", minimum=-10000.0):
    s = QDoubleSpinBox()
    s.setRange(minimum, maximum)
    s.setDecimals(decimals)
    s.setSuffix(suffix)
    s.setKeyboardTracking(False)
    return s


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vintyl")
        self.setWindowIcon(icons.app_icon())
        self.design = Design()
        self.selected = None
        self.counter = {}
        self.last_job = None              # the last successful build (for the summary)
        self.profile_names = profiles.builtin_names()
        self.profile = profiles.load_builtin(self.profile_names[0])
        self._updating = False

        self.view = MaterialView()
        self._make_actions()
        self._make_menu()
        self._make_ribbon()
        self._make_tool_strip()

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._make_options_bar())
        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        middle.addWidget(self._make_left_panel())
        middle.addWidget(self.view, 1)
        outer.addLayout(middle, 1)
        self.setCentralWidget(central)

        self.cursor_label = QLabel()
        self.profile_label = QLabel()
        self.statusBar().addWidget(self.cursor_label)
        self.statusBar().addPermanentWidget(self.profile_label)

        s = self.view.signals
        s.selected.connect(self._on_selected)
        s.moved.connect(self._on_moved)
        s.drawn.connect(self._on_drawn)
        s.line_drawn.connect(self._on_line_drawn)
        s.cursor.connect(lambda x, y: self.cursor_label.setText(_("Pointer: %.1f / %.1f mm") % (x, y)))
        self.resize(1440, 900)
        self._profile_changed(self.profile_box.currentIndex())   # fills the panel and draws

    # ---- actions, menu, ribbon, tools ----------------------------------------
    def _action(self, text, slot, icon=None, shortcut=None, tip=None, enabled=True):
        a = QAction(text, self)
        if icon:
            a.setIcon(icons.tabler(icon))
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setToolTip(tip)
            a.setStatusTip(tip)
        if slot is not None:
            a.triggered.connect(slot)
        a.setEnabled(enabled)
        return a

    def _make_actions(self):
        self.act_new = self._action(_("New"), self.new_design, "file-plus", QKeySequence.New,
                                    _("Start an empty design"))
        self.act_open = self._action(_("Open SVG"), lambda: self.import_svg(), "folder-open", QKeySequence.Open,
                                     _("Add the shapes of an SVG file to the design"))
        self.act_save_cut = self._action(_("Save .hpgl"), lambda: self.save_cutter_file(), "device-floppy",
                                         "Ctrl+Shift+S", _("Save exactly what would go to the cutter, as a file"))
        self.act_delete = self._action(_("Delete"), self.delete_selected, "trash", QKeySequence.Delete,
                                       _("Delete the selected element"))
        self.act_fit = self._action(_("Fit"), self.view.fit_requested, "zoom-scan", "Ctrl+0",
                                    _("Show the whole material and design"))
        self.act_knife = self._action(_("Knife path"), None, "route", tip=LATER, enabled=False)
        self.act_connect = self._action(_("Connect"), None, "plug-connected", tip=LATER, enabled=False)
        self.act_profile = self._action(_("Profile"), None, "settings-2", tip=LATER, enabled=False)
        self.act_quit = self._action(_("Quit"), self.close, None, QKeySequence.Quit)

    def _make_menu(self):
        mb = self.menuBar()
        m = mb.addMenu(_("&File"))
        for a in (self.act_new, self.act_open, self.act_save_cut, None, self.act_quit):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Edit"))
        m.addAction(self.act_delete)
        m = mb.addMenu(_("&Cutter"))
        for a in (self.act_connect, self.act_profile):
            m.addAction(a)
        m = mb.addMenu(_("&View"))
        for a in (self.act_fit, self.act_knife):
            m.addAction(a)
        m = mb.addMenu(_("&Help"))
        m.addAction(self._action(_("About Vintyl"), self.about))

    def _make_ribbon(self):
        tb = QToolBar(_("Main"))
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        for a in (self.act_new, self.act_open, self.act_save_cut, None, self.act_delete, None,
                  self.act_fit, self.act_knife, None, self.act_connect, self.act_profile):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.addToolBar(Qt.TopToolBarArea, tb)

    def _make_tool_strip(self):
        tb = QToolBar(_("Tools"))
        tb.setObjectName("tool_strip")
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))
        group = QActionGroup(self)
        self.tool_actions = {}
        for key, text, icon in (("select", _("Select and move"), "pointer"),
                                ("rectangle", _("Rectangle"), "square"),
                                ("ellipse", _("Ellipse"), "circle"),
                                ("line", _("Line"), "line")):
            a = self._action(text, lambda _c=False, k=key: self.set_tool(k), icon, tip=text)
            a.setCheckable(True)
            group.addAction(a)
            tb.addAction(a)
            self.tool_actions[key] = a
        self.tool_actions["select"].setChecked(True)
        self.addToolBar(Qt.RightToolBarArea, tb)

    def set_tool(self, tool):
        self.tool_actions[tool].setChecked(True)
        self.view.set_tool(tool)

    # ---- options bar: the selected element ------------------------------------
    def _make_options_bar(self):
        bar = QWidget()
        bar.setObjectName("options_bar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 4, 10, 4)
        self.opt_x, self.opt_y = _spin(), _spin()
        self.opt_w, self.opt_h = _spin(minimum=0.0), _spin(minimum=0.0)
        for label, spin, tip in ((_("X"), self.opt_x, _("Left edge, along the material from the origin")),
                                 (_("Y"), self.opt_y, _("Bottom edge, across the material from the origin")),
                                 (_("Width"), self.opt_w, None), (_("Height"), self.opt_h, None)):
            lab = QLabel(label)
            lab.setBuddy(spin)
            if tip:
                spin.setToolTip(tip)
            row.addWidget(lab)
            row.addWidget(spin)
            spin.valueChanged.connect(self._options_changed)
        self.opt_cut = QCheckBox(_("Cut this element"))
        self.opt_cut.toggled.connect(self._options_changed)
        row.addSpacing(16)
        row.addWidget(self.opt_cut)
        row.addStretch(1)
        self.options_widgets = (self.opt_x, self.opt_y, self.opt_w, self.opt_h, self.opt_cut)
        return bar

    def _show_options(self):
        self._updating = True
        e = self.selected
        for w in self.options_widgets:
            w.setEnabled(e is not None)
        if e is not None:
            xmin, xmax, ymin, ymax = e.bounds
            self.opt_x.setValue(xmin)
            self.opt_y.setValue(-ymax)            # bottom edge, material y (up)
            self.opt_w.setValue(xmax - xmin)
            self.opt_h.setValue(ymax - ymin)
            self.opt_cut.setChecked(e.cut)
        self._updating = False

    def _options_changed(self):
        e = self.selected
        if self._updating or e is None:
            return
        w, h = self.opt_w.value(), self.opt_h.value()
        if (w, h) != tuple(round(v, 2) for v in e.size) and w > 0 and h > 0:
            e.set_size(w, h)
        _xmin, _xmax, _ymin, ymax = e.bounds
        e.move_by(self.opt_x.value() - e.bounds[0], -self.opt_y.value() - ymax)
        e.cut = self.opt_cut.isChecked()
        self.refresh()

    # ---- left panel: project, cutter, job --------------------------------------
    def _make_left_panel(self):
        panel = QWidget()
        panel.setObjectName("job_panel")
        panel.setFixedWidth(340)
        col = QVBoxLayout(panel)
        col.setContentsMargins(10, 10, 10, 10)
        col.setSpacing(10)

        box = QGroupBox(_("Project"))
        lay = QVBoxLayout(box)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        self.element_list = QListWidget()
        self.element_list.itemChanged.connect(self._list_item_changed)
        self.element_list.currentRowChanged.connect(self._list_row_changed)
        lay.addWidget(self.element_list)
        btns = QHBoxLayout()
        self.btn_up = QPushButton(icons.tabler("arrow-up"), "")
        self.btn_up.setToolTip(_("Cut earlier"))
        self.btn_up.setAccessibleName(_("Move up"))
        self.btn_down = QPushButton(icons.tabler("arrow-down"), "")
        self.btn_down.setToolTip(_("Cut later"))
        self.btn_down.setAccessibleName(_("Move down"))
        self.btn_up.clicked.connect(lambda: self.move_selected(-1))
        self.btn_down.clicked.connect(lambda: self.move_selected(1))
        btns.addWidget(self.btn_up)
        btns.addWidget(self.btn_down)
        btns.addStretch(1)
        lay.addLayout(btns)
        col.addWidget(box, 1)

        box = QGroupBox(_("Cutter"))
        form = QFormLayout(box)
        self.profile_box = QComboBox()
        for name in self.profile_names:
            self.profile_box.addItem(profiles.load_builtin(name).name, name)
        self.profile_box.currentIndexChanged.connect(self._profile_changed)
        form.addRow(_("Profile"), self.profile_box)
        self.port_label = QLabel(_("not connected (sending comes later)"))
        form.addRow(_("Port"), self.port_label)
        self.knife = _spin(5, 2, minimum=0)
        self.overcut = _spin(5, 2, minimum=0)
        for w in (self.knife, self.overcut):
            w.setEnabled(False)
            w.setToolTip(LATER)
        form.addRow(_("Knife offset"), self.knife)
        form.addRow(_("Overcut"), self.overcut)
        self.speed = _spin(80, 1, " cm/s", minimum=0)
        self.force = _spin(1000, 0, " g", minimum=0)
        for w in (self.speed, self.force):
            w.setSpecialValueText(_("from the panel"))
            w.setToolTip(_("Empty: the cutter uses what is set on its panel"))
            w.valueChanged.connect(lambda _v: self.refresh_job())
        form.addRow(_("Speed"), self.speed)
        form.addRow(_("Force"), self.force)
        self.inside_first = QCheckBox(_("Inside shapes first"))
        self.inside_first.setChecked(True)
        self.inside_first.setEnabled(False)
        self.inside_first.setToolTip(LATER)
        form.addRow(self.inside_first)
        col.addWidget(box)

        box = QGroupBox(_("Job"))
        lay = QVBoxLayout(box)
        self.job_label = QLabel()
        self.job_label.setWordWrap(True)
        lay.addWidget(self.job_label)
        self.dry_run = QCheckBox(_("Dry run: only save to a file"))
        self.dry_run.setChecked(True)
        self.dry_run.setEnabled(False)
        self.dry_run.setToolTip(_("Sending to the cutter comes in a later step"))
        lay.addWidget(self.dry_run)
        grid = QGridLayout()
        self.btn_preview = QPushButton(icons.tabler("route"), _("Knife path"))
        self.btn_preview.setEnabled(False)
        self.btn_preview.setToolTip(LATER)
        self.btn_save = QPushButton(icons.tabler("device-floppy"), _("Save .hpgl"))
        self.btn_save.clicked.connect(lambda: self.save_cutter_file())
        self.btn_start = QPushButton(icons.tabler("player-play"), _("Start"))
        self.btn_start.setObjectName("start")
        self.btn_stop = QPushButton(icons.tabler("player-stop"), _("Stop"))
        for b in (self.btn_start, self.btn_stop):
            b.setEnabled(False)
            b.setToolTip(LATER)
        for i, b in enumerate((self.btn_preview, self.btn_save, self.btn_start, self.btn_stop)):
            b.setMinimumHeight(40)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            grid.addWidget(b, i // 2, i % 2)
        lay.addLayout(grid)
        col.addWidget(box)
        return panel

    # ---- profile -----------------------------------------------------------------
    def _profile_changed(self, index):
        self.profile = profiles.load_builtin(self.profile_box.itemData(index))
        self.knife.setValue(self.profile.knife_offset_mm)
        self.overcut.setValue(self.profile.overcut_mm)
        self.refresh()

    def job_profile(self):
        """The chosen profile with the panel's speed and force (0 = from the panel)."""
        return dataclasses.replace(self.profile,
                                   speed_cm_s=self.speed.value() or None,
                                   force_g=self.force.value() or None)

    # ---- design changes -----------------------------------------------------------
    def _name(self, base):
        self.counter[base] = self.counter.get(base, 0) + 1
        return "%s %d" % (base, self.counter[base])

    def add_element(self, element):
        self.design.elements.append(element)
        self.selected = element
        self.refresh()

    def new_design(self):
        if self.design.elements and QMessageBox.question(
                self, _("New design"), _("Remove everything from the material?")) != QMessageBox.Yes:
            return
        self.design = Design()
        self.selected = None
        self.view.fit_requested()
        self.refresh()

    def import_svg(self, path=None):
        if path is None:
            path, _f = QFileDialog.getOpenFileName(self, _("Open SVG"), "", _("SVG files (*.svg)"))
            if not path:
                return None
        try:
            e = load_svg(path)
        except LoadError as err:
            QMessageBox.warning(self, _("Open SVG"), str(err))
            return None
        # place it on the material, PLACE_MARGIN_MM from the origin in both directions
        _w, h = e.size
        e.move_to(PLACE_MARGIN_MM, -PLACE_MARGIN_MM - h)
        self.add_element(e)
        self.statusBar().showMessage(_("Opened %s") % os.path.basename(path), 5000)
        return e

    def _on_drawn(self, tool, rect):
        make = {"rectangle": (shapes.rectangle, _("Rectangle")),
                "ellipse": (shapes.ellipse, _("Ellipse"))}[tool]
        paths = make[0](rect.left(), rect.top(), rect.right(), rect.bottom())
        self.add_element(Element(self._name(make[1]), paths))
        self.set_tool("select")

    def _on_line_drawn(self, a, b):
        self.add_element(Element(self._name(_("Line")), shapes.line(a.x(), a.y(), b.x(), b.y())))
        self.set_tool("select")

    def _on_moved(self, element, dx, dy):
        element.move_by(dx, dy)
        self.refresh()

    def _on_selected(self, element):
        if self._updating:
            return
        self.selected = element
        self._show_list()
        self._show_options()

    def delete_selected(self):
        if self.selected in self.design.elements:
            self.design.elements.remove(self.selected)
            self.selected = None
            self.refresh()

    def move_selected(self, step):
        els = self.design.elements
        if self.selected not in els:
            return
        i = els.index(self.selected)
        j = i + step
        if 0 <= j < len(els):
            els[i], els[j] = els[j], els[i]
            self.refresh()

    # ---- element list ---------------------------------------------------------------
    def _show_list(self):
        self._updating = True
        lst = self.element_list
        lst.clear()
        for e in self.design.elements:
            item = QListWidgetItem(e.name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if e.cut else Qt.Unchecked)
            item.setToolTip(_("Ticked: cut. Not ticked: shown only."))
            lst.addItem(item)
        if self.selected in self.design.elements:
            lst.setCurrentRow(self.design.elements.index(self.selected))
        self._updating = False

    def _list_item_changed(self, item):
        if self._updating:
            return
        e = self.design.elements[self.element_list.row(item)]
        e.cut = item.checkState() == Qt.Checked
        self.refresh()

    def _list_row_changed(self, row):
        if self._updating or not 0 <= row < len(self.design.elements):
            return
        self.selected = self.design.elements[row]
        self._updating = True
        self.view.select(self.selected)
        self._updating = False
        self._show_options()

    # ---- refresh -------------------------------------------------------------------------
    def refresh(self):
        self._updating = True
        self.view.show_design(self.design, self.profile.width_mm, self.selected)
        self._updating = False
        self._show_list()
        self._show_options()
        box = self.design.bounds()
        n = len(self.design.elements)
        if box is None:
            self.summary.setText(_("Empty. Open an SVG file or draw a shape."))
        else:
            self.summary.setText(_("%d elements · %.1f × %.1f mm") % (n, box[1] - box[0], box[3] - box[2]))
        self.act_delete.setEnabled(self.selected is not None)
        self.refresh_job()

    def refresh_job(self):
        p = self.job_profile()
        self.profile_label.setText("%s · %s · %d" % (p.name, p.language.upper(), p.baud))
        self.last_job = None
        try:
            self.last_job = build_job(self.design.material_polylines(), p)
        except (JobError, ProfileError) as e:
            self.job_label.setText(str(e))
            self.job_label.setStyleSheet("color: #b91c1c")
            self.btn_save.setEnabled(False)
            self.act_save_cut.setEnabled(False)
            return
        j = self.last_job
        text = _("Cut length: %.2f m · travel: %.2f m") % (j.cut_mm / 1000.0, j.travel_mm / 1000.0)
        if p.speed_cm_s:
            minutes = (j.cut_mm + j.travel_mm) / (p.speed_cm_s * 10.0) / 60.0
            text += "\n" + _("About %.1f min at %g cm/s") % (minutes, p.speed_cm_s)
        self.job_label.setText(text)
        self.job_label.setStyleSheet("")
        self.btn_save.setEnabled(True)
        self.act_save_cut.setEnabled(True)

    # ---- output --------------------------------------------------------------------------
    def save_cutter_file(self, path=None):
        """Save the cutter commands to a file. Returns the path, or None."""
        try:
            job = build_job(self.design.material_polylines(), self.job_profile())
        except (JobError, ProfileError) as e:
            QMessageBox.warning(self, _("Save cutter file"), str(e))
            return None
        if path is None:
            path, _f = QFileDialog.getSaveFileName(self, _("Save cutter file"), "design" + job.extension,
                                                   _("Cutter files (*%s)") % job.extension)
            if not path:
                return None
        job.save(path)
        self.statusBar().showMessage(_("Saved %s (%d bytes)") % (os.path.basename(path), len(job.text)), 8000)
        return path

    def about(self):
        QMessageBox.about(self, _("About Vintyl"),
                          _("Vintyl %s\nSoftware for vinyl cutters.\nGPL-3.0-or-later.") % __version__)
