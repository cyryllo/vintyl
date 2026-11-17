"""
The windows of the Help menu (UI v2):

    about_dialog()       the program's icon, name, version; licence, website,
                         authors, what it is built with; "Check for a new
                         version", "Diagnostic report", "Third-party licences"
    notices_dialog()     THIRD-PARTY-NOTICES.md, as it travels with Vintyl
    shortcuts_dialog()   every key in groups, in three columns of cards, the
                         keys drawn as keys, with a search field
    report_dialog()      the diagnostic report: copy it, report on GitHub
    access_dialog()      which Linux group a cutter's device needs, and the
                         commands to join it, to copy

They are module functions; show=False returns the dialog, not run (tests).

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QScrollArea, QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from vintyl.gui import _, icons, theme, widgets

WEBSITE = "https://github.com/cyryllo/vintyl"


def _close_footer(dlg, outer, left=()):
    close = QPushButton(_("Close"))
    close.setObjectName("primary")
    close.setDefault(True)
    close.clicked.connect(dlg.accept)
    widgets.footer(outer, [close], left)
    dlg.close_button = close
    return close


def _muted(text):
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


def _run(dlg, show):
    if not show:
        return dlg
    dlg.exec()
    return dlg


# ---- About -------------------------------------------------------------------------------------------
def about_dialog(parent, version, on_check, on_report, show=True):
    """on_check(), on_report(): what the two buttons do."""
    dlg, outer, body = widgets.plain_dialog(parent, _("About Vintyl"), 480)
    top = QHBoxLayout()
    top.setSpacing(18)
    icon = QLabel()
    icon.setPixmap(icons.app_icon().pixmap(88, 88))
    top.addWidget(icon, 0, Qt.AlignTop)
    words = QVBoxLayout()
    words.setSpacing(2)
    name = QLabel("Vintyl")
    name.setObjectName("app_name")
    words.addWidget(name)
    words.addWidget(QLabel(_("Version %s") % version))
    words.addWidget(_muted(_("Software for cutting plotters, for Linux")))
    words.addStretch(1)
    top.addLayout(words, 1)
    body.addLayout(top)
    card = widgets.Card()
    link = QLabel('<a href="%s">%s</a>' % (WEBSITE, WEBSITE.split("://", 1)[1]))
    link.setOpenExternalLinks(True)
    built = QLabel(_("Python, Qt 6 (PySide6), pyserial, pyclipper, segno, svgelements, Tabler Icons. "
                     "Part of the code comes from Kerfly."))
    built.setWordWrap(True)
    for label, widget in ((_("Licence"), QLabel("GPL-3.0-or-later")), (_("Website"), link),
                          (_("Authors"), QLabel("Vintyl contributors")), (_("Built with"), built)):
        row = card.add_row(label, widget)
        row.layout().setAlignment(row.layout().itemAt(0).widget(), Qt.AlignTop)
    body.addWidget(card)
    buttons = QHBoxLayout()
    check = QPushButton(icons.tabler("cloud-download"), _("Check for a new version"))
    check.clicked.connect(lambda: on_check())
    report = QPushButton(icons.tabler("bug"), _("Diagnostic report"))
    report.clicked.connect(lambda: on_report())
    buttons.addWidget(check)
    buttons.addWidget(report)
    body.addLayout(buttons)
    body.addWidget(_muted(_("Does it work on another cutter for you? Tell us through “Diagnostic "
                            "report”; it helps others.")))
    body.addStretch(1)
    notices = QPushButton(_("Third-party licences"))
    notices.clicked.connect(lambda: notices_dialog(dlg))
    _close_footer(dlg, outer, [notices])
    dlg.check_button, dlg.report_button, dlg.notices_button = check, report, notices
    return _run(dlg, show)


def notices_text():
    """THIRD-PARTY-NOTICES.md: next to the program in the AppImage, at the
    top of the source otherwise; a pointer to it online when missing."""
    here = os.path.dirname(os.path.abspath(__file__))
    places = [getattr(sys, "_MEIPASS", None), os.path.join(here, "..", "..", "..")]
    for folder in places:
        if folder and os.path.isfile(os.path.join(folder, "THIRD-PARTY-NOTICES.md")):
            with open(os.path.join(folder, "THIRD-PARTY-NOTICES.md"), encoding="utf-8") as f:
                return f.read()
    return _("The list of the libraries and their licences is in THIRD-PARTY-NOTICES.md: %s") % (
        WEBSITE + "/blob/main/THIRD-PARTY-NOTICES.md")


def notices_dialog(parent, show=True):
    dlg, outer, body = widgets.plain_dialog(parent, _("Third-party licences"), 640)
    text = QTextBrowser()
    text.setOpenExternalLinks(True)
    text.setMarkdown(notices_text())
    body.addWidget(text, 1)
    _close_footer(dlg, outer)
    dlg.resize(720, 520)
    dlg.text = text
    return _run(dlg, show)


# ---- Keyboard shortcuts ---------------------------------------------------------------------------
def key_parts(sequence):
    """'Ctrl+Shift+G' -> ['Ctrl', 'Shift', 'G']; the plus key stays a key."""
    if sequence == "+":
        return ["+"]
    if sequence.endswith("++"):
        return sequence[:-2].split("+") + ["+"]
    return sequence.split("+")


def _keycaps(keys):
    """The keys of one or more sequences, each drawn as a key."""
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    for n, sequence in enumerate(keys):
        if n:
            row.addWidget(_muted("/"))
        for part in key_parts(sequence):
            cap = QLabel(part)
            cap.setObjectName("keycap")
            cap.setAlignment(Qt.AlignCenter)
            row.addWidget(cap)
    return box


def shortcuts_dialog(parent, groups, show=True):
    """groups: [(title, [(name, [key sequences], what it does)])], in order.
    Three columns of cards; the search hides what does not match the name
    or the key."""
    dlg, outer, body = widgets.plain_dialog(parent, _("Keyboard shortcuts"), 900)
    search_row = QHBoxLayout()
    search_row.setSpacing(10)
    search_row.addWidget(QLabel(_("Search")))
    search = QLineEdit()
    search.setPlaceholderText(_("Command name or key"))
    search.setClearButtonEnabled(True)
    search_row.addWidget(search, 1)
    body.addLayout(search_row)
    # the groups go into three columns, in order, each column about a third
    # of all the rows high
    total = sum(len(rows) + 2 for _t, rows in groups)
    columns, heights, col = [[], [], []], [0, 0, 0], 0
    for title, rows in groups:
        h = len(rows) + 2
        if heights[col] and heights[col] + h > total / 3.0 * 1.15 and col < 2:
            col += 1
        columns[col].append((title, rows))
        heights[col] += h
    inner = QWidget()
    inner.setObjectName("plain_scroll_inner")
    grid = QHBoxLayout(inner)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(12)
    entries = []                         # (card, [(row widget, text to search)])
    for groups_here in columns:
        lay = QVBoxLayout()
        lay.setSpacing(12)
        for title, rows in groups_here:
            card = widgets.Card(title)
            card.body.setSpacing(6)                  # a list, not a form: closer rows
            found = []
            for name, keys, about in rows:
                line = QWidget()
                h = QHBoxLayout(line)
                h.setContentsMargins(0, 0, 0, 0)
                h.setSpacing(8)
                label = QLabel(name)
                if about:
                    line.setToolTip(about)
                h.addWidget(label, 1)
                h.addWidget(_keycaps(keys))
                card.body.addWidget(line)
                found.append((line, (name + " " + " ".join(keys)).lower()))
            lay.addWidget(card)
            entries.append((card, found))
        lay.addStretch(1)
        grid.addLayout(lay, 1)
    scroll = QScrollArea()
    scroll.setObjectName("plain_scroll")             # the dialog's own ground shows through
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidget(inner)
    body.addWidget(scroll, 1)
    nothing = _muted(_("No command matches."))
    nothing.hide()
    body.addWidget(nothing)
    body.addWidget(_muted(_("Mouse: the wheel zooms, the middle button moves the view, Alt turns snapping "
                            "off, Shift draws lines in 45° steps, Escape leaves a tool.")))

    def find(text):
        words = text.lower().split()
        shown = 0
        for card, found in entries:
            here = 0
            for line, haystack in found:
                hit = all(w in haystack for w in words)
                line.setVisible(hit)
                here += hit
            card.setVisible(bool(here))
            shown += here
        nothing.setVisible(not shown)
    search.textChanged.connect(find)
    _close_footer(dlg, outer)
    dlg.resize(1000, 720)
    dlg.search, dlg.cards = search, [card for card, _f in entries]
    return _run(dlg, show)


# ---- Diagnostic report ---------------------------------------------------------------------------
def report_dialog(parent, text, on_copy, on_issue, show=True):
    """on_copy(): after the report is copied; on_issue(kind): open GitHub's
    form ("bug" or "cutter"), the report copied first."""
    dlg, outer, body = widgets.plain_dialog(parent, _("Diagnostic report"), 640)
    body.addWidget(_muted(_("Copy this and paste it into your report on GitHub. It holds the versions, the "
                            "checks, the chosen cutter and Vintyl's log; no user name, no designs.")))
    view = QPlainTextEdit(text)
    view.setReadOnly(True)
    view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))     # the columns line up
    view.setLineWrapMode(QPlainTextEdit.NoWrap)
    body.addWidget(view, 1)

    def copy():
        QGuiApplication.clipboard().setText(text)
        on_copy()
    copy_button = QPushButton(icons.tabler("copy"), _("Copy"))
    copy_button.clicked.connect(copy)
    bug = QPushButton(icons.tabler("bug"), _("Report a problem"))
    bug.setToolTip(_("Copies the report and opens GitHub's form"))
    cutter = QPushButton(_("Report my cutter"))
    cutter.setToolTip(_("Tell us how Vintyl works on your cutter (copies the report, opens GitHub's form)"))
    for button, kind in ((bug, "bug"), (cutter, "cutter")):
        button.clicked.connect(lambda _c=False, k=kind: (QGuiApplication.clipboard().setText(text), on_issue(k)))
    close = QPushButton(_("Close"))
    close.setObjectName("primary")
    close.setDefault(True)
    close.clicked.connect(dlg.accept)
    widgets.footer(outer, [bug, cutter, close], [copy_button])
    dlg.resize(760, 560)
    dlg.view, dlg.copy_button, dlg.bug_button, dlg.cutter_button = view, copy_button, bug, cutter
    return _run(dlg, show)


# ---- Access to the cutter ------------------------------------------------------------------------
COMMANDS = "sudo usermod -aG lp $USER\nsudo usermod -aG dialout $USER"


def access_dialog(parent, port, problem, show=True):
    """port: the chosen cutter's port; problem: what stops Vintyl using it
    (vintyl.core.transport.access_problem), or None."""
    dlg, outer, body = widgets.plain_dialog(parent, _("Access to the cutter"), 620)
    # the state now: green when the port can be used, yellow with the problem
    state = QFrame()
    state.setObjectName("warn" if problem or not port else "state_ok")
    row = QHBoxLayout(state)
    row.setContentsMargins(12, 10, 12, 10)
    row.setSpacing(10)
    mark = QLabel()
    if problem or not port:
        mark.setPixmap(icons.tabler("alert-triangle", theme.token("warn_ink")).pixmap(20, 20))
        now = _("Now: %s") % problem if problem else _("Now: no port is chosen.")
    else:
        mark.setPixmap(icons.tabler("check", theme.token("ok")).pixmap(20, 20))
        now = _("Now: you may use %s.") % port
    words = QLabel(now)
    words.setWordWrap(True)
    row.addWidget(mark, 0, Qt.AlignTop)
    row.addWidget(words, 1)
    body.addWidget(state)
    explain = QLabel(_("On Linux a cutter is a device file, and only the members of its group may send to it:"))
    explain.setWordWrap(True)
    body.addWidget(explain)
    card = widgets.Card()
    table = QGridLayout()
    table.setHorizontalSpacing(16)
    table.setVerticalSpacing(8)
    for r, (device, group) in enumerate(((_("USB printer (/dev/usb/lp0, as the VEVOR KI-375A)"), "lp"),
                                         (_("Serial port or USB-serial cable (/dev/ttyUSB0, /dev/ttyACM0)"),
                                          "dialout"))):
        d = QLabel(device)
        d.setWordWrap(True)
        g = QLabel(group)
        g.setObjectName("group_value")
        table.addWidget(d, r, 0)
        table.addWidget(g, r, 1, Qt.AlignRight)
    table.setColumnStretch(0, 1)
    card.body.addLayout(table)
    card.add_hint(_("On Arch and Manjaro: uucp instead of dialout."))
    body.addWidget(card)
    join = QLabel(_("Join the group once, in a terminal, then log out and in again:"))
    join.setWordWrap(True)
    body.addWidget(join)
    code = QFrame()
    code.setObjectName("code_box")
    crow = QHBoxLayout(code)
    crow.setContentsMargins(14, 10, 8, 10)
    commands = QLabel(COMMANDS.replace("\n", "<br>").replace("$", "&#36;"))
    commands.setTextFormat(Qt.RichText)
    commands.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
    commands.setTextInteractionFlags(Qt.TextSelectableByMouse)
    crow.addWidget(commands, 1)
    copy = QToolButton()
    copy.setIcon(icons.tabler("copy", theme.token("code_ink")))
    copy.setToolTip(_("Copy commands"))
    copy.setAccessibleName(_("Copy commands"))
    copy.setCursor(Qt.PointingHandCursor)
    copied = _muted(_("Copied. Paste them into a terminal."))
    copied.hide()

    def do_copy():
        QGuiApplication.clipboard().setText(COMMANDS)
        copied.show()
    copy.clicked.connect(do_copy)
    crow.addWidget(copy, 0, Qt.AlignVCenter)
    body.addWidget(code)
    body.addWidget(copied)
    body.addWidget(_muted(_("Vintyl checks the port you choose and says under it which group that device "
                            "needs.")))
    _close_footer(dlg, outer)
    dlg.state, dlg.copy_button = state, copy
    return _run(dlg, show)
