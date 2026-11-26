from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QDialog, QFormLayout,
    QDoubleSpinBox, QSpinBox, QComboBox, QDialogButtonBox
)

from rabbitfeeder.core.aircraft_database import AircraftDatabase
from rabbitfeeder.core.aircraft_lookup import AircraftLookupService
from rabbitfeeder.core.aircraft_worker import AircraftLookupWorker
from rabbitfeeder.receiver.sbs_client import SBSClient
from rabbitfeeder.ui.map_widget import MapWidget, load_settings


class MapSettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RabbitFeeder | Map Settings")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.theme = QComboBox()
        self.theme.addItem("Light", "light")
        self.theme.addItem("Dark", "dark")

        current_theme = settings.get("theme", "light")
        index = self.theme.findData(current_theme)
        self.theme.setCurrentIndex(index if index >= 0 else 0)

        self.latitude = QDoubleSpinBox()
        self.latitude.setRange(-90, 90)
        self.latitude.setDecimals(6)
        self.latitude.setValue(float(settings["latitude"]))

        self.longitude = QDoubleSpinBox()
        self.longitude.setRange(-180, 180)
        self.longitude.setDecimals(6)
        self.longitude.setValue(float(settings["longitude"]))

        self.zoom = QSpinBox()
        self.zoom.setRange(1, 21)
        self.zoom.setValue(int(settings["zoom"]))

        form.addRow("Map appearance:", self.theme)
        form.addRow("Centre latitude:", self.latitude)
        form.addRow("Centre longitude:", self.longitude)
        form.addRow("Initial zoom:", self.zoom)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        return {
            "latitude": self.latitude.value(),
            "longitude": self.longitude.value(),
            "zoom": self.zoom.value(),
            "theme": self.theme.currentData()
        }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("RabbitFeeder | Aviation Feeder Manager")
        self.resize(1450, 1000)

        self.aircraft_rows = {}
        self.latest_aircraft = {}
        self.lookup_requested = set()

        self.aircraft_database = AircraftDatabase()
        self.lookup_service = AircraftLookupService(
            self.aircraft_database
        )
        self.lookup_worker = AircraftLookupWorker(
            self.lookup_service, self
        )

        self.lookup_worker.lookup_completed.connect(
            self.update_aircraft_enrichment
        )
        self.lookup_worker.lookup_failed.connect(
            self.aircraft_lookup_failed
        )
        self.lookup_worker.start()

        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()

        title = QLabel("RABBITFEEDER")
        title.setObjectName("title")

        subtitle = QLabel("MASTER AVIATION FEEDER CONTROL")
        subtitle.setObjectName("subtitle")

        header.addWidget(title)
        header.addSpacing(18)
        header.addWidget(subtitle)
        header.addStretch()

        self.settings_button = QPushButton("MAP SETTINGS")
        self.settings_button.clicked.connect(self.open_map_settings)
        header.addWidget(self.settings_button)

        self.connection_label = QLabel("● CONNECTING")
        self.connection_label.setObjectName("status_bad")
        header.addWidget(self.connection_label)

        layout.addLayout(header)

        # Metric cards
        cards = QHBoxLayout()

        self.aircraft_value = self.make_card(
            cards, "AIRCRAFT TRACKED", "0"
        )
        self.messages_value = self.make_card(
            cards, "MESSAGES RECEIVED", "0"
        )
        self.receiver_value = self.make_card(
            cards, "RECEIVER", "STARTING"
        )

        layout.addLayout(cards)

        # Map
        map_header = QHBoxLayout()
        map_title = QLabel("LIVE AVIATION MAP")
        map_title.setObjectName("section")
        map_header.addWidget(map_title)
        map_header.addStretch()

        self.map_location_label = QLabel("RECEIVER LOCATION")
        self.map_location_label.setObjectName("footer")
        map_header.addWidget(self.map_location_label)

        layout.addLayout(map_header)

        self.map_widget = MapWidget()
        layout.addWidget(self.map_widget, 3)

        # Aircraft table
        section = QLabel("LIVE AIRCRAFT DATA")
        section.setObjectName("section")
        layout.addWidget(section)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "ICAO", "CALLSIGN", "ALTITUDE (ft)", "SPEED (kt)",
            "HEADING", "LATITUDE", "LONGITUDE",
            "VERTICAL (ft/min)", "SQUAWK"
        ])

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        layout.addWidget(self.table, 2)

        footer = QLabel(
            "DATA SOURCE: 127.0.0.1:31003 | FORMAT: SBS / BASESTATION"
        )
        footer.setObjectName("footer")
        layout.addWidget(footer)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #101820;
                color: #e5edf5;
                font-family: Sans Serif;
                font-size: 12px;
            }
            QLabel#title {
                color: #ffffff;
                font-size: 25px;
                font-weight: bold;
                letter-spacing: 2px;
            }
            QLabel#subtitle, QLabel#footer {
                color: #8da3b8;
                font-size: 10px;
            }
            QLabel#section {
                color: #72c7e8;
                font-size: 14px;
                font-weight: bold;
                padding-top: 5px;
            }
            QLabel#status_bad {
                color: #f0b45b;
                font-weight: bold;
                padding: 9px;
                background: #30291e;
                border-radius: 6px;
            }
            QLabel#status_good {
                color: #6ee7a0;
                font-weight: bold;
                padding: 9px;
                background: #183326;
                border-radius: 6px;
            }
            QFrame#metric {
                background: #1a2937;
                border: 1px solid #2a4053;
                border-radius: 9px;
                min-height: 75px;
            }
            QLabel#metric_name {
                color: #91a9bd;
                font-size: 10px;
                font-weight: bold;
            }
            QLabel#metric_value {
                color: #ffffff;
                font-size: 25px;
                font-weight: bold;
            }
            QTableWidget {
                background: #172431;
                alternate-background-color: #1b2b3a;
                gridline-color: #293d50;
                border: 1px solid #293d50;
                border-radius: 7px;
                selection-background-color: #24516c;
            }
            QHeaderView::section {
                background: #22384a;
                color: #a9c6dc;
                border: none;
                padding: 8px 5px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton {
                background: #24516c;
                color: white;
                border: 1px solid #397493;
                border-radius: 5px;
                padding: 9px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #306b8e;
            }
            QDialog {
                background: #172431;
                color: #e5edf5;
            }
            QLineEdit, QDoubleSpinBox, QSpinBox {
                background: #101820;
                color: white;
                border: 1px solid #39536a;
                padding: 7px;
                border-radius: 4px;
            }
        """)

        self.client = SBSClient()
        self.client.connection_changed.connect(self.update_connection)
        self.client.aircraft_received.connect(self.update_aircraft)
        self.client.message_count_changed.connect(
            lambda count: self.messages_value.setText(f"{count:,}")
        )

        self.client.start()

    def make_card(self, layout, name, value):
        frame = QFrame()
        frame.setObjectName("metric")

        box = QVBoxLayout(frame)
        box.setContentsMargins(16, 10, 16, 10)

        heading = QLabel(name)
        heading.setObjectName("metric_name")

        number = QLabel(value)
        number.setObjectName("metric_value")

        box.addWidget(heading)
        box.addWidget(number)
        layout.addWidget(frame)

        return number

    @staticmethod
    def display(value, decimals=2):
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:,.{decimals}f}"
        return str(value)

    def open_map_settings(self):
        current = load_settings()

        dialog = MapSettingsDialog(current, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()

            self.map_widget.apply_settings(settings)

            self.map_location_label.setText(
                f"CENTRE: {settings['latitude']:.4f}, "
                f"{settings['longitude']:.4f}"
            )

            # Refresh markers after the map reloads.
            self.map_widget.update_aircraft(
                list(self.latest_aircraft.values())
            )

    def update_connection(self, connected, message):
        self.connection_label.setText(
            "● CONNECTED" if connected else "● DISCONNECTED"
        )

        self.connection_label.setObjectName(
            "status_good" if connected else "status_bad"
        )

        self.receiver_value.setText(
            "ONLINE" if connected else "OFFLINE"
        )

        self.connection_label.style().unpolish(
            self.connection_label
        )
        self.connection_label.style().polish(
            self.connection_label
        )

        self.statusBar().showMessage(message)

    def update_aircraft(self, aircraft):
        icao = aircraft["icao"]

        previous = self.latest_aircraft.get(icao, {})
        combined = previous.copy()

        # Keep previous valid position when an SBS message
        # contains no new position.
        combined.update({
            key: value for key, value in aircraft.items()
            if value is not None
        })

        self.latest_aircraft[icao] = combined

        # Request identification once per aircraft during this session.
        if icao not in self.lookup_requested:
            if self.lookup_worker.enqueue(icao):
                self.lookup_requested.add(icao)

        if icao not in self.aircraft_rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.aircraft_rows[icao] = row

        row = self.aircraft_rows[icao]

        values = [
            combined.get("icao", ""),
            combined.get("callsign") or "—",
            self.display(combined.get("altitude"), 0),
            self.display(combined.get("speed"), 1),
            self.display(combined.get("track"), 1),
            self.display(combined.get("latitude"), 5),
            self.display(combined.get("longitude"), 5),
            self.display(combined.get("vertical_rate"), 0),
            combined.get("squawk") or "—",
        ]

        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, column, item)

        self.aircraft_value.setText(str(self.table.rowCount()))

        self.map_widget.update_aircraft(
            list(self.latest_aircraft.values())
        )

    def update_aircraft_enrichment(self, icao, result):
        """Merge identification data without replacing live telemetry."""
        if not result:
            return

        aircraft = self.latest_aircraft.get(icao)

        if aircraft is None:
            return

        identification_fields = (
            "registration",
            "manufacturer",
            "model",
            "icao_type",
            "operator",
            "registered_owner",
            "operator_flag_code",
            "images",
            "country",
            "serial_number",
            "category",
            "source",
        )

        for field in identification_fields:
            value = result.get(field)

            if value is not None and value != "":
                aircraft[field] = value

        # Refresh the existing row and map using the latest telemetry.
        self.update_aircraft(aircraft)

        self.statusBar().showMessage(
            f"Aircraft identification updated: {icao}", 5000
        )

    def aircraft_lookup_failed(self, icao, message):
        """Report a lookup failure without interrupting live tracking."""
        self.statusBar().showMessage(
            f"Aircraft lookup failed for {icao}: {message}", 8000
        )

    def closeEvent(self, event):
        self.client.stop()
        self.lookup_worker.stop()
        event.accept()
