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
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFontComboBox, QFormLayout,
                               QFrame, QLineEdit, QMenu, QScrollArea,
                               QProgressBar, QSpinBox, QToolButton,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSizePolicy,
                               QToolBar, QVBoxLayout, QWidget)

from vintyl import __version__
from vintyl.core import profile as profiles
from vintyl.core import shapes
from vintyl.core import ready
from vintyl.core import transport
from vintyl.core.design import Design, Element
from vintyl.core.job import JobError, build_job
from vintyl.core.loaders import LoadError, load_svg
from vintyl.core.profile import ProfileError
from vintyl.gui import N_, _, ngettext
from vintyl.gui import icons
from vintyl.gui.canvas import MaterialView, shape_icon
from vintyl.gui.sender import SendWorker
from vintyl.gui import text as texts

LATER = N_("Comes in a later step of Vintyl")   # translated where it is shown
PLACE_MARGIN_MM = 10.0        # a new file is placed this far from the origin


def _spin(maximum=10000.0, decimals=2, suffix=" mm", minimum=-10000.0):
    s = QDoubleSpinBox()
    s.setRange(minimum, maximum)
    s.setDecimals(decimals)
    s.setSuffix(suffix)
    s.setKeyboardTracking(False)
    return s


def open_settings():
    """The user's settings (QSettings). VINTYL_SETTINGS names another file
    (the tests use their own, so they never touch the user's)."""
    from PySide6.QtCore import QSettings
    path = os.environ.get("VINTYL_SETTINGS")
    if path:
        return QSettings(path, QSettings.IniFormat)
    return QSettings("Vintyl", "Vintyl")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vintyl")
        self.setWindowIcon(icons.app_icon())
        self.design = Design()
        self.selected = None
        self.selection = []               # every selected element (selected is the first)
        self.counter = {}
        self.last_job = None              # the last successful build (for the summary)
        self.settings = open_settings()
        self.profile_names = profiles.builtin_names()
        self.profile = profiles.load_builtin(self.profile_names[0])
        self._updating = False
        self._undo = []                   # snapshots before each change (see _checkpoint)
        self._redo = []

        self.view = MaterialView()
        self._make_actions()
        self._make_menu()
        self._make_ribbon()
        self._make_tool_strip()

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # the options bar scrolls sideways when it is wider than the window,
        # so it never makes the window wider than the screen (as in Kerfly)
        bar = self._make_options_bar()
        bar_scroll = QScrollArea()
        bar_scroll.setObjectName("options_scroll")
        bar_scroll.setWidget(bar)
        bar_scroll.setWidgetResizable(True)
        bar_scroll.setFrameShape(QFrame.NoFrame)
        bar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        bar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        bar_scroll.setFixedHeight(bar.sizeHint().height() + bar_scroll.horizontalScrollBar().sizeHint().height())
        outer.addWidget(bar_scroll)
        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        middle.addWidget(self._make_left_panel())
        middle.addWidget(self.view, 1)
        middle.addWidget(self.tool_panel)
        outer.addLayout(middle, 1)
        self.setCentralWidget(central)

        self.cursor_label = QLabel()
        self.profile_label = QLabel()
        self.statusBar().addWidget(self.cursor_label)
        self.statusBar().addPermanentWidget(self.profile_label)

        s = self.view.signals
        s.selected.connect(self._on_selected)
        s.selection.connect(self._on_selection)
        s.moved.connect(self._on_moved)
        s.drawn.connect(self._on_drawn)
        s.line_drawn.connect(self._on_line_drawn)
        s.polyline_drawn.connect(self._on_polyline_drawn)
        s.text_clicked.connect(self._on_text_clicked)
        s.resized.connect(self._on_resized)
        s.nudged.connect(self._on_moved)
        s.nodes_changed.connect(self._on_nodes_changed)
        s.edit_nodes.connect(self._on_edit_nodes)
        s.cancel_tool.connect(lambda: self.set_tool("select"))
        s.node_selection.connect(self._on_node_selection)
        s.cursor.connect(lambda x, y: self.cursor_label.setText(_("Pointer: %.1f / %.1f mm") % (x, y)))
        self.resize(1440, 900)
        # the cutter used last time (and its port), not always the first profile
        last = self.settings.value("cutter/profile", "")
        if last in self.profile_names:
            self.profile_box.blockSignals(True)
            self.profile_box.setCurrentIndex(self.profile_names.index(last))
            self.profile_box.blockSignals(False)
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
                                         "Ctrl+S", _("Save exactly what would go to the cutter, as a file"))
        self.act_delete = self._action(_("Delete"), self.delete_selected, "trash", QKeySequence.Delete,
                                       _("Delete the selected element"))
        self.act_undo = self._action(_("Undo"), self.undo, "arrow-back-up", QKeySequence.Undo,
                                     _("Take back the last change"))
        self.act_redo = self._action(_("Redo"), self.redo, "arrow-forward-up", None,
                                     _("Do again what was taken back"))
        self.act_redo.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y")])
        self.act_select_all = self._action(_("Select all"), self.select_all, "select-all", QKeySequence.SelectAll,
                                           _("Select every element"))
        self.act_cut = self._action(_("Cut"), self.cut_selected, "scissors", QKeySequence.Cut,
                                    _("Take the selected elements away, to paste them elsewhere"))
        self.act_copy = self._action(_("Copy"), self.copy_selected, "copy", QKeySequence.Copy,
                                     _("Remember the selected elements, to paste them"))
        self.act_paste = self._action(_("Paste"), self.paste, "clipboard", QKeySequence.Paste,
                                      _("Put the copied elements back, 5 mm beside where they were"))
        self.clipboard = []
        self.act_duplicate = self._action(_("Duplicate"), self.duplicate, "copy", "Ctrl+D",
                                          _("A copy of the selected element, a little to the side"))
        self.act_rot_left = self._action(_("Rotate left"), lambda: self.transform_selected("rot", 90), "rotate-2",
                                         "Ctrl+[", _("Rotate 90° counter-clockwise"))
        self.act_rot_right = self._action(_("Rotate right"), lambda: self.transform_selected("rot", -90),
                                          "rotate-clockwise-2", "Ctrl+]", _("Rotate 90° clockwise"))
        self.act_mirror_h = self._action(_("Mirror"), lambda: self.transform_selected("mirror", True),
                                         "flip-horizontal", "Ctrl+M", _("Mirror left to right"))
        self.act_mirror_v = self._action(_("Flip"), lambda: self.transform_selected("mirror", False),
                                         "flip-vertical", "Ctrl+Shift+M", _("Flip top to bottom"))
        # align the selected shapes to each other (the box round all of them)
        self.act_align = {}
        for key, icon, text in (("left", "layout-align-left", N_("Left edges")),
                                ("centre", "layout-align-center", N_("Centres across")),
                                ("right", "layout-align-right", N_("Right edges")),
                                ("top", "layout-align-top", N_("Top edges")),
                                ("middle", "layout-align-middle", N_("Centres up and down")),
                                ("bottom", "layout-align-bottom", N_("Bottom edges"))):
            self.act_align[key] = self._action(_(text), lambda _c=False, k=key: self.align_selected(k), icon,
                                               tip=_("Align the selected shapes to each other: %s") % _(text).lower())
        # group / ungroup and combining shapes, as in Kerfly (and Inkscape's keys)
        self.act_group = self._action(_("Group"), self.group_selected, "squares-selected", "Ctrl+G",
                                      _("Join the selected elements into a group that is selected and moved as one"))
        self.act_ungroup = self._action(_("Ungroup"), self.ungroup_selected, "squares", "Ctrl+Shift+G",
                                        _("Split the selected group into separate elements; a single element with "
                                          "several outlines is split into one element per outline"))
        self.act_boolean = {}
        for code, icon, tip, key in (
                ("union", "layers-union", N_("Union: join the selected shapes into one outline"), "Ctrl++"),
                ("difference", "layers-subtract", N_("Difference: cut the other selected shapes out of the "
                                                     "first one"), "Ctrl+-"),
                ("intersection", "layers-intersect-2", N_("Intersection: keep only where the selected shapes "
                                                          "overlap"), "Ctrl+*"),
                ("exclusion", "layers-difference", N_("Exclusion: keep where the shapes do not overlap"), "Ctrl+^")):
            self.act_boolean[code] = self._action(_(self.BOOLEAN_NAMES[code]),
                                                  lambda _c=False, k=code: self.boolean_selected(k), icon, key, _(tip))
        self.selection_actions = [self.act_cut, self.act_copy, self.act_group, self.act_ungroup] + \
            list(self.act_boolean.values()) + [
            self.act_duplicate, self.act_rot_left, self.act_rot_right,
                                  self.act_mirror_h, self.act_mirror_v] + list(self.act_align.values())
        self.act_zoom_in = self._action(_("Zoom in"), lambda: self.view.zoom_by(1.25), None, "+",
                                        _("Look closer (the mouse wheel does the same)"))
        self.act_zoom_out = self._action(_("Zoom out"), lambda: self.view.zoom_by(1 / 1.25), None, "-",
                                         _("Look from further away"))
        self.act_shortcuts = self._action(_("Keyboard shortcuts"), self.show_shortcuts, None, "Ctrl+F1",
                                          _("Every key in one window"))
        self.act_fit = self._action(_("Fit"), self.view.fit_requested, "zoom-scan", "Ctrl+0",
                                    _("Show the whole material and design"))
        self.act_knife = self._action(_("Knife path"), None, "route", "Ctrl+K",
                                      _("Show exactly where the knife goes: cuts, travels and their order"))
        self.act_knife.setCheckable(True)
        self.act_knife.toggled.connect(lambda on: self.set_knife_preview(on))
        self.act_connect = self._action(_("Connect"), None, "plug-connected", tip=_(LATER), enabled=False)
        self.act_profile = self._action(_("Profile"), None, "settings-2", tip=_(LATER), enabled=False)
        self.act_quit = self._action(_("Quit"), self.close, None, QKeySequence.Quit)

    def _make_menu(self):
        mb = self.menuBar()
        m = mb.addMenu(_("&File"))
        for a in (self.act_new, self.act_open, self.act_save_cut, None, self.act_quit):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Edit"))
        for a in (self.act_undo, self.act_redo, None, self.act_cut, self.act_copy, self.act_paste,
                  self.act_duplicate, self.act_delete, None, self.act_select_all):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Object"))
        for a in [self.act_group, self.act_ungroup, None] + list(self.act_boolean.values()) + [None] + \
                [self.act_rot_left, self.act_rot_right, self.act_mirror_h, self.act_mirror_v, None] + \
                list(self.act_align.values()):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Cutter"))
        for a in (self.act_connect, self.act_profile):
            m.addAction(a)
        m = mb.addMenu(_("&View"))
        for a in (self.act_fit, self.act_zoom_in, self.act_zoom_out, None, self.act_knife):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Help"))
        m.addAction(self.act_shortcuts)
        m.addAction(self._action(_("About Vintyl"), self.about))

    def _make_ribbon(self):
        """The ribbon: groups with a caption under them; big buttons with a label,
        or small icon-only buttons in two rows where a group has many
        (the layout of Kerfly's ribbon, kerfly/gui/main_window.py, commit cf48565)."""
        groups = [
            (_("File"), [(self.act_new, _("New")), (self.act_open, _("Open SVG")),
                         (self.act_save_cut, _("Save .hpgl"))]),
            (_("Edit"), [(self.act_undo, _("Undo")), (self.act_redo, _("Redo"))]),
            (_("Element"), "grid", [self.act_duplicate, self.act_delete]),
            (_("Transform"), "grid", [self.act_rot_left, self.act_rot_right,
                                      self.act_mirror_h, self.act_mirror_v]),
            (_("Align"), "grid", [self.act_align["left"], self.act_align["centre"], self.act_align["right"],
                                  self.act_align["top"], self.act_align["middle"], self.act_align["bottom"]]),
            (_("Shapes"), "grid", [self.act_group, self.act_boolean["union"], self.act_boolean["difference"],
                                   self.act_ungroup, self.act_boolean["intersection"],
                                   self.act_boolean["exclusion"]]),
            (_("View"), [(self.act_fit, _("Fit")), (self.act_knife, _("Knife path"))]),
        ]
        tb = QToolBar(_("Main"))
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        for i, group_def in enumerate(groups):
            title, entries = group_def[0], group_def[-1]
            if i:
                line = QFrame()
                line.setFrameShape(QFrame.VLine)
                line.setObjectName("ribbon_separator")
                tb.addWidget(line)
            group = QWidget()
            v = QVBoxLayout(group)
            v.setContentsMargins(1, 2, 1, 0)
            v.setSpacing(0)
            if len(group_def) == 3:                       # small icon-only buttons in two rows
                grid = QGridLayout()
                grid.setSpacing(0)
                per_row = (len(entries) + 1) // 2
                for n, action in enumerate(entries):
                    button = QToolButton()
                    button.setDefaultAction(action)
                    button.setToolButtonStyle(Qt.ToolButtonIconOnly)
                    button.setIconSize(QSize(20, 20))
                    button.setAutoRaise(True)
                    button.setFixedSize(28, 28)
                    grid.addWidget(button, n // per_row, n % per_row)
                v.addLayout(grid)
                v.addStretch(1)
            else:
                row = QHBoxLayout()
                row.setSpacing(0)
                for action, short in entries:
                    action.setIconText(short)
                    button = QToolButton()
                    button.setDefaultAction(action)
                    button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                    button.setIconSize(QSize(24, 24))
                    button.setAutoRaise(True)
                    button.setFixedHeight(52)
                    row.addWidget(button, 0, Qt.AlignTop)
                v.addLayout(row)
            caption = QLabel(title)
            caption.setObjectName("ribbon_caption")
            caption.setAlignment(Qt.AlignHCenter)
            v.addWidget(caption)
            tb.addWidget(group)
        self.addToolBar(Qt.TopToolBarArea, tb)

    # the right-hand bar: a button per category; a click opens a square of
    # icons beside it (as SignMaster's), a category with one tool takes it at
    # once. Only the basic drawing tools: what the ribbon on top has
    # (transform, align, duplicate, delete) is not repeated.
    # A tool: ("tool", key, label, tooltip, icon); a ready shape: ("ready", key)
    PANEL = [
        ("pick", N_("Select"), "pointer", [
            ("tool", "select", N_("Select"), N_("Select and move"), "pointer"),
        ]),
        ("nodes", N_("Nodes"), "vector-bezier-2", [
            ("tool", "nodes", N_("Nodes"), N_("Edit nodes (or double-click an element)"), "vector-bezier-2"),
        ]),
        ("shapes", N_("Shapes"), "square", [
            ("tool", "rectangle", N_("Rectangle"), N_("Rectangle: drag from corner to corner"), "square"),
            ("tool", "ellipse", N_("Ellipse"), N_("Ellipse: drag the box it fits in"), "circle"),
            ("tool", "polygon", N_("Polygon"), N_("Regular polygon: drag the box it fits in; the number of "
                                                  "sides is in the options bar"), "polygon"),
        ]),
        ("ready", N_("Ready"), None, [("ready", k) for k in ready.READY]),
        ("lines", N_("Lines"), "vector", [
            ("tool", "polyline", N_("Polyline"), N_("Polyline: click the corners; the first corner closes it, "
                                                     "double-click or Enter leaves it open"), "vector"),
            ("tool", "line", N_("Line"), N_("Line: drag from end to end"), "line"),
        ]),
        ("text", N_("Text"), "typography", [
            ("tool", "text", N_("Text"), N_("Text: click where it should start"), "typography"),
        ]),
    ]

    def _make_tool_strip(self):
        from PySide6.QtWidgets import QButtonGroup
        panel = QWidget()
        panel.setObjectName("tool_panel")
        col = QVBoxLayout(panel)
        col.setContentsMargins(4, 6, 4, 6)
        col.setSpacing(2)
        group = QActionGroup(self)
        cat_group = QButtonGroup(self)
        cat_group.setExclusive(True)
        self.tool_actions = {}
        self.category_buttons = {}
        self.category_entries = {}
        self._category_of = {}
        for cat, title, icon, entries in self.PANEL:
            for entry in entries:
                if entry[0] == "tool":
                    _kind, key, label, tip, ticon = entry
                    a = self._action(_(tip), lambda _c=False, k=key: self.set_tool(k), ticon, tip=_(tip))
                    a.setCheckable(True)
                    a.setIconText(_(label))
                    group.addAction(a)
                    self.tool_actions[key] = a
                    self._category_of[key] = cat
            cb = QToolButton()
            cb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            cb.setIconSize(QSize(26, 26))
            cb.setAutoRaise(True)
            cb.setFixedSize(72, 58)
            cb.setIcon(icons.tabler(icon) if icon else shape_icon(ready.make("star")))
            cb.setText(_(title))
            cb.setCheckable(True)
            cb.clicked.connect(lambda _c=False, c=cat: self.show_category(c))
            cat_group.addButton(cb)
            col.addWidget(cb)
            self.category_buttons[cat] = cb
            self.category_entries[cat] = entries
        col.addStretch(1)
        # one letter per tool (a letter typed into a field goes to the field)
        for key, letter in (("select", "V"), ("nodes", "N"), ("rectangle", "R"), ("ellipse", "E"),
                            ("polygon", "P"), ("polyline", "L"), ("line", "Shift+L"), ("text", "T")):
            a = self.tool_actions[key]
            a.setShortcut(QKeySequence(letter))
            a.setToolTip("%s (%s)" % (a.toolTip(), QKeySequence(letter).toString(QKeySequence.NativeText)))
            self.addAction(a)                       # the keys work wherever the focus is in the window
        self.tool_panel = panel
        self.tool_popup = None
        self.tool_actions["select"].setChecked(True)
        self.category_buttons["pick"].setChecked(True)

    def show_category(self, cat):
        """A click on a category: one tool takes it at once; more open a square
        of icons beside the button. Returns the square (or None)."""
        entries = self.category_entries[cat]
        if len(entries) == 1 and entries[0][0] == "tool":
            self.set_tool(entries[0][1])
            return None
        popup = QFrame(self, Qt.Popup)
        popup.setObjectName("tool_popup")
        popup.setFrameShape(QFrame.StyledPanel)
        grid = QGridLayout(popup)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(2)
        per_row = 4 if len(entries) > 6 else (3 if len(entries) > 2 else len(entries))
        for n, entry in enumerate(entries):
            b = QToolButton()
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIconSize(QSize(24, 24))
            b.setAutoRaise(True)
            b.setFixedSize(76, 54)
            if entry[0] == "tool":
                a = self.tool_actions[entry[1]]
                b.setIcon(a.icon())
                b.setText(a.iconText())
                b.setToolTip(a.toolTip())
                b.setCheckable(True)
                b.setChecked(a.isChecked())
                b.clicked.connect(lambda _c=False, k=entry[1], p=popup: (p.close(), self.set_tool(k)))
            else:
                key = entry[1]
                name = ready.READY[key][0]
                b.setIcon(shape_icon(ready.make(key)))
                b.setText(_(name))
                b.setToolTip(_("Insert: %s") % _(name))
                b.clicked.connect(lambda _c=False, k=key, p=popup: (p.close(), self.insert_ready(k)))
            grid.addWidget(b, n // per_row, n % per_row)
        # beside the category's button, on the side of the material
        button = self.category_buttons[cat]
        popup.adjustSize()
        top_left = button.mapToGlobal(button.rect().topLeft())
        popup.move(top_left.x() - popup.width() - 2, top_left.y())
        popup.show()
        self.tool_popup = popup
        # the category of the tool in use stays marked meanwhile
        popup.destroyed.connect(lambda *_a: None)
        self.category_buttons[self._category_of[self.view.tool]].setChecked(True)
        return popup

    # ---- ready shapes ---------------------------------------------------------------------
    def insert_ready(self, key, values=None):
        """Insert a ready shape: ask for its parameters (values None) and put it
        10 mm from the origin, like an opened file. Returns the element or None."""
        name, _func, spec = ready.READY[key]
        if values is None:
            values = self._ask_ready(_(name), spec)
            if values is None:
                return None
        paths = ready.make(key, **values)
        e = Element(self._name(_(name)), paths, spec=dict(values, kind="ready", shape=key))
        w, h = e.size
        e.move_to(-PLACE_MARGIN_MM - w, -PLACE_MARGIN_MM - h)
        self.add_element(e)
        return e

    def _ask_ready(self, title, spec):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        form = QFormLayout(dlg)
        fields = {}
        for key, label, default, lo, hi, step in spec:
            if isinstance(default, int):
                w = QSpinBox()
                w.setRange(int(lo), int(hi))
            else:
                w = QDoubleSpinBox()
                w.setRange(lo, hi)
                w.setDecimals(1 if step >= 0.5 else 2)
                w.setSingleStep(step)
            w.setValue(default)
            form.addRow(_(label), w)
            fields[key] = w
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.Accepted:
            return None
        return {k: w.value() for k, w in fields.items()}

    def set_tool(self, tool):
        self.tool_actions[tool].setChecked(True)
        self.category_buttons[self._category_of[tool]].setChecked(True)
        self.view.set_tool(tool)
        self.node_hint.setVisible(tool == "nodes")
        self._show_text_options()
        self._show_polygon_options()

    # ---- options bar: the selected element ------------------------------------
    def _make_options_bar(self):
        bar = QWidget()
        bar.setObjectName("options_bar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 4, 10, 4)
        self.opt_x, self.opt_y = _spin(), _spin()
        self.opt_w, self.opt_h = _spin(minimum=0.0), _spin(minimum=0.0)
        # the lock: width and height change together (also with the small squares)
        self.opt_lock = QToolButton()
        self.opt_lock.setCheckable(True)
        self.opt_lock.setToolTip(_("Keep the proportions: width and height change together, "
                                   "in the fields and with the small squares round the selection"))
        self.opt_lock.setAccessibleName(_("Keep the proportions"))
        self.opt_lock.toggled.connect(self._lock_toggled)
        for label, spin, tip in ((_("X"), self.opt_x, _("Bottom edge: how far up from the origin, along the material")),
                                 (_("Y"), self.opt_y, _("Right edge: how far left from the origin, across the material")),
                                 (_("Width"), self.opt_w, None), (None, self.opt_lock, None),
                                 (_("Height"), self.opt_h, None)):
            if label is not None:
                lab = QLabel(label)
                lab.setBuddy(spin)
                row.addWidget(lab)
            if tip:
                spin.setToolTip(tip)
            row.addWidget(spin)
            if spin is not self.opt_lock:
                spin.valueChanged.connect(self._options_changed)
        self.opt_cut = QCheckBox(_("Cut this element"))
        self.opt_cut.toggled.connect(self._options_changed)
        row.addSpacing(16)
        row.addWidget(self.opt_cut)
        row.addSpacing(16)
        self.sides_label = QLabel(_("Sides"))
        self.opt_sides = QSpinBox()
        self.opt_sides.setRange(3, 64)
        self.opt_sides.setValue(self.view.polygon_sides)
        self.opt_sides.valueChanged.connect(self._sides_changed)
        self.sides_label.setBuddy(self.opt_sides)
        row.addWidget(self.sides_label)
        row.addWidget(self.opt_sides)
        self.node_hint = QLabel(_("Drag nodes and handles · double-click a side: add a node · "
                                  "D delete · L line · C curve · O smooth · Z close/open · B break"))
        self.node_hint.setStyleSheet("color: #4b5563")
        # the hint wraps and never makes the window wider than the screen
        self.node_hint.setWordWrap(True)
        self.node_hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        row.addWidget(self.node_hint, 1)
        for w in (self.sides_label, self.opt_sides, self.node_hint):
            w.setVisible(False)
        # text: the text itself, font, size (em height), bold, italic, letter spacing
        self.text_defaults = dict(texts.DEFAULTS)
        self.opt_text = QLineEdit(self.text_defaults["text"])
        self.opt_text.setFixedWidth(140)
        self.opt_text.setToolTip(_("The text; Enter applies it"))
        self.opt_font = QFontComboBox()
        self.opt_font.setFixedWidth(170)
        self.opt_font.setCurrentFont(self.opt_font.currentFont().__class__(self.text_defaults["family"]))
        self.opt_size = _spin(1000.0, 1, minimum=1.0)
        self.opt_size.setValue(self.text_defaults["size"])
        self.opt_size.setToolTip(_("Font size: the height of the font's em in mm"))
        self.opt_bold = QToolButton()
        self.opt_bold.setIcon(icons.tabler("bold"))
        self.opt_bold.setCheckable(True)
        self.opt_bold.setChecked(self.text_defaults["bold"])
        self.opt_bold.setToolTip(_("Bold"))
        self.opt_italic = QToolButton()
        self.opt_italic.setIcon(icons.tabler("italic"))
        self.opt_italic.setCheckable(True)
        self.opt_italic.setToolTip(_("Italic"))
        self.opt_spacing = _spin(100.0, 2, minimum=-20.0)
        self.opt_spacing.setToolTip(_("Extra space between letters, mm"))
        self.text_widgets = [self.opt_text, self.opt_font, self.opt_size, self.opt_bold, self.opt_italic,
                             self.opt_spacing]
        self.text_labels = []
        for label, w in ((_("Text"), self.opt_text), (_("Font"), self.opt_font), (_("Size"), self.opt_size),
                         (None, self.opt_bold), (None, self.opt_italic), (_("Spacing"), self.opt_spacing)):
            if label:
                lab = QLabel(label)
                lab.setBuddy(w)
                row.addWidget(lab)
                self.text_labels.append(lab)
            row.addWidget(w)
        self.opt_text.editingFinished.connect(self._text_changed)
        self.opt_font.currentFontChanged.connect(lambda _f: self._text_changed())
        for w in (self.opt_size, self.opt_spacing):
            w.valueChanged.connect(lambda _v: self._text_changed())
        for w in (self.opt_bold, self.opt_italic):
            w.toggled.connect(lambda _v: self._text_changed())
        for w in self.text_widgets + self.text_labels:
            w.setVisible(False)
        row.addStretch(1)
        self.options_widgets = (self.opt_x, self.opt_y, self.opt_w, self.opt_h, self.opt_cut)
        locked = str(self.settings.value("view/keep_ratio", "true")).lower() == "true"
        self.opt_lock.setChecked(locked)
        self._lock_toggled(locked)
        return bar

    def _show_options(self):
        self._updating = True
        e = self.selected
        for w in self.options_widgets:
            w.setEnabled(e is not None)
        if e is not None:
            xmin, xmax, ymin, ymax = e.bounds
            self.opt_x.setValue(-ymax)            # bottom edge: along the material from the origin
            self.opt_y.setValue(-xmax)            # right edge: across the material from the origin
            self.opt_w.setValue(xmax - xmin)
            self.opt_h.setValue(ymax - ymin)
            self.opt_cut.setChecked(e.cut)
        self._updating = False
        self._show_text_options()
        self._show_polygon_options()

    def _lock_toggled(self, on):
        self.opt_lock.setIcon(icons.tabler("link" if on else "link-off"))
        self.view.keep_ratio = on
        self.settings.setValue("view/keep_ratio", "true" if on else "false")

    def _on_resized(self, elements, old, new):
        """The small squares were dragged: every selected element goes from the
        old box to the new one (texts and polygons become plain shapes)."""
        sx = new.width() / old.width() if old.width() > 1e-9 else 1.0
        sy = new.height() / old.height() if old.height() > 1e-9 else 1.0
        self._checkpoint()
        for e in elements:
            e.transform(lambda x, y: (new.left() + (x - old.left()) * sx, new.top() + (y - old.top()) * sy))
            e.spec = None
        self.selection = list(elements)
        self.selected = elements[0] if elements else None
        self.refresh()

    def _options_changed(self):
        e = self.selected
        if self._updating or e is None:
            return
        self._checkpoint()
        w, h = self.opt_w.value(), self.opt_h.value()
        w0, h0 = e.size
        if self.opt_lock.isChecked() and w0 > 1e-9 and h0 > 1e-9:
            # locked: the field that changed drives the other one
            if abs(w - round(w0, 2)) > 1e-9:
                h = w * h0 / w0
            elif abs(h - round(h0, 2)) > 1e-9:
                w = h * w0 / h0
        if (w, h) != tuple(round(v, 2) for v in e.size) and w > 0 and h > 0:
            e.set_size(w, h)
            e.spec = None                # stretched: it is a shape now, no longer an editable text
        _xmin, xmax, _ymin, ymax = e.bounds
        e.move_by(-self.opt_y.value() - xmax, -self.opt_x.value() - ymax)
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
        # the cutter's port: the profile's, plus whatever cutter-like device is plugged in
        self.port_box = QComboBox()
        self.port_box.setEditable(True)
        self.port_box.setToolTip(_("USB printer (/dev/usb/lp…) or serial port (/dev/ttyUSB…, /dev/ttyACM…)"))
        self.port_box.currentTextChanged.connect(self._port_changed)
        form.addRow(_("Port"), self.port_box)
        self.knife = _spin(5, 2, minimum=0)
        self.knife.setSingleStep(0.05)
        self.knife.setSpecialValueText(_("pen (no offset)"))
        self.knife.setToolTip(_("How far the blade tip trails the holder's axis. "
                                "A 45° blade: usually 0.20–0.30 mm. 0 = pen."))
        self.overcut = _spin(5, 2, minimum=0)
        self.overcut.setSingleStep(0.1)
        self.overcut.setToolTip(_("Closed shapes are cut this far past their start, "
                                  "so the cut closes cleanly"))
        for w in (self.knife, self.overcut):
            w.valueChanged.connect(lambda _v: self.refresh_job())
        form.addRow(_("Knife offset"), self.knife)
        form.addRow(_("Overcut"), self.overcut)
        self.speed = _spin(80, 1, " cm/s", minimum=0)
        self.force = _spin(1000, 0, " g", minimum=0)
        for w in (self.speed, self.force):
            w.setSpecialValueText(_("from the panel"))
            w.valueChanged.connect(lambda _v: self.refresh_job())
        self.speed_label = QLabel(_("Speed"))
        self.force_label = QLabel(_("Force"))
        form.addRow(self.speed_label, self.speed)
        form.addRow(self.force_label, self.force)
        self.inside_first = QCheckBox(_("Inside shapes first"))
        self.inside_first.setChecked(True)
        self.inside_first.setToolTip(_("Holes and shapes inside others are cut before them, so a piece "
                                       "is never cut free while its holes are still to be cut. "
                                       "Off: exactly the order of the list."))
        self.inside_first.toggled.connect(lambda _v: self.refresh_job())
        form.addRow(self.inside_first)
        col.addWidget(box)

        box = QGroupBox(_("Job"))
        lay = QVBoxLayout(box)
        self.job_label = QLabel()
        self.job_label.setWordWrap(True)
        lay.addWidget(self.job_label)
        # a frame round the whole design, cut last, for weeding
        frame_row = QHBoxLayout()
        self.weed_frame = QCheckBox(_("Frame round the design"))
        self.weed_frame.setToolTip(_("A rectangle round everything that is cut, cut last: "
                                     "the waste vinyl inside it peels off in one piece"))
        self.weed_margin = _spin(100.0, 1, minimum=0.5)
        self.weed_margin.setValue(5.0)
        self.weed_margin.setToolTip(_("Space between the design and the frame"))
        self.weed_frame.toggled.connect(lambda _v: self.refresh_job())
        self.weed_margin.valueChanged.connect(lambda _v: self.refresh_job())
        frame_row.addWidget(self.weed_frame)
        frame_row.addWidget(self.weed_margin)
        lay.addLayout(frame_row)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        lay.addWidget(self.progress)
        grid = QGridLayout()
        self.btn_save = QPushButton(icons.tabler("device-floppy"), _("Save .hpgl"))
        self.btn_save.clicked.connect(lambda: self.save_cutter_file())
        self.btn_start = QPushButton(icons.tabler("player-play"), _("Start"))
        self.btn_start.setObjectName("start")
        self.btn_start.setToolTip(_("Cut the design (after a short check list)"))
        self.btn_start.clicked.connect(self.start)
        self.btn_stop = QPushButton(icons.tabler("player-stop"), _("Stop"))
        self.btn_stop.setToolTip(_("Stop sending and lift the knife. What the cutter already has "
                                   "is stopped with Test or Reset on its panel."))
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop)
        # Save on its own row, Start and Stop under it (the knife path is on the ribbon)
        for b, r, c, span in ((self.btn_save, 0, 0, 2), (self.btn_start, 1, 0, 1), (self.btn_stop, 1, 1, 1)):
            b.setMinimumHeight(40)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            grid.addWidget(b, r, c, 1, span)
        lay.addLayout(grid)
        col.addWidget(box)
        return panel

    # ---- profile -----------------------------------------------------------------
    def _profile_changed(self, index):
        self.profile = profiles.load_builtin(self.profile_box.itemData(index))
        self.knife.setValue(self.profile.knife_offset_mm)
        self.overcut.setValue(self.profile.overcut_mm)
        self.fill_ports()
        self.settings.setValue("cutter/profile", self.profile_box.itemData(index))
        saved_port = self.settings.value("cutter/port/" + self.profile_box.itemData(index), "")
        if saved_port:
            self.port_box.blockSignals(True)
            self.port_box.setEditText(saved_port)
            self.port_box.blockSignals(False)
        # cutters set on their panel only: speed is just for the time estimate, no force field
        sends = self.profile.send_speed_force
        self.speed_label.setText(_("Speed") if sends else _("Speed on the panel"))
        self.speed.setToolTip(_("Empty: the cutter uses what is set on its panel") if sends else
                              _("Not sent: this cutter takes its speed from its panel. "
                                "Enter it here for the time estimate."))
        self.force.setToolTip(_("Empty: the cutter uses what is set on its panel"))
        self.force_label.setVisible(sends)
        self.force.setVisible(sends)
        self.refresh()

    def _port_changed(self, text):
        """Remember the port chosen for this cutter."""
        name = self.profile_box.currentData()
        if name:
            self.settings.setValue("cutter/port/" + name, text.strip())
        self.refresh_job()

    def fill_ports(self):
        """The profile's port first, then every cutter-like device plugged in now."""
        self.port_box.blockSignals(True)
        self.port_box.clear()
        ports = [self.profile.port] if self.profile.port else []
        ports += [p for p in transport.find_ports() if p not in ports]
        self.port_box.addItems(ports)
        self.port_box.setCurrentIndex(0 if ports else -1)
        self.port_box.blockSignals(False)

    def job_profile(self):
        """The chosen profile with the panel's knife, overcut, speed and force
        (speed and force 0 = from the cutter's panel)."""
        return dataclasses.replace(self.profile,
                                   port=self.port_box.currentText().strip(),
                                   knife_offset_mm=self.knife.value(),
                                   overcut_mm=self.overcut.value(),
                                   speed_cm_s=self.speed.value() or None,
                                   force_g=self.force.value() or None)

    def build(self):
        """The job as it would go to the cutter now (raises JobError / ProfileError)."""
        polys, groups = self.design.material_paths()
        frame = self.weed_frame_polyline(polys)
        if frame:
            polys = polys + [frame]                      # in its own last group: cut last
            groups = groups + [max(groups) + 1]
        return build_job(polys, self.job_profile(), groups, self.inside_first.isChecked())

    def weed_frame_polyline(self, polys):
        """The weeding frame (material mm): a rectangle round all that is cut,
        weed_margin away; None when it is off or there is nothing to cut."""
        if not polys or not self.weed_frame.isChecked():
            return None
        m = self.weed_margin.value()
        xs = [x for poly in polys for x, _y in poly]
        ys = [y for poly in polys for _x, y in poly]
        x0, x1, y0, y1 = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]

    # ---- knife path preview --------------------------------------------------------
    def set_knife_preview(self, on):
        if self.act_knife.isChecked() != on:
            self.act_knife.blockSignals(True)
            self.act_knife.setChecked(on)
            self.act_knife.blockSignals(False)
        self.view.show_knife(self.last_job.knife_paths if on and self.last_job else None)

    # ---- design changes -----------------------------------------------------------
    def _name(self, base):
        self.counter[base] = self.counter.get(base, 0) + 1
        return "%s %d" % (base, self.counter[base])

    def add_element(self, element):
        self._checkpoint()
        self.design.elements.append(element)
        self.selected = element
        self.refresh()

    def new_design(self):
        if self.design.elements and QMessageBox.question(
                self, _("New design"), _("Remove everything from the material?")) != QMessageBox.Yes:
            return
        self._checkpoint()
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
        # place it on the material, PLACE_MARGIN_MM from the origin (lower right) both ways
        w, h = e.size
        e.move_to(-PLACE_MARGIN_MM - w, -PLACE_MARGIN_MM - h)
        self.add_element(e)
        self.statusBar().showMessage(_("Opened %s") % os.path.basename(path), 5000)
        return e

    def _on_drawn(self, tool, rect):
        make = {"rectangle": (shapes.rectangle, _("Rectangle")),
                "ellipse": (shapes.ellipse, _("Ellipse")),
                "polygon": (lambda *r: shapes.polygon(*r, sides=self.opt_sides.value()), _("Polygon"))}[tool]
        paths = make[0](rect.left(), rect.top(), rect.right(), rect.bottom())
        e = Element(self._name(make[1]), paths)
        if tool == "polygon":
            # remember how it was drawn, so its number of sides can be changed later:
            # the rectangle it was drawn in, relative to the polygon's own box
            b = e.bounds
            e.spec = {"kind": "polygon", "sides": self.opt_sides.value(), "w": rect.width(), "h": rect.height(),
                      "ox": b[0] - rect.left(), "oy": b[2] - rect.top()}
        self.add_element(e)
        self.set_tool("select")

    # ---- polygon: the number of sides, also of a drawn polygon ---------------------------
    def _is_polygon(self, e):
        return e is not None and e.spec is not None and e.spec.get("kind") == "polygon"

    def _show_polygon_options(self):
        e = self.selected
        show = self.view.tool == "polygon" or self._is_polygon(e)
        self.sides_label.setVisible(show)
        self.opt_sides.setVisible(show)
        if self._is_polygon(e) and self.opt_sides.value() != e.spec["sides"]:
            self._updating = True
            self.opt_sides.setValue(e.spec["sides"])
            self._updating = False

    def _sides_changed(self, sides):
        """New polygons get this many sides; a selected polygon is redrawn with them,
        in the rectangle it was drawn in."""
        self.view.polygon_sides = sides
        e = self.selected
        if self._updating or not self._is_polygon(e) or e.spec["sides"] == sides:
            return
        self._checkpoint()
        sp = e.spec
        x0, _x1, y0, _y1 = e.bounds
        rx, ry = x0 - sp["ox"], y0 - sp["oy"]
        e.paths = shapes.polygon(rx, ry, rx + sp["w"], ry + sp["h"], sides)
        nb = e.bounds
        e.spec = dict(sp, sides=sides, ox=nb[0] - rx, oy=nb[2] - ry)
        self.refresh()

    def _on_line_drawn(self, a, b):
        self.add_element(Element(self._name(_("Line")), shapes.line(a.x(), a.y(), b.x(), b.y())))
        self.set_tool("select")

    def _on_polyline_drawn(self, points, closed):
        from vintyl.core import curves
        name = _("Shape") if closed else _("Polyline")
        self.add_element(Element(self._name(name), curves.from_polylines([points], [closed])))
        self.set_tool("select")

    # ---- text --------------------------------------------------------------------------
    def _text_spec_from_widgets(self):
        return {"kind": "text", "text": self.opt_text.text(), "family": self.opt_font.currentFont().family(),
                "size": self.opt_size.value(), "bold": self.opt_bold.isChecked(),
                "italic": self.opt_italic.isChecked(), "spacing": self.opt_spacing.value()}

    def _is_text(self, e):
        return e is not None and e.spec is not None and e.spec.get("kind") == "text"

    def _show_text_options(self):
        """The text fields: with the text tool, or when a text is selected (filled from it)."""
        e = self.selected
        show = self.view.tool == "text" or self._is_text(e)
        for w in self.text_widgets + self.text_labels:
            w.setVisible(show)
        if self._is_text(e):
            self._updating = True
            spec = e.spec
            self.opt_text.setText(spec["text"])
            f = self.opt_font.currentFont()
            f.setFamily(spec["family"])
            self.opt_font.setCurrentFont(f)
            self.opt_size.setValue(spec["size"])
            self.opt_bold.setChecked(spec["bold"])
            self.opt_italic.setChecked(spec["italic"])
            self.opt_spacing.setValue(spec["spacing"])
            self._updating = False

    def _on_text_clicked(self, p):
        spec = self._text_spec_from_widgets()
        paths = texts.spec_paths(spec)
        if not paths:
            QMessageBox.warning(self, _("Text"), _("Type the text in the options bar first."))
            return
        e = Element(spec["text"].split("\n")[0][:30] or _("Text"), paths, spec=spec)
        e.move_to(p.x(), p.y())                       # the text starts where it was clicked
        self.add_element(e)
        self.set_tool("select")

    def _text_changed(self):
        """A text field changed: remember it for new texts, and redo the selected
        text with it (its lower left corner stays where it is)."""
        if self._updating:
            return
        spec = self._text_spec_from_widgets()
        e = self.selected
        if not self._is_text(e) or spec == e.spec:
            return
        paths = texts.spec_paths(spec)
        if not paths:
            return
        self._checkpoint()
        x0, _x1, _y0, y1 = e.bounds
        e.paths = paths
        e.spec = spec
        e.name = spec["text"].split("\n")[0][:30] or e.name
        nx0, _nx1, _ny0, ny1 = e.bounds
        e.move_by(x0 - nx0, y1 - ny1)
        self.refresh()

    # ---- select all, cut, copy, paste ------------------------------------------------------
    def select_all(self):
        self.set_tool("select")
        self.view.select_many(list(self.design.elements))
        self.selection = list(self.design.elements)
        self.selected = self.selection[0] if self.selection else None
        self._show_list()
        self._show_options()
        self._enable_selection_actions()

    def copy_selected(self):
        self.clipboard = [e.copy() for e in self._chosen()]
        self.act_paste.setEnabled(bool(self.clipboard))
        if self.clipboard:
            self.statusBar().showMessage(ngettext("Copied %d element.", "Copied %d elements.", len(self.clipboard))
                                         % len(self.clipboard), 4000)

    def cut_selected(self):
        self.copy_selected()
        self.delete_selected()

    def paste(self):
        """The copied elements, 5 mm to the left of where they were (a group
        stays a group of its own)."""
        if not self.clipboard:
            return
        import uuid
        self._checkpoint()
        new_groups = {}
        pasted = []
        for e in self.clipboard:
            c = e.copy()
            if c.group:
                c.group = new_groups.setdefault(c.group, uuid.uuid4().hex[:8])
            c.move_by(-5.0, 0.0)
            self.design.elements.append(c)
            pasted.append(c)
        self.clipboard = [c.copy() for c in pasted]       # the next paste goes 5 mm further
        self.selection = pasted
        self.selected = pasted[0]
        self.refresh()

    def show_shortcuts(self):
        """Every action with a key, in one window (built from the actions, so it is never out of date)."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem
        rows = self.shortcut_list()
        dlg = QDialog(self)
        dlg.setWindowTitle(_("Keyboard shortcuts"))
        lay = QVBoxLayout(dlg)
        table = QTableWidget(len(rows), 3)
        table.setHorizontalHeaderLabels([_("Key"), _("Command"), _("What it does")])
        for r, (keys, name, about) in enumerate(rows):
            table.setItem(r, 0, QTableWidgetItem(keys))
            table.setItem(r, 1, QTableWidgetItem(name))
            table.setItem(r, 2, QTableWidgetItem(about))
        table.setWordWrap(True)
        table.resizeColumnsToContents()
        table.setColumnWidth(2, 380)
        table.resizeRowsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        lay.addWidget(table)
        hint = QLabel(_("Mouse: the wheel zooms, the middle button moves the view, Alt turns snapping off, "
                        "Shift draws lines in 45° steps, Escape leaves a tool."))
        hint.setWordWrap(True)
        lay.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        dlg.resize(760, 640)
        dlg.exec()
        return rows

    def shortcut_list(self):
        """(keys, command, short description) of every action with a key, by command."""
        rows, seen = [], set()
        for a in self.findChildren(QAction):
            keys = [k.toString(QKeySequence.NativeText) for k in a.shortcuts() if not k.isEmpty()]
            if not keys or id(a) in seen:
                continue
            seen.add(id(a))
            name = (a.iconText() or a.text()).replace("&", "")
            about = a.toolTip().replace("&", "")
            for k in keys:                                    # the key is in its own column
                about = about.replace(" (%s)" % k, "")
            about = about.split(":", 1)[1].strip() if about.startswith(name + ":") else about
            if about.strip() == name:                          # no description of its own
                about = ""
            rows.append((", ".join(keys), name, about[:1].upper() + about[1:]))
        rows.sort(key=lambda r: r[1].lower())
        return rows

    def duplicate(self):
        e = self.selected
        if e is None:
            return
        c = e.copy()
        c.name = self._name(e.name.rsplit(" ", 1)[0] if e.name[-1:].isdigit() else e.name)
        w, _h = c.size
        c.move_by(-(w + 5.0), 0.0)               # beside it, further left (across the material)
        self.add_element(c)

    def transform_selected(self, kind, value):
        e = self.selected
        if e is None:
            return
        self._checkpoint()
        # turning or mirroring keeps the element's lower right corner where it was
        _x0, x1, _y0, y1 = e.bounds
        if kind == "rot":
            e.rotate(value)
        else:
            e.mirror(value)
        e.spec = None                    # turned or mirrored: a shape now, no longer an editable text
        _x0, nx1, _y0, ny1 = e.bounds
        e.move_by(x1 - nx1, y1 - ny1)
        self.refresh()

    def align_selected(self, where):
        """Align the selected shapes to each other: to the box round all of
        them (where: left, centre, right, top, middle, bottom). Nothing to
        align with one shape alone."""
        chosen = self._chosen()
        if len(chosen) < 2:
            self.statusBar().showMessage(_("Select two or more shapes to align them to each other."), 6000)
            return
        self._checkpoint()
        boxes = [e.bounds for e in chosen]
        x0, x1 = min(b[0] for b in boxes), max(b[1] for b in boxes)
        y0, y1 = min(b[2] for b in boxes), max(b[3] for b in boxes)
        for e in chosen:
            ex0, ex1, ey0, ey1 = e.bounds
            dx = dy = 0.0
            if where == "left":
                dx = x0 - ex0
            elif where == "right":
                dx = x1 - ex1
            elif where == "centre":
                dx = (x0 + x1) / 2.0 - (ex0 + ex1) / 2.0
            elif where == "top":
                dy = y0 - ey0
            elif where == "bottom":
                dy = y1 - ey1
            elif where == "middle":
                dy = (y0 + y1) / 2.0 - (ey0 + ey1) / 2.0
            e.move_by(dx, dy)
        self.refresh()

    def _on_moved(self, elements, dx, dy):
        self._checkpoint()
        for e in elements:
            e.move_by(dx, dy)
        self.selection = list(elements)
        self.selected = elements[0] if elements else None
        self.refresh()

    def _on_nodes_changed(self, element, paths, _unused):
        self._checkpoint()
        element.paths = paths
        element.spec = None              # edited by its nodes: a shape now
        self.refresh()

    def _on_edit_nodes(self, element):
        self.selected = element
        self.view.select(element)
        self.set_tool("nodes")

    def _on_node_selection(self, n):
        if self.view.tool == "nodes" and n:
            self.statusBar().showMessage(ngettext("%d node selected", "%d nodes selected", n) % n, 3000)

    def _on_selected(self, element):
        if self._updating:
            return
        self.selected = element
        self._show_list()
        self._show_options()
        self._enable_selection_actions()

    def _on_selection(self, elements):
        if self._updating:
            return
        self.selection = [e for e in elements if any(e is d for d in self.design.elements)]

    def _chosen(self):
        """The selected elements (at least the one in the options bar), in the
        order of the element list: the difference cuts the later ones out of
        the earliest (as Inkscape: the lower one minus the upper ones)."""
        sel = [e for e in self.selection if any(e is d for d in self.design.elements)]
        if self.selected is not None and not any(self.selected is e for e in sel):
            sel = [self.selected]
        return [d for d in self.design.elements if any(d is e for e in sel)]

    def delete_selected(self):
        chosen = self._chosen()
        if chosen:
            self._checkpoint()
            for e in chosen:
                self.design.elements.remove(e)
            self.selected = None
            self.selection = []
            self.refresh()

    # ---- group, ungroup, union / difference / intersection / exclusion -------------------------
    BOOLEAN_NAMES = {"union": N_("Union"), "difference": N_("Difference"),
                     "intersection": N_("Intersection"), "exclusion": N_("Exclusion")}

    def group_selected(self):
        chosen = self._chosen()
        if len(chosen) < 2:
            self.statusBar().showMessage(_("Select two or more elements to group them."), 6000)
            return
        import uuid
        self._checkpoint()
        gid = uuid.uuid4().hex[:8]
        for e in chosen:
            e.group = gid
        self.statusBar().showMessage(ngettext("Grouped %d element.", "Grouped %d elements.", len(chosen))
                                     % len(chosen), 6000)
        self.refresh()

    def ungroup_selected(self):
        """A group splits into its elements; a single element with several
        outlines (an opened file, a text) splits into one element per outline."""
        chosen = self._chosen()
        if not chosen:
            return
        grouped = [e for e in chosen if e.group]
        if grouped:
            self._checkpoint()
            for e in grouped:
                e.group = ""
            self.selection = [chosen[0]]
            self.selected = chosen[0]
            self.refresh()
            return
        e = chosen[0]
        if len(e.paths) < 2:
            self.statusBar().showMessage(_("Nothing to split: one outline, no group."), 6000)
            return
        self._checkpoint()
        i = self.design.elements.index(e)
        parts = []
        for k, sub in enumerate(e.paths, 1):
            parts.append(Element("%s %d" % (e.name, k), [sub], e.cut, e.source))
        self.design.elements[i:i + 1] = parts
        self.selected = parts[0]
        self.selection = list(parts)
        self.refresh()

    def boolean_selected(self, op):
        """Combine the closed outlines of the selected elements into one shape:
        union, difference (the first minus the others), intersection or
        exclusion (where an odd number of them overlap). As in Kerfly, Qt does
        the geometry; it turns curves into short straight pieces, so the shapes
        are worked on 10 times bigger and scaled back: a circle of 30 mm then
        stays within 0.001 mm of round (at 1:1 it was 0.025 mm, 18 pieces)."""
        from PySide6.QtGui import QTransform
        from vintyl.gui.canvas import painter_path
        scale = 10.0
        up = QTransform.fromScale(scale, scale)
        chosen = self._chosen()
        parts = []
        for e in chosen:
            closed = [sub for sub in e.paths if sub["closed"]]
            if closed:
                path = up.map(painter_path(closed))
                path.setFillRule(Qt.OddEvenFill)
                parts.append((e, path))
        if len(parts) < 2:
            self.statusBar().showMessage(_("Select two or more shapes with closed outlines."), 6000)
            return
        result = parts[0][1]
        for _e, path in parts[1:]:
            if op == "union":
                result = result.united(path)
            elif op == "difference":
                result = result.subtracted(path)
            elif op == "intersection":
                result = result.intersected(path)
            else:
                result = result.united(path).subtracted(result.intersected(path))
        new_paths = texts.painter_path_to_curves(result.simplified(), 1.0 / scale)
        if not new_paths:
            self.statusBar().showMessage(_("Nothing is left of the shapes after this operation."), 6000)
            return
        self._checkpoint()
        first = parts[0][0]
        index = self.design.elements.index(first)
        for e, _p in parts:
            self.design.elements.remove(e)
        new = Element(self._name(_(self.BOOLEAN_NAMES[op])), new_paths, first.cut)
        self.design.elements.insert(min(index, len(self.design.elements)), new)
        self.selected = new
        self.selection = [new]
        self.refresh()

    def _enable_selection_actions(self):
        for a in self.selection_actions:
            a.setEnabled(self.selected is not None)
        self.act_delete.setEnabled(self.selected is not None)

    def move_selected(self, step):
        els = self.design.elements
        if self.selected not in els:
            return
        i = els.index(self.selected)
        j = i + step
        if 0 <= j < len(els):
            self._checkpoint()
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
        self._checkpoint()
        e.cut = item.checkState() == Qt.Checked
        self.refresh()

    def _list_row_changed(self, row):
        if self._updating or not 0 <= row < len(self.design.elements):
            return
        self.selected = self.design.elements[row]
        self.selection = [self.selected]
        self._updating = True
        self.view.select(self.selected)
        self._updating = False
        self._show_options()

    # ---- undo / redo ----------------------------------------------------------------------
    UNDO_LIMIT = 100

    def _snapshot(self):
        els = self.design.elements
        return ([e.copy() for e in els], els.index(self.selected) if self.selected in els else None)

    def _restore(self, snap):
        elements, index = snap
        self.design.elements = elements
        self.selected = elements[index] if index is not None else None
        self.refresh()

    def _checkpoint(self):
        """Remember the design as it is, before a change: Undo goes back to it."""
        self._undo.append(self._snapshot())
        del self._undo[:-self.UNDO_LIMIT]
        self._redo.clear()

    def undo(self):
        if self._undo:
            self._redo.append(self._snapshot())
            self._restore(self._undo.pop())

    def redo(self):
        if self._redo:
            self._undo.append(self._snapshot())
            self._restore(self._redo.pop())

    # ---- refresh -------------------------------------------------------------------------
    def refresh(self):
        self._updating = True
        if self.selected is not None and not any(self.selected is e for e in self.selection):
            self.selection = [self.selected]
        if self.selected is None:
            self.selection = []
        self.view.show_design(self.design, self.profile.width_mm, self.selection)
        self._updating = False
        self._show_list()
        self._show_options()
        box = self.design.bounds()
        n = len(self.design.elements)
        if box is None:
            self.summary.setText(_("Empty. Open an SVG file or draw a shape."))
        else:
            self.summary.setText(ngettext("%d element", "%d elements", n) % n
                                 + " · " + _("%.1f × %.1f mm") % (box[1] - box[0], box[3] - box[2]))
        self._enable_selection_actions()
        self.act_undo.setEnabled(bool(self._undo))
        self.act_redo.setEnabled(bool(self._redo))
        self.refresh_job()

    def refresh_job(self):
        self.view.show_frame(self.weed_frame_polyline(self.design.material_paths()[0]))
        p = self.job_profile()
        self.profile_label.setText("%s · %s · %s" % (p.name, p.language.upper(), p.port or _("no port")))
        busy = getattr(self, "sending", False)
        self.last_job = None
        try:
            self.last_job = self.build()
        except (JobError, ProfileError) as e:
            self.job_label.setText(str(e))
            self.job_label.setStyleSheet("color: #b91c1c")
            for w in (self.btn_save, self.act_save_cut, self.btn_start):
                w.setEnabled(False)
            self.view.show_knife(None)
            return
        self.view.show_knife(self.last_job.knife_paths if self.act_knife.isChecked() else None)
        j = self.last_job
        text = _("Cut length: %.2f m · travel: %.2f m") % (j.cut_mm / 1000.0, j.travel_mm / 1000.0)
        if p.speed_cm_s:
            minutes = (j.cut_mm + j.travel_mm) / (p.speed_cm_s * 10.0) / 60.0
            text += "\n" + _("About %.1f min at %g cm/s") % (minutes, p.speed_cm_s)
        self.job_label.setText(text)
        self.job_label.setStyleSheet("")
        for w in (self.btn_save, self.act_save_cut, self.btn_start):
            w.setEnabled(not busy)

    # ---- output --------------------------------------------------------------------------
    def save_cutter_file(self, path=None):
        """Save the cutter commands to a file. Returns the path, or None."""
        try:
            job = self.build()
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

    # ---- sending ---------------------------------------------------------------------------
    def start(self):
        """Start: cut the design, after a check list. (Saving the cutter file
        without cutting is the Save button.)"""
        try:
            job = self.build()
        except (JobError, ProfileError) as e:
            QMessageBox.warning(self, _("Start"), str(e))
            return None
        p = self.job_profile()
        if QMessageBox.question(
                self, _("Cut now?"),
                _("Send the design to %s (%s)?\n\n"
                  "Check before you go on:\n"
                  "• the knife is in the holder (or the pen for a test)\n"
                  "• the material is under the pinch rollers\n"
                  "• the origin is set (Origin key) where the design should start\n"
                  "• speed and force are set on the cutter's panel\n\n"
                  "To stop the cutter at once: Test (pause) or Reset on its panel.")
                % (p.port, p.name)) != QMessageBox.Yes:
            return None
        from vintyl.core.protocols import encoder_for
        self.worker = SendWorker(job.text, p, p.port, encoder_for(p).units_per_mm, self)
        self.worker.progress.connect(self._send_progress)
        self.worker.finished_send.connect(self._send_finished)
        self._set_sending(True)
        self.progress.setRange(0, len(job.text))
        self.progress.setValue(0)
        self.worker.start()
        return self.worker

    def stop(self):
        w = getattr(self, "worker", None)
        if w is not None and w.isRunning():
            w.request_stop()
            self.statusBar().showMessage(_("Stopping: lifting the knife…"))

    def _send_progress(self, sent, total):
        self.progress.setMaximum(total)
        self.progress.setValue(sent)

    def _send_finished(self, ok, message):
        self._set_sending(False)
        self.statusBar().showMessage(message, 15000)
        if not ok:
            QMessageBox.warning(self, _("Cutting"), message)

    def _set_sending(self, on):
        """While sending: Stop works, nothing else that would change the job."""
        self.sending = on
        self.progress.setVisible(on)
        self.btn_stop.setEnabled(on)
        for w in (self.btn_start, self.btn_save, self.act_save_cut, self.profile_box, self.port_box,
                  self.view):
            w.setEnabled(not on)

    def closeEvent(self, event):
        w = getattr(self, "worker", None)
        if w is not None and w.isRunning():
            w.request_stop()
            w.wait(15000)
        super().closeEvent(event)

    def about(self):
        QMessageBox.about(self, _("About Vintyl"),
                          _("Vintyl %s\nSoftware for vinyl cutters.\nGPL-3.0-or-later.") % __version__)
