import json
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.json"

DEFAULT_SETTINGS = {
    "latitude": 0.0,
    "longitude": 0.0,
    "zoom": 8,
    "theme": "light"
}


def load_settings():
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if SETTINGS_FILE.exists():
        try:
            settings = json.loads(
                SETTINGS_FILE.read_text(encoding="utf-8")
            )
            return {**DEFAULT_SETTINGS, **settings}
        except (OSError, json.JSONDecodeError):
            pass

    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    SETTINGS_FILE.write_text(
        json.dumps(settings, indent=4),
        encoding="utf-8"
    )

    SETTINGS_FILE.chmod(0o600)


class MapWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.settings = load_settings()
        self.latest_aircraft = []

        self.web = QWebEngineView(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)

        self.web.setMinimumHeight(360)
        self.load_map()

    def load_map(self):
        lat = float(self.settings["latitude"])
        lon = float(self.settings["longitude"])
        zoom = int(self.settings["zoom"])
        theme = str(self.settings.get("theme", "light")).lower()

        if theme not in ("light", "dark"):
            theme = "light"

        style_url = (
            "https://tiles.openfreemap.org/styles/dark"
            if theme == "dark"
            else "https://tiles.openfreemap.org/styles/liberty"
        )

        page = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">

<link
 href="https://unpkg.com/maplibre-gl@5.6.2/dist/maplibre-gl.css"
 rel="stylesheet"
/>

<script src="https://unpkg.com/maplibre-gl@5.6.2/dist/maplibre-gl.js">
</script>

<style>
html, body, #map {
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
    background: #101820;
}

/* RabbitFeeder retro radar overlay */
#radar-overlay {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    z-index: 1;
    pointer-events: none;
}

#status {
    position: absolute;
    top: 12px;
    left: 50px;
    z-index: 5;
    padding: 9px 12px;
    background: #172431;
    color: #ffffff;
    font: 12px sans-serif;
    border: 1px solid #39536a;
    border-radius: 5px;
}

.maplibregl-marker {
    z-index: 2 !important;
}

.plane-marker {
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    filter: drop-shadow(0 0 4px #00bfff);
    transition: filter 0.9s ease-out;
}

.plane-marker.radar-hit {
    filter: drop-shadow(0 0 8px #00ff80)
            drop-shadow(0 0 16px rgba(0, 255, 128, 0.95));
}

.plane-marker.radar-hit .plane-icon {
    filter: drop-shadow(0 0 8px #00ff80)
            drop-shadow(0 0 13px rgba(0, 255, 128, 0.9));
}

.plane-icon {
    width: 30px;
    height: 30px;
    display: block;
    transform-origin: center center;
    transition: transform 0.25s linear;
    filter: drop-shadow(0 0 4px #00bfff);
}

.plane-icon svg {
    width: 100%;
    height: 100%;
    display: block;
    overflow: visible;
}

#aircraft-panel {
    position: absolute;
    top: 55px;
    right: 12px;
    z-index: 10;
    width: 245px;
    max-width: calc(100% - 40px);
    padding: 14px;
    background: #172431;
    color: #e5edf5;
    border: 1px solid #40d8ff;
    border-radius: 8px;
    box-shadow: 0 4px 18px rgba(0,0,0,0.45);
    font: 12px sans-serif;
}

#aircraft-panel[hidden] {
    display: none;
}

.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.panel-title {
    color: #40d8ff;
    font-size: 16px;
    font-weight: bold;
}

.panel-close {
    border: 0;
    background: transparent;
    color: white;
    font-size: 22px;
    cursor: pointer;
}

.panel-detail {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 5px 0;
    border-bottom: 1px solid #304353;
}

.panel-detail span:first-child {
    color: #91a8bb;
}

.panel-detail span:last-child {
    text-align: right;
    font-weight: bold;
}

.receiver-marker {
    width: 24px;
    height: 24px;
    border: 3px solid white;
    background: #18a558;
    border-radius: 50%;
    box-shadow: 0 0 12px #18a558;
}

.maplibregl-popup-content {
    background: #172431;
    color: #e5edf5;
    border: 1px solid #39536a;
    border-radius: 7px;
    font: 12px sans-serif;
    min-width: 180px;
}

.maplibregl-popup-close-button {
    color: white;
    font-size: 18px;
}

.aircraft-title {
    color: #40d8ff;
    font-weight: bold;
    font-size: 14px;
    margin-bottom: 7px;
}

.aircraft-detail {
    margin: 4px 0;
}
</style>
</head>

<body>

<div id="map"></div>
<canvas id="radar-overlay" aria-hidden="true"></canvas>
<div id="status">RABBITFEEDER · LOADING MAP</div>
<div id="aircraft-panel" hidden></div>

<script>
let map = null;
let aircraftMarkers = new Map();
let latestAircraft = [];

const receiverPosition = [__LON__, __LAT__];

let radarCanvas = null;
let radarContext = null;
let radarAngle = 0;
let radarLastFrame = 0;
let radarFrameId = null;

function resizeRadar() {
    if (!radarCanvas) return;

    const rect = radarCanvas.getBoundingClientRect();
    const pixelRatio = window.devicePixelRatio || 1;

    radarCanvas.width = Math.round(rect.width * pixelRatio);
    radarCanvas.height = Math.round(rect.height * pixelRatio);

    radarContext.setTransform(
        pixelRatio, 0, 0, pixelRatio, 0, 0
    );

    drawRadar();
}

function drawRadar() {
    if (!map || !radarContext || !map.loaded()) return;

    const canvasRect = radarCanvas.getBoundingClientRect();
    const mapRect = map.getContainer().getBoundingClientRect();

    const width = canvasRect.width;
    const height = canvasRect.height;

    radarContext.clearRect(0, 0, width, height);

    const projected = map.project(receiverPosition);

    const cx = mapRect.left + projected.x - canvasRect.left;
    const cy = mapRect.top + projected.y - canvasRect.top;

    const latitude = receiverPosition[1];
    const metresPerPixel =
        40075016.686 * Math.cos(latitude * Math.PI / 180) /
        (512 * Math.pow(2, map.getZoom()));

    const radarRadius = 100000 / metresPerPixel;

    if (!Number.isFinite(radarRadius) || radarRadius <= 0) return;

    const ctx = radarContext;

    // Subtle radar range rings.
    ctx.save();

    ctx.strokeStyle = "rgba(0, 255, 125, 0.25)";
    ctx.lineWidth = 1;

    for (const range of [25000, 50000, 75000, 100000]) {
        const radius = range / metresPerPixel;

        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = "rgba(100, 255, 160, 0.65)";
        ctx.font = "10px monospace";
        ctx.fillText(
            (range / 1000) + " KM",
            cx + 5,
            cy - radius + 13
        );
    }

    // Radar crosshairs.
    ctx.strokeStyle = "rgba(0, 255, 125, 0.16)";
    ctx.setLineDash([4, 7]);

    ctx.beginPath();
    ctx.moveTo(cx - radarRadius, cy);
    ctx.lineTo(cx + radarRadius, cy);
    ctx.moveTo(cx, cy - radarRadius);
    ctx.lineTo(cx, cy + radarRadius);
    ctx.stroke();

    ctx.setLineDash([]);

    // Fading green sweep fan.
    const trailWidth = 0.75;
    const trailSteps = 32;

    for (let i = 0; i < trailSteps; i++) {
        const start = radarAngle - trailWidth +
            (i / trailSteps) * trailWidth;

        const end = radarAngle - trailWidth +
            ((i + 1) / trailSteps) * trailWidth;

        const alpha = 0.14 * (i / trailSteps);

        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, radarRadius, start, end);
        ctx.closePath();

        ctx.fillStyle = "rgba(0, 255, 110, " + alpha + ")";
        ctx.fill();
    }

    // Bright leading sweep line.
    const sweepX = cx + Math.cos(radarAngle) * radarRadius;
    const sweepY = cy + Math.sin(radarAngle) * radarRadius;

    ctx.save();
    ctx.shadowColor = "#00ff80";
    ctx.shadowBlur = 16;
    ctx.strokeStyle = "#70ffae";
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(sweepX, sweepY);
    ctx.stroke();
    ctx.restore();

    // Illuminated receiver centre.
    ctx.shadowColor = "#00ff80";
    ctx.shadowBlur = 14;
    ctx.fillStyle = "#aaffcc";

    ctx.beginPath();
    ctx.arc(cx, cy, 4, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
}

function normalizeRadarAngle(angle) {
    const fullCircle = Math.PI * 2;
    return ((angle % fullCircle) + fullCircle) % fullCircle;
}

function radarSweepPassed(target, previous, current) {
    target = normalizeRadarAngle(target);
    previous = normalizeRadarAngle(previous);
    current = normalizeRadarAngle(current);

    if (current >= previous) {
        return target > previous && target <= current;
    }

    return target > previous || target <= current;
}

function illuminateAircraftTargets(timestamp, previousAngle, currentAngle) {
    if (!map || !map.loaded()) return;

    const canvasRect = radarCanvas.getBoundingClientRect();
    const mapRect = map.getContainer().getBoundingClientRect();

    const receiver = map.project(receiverPosition);
    const cx = mapRect.left + receiver.x - canvasRect.left;
    const cy = mapRect.top + receiver.y - canvasRect.top;

    const latitude = receiverPosition[1];
    const metresPerPixel =
        40075016.686 * Math.cos(latitude * Math.PI / 180) /
        (512 * Math.pow(2, map.getZoom()));

    const radarRadius = 100000 / metresPerPixel;

    for (const entry of aircraftMarkers.values()) {
        const position = entry.marker.getLngLat();
        const projected = map.project([position.lng, position.lat]);

        const x = mapRect.left + projected.x - canvasRect.left;
        const y = mapRect.top + projected.y - canvasRect.top;

        const dx = x - cx;
        const dy = y - cy;
        const distance = Math.hypot(dx, dy);

        if (distance <= radarRadius && distance > 0) {
            const bearing = normalizeRadarAngle(
                Math.atan2(dy, dx)
            );

            if (radarSweepPassed(
                bearing,
                previousAngle,
                currentAngle
            )) {
                entry.illuminatedUntil = timestamp + 900;
                entry.element.classList.add("radar-hit");
            }
        }

        if (entry.illuminatedUntil &&
            timestamp >= entry.illuminatedUntil) {
            entry.element.classList.remove("radar-hit");
            entry.illuminatedUntil = 0;
        }
    }
}

function animateRadar(timestamp) {
    const previousAngle = radarAngle;

    if (radarLastFrame) {
        const elapsed = Math.min(timestamp - radarLastFrame, 100);
        radarAngle = (
            radarAngle + elapsed * Math.PI * 2 / 12000
        ) % (Math.PI * 2);

        illuminateAircraftTargets(
            timestamp,
            previousAngle,
            radarAngle
        );
    }

    radarLastFrame = timestamp;
    drawRadar();

    radarFrameId = requestAnimationFrame(animateRadar);
}

function startRadar() {
    radarCanvas = document.getElementById("radar-overlay");
    radarContext = radarCanvas.getContext("2d");

    resizeRadar();

    window.addEventListener("resize", resizeRadar);
    map.on("move", drawRadar);
    map.on("zoom", drawRadar);
    map.on("resize", resizeRadar);

    if (radarFrameId !== null) {
        cancelAnimationFrame(radarFrameId);
    }

    radarLastFrame = 0;
    radarFrameId = requestAnimationFrame(animateRadar);
}

function initMap() {

    map = new maplibregl.Map({
        container: "map",
        style: __STYLE__,
        center: receiverPosition,
        zoom: __ZOOM__,
        attributionControl: true
    });

    map.addControl(
        new maplibregl.NavigationControl(),
        "top-right"
    );

    map.addControl(
        new maplibregl.ScaleControl(),
        "bottom-left"
    );

    map.on("load", () => {

        document.getElementById("status").textContent =
            "RABBITFEEDER · MAP ONLINE";

        startRadar();

        const receiver = document.createElement("div");
        receiver.className = "receiver-marker";
        receiver.title = "Your receiver location";

        new maplibregl.Marker({
            element: receiver
        })
        .setLngLat(receiverPosition)
        .setPopup(
            new maplibregl.Popup().setText(
                "RabbitFeeder receiver location"
            )
        )
        .addTo(map);

        updateAircraft(latestAircraft);
    });

    map.on("error", (event) => {
        console.error("MapLibre error:", event.error);

        document.getElementById("status").textContent =
            "MAP ERROR · CHECK INTERNET CONNECTION";
    });
}



let selectedAircraftId = null;

function showAircraftPanel(aircraft) {

    const panel = document.getElementById("aircraft-panel");
    panel.replaceChildren();
    panel.hidden = false;

    const header = document.createElement("div");
    header.className = "panel-header";

    const title = document.createElement("div");
    title.className = "panel-title";
    title.textContent = aircraft.callsign || aircraft.icao || "Aircraft";

    const close = document.createElement("button");
    close.className = "panel-close";
    close.textContent = "×";
    close.title = "Close aircraft information";

    close.addEventListener("click", () => {
        selectedAircraftId = null;
        panel.hidden = true;
    });

    header.append(title, close);
    panel.appendChild(header);

    const id = String(aircraft.icao || "");

    const values = [
        ["ICAO", id],
        ["Callsign", aircraft.callsign || "—"],
        ["Altitude", aircraft.altitude == null ? "—" : aircraft.altitude + " ft"],
        ["Speed", aircraft.speed == null ? "—" : aircraft.speed + " kt"],
        ["Compass track", aircraft.track == null ? "—" : aircraft.track + "°"],
        ["Squawk", aircraft.squawk || "—"],
        ["Latitude", aircraft.latitude == null ? "—" : Number(aircraft.latitude).toFixed(5)],
        ["Longitude", aircraft.longitude == null ? "—" : Number(aircraft.longitude).toFixed(5)]
    ];

    for (const [label, value] of values) {
        const line = document.createElement("div");
        line.className = "panel-detail";

        const name = document.createElement("span");
        name.textContent = label;

        const data = document.createElement("span");
        data.textContent = String(value);

        line.append(name, data);
        panel.appendChild(line);
    }
}


function updateAircraft(items) {

    latestAircraft = items || [];

    if (!map || !map.loaded()) {
        return;
    }

    let visibleCount = 0;

    for (const aircraft of latestAircraft) {

        if (aircraft.latitude == null ||
            aircraft.longitude == null) {
            continue;
        }

        const lat = Number(aircraft.latitude);
        const lon = Number(aircraft.longitude);

        if (!Number.isFinite(lat) ||
            !Number.isFinite(lon) ||
            Math.abs(lat) > 90 ||
            Math.abs(lon) > 180) {
            continue;
        }

        const id = String(aircraft.icao || "");

        if (!id) {
            continue;
        }

        visibleCount++;

        const position = [lon, lat];
        let entry = aircraftMarkers.get(id);

        if (!entry) {

            const element = document.createElement("div");
            element.className = "plane-marker";

            const icon = document.createElement("span");
            icon.className = "plane-icon";

            // Aircraft nose points North at zero degrees.
            icon.innerHTML = `
                <svg viewBox="0 0 24 30"
                     xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 1
                             L15 10
                             L23 15
                             L23 18
                             L15 16
                             L15 24
                             L18 27
                             L18 29
                             L12 27
                             L6 29
                             L6 27
                             L9 24
                             L9 16
                             L1 18
                             L1 15
                             L9 10 Z"
                          fill="#40d8ff"
                          stroke="#003344"
                          stroke-width="0.8"/>
                </svg>
            `;

            element.appendChild(icon);

            const marker = new maplibregl.Marker({
                element: element,
                anchor: "center"
            })
            .setLngLat(position)
            .addTo(map);

            entry = {
                marker: marker,
                icon: icon,
                element: element,
                illuminatedUntil: 0
            };

            aircraftMarkers.set(id, entry);

            element.addEventListener("click", (event) => {
                event.stopPropagation();
                selectedAircraftId = id;

                const selected = latestAircraft.find(
                    item => String(item.icao || "") === id
                );

                if (selected) {
                    showAircraftPanel(selected);
                }
            });
        }

        entry.marker.setLngLat(position);

        const heading = Number(aircraft.track);

        if (aircraft.track != null && Number.isFinite(heading)) {
            entry.icon.style.transform =
                "rotate(" + ((heading % 360 + 360) % 360) + "deg)";
        }

        entry.marker.getElement().title =
            (aircraft.callsign || id) + " · " + id;
    }

    // Refresh selected information without closing the panel.
    if (selectedAircraftId !== null) {

        const selected = latestAircraft.find(
            item => String(item.icao || "") === selectedAircraftId
        );

        if (selected) {
            showAircraftPanel(selected);
        }
    }

    document.getElementById("status").textContent =
        "LIVE AIRCRAFT · " + visibleCount;
}

window.updateAircraft = updateAircraft;

window.rabbitFeederMapReady = false;

initMap();

</script>
</body>
</html>
"""

        page = page.replace("__LAT__", str(lat))
        page = page.replace("__LON__", str(lon))
        page = page.replace("__ZOOM__", str(zoom))
        page = page.replace("__STYLE__", json.dumps(style_url))

        self.web.setHtml(
            page,
            QUrl("https://rabbitfeeder.local/")
        )

    def update_aircraft(self, aircraft):
        self.latest_aircraft = aircraft

        payload = json.dumps(aircraft)

        self.web.page().runJavaScript(
            "window.updateAircraft && "
            f"window.updateAircraft({payload});"
        )

    def apply_settings(self, settings):
        self.settings = {
            **DEFAULT_SETTINGS,
            **settings
        }

        save_settings(self.settings)
        self.load_map()

        self.update_aircraft(self.latest_aircraft)
