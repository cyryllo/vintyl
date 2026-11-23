"""
Start the Vintyl window:  python -m vintyl [design.svg | drawing.dxf | project.vintyl | photo.jpg ...]
Checks:                   python -m vintyl --self-test   (or --version)

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import sys


def _style():
    from vintyl.gui import theme
    return theme.style_sheet("light")


def __getattr__(name):  # STYLE kept for scripts that set it on their own QApplication
    if name == "STYLE":
        return _style()
    raise AttributeError(name)


def main(argv=None):
    if "--self-test" in (sys.argv if argv is None else argv):
        from vintyl import selftest              # checks without a cutter and without a window on screen
        return selftest.run()
    if "--version" in (sys.argv if argv is None else argv):
        from vintyl import __version__
        print("Vintyl", __version__)
        return 0
    from PySide6.QtWidgets import QApplication
    from vintyl import i18n
    from vintyl.gui.main_window import open_settings
    settings = open_settings()
    # the language chosen in Settings ("" = the system's), then the window's texts
    i18n.setup(str(settings.value("view/language", "")))
    from vintyl.gui.main_window import MainWindow
    from vintyl.gui import theme
    argv = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(argv)
    theme.apply(app, str(settings.value("view/theme", theme.DEFAULT)))
    # Qt's own texts (standard buttons such as Close, Cancel) in the same language
    from PySide6.QtCore import QLibraryInfo, QTranslator
    qt_tr = QTranslator(app)
    if qt_tr.load("qtbase_" + i18n.current_language(), QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(qt_tr)
    app.setApplicationName("Vintyl")
    win = MainWindow()
    win.show()
    # the files given, once the window is up: an SVG of colours and a picture open a
    # window of their own, placed beside this one
    from PySide6.QtCore import QTimer
    from vintyl.gui.picture_import import EXTENSIONS
    files = [p for p in argv[1:] if p.lower().endswith((".svg", ".dxf", ".vintyl") + EXTENSIONS)]
    QTimer.singleShot(0, lambda: [win.open_file(p) for p in files])
    # the log for bug reports; a new version (at most once a day, in the background);
    # the AppImage asks once to be put into the applications menu
    from vintyl import __version__
    from vintyl.core import diag
    diag.setup(__version__)
    win.check_for_updates(auto=True)
    QTimer.singleShot(800, lambda: win.install_menu_entry(ask=True))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
