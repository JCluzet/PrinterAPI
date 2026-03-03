#!/bin/bash
# setup.sh — run once on the Raspberry Pi after cloning the repo
set -e

echo "==> Creating virtualenv"
python3 -m venv .venv

echo "==> Installing dependencies"
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> Installing systemd service"
sudo cp printer-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable printer-api
sudo systemctl start printer-api

echo "==> Done. Service status:"
sudo systemctl status printer-api --no-pager
