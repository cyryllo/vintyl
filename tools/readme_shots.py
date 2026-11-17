"""
The README's screenshots, made again from the program itself:

    .venv/bin/python tools/readme_shots.py [docs/screenshots]

English, the light look, a 1400 x 860 window. It runs offscreen with its own
settings, cutter profiles and materials in a temporary folder, so it never
changes the user's own (~/.config/Vintyl). Nothing is sent to a cutter.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "docs", "screenshots"))

# before anything of Vintyl or Qt is loaded: offscreen, and settings of its own
TEMP = tempfile.mkdtemp(prefix="vintyl-shots-")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["VINTYL_SETTINGS"] = os.path.join(TEMP, "settings.ini")
os.environ["VINTYL_PROFILES"] = os.path.join(TEMP, "profiles")
os.environ["VINTYL_MATERIALS"] = os.path.join(TEMP, "materials")
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from vintyl import i18n  # noqa: E402

i18n.setup("en")

from PySide6.QtCore import QPoint, QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QPainter  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

app = QApplication([])

from vintyl.gui import theme  # noqa: E402

theme.apply(app, "light")

from vintyl.core import transport  # noqa: E402
from vintyl.gui.main_window import MainWindow  # noqa: E402

# the pictures show a cutter plugged in and usable, whatever is plugged into
# this computer now (only the window's state line; nothing is sent)
_exists = os.path.exists
os.path.exists = lambda path: True if str(path).startswith("/dev/") else _exists(path)
transport.access_problem = lambda port: None


def wait(ms=120):
    QTest.qWait(ms)


def until(cond, ms=8000):
    for _i in range(ms // 20):
        if cond():
            return
        QTest.qWait(20)


def save(image, name):
    path = os.path.join(OUT, name)
    image.save(path)
    print("saved", path, flush=True)


def with_dialog(win, dlg):
    """The window's picture with the dialog drawn over it where it stands."""
    shot = win.grab()
    p = QPainter(shot)
    p.drawPixmap(dlg.pos() - win.pos(), dlg.grab())
    p.end()
    return shot


def window(cutter="vevor-870"):
    win = MainWindow()
    win.resize(1400, 860)
    win.show()
    win.profile_box.setCurrentIndex(win.profile_box.findData(cutter))
    wait()
    return win


def ready(win, key, left, top, **values):
    e = win.insert_ready(key, values)
    e.move_to(left, top)
    win.refresh()
    return e


def main_window():
    win = window()
    win._on_drawn("ellipse", QRectF(-700, -470, 120, 120))
    ready(win, "star", -580, -470, points=5, size=90.0, inner=45.0)
    win._on_text_clicked(QPointF(-560, -170))
    win.opt_text.setText("Vintyl")
    win.opt_size.setValue(40.0)
    win._text_changed()
    heart = ready(win, "heart", -230, -200, width=200.0, height=175.0)
    win.selected, win.selection = heart, [heart]
    win.tile_selected({"motif": "star", "size": 8.0, "gap": 3.0, "margin": 3.0, "stagger": True})
    win.weed_frame.setChecked(True)
    star = [e for e in win.design.elements if e.name.startswith("Star")][0]
    win.view.select_many([star])
    win.selected, win.selection = star, [star]
    win._show_list()
    win._show_options()
    win.act_fit.trigger()
    wait(200)
    save(win.grab(), "main-window.png")
    return win


def pattern_of_shapes():
    win = window()
    win._on_drawn("rectangle", QRectF(-750, -300, 300, 180))
    win.settings.setValue("tile/motif", "heart")
    win.settings.setValue("tile/size", 14.0)
    win.settings.setValue("tile/gap", 4.0)
    win.settings.setValue("tile/margin", 5.0)
    dlg = win._ask_tile([win.selected], show=False)
    win._place_beside(dlg)
    dlg.show()
    until(lambda: not dlg.preview._pattern.isEmpty() and win.view._preview_item is not None)
    wait(200)
    save(with_dialog(win, dlg), "pattern-of-shapes.png")
    dlg.previewer.wait()
    dlg.close()


def pen_mode():
    win = window()
    win.tool_box.setCurrentIndex(win.tool_box.findData("pen"))
    win.material_box.setCurrentIndex(win.material_box.findData("paper"))
    win._on_drawn("ellipse", QRectF(-640, -360, 150, 150))
    win.fill_selected({"pattern": "lines", "spacing": 2.0, "angle": 45.0, "margin": 0.0})
    star = ready(win, "star", -450, -370, points=5, size=170.0, inner=45.0)
    win.selected, win.selection = star, [star]
    win.fill_selected({"pattern": "cross", "spacing": 4.0, "angle": 0.0, "margin": 0.0})
    heart = ready(win, "heart", -230, -330, width=170.0, height=148.0)
    win.selected, win.selection = heart, [heart]
    win.fill_selected({"pattern": "honeycomb", "spacing": 5.0, "angle": 0.0, "margin": 0.0})
    win.view.select_many([])
    win.selected, win.selection = None, []
    win._show_options()
    win.act_fit.trigger()
    wait(200)
    save(win.grab(), "pen-mode.png")


def dialog_shot(open_it, name, size=None):
    """A window that waits for a click: its picture (at `size`, or its own),
    then closed."""
    def fake_exec(dlg):
        if size:
            dlg.resize(*size)
        dlg.show()
        wait(150)
        save(dlg.grab(), name)
        dlg.close()
        return 0
    real = QDialog.exec
    QDialog.exec = fake_exec
    try:
        open_it()
    finally:
        QDialog.exec = real


def main():
    os.makedirs(OUT, exist_ok=True)
    win = main_window()
    pattern_of_shapes()
    pen_mode()
    dialog_shot(win.edit_profile, "cutter-settings.png", None)       # their own size, 1000 x 700
    dialog_shot(win.edit_material, "materials.png", None)
    # the check list before Start, shown by itself: Start is never pressed here
    from vintyl.gui import start_dialogs
    dlg = start_dialogs.confirm_start(win, win.profile.name, win.profile.port, False, win._material_name(),
                                      ("Set on the cutter's panel", "90 g", "300 mm/s"), True, False,
                                      "", show=False)
    dlg.show()
    wait(150)
    save(dlg.grab(), "check-list.png")
    dlg.close()
    os._exit(0)


if __name__ == "__main__":
    main()
