#!/bin/bash
# start.sh — called by systemd on each service start
# Pulls latest code from GitHub, updates deps, then starts the API
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Pulling latest from GitHub..."
git fetch origin
git reset --hard origin/main

echo "==> Updating dependencies..."
"$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q

echo "==> Starting PrinterAPI..."
exec "$SCRIPT_DIR/.venv/bin/uvicorn" src.main:app --host 0.0.0.0 --port 8000
