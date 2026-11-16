"""
Start the Vintyl window:  python -m vintyl [design.svg | drawing.dxf | project.vintyl ...]
Checks:                   python -m vintyl --self-test   (or --version)

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import sys

STYLE = """
QToolBar#main_toolbar { spacing: 1px; padding: 2px; }
QToolBar#main_toolbar QToolButton { padding: 2px 3px; font-size: 11px; }
QLabel#ribbon_caption { color: #6b7280; font-size: 10px; padding-bottom: 1px; }
QFrame#ribbon_separator { color: #c4c9d0; margin: 4px 2px; }
QWidget#options_bar { background: #eef0f3; border-bottom: 1px solid #c4c9d0; }
QPushButton#start:enabled { background: #be185d; color: white; font-weight: bold; }
QGroupBox { font-weight: bold; }
QGroupBox QLabel, QGroupBox QCheckBox { font-weight: normal; }
"""


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
    i18n.setup()                       # the system language, if Vintyl has it
    from vintyl.gui.main_window import MainWindow
    argv = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(argv)
    # Qt's own texts (standard buttons such as Close, Cancel) in the same language
    from PySide6.QtCore import QLibraryInfo, QTranslator
    qt_tr = QTranslator(app)
    if qt_tr.load("qtbase_" + i18n.current_language(), QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(qt_tr)
    app.setApplicationName("Vintyl")
    app.setStyleSheet(STYLE)
    win = MainWindow()
    for path in argv[1:]:
        if path.lower().endswith((".svg", ".dxf", ".vintyl")):
            win.open_file(path)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
