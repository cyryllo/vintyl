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

TOKENS = {
    "light": {"bar": "#eef0f3", "bar_border": "#c4c9d0", "update_bg": "#e3f2fd", "update_border": "#90caf9",
              "hint": "#4b5563", "caption": "#6b7280", "separator": "#c4c9d0", "ink": "#2b2f36",
              "muted": "#6b7280", "error": "#b91c1c", "ok": "#15803d"},
    "dark": {"bar": "#2b2f35", "bar_border": "#1b1e22", "update_bg": "#1d3a5c", "update_border": "#2f6aa8",
             "hint": "#b4bac3", "caption": "#9aa1ab", "separator": "#4a505a", "ink": "#d9dce1",
             "muted": "#9aa1ab", "error": "#ef5350", "ok": "#66bb6a"},
}

STYLE = Template("""
QToolBar#main_toolbar { spacing: 1px; padding: 2px; }
QToolBar#main_toolbar QToolButton { padding: 2px 3px; font-size: 11px; }
QLabel#ribbon_caption { color: $caption; font-size: 10px; padding-bottom: 1px; }
QFrame#ribbon_separator { color: $separator; margin: 4px 2px; }
QWidget#options_bar { background: $bar; border-bottom: 1px solid $bar_border; }
QFrame#update_bar { background: $update_bg; border-bottom: 1px solid $update_border; }
QLabel#node_hint { color: $hint; }
QLabel#muted { color: $muted; }
QPushButton#start:enabled { background: #be185d; color: white; font-weight: bold; }
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
    return STYLE.substitute(TOKENS[resolved or _current])


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
