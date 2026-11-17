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

## Code from other programs

Each file with code from another program says so in its header, with the
source and the licence.

| From | What in Vintyl | Licence |
|---|---|---|
| [Kerfly](https://github.com/cyryllo/Kerfly) | drawing and editing: curves, shapes, nodes, snapping, offsets, fills, ready shapes, patterns, the sheet; the website's layout and style | GPL-3.0-or-later |
| [K40 Whisperer](https://www.scorchworks.com/K40whisperer/k40whisperer.html) by Scorch, through Kerfly | the DXF reader (`vintyl/core/dxf_reader.py`, unchanged) | GPL-3.0-or-later |

## Ideas and references (no code copied)

These programs were studied for how vinyl cutters are driven; Vintyl's code
for it is its own. Thanks to their authors.

- [Inkcut](https://github.com/inkcut/inkcut) (Jairus Martin and contributors):
  the blade offset and overcut, the HPGL and DMPL commands. Inkcut 2.1.8 is
  also the reference for some tests: `tools/inkcut_wzorzec.py` runs it in an
  environment of its own to record what it would send to a cutter; nothing of
  it is in Vintyl or its packages.
- CutScape (jetpax): its port of Inkcut's knife filters and the DMPL dialects.
- RedsailCut: notes on how Redsail cutters read pen-up moves.
- K40 Whisperer (Scorch), as kept in Kerfly: inside shapes cut first.
