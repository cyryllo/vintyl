"""
A picture (PNG, JPG...) traced into shapes to cut (vintyl.core.trace): its
dark areas become closed outlines, holes too. The window with the width,
threshold, invert, specks, detail and smooth curves, and a live preview.

Every value is in mm, so the preview (traced smaller, quickly) and the
result (traced at about PIXEL_MM a pixel) agree.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from PySide6.QtCore import Qt

from vintyl.core import trace
from vintyl.gui import _, ngettext, widgets

PIXEL_MM = 0.15                 # the picture is traced at about this size of a pixel (fine for a knife)
MAX_SIDE = 1600                 # and at most this many pixels across (the tracer is plain Python)
PREVIEW_SIDE = 450              # the preview: a smaller picture, quick


def lightness_rows(img, cols):
    """The grey picture (picture_import.load_image) at cols pixels across, as
    rows of lightness (bytes, 0 black .. 255 white), and mm per pixel is up
    to the caller."""
    rows_n = max(1, int(round(cols * img.height() / img.width())))
    small = img.scaled(cols, rows_n, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    data = bytes(small.constBits())
    line = small.bytesPerLine()
    return [data[y * line:y * line + cols] for y in range(rows_n)]


def shapes_of(img, values, preview=False):
    """The outlines (curves subpaths, mm, from the picture's top-left
    corner) of the picture traced with the window's values."""
    width = values["width"]
    cols = min(img.width(), MAX_SIDE, max(8, int(width / PIXEL_MM)))
    if preview:
        cols = min(cols, PREVIEW_SIDE)
    mm_px = width / cols
    rows = lightness_rows(img, cols)
    return trace.trace(rows, threshold=int(round(255 * values["threshold"] / 100.0)), invert=values["invert"],
                       specks=values["specks"] / (mm_px * mm_px), detail=values["detail"] / mm_px,
                       smooth=values["smooth"], mm_per_px=mm_px)


def trace_dialog(win, img, show=True):
    """The window: width, threshold, invert, specks, detail, smooth curves.
    Returns its values, or None (cancelled). show=False returns the window,
    not run (tests), with .values_now(), .preview, .previewer, .status."""
    from vintyl.gui.canvas import painter_path
    from vintyl.gui.main_window import _spin
    from vintyl.gui.previewer import Previewer
    from vintyl.gui.previews import ShapePreview
    from vintyl.gui.widgets import Switch
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
    st = win.settings

    def num(key, default):
        try:
            return float(st.value("trace/" + key, default))
        except (TypeError, ValueError):
            return default
    width = _spin(2000.0, 1, " mm", minimum=5.0)
    width.setValue(num("width", 100.0))
    threshold = _spin(99.0, 0, " %", minimum=1.0)
    threshold.setValue(num("threshold", 50.0))
    threshold.setToolTip(_("What counts as dark: higher takes in lighter greys too"))
    specks = _spin(500.0, 2, " mm²", minimum=0.0)
    specks.setValue(num("specks", 1.0))
    specks.setToolTip(_("Spots smaller than this are left out (too small to weed)"))
    detail = _spin(5.0, 2, " mm", minimum=0.05)
    detail.setSingleStep(0.05)
    detail.setValue(num("detail", 0.15))
    detail.setToolTip(_("How far the outline may stray from the picture's edge: smaller follows every "
                        "step of the pixels, larger gives calmer outlines"))
    invert = Switch(_("Invert: trace the light areas"))
    invert.setChecked(str(st.value("trace/invert", "false")) == "true")
    smooth = Switch(_("Smooth curves (sharp corners stay sharp)"))
    smooth.setChecked(str(st.value("trace/smooth", "true")) == "true")

    column = QWidget()
    lay = QVBoxLayout(column)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    preview = ShapePreview(300)
    status = QLabel()
    status.setObjectName("preview_caption")
    status.setAlignment(Qt.AlignCenter)
    status.setWordWrap(True)
    status.setFixedWidth(300)
    lay.addWidget(preview)
    lay.addWidget(status)
    rows = [("width", _("Width"), width), ("threshold", _("Threshold"), threshold),
            ("specks", _("Leave out specks under"), specks), ("detail", _("Detail"), detail),
            ("invert", None, invert), ("smooth", None, smooth)]
    dlg = widgets.form_dialog(win, _("Trace a picture"), rows, action=_("Insert"), left=column,
                              hint=_("The dark areas become shapes to cut, their holes too. The preview is "
                                     "traced smaller; the shapes are finer."), show=False)

    def values_now():
        return {"width": width.value(), "threshold": threshold.value(), "specks": specks.value(),
                "detail": detail.value(), "invert": invert.isChecked(), "smooth": smooth.isChecked()}

    prev = Previewer(dlg)

    def ask_preview(*_a):
        values = values_now()
        prev.request(lambda: shapes_of(img, values, preview=True))

    def show_result(result):
        if isinstance(result, Exception):
            status.setText(_("Cannot work it out: %s") % result)
            return
        values = values_now()
        w, h = values["width"], values["width"] * img.height() / img.width()
        status.setText(_("%(w).0f × %(h).0f mm") % {"w": w, "h": h} + "  ·  "
                       + ngettext("%d outline", "%d outlines", len(result)) % len(result))
        preview.set_paths(painter_path(result))
    prev.ready.connect(show_result)
    prev.busy.connect(lambda b: b and status.setText(_("Working it out…")))
    for w in (width, threshold, specks, detail):
        w.valueChanged.connect(ask_preview)
    for w in (invert, smooth):
        w.toggled.connect(ask_preview)
    ask_preview()
    dlg.values_now, dlg.preview, dlg.previewer, dlg.status = values_now, preview, prev, status
    if not show:
        return dlg
    if not win._run_preview_dialog(dlg, prev):
        return None
    values = values_now()
    for k, v in values.items():
        st.setValue("trace/" + k, str(v).lower() if isinstance(v, bool) else v)
    return values
