"""
Live preview worked out in the background: while the user changes a value
in a dialog (the fill's spacing, the pattern's size...), the result is
worked out in a thread, so the window does not freeze on a big honeycomb.

It starts a moment after the last change (a value being typed or spun is
not worked out at every step), only the newest request counts, and a
result that is already old when it arrives is dropped.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
from PySide6.QtCore import QObject, QThread, QTimer, Signal


class _Job(QThread):
    done = Signal(int, object)

    def __init__(self, token, func, parent=None):
        super().__init__(parent)
        self.token = token
        self.func = func

    def run(self):
        try:
            result = self.func()
        except Exception as e:                  # shown as "cannot", never a crash of the window
            result = e
        self.done.emit(self.token, result)


class Previewer(QObject):
    ready = Signal(object)        # the newest result (or the exception it raised)
    busy = Signal(bool)

    def __init__(self, parent=None, delay_ms=200):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._start)
        self._pending = None
        self._job = None
        self._token = 0
        self._jobs = []

    def request(self, func):
        """Work out func() in the background soon; replaces an earlier request."""
        self._pending = func
        self._timer.start()

    def _start(self):
        if self._job is not None and self._job.isRunning():
            return                               # started again when that one is done
        func, self._pending = self._pending, None
        if func is None:
            return
        self._token += 1
        job = _Job(self._token, func)
        job.done.connect(self._done)
        self._jobs = [j for j in self._jobs if j.isRunning()] + [job]
        self._job = job
        self.busy.emit(True)
        job.start()

    def _done(self, token, result):
        if self._pending is not None:            # something newer was asked meanwhile
            self._job = None
            self._start()
            return
        if token != self._token:
            return
        self._job = None
        self.busy.emit(False)
        self.ready.emit(result)

    def wait(self):
        """Drop what is still waiting and let the running threads finish
        (before the dialog closes)."""
        self._timer.stop()
        self._pending = None
        for j in self._jobs:
            j.wait()
        self._jobs = []
