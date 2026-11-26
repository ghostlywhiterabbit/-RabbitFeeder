#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/.local/share/RabbitFeeder"

if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    echo "RabbitFeeder is not installed. Please run install.sh first."
    exit 1
fi

cd "$APP_DIR"
exec "$APP_DIR/.venv/bin/python" -m rabbitfeeder
