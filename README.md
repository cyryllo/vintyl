<p align="center"><img src="assets/logo/vintyl-logo-light.png" alt="Vintyl" width="560"></p>

# Vintyl

Software for vinyl cutters, for Linux first. Draw or open a design and cut
it on a drag-knife vinyl cutter connected as a USB printer or over a
serial (or USB-serial) port, in HPGL or DMPL.

**Status: first test versions (pre-release).** Cuts from the window on a
VEVOR KI-375A (USB printer, HPGL); drawing, text, ready shapes, SVG files,
knife compensation, overcut, a weeding frame, a pen / pencil mode with fill
patterns, projects. See [CHANGELOG.md](CHANGELOG.md).

First cutters: VEVOR KI-375A (checked) and Seiki SK-870T (to be checked).

## Download

The AppImage from [Releases](https://github.com/cyryllo/vintyl/releases):
one file with everything inside. Make it executable and start it:

```bash
chmod +x Vintyl-*-x86_64.AppImage
./Vintyl-*-x86_64.AppImage
```

## Access to the cutter (Linux groups)

On Linux a cutter is a device file, and only the members of its group may
send to it. Join the group once, then log out and in again (a running
session keeps its old groups):

| The cutter connects as | Device | Group |
|---|---|---|
| a USB printer (VEVOR KI-375A) | `/dev/usb/lp0`, `/dev/usb/lp1`… | `lp` |
| a serial port or a USB-serial cable | `/dev/ttyUSB0`, `/dev/ttyACM0`… | `dialout` (Arch, Manjaro: `uucp`) |

```bash
sudo usermod -aG lp $USER
sudo usermod -aG dialout $USER
```

Vintyl checks the port you choose and says under it which group that
device needs (Help → Access to the cutter).

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[gui,dev]'
.venv/bin/python -m vintyl            # the window; add an .svg or .vintyl file to open it
.venv/bin/python -m vintyl --self-test
.venv/bin/python -m pytest            # the tests (the window ones run offscreen)
```

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). Vintyl's drawing code comes from
[Kerfly](https://github.com/cyryllo/Kerfly) (same license); the libraries
in the AppImage are listed in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Ideas for
knife compensation and the cutter languages were studied in Inkcut,
CutScape and RedsailCut; see [docs/weryfikacja.md](docs/weryfikacja.md).
