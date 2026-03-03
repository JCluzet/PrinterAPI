#!/bin/bash
# setup.sh — run once on the Raspberry Pi after cloning the repo
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Checking Python version (requires 3.11+)"
python3 -c "import sys; assert sys.version_info >= (3, 11), f'Python 3.11+ required, got {sys.version}'" \
  || { echo "ERROR: Python 3.11+ is required. Install it first."; exit 1; }

echo "==> Creating virtualenv"
python3 -m venv "$SCRIPT_DIR/.venv"

echo "==> Installing dependencies"
"$SCRIPT_DIR/.venv/bin/pip" install --upgrade pip -q
"$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q

echo "==> Installing systemd service"
sudo cp "$SCRIPT_DIR/printer-api.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable printer-api
sudo systemctl start printer-api || true

echo "==> Done. Service status:"
sudo systemctl status printer-api --no-pager || true
