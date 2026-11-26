#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/RabbitFeeder"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "======================================"
echo "       RABBITFEEDER INSTALLER"
echo "======================================"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: Python 3 is not installed."
    exit 1
fi

PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

echo "Detected Python: $PYTHON_VERSION"

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
    echo "ERROR: RabbitFeeder requires Python 3.10 or newer."
    exit 1
fi

echo "Installing RabbitFeeder into:"
echo "$APP_DIR"

if [ ! -f "$SCRIPT_DIR/run.sh" ]; then
    echo "ERROR: run.sh is missing from the installation package."
    exit 1
fi

mkdir -p "$APP_DIR" "$DESKTOP_DIR"

cp -a "$SCRIPT_DIR/rabbitfeeder" "$APP_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$APP_DIR/"
cp "$SCRIPT_DIR/run.sh" "$APP_DIR/run.sh"
chmod +x "$APP_DIR/run.sh"

if [ ! -d "$APP_DIR/.venv" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi

echo "Installing Python dependencies..."

"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

cat > "$DESKTOP_DIR/rabbitfeeder.desktop" <<DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=RabbitFeeder
Comment=Aviation Feeder Manager
Exec="$APP_DIR/run.sh"
Path=$APP_DIR
Terminal=false
Categories=Utility;
DESKTOP

chmod +x "$DESKTOP_DIR/rabbitfeeder.desktop"

echo
echo "======================================"
echo "       INSTALLATION COMPLETE"
echo "======================================"
echo "RabbitFeeder is installed."
echo "You can launch it from your applications menu."
echo
echo "Next: configure your receiver using MAP SETTINGS."
