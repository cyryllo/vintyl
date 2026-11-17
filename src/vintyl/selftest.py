"""
Self-test:  vintyl --self-test   (also the AppImage: Vintyl-*.AppImage --self-test)

Checks that everything the program needs is there and works, without a
cutter and without opening a window on the screen: the libraries, the
cutter profiles, a job for each of them, the translations, the icons, the
fonts for text, and the window itself (offscreen). Used after building a
package, so a package with something missing is never released.

Prints one line per check and returns 0 when all passed.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import os
import sys
import tempfile
import traceback

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="30mm" viewBox="0 0 40 30">
  <rect x="5" y="5" width="20" height="20" fill="#000"/><circle cx="32" cy="15" r="5" fill="#000"/>
</svg>"""


def _checks():
    from vintyl import __version__

    def libraries():
        import pyclipper  # noqa: F401
        import segno  # noqa: F401
        import serial  # noqa: F401
        import svgelements  # noqa: F401
        from PySide6 import __version__ as qt
        return "PySide6 %s, pyserial, pyclipper, segno, svgelements" % qt

    def profiles():
        from vintyl.core import profile
        names = profile.builtin_names()
        for n in names:
            profile.load_builtin(n).validate()
        return ", ".join(names)

    def materials():
        # the built-in materials travel with the program (the AppImage too)
        from vintyl.core import material
        names = material.builtin_names()
        for n in names:
            material.load_builtin(n).validate()
        if not names:
            raise RuntimeError("no built-in materials")
        return ", ".join(names)

    def jobs():
        from vintyl.core import profile
        from vintyl.core.job import build_job
        square = [(10, 10), (30, 10), (30, 30), (10, 30), (10, 10)]
        out = []
        for n in profile.builtin_names():
            job = build_job([square], profile.load_builtin(n))
            if "PD" not in job.text and "D" not in job.text:
                raise RuntimeError("no cutting moves for %s" % n)
            out.append("%s %d bytes" % (n, len(job.text)))
        return "; ".join(out)

    def svg_file():
        from vintyl.core.loaders import load_svg
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(SVG)
            element = load_svg(path)
        n = len(element.paths)
        if not n:
            raise RuntimeError("nothing read from the SVG")
        return "%d shape(s)" % n

    def dxf_file():
        from vintyl.core.loaders import load_dxf
        dxf = "\n".join(["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
                         "0", "SECTION", "2", "ENTITIES",
                         "0", "CIRCLE", "8", "0", "10", "20", "20", "20", "30", "0", "40", "10",
                         "0", "ENDSEC", "0", "EOF"]) + "\n"
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.dxf")
            with open(path, "w", encoding="utf-8") as f:
                f.write(dxf)
            element = load_dxf(path)
        w, h = element.size
        if not (19.9 < w < 20.1 and 19.9 < h < 20.1):
            raise RuntimeError("a 20 mm circle came out %.2f x %.2f mm" % (w, h))
        return "a 20 mm circle"

    def offset_and_patterns():
        from vintyl.core import offset, shapes, tile
        from vintyl.core.design import Element
        ring = offset.offset_polygons([[(0, 0), (20, 0), (20, 20), (0, 20)]], 2.0)
        e = Element("t", shapes.rectangle(0, 0, 40, 30),
                    fill={"pattern": "honeycomb", "spacing": 3.0, "angle": 0.0, "margin": 0.0})
        _paths, n = tile.tile(shapes.rectangle(0, 0, 40, 30), tile.motif("star"), 5, 2)
        if not ring or not e.fill_lines() or not n:
            raise RuntimeError("offset, fill or pattern gave nothing")
        return "offset, fill, %d stars" % n

    def translations():
        import gettext
        from vintyl import i18n
        # read the catalogue directly: the language in use is not changed
        text = gettext.translation(i18n.DOMAIN, i18n.LOCALE_DIR, languages=["pl"], fallback=True).gettext("Cut")
        if text == "Cut":
            raise RuntimeError("the Polish catalogue was not found")
        return "pl: %s" % text

    def window():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from vintyl.gui import icons, text
        from vintyl.gui.main_window import MainWindow
        for name in ("pointer", "pencil", "rosette", "player-play"):
            if icons.tabler(name).isNull():
                raise RuntimeError("icon %s missing" % name)
        if icons.own("drag-knife").isNull() or icons.app_icon().isNull():
            raise RuntimeError("Vintyl's own icons missing")
        if not text.text_paths("Vintyl"):
            raise RuntimeError("no font could draw a text")
        win = MainWindow()
        win._on_drawn("rectangle", __import__("PySide6.QtCore", fromlist=["QRectF"]).QRectF(-60, -40, 20, 20))
        job = win.build()
        win.modified = False
        win.close()
        app.processEvents()
        return "window, icons, text; a drawn square: %.0f mm to cut" % job.cut_mm

    return [("Vintyl %s" % __version__, lambda: sys.version.split()[0]),
            ("libraries", libraries), ("cutter profiles", profiles), ("materials", materials),
            ("jobs", jobs),
            ("SVG", svg_file), ("DXF", dxf_file), ("offset and patterns", offset_and_patterns),
            ("translations", translations), ("window", window)]


def results(skip=()):
    """[(OK/FAIL, name, detail), ...] of the checks, without the ones named in skip."""
    out = []
    for name, check in _checks():
        if name in skip:
            continue
        try:
            out.append(("OK", name, check()))
        except Exception as e:
            out.append(("FAIL", name, str(e) or type(e).__name__))
    return out


def run(out=None):
    out = out or sys.stdout
    # the test never touches the user's own settings
    settings_dir = tempfile.mkdtemp(prefix="vintyl-selftest-")
    os.environ["VINTYL_SETTINGS"] = os.path.join(settings_dir, "settings.ini")
    print("Vintyl self-test\n", file=out, flush=True)
    failed = 0
    for name, check in _checks():
        try:
            detail = check()
            print("OK    %-22s %s" % (name, detail), file=out, flush=True)
        except Exception as e:
            failed += 1
            print("FAIL  %-22s %s" % (name, e), file=out, flush=True)
            traceback.print_exc(file=out)
    print("\n%s" % ("All checks passed." if not failed else "%d check(s) failed." % failed), file=out, flush=True)
    return 0 if not failed else 1
