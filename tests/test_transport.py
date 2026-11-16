"""
Tests of sending (plan step 2) without a cutter: a FIFO stands in for the
USB printer device (/dev/usb/lpN), pyserial's loop:// for a serial port.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import dataclasses
import os
import stat
import threading

import pytest

from vintyl.core import transport
from vintyl.core.job import build_job
from vintyl.core.profile import Profile

USB = Profile(width_mm=285, connection="usb-printer", chunk_bytes=64, pacing="none")


def square(x0, y0, side=20.0):
    return [(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side), (x0, y0)]


class FifoReader:
    """Reads everything written to a FIFO, in a thread (the stand-in cutter)."""

    def __init__(self, path):
        self.path = path
        self.data = b""
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        with open(self.path, "rb") as f:          # blocks until the sender opens it
            while True:
                chunk = f.read(4096)
                if not chunk:
                    return
                self.data += chunk

    def join(self):
        self.thread.join(5)
        return self.data


@pytest.fixture
def fifo(tmp_path):
    path = str(tmp_path / "lp0")
    os.mkfifo(path)
    return path


# ---- pieces ----------------------------------------------------------------------------

def test_pieces_end_at_a_command_and_join_back():
    text = build_job([square(10, 10), square(40, 10)], USB).text
    parts = transport.pieces(text, 64)
    assert "".join(parts) == text
    assert all(p.endswith(";") for p in parts)
    assert all(len(p) <= 64 for p in parts)


def test_pieces_of_dmpl_end_at_a_space():
    p = dataclasses.replace(USB, language="dmpl")
    text = build_job([square(10, 10)], p).text
    parts = transport.pieces(text, 20)
    assert "".join(parts) == text and all(x.endswith(" ") for x in parts)


def test_last_position():
    assert transport.last_position("IN;SP1;PU400,400;PD1200,400;PD1200,1200;") == (1200, 1200)
    assert transport.last_position(" ;:H A L0 U400,400 D800,40 ") == (800, 40)


# ---- USB printer -------------------------------------------------------------------------

def test_usb_printer_gets_exactly_the_job(fifo):
    job = build_job([square(10, 10), square(40, 10)], USB)
    reader = FifoReader(fifo)
    seen = []
    out = transport.open_output(USB, fifo)
    sent = transport.send(job.text, out, USB, progress=lambda a, b: seen.append((a, b)))
    out.close()
    assert sent == len(job.text)
    assert reader.join() == job.text.encode("ascii")
    assert seen[-1] == (len(job.text), len(job.text))
    assert len(seen) == len(transport.pieces(job.text, 64))


def test_stop_lifts_the_knife_where_it_stands(fifo):
    job = build_job([square(10, 10), square(40, 10)], USB)
    reader = FifoReader(fifo)
    stop = threading.Event()
    out = transport.open_output(USB, fifo)
    calls = []

    def progress(a, b):
        calls.append(a)
        if len(calls) == 2:
            stop.set()                         # Stop pressed after the second piece
    with pytest.raises(transport.SendStopped) as e:
        transport.send(job.text, out, USB, progress=progress, stop=stop)
    out.close()
    got = reader.join().decode("ascii")
    first_two = "".join(transport.pieces(job.text, 64)[:2])
    assert e.value.args[0] == len(first_two)
    x, y = transport.last_position(first_two)
    assert got == first_two + "PU%d,%d;" % (x, y)          # lifted in place, no travel home


def test_a_cutter_that_takes_nothing_gives_a_message_not_a_hang(fifo):
    # nobody reads the FIFO: it fills up, like a cutter that is offline
    out = transport.UsbPrinterOutput(fifo, stall_s=0.3)
    with pytest.raises(transport.TransportError, match="taken no data"):
        out.write(b"PU0,0;" * 50000)
    os.close(out.fd)
    out.fd = None


def test_missing_device_and_no_permission_say_what_to_do(tmp_path):
    with pytest.raises(transport.TransportError, match="not there"):
        transport.open_output(USB, str(tmp_path / "lp9"))
    locked = tmp_path / "lp1"
    locked.write_bytes(b"")
    os.chmod(locked, 0)
    if os.access(locked, os.W_OK):               # running as root: no permission check
        pytest.skip("root can open anything")
    with pytest.raises(transport.TransportError, match="group lp"):
        transport.open_output(USB, str(locked))
    os.chmod(locked, stat.S_IRUSR | stat.S_IWUSR)


def test_no_port_set():
    with pytest.raises(transport.TransportError, match="No port"):
        transport.open_output(USB, "")


# ---- serial ---------------------------------------------------------------------------

def test_serial_port_gets_exactly_the_job():
    p = dataclasses.replace(USB, connection="serial")
    job = build_job([square(10, 10)], p)
    out = transport.open_output(p, "loop://")
    transport.send(job.text, out, p)
    back = out.ser.read(len(job.text) + 10)
    out.close()
    assert back == job.text.encode("ascii")


# ---- pacing ----------------------------------------------------------------------------

def test_pacing_keeps_only_a_little_movement_ahead():
    """With the panel speed known, the sender waits so the cutter never has
    much more than lookahead_s of movement queued."""
    p = dataclasses.replace(USB, pacing="time", speed_cm_s=10.0, lookahead_s=0.5, chunk_bytes=16)
    job = build_job([[(0, 1), (100, 1)], [(100, 50), (0, 50)]], p)     # 300 mm of moves
    waits = []

    class Sink:
        def write(self, data):
            pass

        def drain(self):
            pass
    transport.send(job.text, Sink(), p, sleep=waits.append)
    moved_s = (job.cut_mm + job.travel_mm) / 100.0          # at 100 mm/s
    # everything but the last half second of movement is waited for, while sending
    assert sum(waits) == pytest.approx(moved_s - 0.5, abs=0.05)


def test_no_pacing_without_a_speed():
    p = dataclasses.replace(USB, pacing="time", speed_cm_s=None)
    waits = []

    class Sink:
        def write(self, data):
            pass

        def drain(self):
            pass
    transport.send(build_job([square(10, 10)], p).text, Sink(), p, sleep=waits.append)
    assert waits == []
