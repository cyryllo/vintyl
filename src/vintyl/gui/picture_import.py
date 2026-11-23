"""
A picture (PNG, JPG...) opened as a pen drawing (vintyl.core.picture): the
window with the style (waves, spiral, hatching), its values and a live
preview, worked out in the background.

The picture is read once, laid on white (transparent parts are paper) and
kept grey and no bigger than MAX_SIDE; for each preview it is scaled to
about two pixels per line spacing, which averages its grain away.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from vintyl.core import picture
from vintyl.gui import _, ngettext, widgets
from vintyl.i18n import N_, decimal

MAX_SIDE = 1600                 # a bigger picture is made smaller first (the lines cannot use more)
MAX_COLUMNS = 700               # the grey picture's width at most, whatever the spacing
PICTURE_FILTER = "*.png *.jpg *.jpeg *.bmp *.gif *.webp"
EXTENSIONS = tuple(ext[1:] for ext in PICTURE_FILTER.split())
STYLE_NAMES = (("waves", N_("Waves")), ("spiral", N_("Spiral")), ("hatching", N_("Hatching")))


def load_image(path):
    """The picture as grey on white, at most MAX_SIDE px; None when it
    cannot be read."""
    img = QImage(path)
    if img.isNull():
        return None
    if max(img.width(), img.height()) > MAX_SIDE:
        img = img.scaled(MAX_SIDE, MAX_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    paper = QImage(img.size(), QImage.Format_RGB32)
    paper.fill(QColor("white"))
    p = QPainter(paper)
    p.drawImage(0, 0, img)
    p.end()
    return paper.convertToFormat(QImage.Format_Grayscale8)


def grey_of(img, width_mm, spacing):
    """The picture as vintyl.core.picture.Grey, about two pixels per line
    spacing across (no more than MAX_COLUMNS)."""
    cols = max(8, min(MAX_COLUMNS, int(2 * width_mm / max(spacing, 0.05))))
    rows = max(4, int(round(cols * img.height() / img.width())))
    small = img.scaled(cols, rows, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    data = bytes(small.constBits())
    line = small.bytesPerLine()
    return picture.Grey([[1.0 - b / 255.0 for b in data[y * line:y * line + cols]] for y in range(rows)])


def lines_of(img, values):
    """The polylines (mm) of the picture with the window's values."""
    grey = grey_of(img, values["width"], values["spacing"]).adjusted(
        values.get("contrast", 100.0) / 100.0, values.get("brightness", 0.0) / 100.0, values.get("invert", False))
    spacing = values["spacing"]
    kw = {"spacing": spacing}
    if values["style"] in ("waves", "spiral"):
        kw["amplitude"] = spacing / 2.0 * values.get("strength", 100.0) / 100.0
        kw["frequency"] = values.get("waves", 10.0) / 10.0            # per cm in the window, per mm here
        kw["skip_light"] = 0.04 if values.get("lift", False) else 0.0
        if values["style"] == "waves":
            kw["joined"] = values.get("joined", False)
    else:
        kw["angle"] = values.get("angle", 45.0)
    return picture.draw(values["style"], grey, values["width"], **kw)


def picture_dialog(win, img, show=True):
    """The window: style, size, spacing, the waves' strength and density
    (waves, spiral) or the angle (hatching), contrast, brightness, invert,
    lift the pen on white, one line (waves). Returns its values, or None
    (cancelled). show=False returns the window, not run (tests), with
    .values_now(), .preview, .previewer, .status, .style."""
    from vintyl.gui.main_window import _spin
    from vintyl.gui.widgets import Segmented, Switch
    from vintyl.gui.previewer import Previewer
    from vintyl.gui.previews import ShapePreview, polyline_path
    st = win.settings

    def num(key, default):
        try:
            return float(st.value("picture/" + key, default))
        except (TypeError, ValueError):
            return default
    style = Segmented()
    for code, label in STYLE_NAMES:
        style.addItem(_(label), code)
    style.setCurrentIndex(max(0, style.findData(str(st.value("picture/style", "waves")))))
    width = _spin(2000.0, 1, " mm", minimum=10.0)
    width.setValue(num("width", 150.0))
    spacing = _spin(20.0, 2, " mm", minimum=0.3)
    spacing.setSingleStep(0.1)
    spacing.setValue(num("spacing", 1.5))
    spacing.setToolTip(_("Distance between the lines (the spiral's turns). Smaller: more detail, longer "
                         "to draw; not less than the pen's width"))
    strength = _spin(200.0, 0, " %", minimum=0.0)
    strength.setSingleStep(10)
    strength.setValue(num("strength", 100.0))
    strength.setToolTip(_("How high the waves get where the picture is black (at 100 they fill the room "
                          "between two lines)"))
    waves = _spin(40.0, 1, "", minimum=1.0)
    waves.setValue(num("waves", 10.0))
    waves.setToolTip(_("Waves in one centimetre where the picture is black (fewer where it is lighter)"))
    angle = _spin(180.0, 1, "°", minimum=-180.0)
    angle.setValue(num("angle", 45.0))
    contrast = _spin(300.0, 0, " %", minimum=20.0)
    contrast.setSingleStep(10)
    contrast.setValue(num("contrast", 100.0))
    brightness = _spin(50.0, 0, " %", minimum=-50.0)
    brightness.setSingleStep(5)
    brightness.setValue(num("brightness", 0.0))
    invert = Switch(_("Invert: lines where the picture is light"))
    invert.setChecked(str(st.value("picture/invert", "false")) == "true")
    lift = Switch(_("Lift the pen where the picture is white"))
    lift.setChecked(str(st.value("picture/lift", "false")) == "true")
    joined = Switch(_("One line: the rows joined at the edges"))
    joined.setChecked(str(st.value("picture/joined", "false")) == "true")

    # the preview, bigger than the fill's: a picture needs it
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
    rows = [("style", None, style), ("width", _("Width"), width), ("spacing", _("Line spacing"), spacing),
            ("strength", _("Wave height"), strength), ("waves", _("Waves per cm"), waves),
            ("angle", _("Angle"), angle), ("contrast", _("Contrast"), contrast),
            ("brightness", _("Brightness"), brightness), ("invert", None, invert), ("lift", None, lift),
            ("joined", None, joined)]
    dlg = widgets.form_dialog(win, _("Picture as a drawing"), rows, action=_("Insert"), left=column,
                              hint=_("For the pen: drawn with the knife, it would cut the material to strips."),
                              show=False)

    def row_of(w):
        """What to hide for a field: a switch itself, a field its row (with the label)."""
        return w if isinstance(w, Switch) else w.parentWidget()

    def show_fields():
        s = style.currentData()
        for w, wanted in ((strength, s != "hatching"), (waves, s != "hatching"), (lift, s != "hatching"),
                          (angle, s == "hatching"), (joined, s == "waves")):
            row_of(w).setVisible(wanted)
        dlg.adjustSize()

    def values_now():
        return {"style": style.currentData(), "width": width.value(), "spacing": spacing.value(),
                "strength": strength.value(), "waves": waves.value(), "angle": angle.value(),
                "contrast": contrast.value(), "brightness": brightness.value(), "invert": invert.isChecked(),
                "lift": lift.isChecked(), "joined": joined.isChecked()}

    prev = Previewer(dlg)

    def ask_preview(*_a):
        values = values_now()
        prev.request(lambda: lines_of(img, values))

    def show_result(result):
        if isinstance(result, Exception):
            status.setText(_("Cannot work it out: %s") % result)
            return
        values = values_now()
        w, h = values["width"], values["width"] * img.height() / img.width()
        length = sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for p in result for a, b in zip(p, p[1:]))
        status.setText(_("%(w).0f × %(h).0f mm") % {"w": w, "h": h} + "  ·  "
                       + ngettext("%d line", "%d lines", len(result)) % len(result) + "  ·  "
                       + decimal(_("%.1f m to draw") % (length / 1000.0)))
        preview.set_paths(QPainterPath(), polyline_path(result))
    prev.ready.connect(show_result)
    prev.busy.connect(lambda b: b and status.setText(_("Working it out…")))
    style.currentIndexChanged.connect(lambda _i: (show_fields(), ask_preview()))
    for w in (width, spacing, strength, waves, angle, contrast, brightness):
        w.valueChanged.connect(ask_preview)
    for w in (invert, lift, joined):
        w.toggled.connect(ask_preview)
    show_fields()
    ask_preview()
    dlg.values_now, dlg.preview, dlg.previewer, dlg.status, dlg.style = values_now, preview, prev, status, style
    if not show:
        return dlg
    if not win._run_preview_dialog(dlg, prev):
        return None
    values = values_now()
    for k, v in values.items():
        st.setValue("picture/" + k, str(v).lower() if isinstance(v, bool) else v)
    return values
