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
from vintyl.core import pen as pens
from vintyl.core import profile as profiles
from vintyl.core import shapes
from vintyl.core import project
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


def outermost(rings):
    """Only the rings not lying inside another ring (a silhouette without holes)."""
    from vintyl.core.knife import point_in_polygon
    return [r for i, r in enumerate(rings)
            if not any(j != i and point_in_polygon(r[0], other) for j, other in enumerate(rings))]


class _SideScroll(QScrollArea):
    """The left panel's scroll area. It gives the panel the window's height
    (the project list gives way first) and scrolls only when even the panel's
    minimum does not fit. Done here because QScrollArea's own resizing sized
    the panel by its wrapped labels at its full preferred height, so it
    scrolled at once and hid Start below the edge."""

    def __init__(self, panel):
        super().__init__()
        self.setWidget(panel)
        self.setWidgetResizable(False)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedWidth(panel.width() + self.verticalScrollBar().sizeHint().width())
        panel.installEventFilter(self)

    def fit(self):
        panel = self.widget()
        if panel is not None:
            panel.resize(panel.width(), max(self.viewport().height(), self._least_height(panel)))

    @staticmethod
    def _least_height(panel):
        """The least height the panel's boxes need. A box with wrapped text
        (the port's message) needs its height at this width, which Qt's
        minimum leaves out, so it was squeezed."""
        col = panel.layout()
        m = col.contentsMargins()
        width = panel.width() - m.left() - m.right()
        total, shown = m.top() + m.bottom(), 0
        for i in range(col.count()):
            w = col.itemAt(i).widget()
            if w is None or w.isHidden():
                continue
            h = w.minimumSizeHint().height()
            if w.hasHeightForWidth():
                h = max(h, w.heightForWidth(width))
            total += h
            shown += 1
        return total + col.spacing() * max(0, shown - 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent, QTimer
        if obj is self.widget() and event.type() == QEvent.LayoutRequest:
            QTimer.singleShot(0, self.fit)            # rows came or went: fit again
        return super().eventFilter(obj, event)


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
        self.project_path = None          # the .vintyl file of the design, once saved or opened
        self.modified = False
        self.counter = {}
        self.last_job = None              # the last successful build (for the summary)
        self.settings = open_settings()
        self.profile_names = []              # the ids of the cutters in the machine list
        self.profile_entries = {}
        self.profile = profiles.load_builtin(profiles.builtin_names()[0])
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
        # the left panel scrolls when the window is too low for it, instead of
        # squeezing its rows into each other
        self.left_scroll = _SideScroll(self._make_left_panel())
        middle.addWidget(self.left_scroll)
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
        s.pen_drawn.connect(self._on_pen_drawn)
        s.measured.connect(self._on_measured)
        s.sheet_changed.connect(self.refresh)
        s.resized.connect(self._on_resized)
        s.nudged.connect(self._on_moved)
        s.nodes_changed.connect(self._on_nodes_changed)
        s.edit_nodes.connect(self._on_edit_nodes)
        s.cancel_tool.connect(lambda: self.set_tool("select"))
        s.node_selection.connect(self._on_node_selection)
        s.cursor.connect(lambda x, y: self.cursor_label.setText(_("Pointer: %.1f / %.1f mm") % (x, y)))
        self.resize(1440, 900)
        # the cutter used last time, not always the first one
        self.reload_profiles(self.settings.value("cutter/profile", ""), apply=False)
        self.grid_step = float(self.settings.value("view/grid_step", 10.0))
        self.view.snap_objects = str(self.settings.value("view/snap_objects", "true")).lower() == "true"
        self.act_grid.blockSignals(True)
        self.act_grid.setChecked(str(self.settings.value("view/grid", "false")).lower() == "true")
        self.act_grid.blockSignals(False)
        self.view.grid_mm = self.grid_step if self.act_grid.isChecked() else 0.0
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
        self.act_open = self._action(_("Open"), lambda: self.open_file(), "folder-open", QKeySequence.Open,
                                     _("Open a Vintyl project, or add the shapes of an SVG file to the design"))
        self.act_save = self._action(_("Save"), lambda: self.save_project(), "device-floppy", "Ctrl+S",
                                     _("Save the project (.vintyl): the design and the job's settings"))
        self.act_save_as = self._action(_("Save as…"), lambda: self.save_project(ask=True), None, "Ctrl+Shift+S",
                                        _("Save the project under another name"))
        self.act_save_cut = self._action(_("Save .hpgl"), lambda: self.save_cutter_file(), "file-export",
                                         "Ctrl+E", _("Save exactly what would go to the cutter, as a file"))
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
        self.act_distribute_across = self._action(_("Spread across"), lambda: self.distribute_selected(True),
                                                  "layout-distribute-vertical", None,
                                                  _("Spread three or more shapes evenly from left to right: "
                                                    "equal gaps, the outermost stay"))
        self.act_distribute_up = self._action(_("Spread up and down"), lambda: self.distribute_selected(False),
                                              "layout-distribute-horizontal", None,
                                              _("Spread three or more shapes evenly up and down: "
                                                "equal gaps, the outermost stay"))
        self.act_qr = self._action(_("QR code"), lambda: self.insert_qr(), "qrcode", None,
                                   _("A QR code to cut: an address or a text"))
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
        self.act_offset = self._action(_("Offset"), lambda: self.offset_selected(), "box-padding", "O",
                                       _("A new outline round the selected shapes (or inside them), "
                                         "a set distance away: an edge round a text, a backing in another colour"))
        self.act_fill = self._action(_("Fill"), lambda: self.fill_selected(), "bucket-droplet", "Shift+F",
                                     _("Fill the selected closed shapes with a pattern of lines, drawn "
                                       "with the pen (only when the tool is the pen)"))
        self.act_tile = self._action(_("Pattern of shapes"), lambda: self.tile_selected(), "rosette", "Shift+T",
                                     _("Fill the selected closed shape with rows of small shapes (dots, stars, "
                                       "hearts...), each one whole, to be cut out as holes"))
        self.selection_actions = [self.act_offset, self.act_fill, self.act_tile, self.act_cut, self.act_copy, self.act_group, self.act_ungroup,
                                  self.act_distribute_across, self.act_distribute_up] + \
            list(self.act_boolean.values()) + [
            self.act_duplicate, self.act_rot_left, self.act_rot_right,
                                  self.act_mirror_h, self.act_mirror_v] + list(self.act_align.values())
        self.act_zoom_in = self._action(_("Zoom in"), lambda: self.view.zoom_by(1.25), None, "+",
                                        _("Look closer (the mouse wheel does the same)"))
        self.act_zoom_out = self._action(_("Zoom out"), lambda: self.view.zoom_by(1 / 1.25), None, "-",
                                         _("Look from further away"))
        self.act_grid = self._action(_("Grid"), None, "grid-dots", "Ctrl+'",
                                     _("Show the grid and snap to it (its step is in the Settings)"))
        self.act_grid.setCheckable(True)
        self.act_grid.toggled.connect(self.set_grid)
        self.act_settings = self._action(_("Settings…"), lambda: self.show_settings(), "settings", "Ctrl+,",
                                         _("Grid step, snapping"))
        self.act_shortcuts = self._action(_("Keyboard shortcuts"), self.show_shortcuts, None, "Ctrl+F1",
                                          _("Every key in one window"))
        self.act_fit = self._action(_("Fit"), self.view.fit_requested, "zoom-scan", "Ctrl+0",
                                    _("Show the whole material and design"))
        self.act_knife = self._action(_("Knife path"), None, "route", "Ctrl+K",
                                      _("Show exactly where the knife goes: cuts, travels and their order"))
        self.act_knife.setCheckable(True)
        self.act_knife.toggled.connect(lambda on: self.set_knife_preview(on))
        self.act_profile = self._action(_("Cutter settings…"), lambda: self.edit_profile(), "settings-2", None,
                                        _("The chosen cutter's port, connection, knife and speed; "
                                          "new cutters"))
        self.act_quit = self._action(_("Quit"), self.close, None, QKeySequence.Quit)

    def _make_menu(self):
        mb = self.menuBar()
        m = mb.addMenu(_("&File"))
        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as, None, self.act_save_cut, None,
                  self.act_quit):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Edit"))
        for a in (self.act_undo, self.act_redo, None, self.act_cut, self.act_copy, self.act_paste,
                  self.act_duplicate, self.act_delete, None, self.act_select_all):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Object"))
        for a in [self.act_group, self.act_ungroup, None] + list(self.act_boolean.values()) + [None] + \
                [self.act_rot_left, self.act_rot_right, self.act_mirror_h, self.act_mirror_v, None] + \
                list(self.act_align.values()) + [None, self.act_offset, self.act_tile, self.act_fill]:
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Cutter"))
        m.addAction(self.act_profile)
        m = mb.addMenu(_("&View"))
        for a in (self.act_fit, self.act_zoom_in, self.act_zoom_out, None, self.act_knife, self.act_grid):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Settings"))
        m.addAction(self.act_settings)
        m = mb.addMenu(_("&Help"))
        m.addAction(self.act_shortcuts)
        m.addAction(self._action(_("Access to the cutter (Linux groups)"), self.show_access_help))
        m.addAction(self._action(_("About Vintyl"), self.about))

    def _make_ribbon(self):
        """The ribbon: groups with a caption under them; big buttons with a label,
        or small icon-only buttons in two rows where a group has many
        (the layout of Kerfly's ribbon, kerfly/gui/main_window.py, commit cf48565)."""
        groups = [
            (_("File"), [(self.act_new, _("New")), (self.act_open, _("Open")), (self.act_save, _("Save")),
                         (self.act_save_cut, _("Save .hpgl"))]),
            (_("Edit"), [(self.act_undo, _("Undo")), (self.act_redo, _("Redo"))]),
            (_("Element"), "grid", [self.act_duplicate, self.act_delete]),
            (_("Transform"), "grid", [self.act_rot_left, self.act_rot_right,
                                      self.act_mirror_h, self.act_mirror_v]),
            (_("Align"), "grid", [self.act_align["left"], self.act_align["centre"], self.act_align["right"],
                                  self.act_distribute_across, self.act_align["top"], self.act_align["middle"],
                                  self.act_align["bottom"], self.act_distribute_up]),
            (_("Shapes"), "grid", [self.act_group, self.act_boolean["union"], self.act_boolean["difference"],
                                   self.act_ungroup, self.act_boolean["intersection"],
                                   self.act_boolean["exclusion"]]),
            (_("View"), [(self.act_fit, _("Fit")), (self.act_knife, _("Knife path")), (self.act_grid, _("Grid"))]),
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
        ("ready", N_("Ready"), None, [("ready", k) for k in ready.READY] + [("act", "act_qr", N_("QR code"))]),
        ("lines", N_("Lines"), "vector", [
            ("tool", "polyline", N_("Polyline"), N_("Polyline: click the corners; the first corner closes it, "
                                                     "double-click or Enter leaves it open"), "vector"),
            ("tool", "line", N_("Line"), N_("Line: drag from end to end"), "line"),
            ("tool", "pen", N_("Pen"), N_("Pen: click = corner, press and drag = smooth curve; the first "
                                          "node closes it, double-click or Enter leaves it open"), "vector-spline"),
            ("tool", "freehand", N_("Freehand"), N_("Freehand: draw with the button held; ending at the start "
                                                    "closes it"), "scribble"),
        ]),
        ("measure", N_("Ruler"), "ruler-measure", [
            ("tool", "measure", N_("Ruler"), N_("Ruler: drag between two points to measure"), "ruler-measure"),
        ]),
        ("text", N_("Text"), "typography", [
            ("tool", "text", N_("Text"), N_("Text: click where it should start"), "typography"),
        ]),
        ("offset", N_("Offset"), "box-padding", [
            ("act", "act_offset", N_("Offset")),
        ]),
        ("fill", N_("Fill"), "rosette", [
            ("act", "act_tile", N_("Pattern of shapes")),
            ("act", "act_fill", N_("Fill")),
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
                            ("polygon", "P"), ("polyline", "L"), ("line", "Shift+L"), ("text", "T"),
                            ("pen", "B"), ("freehand", "F"), ("measure", "M")):
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
        # an action not offered now (the pen's fill with the knife) is left out
        entries = [e for e in self.category_entries[cat] if e[0] != "act" or getattr(self, e[1]).isVisible()]
        if len(entries) == 1 and entries[0][0] == "tool":
            self.set_tool(entries[0][1])
            return None
        if len(entries) == 1 and entries[0][0] == "act":
            getattr(self, entries[0][1]).trigger()
            self.category_buttons[self._category_of[self.view.tool]].setChecked(True)
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
            elif entry[0] == "act":
                a = getattr(self, entry[1])
                b.setIcon(a.icon())
                b.setText(_(entry[2]))
                b.setToolTip(a.toolTip())
                b.clicked.connect(lambda _c=False, act=a, p=popup: (p.close(), act.trigger()))
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
            values = self._ask_ready(_(name), spec, ready.LINKED.get(key, ()))
            if values is None:
                return None
        paths = ready.make(key, **values)
        e = Element(self._name(_(name)), paths, spec=dict(values, kind="ready", shape=key))
        w, h = e.size
        e.move_to(-PLACE_MARGIN_MM - w, -PLACE_MARGIN_MM - h)
        self.add_element(e)
        return e

    def insert_qr(self, text=None, size=30.0, error="m"):
        """A QR code to cut (asks for the text and size when text is None)."""
        if text is None:
            from PySide6.QtWidgets import QDialog, QDialogButtonBox
            dlg = QDialog(self)
            dlg.setWindowTitle(_("QR code"))
            form = QFormLayout(dlg)
            edit = QLineEdit(self.settings.value("qr/text", "https://"))
            edit.setMinimumWidth(320)
            sz = _spin(2000.0, 1, minimum=5.0)
            sz.setValue(float(self.settings.value("qr/size", 30.0)))
            err = QComboBox()
            for code, label in (("l", _("low (7%)")), ("m", _("medium (15%)")), ("q", _("high (25%)")),
                                ("h", _("highest (30%)"))):
                err.addItem(label, code)
            err.setCurrentIndex(1)
            err.setToolTip(_("How much of the code may be damaged and it still reads; more = more modules"))
            form.addRow(_("Text or address"), edit)
            form.addRow(_("Size (mm)"), sz)
            form.addRow(_("Error correction"), err)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            form.addRow(buttons)
            if dlg.exec() != QDialog.Accepted:
                return None
            text, size, error = edit.text(), sz.value(), err.currentData()
            self.settings.setValue("qr/text", text)
            self.settings.setValue("qr/size", size)
        try:
            paths = ready.qr_code(text, size, error)
        except ValueError as e:
            QMessageBox.warning(self, _("QR code"), str(e))
            return None
        e = Element(self._name(_("QR code")), paths,
                    spec={"kind": "ready", "shape": "qr", "text": text, "size": size, "error": error})
        w, h = e.size
        e.move_to(-PLACE_MARGIN_MM - w, -PLACE_MARGIN_MM - h)
        self.add_element(e)
        return e

    def distribute_selected(self, across=True):
        from vintyl.core.design import distribute
        chosen = self._chosen()
        if len(chosen) < 3:
            self.statusBar().showMessage(_("Select three or more shapes to spread them evenly."), 6000)
            return
        self._checkpoint()
        distribute(chosen, across)
        self.refresh()

    def _ask_ready(self, title, spec, linked=()):
        """The parameters of a ready shape. linked: the sizes that keep their
        proportions while the lock is on (on by default)."""
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
        self.ready_lock = None
        linked = [k for k in linked if k in fields]
        if len(linked) >= 2:
            # the lock: change one size and the others follow, so the shape keeps its look
            lock = QCheckBox(_("Keep the proportions"))
            lock.setIcon(icons.tabler("link"))
            lock.setChecked(str(self.settings.value("ready/keep_ratio", "true")).lower() == "true")
            lock.setToolTip(_("Change one size and the others follow, so the shape keeps its look"))
            lock.toggled.connect(lambda on: (lock.setIcon(icons.tabler("link" if on else "link-off")),
                                             self.settings.setValue("ready/keep_ratio", "true" if on else "false")))
            lock.toggled.emit(lock.isChecked())
            form.addRow(lock)
            self.ready_lock = lock
            last = {k: fields[k].value() for k in linked}

            def follow(key, value):
                old = last[key]
                if lock.isChecked() and old > 1e-9:
                    k = value / old
                    for other in linked:
                        if other != key:
                            w = fields[other]
                            w.blockSignals(True)
                            w.setValue(min(w.maximum(), max(w.minimum(), last[other] * k)))
                            w.blockSignals(False)
                for other in linked:
                    last[other] = fields[other].value()
            for k in linked:
                fields[k].valueChanged.connect(lambda v, key=k: follow(key, v))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        self._ready_fields = fields
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
        # one line, not wrapped: a wrapped label makes Qt treat the whole box as
        # rigid (height for width), and the column then squeezed the Cutter box
        # until its rows ran into the Job box
        self.summary.setWordWrap(False)
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
        self.cutter_box = box
        form = QFormLayout(box)
        # only the machine is chosen here; its port, knife and speed are in its settings
        self.profile_box = QComboBox()
        self.profile_box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.profile_box.setMinimumContentsLength(10)
        self.profile_box.currentIndexChanged.connect(self._profile_changed)
        self.btn_profile = QToolButton()
        self.btn_profile.setDefaultAction(self.act_profile)
        self.btn_profile.setToolButtonStyle(Qt.ToolButtonIconOnly)
        machine = QWidget()
        ml = QHBoxLayout(machine)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.addWidget(self.profile_box, 1)
        ml.addWidget(self.btn_profile)
        form.addRow(_("Machine"), machine)
        # what the machine is set to: its port and width, in one line
        self.cutter_info = QLabel()
        self.cutter_info.setWordWrap(False)
        self.cutter_info.setStyleSheet("color: #6b7280")
        form.addRow(self.cutter_info)
        # no permission for the port (or it is not plugged in): what to do, right under it
        self.port_problem = QLabel()
        self.port_problem.setWordWrap(True)
        self.port_problem.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(self.port_problem)
        self.cutter_form = form
        # what is in the holder: the knife cuts, a pen (or a pencil) draws
        self.tool_box = QComboBox()
        self.tool_box.addItem(icons.own("drag-knife"), _("Knife"), "knife")
        self.tool_box.addItem(icons.tabler("pencil"), _("Pen / pencil"), "pen")
        self.tool_box.setToolTip(_("What is in the cutter's holder. Pen: drawing on paper or card, "
                                   "with no knife offset or overcut; fill patterns are drawn too."))
        # bigger than the other fields: the knife or the pen is seen at a glance
        self.tool_box.setObjectName("tool_box")
        self.tool_box.setIconSize(QSize(30, 30))
        self.tool_box.setFixedHeight(46)
        big = self.tool_box.font()
        big.setPointSizeF(big.pointSizeF() * 1.2)
        self.tool_box.setFont(big)
        self.tool_box.view().setFont(big)
        self.tool_box.currentIndexChanged.connect(lambda _i: self._tool_changed())
        tool_label = QLabel(_("Tool"))
        tool_label.setFixedHeight(46)
        tool_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.addRow(tool_label, self.tool_box)
        self.pen_note = QLabel(_("For drawing on paper or card, not for vinyl. To cut vinyl, choose the knife."))
        self.pen_note.setWordWrap(True)
        form.addRow(self.pen_note)
        self.pen_width = _spin(5, 2, " mm", minimum=0.05)
        self.pen_width.setSingleStep(0.05)
        self.pen_width.setValue(pens.DEFAULT_WIDTH_MM)
        self.pen_width.setToolTip(_("How wide a line the pen or pencil draws (a fineliner: 0.3–0.5 mm)"))
        self.pen_place = QComboBox()
        for code, label in (("on", N_("on the line")), ("outside", N_("outside the line")),
                            ("inside", N_("inside the line"))):
            self.pen_place.addItem(_(label), code)
        self.pen_place.setToolTip(_("Where the pen's stroke lies against the line of a closed shape. "
                                    "Outside: the shape keeps its exact size inside the stroke; inside: "
                                    "the stroke stays within the shape. Open lines are drawn on the line."))
        for w in (self.pen_width, self.pen_place):
            (w.valueChanged if w is self.pen_width else w.currentIndexChanged).connect(
                lambda _v: self._tool_changed())
        form.addRow(_("Pen width"), self.pen_width)
        form.addRow(_("Draw"), self.pen_place)
        col.addWidget(box)

        box = QGroupBox(_("Job"))
        self.job_box = box
        lay = QVBoxLayout(box)
        self.job_label = QLabel()
        self.job_label.setWordWrap(True)
        lay.addWidget(self.job_label)
        self.inside_first = QCheckBox(_("Inside shapes first"))
        self.inside_first.setChecked(True)
        self.inside_first.setToolTip(_("Holes and shapes inside others are cut before them, so a piece "
                                       "is never cut free while its holes are still to be cut. "
                                       "Off: exactly the order of the list."))
        self.inside_first.toggled.connect(lambda _v: self.refresh_job())
        lay.addWidget(self.inside_first)
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
        self.frame_row = QWidget()
        self.frame_row.setLayout(frame_row)
        frame_row.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.frame_row)
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

    # ---- the machine ----------------------------------------------------------------
    def reload_profiles(self, select=None, apply=True):
        """Fill the machine list from the profiles (built-in and the user's);
        choose `select` (an id), else the one chosen now, else the first."""
        entries = profiles.catalogue()
        broken = [e for e in entries if e["profile"] is None]
        entries = [e for e in entries if e["profile"] is not None]
        self.profile_entries = {e["id"]: e for e in entries}
        self.profile_names = [e["id"] for e in entries]
        want = select if select in self.profile_entries else self.profile_box.currentData()
        if want not in self.profile_entries:
            want = self.profile_names[0]
        self.profile_box.blockSignals(True)
        self.profile_box.clear()
        for e in entries:
            self.profile_box.addItem(e["profile"].name + (" *" if e["changed"] else ""), e["id"])
        self.profile_box.setCurrentIndex(self.profile_names.index(want))
        self.profile_box.blockSignals(False)
        for e in broken:
            self.statusBar().showMessage(_("A cutter profile cannot be read: %s") % e["error"], 15000)
        if apply:
            self._profile_changed(self.profile_box.currentIndex())

    def use_profile_values(self, **changes):
        """Use the chosen machine with some values changed, for now only (not
        saved; the settings window saves). E.g. knife_offset_mm=0, port=..."""
        self.profile = dataclasses.replace(self.profile, **changes).validate()
        self.refresh()

    def edit_profile(self):
        """The chosen machine's settings window; saved: use what it says."""
        from vintyl.gui.profile_editor import ProfileEditor
        entry = self.profile_entries.get(self.profile_box.currentData())
        if entry is None:
            return None
        dlg = ProfileEditor(entry, self)
        dlg.exec()
        if dlg.chosen is not None:
            self.reload_profiles(dlg.chosen or None)
        return dlg

    def _profile_changed(self, index):
        pid = self.profile_box.itemData(index)
        entry = self.profile_entries.get(pid)
        if entry is None:
            return
        self.profile = entry["profile"]
        self.settings.setValue("cutter/profile", pid)
        # the tool last used in this cutter (a pen stays a pen until changed)
        self._loading_tool = True
        tool = self.settings.value("cutter/tool/" + pid, "knife")
        self.tool_box.setCurrentIndex(max(0, self.tool_box.findData(tool)))
        try:
            self.pen_width.setValue(float(self.settings.value("cutter/pen_width/" + pid, pens.DEFAULT_WIDTH_MM)))
        except (TypeError, ValueError):
            self.pen_width.setValue(pens.DEFAULT_WIDTH_MM)
        self.pen_place.setCurrentIndex(max(0, self.pen_place.findData(
            self.settings.value("cutter/pen_place/" + pid, "on"))))
        self._loading_tool = False
        self._tool_changed(refresh=False)
        self.refresh()

    def is_pen(self):
        return self.tool_box.currentData() == "pen"

    def _tool_changed(self, refresh=True):
        """Knife or pen: show the settings that matter for it, hide the others,
        and remember the choice for this cutter."""
        pen = self.is_pen()
        form = self.cutter_form
        self.inside_first.setVisible(not pen)
        for w in (self.pen_width, self.pen_place):
            form.setRowVisible(w, pen)
        form.setRowVisible(self.pen_note, pen)
        self.frame_row.setVisible(not pen)
        # the fill is for drawing: with the knife it is not offered (it would cut the vinyl into strips)
        self.act_fill.setVisible(pen)
        self.view.pen_mode = pen
        self.act_knife.setText(_("Pen path") if pen else _("Knife path"))
        self.act_knife.setIconText(self.act_knife.text())
        name = self.profile_box.currentData()
        if name and not getattr(self, "_loading_tool", False):
            self.settings.setValue("cutter/tool/" + name, self.tool_box.currentData())
            self.settings.setValue("cutter/pen_width/" + name, self.pen_width.value())
            self.settings.setValue("cutter/pen_place/" + name, self.pen_place.currentData())
        if refresh and not getattr(self, "_loading_tool", False):
            self.refresh()

    def job_profile(self):
        """The chosen machine's profile; with the pen: no knife offset and no
        overcut (no blade trails behind, nothing to close)."""
        if self.is_pen():
            return dataclasses.replace(self.profile, knife_offset_mm=0.0, overcut_mm=0.0)
        return self.profile

    def build(self):
        """The job as it would go to the cutter now (raises JobError / ProfileError)."""
        polys, groups = self.design.material_paths()
        if self.is_pen():
            # the outlines placed against the pen's stroke, each element's fill before its outline,
            # in the list's order (nothing comes loose on paper)
            polys, groups = pens.place(polys, groups, self.pen_width.value(), self.pen_place.currentData())
            fills, fill_groups = self.design.material_fills()
            polys, groups = pens.merge(fills, fill_groups, polys, groups)
            return build_job(polys, self.job_profile(), groups, False)
        frame = self.weed_frame_polyline(polys)
        if frame:
            polys = polys + [frame]                      # in its own last group: cut last
            groups = groups + [max(groups) + 1]
        return build_job(polys, self.job_profile(), groups, self.inside_first.isChecked())

    def weed_frame_polyline(self, polys):
        """The weeding frame (material mm): a rectangle round all that is cut,
        weed_margin away; None when it is off or there is nothing to cut."""
        if not polys or not self.weed_frame.isChecked() or self.is_pen():
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
        if not self.maybe_save():
            return
        self.design = Design()
        self.selected = None
        self.selection = []
        self._undo.clear()
        self._redo.clear()
        self.project_path = None
        self.modified = False
        self.view.fit_requested()
        self.refresh()

    # ---- project files (.vintyl) -------------------------------------------------------------
    def project_settings(self):
        """What a project keeps besides the design: the cutter and the job."""
        return {"profile": self.profile_box.currentData(), "inside_first": self.inside_first.isChecked(),
                "weed_frame": self.weed_frame.isChecked(), "weed_margin_mm": self.weed_margin.value(),
                "tool": self.tool_box.currentData(), "pen_width_mm": self.pen_width.value(),
                "pen_place": self.pen_place.currentData()}

    def _apply_project_settings(self, st):
        # the machine (its knife and port are its own settings, not the project's)
        if st.get("profile") in self.profile_names:
            self.profile_box.setCurrentIndex(self.profile_names.index(st["profile"]))
        if st.get("tool") in ("knife", "pen"):
            self.tool_box.setCurrentIndex(self.tool_box.findData(st["tool"]))
        if st.get("pen_place") in pens.PLACES:
            self.pen_place.setCurrentIndex(self.pen_place.findData(st["pen_place"]))
        for key, widget in (("weed_margin_mm", self.weed_margin), ("pen_width_mm", self.pen_width)):
            if isinstance(st.get(key), (int, float)):
                widget.setValue(float(st[key]))
        for key, box in (("inside_first", self.inside_first), ("weed_frame", self.weed_frame)):
            if isinstance(st.get(key), bool):
                box.setChecked(st[key])

    def open_file(self, path=None):
        """Open a project (.vintyl) or add an SVG file's shapes."""
        if path is None:
            path, _f = QFileDialog.getOpenFileName(
                self, _("Open"), os.path.dirname(self.project_path or ""),
                _("Vintyl projects and SVG files (*.vintyl *.svg);;Vintyl projects (*.vintyl);;SVG files (*.svg)"))
            if not path:
                return None
        if path.lower().endswith(project.EXTENSION):
            return self.open_project(path)
        return self.import_svg(path)

    def open_project(self, path):
        if not self.maybe_save():
            return None
        try:
            design, st = project.load(path)
        except project.ProjectError as err:
            QMessageBox.warning(self, _("Open"), str(err))
            return None
        self.design = design
        self.selected = None
        self.selection = []
        self._undo.clear()
        self._redo.clear()
        self._apply_project_settings(st)
        self.project_path = path
        self.modified = False
        self.view.fit_requested()
        self.refresh()
        self.statusBar().showMessage(_("Opened %s") % os.path.basename(path), 5000)
        return design

    def save_project(self, path=None, ask=False):
        """Save the project; asks for a name the first time (or with ask).
        Returns the path, or None."""
        if path is None:
            path = self.project_path
        if path is None or ask:
            start = self.project_path or (_("design") + project.EXTENSION)
            path, _f = QFileDialog.getSaveFileName(self, _("Save project"), start,
                                                   _("Vintyl projects (*.vintyl)"))
            if not path:
                return None
            if not path.lower().endswith(project.EXTENSION):
                path += project.EXTENSION
        try:
            project.save(path, self.design, self.project_settings())
        except OSError as err:
            QMessageBox.warning(self, _("Save project"), _("Cannot save %s: %s") % (path, err.strerror or err))
            return None
        self.project_path = path
        self.modified = False
        self._update_title()
        self.statusBar().showMessage(_("Saved %s") % os.path.basename(path), 5000)
        return path

    def maybe_save(self):
        """Unsaved changes: ask whether to save them. True: go on."""
        if not getattr(self, "modified", False):
            return True
        answer = QMessageBox.question(
            self, _("Unsaved changes"), _("Save the changes to the project first?"),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.Save:
            return self.save_project() is not None
        return True

    def _update_title(self):
        name = os.path.basename(self.project_path) if self.project_path else _("new project")
        self.setWindowTitle("%s%s – Vintyl" % (name, " *" if getattr(self, "modified", False) else ""))

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

    def _on_pen_drawn(self, paths):
        closed = any(sub["closed"] for sub in paths)
        name = _("Freehand") if self.view.tool == "freehand" else (_("Shape") if closed else _("Curve"))
        self.add_element(Element(self._name(name), paths))
        self.set_tool("select")

    def _on_measured(self, dx, dy):
        import math
        self.statusBar().showMessage(_("Measured: %.2f mm (across %.2f mm, along %.2f mm)")
                                     % (math.hypot(dx, dy), abs(dx), abs(dy)))

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

    # ---- offset --------------------------------------------------------------------------------
    def offset_selected(self, values=None):
        """A new outline round each selected shape (or inside it), as Kerfly's
        Offset: the closed outlines are joined even-odd, so holes move the
        other way. values: {"distance", "outward", "round", "keep", "no_holes"};
        None asks. no_holes: only the outermost outlines stay (a solid backing).
        One undo step. Returns the new elements."""
        from vintyl.core import curves, offset
        chosen = [e for e in self._chosen() if any(sub["closed"] for sub in e.paths)]
        if not chosen:
            self.statusBar().showMessage(_("Select one or more shapes with closed outlines first."), 6000)
            return []
        if values is None:
            values = self._ask_offset()
            if values is None:
                return []
        d = float(values["distance"]) * (1 if values.get("outward", True) else -1)
        join = "round" if values.get("round", True) else "miter"
        made = []
        for e in chosen:
            polys = [p for p in curves.flatten([sub for sub in e.paths if sub["closed"]])]
            rings = [r[:-1] for r in offset.offset_polygons(polys, d, join)]
            if values.get("no_holes"):
                rings = outermost(rings)
            if rings:
                made.append((e, Element("%s: %s" % (_("Offset"), e.name), curves.from_polylines(rings, [True] * len(rings)),
                                        e.cut)))
        if not made:
            self.statusBar().showMessage(_("Nothing is left after the offset (the shape is thinner than that)."), 6000)
            return []
        self._checkpoint()
        for e, new in made:
            i = self.design.elements.index(e)
            if values.get("keep", True):
                self.design.elements.insert(i + 1, new)
            else:
                self.design.elements[i] = new
        self.selection = [new for _e, new in made]
        self.selected = self.selection[0]
        self.refresh()
        return self.selection

    def _ask_offset(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QRadioButton
        dlg = QDialog(self)
        dlg.setWindowTitle(_("Offset"))
        form = QFormLayout(dlg)
        dist = _spin(500.0, 2, minimum=0.01)
        dist.setValue(float(self.settings.value("offset/distance", 3.0)))
        out_btn, in_btn = QRadioButton(_("outwards")), QRadioButton(_("inwards"))
        (out_btn if self.settings.value("offset/outward", "true") == "true" else in_btn).setChecked(True)
        round_btn, sharp_btn = QRadioButton(_("round")), QRadioButton(_("sharp"))
        (round_btn if self.settings.value("offset/round", "true") == "true" else sharp_btn).setChecked(True)
        keep = QCheckBox(_("Keep the original shape"))
        keep.setChecked(self.settings.value("offset/keep", "true") == "true")
        no_holes = QCheckBox(_("Remove the holes inside"))
        no_holes.setToolTip(_("Only the outer outline stays, with no holes (in O, A, a ring): "
                              "a solid backing for a text in another colour"))
        no_holes.setChecked(self.settings.value("offset/no_holes", "false") == "true")
        form.addRow(_("Distance"), dist)
        way = QHBoxLayout()
        way.addWidget(out_btn)
        way.addWidget(in_btn)
        form.addRow(_("Direction"), way)
        corners_box = QWidget()
        corners = QHBoxLayout(corners_box)
        corners.setContentsMargins(0, 0, 0, 0)
        corners.addWidget(round_btn)
        corners.addWidget(sharp_btn)
        form.addRow(_("Corners"), corners_box)
        form.addRow(no_holes)
        form.addRow(keep)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.Accepted:
            return None
        values = {"distance": dist.value(), "outward": out_btn.isChecked(), "round": round_btn.isChecked(),
                  "keep": keep.isChecked(), "no_holes": no_holes.isChecked()}
        for k, v in values.items():
            self.settings.setValue("offset/" + k, str(v).lower() if isinstance(v, bool) else v)
        return values

    # ---- fill patterns (for the pen), after Kerfly's Fill tool ---------------------------------------
    FILL_PATTERNS = [("lines", N_("Lines")), ("cross", N_("Cross-hatch")), ("waves", N_("Waves")),
                     ("zigzag", N_("Zigzag")), ("circles", N_("Circles")), ("honeycomb", N_("Honeycomb")),
                     ("diamonds", N_("Diamonds")), ("bricks", N_("Bricks")), ("concentric", N_("Concentric"))]

    def fill_selected(self, values=None):
        """Give the selected closed shapes a fill pattern (values: None asks;
        {"pattern": None} removes it). Returns the elements filled."""
        if not self.is_pen():                    # a knife does not fill (see _tool_changed)
            return []
        chosen = [e for e in self._chosen() if any(sub["closed"] for sub in e.paths)]
        if not chosen:
            self.statusBar().showMessage(_("Select a closed shape to fill."), 6000)
            return []
        if values is None:
            before = [e.fill for e in chosen]
            values = self._ask_fill(chosen)
            for e, f in zip(chosen, before):        # the preview's changes undone; done properly below
                e.fill = f
            if values is None:
                self.refresh()
                return []
        self._checkpoint()
        for e in chosen:
            e.fill = self._fill_spec(values)
        self.refresh()
        return chosen

    @staticmethod
    def _fill_spec(values):
        if not values.get("pattern"):
            return None
        return {"pattern": values["pattern"], "spacing": float(values["spacing"]),
                "angle": float(values.get("angle", 0.0)), "margin": float(values.get("margin", 0.0))}

    def _place_beside(self, dlg):
        """A dialog with a live preview goes to the right, over the tool bar,
        so it does not hide the middle of the sheet."""
        from PySide6.QtCore import QPoint
        dlg.adjustSize()
        dlg.move(self.mapToGlobal(QPoint(max(0, self.width() - dlg.width() - 100), 110)))

    # ---- a pattern of shapes (for the knife and the pen) ------------------------------------------
    def tile_selected(self, values=None):
        """Rows of small shapes inside the selected closed shape, as a new
        element grouped with it. Returns the new element (or None)."""
        from vintyl.core import tile
        chosen = [e for e in self._chosen() if any(sub["closed"] for sub in e.paths)]
        if not chosen:
            self.statusBar().showMessage(_("Select a closed shape to fill with a pattern of shapes."), 6000)
            return None
        if values is None:
            values = self._ask_tile(chosen)
            if values is None:
                return None
        outline = [sub for e in chosen for sub in e.paths]
        paths, count = tile.tile(outline, tile.motif(values["motif"]), values["size"], values["gap"],
                                 values["stagger"], values["margin"])
        if not count:
            self.statusBar().showMessage(_("No shape fits inside: make them smaller or the margin narrower."),
                                         8000)
            return None
        self._checkpoint()
        import uuid
        gid = chosen[0].group or uuid.uuid4().hex[:8]
        for e in chosen:                          # the pattern moves with its shape
            e.group = gid
        new = Element(self._name(_("Pattern")), paths, chosen[0].cut, group=gid)
        i = max(self.design.elements.index(e) for e in chosen)
        self.design.elements.insert(i, new)        # in the list before its shape: cut before it
        self.selected = new
        self.selection = [new]
        self.refresh()
        self.statusBar().showMessage(ngettext("%d shape placed.", "%d shapes placed.", count) % count, 6000)
        return new

    def _ask_tile(self, chosen):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        from vintyl.core import tile
        from vintyl.gui.previewer import Previewer
        dlg = QDialog(self)
        dlg.setWindowTitle(_("Pattern of shapes"))
        form = QFormLayout(dlg)
        st = self.settings
        motif = QComboBox()
        motif.setIconSize(QSize(22, 22))
        for code in tile.MOTIFS:
            name = tile.BASIC[code][0] if code in tile.BASIC else ready.READY[code][0]
            motif.addItem(shape_icon(tile.motif(code), 22), _(name), code)
        motif.setCurrentIndex(max(0, motif.findData(st.value("tile/motif", "circle"))))
        size = _spin(500.0, 1, " mm", minimum=0.5)
        size.setValue(float(st.value("tile/size", 5.0)))
        size.setToolTip(_("How big each shape is (its longer side)"))
        gap = _spin(500.0, 1, " mm", minimum=0.0)
        gap.setValue(float(st.value("tile/gap", 3.0)))
        gap.setToolTip(_("Vinyl left between the shapes; below about 1.5 mm it tears when weeding"))
        margin = _spin(100.0, 1, " mm", minimum=0.0)
        margin.setValue(float(st.value("tile/margin", 2.0)))
        margin.setToolTip(_("Vinyl kept between the shapes and the outline"))
        stagger = QCheckBox(_("Every second row shifted"))
        stagger.setChecked(st.value("tile/stagger", "true") == "true")
        form.addRow(_("Shape"), motif)
        form.addRow(_("Size"), size)
        form.addRow(_("Gap"), gap)
        form.addRow(_("Margin"), margin)
        form.addRow(stagger)
        note = QLabel(_("Only shapes that fit whole are placed; they are cut before the outline."))
        note.setWordWrap(True)
        form.addRow(note)
        status = QLabel()
        form.addRow(status)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        def values_now():
            return {"motif": motif.currentData(), "size": size.value(), "gap": gap.value(),
                    "margin": margin.value(), "stagger": stagger.isChecked()}

        # the live preview: dashed on the sheet, worked out in the background
        outline = [sub for e in chosen for sub in e.paths]
        prev = Previewer(dlg)

        def ask_preview(*_a):
            v = values_now()
            m = tile.motif(v["motif"])
            prev.request(lambda: tile.tile(outline, m, v["size"], v["gap"], v["stagger"], v["margin"]))

        def show(result):
            if isinstance(result, Exception):
                self.view.show_preview(None)
                status.setText(_("Cannot work it out: %s") % result)
                return
            paths, count = result
            self.view.show_preview(paths)
            status.setText(ngettext("%d shape fits.", "%d shapes fit.", count) % count if count else
                           _("No shape fits inside: make them smaller or the margin narrower."))
        prev.ready.connect(show)
        prev.busy.connect(lambda b: b and status.setText(_("Working it out…")))
        motif.currentIndexChanged.connect(ask_preview)
        for w in (size, gap, margin):
            w.valueChanged.connect(ask_preview)
        stagger.toggled.connect(ask_preview)
        ask_preview()
        self._place_beside(dlg)
        accepted = dlg.exec() == QDialog.Accepted
        prev.wait()
        self.view.show_preview(None)
        if not accepted:
            return None
        values = values_now()
        for k, v in values.items():
            st.setValue("tile/" + k, str(v).lower() if isinstance(v, bool) else v)
        return values

    def _ask_fill(self, chosen):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        from vintyl.gui.previewer import Previewer
        current = chosen[0].fill
        dlg = QDialog(self)
        dlg.setWindowTitle(_("Fill"))
        form = QFormLayout(dlg)
        pattern = QComboBox()
        for code, label in self.FILL_PATTERNS:
            pattern.addItem(_(label), code)
        st = self.settings
        start = current or {"pattern": st.value("fill/pattern", "lines"),
                            "spacing": st.value("fill/spacing", 1.0), "angle": st.value("fill/angle", 45.0),
                            "margin": st.value("fill/margin", 0.0)}
        pattern.setCurrentIndex(max(0, pattern.findData(start["pattern"])))
        spacing = _spin(100.0, 2, " mm", minimum=0.05)
        spacing.setSingleStep(0.1)
        spacing.setValue(float(start["spacing"]))
        spacing.setToolTip(_("Distance between the lines (the size of one repeat). For a solid fill: "
                             "a little less than the pen's width."))
        angle = _spin(180.0, 1, "°", minimum=-180.0)
        angle.setValue(float(start["angle"]))
        margin = _spin(50.0, 2, " mm", minimum=0.0)
        margin.setValue(float(start["margin"]))
        margin.setToolTip(_("Keep the pattern this far from the outline"))
        form.addRow(_("Pattern"), pattern)
        form.addRow(_("Spacing"), spacing)
        form.addRow(_("Angle"), angle)
        form.addRow(_("Margin"), margin)
        status = QLabel()
        form.addRow(status)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        remove = buttons.addButton(_("Remove the fill"), QDialogButtonBox.DestructiveRole)
        removed = []
        remove.clicked.connect(lambda: (removed.append(True), dlg.accept()))
        remove.setEnabled(bool(current))
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        def values_now():
            return {"pattern": pattern.currentData(), "spacing": spacing.value(), "angle": angle.value(),
                    "margin": margin.value()}

        # the live preview: the shapes show the fill as it would be; worked out in
        # the background (into the fill cache), then drawn
        prev = Previewer(dlg)

        def ask_preview(*_a):
            spec = self._fill_spec(values_now())
            copies = [e.copy() for e in chosen]

            def work():
                for c in copies:
                    c.fill = spec
                    c.fill_lines()
                return spec
            prev.request(work)

        def show(result):
            if isinstance(result, Exception):
                status.setText(_("Cannot work it out: %s") % result)
                return
            status.setText("")
            for e in chosen:
                e.fill = dict(result)
            self.refresh()
        prev.ready.connect(show)
        prev.busy.connect(lambda b: b and status.setText(_("Working it out…")))
        pattern.currentIndexChanged.connect(ask_preview)
        for w in (spacing, angle, margin):
            w.valueChanged.connect(ask_preview)
        ask_preview()
        self._place_beside(dlg)
        accepted = dlg.exec() == QDialog.Accepted
        prev.wait()
        if not accepted:
            return None
        if removed:
            return {"pattern": None}
        values = values_now()
        for k, v in values.items():
            st.setValue("fill/" + k, v)
        return values

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

    # ---- grid and settings ---------------------------------------------------------------------
    def set_grid(self, on):
        """Grid on: shown at the step from the Settings, and things snap to it."""
        self.view.grid_mm = self.grid_step if on else 0.0
        self.settings.setValue("view/grid", "true" if on else "false")
        self.refresh()

    def show_settings(self, values=None):
        """The program's settings. values: {"grid_step", "snap_objects"} without
        asking (for the tests); None asks."""
        if values is None:
            from PySide6.QtWidgets import QDialog, QDialogButtonBox
            dlg = QDialog(self)
            dlg.setWindowTitle(_("Settings"))
            form = QFormLayout(dlg)
            step = _spin(1000.0, 1, minimum=0.5)
            step.setValue(self.grid_step)
            step.setToolTip(_("Distance between the grid's lines; drawing and nodes snap to them "
                              "while the grid is on"))
            snap = QCheckBox(_("Snap to other shapes (corners, centres, edges)"))
            snap.setChecked(self.view.snap_objects)
            snap.setToolTip(_("Hold Alt to drag without any snapping for a moment"))
            form.addRow(_("Grid step"), step)
            form.addRow(snap)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            form.addRow(buttons)
            if dlg.exec() != QDialog.Accepted:
                return None
            values = {"grid_step": step.value(), "snap_objects": snap.isChecked()}
        self.grid_step = float(values["grid_step"])
        self.view.snap_objects = bool(values["snap_objects"])
        self.settings.setValue("view/grid_step", self.grid_step)
        self.settings.setValue("view/snap_objects", "true" if self.view.snap_objects else "false")
        if self.act_grid.isChecked():
            self.view.grid_mm = self.grid_step
        self.refresh()
        return values

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
        self.modified = True
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
        self._update_title()
        self.refresh_job()

    def _show_machine(self):
        """The machine's line under its name: connection, port, width."""
        p = self.profile
        conn = _("USB printer") if p.connection == "usb-printer" else _("serial port")
        self.cutter_info.setText("%s · %s · %s" % (conn, p.port or _("no port"), _("cuts %g mm") % p.width_mm))
        self.cutter_info.setToolTip(_("Knife offset %(k).2f mm, overcut %(o).2f mm, %(lang)s. "
                                      "Change them in the cutter's settings (the button beside it).")
                                    % {"k": p.knife_offset_mm, "o": p.overcut_mm, "lang": p.language.upper()})

    def check_port_access(self):
        """Show under the machine what to do when this user may not use its
        port, or that it is not plugged in. Returns the problem (or None)."""
        self._show_machine()
        port = self.profile.port
        problem = transport.access_problem(port)
        if problem:
            text, color = problem, "#b91c1c"
        elif port and not os.path.exists(port):
            text, color = _("%s is not there now: plug the cutter in and switch it on, or choose "
                            "its port in the cutter's settings.") % port, "#6b7280"
        else:
            text, color = "", "#6b7280"
        self.port_problem.setText(text)
        self.port_problem.setStyleSheet("color: %s" % color)
        self.cutter_form.setRowVisible(self.port_problem, bool(text))
        return problem

    def show_access_help(self):
        port = self.profile.port
        problem = transport.access_problem(port)
        now = (_("Now: %s") % problem) if problem else (
            _("Now: you may use %s.") % port if port else _("Now: no port is chosen."))
        box = QMessageBox(self)
        box.setWindowTitle(_("Access to the cutter"))
        box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box.setText(_(
            "On Linux a cutter is a device file, and only the members of its group may send to it:\n\n"
            "• a cutter connected as a USB printer (/dev/usb/lp0, as the VEVOR KI-375A): the group lp\n"
            "• a serial port or a USB-serial cable (/dev/ttyUSB0, /dev/ttyACM0): the group dialout "
            "(on Arch and Manjaro: uucp)\n\n"
            "Join the group once, in a terminal:\n"
            "    sudo usermod -aG lp $USER\n"
            "    sudo usermod -aG dialout $USER\n"
            "then log out and in again (a running session keeps its old groups).\n\n"
            "Vintyl checks the port you choose and says under it which group that device needs.")
            + "\n\n" + now)
        box.exec()

    def refresh_job(self):
        self.check_port_access()
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
        text = (_("Drawn length: %.2f m · travel: %.2f m") if self.is_pen() else
                _("Cut length: %.2f m · travel: %.2f m")) % (j.cut_mm / 1000.0, j.travel_mm / 1000.0)
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
        if self.is_pen():
            ask = (_("Draw now?"),
                   _("Send the drawing to %s (%s)?\n\n"
                     "Tool: PEN. Check before you go on:\n"
                     "• the pen (not the knife) is in the holder, its tip just above the paper\n"
                     "• the force on the cutter's panel is LOW, for a pen\n"
                     "• the paper is under the pinch rollers\n"
                     "• the origin is set (Origin key) where the drawing should start\n\n"
                     "To stop the cutter at once: Test (pause) or Reset on its panel.") % (p.port, p.name))
        else:
            ask = (_("Cut now?"),
                   _("Send the design to %s (%s)?\n\n"
                     "Tool: KNIFE. Check before you go on:\n"
                     "• the knife is in the holder\n"
                     "• the material is under the pinch rollers\n"
                     "• the origin is set (Origin key) where the design should start\n"
                     "• speed and force are set on the cutter's panel\n\n"
                     "To stop the cutter at once: Test (pause) or Reset on its panel.") % (p.port, p.name))
        if QMessageBox.question(self, ask[0], ask[1]) != QMessageBox.Yes:
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
        for w in (self.btn_start, self.btn_save, self.act_save_cut, self.profile_box, self.act_profile,
                  self.view):
            w.setEnabled(not on)

    def closeEvent(self, event):
        if not self.maybe_save():
            event.ignore()
            return
        w = getattr(self, "worker", None)
        if w is not None and w.isRunning():
            w.request_stop()
            w.wait(15000)
        super().closeEvent(event)

    def about(self):
        QMessageBox.about(self, _("About Vintyl"),
                          _("Vintyl %s\nSoftware for vinyl cutters.\nGPL-3.0-or-later.") % __version__)
