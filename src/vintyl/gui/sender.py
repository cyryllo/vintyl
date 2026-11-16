"""
Sending a job in a background thread, so the window stays responsive and
Stop can be pressed. All the work is vintyl.core.transport; this only
moves it off the window's thread and reports back with Qt signals.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import threading

from PySide6.QtCore import QThread, Signal

from vintyl.core import transport
from vintyl.gui import _


class SendWorker(QThread):
    progress = Signal(int, int)          # bytes sent, bytes in all
    finished_send = Signal(bool, str)    # ok, message for the user

    def __init__(self, text, profile, port, units_per_mm, parent=None):
        super().__init__(parent)
        self.text = text
        self.profile = profile
        self.port = port
        self.units_per_mm = units_per_mm
        self.stop_event = threading.Event()

    def request_stop(self):
        """Called from the window: stop at the next piece and lift the knife."""
        self.stop_event.set()

    def run(self):
        out = None
        try:
            out = transport.open_output(self.profile, self.port)
            sent = transport.send(self.text, out, self.profile,
                                  progress=lambda a, b: self.progress.emit(a, b),
                                  stop=self.stop_event, units_per_mm=self.units_per_mm)
            out.close()
            out = None
            self.finished_send.emit(True, _("Sent %d bytes to %s. The cutter cuts from its own memory "
                                            "at the speed set on its panel.") % (sent, self.port))
        except transport.SendStopped as e:
            self.finished_send.emit(False, _("Stopped after %d bytes; the knife was lifted. The cutter still "
                                             "cuts what it already has: press Test (pause) or Reset on its "
                                             "panel to stop it at once.") % e.args[0])
        except transport.TransportError as e:
            self.finished_send.emit(False, str(e))
        except Exception as e:                       # never leave the window waiting
            self.finished_send.emit(False, _("Sending failed: %s") % e)
        finally:
            if out is not None:
                try:
                    out.close()
                except Exception:
                    pass
