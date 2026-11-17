"""
Light and dark look of the window (Settings → Theme; applies after a restart,
like the language). The sheet itself stays light in both: it stands for the
vinyl, and the cut lines are drawn on it in their own colours.

Adapted from Kerfly (kerfly/gui/theme.py, commit cf48565): the same palette
and the idea of colour tokens in the style sheet; Vintyl's own widgets.

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from string import Template

from vintyl.i18n import N_

# (setting value, name shown in Settings)
THEMES = [("light", N_("Light")), ("dark", N_("Dark")), ("system", N_("As the system"))]
DEFAULT = "light"

# The colours of the window (UI v2, "Vintyl - projekt okna", page "Wersja 2").
# Light: as designed; dark: chosen from dark_palette() below so that text keeps
# a contrast of at least 4.5:1 (tests/test_widgets.py checks the pairs).
# The sheet stays light in both: it stands for the vinyl.
TOKENS = {
    "light": {
        "window": "#f4f5f7",          # dialog background
        "panel": "#ffffff",           # ribbon, left panel, tool strip, cards
        "bar": "#fafbfc",             # the selection bar
        "border": "#dfe2e7",          # lines between areas, card frames
        "field_border": "#cfd4dc",    # frames of fields and buttons
        "ink": "#1f2430",             # text and icons
        "ink_2": "#3b4352",           # field labels
        "muted": "#5b6472",           # hints, group captions
        "disabled_icon": "#a3aab5",
        "disabled_text": "#6b7480",
        "accent": "#be185d",          # Start, the main button, a switch that is on, cut lines
        "accent_soft": "#fce7f1",     # the chosen tool, the selected row, a button that is on
        "accent_ink": "#9d174d",
        "on_accent": "#ffffff",       # text on the accent (and on stop, danger)
        "well": "#eef0f3",            # behind a group of choice buttons
        "stat": "#f4f5f7",            # tiles with numbers
        "canvas": "#3d4350",          # round the sheet
        "sheet": "#f7f8fa",
        "selection": "#2563eb",
        "info_bg": "#eef2ff", "info_ink": "#1e3a8a",
        "warn_bg": "#fef3c7", "warn_ink": "#7c2d12",
        "ok": "#15803d", "ok_bg": "#dcfce7",
        "danger": "#b91c1c",
        "switch_off": "#8c95a3",
        "stop": "#1f2430",
        # older names, still used by some widgets
        "error": "#b91c1c", "hint": "#5b6472", "caption": "#5b6472", "separator": "#dfe2e7",
        "update_bg": "#eef2ff", "update_border": "#c7d2fe", "bar_border": "#dfe2e7",
    },
    "dark": {
        "window": "#26292e",
        "panel": "#30343a",
        "bar": "#2b2f34",
        "border": "#41464e",
        "field_border": "#555b66",
        "ink": "#e3e6ea",
        "ink_2": "#c9ced6",
        "muted": "#a7afba",
        "disabled_icon": "#636a75",
        "disabled_text": "#99a1ad",
        "accent": "#be185d",
        "accent_soft": "#4a1d33",
        "accent_ink": "#f9a8d4",
        "on_accent": "#ffffff",
        "well": "#24272b",
        "stat": "#26292e",
        "canvas": "#1f2227",
        "sheet": "#f7f8fa",
        "selection": "#2563eb",
        "info_bg": "#1e2a4a", "info_ink": "#c7d2fe",
        "warn_bg": "#422006", "warn_ink": "#fde68a",
        "ok": "#4ade80", "ok_bg": "#14361f",
        "danger": "#b91c1c",
        "switch_off": "#6b7280",
        "stop": "#4b5563",
        "error": "#f87171", "hint": "#a7afba", "caption": "#a7afba", "separator": "#41464e",
        "update_bg": "#1e2a4a", "update_border": "#2f6aa8", "bar_border": "#41464e",
    },
}

# Sizes (UI v2): fields 30 px high, rounded 6 px; buttons 36 px, rounded 8 px;
# cards rounded 8 px; Start 48 px. Main text 13 px, ribbon captions 11 px, hints 12 px.
STYLE = Template("""
QWidget { font-size: 13px; }
QDialog { background: $window; }
QToolBar#main_toolbar { background: $panel; border-bottom: 1px solid $border; spacing: 1px; padding: 2px; }
QToolBar#main_toolbar QToolButton { padding: 2px 4px; font-size: 11px; border: 0; border-radius: 6px; color: $ink; }
QToolBar#main_toolbar QToolButton[toolButtonStyle="2"] { font-size: 13px; }
QToolBar#main_toolbar QToolButton:hover { background: $well; }
QToolBar#main_toolbar QToolButton:checked { background: $accent_soft; color: $accent_ink; }
QToolBar#main_toolbar QToolButton:disabled { color: $disabled_text; }
QLabel#ribbon_caption { color: $muted; font-size: 11px; padding-bottom: 1px; }
QFrame#ribbon_separator { color: $border; margin: 4px 2px; }
QWidget#options_bar { background: $bar; border-bottom: 1px solid $border; }
QFrame#update_bar { background: $info_bg; border-bottom: 1px solid $update_border; }
QFrame#update_bar QLabel { color: $info_ink; }
QLabel#node_hint, QLabel#muted, QLabel#hint, QLabel#sel_hint { color: $muted; }
QLabel#sel_name { font-weight: 600; color: $ink; }
QLabel#bar_label { color: $muted; }
QFrame#bar_separator { color: $border; max-width: 1px; margin: 2px 4px; }
QToolButton#lock, QToolButton#toggle, QToolButton#bar_button {
    min-height: 28px; min-width: 28px; border: 1px solid $field_border; border-radius: 6px;
    background: $panel; color: $ink; padding: 0 6px; }
QToolButton#lock:checked, QToolButton#toggle:checked { background: $accent_soft; border-color: $accent;
    color: $accent_ink; }
QLabel#hint { font-size: 12px; }
QFrame#card { background: $panel; border: 1px solid $border; border-radius: 8px; }
QFrame#card QLabel { background: transparent; }
QLabel#card_title { font-weight: 600; color: $ink; }
QLabel#field_label { color: $ink_2; }
QFrame#footer { background: $panel; border-top: 1px solid $border; }
QLineEdit, QAbstractSpinBox, QComboBox {
    min-height: 28px; padding: 0 6px; border: 1px solid $field_border; border-radius: 6px;
    background: $panel; color: $ink; }
QComboBox::drop-down { border: 0; width: 22px; }
QComboBox::down-arrow { image: url($chevron); width: 12px; height: 12px; }
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { width: 0; border: 0; }
QPushButton { min-height: 34px; padding: 0 14px; border: 1px solid $field_border; border-radius: 8px;
    background: $panel; color: $ink; }
QPushButton:hover { border-color: $muted; }
QPushButton:disabled { color: $disabled_text; }
QPushButton#primary, QPushButton#start { background: $accent; color: $on_accent; border: 0; font-weight: 600; }
QPushButton#start { min-height: 46px; }
QPushButton#danger { background: $danger; color: $on_accent; border: 0; font-weight: 600; }
QPushButton#stop { background: $stop; color: $on_accent; border: 0; font-weight: 600; min-height: 46px; }
QPushButton#primary:disabled, QPushButton#start:disabled { background: $well; color: $disabled_text; }
QWidget#segmented { background: $well; border-radius: 8px; }
QWidget#segmented QToolButton { border: 1px solid transparent; border-radius: 6px; background: transparent;
    color: $ink_2; padding: 4px 10px; min-height: 22px; }
QWidget#segmented QToolButton:checked { background: $panel; border: 1px solid $accent; color: $accent_ink;
    font-weight: 600; }
QWidget#segmented QToolButton:focus { border: 1px dashed $accent; }
QWidget#job_panel { background: $panel; border-right: 1px solid $border; }
QFrame#panel_line { color: $border; max-height: 1px; border: 0; background: $border; }
QLabel#section_title { font-weight: 600; font-size: 14px; color: $ink; }
QLabel#cutter_state { color: $muted; }
QListWidget#element_list { background: transparent; border: 0; outline: 0; }
QListWidget#element_list::item:selected, QListWidget#element_list::item:hover { background: transparent; }
QFrame#warn { background: $warn_bg; border-radius: 8px; }
QFrame#warn QLabel { color: $warn_ink; }
QFrame#info { background: $info_bg; border-radius: 8px; }
QFrame#info QLabel { color: $info_ink; }
QFrame#stat { background: $stat; border-radius: 8px; }
QLabel#stat_title { color: $muted; font-size: 12px; }
QLabel#stat_value { color: $ink; font-size: 18px; font-weight: 700; }
QToolButton#square { min-height: 28px; min-width: 28px; border: 1px solid $field_border; border-radius: 6px;
    background: $panel; }
QProgressBar { border: 0; border-radius: 4px; background: $well; }
QProgressBar::chunk { border-radius: 4px; background: $accent; }
QWidget#tool_panel { background: $panel; border-left: 1px solid $border; }
QToolButton#tool_tile { border: 0; border-radius: 8px; font-size: 11px; color: $ink; padding-top: 4px; }
QToolButton#tool_tile:hover { background: $well; }
QToolButton#tool_tile:checked { background: $accent_soft; color: $accent_ink; font-weight: 600; }
QFrame#tool_popup { background: $panel; border: 1px solid $border; border-radius: 10px; }
QStatusBar { background: $panel; border-top: 1px solid $border; color: $muted; }
QStatusBar QLabel { color: $muted; padding: 0 8px; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: $field_border; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QFrame#zoom_box { background: rgba(31, 36, 48, 215); border-radius: 8px; }
QFrame#zoom_box QToolButton { color: #ffffff; border: 0; padding: 2px 6px; min-height: 26px; }
QToolButton#zoom_label { min-width: 48px; font-weight: 600; }
QMenu { background: $panel; border: 1px solid $border; border-radius: 8px; padding: 6px; color: $ink; }
QMenu::item { padding: 6px 28px 6px 10px; border-radius: 6px; }
QMenu::item:selected { background: $accent_soft; color: $accent_ink; }
QMenu::item:disabled { color: $disabled_text; }
QMenu::separator { height: 1px; background: $border; margin: 4px 6px; }
QMenu::icon { padding-left: 8px; }
QGroupBox { font-weight: bold; }
QGroupBox QLabel, QGroupBox QCheckBox { font-weight: normal; }
""")

_current = DEFAULT


def system_is_dark():
    """The desktop's colour scheme (Qt 6.5+: GNOME, KDE, ...)."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        return False


def resolve(name):
    """'light' or 'dark' for a setting value."""
    if name == "system":
        return "dark" if system_is_dark() else "light"
    return name if name in TOKENS else DEFAULT


def current():
    return _current


def token(key):
    """A colour of the theme in use, for widgets coloured in code."""
    return TOKENS[_current][key]


def style_sheet(resolved=None):
    import os
    look = resolved or _current
    # the drop-down arrow is a file (style sheets take images by path), one per look
    chevron = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "chevron-down-%s.svg" % look)
    return STYLE.substitute(TOKENS[look], chevron=chevron.replace("\\", "/"))


def dark_palette():
    from PySide6.QtGui import QColor, QPalette
    pal = QPalette()
    colors = {
        QPalette.Window: "#30343a", QPalette.WindowText: "#e3e6ea", QPalette.Base: "#24272b",
        QPalette.AlternateBase: "#2b2f34", QPalette.ToolTipBase: "#3a3f46", QPalette.ToolTipText: "#e3e6ea",
        QPalette.PlaceholderText: "#8a9099", QPalette.Text: "#e3e6ea", QPalette.Button: "#383d44",
        QPalette.ButtonText: "#e3e6ea", QPalette.BrightText: "#ff6e6e", QPalette.Link: "#64b5f6",
        QPalette.LinkVisited: "#b39ddb", QPalette.Highlight: "#2f6aa8", QPalette.HighlightedText: "#ffffff",
        QPalette.Light: "#4a5058", QPalette.Midlight: "#40454c", QPalette.Mid: "#2a2d32",
        QPalette.Dark: "#1e2024", QPalette.Shadow: "#141518",
    }
    for role, color in colors.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        pal.setColor(QPalette.Disabled, role, QColor("#7a8089"))
    pal.setColor(QPalette.Disabled, QPalette.Base, QColor("#2a2d31"))
    pal.setColor(QPalette.Disabled, QPalette.Button, QColor("#33373d"))
    return pal


def apply(app, name):
    """Fusion style with the light or dark palette, the style sheet and the
    icons' colour. Call before the window is built (icons are drawn then)."""
    global _current
    from vintyl.gui import icons
    _current = resolve(name)
    app.setStyle("Fusion")
    app.setPalette(dark_palette() if _current == "dark" else app.style().standardPalette())
    icons.set_ink(TOKENS[_current]["ink"])
    app.setStyleSheet(style_sheet())
    return _current
