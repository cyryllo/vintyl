<p align="center"><img src="assets/logo/vintyl-logo-light.png" alt="Vintyl" width="560"></p>

# Vintyl

Software for vinyl cutters, for Linux first. Draw or open a design and cut
it on a drag-knife vinyl cutter over a serial (or USB-serial) port, in
HPGL or DMPL.

**Status: early development.** The cutter core (profiles, HPGL / DMPL
output to a file) works and is tested; sending to a port, knife offset,
overcut and the window come next. Nothing is sent to a cutter yet.

First cutters: Seiki SK-870T and VEVOR KI-375A (profiles still being
checked on the machines).

## Run the tests

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
```

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). Vintyl's drawing code will come
from [Kerfly](https://github.com/cyryllo/Kerfly) (same license). Ideas for
knife compensation and the cutter languages were studied in Inkcut,
CutScape and RedsailCut; see [docs/weryfikacja.md](docs/weryfikacja.md).
