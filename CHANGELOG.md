# Changes

## 0.1.0a1 (pre-release)

The first test version, for Linux (an AppImage). Tested on a VEVOR KI-375A
(cuts from the window: an SVG heart, cut cleanly). Expect rough edges; please
report what goes wrong in the [issues](https://github.com/cyryllo/vintyl/issues).

**Cutting**
- Send to the cutter from the window: Start and Stop, a check list before
  cutting, progress. USB printer cutters (/dev/usb/lp…, such as the VEVOR
  KI-375A) and serial ports (/dev/ttyUSB…); HPGL and DMPL.
- Knife compensation at the corners only (smooth on curves), overcut,
  inside shapes cut first, a weeding frame round the design, the knife path
  shown on the sheet. Save the cutter file (.hpgl) without cutting.
- Pen / pencil mode: draws on paper, with the stroke on, outside or inside
  the line, and fill patterns (lines, cross-hatch, waves, honeycomb and more).
- Under the port, Vintyl says when the device needs a Linux group (lp or
  dialout) and how to join it.

**Drawing**
- The sheet as you see it from the front of the cutter, the cutting width
  across, growing upwards with the design.
- Rectangle, ellipse, polygon, line, polyline, pen with curves, freehand,
  text with the system's fonts, ready shapes (star, heart, gear, ring,
  arrow and more), QR codes; open SVG files.
- Move, resize with handles, rotate, mirror, align, distribute, group,
  union / difference / intersection / exclusion, offset (with "remove the
  holes"), a pattern of small shapes inside a shape, node editing, ruler,
  grid, snapping, undo, shortcuts.
- Projects (.vintyl). Polish and English.

Profiles: VEVOR KI-375A (checked on the machine) and Seiki SK-870T (to be
checked).
