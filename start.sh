#!/bin/bash
# start.sh — called by systemd on each service start
# Pulls latest code from GitHub, updates deps, then starts the API
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Pulling latest from GitHub..."
git fetch origin
git reset --hard origin/main

echo "==> Installing system dependencies if needed..."
dpkg -l libcairo2 2>/dev/null | grep -q '^ii' || sudo apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 -q

echo "==> Updating dependencies..."
"$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q

echo "==> Starting PrinterAPI..."
exec "$SCRIPT_DIR/.venv/bin/uvicorn" src.main:app --host 0.0.0.0 --port 8000
