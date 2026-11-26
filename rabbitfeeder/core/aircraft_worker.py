"""Background aircraft enrichment worker for RabbitFeeder."""

import re
import threading
from queue import Empty, Full, Queue

from PySide6.QtCore import QThread, Signal


class AircraftLookupWorker(QThread):
    """Process aircraft identification lookups outside the GUI thread."""

    MAX_QUEUE_SIZE = 500

    lookup_completed = Signal(str, object)
    lookup_failed = Signal(str, str)

    def __init__(self, lookup_service, parent=None):
        super().__init__(parent)

        self.lookup_service = lookup_service
        self._queue = Queue(maxsize=self.MAX_QUEUE_SIZE)
        self._lock = threading.Lock()
        self._active_icao = set()
        self._stopping = threading.Event()

    def enqueue(self, icao):
        """Queue an ICAO address unless duplicated or the queue is full."""
        icao = str(icao).strip().upper()

        if not re.fullmatch(r"[0-9A-F]{6}", icao):
            return False

        with self._lock:
            if self._stopping.is_set() or icao in self._active_icao:
                return False

            self._active_icao.add(icao)

            try:
                self._queue.put_nowait(icao)
            except Full:
                self._active_icao.discard(icao)
                return False

        return True

    def stop(self):
        """Request shutdown and wait for an active lookup to finish."""
        self._stopping.set()
        self.wait(12000)

    def run(self):
        """Process queued lookups sequentially."""
        while not self._stopping.is_set():
            try:
                icao = self._queue.get(timeout=0.25)
            except Empty:
                continue

            try:
                result = self.lookup_service.lookup(icao)
                self.lookup_completed.emit(icao, result)

            except Exception as error:
                self.lookup_failed.emit(icao, str(error))

            finally:
                with self._lock:
                    self._active_icao.discard(icao)

                self._queue.task_done()
