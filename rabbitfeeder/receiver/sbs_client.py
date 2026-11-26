import csv
import socket
import time

from PySide6.QtCore import QThread, Signal


def number(value):
    try:
        return float(value) if value.strip() else None
    except (ValueError, AttributeError):
        return None


class SBSClient(QThread):
    connection_changed = Signal(bool, str)
    aircraft_received = Signal(dict)
    message_count_changed = Signal(int)

    def __init__(self, host="127.0.0.1", port=31003, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.running = True
        self.message_count = 0

    def stop(self):
        self.running = False
        self.wait(3000)

    def run(self):
        while self.running:
            try:
                self.connection_changed.emit(
                    False, f"Connecting to {self.host}:{self.port}"
                )

                with socket.create_connection(
                    (self.host, self.port), timeout=5
                ) as sock:
                    sock.settimeout(1)
                    self.connection_changed.emit(True, "Connected to SBS decoder")
                    buffer = b""

                    while self.running:
                        try:
                            chunk = sock.recv(65536)
                            if not chunk:
                                raise ConnectionError("Decoder closed connection")
                            buffer += chunk

                            while b"\n" in buffer:
                                raw_line, buffer = buffer.split(b"\n", 1)
                                self.process_line(raw_line.decode(
                                    "utf-8", errors="replace"
                                ).strip())
                        except socket.timeout:
                            continue

            except (OSError, ConnectionError) as exc:
                self.connection_changed.emit(False, str(exc))
                for _ in range(20):
                    if not self.running:
                        break
                    time.sleep(0.25)

        self.connection_changed.emit(False, "Receiver stopped")

    def process_line(self, line):
        if not line.startswith("MSG,"):
            return

        try:
            fields = next(csv.reader([line]))
            if len(fields) < 22:
                return

            icao = fields[4].strip().upper()
            if not icao:
                return

            aircraft = {
                "icao": icao,
                "callsign": fields[10].strip(),
                "altitude": number(fields[11]),
                "speed": number(fields[12]),
                "track": number(fields[13]),
                "latitude": number(fields[14]),
                "longitude": number(fields[15]),
                "vertical_rate": number(fields[16]),
                "squawk": fields[17].strip(),
                "on_ground": fields[21].strip(),
            }

            self.message_count += 1
            self.aircraft_received.emit(aircraft)
            self.message_count_changed.emit(self.message_count)

        except (ValueError, IndexError, csv.Error):
            return
