#!/usr/bin/env python3
"""
Wzorzec z Inkcuta: co Inkcut 2.1.8 wysłałby na ploter dla kwadratu 20x20 mm
(krok A5). Wynik trafia do tests/wzorce_inkcut/ i służy do porównania
z naszym generatorem.

CO ROBI: odtwarza Device.submit() z Inkcuta 2.1.8 krok po kroku:
init(job) -> process(model) -> protocol.move(...) -> finish(),
ale z TestTransport (bufor w pamięci) zamiast portu i bez czekania.
DLACZEGO TAK: w 2.1.8 submit() działa na pętli zdarzeń Twisted i czeka
między ruchami; nam potrzebne są tylko bajty, a nie ich tempo. Kolejność
i treść poleceń daje kod Inkcuta, nie nasz: wywołujemy jego własne funkcje.

Uruchamianie (Inkcut tylko w osobnym środowisku, nie w Vintyl):
    QT_QPA_PLATFORM=offscreen ~/ref-plotery/venv-inkcut/bin/python tools/inkcut_wzorzec.py

Uwaga: Inkcut przelicza HPGL i DMPL ze skalą 1021/90 na jednostkę SVG
(1021 jednostek na cal), a nie 1016 (40 na mm).
"""
import os
import sys

from enaml.qt.qt_application import QtApplication

from inkcut.device.plugin import Device, DeviceConfig, TestTransport
from inkcut.device.extensions import DeviceDriver
from inkcut.device.protocols.hpgl import HPGLProtocol
from inkcut.device.protocols.dmpl import DMPLProtocol, DMPLConfig
from inkcut.device.filters.blade_offset import BladeOffsetFilter, BladeOffsetConfig
from inkcut.device.filters.overcut import OvercutFilter, OvercutConfig
from inkcut.core.api import from_unit
from inkcut.core.workbench import InkcutWorkbench
from inkcut.job.models import Job

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "tests", "wzorce_inkcut")

# Kwadrat 20x20 mm, przesunięty od rogu strony o 10 mm. Inkcut i tak
# przesuwa projekt do punktu zerowego (auto_shift), więc wynik zaczyna się od 0.
SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="40mm" viewBox="0 0 40 40">
  <path d="M10 10 H30 V30 H10 Z" fill="none" stroke="#ff0000" stroke-width="0.1"/>
</svg>
"""


class _JobPluginDefaults:
    """Zaślepka wtyczki okna Inkcuta „inkcut.job”.

    DLACZEGO: Job.document przy wczytywaniu pliku pyta wtyczkę okna o dwa
    ustawienia DPI, a okna tu nie uruchamiamy. Wartości to domyślne
    z inkcut/job/plugin.py (2.1.8). Kwadrat ma wymiary w mm, więc DPI i tak
    nie zmienia wyniku.
    """
    dpi_default = 96.0
    dpi_auto_detect_inkscape = True

    def get_plugin(self, name):
        assert name == "inkcut.job", name
        return self


def run(name, protocol, filters=(), speed=None, force=None):
    """Jedno zadanie: zwraca bajty, które Inkcut wysłałby na port."""
    driver = DeviceDriver(manufacturer="SeikiTech", model="SK-870T", width="86cm",
                          protocols=["hpgl", "dmpl"], connections=["serial"])
    config = DeviceConfig()
    config.test_mode = True
    if speed is not None:          # Inkcut: prędkość w cm/s, wysyłana jako VS / V
        config.speed_units = "cm/s"
        config.speed = speed
        config.speed_enabled = True
    if force is not None:          # Inkcut: nacisk w gramach, FS / BP
        config.force = force
        config.force_enabled = True
    connection = TestTransport(protocol=protocol)
    device = Device(declaration=driver, config=config, connection=connection,
                    filters=list(filters))

    job = Job()
    job.document = os.path.join(OUT, "kwadrat_20mm.svg")
    job.info.auto_approve = True

    # --- to samo, co Device.submit() w 2.1.8, w tej samej kolejności ---
    model = device.init(job)
    connection.connect()                      # protocol.connection_made(): IN; / ;:HAEC1 ...
    if config.commands_before:
        connection.write(config.commands_before)
    if config.force_enabled:
        protocol.set_force(config.force)
    if config.speed_enabled:
        protocol.set_velocity(config.speed)
    for _d, cmd, args, kwargs in device.process(model):
        cmd(*args, **kwargs)                  # device.move -> protocol.move -> PU/PD
    device.finish()                           # HPGL: IN;
    if config.commands_after:
        connection.write(config.commands_after)
    connection.disconnect()

    data = connection.buffer.getvalue()
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(data)
    print("%-38s %4d B  %s" % (name, len(data), data[:160].decode("ascii", "replace")))
    return data


def blade(mm):
    return BladeOffsetFilter(config=BladeOffsetConfig(offset=from_unit(mm, "mm")))


def overcut(mm):
    return OvercutFilter(config=OvercutConfig(overcut=from_unit(mm, "mm")))


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "kwadrat_20mm.svg"), "w") as f:
        f.write(SVG)
    app = QtApplication()   # Inkcut liczy ścieżki na obiektach Qt (QPainterPath)
    InkcutWorkbench._instance = _JobPluginDefaults()

    run("hpgl_podstawowy.hpgl", HPGLProtocol())
    run("hpgl_vs20_fs80.hpgl", HPGLProtocol(), speed=20, force=80)
    run("hpgl_noz0.25_nadciecie0.5.hpgl", HPGLProtocol(), filters=[blade(0.25), overcut(0.5)])
    run("hpgl_nadciecie0.5.hpgl", HPGLProtocol(), filters=[overcut(0.5)])
    run("dmpl_tryb1.dmpl", DMPLProtocol(config=DMPLConfig(mode=1)))
    run("dmpl_tryb3.dmpl", DMPLProtocol(config=DMPLConfig(mode=3)))
    del app
    return 0


if __name__ == "__main__":
    sys.exit(main())
