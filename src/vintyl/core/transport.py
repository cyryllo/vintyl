"""
Sending a job to the cutter: a USB printer device (/dev/usb/lpN) or a
serial port (/dev/ttyUSB0, /dev/ttyACM0).

    out = open_output(profile, port)      # opens the device
    send(job.text, out, profile, progress, stop)
    out.close()                           # waits for the last packet first

What the cutter on the bench taught us (VEVOR KI-375A, 16.11.2026):
- a write to a USB printer only queues the transfer; closing the device
  right after it cancels the transfer still in flight and the end of the
  job is lost. close() therefore waits until the device has taken it.
- the cutter keeps the whole job in its own memory and cuts it at its own
  pace. Stop can only hold back what has not been sent yet; what the
  cutter already has is stopped with its Test (pause) or Reset key.
- the data are cut into pieces only at the end of a command (";"), so a
  stopped job never leaves half a command in the cutter (a half command
  would be glued to the start of the next job).

No GUI toolkit here; pyserial is imported only for a serial port.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import math
import os
import re
import select
import time

from ..i18n import _

STALL_S = 10.0            # the cutter takes nothing for this long: give up with a message
CONNECTIONS = ("usb-printer", "serial")


class TransportError(RuntimeError):
    """Sending failed; the message is safe to show the user."""


class SendStopped(Exception):
    """The user pressed Stop; holds how many bytes had gone out."""


# ---- outputs --------------------------------------------------------------------------

class UsbPrinterOutput:
    """A cutter that connects as a USB printer (Linux driver usblp)."""

    def __init__(self, path, stall_s=STALL_S):
        self.path = path
        self.stall_s = stall_s
        # OPENING THE DEVICE
        # non-blocking: a cutter that is offline (Leave) never makes the
        # program hang; after stall_s without progress we say what to check
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError:
            raise TransportError(access_problem(path) or _("No permission to use %s.") % path) from None
        except FileNotFoundError:
            raise TransportError(_("%s is not there. Is the cutter connected by USB and switched on?")
                                 % path) from None
        except OSError as e:
            raise TransportError(_("Cannot open %s: %s") % (path, e.strerror or e)) from None

    def _wait_writable(self):
        _r, w, _x = select.select([], [self.fd], [], self.stall_s)
        if not w:
            raise TransportError(_("The cutter has taken no data for %d s. Is it online (not Leave) "
                                   "and is there material in it?") % self.stall_s)

    def write(self, data):
        """Write all of data, waiting (up to stall_s at a time) for the cutter."""
        done = 0
        while done < len(data):
            self._wait_writable()
            try:
                done += os.write(self.fd, data[done:])
            except BlockingIOError:
                continue
            except OSError as e:
                raise TransportError(_("Writing to %s failed: %s") % (self.path, e.strerror or e)) from None

    def drain(self):
        """Wait until the cutter has taken the last transfer (see the module notes)."""
        self._wait_writable()

    def close(self):
        if self.fd is None:
            return
        try:
            self.drain()
        finally:
            os.close(self.fd)
            self.fd = None


class SerialOutput:
    """A cutter on a serial port (8N1); pyserial does the flow control."""

    def __init__(self, path, baud=9600, flow="none", stall_s=STALL_S):
        import serial
        self.path = path
        self._serial_mod = serial
        try:
            # serial_for_url also takes test ports such as loop://
            self.ser = serial.serial_for_url(path, baudrate=int(baud), bytesize=8, parity="N", stopbits=1,
                                             rtscts=(flow == "rtscts"), xonxoff=(flow == "xonxoff"),
                                             timeout=0.5, write_timeout=stall_s)
        except serial.SerialException as e:
            text = str(e)
            if "ermission" in text:
                raise TransportError(access_problem(path) or _("No permission to use %s.") % path) from None
            raise TransportError(_("Cannot open %s: %s") % (path, text)) from None

    def write(self, data):
        try:
            self.ser.write(data)
        except self._serial_mod.SerialTimeoutException:
            raise TransportError(_("The cutter has taken no data for %d s. Is it online (not Leave), "
                                   "and do the port's speed and flow control match its menu?")
                                 % self.ser.write_timeout) from None
        except self._serial_mod.SerialException as e:
            raise TransportError(_("Writing to %s failed: %s") % (self.path, e)) from None

    def drain(self):
        self.ser.flush()                  # waits until the operating system has sent everything

    def close(self):
        if self.ser is None:
            return
        try:
            self.drain()
        finally:
            self.ser.close()
            self.ser = None


def open_output(profile, port=None):
    """The output for this profile's connection; port overrides the profile's."""
    path = port or profile.port
    if not path:
        raise TransportError(_("No port is set. Choose the cutter's port in the panel."))
    if profile.connection == "usb-printer":
        return UsbPrinterOutput(path)
    return SerialOutput(path, profile.baud, profile.flow)


# ---- may this user use the port? ---------------------------------------------------------
# On Linux a cutter's device file belongs to a group: lp for a USB printer
# (/dev/usb/lp0), dialout for a serial port (/dev/ttyUSB0; uucp on Arch).
# Only that group's members may write to it, so the user joins it once:
#     sudo usermod -aG lp $USER        (or dialout, or what the device says)
# and logs out and in again: a running session keeps its old groups.

def access_problem(path):
    """None when this user may use the port (or it is not there: that is
    said when sending); else a message saying what to do, with the group
    the device really belongs to."""
    if not path or not os.path.exists(path) or os.access(path, os.R_OK | os.W_OK):
        return None
    try:
        import grp
        import pwd
        st = os.stat(path)
        gid = st.st_gid
        group = grp.getgrgid(gid)
    except (ImportError, KeyError, OSError):
        return _("No permission to use %s.") % path
    if st.st_mode & 0o060 != 0o060:                  # the group itself may not write: joining it does not help
        return _("No permission to use %s.") % path
    user = pwd.getpwuid(os.getuid()).pw_name
    if user in group.gr_mem or pwd.getpwuid(os.getuid()).pw_gid == gid:
        # in the group already, but this session started before that
        return (_("You are in the group %(group)s, but this session started before you joined it. "
                  "Log out and in again (or restart the computer) to use %(port)s.")
                % {"group": group.gr_name, "port": path})
    return (_("No permission to use %(port)s: it belongs to the group %(group)s. Join that group once "
              "(in a terminal):\n  sudo usermod -aG %(group)s $USER\nthen log out and in again.")
            % {"group": group.gr_name, "port": path})


# the control board of the VEVOR and Seiki cutters (checked on the KI-375A and the SK-870T)
KNOWN_BOARDS = {("0483", "5750"): "VEVOR / Seiki (XILI board)"}


def device_name(path):
    """What is behind a USB printer device, from Linux's sysfs: the known
    board's name ("VEVOR / Seiki (XILI board)"), else "maker product (vid:pid)";
    None when it cannot be told (not a USB printer, not Linux)."""
    name = os.path.basename(path or "")
    usb = os.path.join("/sys/class/usbmisc", name, "device", "..")
    try:
        vid = open(os.path.join(usb, "idVendor")).read().strip()
        pid = open(os.path.join(usb, "idProduct")).read().strip()
    except OSError:
        return None
    if (vid, pid) in KNOWN_BOARDS:
        return KNOWN_BOARDS[(vid, pid)]
    parts = []
    for f in ("manufacturer", "product"):
        try:
            parts.append(open(os.path.join(usb, f)).read().strip())
        except OSError:
            pass
    return "%s (%s:%s)" % (" ".join(p for p in parts if p) or "USB", vid, pid)


def find_ports():
    """Device files that may be a cutter: USB printers and serial ports."""
    import glob
    found = []
    for pattern in ("/dev/usb/lp*", "/dev/ttyUSB*", "/dev/ttyACM*"):
        found.extend(sorted(glob.glob(pattern)))
    return found


# ---- pieces and pacing ------------------------------------------------------------------

_MOVE = re.compile(r"^(PU|PD)(-?\d+),(-?\d+)$")


def pieces(text, size):
    """The job cut into pieces of at most `size` bytes, each ending at the end
    of a command (";", or the space that ends a DMPL command). A single command
    longer than size is one piece of its own."""
    out, cur = [], ""
    for m in re.finditer(r"[^; ]*[; ]|[^; ]+$", text):
        cmd = m.group(0)
        if cur and len(cur) + len(cmd) > size:
            out.append(cur)
            cur = ""
        cur += cmd
    if cur:
        out.append(cur)
    return out


def last_position(text, start=(0, 0)):
    """Where the knife is after these HPGL / DMPL moves (machine units)."""
    pos = start
    for cmd in re.split(r"[; ]+", text):
        m = _MOVE.match(cmd.strip()) or re.match(r"^([UD])(-?\d+),(-?\d+)$", cmd.strip())
        if m:
            pos = (int(m.group(2)), int(m.group(3)))
    return pos


def motion_seconds(piece, pos, speed_mm_s, units_per_mm):
    """(seconds the moves in this piece take at speed_mm_s, position after it)."""
    dist = 0.0
    for cmd in re.split(r"[; ]+", piece):
        m = _MOVE.match(cmd.strip()) or re.match(r"^([UD])(-?\d+),(-?\d+)$", cmd.strip())
        if m:
            p = (int(m.group(2)), int(m.group(3)))
            dist += math.dist(pos, p)
            pos = p
    return dist / units_per_mm / speed_mm_s, pos


# ---- sending ----------------------------------------------------------------------------

def send(text, output, profile, progress=None, stop=None, units_per_mm=None, sleep=time.sleep):
    """Send the job. progress(sent_bytes, total_bytes) after every piece;
    stop: a threading.Event; when it is set, sending stops at the next piece
    boundary and the knife is lifted where it stands (raises SendStopped).

    Pacing: with profile.pacing == "time" and the speed set on the cutter's
    panel (profile.speed_cm_s), the cutter is never given more than about
    lookahead_s of movement ahead, so Stop takes effect soon. Otherwise
    everything goes out as fast as the cutter takes it (it keeps the job in
    its own memory)."""
    data = text.encode("ascii")
    total = len(data)
    upm = units_per_mm or profile.units_per_mm
    speed = (profile.speed_cm_s or 0) * 10.0
    pace = profile.pacing == "time" and speed > 0
    sent = 0
    pos = (0, 0)
    ahead = 0.0                      # seconds of movement the cutter has queued (estimate)
    for piece in pieces(text, profile.chunk_bytes):
        if stop is not None and stop.is_set():
            _lift(output, profile, pos)
            raise SendStopped(sent)
        output.write(piece.encode("ascii"))
        sent += len(piece)
        if progress is not None:
            progress(sent, total)
        if pace:
            secs, pos = motion_seconds(piece, pos, speed, upm)
            ahead += secs
            if ahead > profile.lookahead_s:
                wait = ahead - profile.lookahead_s
                sleep(wait)
                ahead -= wait
        else:
            pos = last_position(piece, pos)
    output.drain()
    return sent


def _lift(output, profile, pos):
    """Stop: lift the knife where it stands. No travel home: the user stopped
    for a reason, the material may need attention."""
    x, y = pos
    if profile.language == "dmpl":
        output.write(("U%d,%d " % (x, y)).encode("ascii"))
    else:
        output.write(("PU%d,%d;" % (x, y)).encode("ascii"))
    output.drain()
