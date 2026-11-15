<p align="center"><img src="assets/logo/vintyl-logo-light.png" alt="Vintyl" width="560"></p>

# Vintyl

Software for vinyl cutters, for Linux first. Draw or open a design and cut
it on a drag-knife vinyl cutter over a serial (or USB-serial) port, in
HPGL or DMPL.

**Status: early development.** Works now: the window with the strip of
material, opening SVG files, drawing rectangles, ellipses and lines,
moving and resizing, choosing what is cut, cutter profiles, and saving the
cutter commands (HPGL / DMPL) to a file. Next: sending to a port, knife
offset, overcut, the knife path preview, and the rest of the drawing tools
from Kerfly. Nothing is sent to a cutter yet.

First cutters: Seiki SK-870T and VEVOR KI-375A (profiles still being
checked on the machines).

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[gui,dev]'
.venv/bin/python -m vintyl            # the window; add an .svg file to open it
.venv/bin/python -m pytest            # the tests (the window ones run offscreen)
```

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). Vintyl's drawing code will come
from [Kerfly](https://github.com/cyryllo/Kerfly) (same license). Ideas for
knife compensation and the cutter languages were studied in Inkcut,
CutScape and RedsailCut; see [docs/weryfikacja.md](docs/weryfikacja.md).
