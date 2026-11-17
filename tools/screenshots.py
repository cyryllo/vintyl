"""
The screenshots of the README and the website (docs/), made again from the
program itself:

    .venv/bin/python tools/screenshots.py          # English: docs/screenshots/
    .venv/bin/python tools/screenshots.py pl       # Polish:  docs/screenshots/pl/

The light look, a 1400 x 860 window. It runs offscreen with its own
settings, cutter profiles and materials in a temporary folder, so it never
changes the user's own (~/.config/Vintyl). Nothing is sent to a cutter:
Start is never pressed, and the windows before sending are only shown.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LANG = sys.argv[1] if len(sys.argv) > 1 else "en"
OUT = os.path.join(HERE, "..", "docs", "screenshots", *([] if LANG == "en" else [LANG]))

# before anything of Vintyl or Qt is loaded: offscreen, and settings of its own
TEMP = tempfile.mkdtemp(prefix="vintyl-shots-")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["VINTYL_SETTINGS"] = os.path.join(TEMP, "settings.ini")
os.environ["VINTYL_PROFILES"] = os.path.join(TEMP, "profiles")
os.environ["VINTYL_MATERIALS"] = os.path.join(TEMP, "materials")
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from vintyl import i18n  # noqa: E402

i18n.setup(LANG)

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
    star = ready(win, "star", -580, -470, points=5, size=90.0, inner=45.0)
    win._on_text_clicked(QPointF(-560, -170))
    win.opt_text.setText("Vintyl")
    win.opt_size.setValue(40.0)
    win._text_changed()
    heart = ready(win, "heart", -230, -200, width=200.0, height=175.0)
    win.selected, win.selection = heart, [heart]
    win.tile_selected({"motif": "star", "size": 8.0, "gap": 3.0, "margin": 3.0, "stagger": True})
    win.weed_frame.setChecked(True)
    win.view.select_many([star])
    win.selected, win.selection = star, [star]
    win._show_list()
    win._show_options()
    win.act_fit.trigger()
    wait(200)
    save(win.grab(), "main-window.png")
    # a tool set, beside its button
    pop = win.show_category("lines")
    wait(150)
    save(pop.grab(), "tool-set.png")
    pop.close()
    # the right-click menu on the element list
    lst = win.element_list
    pos = lst.visualItemRect(lst.item(1)).center()
    menu = win.list_context_menu(pos, show=False)
    menu.popup(lst.viewport().mapToGlobal(pos))
    wait(150)
    shot = win.grab()
    p = QPainter(shot)
    p.drawPixmap(menu.pos() - win.pos(), menu.grab())
    p.end()
    save(shot.copy(0, 100, 720, 600), "list-menu.png")
    menu.close()
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
    # the fill window, with its preview
    win.selected, win.selection = heart, [heart]
    dlg = win._ask_fill([heart], show=False)
    win._place_beside(dlg)
    dlg.show()
    until(lambda: not dlg.preview._pattern.isEmpty())
    wait(200)
    save(dlg.grab(), "fill.png")
    dlg.previewer.wait()
    dlg.close()


def knife_path():
    """The knife path on a plain design: the order of the cuts and the travels."""
    win = window()
    win.tool_box.setCurrentIndex(win.tool_box.findData("knife"))
    win.material_box.setCurrentIndex(win.material_box.findData("vinyl"))
    win._on_drawn("ellipse", QRectF(-560, -330, 120, 120))
    ready(win, "star", -400, -340, points=5, size=130.0, inner=45.0)
    win._on_text_clicked(QPointF(-520, -150))
    win.opt_text.setText("Vintyl")
    win.opt_size.setValue(50.0)
    win._text_changed()
    win.view.select_many([])
    win.selected, win.selection = None, []
    win._show_options()
    win.act_knife.setChecked(True)
    win.act_fit.trigger()
    wait(200)
    save(win.grab(), "knife-path.png")


def to_origin():
    """Two shapes far from the origin, then To 0,0 with the weeding frame."""
    win = window()
    win.tool_box.setCurrentIndex(win.tool_box.findData("knife"))
    win.material_box.setCurrentIndex(win.material_box.findData("vinyl"))
    win._on_drawn("ellipse", QRectF(-420, -330, 110, 80))
    win._on_drawn("rectangle", QRectF(-560, -420, 90, 90))
    win.weed_frame.setChecked(True)
    win.view.select_many([])
    win.selected, win.selection = None, []
    win._show_options()
    win.act_fit.trigger()
    wait(150)
    save(win.grab(), "to-origin-before.png")
    win.move_to_origin()
    wait(150)
    save(win.grab(), "to-origin-after.png")


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
    knife_path()
    to_origin()
    dialog_shot(win.edit_profile, "cutter-settings.png", None)       # their own size, 1000 x 700
    dialog_shot(win.edit_material, "materials.png", None)
    dialog_shot(lambda: win.show_shortcuts(), "shortcuts.png", (1180, 760))
    # the windows before sending, shown by themselves: Start is never pressed here
    from vintyl.core import weeding
    from vintyl.gui import start_dialogs
    from vintyl.gui import _
    m = win.material()
    note = _(m.note) if m is not None and m.note else ""        # a built-in material's note, as Start has it
    dlg = start_dialogs.confirm_start(win, win.profile.name, win.profile.port, False, win._material_name(),
                                      win.material_values(), not win.profile.send_speed_force, False, note,
                                      show=False, details=win.cut_details())
    dlg.show()
    wait(150)
    save(dlg.grab(), "check-list.png")
    dlg.close()
    dlg = start_dialogs.confirm_knife_test(win, win.profile.name, win.KNIFE_TEST_MM,
                                           weeding.knife_test(win.KNIFE_TEST_MM), win.material_values(),
                                           show=False, details=win.cut_details(pen=False))
    dlg.show()
    wait(150)
    save(dlg.grab(), "knife-test.png")
    dlg.close()
    os._exit(0)


if __name__ == "__main__":
    main()
