# PrinterAPI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A minimal FastAPI service on Raspberry Pi that receives raw ESC/POS bytes (base64-encoded) via HTTP and writes them directly to `/dev/usb/lp0`.

**Architecture:** Single stateless FastAPI app with one print endpoint and one health endpoint. No database. The printer module opens `/dev/usb/lp0` in binary write mode and flushes. A systemd unit starts the service on boot.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, pytest, python-escpos (dev/test only)

---

### Task 1: Project scaffolding

**Files:**
- Create: `src/__init__.py`
- Create: `src/printer.py`
- Create: `src/main.py`
- Create: `tests/__init__.py`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`

**Step 1: Create directory structure**

```bash
mkdir -p src tests
touch src/__init__.py tests/__init__.py
```

**Step 2: Create `requirements.txt`**

```
fastapi==0.115.0
uvicorn==0.30.6
```

**Step 3: Create `requirements-dev.txt`**

```
pytest==8.3.2
httpx==0.27.2
pytest-asyncio==0.24.0
```

**Step 4: Commit**

```bash
git add requirements.txt requirements-dev.txt src/__init__.py tests/__init__.py
git commit -m "chore: scaffold project structure"
```

---

### Task 2: Printer module

**Files:**
- Create: `src/printer.py`
- Create: `tests/test_printer.py`

**Step 1: Write the failing test**

```python
# tests/test_printer.py
import pytest
from unittest.mock import patch, MagicMock
from src.printer import print_raw


def test_print_raw_writes_bytes_to_device():
    data = b'\x1b@Hello\n'
    mock_file = MagicMock()
    with patch('builtins.open', return_value=mock_file.__enter__.return_value):
        with patch('src.printer.open', mock_open := MagicMock()) as m:
            mock_open.return_value.__enter__.return_value.write = MagicMock()
            print_raw(data, device='/dev/usb/lp0')
            m.assert_called_once_with('/dev/usb/lp0', 'wb')


def test_print_raw_raises_on_missing_device():
    with pytest.raises(OSError):
        print_raw(b'hello', device='/dev/usb/nonexistent')
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_printer.py -v
```
Expected: FAIL with `ImportError: cannot import name 'print_raw'`

**Step 3: Write minimal implementation**

```python
# src/printer.py
DEFAULT_DEVICE = '/dev/usb/lp0'


def print_raw(data: bytes, device: str = DEFAULT_DEVICE) -> None:
    """Write raw ESC/POS bytes directly to the printer device."""
    with open(device, 'wb') as f:
        f.write(data)
        f.flush()
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_printer.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/printer.py tests/test_printer.py
git commit -m "feat: add printer module with raw byte write"
```

---

### Task 3: FastAPI app

**Files:**
- Create: `src/main.py`
- Create: `tests/test_main.py`

**Step 1: Write the failing tests**

```python
# tests/test_main.py
import base64
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_print_sends_bytes_to_printer():
    data = b'\x1b@Hello\n'
    payload = {'raw': base64.b64encode(data).decode()}
    with patch('src.main.print_raw') as mock_print:
        response = client.post('/print', json=payload)
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    mock_print.assert_called_once_with(data)


def test_print_rejects_invalid_base64():
    response = client.post('/print', json={'raw': 'not-valid-base64!!!'})
    assert response.status_code == 422


def test_print_returns_error_on_printer_failure():
    payload = {'raw': base64.b64encode(b'test').decode()}
    with patch('src.main.print_raw', side_effect=OSError('device busy')):
        response = client.post('/print', json=payload)
    assert response.status_code == 500
    assert response.json()['detail'] == 'device busy'
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```
Expected: FAIL with `ImportError: cannot import name 'app'`

**Step 3: Write minimal implementation**

```python
# src/main.py
import base64
import binascii
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from src.printer import print_raw

app = FastAPI(title='PrinterAPI')


class PrintRequest(BaseModel):
    raw: str

    @field_validator('raw')
    @classmethod
    def must_be_valid_base64(cls, v: str) -> str:
        try:
            base64.b64decode(v, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError(f'invalid base64: {e}')
        return v


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/print')
def print_ticket(req: PrintRequest):
    data = base64.b64decode(req.raw)
    try:
        print_raw(data)
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'status': 'ok'}
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/ -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add src/main.py tests/test_main.py
git commit -m "feat: add FastAPI app with /print and /health endpoints"
```

---

### Task 4: Systemd service unit

**Files:**
- Create: `printer-api.service`

**Step 1: Create the unit file**

```ini
# printer-api.service
[Unit]
Description=PrinterAPI - ESC/POS HTTP service
After=network.target

[Service]
Type=simple
User=printer
WorkingDirectory=/home/printer/PrinterAPI
ExecStart=/home/printer/PrinterAPI/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Step 2: Commit**

```bash
git add printer-api.service
git commit -m "chore: add systemd service unit"
```

---

### Task 5: Setup script for Raspberry Pi

**Files:**
- Create: `setup.sh`

**Step 1: Create the setup script**

```bash
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
```

**Step 2: Make it executable and commit**

```bash
chmod +x setup.sh
git add setup.sh
git commit -m "chore: add Raspberry Pi setup script"
```

---

### Task 6: Push to GitHub

**Step 1: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
```

**Step 2: Commit and push**

```bash
git add .gitignore
git commit -m "chore: add gitignore"
git push origin main
```

---

## Testing the full flow manually on the Raspberry Pi

Once deployed, test with curl from any machine on the network:

```bash
python3 -c "
import base64, json
ESC = b'\x1b'
data = ESC + b'@' + b'Hello from API!\n\n\n' + b'\x1d\x56\x41\x03'
print(json.dumps({'raw': base64.b64encode(data).decode()}))
" | curl -s -X POST http://192.168.1.49:8000/print \
  -H 'Content-Type: application/json' \
  -d @-
```

Expected response: `{"status":"ok"}`
