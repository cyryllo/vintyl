# Third-party software in Vintyl

Vintyl is GPL-3.0-or-later (see [LICENSE](LICENSE)). Its packages (the
AppImage) also contain the libraries below, each under its own licence. The
licence texts travel with each library in the package (its `*.dist-info`
folder); Qt's LGPL-3.0 text is in `licenses/LGPL-3.0.txt`. The licences
listed are those the libraries' own package data state.

| Part | What it does in Vintyl | Licence |
|---|---|---|
| Python | the language the program runs in | PSF License |
| Qt 6 with PySide6 and shiboken6 | the window | LGPL-3.0-only (or GPL-2.0 / GPL-3.0) |
| pyserial | sending to a cutter on a serial port | BSD |
| pyclipper | offsets, holes and concentric fills | MIT |
| segno | QR codes | BSD |
| svgelements | opening SVG files | MIT |
| Tabler Icons | the toolbar icons (`vintyl/gui/icons/tabler`) | MIT |

Code adapted from [Kerfly](https://github.com/cyryllo/Kerfly) (GPL-3.0-or-later)
is marked in the header of each file it is in.
