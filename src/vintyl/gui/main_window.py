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
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFontComboBox, QFormLayout,
                               QFrame, QLineEdit, QMenu, QScrollArea,
                               QProgressBar, QSpinBox, QToolButton,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QPushButton, QSizePolicy,
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
from vintyl.core.loaders import LoadError, load_svg, load_svg_colors
from vintyl.core.profile import ProfileError
from vintyl.gui import N_, NP_, _, ngettext, pgettext
from vintyl.gui import icons
from vintyl.gui import theme
from vintyl.gui import widgets
from vintyl.gui.canvas import MaterialView, painter_path, shape_icon
from vintyl.gui.sender import SendWorker
from vintyl.gui import text as texts
from vintyl.gui.widgets import COLOR_ROLE, ICON_ROLE, Segmented, Switch, ToolTile

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
        """The least height the panel needs: the sections that keep their
        height at their full height (with wrapped text at this width), the
        one that gives way (the element list) at its minimum."""
        col = panel.layout()
        m = col.contentsMargins()
        width = panel.width() - m.left() - m.right()
        total, shown = m.top() + m.bottom(), 0
        for i in range(col.count()):
            w = col.itemAt(i).widget()
            if w is None or w.isHidden():
                continue
            fixed = w.sizePolicy().verticalPolicy() == QSizePolicy.Fixed
            h = (w.sizeHint() if fixed else w.minimumSizeHint()).height()
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
        # "a new version is available", right under the ribbon (hidden until a
        # check finds one)
        from vintyl.gui.update_check import UpdateBar
        self.update_bar = UpdateBar(self)
        self.update_bar.skip.connect(lambda v: self.settings.setValue("updates/skip", v))
        outer.addWidget(self.update_bar)
        # the selection bar: two rows (the second only for a text), so it never
        # scrolls sideways (UI v2)
        outer.addWidget(self._make_options_bar())
        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        # the left panel scrolls when the window is too low for it, instead of
        # squeezing its rows into each other; Start and the rest stay under it
        left = QWidget()
        left_col = QVBoxLayout(left)
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(0)
        self.left_scroll = _SideScroll(self._make_left_panel())
        left_col.addWidget(self.left_scroll, 1)
        self.send_footer.setFixedWidth(self.left_scroll.width())
        left_col.addWidget(self.send_footer)
        middle.addWidget(left)
        middle.addWidget(self.view, 1)
        middle.addWidget(self.tool_panel)
        outer.addLayout(middle, 1)
        self.setCentralWidget(central)

        self.cursor_label = QLabel()
        self.selected_label = QLabel()                 # "Selected: <name>" (UI v2)
        self.profile_label = QLabel()
        self.statusBar().addWidget(self.cursor_label)
        self.statusBar().addWidget(self.selected_label)
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
        s.context.connect(self.show_context_menu)
        s.resized.connect(self._on_resized)
        s.nudged.connect(self._on_moved)
        s.nodes_changed.connect(self._on_nodes_changed)
        s.edit_nodes.connect(self._on_edit_nodes)
        s.cancel_tool.connect(lambda: self.set_tool("select"))
        s.node_selection.connect(self._on_node_selection)
        s.cursor.connect(lambda x, y: self.cursor_label.setText(_("Cursor: %.1f / %.1f mm") % (x, y)))
        self.resize(1440, 900)
        # the materials, then the cutter used last time (not always the first one)
        self.material_entries = {}
        self.reload_materials()
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
            # called with no arguments: Qt passes "checked" (False), and a
            # method such as about(show=True) then took it for show=False and
            # built its window without opening it (About, Shortcuts, Access)
            a.triggered.connect(lambda _checked=False, s=slot: s())
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
        # as Kerfly's "design to the head": here the head starts at the origin
        # (set with the cutter's Origin key), so the design goes there
        self.act_to_origin = self._action(_("Move to the origin"), lambda: self.move_to_origin(),
                                          "arrow-down-right", "Ctrl+Home",
                                          _("The selected elements, or the whole design when nothing is "
                                            "selected, together up to the origin (0, 0): no vinyl wasted "
                                            "before them. Room is left for the weeding frame and the knife"))
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
        self.act_copies = self._action(_("Copies…"), lambda: self.copies_selected(), "copy-plus", None,
                                       _("Many copies of the selection in rows and columns, a gap apart"))
        self.act_panels = self._action(_("Split into strips…"), lambda: self.split_into_strips(), "table", None,
                                       _("A design wider than the cutter (or longer than the sheet): cut it in "
                                         "strips that overlap, laid one after another on the material"))
        self.act_weed_lines = self._action(_("Weeding lines…"), lambda: self.add_weeding_lines(), "slash", None,
                                           _("Cuts through the waste vinyl between the shapes, so it peels off "
                                             "in strips"))
        self.act_knife_test = self._action(_("Knife test"), lambda: self.knife_test(), None, None,
                                           _("Cut a small square with a triangle to check the knife's force"))
        self.act_text_path = self._action(_("Text on a path"), lambda: self.put_text_on_path(), "circle-dashed",
                                          None, _("Set the selected text along the selected shape (a line, "
                                                  "a curve, a circle...): select the text and the shape"))
        self.selection_actions = [self.act_offset, self.act_fill, self.act_tile, self.act_text_path, self.act_copies,
                                  self.act_cut, self.act_copy, self.act_group, self.act_ungroup,
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
        self.menus = {}
        m = mb.addMenu(_("&File"))
        self.menus["file"] = m
        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as, None, self.act_save_cut, None,
                  self.act_quit):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Edit"))
        self.menus["edit"] = m
        for a in (self.act_undo, self.act_redo, None, self.act_cut, self.act_copy, self.act_paste,
                  self.act_duplicate, self.act_delete, None, self.act_select_all):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Object"))
        self.menus["object"] = m
        for a in [self.act_group, self.act_ungroup, None] + list(self.act_boolean.values()) + [None] + \
                [self.act_rot_left, self.act_rot_right, self.act_mirror_h, self.act_mirror_v, None] + \
                list(self.act_align.values()) + [self.act_to_origin, None, self.act_offset, self.act_tile,
                                                 self.act_fill,
                                                 self.act_text_path, None, self.act_copies, self.act_panels,
                                                 self.act_weed_lines]:
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Cutter"))
        self.menus["cutter"] = m
        m.addAction(self.act_profile)
        m.addAction(self.act_knife_test)
        m = mb.addMenu(_("&View"))
        self.menus["view"] = m
        for a in (self.act_fit, self.act_zoom_in, self.act_zoom_out, None, self.act_knife, self.act_grid):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu(_("&Settings"))
        self.menus["settings"] = m
        m.addAction(self.act_settings)
        m = mb.addMenu(_("&Help"))
        self.menus["help"] = m
        m.addAction(self.act_shortcuts)
        m.addAction(self._action(_("Access to the cutter (Linux groups)"), self.show_access_help))
        m.addSeparator()
        m.addAction(self._action(_("Diagnostic report…"), lambda: self.show_diagnostics(), "bug",
                                 tip=_("Versions, checks, the cutter and the log, to paste into a report")))
        m.addAction(self._action(_("Check for a new version"), lambda: self.check_for_updates(auto=False),
                                 "cloud-download"))
        from vintyl.gui import desktop_entry
        self.act_menu_entry = self._action(_("Add Vintyl to the applications menu"),
                                           lambda: self.install_menu_entry(), None,
                                           tip=_("Put this AppImage into the desktop's menu and open "
                                                 ".vintyl projects with it"))
        self.act_menu_entry.setVisible(desktop_entry.applies())
        m.addAction(self.act_menu_entry)
        m.addSeparator()
        m.addAction(self._action(_("About Vintyl"), self.about))

    def _make_ribbon(self):
        """The ribbon (UI v2): groups with a caption under them. File, Edit and
        View: big buttons with the label under the icon; Element and Shapes:
        small buttons with the label beside the icon, in two rows; Transform
        and Align: icons only, in two rows, with tooltips. A button that is on
        (Grid, Knife path) has the accent's soft background. The groups that
        work on a selection are greyed out while nothing is selected (their
        actions are disabled, see _enable_selection_actions). After Kerfly's
        ribbon (kerfly/gui/main_window.py, commit cf48565)."""
        big, beside, icons_only = "big", "beside", "icons"
        # the labels on the ribbon have their own context: a language may give
        # them shorter words than the menus have, so the ribbon fits 1366 px
        groups = [
            (_("File"), big, [(self.act_new, pgettext("ribbon", "New")), (self.act_open, pgettext("ribbon", "Open")),
                              (self.act_save, pgettext("ribbon", "Save")),
                              (self.act_save_cut, pgettext("ribbon", "Save .hpgl"))]),
            (_("Edit"), big, [(self.act_undo, pgettext("ribbon", "Undo")), (self.act_redo, pgettext("ribbon", "Redo"))]),
            (_("Element"), beside, [(self.act_duplicate, pgettext("ribbon", "Duplicate")),
                                    (self.act_delete, pgettext("ribbon", "Delete"))]),
            (_("Transform"), icons_only, [self.act_rot_left, self.act_rot_right,
                                          self.act_mirror_h, self.act_mirror_v]),
            (_("Align"), icons_only, [self.act_align["left"], self.act_align["centre"], self.act_align["right"],
                                      self.act_distribute_across, self.act_align["top"], self.act_align["middle"],
                                      self.act_align["bottom"], self.act_distribute_up]),
            (_("Shapes"), beside, [(self.act_group, pgettext("ribbon", "Group")),
                                   (self.act_boolean["union"], pgettext("ribbon", "Union")),
                                   (self.act_boolean["difference"], pgettext("ribbon", "Difference")),
                                   (self.act_ungroup, pgettext("ribbon", "Ungroup")),
                                   (self.act_boolean["intersection"], pgettext("ribbon", "Intersection")),
                                   (self.act_boolean["exclusion"], pgettext("ribbon", "Exclusion"))]),
            (_("View"), big, [(self.act_to_origin, pgettext("ribbon", "To 0,0")), (self.act_fit, pgettext("ribbon", "Fit")),
                              (self.act_knife, pgettext("ribbon", "Knife path")),
                              (self.act_grid, pgettext("ribbon", "Grid"))]),
        ]
        tb = QToolBar(_("Main"))
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        self.ribbon_groups = {}
        for i, (title, kind, entries) in enumerate(groups):
            if i:
                line = QFrame()
                line.setFrameShape(QFrame.VLine)
                line.setObjectName("ribbon_separator")
                tb.addWidget(line)
            group = QWidget()
            v = QVBoxLayout(group)
            v.setContentsMargins(2, 2, 2, 0)
            v.setSpacing(0)
            if kind == big:
                row = QHBoxLayout()
                row.setSpacing(2)
                for action, short in entries:
                    action.setIconText(short)
                    button = QToolButton()
                    button.setDefaultAction(action)
                    button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                    button.setIconSize(QSize(22, 22))
                    button.setAutoRaise(True)
                    button.setFixedHeight(54)
                    button.setMinimumWidth(52)
                    row.addWidget(button, 0, Qt.AlignTop)
                v.addLayout(row)
            else:
                grid = QGridLayout()
                grid.setHorizontalSpacing(4 if kind == beside else 2)
                grid.setVerticalSpacing(2)
                per_row = (len(entries) + 1) // 2
                for n, entry in enumerate(entries):
                    button = QToolButton()
                    button.setAutoRaise(True)
                    if kind == beside:
                        action, short = entry
                        if short:
                            action.setIconText(short)
                        button.setDefaultAction(action)
                        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                        button.setIconSize(QSize(18, 18))
                        button.setFixedHeight(26)
                        button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                    else:
                        button.setDefaultAction(entry)
                        button.setToolButtonStyle(Qt.ToolButtonIconOnly)
                        button.setIconSize(QSize(20, 20))
                        button.setFixedSize(34, 26)
                    grid.addWidget(button, n // per_row, n % per_row)
                v.addLayout(grid)
                v.addStretch(1)
            caption = QLabel(title)
            caption.setObjectName("ribbon_caption")
            caption.setAlignment(Qt.AlignHCenter)
            v.addWidget(caption)
            tb.addWidget(group)
            self.ribbon_groups[title] = group
        self.addToolBar(Qt.TopToolBarArea, tb)

    # the right-hand bar: a button per category; a click opens a square of
    # icons beside it (as SignMaster's), a category with one tool takes it at
    # once. Only the basic drawing tools: what the ribbon on top has
    # (transform, align, duplicate, delete) is not repeated.
    # A tool: ("tool", key, label, tooltip, icon); a ready shape: ("ready", key)
    PANEL = [
        ("pick", NP_("tool strip", "Select"), "pointer", [
            ("tool", "select", N_("Select"), N_("Select and move"), "pointer"),
        ]),
        ("nodes", NP_("tool strip", "Nodes"), "vector-bezier-2", [
            ("tool", "nodes", N_("Nodes"), N_("Edit nodes (or double-click an element)"), "vector-bezier-2"),
        ]),
        ("shapes", NP_("tool strip", "Shapes"), "square", [
            ("tool", "rectangle", N_("Rectangle"), N_("Rectangle: drag from corner to corner"), "square"),
            ("tool", "ellipse", N_("Ellipse"), N_("Ellipse: drag the box it fits in"), "circle"),
            ("tool", "polygon", N_("Polygon"), N_("Regular polygon: drag the box it fits in; the number of "
                                                  "sides is in the options bar"), "polygon"),
        ]),
        ("ready", NP_("tool strip", "Ready"), None, [("ready", k) for k in ready.READY] + [("act", "act_qr", N_("QR code"))]),
        ("lines", NP_("tool strip", "Lines"), "vector", [
            ("tool", "polyline", N_("Polyline"), N_("Polyline: click the corners; the first corner closes it, "
                                                     "double-click or Enter leaves it open"), "vector"),
            ("tool", "line", N_("Line"), N_("Line: drag from end to end"), "line"),
            ("tool", "pen", N_("Pen"), N_("Pen: click = corner, press and drag = smooth curve; the first "
                                          "node closes it, double-click or Enter leaves it open"), "vector-spline"),
            ("tool", "freehand", N_("Freehand"), N_("Freehand: draw with the button held; ending at the start "
                                                    "closes it"), "scribble"),
        ]),
        ("text", NP_("tool strip", "Text"), "typography", [
            ("tool", "text", N_("Text"), N_("Text: click where it should start"), "typography"),
            ("act", "act_text_path", N_("Text on a path")),
        ]),
        ("offset", NP_("tool strip", "Offset"), "box-padding", [
            ("act", "act_offset", N_("Offset")),
        ]),
        ("fill", NP_("tool strip", "Fill"), "rosette", [
            ("act", "act_tile", N_("Pattern of shapes")),
            ("act", "act_fill", N_("Fill")),
        ]),
        ("measure", NP_("tool strip", "Ruler"), "ruler-measure", [
            ("tool", "measure", N_("Ruler"), N_("Ruler: drag between two points to measure"), "ruler-measure"),
        ]),
    ]
    PANEL_BREAKS = ("offset", "measure")      # a line before these categories (UI v2)

    def _make_tool_strip(self):
        from PySide6.QtWidgets import QButtonGroup
        panel = QWidget()
        panel.setObjectName("tool_panel")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        panel.setFixedWidth(76)
        col = QVBoxLayout(panel)
        col.setContentsMargins(5, 8, 5, 8)
        col.setSpacing(4)
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
            if cat in self.PANEL_BREAKS:
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setObjectName("panel_line")
                col.addWidget(line)
            cb = ToolTile(has_set=len(entries) > 1)
            cb.setObjectName("tool_tile")
            cb.setIconSize(QSize(22, 22))
            cb.setFixedSize(66, 54)
            cb.setIcon(icons.tabler(icon) if icon else icons.tabler("star"))
            # the strip's own words (context "tool strip"): a language may give
            # a shorter one than its menus, so it fits the 66 px tile
            cb.setText(pgettext("tool strip", title))
            self._fit_tile_text(cb, any(e[0] == "tool" for e in entries))
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

    @staticmethod
    def _fit_tile_text(tile, can_be_chosen):
        """A name too wide for its tile (a wide font such as DejaVu Sans, a
        long word) is written a pixel smaller instead of being cut; bold when
        the tile can be the chosen one (the style sheet makes it bold then)."""
        from PySide6.QtGui import QFont, QFontMetrics
        tile.ensurePolished()
        font = QFont(tile.font())
        if can_be_chosen:
            font.setWeight(QFont.DemiBold)
        if QFontMetrics(font).horizontalAdvance(tile.text()) > tile.width() - 6:
            tile.setStyleSheet("font-size: 9px;")

    def _offered(self, cat):
        """The entries of a category offered now (the pen's fill not with the knife)."""
        return [e for e in self.category_entries[cat] if e[0] != "act" or getattr(self, e[1]).isVisible()]

    def _mark_sets(self):
        """The small triangle only on a category whose click opens a set now
        (with the knife Fill goes straight to the pattern of shapes)."""
        for cat, button in self.category_buttons.items():
            button.has_set = len(self._offered(cat)) > 1
            button.update()

    def show_category(self, cat):
        """A click on a category: one tool takes it at once; more open a square
        of icons beside the button. Returns the square (or None)."""
        # an action not offered now (the pen's fill with the knife) is left out
        entries = self._offered(cat)
        if len(entries) == 1 and entries[0][0] == "tool":
            self.set_tool(entries[0][1])
            return None
        if len(entries) == 1 and entries[0][0] == "act":
            getattr(self, entries[0][1]).trigger()
            self.category_buttons[self._category_of[self.view.tool]].setChecked(True)
            return None
        # the set: a white card with a shadow, each tool with its name and its key
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        popup = QFrame(self, Qt.Popup | Qt.FramelessWindowHint)
        popup.setAttribute(Qt.WA_TranslucentBackground, True)
        holder = QVBoxLayout(popup)
        holder.setContentsMargins(10, 10, 10, 10)
        card = QFrame()
        card.setObjectName("tool_popup")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 60))
        card.setGraphicsEffect(shadow)
        holder.addWidget(card)
        grid = QGridLayout(card)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(4)
        per_row = 4 if len(entries) > 6 else (2 if len(entries) > 1 else 1)
        for n, entry in enumerate(entries):
            key_name = ""
            if entry[0] == "tool":
                seq = self.tool_actions[entry[1]].shortcut()
                key_name = seq.toString(QKeySequence.NativeText) if not seq.isEmpty() else ""
            elif entry[0] == "act":
                seq = getattr(self, entry[1]).shortcut()
                key_name = seq.toString(QKeySequence.NativeText) if not seq.isEmpty() else ""
            b = ToolTile(hint=key_name)
            b.setObjectName("tool_tile")
            b.setIconSize(QSize(22, 22))
            b.setFixedSize(96, 70 if key_name else 60)
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
            # a name too long for the tile ("Rounded rectangle") goes on two
            # lines, not cut in the middle
            text = b.text()
            if b.fontMetrics().horizontalAdvance(text) > b.width() - 10 and " " in text:
                spaces = [i for i, c in enumerate(text) if c == " "]
                cut = min(spaces, key=lambda i: abs(i - len(text) / 2))
                b.setText(text[:cut] + "\n" + text[cut + 1:])
                b.setFixedHeight(b.height() + 14)
            grid.addWidget(b, n // per_row, n % per_row)
        # one tile on two lines: all of the set as high, so the icons line up
        tiles = card.findChildren(ToolTile)
        tallest = max(t.height() for t in tiles)
        for t in tiles:
            t.setFixedHeight(tallest)
        # beside the category's button, on the side of the material
        button = self.category_buttons[cat]
        popup.adjustSize()
        top_left = button.mapToGlobal(button.rect().topLeft())
        popup.move(top_left.x() - popup.width() + 6, top_left.y() - 10)
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
            values = self._ask_ready(_(name), spec, ready.LINKED.get(key, ()), key)
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
            edit = QLineEdit(self.settings.value("qr/text", "https://"))
            edit.setMinimumWidth(320)
            sz = _spin(2000.0, 1, minimum=5.0)
            sz.setValue(float(self.settings.value("qr/size", 30.0)))
            err = QComboBox()
            for code, label in (("l", _("low (7%)")), ("m", _("medium (15%)")), ("q", _("high (25%)")),
                                ("h", _("highest (30%)"))):
                err.addItem(label, code)
            err.setCurrentIndex(1)
            got = widgets.form_dialog(self, _("QR code"), [("text", _("Text or address"), edit),
                                                          ("size", _("Size (mm)"), sz),
                                                          ("error", _("Error correction"), err)],
                                      action=_("Insert"),
                                      hint=_("Error correction: how much of the code may be damaged and it still "
                                             "reads; more = more modules."))
            if got is None:
                return None
            text, size, error = edit.text(), sz.value(), err.currentData()
            self.settings.setValue("qr/text", text)
            self.settings.setValue("qr/size", size)
        try:
            paths = ready.qr_code(text, size, error)
        except ValueError as e:
            widgets.warn(self, _("QR code"), str(e))
            return None
        e = Element(self._name(_("QR code")), paths,
                    spec={"kind": "ready", "shape": "qr", "text": text, "size": size, "error": error})
        w, h = e.size
        e.move_to(-PLACE_MARGIN_MM - w, -PLACE_MARGIN_MM - h)
        self.add_element(e)
        return e

    def move_to_origin(self):
        """The selected elements, or the whole design when nothing is selected,
        moved together (as they are laid out) so their corner is at the origin
        (0, 0): the cutter's head starts there, no vinyl is wasted before them.
        What the knife cuts beyond the shapes needs room: the weeding frame
        (its margin), the knife offset and the overcut; the least room with
        which the job can be made is kept. Returns how far from the origin (mm)."""
        chosen = self._chosen() or list(self.design.elements)
        if not chosen:
            self.statusBar().showMessage(_("Nothing to move: the design is empty."), 6000)
            return None
        self._checkpoint()
        # the bottom right corner of their box (the origin's corner) onto 0, 0
        boxes = [e.bounds for e in chosen]
        xmax, ymax = max(b[1] for b in boxes), max(b[3] for b in boxes)
        for e in chosen:
            e.move_by(-xmax, -ymax)
        p = self.job_profile()
        knife = p.knife_offset_mm + p.overcut_mm
        frame = self.weed_margin.value() if self.weed_frame.isChecked() and not self.is_pen() else 0.0
        tries = [0.0] if frame == 0 and knife == 0 else [frame, frame + knife, frame + knife + 1.0]
        moved = 0.0
        for gap in tries + [frame + knife]:
            for e in chosen:
                e.move_by(moved - gap, moved - gap)
            moved = gap
            try:
                self.build()
                break                                   # this close the job can be made
            except (JobError, ProfileError):
                continue                                # (the last: the room it needs, for another error)
        self.refresh()
        self.statusBar().showMessage(_("Moved to the origin (%s mm from it).") % MaterialView._mm(moved)
                                     if moved else _("Moved to the origin."), 6000)
        return moved

    def distribute_selected(self, across=True):
        from vintyl.core.design import distribute
        chosen = self._chosen()
        if len(chosen) < 3:
            self.statusBar().showMessage(_("Select three or more shapes to spread them evenly."), 6000)
            return
        self._checkpoint()
        distribute(chosen, across)
        self.refresh()

    def _ask_ready(self, title, spec, linked=(), key=None):
        """The parameters of a ready shape (UI v2: its picture on the left,
        changing with the fields). linked: the sizes that keep their
        proportions while the switch is on (on by default)."""
        fields = {}
        rows = []
        for k, label, default, lo, hi, step in spec:
            if isinstance(default, int):
                w = QSpinBox()
                w.setRange(int(lo), int(hi))
            else:
                w = QDoubleSpinBox()
                w.setRange(lo, hi)
                w.setDecimals(1 if step >= 0.5 else 2)
                w.setSingleStep(step)
            w.setValue(default)
            rows.append((k, _(label), w))
            fields[k] = w
        # the picture of the shape, drawn again at every change
        preview = QLabel()
        preview.setFixedSize(112, 112)
        preview.setAlignment(Qt.AlignCenter)

        def redraw(*_a):
            if key is None:
                return
            try:
                preview.setPixmap(shape_icon(ready.make(key, **{k: w.value() for k, w in fields.items()}),
                                             96, theme.token("accent")).pixmap(96, 96))
            except (ValueError, ZeroDivisionError):
                preview.clear()
        for w in fields.values():
            w.valueChanged.connect(redraw)
        redraw()
        self.ready_lock = None
        linked = [k for k in linked if k in fields]
        if len(linked) >= 2:
            # the switch: change one size and the others follow, so the shape keeps its look
            lock = Switch(_("Keep the proportions"))
            lock.setChecked(str(self.settings.value("ready/keep_ratio", "true")).lower() == "true")
            lock.setToolTip(_("Change one size and the others follow, so the shape keeps its look"))
            lock.toggled.connect(lambda on: self.settings.setValue("ready/keep_ratio", "true" if on else "false"))
            rows.append((None, None, lock))
            self.ready_lock = lock
            last = {k: fields[k].value() for k in linked}

            def follow(name, value):
                old = last[name]
                if lock.isChecked() and old > 1e-9:
                    factor = value / old
                    for other in linked:
                        if other != name:
                            w = fields[other]
                            w.blockSignals(True)
                            w.setValue(min(w.maximum(), max(w.minimum(), last[other] * factor)))
                            w.blockSignals(False)
                    redraw()
                for other in linked:
                    last[other] = fields[other].value()
            for k in linked:
                fields[k].valueChanged.connect(lambda v, name=k: follow(name, v))
        self._ready_fields = fields
        got = widgets.form_dialog(self, title, rows, action=_("Insert"), left=preview)
        if got is None:
            return None
        return {k: got[k] for k in fields}           # the fields went with the dialog

    def set_tool(self, tool):
        self.tool_actions[tool].setChecked(True)
        self.category_buttons[self._category_of[tool]].setChecked(True)
        self.view.set_tool(tool)
        self.node_hint.setVisible(tool == "nodes")
        if tool != "measure":
            self.measure_text = ""                # the ruler's result goes with the tool
        self._show_options()

    # ---- options bar: the selected element ------------------------------------
    def _bar_separator(self, row):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setObjectName("bar_separator")
        row.addWidget(line)
        return line

    def _make_options_bar(self):
        """The selection bar (UI v2): the selected element's type and name,
        its place and size, the angle, the fields of its kind, and "Cut this
        element"; a second row for a text. With nothing selected: a hint."""
        bar = QWidget()
        bar.setObjectName("options_bar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        rows = QVBoxLayout(bar)
        rows.setContentsMargins(12, 6, 12, 6)
        rows.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(6)        # 6, not 8: the bar fits 1366 px also with wide fonts (DejaVu Sans)
        rows.addLayout(row)
        # what is selected: its type's icon and its name
        self.sel_icon = QLabel()
        self.sel_name = QLabel()
        self.sel_name.setObjectName("sel_name")
        self.sel_name.setMinimumWidth(110)
        row.addWidget(self.sel_icon)
        row.addWidget(self.sel_name)
        self.sel_hint = QLabel(_("Select an element to change its place and size"))
        self.sel_hint.setObjectName("sel_hint")
        self.sel_hint.setMinimumHeight(30)            # the bar keeps its height with nothing selected
        row.addWidget(self.sel_hint)
        self.opt_x, self.opt_y = _spin(), _spin()
        self.opt_w, self.opt_h = _spin(minimum=0.0), _spin(minimum=0.0)
        # the lock: width and height change together (also with the small squares)
        self.opt_lock = QToolButton()
        self.opt_lock.setObjectName("lock")
        self.opt_lock.setCheckable(True)
        self.opt_lock.setToolTip(_("Keep the proportions: width and height change together, "
                                   "in the fields and with the small squares round the selection"))
        self.opt_lock.setAccessibleName(_("Keep the proportions"))
        self.opt_lock.toggled.connect(self._lock_toggled)
        self.place_widgets = []
        for label, spin, tip in ((_("X"), self.opt_x, _("Bottom edge: how far up from the origin, along the material")),
                                 (_("Y"), self.opt_y, _("Right edge: how far left from the origin, across the material")),
                                 ("|", None, None),
                                 (_("W."), self.opt_w, _("Width")), (None, self.opt_lock, None),
                                 (_("H."), self.opt_h, _("Height"))):
            if label == "|":
                self.place_widgets.append(self._bar_separator(row))
                continue
            if label is not None:
                lab = QLabel(label)
                lab.setObjectName("bar_label")
                lab.setBuddy(spin)
                row.addWidget(lab)
                self.place_widgets.append(lab)
            if tip:
                spin.setToolTip(tip)
            spin.setFixedWidth(96) if spin is not self.opt_lock else None
            row.addWidget(spin)
            self.place_widgets.append(spin)
            if spin is not self.opt_lock:
                spin.valueChanged.connect(self._options_changed)
        # turn the selection by any angle (the buttons on the ribbon turn by 90°)
        self.place_widgets.append(self._bar_separator(row))
        self.angle_label = QLabel(_("Angle"))
        self.angle_label.setObjectName("bar_label")
        self.opt_angle = _spin(360.0, 1, "°", minimum=-360.0)
        self.opt_angle.setFixedWidth(80)
        self.opt_angle.setValue(float(self.settings.value("draw/rotate_by", 15.0)))
        self.opt_angle.setToolTip(_("Turn the selection by this angle: plus = counter-clockwise"))
        self.btn_rotate = QToolButton()
        self.btn_rotate.setIcon(icons.tabler("rotate-2"))
        self.btn_rotate.setToolTip(_("Turn the selection by the angle (Enter in the field does the same)"))
        self.btn_rotate.clicked.connect(lambda: self.rotate_selected(self.opt_angle.value()))
        self.opt_angle.lineEdit().returnPressed.connect(lambda: self.rotate_selected(self.opt_angle.value()))
        self.angle_label.setBuddy(self.opt_angle)
        row.addWidget(self.angle_label)
        row.addWidget(self.opt_angle)
        row.addWidget(self.btn_rotate)
        # the fields of the kind: a polygon's sides, a rectangle's corners, the node tool's keys
        self.kind_separator = self._bar_separator(row)
        self.sides_label = QLabel(_("Sides"))
        self.opt_sides = QSpinBox()
        self.opt_sides.setRange(3, 64)
        self.opt_sides.setValue(self.view.polygon_sides)
        self.opt_sides.valueChanged.connect(self._sides_changed)
        self.sides_label.setBuddy(self.opt_sides)
        row.addWidget(self.sides_label)
        row.addWidget(self.opt_sides)
        # a rectangle's round corners: for new rectangles and the selected one
        self.radius_label = QLabel(_("Corner radius"))
        self.opt_radius = _spin(1000.0, 1, minimum=0.0)
        self.opt_radius.setFixedWidth(96)
        self.opt_radius.setValue(float(self.settings.value("draw/corner_radius", 0.0)))
        self.opt_radius.setToolTip(_("Round corners of the rectangle (0 = sharp)"))
        self.opt_radius.valueChanged.connect(self._radius_changed)
        self.radius_label.setBuddy(self.opt_radius)
        row.addWidget(self.radius_label)
        row.addWidget(self.opt_radius)
        self.node_hint = QLabel(_("Drag nodes and handles · double-click a side: add a node · "
                                  "D delete · L line · C curve · O smooth · Z close/open · B break"))
        self.node_hint.setObjectName("node_hint")
        # one line of its own under the bar (wrapped beside the fields it made
        # the bar many lines high); it never makes the window wider
        self.node_hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        for w in (self.sides_label, self.opt_sides, self.node_hint, self.radius_label, self.opt_radius):
            w.setVisible(False)
        row.addStretch(1)
        self.opt_cut = Switch(_("Cut this element"))
        self.opt_cut.toggled.connect(self._options_changed)
        row.addWidget(self.opt_cut)

        # the second row: a text
        self.text_row = QWidget()
        trow = QHBoxLayout(self.text_row)
        trow.setContentsMargins(0, 0, 0, 0)
        trow.setSpacing(6)
        rows.addWidget(self.text_row)
        rows.addWidget(self.node_hint)
        self.text_defaults = dict(texts.DEFAULTS)
        self.opt_text = QLineEdit(self.text_defaults["text"])
        self.opt_text.setFixedWidth(140)
        self.opt_text.setToolTip(_("The text; Enter applies it"))
        self.opt_font = QFontComboBox()
        self.opt_font.setFixedWidth(140)
        self.opt_font.setCurrentFont(self.opt_font.currentFont().__class__(self.text_defaults["family"]))
        self.opt_size = _spin(1000.0, 1, minimum=1.0)
        self.opt_size.setFixedWidth(90)
        self.opt_size.setValue(self.text_defaults["size"])
        self.opt_size.setToolTip(_("Font size: the height of the font's em in mm"))
        self.opt_bold = QToolButton()
        self.opt_bold.setObjectName("toggle")
        self.opt_bold.setIcon(icons.tabler("bold"))
        self.opt_bold.setCheckable(True)
        self.opt_bold.setChecked(self.text_defaults["bold"])
        self.opt_bold.setToolTip(_("Bold"))
        self.opt_italic = QToolButton()
        self.opt_italic.setObjectName("toggle")
        self.opt_italic.setIcon(icons.tabler("italic"))
        self.opt_italic.setCheckable(True)
        self.opt_italic.setToolTip(_("Italic"))
        self.opt_spacing = _spin(100.0, 2, minimum=-20.0)
        self.opt_spacing.setFixedWidth(90)
        self.opt_spacing.setToolTip(_("Extra space between letters, mm"))
        self.text_widgets = [self.opt_text, self.opt_font, self.opt_size, self.opt_bold, self.opt_italic,
                             self.opt_spacing]
        self.text_labels = []
        for label, w in ((_("Content"), self.opt_text), (_("Font"), self.opt_font), (_("Size"), self.opt_size),
                         (None, self.opt_bold), (None, self.opt_italic), (_("Spacing"), self.opt_spacing)):
            if label:
                lab = QLabel(label)
                lab.setObjectName("bar_label")
                lab.setBuddy(w)
                trow.addWidget(lab)
                self.text_labels.append(lab)
            trow.addWidget(w)
        self._bar_separator(trow)
        self.btn_text_path = QToolButton()
        self.btn_text_path.setDefaultAction(self.act_text_path)
        self.btn_text_path.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_text_path.setObjectName("bar_button")
        trow.addWidget(self.btn_text_path)
        # a text on a path: where along the path, how far from it, which side
        self.opt_path_offset = _spin(100000.0, 1, minimum=-100000.0)
        self.opt_path_offset.setFixedWidth(88)
        self.opt_path_offset.setToolTip(_("Where the text starts along its path, mm"))
        self.opt_path_distance = _spin(1000.0, 1, minimum=-1000.0)
        self.opt_path_distance.setFixedWidth(84)
        self.opt_path_distance.setToolTip(_("How far the letters stand from the path, mm"))
        self.opt_path_flip = Switch(_("other side"))
        self.opt_path_flip.setToolTip(_("The text on the other side of the path (inside a circle), still readable"))
        self.path_widgets, self.path_labels = [self.opt_path_offset, self.opt_path_distance, self.opt_path_flip], []
        for label, w in ((_("Along"), self.opt_path_offset), (_("Away"), self.opt_path_distance),
                         (None, self.opt_path_flip)):
            if label:
                lab = QLabel(label)
                lab.setObjectName("bar_label")
                lab.setBuddy(w)
                trow.addWidget(lab)
                self.path_labels.append(lab)
            trow.addWidget(w)
        trow.addStretch(1)
        for w in self.path_widgets + self.path_labels:
            w.setVisible(False)
        for w in (self.opt_path_offset, self.opt_path_distance):
            w.valueChanged.connect(lambda _v: self._text_changed())
        self.opt_path_flip.toggled.connect(lambda _v: self._text_changed())
        self.opt_text.editingFinished.connect(self._text_changed)
        self.opt_font.currentFontChanged.connect(lambda _f: self._text_changed())
        for w in (self.opt_size, self.opt_spacing):
            w.valueChanged.connect(lambda _v: self._text_changed())
        for w in (self.opt_bold, self.opt_italic):
            w.toggled.connect(lambda _v: self._text_changed())
        for w in self.text_widgets + self.text_labels:
            w.setVisible(False)
        self.text_row.setVisible(False)
        self.options_widgets = (self.opt_x, self.opt_y, self.opt_w, self.opt_h, self.opt_cut)
        locked = str(self.settings.value("view/keep_ratio", "true")).lower() == "true"
        self.opt_lock.setChecked(locked)
        self._lock_toggled(locked)
        self.options_bar = bar
        return bar

    # the icon of an element's type (the selection bar and the element list)
    KIND_ICONS = {"text": "typography", "rectangle": "square", "polygon": "polygon", "ready": "star",
                  "ellipse": "circle", "weeding": "slash", "pattern": "rosette", "line": "line"}

    def kind_icon(self, e):
        kind = (e.spec or {}).get("kind") if e is not None else None
        if kind in self.KIND_ICONS:
            return icons.tabler(self.KIND_ICONS[kind])
        if e is not None and e.fill:
            return icons.tabler("bucket-droplet")
        if e is not None and not any(sub["closed"] for sub in e.paths):
            return icons.tabler("vector-spline")
        return icons.tabler("vector-bezier-2")

    def _show_options(self):
        self._updating = True
        e = self.selected
        has = e is not None
        for w in self.options_widgets:
            w.setEnabled(has)
        n_sel = len(self.selection) if self.selection else (1 if has else 0)
        self.selected_label.setText("" if not has else _("Selected: %s") % (
            e.name if n_sel <= 1 else ngettext("%d element", "%d elements", n_sel) % n_sel))
        # nothing selected: a hint instead of greyed-out fields (see _set_visible)
        fields = self.place_widgets + [self.angle_label, self.opt_angle, self.btn_rotate, self.opt_cut,
                                       self.sel_icon, self.sel_name]
        self._set_visible([(self.sel_hint, not has)] + [(w, has) for w in fields])
        # the ruler, with nothing selected: its result in the bar (UI v2, 6.3)
        ruler = not has and getattr(self.view, "tool", None) == "measure"
        self.sel_icon.setVisible(has or ruler)
        self.sel_name.setVisible(has or ruler)
        if ruler:
            self.sel_icon.setPixmap(icons.tabler("ruler-measure").pixmap(18, 18))
            self.sel_name.setText(_("Ruler"))
            self.sel_hint.setText(getattr(self, "measure_text", "") or _("Drag between two points to measure"))
        else:
            self.sel_hint.setText(_("Select an element to change its place and size"))
        if has:
            n = len(self.selection) if self.selection else 1
            self.sel_icon.setPixmap(self.kind_icon(e).pixmap(18, 18))
            self.sel_name.setText(e.name if n <= 1 else ngettext("%d element", "%d elements", n) % n)
            xmin, xmax, ymin, ymax = e.bounds
            self.opt_x.setValue(-ymax)            # bottom edge: along the material from the origin
            self.opt_y.setValue(-xmax)            # right edge: across the material from the origin
            self.opt_w.setValue(xmax - xmin)
            self.opt_h.setValue(ymax - ymin)
            self.opt_cut.setChecked(e.cut)
        self._updating = False
        self._show_text_options()
        self._show_polygon_options()
        kind = self.sides_label.isVisibleTo(self.options_bar) or self.radius_label.isVisibleTo(self.options_bar)
        self.kind_separator.setVisible(kind)

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
            self._after_resize(e)
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
            self._after_resize(e)        # stretched: a shape now (a rectangle keeps round corners)
        _xmin, xmax, _ymin, ymax = e.bounds
        e.move_by(-self.opt_y.value() - xmax, -self.opt_x.value() - ymax)
        e.cut = self.opt_cut.isChecked()
        self.refresh()

    # ---- left panel: project, cutter, job --------------------------------------
    def _section(self, col, title, stretch=0):
        """A section of the left panel: a title, then its rows (UI v2: one white
        column, the sections divided by a line, no frames)."""
        line = None
        if col.count():
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setObjectName("panel_line")
            col.addWidget(line)
        box = QWidget()
        box.line = line                     # hidden with its section (Colours, one colour)
        box.setObjectName("panel_section")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(6)
        label = QLabel(title)
        label.setObjectName("section_title")
        head.addWidget(label)
        head.addStretch(1)
        lay.addLayout(head)
        col.addWidget(box, stretch)
        # only the element list gives way on a low window; the other sections
        # keep the height of what they show
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding if stretch else QSizePolicy.Fixed)
        box.head = head
        return box, lay

    def _make_left_panel(self):
        """The left panel (UI v2): Elements, Cutter, Job."""
        from vintyl.gui.widgets import ElementRowDelegate, Segmented
        panel = QWidget()
        panel.setObjectName("job_panel")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        panel.setFixedWidth(330)
        col = QVBoxLayout(panel)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        # ---- Elements: the cutting order, each row with its number, type, name, scissors
        box, lay = self._section(col, _("Elements"), 1)
        self.elements_box = box
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        # one line, not wrapped: a wrapped label makes Qt treat the whole box as
        # rigid (height for width) and the column then squeezed the others
        self.summary.setWordWrap(False)
        box.head.addWidget(self.summary)
        self.btn_up = QToolButton()
        self.btn_up.setIcon(icons.tabler("arrow-up"))
        self.btn_up.setToolTip(_("Cut earlier"))
        self.btn_up.setAccessibleName(_("Move up"))
        self.btn_down = QToolButton()
        self.btn_down.setIcon(icons.tabler("arrow-down"))
        self.btn_down.setToolTip(_("Cut later"))
        self.btn_down.setAccessibleName(_("Move down"))
        for b in (self.btn_up, self.btn_down):
            b.setAutoRaise(True)
            box.head.addWidget(b)
        self.btn_up.clicked.connect(lambda: self.move_selected(-1))
        self.btn_down.clicked.connect(lambda: self.move_selected(1))
        self.element_list = QListWidget()
        self.element_list.setObjectName("element_list")
        self.element_list.setItemDelegate(ElementRowDelegate(self.element_list))
        self.element_list.setFrameShape(QFrame.NoFrame)
        self.element_list.setMinimumHeight(90)
        self.element_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.element_list.itemChanged.connect(self._list_item_changed)
        self.element_list.currentRowChanged.connect(self._list_row_changed)
        # the right button: the same menu as on the sheet (duplicate, delete...)
        self.element_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.element_list.customContextMenuRequested.connect(lambda pos: self.list_context_menu(pos))
        lay.addWidget(self.element_list, 1)
        self.empty_hint = QLabel(_("Open an SVG or DXF file, or draw a shape with the tools on the right."))
        self.empty_hint.setObjectName("hint")
        self.empty_hint.setWordWrap(True)
        lay.addWidget(self.empty_hint)

        # ---- Colours: the colour layers, drawn (cut) one after another (only
        # shown for a design of several colours)
        box, lay = self._section(col, _("Colours"))
        self.colours_box = box
        self.layer_summary = QLabel()
        self.layer_summary.setObjectName("muted")
        box.head.addWidget(self.layer_summary)
        self.btn_layer_up = QToolButton()
        self.btn_layer_up.setIcon(icons.tabler("arrow-up"))
        self.btn_layer_up.setToolTip(_("Draw this colour earlier"))
        self.btn_layer_up.clicked.connect(lambda: self.move_layer(-1))
        self.btn_layer_down = QToolButton()
        self.btn_layer_down.setIcon(icons.tabler("arrow-down"))
        self.btn_layer_down.setToolTip(_("Draw this colour later"))
        self.btn_layer_down.clicked.connect(lambda: self.move_layer(1))
        self.btn_layer_edit = QToolButton()
        self.btn_layer_edit.setIcon(icons.tabler("settings"))
        self.btn_layer_edit.setToolTip(_("This colour's name, colour and pen"))
        self.btn_layer_edit.clicked.connect(lambda: self.edit_layer())
        for b in (self.btn_layer_up, self.btn_layer_down, self.btn_layer_edit):
            box.head.addWidget(b)
        self.layer_list = QListWidget()
        self.layer_list.setObjectName("layer_list")
        self.layer_list.setFrameShape(QFrame.NoFrame)
        self.layer_list.setIconSize(QSize(16, 16))
        self.layer_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.layer_list.setToolTip(_("The colours, drawn (cut) one after another in this order; untick one "
                                     "to leave it out. A click selects its elements."))
        self.layer_list.itemChanged.connect(self._layer_item_changed)
        self.layer_list.itemClicked.connect(self._layer_clicked)
        self.layer_list.itemDoubleClicked.connect(lambda _i: self.edit_layer())
        lay.addWidget(self.layer_list)
        box.setVisible(False)
        box.line.setVisible(False)

        # ---- Cutter: the machine, its state, the tool
        box, lay = self._section(col, _("Cutter"))
        self.cutter_box = box
        self.profile_box = QComboBox()
        self.profile_box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.profile_box.setMinimumContentsLength(10)
        self.profile_box.currentIndexChanged.connect(self._profile_changed)
        self.btn_profile = QToolButton()
        self.btn_profile.setObjectName("square")
        self.btn_profile.setDefaultAction(self.act_profile)
        self.btn_profile.setToolButtonStyle(Qt.ToolButtonIconOnly)
        machine = QHBoxLayout()
        machine.setSpacing(8)
        machine.addWidget(self.profile_box, 1)
        machine.addWidget(self.btn_profile)
        lay.addLayout(machine)
        # one line of state with a dot: green ready, grey not plugged in
        self.cutter_info = QLabel()
        self.cutter_info.setObjectName("cutter_state")
        self.cutter_info.setWordWrap(True)
        self.cutter_info.setTextFormat(Qt.RichText)
        lay.addWidget(self.cutter_info)
        # a problem with the port: a yellow frame with what to do and a link to the help
        self.port_warning = QFrame()
        self.port_warning.setObjectName("warn")
        wl = QHBoxLayout(self.port_warning)
        wl.setContentsMargins(10, 8, 10, 8)
        wl.setSpacing(8)
        warn_icon = QLabel()
        warn_icon.setPixmap(icons.tabler("alert-triangle", theme.token("warn_ink")).pixmap(18, 18))
        wl.addWidget(warn_icon, 0, Qt.AlignTop)
        self.port_problem = QLabel()
        self.port_problem.setWordWrap(True)
        self.port_problem.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.port_problem.linkActivated.connect(lambda _l: self.show_access_help())
        wl.addWidget(self.port_problem, 1)
        self.port_warning.setVisible(False)
        lay.addWidget(self.port_warning)
        # what is in the holder: the knife cuts, a pen (or a pencil) draws
        self.tool_box = Segmented(icon_size=22)
        self.tool_box.setObjectName("segmented")
        self.tool_box.addItem(_("Knife"), "knife", icons.own("drag-knife"))
        self.tool_box.addItem(_("Marker pen"), "pen", icons.tabler("pencil"))
        self.tool_box.setToolTip(_("What is in the cutter's holder. Pen: drawing on paper or card, "
                                   "with no knife offset or overcut; fill patterns are drawn too."))
        for k in range(self.tool_box.count()):
            self.tool_box.button(k).setMinimumHeight(40)
        self.tool_box.currentIndexChanged.connect(lambda _i: self._tool_changed())
        lay.addWidget(self.tool_box)
        # the material: choosing it sets the tool, the job's switches and the pen's values;
        # its force and speed for this cutter are shown under it
        self.material_box = QComboBox()
        self.material_box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.material_box.setMinimumContentsLength(10)
        self.material_box.currentIndexChanged.connect(self._material_changed)
        self.btn_material = QToolButton()
        self.btn_material.setObjectName("square")
        self.btn_material.setIcon(icons.tabler("settings-2"))
        self.btn_material.setToolTip(_("Materials: force, speed, knife and pen values"))
        self.btn_material.clicked.connect(lambda: self.edit_material())
        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        mlabel = QLabel(_("Material"))
        mlabel.setObjectName("field_label")
        mrow.addWidget(mlabel)
        mrow.addWidget(self.material_box, 1)
        mrow.addWidget(self.btn_material)
        lay.addLayout(mrow)
        self.material_hint = QLabel()
        self.material_hint.setObjectName("muted")
        self.material_hint.setWordWrap(True)
        lay.addWidget(self.material_hint)
        self.pen_note = QLabel(_("For drawing on paper or card, not for vinyl. To cut vinyl, choose the knife."))
        self.pen_note.setObjectName("muted")
        self.pen_note.setWordWrap(True)
        lay.addWidget(self.pen_note)
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
        self.pen_width.valueChanged.connect(lambda _v: self._tool_changed())
        self.pen_place.currentIndexChanged.connect(lambda _v: self._tool_changed())
        # the pen's two fields side by side, their labels above them
        self.pen_fields = QWidget()
        pg = QGridLayout(self.pen_fields)
        pg.setContentsMargins(0, 0, 0, 0)
        pg.setHorizontalSpacing(10)
        pg.setVerticalSpacing(4)
        for c, (label, w) in enumerate(((_("Pen width"), self.pen_width), (_("Draw"), self.pen_place))):
            lab = QLabel(label)
            lab.setObjectName("field_label")
            lab.setBuddy(w)
            pg.addWidget(lab, 0, c)
            pg.addWidget(w, 1, c)
        lay.addWidget(self.pen_fields)

        # ---- Job: two tiles of numbers, the switches, Start
        box, lay = self._section(col, _("Job"))
        self.job_box = box
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.stat_cut, self.stat_cut_title = self._stat_tile(tiles, _("Cut length"))
        self.stat_travel, _t = self._stat_tile(tiles, _("Travel"))
        lay.addLayout(tiles)
        self.job_label = QLabel()
        self.job_label.setObjectName("muted")
        self.job_label.setWordWrap(True)
        lay.addWidget(self.job_label)
        self.inside_first = Switch(_("Inside shapes first"))
        self.inside_first.setChecked(True)
        self.inside_first.setToolTip(_("Holes and shapes inside others are cut before them, so a piece "
                                       "is never cut free while its holes are still to be cut. "
                                       "Off: exactly the order of the list."))
        self.inside_first.toggled.connect(lambda _v: self.refresh_job())
        lay.addWidget(self.inside_first)
        self.mirror_job = Switch(_("Mirror (heat transfer vinyl)"))
        self.mirror_job.setToolTip(_("For vinyl ironed onto fabric: it is cut from the back, so the cut is "
                                     "mirrored. The design on the screen stays as it will look on the shirt."))
        self.mirror_job.toggled.connect(lambda _v: self.refresh_job())
        lay.addWidget(self.mirror_job)
        # a frame round the whole design, cut last, for weeding: its margin before the switch
        frame_row = QHBoxLayout()
        frame_row.setContentsMargins(0, 0, 0, 0)
        frame_row.setSpacing(10)
        self.weed_frame = Switch(_("Frame round the design"))
        self.weed_frame.setToolTip(_("A rectangle round everything that is cut, cut last: "
                                     "the waste vinyl inside it peels off in one piece"))
        self.weed_margin = _spin(100.0, 1, minimum=0.5)
        self.weed_margin.setValue(5.0)
        self.weed_margin.setFixedWidth(84)
        self.weed_margin.setToolTip(_("Space between the design and the frame"))
        self.weed_frame.toggled.connect(lambda _v: self.refresh_job())
        self.weed_margin.valueChanged.connect(lambda _v: self.refresh_job())
        frame_label = QLabel(_("Frame round the design"))
        frame_label.setBuddy(self.weed_frame)
        frame_label.mousePressEvent = lambda _e: self.weed_frame.toggle()
        self.weed_frame.setText("")                     # its label is beside the margin field
        self.weed_frame.setAccessibleName(_("Frame round the design"))
        frame_row.addWidget(frame_label, 1)
        frame_row.addWidget(self.weed_margin)
        frame_row.addWidget(self.weed_frame)
        self.frame_row = QWidget()
        self.frame_row.setLayout(frame_row)
        lay.addWidget(self.frame_row)
        # sending: what is sent, how much of it; Stop in the place of Start.
        # Pinned under the scrolling panel (the owner, 17.11.2026): Start, Save
        # and the knife test are always in sight, also on a low screen
        self.send_footer = QWidget()
        self.send_footer.setObjectName("send_footer")
        self.send_footer.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self.send_footer)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(10)
        self.send_label = QLabel()
        self.send_label.setObjectName("field_label")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        for w in (self.send_label, self.progress):
            w.setVisible(False)
            lay.addWidget(w)
        self.btn_start = QPushButton(icons.tabler("player-play", "#ffffff"), _("Start"))
        self.btn_start.setObjectName("start")
        self.btn_start.setToolTip(_("Cut the design (after a short check list)"))
        self.btn_start.clicked.connect(self.start)
        self.btn_stop = QPushButton(icons.tabler("player-stop", "#ffffff"), _("Stop"))
        self.btn_stop.setObjectName("stop")
        self.btn_stop.setToolTip(_("Stop sending and lift the knife. What the cutter already has "
                                   "is stopped with Test or Reset on its panel."))
        self.btn_stop.setEnabled(False)
        self.btn_stop.setVisible(False)
        self.btn_stop.clicked.connect(self.stop)
        for b in (self.btn_start, self.btn_stop):
            b.setMinimumHeight(48)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            lay.addWidget(b)
        self.btn_save = QPushButton(icons.tabler("file-export"), _("Save .hpgl"))
        self.btn_save.clicked.connect(lambda: self.save_cutter_file())
        self.btn_test = QPushButton(icons.own("drag-knife"), _("Knife test"))
        self.btn_test.setToolTip(_("Cut a small square with a triangle to check the knife's force"))
        self.btn_test.clicked.connect(lambda: self.knife_test())
        small = QHBoxLayout()
        small.setSpacing(10)
        for b in (self.btn_save, self.btn_test):
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            small.addWidget(b)
        lay.addLayout(small)
        return panel

    def _stat_tile(self, row, title):
        """A tile with a number (the job's lengths): a small title, a big value."""
        tile = QFrame()
        tile.setObjectName("stat")
        v = QVBoxLayout(tile)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(0)
        head = QLabel(title)
        head.setObjectName("stat_title")
        value = QLabel("–")
        value.setObjectName("stat_value")
        v.addWidget(head)
        v.addWidget(value)
        row.addWidget(tile, 1)
        return value, head

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
        self._select_material(self.settings.value("cutter/material/" + pid, ""), apply=False)
        self.refresh()

    def is_pen(self):
        return self.tool_box.currentData() == "pen"

    def _tool_changed(self, refresh=True):
        """Knife or pen: show the settings that matter for it, hide the others,
        and remember the choice for this cutter."""
        pen = self.is_pen()
        self.inside_first.setVisible(not pen)
        self.pen_fields.setVisible(pen)
        self.pen_note.setVisible(pen)
        self.frame_row.setVisible(not pen)
        # the fill is for drawing: with the knife it is not offered (it would cut the vinyl into strips)
        self.act_fill.setVisible(pen)
        self._mark_sets()
        self.view.pen_mode = pen
        self.act_knife.setText(_("Pen path") if pen else _("Knife path"))
        self.act_knife.setIconText(pgettext("ribbon", "Pen path") if pen else pgettext("ribbon", "Knife path"))
        name = self.profile_box.currentData()
        if name and not getattr(self, "_loading_tool", False):
            self.settings.setValue("cutter/tool/" + name, self.tool_box.currentData())
            self.settings.setValue("cutter/pen_width/" + name, self.pen_width.value())
            self.settings.setValue("cutter/pen_place/" + name, self.pen_place.currentData())
        if refresh and not getattr(self, "_loading_tool", False):
            self.refresh()

    def job_profile(self, material=None):
        """The chosen machine's profile with the material's values: its knife
        offset and overcut before the cutter's own, its force and speed for
        this cutter (sent only to a cutter that takes them from the computer;
        the speed also gives the time estimate). With the pen: no knife offset
        and no overcut (no blade trails behind, nothing to close)."""
        p = self.profile
        m = material if material is not None else self.material()
        if m is not None:
            changes = {}
            if m.knife_offset_mm is not None:
                changes["knife_offset_mm"] = m.knife_offset_mm
            if m.overcut_mm is not None:
                changes["overcut_mm"] = m.overcut_mm
            force, speed = m.for_cutter(self.profile_box.currentData())
            if force is not None:
                changes["force_g"] = force
            if speed is not None:
                changes["speed_cm_s"] = speed
            if changes:
                p = dataclasses.replace(p, **changes)
        if self.is_pen():
            return dataclasses.replace(p, knife_offset_mm=0.0, overcut_mm=0.0)
        return p

    # ---- materials --------------------------------------------------------------------------
    def reload_materials(self, select=None):
        """Fill the material list; choose `select` (an id), else the one chosen now."""
        from vintyl.core import material as mats
        from vintyl.gui.material_editor import display_name
        entries = [e for e in mats.catalogue() if e["material"] is not None]
        self.material_entries = {e["id"]: e for e in entries}
        want = select if select in self.material_entries else self.material_box.currentData()
        self.material_box.blockSignals(True)
        self.material_box.clear()
        for e in entries:
            icon = icons.own("drag-knife") if e["material"].tool == "knife" else icons.tabler("pencil")
            self.material_box.addItem(icon, display_name(e), e["id"])
        self.material_box.setCurrentIndex(max(0, self.material_box.findData(want)))
        self.material_box.blockSignals(False)
        self._show_material_hint()

    def material(self):
        """The chosen material (or None when there is none)."""
        e = self.material_entries.get(self.material_box.currentData())
        return e["material"] if e else None

    def _select_material(self, mid, apply=True):
        index = self.material_box.findData(mid)
        if index < 0:
            self._show_material_hint()
            return
        self.material_box.blockSignals(not apply)
        self.material_box.setCurrentIndex(index)
        self.material_box.blockSignals(False)
        self._show_material_hint()

    def _material_changed(self, _index):
        """A material chosen: it sets the tool, the mirror, the weeding frame and
        the pen's values (changed by hand afterwards if wanted), and is
        remembered for this cutter."""
        m = self.material()
        pid = self.profile_box.currentData()
        if m is not None:
            self._loading_tool = True
            self.tool_box.setCurrentIndex(self.tool_box.findData(m.tool))
            if m.pen_width_mm is not None:
                self.pen_width.setValue(m.pen_width_mm)
            self.pen_place.setCurrentIndex(max(0, self.pen_place.findData(m.pen_place)))
            self._loading_tool = False
            self._tool_changed(refresh=False)
            for box, on in ((self.mirror_job, m.mirror), (self.weed_frame, m.weed_frame)):
                box.blockSignals(True)
                box.setChecked(on)
                box.blockSignals(False)
            if pid:
                self.settings.setValue("cutter/material/" + pid, self.material_box.currentData())
        self._show_material_hint()
        self.refresh_job()

    def material_values(self, material=None):
        """(title, force text, speed text) of the material for this cutter, for
        the windows before Start (a text None when not set; speeds in mm/s);
        None without a material."""
        m = material if material is not None else self.material()
        if m is None:
            return None
        force, speed = m.for_cutter(self.profile_box.currentData())
        # also with neither: the window then says where to write them
        title = _("Vintyl sends to the cutter") if self.profile.send_speed_force else _("Set on the cutter's panel")
        return (title, "%g g" % force if force is not None else None,
                "%g mm/s" % round(speed * 10.0, 1) if speed is not None else None)

    def cut_details(self, material=None, pen=None):
        """The rest the job uses, for the windows before sending, as lines
        [(heading, [(label, value)])] that say who does what: the blade to put
        in the holder (the material's); the knife offset and overcut that
        Vintyl works into the knife's path (nothing of them is sent as a
        setting); the pen's width and where its stroke lies. Only force and
        speed are set on the cutter's panel."""
        from vintyl import i18n
        from vintyl.gui.material_editor import BLADE_NAMES

        def mm(v):                                   # as the window writes numbers (1,5 in Polish)
            return i18n.decimal("%g mm" % round(v, 2))
        pen = self.is_pen() if pen is None else pen
        if pen:
            return [(_("Worked into the pen's path by Vintyl"),
                     [(_("Pen width"), mm(self.pen_width.value())), (_("Draw"), self.pen_place.currentText())])]
        m = material if material is not None else self.material()
        p = self.job_profile(material)
        out = []
        if m is not None and m.blade:
            out.append((_("In the holder"), [(_("Blade"), _(BLADE_NAMES[m.blade]))]))
        out.append((_("Worked into the knife's path by Vintyl"),
                    [(_("Knife offset"), mm(p.knife_offset_mm)), (_("Overcut"), mm(p.overcut_mm))]))
        return out

    def _material_is_builtin(self):
        e = self.material_entries.get(self.material_box.currentData())
        return bool(e and e["builtin"])

    def _material_name(self):
        from vintyl.gui.material_editor import display_name
        e = self.material_entries.get(self.material_box.currentData())
        return display_name(e) if e else ""

    def material_values_text(self, material=None):
        """("Set on the cutter's panel" / "Vintyl sends", "force 90 g · speed 300 mm/s"),
        or None when the material has no force or speed for this cutter."""
        m = material if material is not None else self.material()
        if m is None:
            return None
        force, speed = m.for_cutter(self.profile_box.currentData())
        parts = []
        if force is not None:
            parts.append(_("force %g g") % force)
        if speed is not None:
            parts.append(_("speed %g mm/s") % round(speed * 10.0, 1))         # kept in cm/s
        if not parts:
            return None
        title = _("Vintyl sends to the cutter") if self.profile.send_speed_force else _("Set on the cutter's panel")
        return title, " · ".join(parts)

    def _show_material_hint(self):
        if not hasattr(self, "material_hint"):
            return
        values = self.material_values_text() if hasattr(self, "profile_box") else None
        self.material_hint.setText("%s: %s" % values if values else "")
        self.material_hint.setVisible(bool(values))

    def edit_material(self):
        """The materials window; saved: use what it says; "Knife test with these
        values": cut the knife test with them."""
        from vintyl.gui.material_editor import MaterialEditor
        dlg = MaterialEditor(self, self.material_box.currentData(), self.profile_box.currentData())
        dlg.exec()
        if dlg.chosen is not None:
            self.reload_materials(dlg.chosen)
            self._material_changed(self.material_box.currentIndex())
        if dlg.test_material is not None:
            return self.knife_test(material=dlg.test_material)
        return dlg

    def build(self):
        """The job as it would go to the cutter now (raises JobError / ProfileError)."""
        polys, groups = self.design.material_paths()
        if self.is_pen():
            # the outlines placed against the pen's stroke, each element's fill before its outline,
            # in the list's order (nothing comes loose on paper)
            polys, groups = pens.place(polys, groups, self.pen_width.value(), self.pen_place.currentData())
            fills, fill_groups = self.design.material_fills()
            polys, groups = pens.merge(fills, fill_groups, polys, groups)
            return build_job(self._mirrored(polys), self.job_profile(), groups, False)
        frame = self.weed_frame_polyline(self._frame_polys(polys, groups))
        if frame:
            polys = polys + [frame]                      # in its own last group: cut last
            groups = groups + [max(groups) + 1]
        return build_job(self._mirrored(polys), self.job_profile(), groups, self.inside_first.isChecked())

    def _mirrored(self, polys):
        """Heat transfer vinyl is cut from the back: the job is mirrored left to
        right (across the material) within its own box, so it stays in place.
        The design on the screen stays as it will look on the shirt."""
        if not self.mirror_job.isChecked() or not polys:
            return polys
        across = [a for poly in polys for _x, a in poly]
        lo, hi = min(across), max(across)
        return [[(x, lo + hi - a) for x, a in poly] for poly in polys]

    def _frame_polys(self, polys, groups):
        """What the weeding frame goes round: the shapes, not the weeding lines
        (they end at the frame)."""
        weeding = {k for k, e in enumerate(self.design.elements) if e.spec and e.spec.get("kind") == "weeding"}
        return [p for p, g in zip(polys, groups) if g not in weeding]

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
                "mirror": self.mirror_job.isChecked(),
                "tool": self.tool_box.currentData(), "pen_width_mm": self.pen_width.value(),
                "material": self.material_box.currentData(),
                "pen_place": self.pen_place.currentData()}

    def _apply_project_settings(self, st):
        # the machine (its knife and port are its own settings, not the project's)
        if st.get("profile") in self.profile_names:
            self.profile_box.setCurrentIndex(self.profile_names.index(st["profile"]))
        # the material of the project (older projects have none: the current one stays)
        if st.get("material") in getattr(self, "material_entries", {}):
            self._select_material(st["material"], apply=False)
        if st.get("tool") in ("knife", "pen"):
            self.tool_box.setCurrentIndex(self.tool_box.findData(st["tool"]))
        if st.get("pen_place") in pens.PLACES:
            self.pen_place.setCurrentIndex(self.pen_place.findData(st["pen_place"]))
        for key, widget in (("weed_margin_mm", self.weed_margin), ("pen_width_mm", self.pen_width)):
            if isinstance(st.get(key), (int, float)):
                widget.setValue(float(st[key]))
        for key, box in (("inside_first", self.inside_first), ("weed_frame", self.weed_frame),
                         ("mirror", self.mirror_job)):
            if isinstance(st.get(key), bool):
                box.setChecked(st[key])

    def open_file(self, path=None):
        """Open a project (.vintyl) or add an SVG or DXF file's shapes."""
        if path is None:
            path, _f = QFileDialog.getOpenFileName(
                self, _("Open"), os.path.dirname(self.project_path or ""),
                _("Vintyl projects and drawings (*.vintyl *.svg *.dxf);;Vintyl projects (*.vintyl);;"
                  "SVG files (*.svg);;DXF files (*.dxf)"))
            if not path:
                return None
        if path.lower().endswith(project.EXTENSION):
            return self.open_project(path)
        if path.lower().endswith(".dxf"):
            return self.import_dxf(path)
        return self.import_svg(path)

    def import_dxf(self, path, units=None):
        """Add a DXF drawing's shapes. units: for a drawing that does not say
        them (None asks; "Millimeters", "Inches", ...)."""
        from vintyl.core.loaders import DXF_UNITS, LoadCancelled, load_dxf

        def ask():
            if units is not None:
                return units
            names = {"Millimeters": _("millimetres"), "Centimeters": _("centimetres"), "Inches": _("inches"),
                     "Meters": _("metres"), "Feet": _("feet"), "Mils": _("mils (1/1000 inch)")}
            units_box = QComboBox()
            for code in DXF_UNITS:
                if code in names:
                    units_box.addItem(names[code], code)
            note = QLabel(_("%s does not say its units. They are:") % os.path.basename(path))
            note.setWordWrap(True)
            got = widgets.form_dialog(self, _("Open DXF"), [(None, None, note), ("units", _("Units"), units_box)],
                                      action=_("Open"))
            return got["units"] if got else None
        try:
            e = load_dxf(path, ask)
        except LoadCancelled:
            return None
        except LoadError as err:
            widgets.warn(self, _("Open DXF"), str(err))
            return None
        w, h = e.size
        e.move_to(-PLACE_MARGIN_MM - w, -PLACE_MARGIN_MM - h)
        self.add_element(e)
        note = _("Opened %s") % os.path.basename(path)
        if getattr(e, "dxf_messages", ""):
            note += " · " + _("some entities were left out: %s") % e.dxf_messages.splitlines()[0]
        self.statusBar().showMessage(note, 8000)
        return e

    def open_project(self, path):
        if not self.maybe_save():
            return None
        try:
            design, st = project.load(path)
        except project.ProjectError as err:
            widgets.warn(self, _("Open"), str(err))
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
            widgets.warn(self, _("Save project"), _("Cannot save %s: %s") % (path, err.strerror or err))
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
        answer = widgets.ask(self, _("Unsaved changes"), _("Save the changes to the project first?"),
                             [("discard", _("Don't save"), "left"), ("cancel", _("Cancel"), "cancel"),
                              ("save", _("Save"), "main")])
        if answer is None:
            return False
        if answer == "save":
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
            groups = load_svg_colors(path)
        except LoadError as err:
            widgets.warn(self, _("Open SVG"), str(err))
            return None
        self._checkpoint()
        elements = self._colour_elements(path, groups)
        # place them on the material, together, PLACE_MARGIN_MM from the origin (lower right) both ways
        boxes = [e.bounds for e in elements]
        x0, x1 = min(b[0] for b in boxes), max(b[1] for b in boxes)
        y0, y1 = min(b[2] for b in boxes), max(b[3] for b in boxes)
        for e in elements:
            e.move_by(-PLACE_MARGIN_MM - x1, -PLACE_MARGIN_MM - y1)
        self.design.elements.extend(elements)
        self.selected, self.selection = elements[0], list(elements)
        self.refresh()
        self.statusBar().showMessage(_("Opened %s") % os.path.basename(path), 5000)
        return elements[0]

    # default fill of a shape that is filled with a colour in the file (drawn by a pen)
    IMPORT_FILL = {"pattern": "lines", "spacing": 1.0, "angle": 45.0, "margin": 0.0}

    def _colour_elements(self, path, groups):
        """The elements of an SVG read by colour (vintyl.core.loaders.
        load_svg_colors), in the colour layers, similar colours merged;
        grouped, so they move as one. A drawing of several colours (for
        pens): one element per colour and kind, its filled shapes with a
        fill pattern; a drawing of one colour (a sticker): one element, no
        fill. A design with only its empty first layer gets the file's
        colours instead of it."""
        import uuid
        from vintyl.core import layers as lay
        design = self.design
        first = design.layers[0]
        if len(design.layers) == 1 and not design.elements_of(first) and first.id == lay.DEFAULT_ID:
            design.layers = []                 # the empty black layer of a new design: the file's colours instead
        counts = {}
        for (color, _filled), subpaths in groups.items():
            counts[color] = counts.get(color, 0) + len(subpaths)
        to_layer = lay.assign(counts, design.layers, merge=True, name=lambda c: _(lay.color_name(c)))
        name = os.path.splitext(os.path.basename(path))[0]
        group = uuid.uuid4().hex[:8] if len(groups) > 1 else ""
        several = len({layer.id for layer in to_layer.values()}) > 1
        merged = {}
        for (color, filled), subpaths in groups.items():     # the merged colours: one element per layer (and kind)
            merged.setdefault((to_layer[color].id, filled and several), []).extend(subpaths)
        out = []
        for layer in design.layers:
            for filled in (True, False):
                subpaths = merged.get((layer.id, filled))
                if not subpaths:
                    continue
                e = Element(name if len(merged) == 1 else "%s – %s" % (name, layer.name), subpaths, source=path,
                            group=group, layer=layer.id)
                if filled:
                    e.fill = dict(self.IMPORT_FILL)        # drawn with a pen; a knife cuts the outline only
                    if layer.fill is None:
                        layer.fill = dict(self.IMPORT_FILL)
                out.append(e)
        return out

    def _on_drawn(self, tool, rect):
        make = {"rectangle": (lambda *r: shapes.rounded_rectangle(*r, self.opt_radius.value()), _("Rectangle")),
                "ellipse": (shapes.ellipse, _("Ellipse")),
                "polygon": (lambda *r: shapes.polygon(*r, sides=self.opt_sides.value()), _("Polygon"))}[tool]
        paths = make[0](rect.left(), rect.top(), rect.right(), rect.bottom())
        e = Element(self._name(make[1]), paths)
        if tool == "ellipse":
            e.spec = {"kind": "ellipse"}             # for its icon in the list and the selection bar
        if tool == "polygon":
            # remember how it was drawn, so its number of sides can be changed later:
            # the rectangle it was drawn in, relative to the polygon's own box
            b = e.bounds
            e.spec = {"kind": "polygon", "sides": self.opt_sides.value(), "w": rect.width(), "h": rect.height(),
                      "ox": b[0] - rect.left(), "oy": b[2] - rect.top()}
        if tool == "rectangle":
            e.spec = {"kind": "rectangle", "radius": self.opt_radius.value()}
        self.add_element(e)
        self.set_tool("select")

    # ---- polygon: the number of sides, also of a drawn polygon ---------------------------
    def _is_polygon(self, e):
        return e is not None and e.spec is not None and e.spec.get("kind") == "polygon"

    @staticmethod
    def _set_visible(pairs):
        """[(widget, shown)]: the ones that go are hidden first, then the ones
        that come are shown. Qt may lay the selection bar out in between, and
        both sets at once are wider than a 1366 px screen: the window then
        grew and stayed wider."""
        for w, shown in pairs:
            if not shown:
                w.setVisible(False)
        for w, shown in pairs:
            if shown:
                w.setVisible(True)

    def _show_polygon_options(self):
        e = self.selected
        show = self.view.tool == "polygon" or self._is_polygon(e)
        rect = self.view.tool == "rectangle" or self._is_rectangle(e)
        has = e is not None
        self._set_visible([(self.sides_label, show), (self.opt_sides, show), (self.radius_label, rect),
                           (self.opt_radius, rect), (self.angle_label, has), (self.opt_angle, has),
                           (self.btn_rotate, has)])
        if self._is_polygon(e) and self.opt_sides.value() != e.spec["sides"]:
            self._updating = True
            self.opt_sides.setValue(e.spec["sides"])
            self._updating = False
        if self._is_rectangle(e) and abs(self.opt_radius.value() - e.spec["radius"]) > 1e-9:
            self._updating = True
            self.opt_radius.setValue(e.spec["radius"])
            self._updating = False

    @staticmethod
    def _is_rectangle(e):
        return e is not None and e.spec is not None and e.spec.get("kind") == "rectangle"

    def _radius_changed(self, radius):
        """New rectangles get these corners; a selected rectangle is redrawn
        with them in its own box."""
        self.settings.setValue("draw/corner_radius", radius)
        e = self.selected
        if self._updating or not self._is_rectangle(e) or abs(e.spec["radius"] - radius) < 1e-9:
            return
        self._checkpoint()
        x0, x1, y0, y1 = e.bounds
        e.paths = shapes.rounded_rectangle(x0, y0, x1, y1, radius)
        e.spec = {"kind": "rectangle", "radius": radius}
        self.refresh()

    def _after_resize(self, e):
        """A resized element: a rectangle keeps round (not stretched) corners
        and stays editable; texts and polygons become plain shapes."""
        if self._is_rectangle(e):
            x0, x1, y0, y1 = e.bounds
            e.paths = shapes.rounded_rectangle(x0, y0, x1, y1, e.spec["radius"])
        else:
            e.spec = None

    def rotate_selected(self, degrees):
        """Turn the selected elements together by any angle (plus =
        counter-clockwise), about the middle of their box."""
        chosen = self._chosen()
        if not chosen or abs(degrees) < 1e-9:
            return
        self.settings.setValue("draw/rotate_by", degrees)
        self._checkpoint()
        boxes = [e.bounds for e in chosen]
        cx = (min(b[0] for b in boxes) + max(b[1] for b in boxes)) / 2.0
        cy = (min(b[2] for b in boxes) + max(b[3] for b in boxes)) / 2.0
        import math
        a = math.radians(degrees)
        c, s_ = math.cos(a), math.sin(a)
        for e in chosen:
            # y is down on screen: counter-clockwise on screen is -a here (as Element.rotate)
            e.transform(lambda x, y: (cx + (x - cx) * c + (y - cy) * s_, cy - (x - cx) * s_ + (y - cy) * c))
            e.spec = None
        self.refresh()

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

        def mm(v):                               # as the window writes numbers (a comma in Polish)
            return MaterialView._mm(v)
        self.measure_text = _("Length <b>%(length)s mm</b> &nbsp; across %(across)s mm &nbsp; along "
                              "%(along)s mm") % {"length": mm(math.hypot(dx, dy)), "across": mm(abs(dx)),
                                                 "along": mm(abs(dy))}
        self._show_options()

    # ---- text --------------------------------------------------------------------------
    def _text_spec_from_widgets(self):
        spec = {"kind": "text", "text": self.opt_text.text(), "family": self.opt_font.currentFont().family(),
                "size": self.opt_size.value(), "bold": self.opt_bold.isChecked(),
                "italic": self.opt_italic.isChecked(), "spacing": self.opt_spacing.value()}
        e = self.selected
        if self._is_text(e) and e.spec.get("path"):           # a text on a path keeps its path
            def exact(widget, key):
                # the field shows 0.1 mm: its value as shown means "unchanged", keep the exact one
                old = e.spec.get(key, 0.0)
                return old if abs(widget.value() - round(old, widget.decimals())) < 1e-9 else widget.value()
            spec.update(path=e.spec["path"], offset=exact(self.opt_path_offset, "offset"),
                        distance=exact(self.opt_path_distance, "distance"), flip=self.opt_path_flip.isChecked())
        return spec

    def _is_text(self, e):
        return e is not None and e.spec is not None and e.spec.get("kind") == "text"

    def _show_text_options(self):
        """The text fields: with the text tool, or when a text is selected (filled from it)."""
        e = self.selected
        show = self.view.tool == "text" or self._is_text(e)
        on_path = self._is_text(e) and bool(e.spec.get("path"))
        # on a path already: the button keeps only its icon (its name in the
        # tooltip), so the path's fields fit a 1366 px screen
        self.btn_text_path.setToolButtonStyle(Qt.ToolButtonIconOnly if on_path else Qt.ToolButtonTextBesideIcon)
        # the second row of the selection bar (see _set_visible)
        self._set_visible([(w, show) for w in self.text_widgets + self.text_labels] + [(self.text_row, show)]
                          + [(w, on_path) for w in self.path_widgets + self.path_labels])
        if on_path:
            self._updating = True
            self.opt_path_offset.setValue(e.spec.get("offset", 0.0))
            self.opt_path_distance.setValue(e.spec.get("distance", 0.0))
            self.opt_path_flip.setChecked(bool(e.spec.get("flip", False)))
            self._updating = False
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
            widgets.warn(self, _("Text"), _("Type the text in the options bar first."))
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
        if spec.get("path") and abs(spec["offset"] - e.spec.get("offset", 0.0)) < 1e-9:
            # a text on a path changed (not moved along it): its middle stays where it was
            def length(sp):
                return texts.text_length(sp["text"], sp["family"], sp["size"], sp["bold"], sp["italic"],
                                         sp["spacing"])
            spec["offset"] = e.spec.get("offset", 0.0) + (length(e.spec) - length(spec)) / 2.0
            self._updating = True
            self.opt_path_offset.setValue(spec["offset"])
            self._updating = False
        paths = texts.spec_paths(spec)
        if not paths:
            return
        self._checkpoint()
        x0, _x1, _y0, y1 = e.bounds
        e.paths = paths
        e.spec = spec
        e.name = spec["text"].split("\n")[0][:30] or e.name
        if not spec.get("path"):                 # on a path it stands where its path is
            nx0, _nx1, _ny0, ny1 = e.bounds
            e.move_by(x0 - nx0, y1 - ny1)
        self.refresh()

    def put_text_on_path(self):
        """The selected text along the other selected shape (its longest
        outline): a closed one runs clockwise with the text centred at its
        top. The shape stays, but is no longer cut (tick it to cut it too).
        Returns the text (or None)."""
        chosen = self._chosen()
        text = [e for e in chosen if self._is_text(e)]
        guides = [e for e in chosen if e not in text]
        if len(text) != 1 or len(guides) != 1:
            if len(text) == 2 and not guides:          # a text can be the path of another text
                text, guides = text[:1], text[1:]
            else:
                self.statusBar().showMessage(_("Select one text and one shape (a line, a curve, a circle) "
                                               "for it to run along."), 8000)
                return None
        e, guide = text[0], guides[0]
        from vintyl.core import curves
        subs = sorted(guide.paths, key=lambda sub: -len(curves.flatten([sub], 0.05)[0]))
        sub = subs[0]
        pts = curves.flatten([sub], 0.05)[0]
        if sub["closed"] and pts[0] != pts[-1]:
            pts = pts + [pts[0]]
        sp = dict(e.spec)
        sp.pop("path", None)
        length = texts.text_length(sp["text"], sp["family"], sp["size"], sp["bold"], sp["italic"], sp["spacing"])
        path, offset = texts.prepare_path(pts, sub["closed"], length)
        spec = dict(sp, path=path, offset=offset, distance=0.0, flip=False)
        paths = texts.spec_paths(spec)
        if not paths:
            return None
        self._checkpoint()
        e.paths, e.spec = paths, spec
        guide.cut = False
        self.selected, self.selection = e, [e]
        self.refresh()
        self.statusBar().showMessage(_("The text runs along \"%s\"; that shape stays as a guide and is not cut "
                                       "(tick it in the list to cut it too).") % guide.name, 10000)
        return e

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
        from vintyl.gui.widgets import Segmented
        st = self.settings
        dist = _spin(500.0, 2, " mm", minimum=0.01)
        dist.setValue(float(st.value("offset/distance", 3.0)))
        way = Segmented()
        way.addItem(_("outwards"), True)
        way.addItem(_("inwards"), False)
        way.setCurrentIndex(0 if st.value("offset/outward", "true") == "true" else 1)
        corners = Segmented()
        corners.addItem(_("round"), True)
        corners.addItem(_("sharp"), False)
        corners.setCurrentIndex(0 if st.value("offset/round", "true") == "true" else 1)
        keep = Switch(_("Keep the original shape"))
        keep.setChecked(st.value("offset/keep", "true") == "true")
        no_holes = Switch(_("Remove the holes inside"))
        no_holes.setChecked(st.value("offset/no_holes", "false") == "true")
        values = self._ask(_("Offset"), [("distance", _("Distance"), dist), ("outward", _("Direction"), way),
                                         ("round", _("Corners"), corners), ("keep", None, keep),
                                         ("no_holes", None, no_holes)],
                           hint=_("Only the outer outline stays, with no holes (in O, A, a ring): "
                                  "a solid backing for a text in another colour"))
        if values is None:
            return None
        for k, v in values.items():
            st.setValue("offset/" + k, str(v).lower() if isinstance(v, bool) else v)
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
        new = Element(self._name(_("Pattern")), paths, chosen[0].cut, group=gid, spec={"kind": "pattern"})
        i = max(self.design.elements.index(e) for e in chosen)
        self.design.elements.insert(i, new)        # in the list before its shape: cut before it
        self.selected = new
        self.selection = [new]
        self.refresh()
        self.statusBar().showMessage(ngettext("%d shape placed.", "%d shapes placed.", count) % count, 6000)
        return new

    def _preview_column(self):
        """Left of the pattern windows: the 200 px picture, its caption and a
        line of status (how many shapes fit, "working it out")."""
        from vintyl.gui.previews import ShapePreview
        column = QWidget()
        lay = QVBoxLayout(column)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        preview = ShapePreview(200)
        caption = QLabel(_("Preview of your shape"))
        caption.setObjectName("preview_caption")
        caption.setAlignment(Qt.AlignCenter)
        status = QLabel()
        status.setObjectName("preview_caption")
        status.setAlignment(Qt.AlignCenter)
        status.setWordWrap(True)
        status.setFixedWidth(200)
        lay.addWidget(preview)
        lay.addWidget(caption)
        lay.addWidget(status)
        return column, preview, status

    def _run_preview_dialog(self, dlg, prev):
        """Run a pattern window beside the sheet; True when accepted."""
        from PySide6.QtWidgets import QDialog
        self._place_beside(dlg)
        accepted = dlg.exec() == QDialog.Accepted
        prev.wait()
        return accepted

    def _ask_tile(self, chosen, show=True):
        """The Pattern of shapes window (UI v2, 5.8): the preview left, the
        fields right, "Insert the pattern". show=False returns the window, not
        run (for tests), with .values_now() and .preview."""
        from vintyl.core import tile
        from vintyl.gui.previewer import Previewer
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
        stagger = Switch(_("Every second row shifted"))
        stagger.setChecked(st.value("tile/stagger", "true") == "true")
        column, preview, status = self._preview_column()
        rows = [("motif", _("Shape"), motif), ("size", _("Size"), size), ("gap", _("Gap"), gap),
                ("margin", _("Margin"), margin), ("stagger", None, stagger)]
        dlg = widgets.form_dialog(self, _("Pattern of shapes"), rows, action=_("Insert the pattern"),
                                  hint=_("Only shapes that fit whole are placed; they are cut before the "
                                         "outline. A gap below about 1.5 mm tears when weeding."),
                                  left=column, show=False)

        def values_now():
            return {"motif": motif.currentData(), "size": size.value(), "gap": gap.value(),
                    "margin": margin.value(), "stagger": stagger.isChecked()}

        # the live preview: in the window and dashed on the sheet, worked out
        # in the background
        outline = [sub for e in chosen for sub in e.paths]
        outline_path = painter_path(outline)
        preview.set_paths(outline_path)
        prev = Previewer(dlg)

        def ask_preview(*_a):
            v = values_now()
            m = tile.motif(v["motif"])
            prev.request(lambda: tile.tile(outline, m, v["size"], v["gap"], v["stagger"], v["margin"]))

        def show_result(result):
            if isinstance(result, Exception):
                self.view.show_preview(None)
                preview.set_paths(outline_path)
                status.setText(_("Cannot work it out: %s") % result)
                return
            paths, count = result
            self.view.show_preview(paths)
            preview.set_paths(outline_path, painter_path(paths))
            status.setText(ngettext("%d shape fits.", "%d shapes fit.", count) % count if count else
                           _("No shape fits inside: make them smaller or the margin narrower."))
        prev.ready.connect(show_result)
        prev.busy.connect(lambda b: b and status.setText(_("Working it out…")))
        motif.currentIndexChanged.connect(ask_preview)
        for w in (size, gap, margin):
            w.valueChanged.connect(ask_preview)
        stagger.toggled.connect(ask_preview)
        ask_preview()
        dlg.values_now, dlg.preview, dlg.previewer, dlg.status = values_now, preview, prev, status
        if not show:
            return dlg
        accepted = self._run_preview_dialog(dlg, prev)
        self.view.show_preview(None)
        if not accepted:
            return None
        values = values_now()
        for k, v in values.items():
            st.setValue("tile/" + k, str(v).lower() if isinstance(v, bool) else v)
        return values

    def _ask_fill(self, chosen, show=True):
        """The Fill window (UI v2, 5.8): the preview left; the nine patterns as
        pictures in a 3 x 3 grid, Spacing, Angle, Margin; "Remove the fill"
        left, Cancel, "Fill". The shapes on the sheet show the fill too.
        show=False returns the window, not run (for tests)."""
        from vintyl.gui.previewer import Previewer
        from vintyl.gui.previews import pattern_icon, polyline_path
        current = chosen[0].fill
        st = self.settings
        pattern = Segmented(columns=3, icon_size=30)
        for code, label in self.FILL_PATTERNS:
            pattern.addItem(_(label), code, pattern_icon(code, 30))
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
        column, preview, status = self._preview_column()
        remove = QPushButton(_("Remove the fill"))
        remove.setEnabled(bool(current))
        rows = [("pattern", None, pattern), ("spacing", _("Spacing"), spacing), ("angle", _("Angle"), angle),
                ("margin", _("Margin"), margin)]
        # "Fill it": the button's verb ("Fill" is the window's name, "Wypełnienie")
        dlg = widgets.form_dialog(self, _("Fill"), rows, action=_("Fill it"),
                                  hint=_("Only for the pen. A solid fill: the spacing a little less than "
                                         "the pen's width."),
                                  left=column, show=False, buttons_left=[remove])
        removed = []
        remove.clicked.connect(lambda: (removed.append(True), dlg.accept()))

        def values_now():
            return {"pattern": pattern.currentData(), "spacing": spacing.value(), "angle": angle.value(),
                    "margin": margin.value()}

        # the live preview: in the window, and the shapes on the sheet show the
        # fill as it would be; worked out in the background (into the fill
        # cache), then drawn
        outline_path = painter_path([sub for e in chosen for sub in e.paths])
        preview.set_paths(outline_path)
        prev = Previewer(dlg)

        def ask_preview(*_a):
            spec = self._fill_spec(values_now())
            copies = [e.copy() for e in chosen]

            def work():
                lines = []
                for c in copies:
                    c.fill = spec
                    lines += c.fill_lines()
                return spec, lines
            prev.request(work)

        def show_result(result):
            if isinstance(result, Exception):
                status.setText(_("Cannot work it out: %s") % result)
                return
            spec, lines = result
            status.setText("")
            preview.set_paths(outline_path, polyline_path(lines))
            for e in chosen:
                e.fill = dict(spec)
            self.refresh()
        prev.ready.connect(show_result)
        prev.busy.connect(lambda b: b and status.setText(_("Working it out…")))
        pattern.currentIndexChanged.connect(ask_preview)
        for w in (spacing, angle, margin):
            w.valueChanged.connect(ask_preview)
        ask_preview()
        dlg.values_now, dlg.preview, dlg.previewer, dlg.status = values_now, preview, prev, status
        dlg.pattern, dlg.remove_button = pattern, remove
        if not show:
            return dlg
        if not self._run_preview_dialog(dlg, prev):
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
        """The program's settings. values: {"grid_step", "snap_objects",
        and optionally "language" ("" = the system's), "theme",
        "check_updates"} without asking (for the tests); None asks. The
        language and the theme apply at the next start."""
        from vintyl import i18n
        st = self.settings
        if values is None:
            from PySide6.QtWidgets import QDialog
            from vintyl.gui.widgets import Card, Segmented
            dlg = QDialog(self)
            dlg.setWindowTitle(_("Settings"))
            dlg.setMinimumWidth(560)
            outer = QVBoxLayout(dlg)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)
            body = QVBoxLayout()
            body.setContentsMargins(16, 16, 16, 16)
            body.setSpacing(12)
            outer.addLayout(body, 1)
            # drawing: the grid and snapping
            card = Card(_("Drawing"))
            step = _spin(1000.0, 1, minimum=0.5)
            step.setValue(self.grid_step)
            step.setToolTip(_("Distance between the grid's lines; drawing and nodes snap to them "
                              "while the grid is on"))
            snap = Switch(_("Snap to other shapes (corners, centres, edges)"))
            snap.setChecked(self.view.snap_objects)
            card.add_row(_("Grid step"), step)
            card.add_row(None, snap)
            card.add_hint(_("Hold Alt to drag without any snapping for a moment."))
            body.addWidget(card)
            # language and look: applied at the next start
            card = Card(_("Language and look"))
            language = QComboBox()
            language.addItem(_("as the system"), "")
            for code, name in i18n.LANGUAGES.items():
                language.addItem(name, code)
            language.setCurrentIndex(max(0, language.findData(str(st.value("view/language", "")))))
            look = Segmented()
            for code, name in theme.THEMES:
                look.addItem(_(name), code)
            look.setCurrentIndex(max(0, look.findData(str(st.value("view/theme", theme.DEFAULT)))))
            card.add_row(_("Language"), language)
            card.add_row(_("Look"), look)
            card.add_hint(_("The language and the look change at the next start of Vintyl."))
            body.addWidget(card)
            # updates: once a day, and now
            card = Card(_("Updates"))
            updates = Switch(_("Check once a day for a new version"))
            updates.setChecked(str(st.value("updates/check", "true")).lower() == "true")
            card.add_row(None, updates)
            row = QHBoxLayout()
            hint = QLabel(_("Asks GitHub; nothing about you is sent."))
            hint.setObjectName("hint")
            hint.setWordWrap(True)
            now = QPushButton(icons.tabler("cloud-download"), _("Check now"))
            now.clicked.connect(lambda: self.check_for_updates(auto=False))
            row.addWidget(hint, 1)
            row.addWidget(now)
            card.body.addLayout(row)
            body.addWidget(card)
            cancel = QPushButton(_("Cancel"))
            cancel.clicked.connect(dlg.reject)
            ok = QPushButton(_("OK"))
            ok.setObjectName("primary")
            ok.setDefault(True)
            ok.clicked.connect(dlg.accept)
            widgets.footer(outer, [cancel, ok])
            if dlg.exec() != QDialog.Accepted:
                return None
            values = {"grid_step": step.value(), "snap_objects": snap.isChecked(),
                      "language": language.currentData(), "theme": look.currentData(),
                      "check_updates": updates.isChecked()}
        self.grid_step = float(values["grid_step"])
        self.view.snap_objects = bool(values["snap_objects"])
        st.setValue("view/grid_step", self.grid_step)
        st.setValue("view/snap_objects", "true" if self.view.snap_objects else "false")
        restart = False
        if "language" in values and values["language"] != str(st.value("view/language", "")):
            st.setValue("view/language", values["language"])
            restart = True
        if "theme" in values and values["theme"] != str(st.value("view/theme", theme.DEFAULT)):
            st.setValue("view/theme", values["theme"])
            restart = True
        if "check_updates" in values:
            st.setValue("updates/check", "true" if values["check_updates"] else "false")
        if restart:
            self.statusBar().showMessage(_("The new language or look shows at the next start of Vintyl."), 10000)
        if self.act_grid.isChecked():
            self.view.grid_mm = self.grid_step
        self.refresh()
        return values

    def show_shortcuts(self, show=True):
        """Every action with a key, in groups (UI v2, 5.10); built from the
        actions, so it is never out of date. Returns the dialog."""
        from vintyl.gui import info_dialogs
        return info_dialogs.shortcuts_dialog(self, self.shortcut_groups(), show)

    @staticmethod
    def _keys_of(a):
        return [k.toString(QKeySequence.NativeText) for k in a.shortcuts() if not k.isEmpty()]

    def _shortcut_row(self, a):
        """(name, [keys], short description) of an action with a key."""
        keys = self._keys_of(a)
        name = (a.iconText() or a.text()).replace("&", "")
        about = a.toolTip().replace("&", "")
        for k in keys:                                    # the key is shown on its own
            about = about.replace(" (%s)" % k, "")
        about = about.split(":", 1)[1].strip() if about.startswith(name + ":") else about
        if about.strip() == name:                          # no description of its own
            about = ""
        return name, keys, about[:1].upper() + about[1:]

    def shortcut_groups(self):
        """[(group, [(name, [keys], about)])]: the tools in the order of the
        tool strip, then by the menu each action is in (File, Edit, Object);
        the rest (view, cutter, settings, help, keys in no menu) together."""
        seen = set()

        def take(actions):
            rows = []
            for a in actions:
                if a is None or id(a) in seen or not self._keys_of(a):
                    continue
                seen.add(id(a))
                rows.append(self._shortcut_row(a))
            return rows

        def in_menu(menu):
            out = []
            for a in menu.actions():
                out += in_menu(a.menu()) if a.menu() is not None else [a]
            return out
        tools = []
        for _cat, _title, _icon, entries in self.PANEL:
            for e in entries:
                if e[0] == "tool":
                    tools.append(self.tool_actions[e[1]])
                elif e[0] == "act":
                    tools.append(getattr(self, e[1]))
        groups = [(_("Tools"), take(tools)), (_("File"), take(in_menu(self.menus["file"]))),
                  (_("Edit"), take(in_menu(self.menus["edit"]))),
                  (_("Object"), take(in_menu(self.menus["object"])))]
        rest = []
        for key in ("view", "cutter", "settings", "help"):
            rest += in_menu(self.menus[key])
        rest += self.findChildren(QAction)
        groups.append((_("View and program"), take(rest)))
        return [(title, rows) for title, rows in groups if rows]

    def shortcut_list(self):
        """(keys, command, short description) of every action with a key, by command."""
        rows = []
        for _group, entries in self.shortcut_groups():
            rows += [(", ".join(keys), name, about) for name, keys, about in entries]
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

    def show_context_menu(self, element, pos, show=True):
        """The right-click menu: for an element (copy, cut, duplicate, delete,
        group, the cutting order, nodes, cut or not), or for the empty sheet
        (paste, select all). Returns the menu (shown at pos unless show is False)."""
        menu = QMenu(self)
        if element is None:
            for a in (self.act_paste, self.act_select_all, self.act_to_origin):
                menu.addAction(a)
        else:
            for a in (self.act_copy, self.act_cut, self.act_paste, self.act_duplicate, self.act_delete):
                menu.addAction(a)
            menu.addSeparator()
            for a in (self.act_group, self.act_ungroup, self.act_copies):
                menu.addAction(a)
            menu.addSeparator()
            order = menu.addMenu(icons.tabler("arrow-up"), _("Cutting order"))
            order.addAction(_("Cut earlier (up the list)"), lambda: self.move_selected(-1))
            order.addAction(_("Cut later (down the list)"), lambda: self.move_selected(1))
            order.addAction(_("Cut first"), lambda: self.move_selected_to(0))
            order.addAction(_("Cut last"), lambda: self.move_selected_to(-1))
            menu.addSeparator()
            for a in (self.act_rot_left, self.act_rot_right, self.act_mirror_h, self.act_to_origin):
                menu.addAction(a)
            self._colour_menu(menu)
            menu.addAction(icons.tabler("vector-bezier-2"), _("Edit nodes"), lambda: self._on_edit_nodes(element))
            cut = menu.addAction(icons.tabler("check"), _("Cut this element"))
            cut.setIconVisibleInMenu(False)            # the check mark of a checkable item shows it
            cut.setCheckable(True)
            cut.setChecked(element.cut)
            cut.toggled.connect(lambda on: self.opt_cut.setChecked(on))
        self.context_menu = menu
        if show:
            menu.popup(pos)
        return menu

    def move_selected_to(self, where):
        """Move the selected element to the start (0) or the end (-1) of the
        list: it is cut first or last."""
        els = self.design.elements
        if self.selected not in els:
            return
        i = els.index(self.selected)
        j = 0 if where == 0 else len(els) - 1
        if i != j:
            self._checkpoint()
            els.insert(j, els.pop(i))
            self.refresh()

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
            item.setData(ICON_ROLE, self.kind_icon(e))
            if len(self.design.layers) > 1:
                item.setData(COLOR_ROLE, self.design.layer_of(e).color)
            item.setToolTip(_("The scissors: cut, or only shown (not cut)."))
            lst.addItem(item)
        self._show_layers()
        if self.selected in self.design.elements:
            lst.setCurrentRow(self.design.elements.index(self.selected))
        self._updating = False

    # ---- colour layers (0.9) ---------------------------------------------------------------------
    @staticmethod
    def color_icon(color, size=16):
        """A round swatch of a colour, with a thin edge (white shows on white)."""
        from PySide6.QtGui import QPainter, QPen, QPixmap
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor(theme.token("field_border")), 1))
        p.setBrush(QColor(color))
        p.drawEllipse(1, 1, size - 2, size - 2)
        p.end()
        from PySide6.QtGui import QIcon
        return QIcon(pm)

    def _layer(self):
        """The layer chosen in the Colours list (or the first)."""
        row = self.layer_list.currentRow()
        layers = self.design.layers
        return layers[row] if 0 <= row < len(layers) else layers[0]

    def _show_layers(self):
        """The Colours section: shown for a design of several colours."""
        layers = self.design.layers
        several = len(layers) > 1
        self.colours_box.setVisible(several)
        self.colours_box.line.setVisible(several)
        if not several:
            return
        was = self.layer_list.currentRow()
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        for layer in layers:
            n = len(self.design.elements_of(layer))
            item = QListWidgetItem(self.color_icon(layer.color), "%s  ·  %d" % (layer.name, n))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if layer.enabled else Qt.Unchecked)
            self.layer_list.addItem(item)
        self.layer_list.setCurrentRow(min(max(was, 0), len(layers) - 1))
        self.layer_list.blockSignals(False)
        # as high as its rows (it does not scroll with a few colours)
        rows = min(len(layers), 6)
        self.layer_list.setFixedHeight(rows * self.layer_list.sizeHintForRow(0) + 4)
        self.layer_summary.setText(ngettext("%d colour", "%d colours", len(layers)) % len(layers))

    def _layer_item_changed(self, item):
        layer = self.design.layers[self.layer_list.row(item)]
        on = item.checkState() == Qt.Checked
        if layer.enabled != on:
            self._checkpoint()
            layer.enabled = on
            self.refresh()

    def _layer_clicked(self, item):
        """A click on a colour selects its elements on the sheet."""
        layer = self.design.layers[self.layer_list.row(item)]
        els = self.design.elements_of(layer)
        if els:
            self.view.select_many(els)
            self.selection, self.selected = list(els), els[0]
            self._show_options()

    def move_layer(self, step):
        """Draw the chosen colour earlier (-1) or later (+1)."""
        layers = self.design.layers
        i = self.layer_list.currentRow()
        j = i + step
        if not (0 <= i < len(layers) and 0 <= j < len(layers)):
            return
        self._checkpoint()
        layers[i], layers[j] = layers[j], layers[i]
        self.layer_list.setCurrentRow(j)
        self.refresh()
        self.layer_list.setCurrentRow(j)

    def edit_layer(self, layer=None, values=None):
        """A colour's name, colour, and its pen (width, where the stroke lies;
        empty: as in the window). values: {"name", "color", "pen_width_mm",
        "pen_place"} without asking (tests); None asks. Returns the values."""
        layer = layer or self._layer()
        if values is None:
            from PySide6.QtWidgets import QColorDialog
            name = QLineEdit(layer.name)
            color = QPushButton(layer.color)
            color.setIcon(self.color_icon(layer.color))
            picked = [layer.color]

            def pick():
                c = QColorDialog.getColor(QColor(picked[0]), self, _("Colour"))
                if c.isValid():
                    picked[0] = c.name()
                    color.setText(picked[0])
                    color.setIcon(self.color_icon(picked[0]))
            color.clicked.connect(pick)
            width = _spin(5.0, 2, " mm", minimum=0.0)
            width.setSpecialValueText(_("as in the window"))
            width.setValue(layer.pen_width_mm or 0.0)
            place = QComboBox()
            place.addItem(_("as in the window"), None)
            for code, label in (("on", N_("on the line")), ("outside", N_("outside the line")),
                                ("inside", N_("inside the line"))):
                place.addItem(_(label), code)
            place.setCurrentIndex(max(0, place.findData(layer.pen_place)))
            got = self._ask(_("Colour"), [("name", _("Name"), name), ("color", _("Colour"), color),
                                          ("pen_width_mm", _("Pen width"), width), ("pen_place", _("Draw"), place)],
                            hint=_("The pen's values are used when the tool is the marker pen; empty: as in "
                                   "the window."))
            if got is None:
                return None
            values = {"name": name.text().strip() or layer.name, "color": picked[0],
                      "pen_width_mm": width.value() or None, "pen_place": place.currentData()}
        self._checkpoint()
        layer.name = values.get("name", layer.name)
        layer.color = values.get("color", layer.color)
        layer.pen_width_mm = values.get("pen_width_mm", layer.pen_width_mm)
        layer.pen_place = values.get("pen_place", layer.pen_place)
        self.refresh()
        return values

    def move_to_layer(self, layer):
        """The selected elements into a colour layer."""
        chosen = self._chosen()
        if not chosen:
            return
        self._checkpoint()
        for e in chosen:
            e.layer = layer.id
        self.refresh()

    def new_layer_for_selection(self, color=None, name=None):
        """A new colour for the selected elements (color None asks for it).
        Returns the new layer."""
        from vintyl.core import layers as lay
        if color is None:
            from PySide6.QtWidgets import QColorDialog
            c = QColorDialog.getColor(QColor("#e11d48"), self, _("New colour"))
            if not c.isValid():
                return None
            color = c.name()
        layer = lay.Layer(lay.new_id(self.design.layers),
                          lay.unique_name(name or _(lay.color_name(color)), self.design.layers), color)
        self.design.layers.append(layer)
        self.move_to_layer(layer)
        return layer

    def _colour_menu(self, menu):
        """The right-click menu's "Colour" part: move the selection into a layer."""
        sub = menu.addMenu(icons.tabler("palette"), _("Colour"))
        for layer in self.design.layers:
            a = sub.addAction(self.color_icon(layer.color), layer.name)
            a.triggered.connect(lambda _c=False, ly=layer: self.move_to_layer(ly))
        sub.addSeparator()
        sub.addAction(_("New colour…"), lambda: self.new_layer_for_selection())
        return sub

    def _list_item_changed(self, item):
        if self._updating:
            return
        e = self.design.elements[self.element_list.row(item)]
        self._checkpoint()
        e.cut = item.checkState() == Qt.Checked
        self.refresh()

    def list_context_menu(self, pos, show=True):
        """The right button on the element list (pos: in its viewport): the
        row's element is selected (a selection it is part of stays) and the
        same menu as on the sheet opens; below the rows, the sheet's menu.
        Returns the menu."""
        item = self.element_list.itemAt(pos)
        element = None
        if item is not None:
            element = self.design.elements[self.element_list.row(item)]
            if element not in (self.selection or [self.selected]):
                self.element_list.setCurrentRow(self.element_list.row(item))
                self._enable_selection_actions()
        return self.show_context_menu(element, self.element_list.viewport().mapToGlobal(pos), show)

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
        return ([e.copy() for e in els], els.index(self.selected) if self.selected in els else None,
                [layer.copy() for layer in self.design.layers])

    def _restore(self, snap):
        elements, index, layers = snap
        self.design.elements = elements
        self.design.layers = layers
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
        # the header's short line (UI v2: "5 · 680 × 286 mm"); empty: a word, and a hint in the list
        if box is None:
            self.summary.setText(_("Empty"))
        else:
            self.summary.setText("%d · %s" % (n, _("%.0f × %.0f mm") % (box[1] - box[0], box[3] - box[2])))
        self.empty_hint.setVisible(box is None)
        self._enable_selection_actions()
        self.act_undo.setEnabled(bool(self._undo))
        self.act_redo.setEnabled(bool(self._redo))
        self._update_title()
        self.refresh_job()

    def _show_machine(self):
        """The machine's line under its name: connection, port, width."""
        p = self.profile
        conn = _("USB printer") if p.connection == "usb-printer" else _("serial port")
        line = "%s · %s · %s" % (conn, p.port or _("no port"), _("cuts %g mm") % p.width_mm)
        ready = bool(p.port) and os.path.exists(p.port) and transport.access_problem(p.port) is None
        state = _("Ready to cut") if ready else _("Not plugged in")
        dot = theme.token("ok") if ready else theme.token("disabled_icon")
        self.cutter_info.setText('<span style="color:%s">&#9679;</span>&nbsp; %s · %s'
                                 % (dot, state, line.replace("<", "&lt;")))
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
            text = problem
        elif port and not os.path.exists(port):
            text = _("%s is not there now: plug the cutter in and switch it on, or choose "
                     "its port in the cutter's settings.") % port
        else:
            text = ""
        # the yellow frame: what is wrong, and a link to the help on Linux groups
        self.port_problem.setText(text.replace("\n", "<br>") + (' <a href="help">%s</a>' % _("How to do it")
                                                                if problem else ""))
        self.port_warning.setVisible(bool(text))
        return problem

    def show_access_help(self, show=True):
        """Which Linux group the cutter's device needs, and the commands to
        join it (UI v2, 5.11). Returns the dialog."""
        from vintyl.gui import info_dialogs
        port = self.profile.port
        return info_dialogs.access_dialog(self, port, transport.access_problem(port), show)

    def refresh_job(self):
        self.check_port_access()
        self.view.show_frame(self.weed_frame_polyline(self._frame_polys(*self.design.material_paths())))
        p = self.job_profile()
        self.profile_label.setText("%s · %s · %s" % (p.name, p.language.upper(), p.port or _("no port")))
        busy = getattr(self, "sending", False)
        self.last_job = None
        try:
            self.last_job = self.build()
        except (JobError, ProfileError) as e:
            self.stat_cut.setText("–")
            self.stat_travel.setText("–")
            self.job_label.setText(str(e))
            self.job_label.setVisible(True)
            self.job_label.setStyleSheet("color: %s" % theme.token("error"))
            for w in (self.btn_save, self.act_save_cut, self.btn_start):
                w.setEnabled(False)
            self.view.show_knife(None)
            return
        self.view.show_knife(self.last_job.knife_paths if self.act_knife.isChecked() else None)
        j = self.last_job
        # the two tiles: the length cut (or drawn) and the travel, in metres
        self.stat_cut_title.setText(_("Drawn length") if self.is_pen() else _("Cut length"))
        self.stat_cut.setText(_("%.2f m") % (j.cut_mm / 1000.0))
        self.stat_travel.setText(_("%.2f m") % (j.travel_mm / 1000.0))
        text = []
        if self.mirror_job.isChecked():
            text.append(_("MIRRORED"))
        if p.speed_cm_s:
            minutes = (j.cut_mm + j.travel_mm) / (p.speed_cm_s * 10.0) / 60.0
            text.append(_("About %.1f min at %g mm/s") % (minutes, round(p.speed_cm_s * 10.0, 1)))
        self.job_label.setText(" · ".join(text))
        self.job_label.setVisible(bool(text))
        self.job_label.setStyleSheet("")
        for w in (self.btn_save, self.act_save_cut, self.btn_start):
            w.setEnabled(not busy)

    # ---- output --------------------------------------------------------------------------
    def save_cutter_file(self, path=None):
        """Save the cutter commands to a file. Returns the path, or None."""
        try:
            job = self.build()
        except (JobError, ProfileError) as e:
            widgets.warn(self, _("Save cutter file"), str(e))
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
            widgets.warn(self, _("Start"), str(e))
            return None
        p = self.job_profile()
        # the check list (UI v2): the cutter, the tool, the material; its force and speed; what to check
        from vintyl.gui import start_dialogs
        m = self.material()
        note = (_(m.note) if self._material_is_builtin() else m.note) if m is not None and m.note else ""
        if not start_dialogs.confirm_start(self, p.name, p.port, self.is_pen(), self._material_name(),
                                           self.material_values(), not self.profile.send_speed_force,
                                           self.mirror_job.isChecked(), note, details=self.cut_details()):
            return None
        return self._send(job, p, "the design")

    def _send(self, job, p, what):
        """Send a job to the cutter in the background (after the user said yes)."""
        from vintyl.core.protocols import encoder_for
        from vintyl.core import diag
        diag.log.info("Start (%s): %s on %s (%s, %s), %d bytes, %.2f m to %s", what, p.name, p.port, p.connection,
                      p.language, len(job.text), job.cut_mm / 1000.0, "draw" if self.is_pen() else "cut")
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
        self.send_label.setText("%s  %d%%" % (_("Sending to the cutter"), round(100.0 * sent / max(total, 1))))

    # ---- copies, weeding lines, strips ------------------------------------------------------------
    def _ask(self, title, rows, extra=None, hint=None, action=None):
        """A small dialog of fields (UI v2, widgets.form_dialog): rows =
        [(key, label, widget)]; returns {key: value} or None. extra(layout)
        may add more (e.g. a button); hint: a line under the fields."""
        return widgets.form_dialog(self, title, rows, action=action, hint=hint, extra=extra)

    def copies_selected(self, values=None):
        """Copies of the selection in rows (up the material) and columns
        (across, to the left), `gap` mm apart; the selection is the first.
        values: {"rows", "columns", "gap"}; None asks. Returns the copies."""
        chosen = self._chosen()
        if not chosen:
            return []
        boxes = [e.bounds for e in chosen]
        x0, x1 = min(b[0] for b in boxes), max(b[1] for b in boxes)
        y0, y1 = min(b[2] for b in boxes), max(b[3] for b in boxes)
        w, h = x1 - x0, y1 - y0
        if values is None:
            rows, cols = QSpinBox(), QSpinBox()
            rows.setRange(1, 200)
            cols.setRange(1, 200)
            rows.setValue(int(self.settings.value("copies/rows", 2)))
            cols.setValue(int(self.settings.value("copies/columns", 2)))
            gap = _spin(1000.0, 1, minimum=0.0)
            gap.setValue(float(self.settings.value("copies/gap", 3.0)))
            gap.setToolTip(_("Vinyl left between the copies"))

            def fill_width(form):
                b = QPushButton(_("As many columns as fit in the width"))
                b.clicked.connect(lambda: cols.setValue(max(1, int((x1 + self.profile.width_mm + gap.value())
                                                                   / (w + gap.value())))))
                form.addWidget(b)
            values = self._ask(_("Copies"), [("rows", _("Rows (along)"), rows), ("columns", _("Columns (across)"), cols),
                                             ("gap", _("Gap"), gap)], fill_width,
                               hint=_("The gap is the vinyl left between the copies."))
            if values is None:
                return []
            for k in ("rows", "columns", "gap"):
                self.settings.setValue("copies/" + k, values[k])
        import uuid
        made = []
        for r in range(int(values["rows"])):
            for c in range(int(values["columns"])):
                if r == 0 and c == 0:
                    continue
                groups = {}
                for e in chosen:
                    n = e.copy()
                    if e.group:                         # each copy of a group is a group of its own
                        n.group = groups.setdefault(e.group, uuid.uuid4().hex[:8])
                    n.move_by(-c * (w + values["gap"]), -r * (h + values["gap"]))
                    made.append(n)
        if not made:
            return []
        self._checkpoint()
        self.design.elements.extend(made)
        self.selection = list(chosen) + made
        self.selected = chosen[0]
        self.refresh()
        self.statusBar().showMessage(ngettext("%d copy made.", "%d copies made.", len(made) // len(chosen))
                                     % (len(made) // len(chosen)), 6000)
        return made

    def add_weeding_lines(self, values=None):
        """Weeding lines in the weeding frame (it is switched on), replacing
        earlier ones. values: {"direction", "spacing", "margin"}; None asks.
        Returns the new element (or None)."""
        from vintyl.core import curves, weeding
        shapes_ = [e for e in self.design.elements if e.cut and not (e.spec and e.spec.get("kind") == "weeding")]
        if not shapes_:
            self.statusBar().showMessage(_("There is nothing to cut yet."), 6000)
            return None
        if values is None:
            from vintyl.gui.widgets import Segmented
            way = Segmented()
            for code, label in (("level", N_("across")), ("upright", N_("up and down")), ("both", N_("both"))):
                way.addItem(_(label), code)
            way.setCurrentIndex(max(0, way.findData(self.settings.value("weed/direction", "upright"))))
            spacing = _spin(1000.0, 0, minimum=5.0)
            spacing.setValue(float(self.settings.value("weed/spacing", 40.0)))
            spacing.setToolTip(_("Distance between the lines"))
            margin = _spin(20.0, 1, minimum=0.5)
            margin.setValue(float(self.settings.value("weed/margin", 1.5)))
            margin.setToolTip(_("The lines stop this far from the shapes"))
            values = self._ask(_("Weeding lines"), [("direction", _("Lines"), way), ("spacing", _("Every"), spacing),
                                                    ("margin", _("Margin"), margin)],
                               hint=_("Margin: the lines stop this far from the shapes."))
            if values is None:
                return None
            for k, v in values.items():
                self.settings.setValue("weed/" + k, v)
        boxes = [e.bounds for e in shapes_]
        m = self.weed_margin.value()
        frame = (min(b[0] for b in boxes) - m, max(b[1] for b in boxes) + m,
                 min(b[2] for b in boxes) - m, max(b[3] for b in boxes) + m)
        rings = []
        for e in shapes_:
            rings += curves.flatten([sub for sub in e.paths if sub["closed"]], 0.05)
        lines = weeding.weeding_lines(frame, outermost(rings), values["spacing"], values["direction"],
                                      values["margin"])
        if not lines:
            self.statusBar().showMessage(_("No line fits between the shapes; try a smaller margin."), 8000)
            return None
        self._checkpoint()
        self.design.elements = [e for e in self.design.elements
                                if not (e.spec and e.spec.get("kind") == "weeding")]
        e = Element(_("Weeding lines"), curves.from_polylines(lines, [False] * len(lines)),
                    spec={"kind": "weeding", **values})
        self.design.elements.append(e)                  # last in the list: cut after the shapes
        self.weed_frame.blockSignals(True)
        self.weed_frame.setChecked(True)                # the lines end at the frame
        self.weed_frame.blockSignals(False)
        self.selected, self.selection = e, [e]
        self.refresh()
        return e

    def split_into_strips(self, values=None):
        """Split the selection (or the whole design) into strips that overlap:
        "across" for a design wider than the cutter, "along" for one longer
        than a sheet. The strips are laid one after another along the
        material, a gap apart, each within the cutting width. values:
        {"direction", "size", "overlap", "gap"}; None asks. Returns the strips."""
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPainterPath, QTransform
        from vintyl.core import curves
        from vintyl.core.patterns import clip_polylines
        from vintyl.gui.canvas import painter_path
        chosen = self._chosen() or [e for e in self.design.elements]
        if not chosen:
            return []
        boxes = [e.bounds for e in chosen]
        x0, x1 = min(b[0] for b in boxes), max(b[1] for b in boxes)
        y0, y1 = min(b[2] for b in boxes), max(b[3] for b in boxes)
        if values is None:
            way = QComboBox()
            way.addItem(_("across: wider than the cutter"), "across")
            way.addItem(_("along: longer than the sheet"), "along")
            size = _spin(100000.0, 0, minimum=20.0)
            size.setValue(max(20.0, self.profile.width_mm - 2 * PLACE_MARGIN_MM))
            size.setToolTip(_("How wide (or long) each strip is, with its overlap"))
            overlap = _spin(200.0, 1, minimum=0.0)
            overlap.setValue(10.0)
            overlap.setToolTip(_("The strips cover this much of each other, for laying them together"))
            gap = _spin(500.0, 0, minimum=0.0)
            gap.setValue(20.0)
            gap.setToolTip(_("Space between the strips on the material"))
            values = self._ask(_("Split into strips"), [("direction", _("Split"), way), ("size", _("Strip"), size),
                                                         ("overlap", _("Overlap"), overlap), ("gap", _("Gap"), gap)],
                               hint=_("Overlap: the strips cover this much of each other, for laying them "
                                      "together."))
            if values is None:
                return []
        across = values["direction"] == "across"
        span = (x1 - x0) if across else (y1 - y0)
        size, lap = float(values["size"]), float(values["overlap"])
        if size <= lap or span <= size:
            self.statusBar().showMessage(_("The design fits in one strip; nothing to split."), 6000)
            return []
        step = size - lap
        n = int((span - lap) // step) + (1 if (span - lap) % step > 1e-6 else 0)
        scale = 10.0                                    # as the shape operations: Qt's curves stay round
        up = QTransform.fromScale(scale, scale)
        strips = []
        for k in range(n):
            if across:                                  # strips from the right (the origin's side)
                hi = x1 - k * step
                rect = QRectF(hi - size, y0 - 1, size, (y1 - y0) + 2)
            else:                                       # strips from the front (the origin's side)
                hi = y1 - k * step
                rect = QRectF(x0 - 1, hi - size, (x1 - x0) + 2, size)
            clip = QPainterPath()
            clip.addRect(up.mapRect(rect))
            paths = []
            for e in chosen:
                closed = [sub for sub in e.paths if sub["closed"]]
                if closed and e.cut:
                    path = up.map(painter_path(closed))
                    path.setFillRule(Qt.OddEvenFill)
                    paths += texts.painter_path_to_curves(path.intersected(clip).simplified(), 1.0 / scale)
                opened = [sub for sub in e.paths if not sub["closed"]]
                if opened and e.cut:
                    ring = [(rect.left(), rect.top()), (rect.right(), rect.top()), (rect.right(), rect.bottom()),
                            (rect.left(), rect.bottom()), (rect.left(), rect.top())]
                    lines = clip_polylines(curves.flatten(opened, 0.05), [ring])
                    paths += curves.from_polylines(lines, [False] * len(lines))
            if paths:
                strips.append(Element("%s %d" % (_("Strip"), k + 1), paths))
        if len(strips) < 2:
            self.statusBar().showMessage(_("The design fits in one strip; nothing to split."), 6000)
            return []
        # lay them one after another along the material, each near the origin's side
        self._checkpoint()
        pos = -PLACE_MARGIN_MM
        for s_ in strips:
            bx0, bx1, by0, by1 = s_.bounds
            s_.move_by(-PLACE_MARGIN_MM - bx1, pos - by1)
            pos -= (by1 - by0) + values["gap"]
        index = min(self.design.elements.index(e) for e in chosen)
        self.design.elements = [e for e in self.design.elements if not any(e is c for c in chosen)]
        self.design.elements[index:index] = strips
        self.selection, self.selected = list(strips), strips[0]
        self.refresh()
        self.statusBar().showMessage(ngettext("Split into %d strip, laid one after another; cut it, then lay it "
                                              "on its overlap.",
                                              "Split into %d strips, laid one after another; cut them, then lay "
                                              "them together on their overlaps.", len(strips)) % len(strips), 10000)
        return strips

    KNIFE_TEST_MM = 15.0
    KNIFE_TEST_FROM_ORIGIN_MM = 5.0

    def knife_test_job(self, material=None):
        """The job of the knife test alone: a 15 mm square with a triangle,
        5 mm from the origin (raises JobError / ProfileError)."""
        from vintyl.core import weeding
        from vintyl.core.design import Element as _El
        d = self.KNIFE_TEST_FROM_ORIGIN_MM
        test = _El("knife test", weeding.knife_test(self.KNIFE_TEST_MM, right=-d, bottom=-d))
        polys, groups = Design([test]).material_paths()
        return build_job(polys, self.job_profile(material), groups, True)

    def knife_test(self, material=None):
        """Cut the knife test (after a check list): the triangle must peel off
        cleanly and the backing must stay whole. Returns the sending (or None)."""
        try:
            job = self.knife_test_job(material)
        except (JobError, ProfileError) as e:
            widgets.warn(self, _("Knife test"), str(e))
            return None
        p = self.job_profile(material)
        from vintyl.core import weeding
        from vintyl.gui import start_dialogs
        if not start_dialogs.confirm_knife_test(self, p.name, self.KNIFE_TEST_MM,
                                                weeding.knife_test(self.KNIFE_TEST_MM),
                                                self.material_values(material),
                                                details=self.cut_details(material, pen=False)):
            return None
        return self._send(job, p, "knife test")

    def _send_finished(self, ok, message):
        from vintyl.core import diag
        (diag.log.info if ok else diag.log.warning)("Sending ended (%s): %s", "ok" if ok else "not ok", message)
        self._set_sending(False)
        self.statusBar().showMessage(message, 15000)
        if not ok:
            widgets.warn(self, _("Cutting"), message)

    def _set_sending(self, on):
        """While sending: Stop works, nothing else that would change the job."""
        self.sending = on
        self.progress.setVisible(on)
        self.send_label.setVisible(on)
        self.send_label.setText(_("Sending to the cutter"))
        self.btn_stop.setEnabled(on)
        self.btn_stop.setVisible(on)                   # Stop takes Start's place
        self.btn_start.setVisible(not on)
        for w in (self.btn_start, self.btn_save, self.btn_test, self.act_save_cut, self.profile_box, self.act_profile,
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

    # ---- new versions, the applications menu, diagnostics -----------------------------------------
    def check_for_updates(self, auto=True, fetch=None):
        """Ask GitHub for a newer release in the background. auto (at start): at
        most once a day, only when allowed in the Settings, silent when there is
        nothing new or no internet. Returns the check (a thread) or None."""
        import time
        from vintyl.core import updates
        from vintyl.gui.update_check import UpdateCheck
        st = self.settings
        if auto:
            if str(st.value("updates/check", "true")).lower() != "true":
                return None
            try:
                last = float(st.value("updates/last", 0) or 0)
            except (TypeError, ValueError):
                last = 0.0
            if time.time() - last < updates.CHECK_EVERY_S:
                return None
        st.setValue("updates/last", time.time())
        check = UpdateCheck(__version__, str(st.value("updates/skip", "")) if auto else "", self, fetch)

        def done(release, error):
            if release is not None:
                self.update_bar.show_release(release, __version__)
            elif not auto:
                if error:
                    widgets.warn(self, _("New version"),
                                        _("Could not ask GitHub (no internet?): %s") % error)
                else:
                    widgets.inform(self, _("New version"), _("You have the newest Vintyl (%s).")
                                            % __version__)
        check.done.connect(done)
        self._update_check = check
        check.start()
        return check

    def install_menu_entry(self, ask=False):
        """Put this AppImage into the desktop's applications menu (ask: first
        start, ask first and remember the answer). Returns the files written."""
        from vintyl.gui import desktop_entry
        if not desktop_entry.applies():
            return []
        if ask:
            if self.settings.value("desktop/asked", "") or desktop_entry.installed_for() == \
                    desktop_entry.appimage_path():
                return []
            self.settings.setValue("desktop/asked", "yes")
            if widgets.ask(self, _("Applications menu"),
                           _("Add Vintyl to the applications menu, and open .vintyl projects with it?\n"
                             "(Help → Add Vintyl to the applications menu does it later too.)"),
                           [("cancel", _("Not now"), "cancel"), ("add", _("Add to the menu"), "main")]) != "add":
                return []
        try:
            written = desktop_entry.install()
        except (OSError, RuntimeError) as e:
            widgets.warn(self, _("Applications menu"), str(e))
            return []
        self.statusBar().showMessage(_("Vintyl is in the applications menu (it may need a new login to show)."),
                                     10000)
        return written

    def diagnostic_report(self):
        """The text of the diagnostic report (see vintyl.core.diag)."""
        from vintyl import selftest
        from vintyl.core import diag
        from PySide6 import __version__ as qt_version
        checks = selftest.results(skip=("window",))     # this window is the window check
        keys = ("view/language", "view/theme", "view/grid_step", "view/snap_objects", "cutter/profile",
                "updates/check")
        settings = {k: self.settings.value(k) for k in keys if self.settings.value(k) is not None}
        settings["tool"] = self.tool_box.currentData()
        return diag.build_report(__version__, checks, self.profile, settings,
                                 extra=["PySide6 %s" % qt_version,
                                        "Theme %s, language %s" % (theme.current(), self._language())])

    @staticmethod
    def _language():
        from vintyl import i18n
        return i18n.current_language()

    def show_diagnostics(self, show=True):
        """The report in a window: copy it, or open GitHub's forms to report a
        problem or how Vintyl works on a cutter. Returns the dialog."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from vintyl.core import diag
        from vintyl.gui import info_dialogs
        dlg = info_dialogs.report_dialog(
            self, self.diagnostic_report(),
            lambda: self.statusBar().showMessage(_("The report is copied."), 5000),
            lambda kind: QDesktopServices.openUrl(QUrl(diag.issue_url(kind, __version__, self.profile.name))),
            show=False)
        self.diagnostics_dialog = dlg
        if show:
            dlg.exec()
        return dlg

    def about(self, show=True):
        """About Vintyl (UI v2, 5.9). Returns the dialog."""
        from vintyl.gui import info_dialogs
        return info_dialogs.about_dialog(self, __version__, lambda: self.check_for_updates(auto=False),
                                         lambda: self.show_diagnostics(), show)
