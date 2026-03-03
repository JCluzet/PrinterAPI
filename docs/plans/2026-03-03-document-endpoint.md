# Document Endpoint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `POST /print/document` endpoint that accepts a high-level JSON document model (title, text, kv, separator, feed, qr, image, cut) and converts it to ESC/POS bytes, so n8n and other tools never have to touch raw bytes.

**Architecture:** New `src/document.py` module converts a list of typed elements into ESC/POS bytes using Pillow for image support. The existing `POST /print` raw endpoint is unchanged. A new `POST /print/document` route in `src/main.py` calls `document_to_escpos()` then `print_raw()`. Documentation lives in `docs/API.md`.

**Tech Stack:** Python 3.11+, FastAPI, Pillow (image resize + 1-bit conversion), existing `src/printer.py`

---

### Task 1: Add Pillow dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add Pillow to requirements.txt**

```
fastapi==0.115.11
uvicorn==0.34.0
Pillow==11.1.0
```

**Step 2: Install in local venv**

```bash
cd /Users/jo/Desktop/PrinterAPI
.venv/bin/pip install Pillow==11.1.0 -q
```

Expected: installs without error.

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add Pillow for image support in document endpoint"
```

---

### Task 2: Document converter module (TDD)

**Files:**
- Create: `src/document.py`
- Create: `tests/test_document.py`

**Step 1: Write the failing tests**

```python
# tests/test_document.py
import base64
import pytest
from unittest.mock import patch, MagicMock
from src.document import document_to_escpos


def _decode(data: bytes) -> str:
    return data.decode('latin-1')


def test_init_resets_printer():
    result = document_to_escpos([])
    assert result[:2] == b'\x1b@'


def test_title_element():
    result = document_to_escpos([{'type': 'title', 'text': 'Hello'}])
    assert b'Hello' in result
    # double size GS ! 0x11
    assert b'\x1d!\x11' in result


def test_text_element_defaults():
    result = document_to_escpos([{'type': 'text', 'content': 'World'}])
    assert b'World' in result


def test_text_element_bold():
    result = document_to_escpos([{'type': 'text', 'content': 'X', 'bold': True}])
    assert b'\x1bE\x01' in result  # bold on
    assert b'\x1bE\x00' in result  # bold off


def test_text_element_align_center():
    result = document_to_escpos([{'type': 'text', 'content': 'X', 'align': 'center'}])
    assert b'\x1ba\x01' in result


def test_kv_element():
    result = document_to_escpos([{'type': 'kv', 'key': 'Foo', 'value': 'Bar'}])
    assert b'Foo' in result
    assert b'Bar' in result
    assert b'.' in result  # dots between key and value


def test_separator_element():
    result = document_to_escpos([{'type': 'separator'}])
    assert b'---' in result


def test_feed_element():
    result = document_to_escpos([{'type': 'feed', 'lines': 3}])
    assert result.count(b'\n') >= 3


def test_qr_element():
    result = document_to_escpos([{'type': 'qr', 'url': 'https://example.com'}])
    assert b'https://example.com' in result
    assert b'\x1d(k' in result  # QR code ESC/POS command


def test_cut_element():
    result = document_to_escpos([{'type': 'cut'}])
    assert b'\x1dV' in result


def test_unknown_element_skipped():
    # Should not raise, just skip unknown types
    result = document_to_escpos([{'type': 'unicorn', 'data': 'whatever'}])
    assert result[:2] == b'\x1b@'


def test_image_base64_element():
    # 1x1 white PNG in base64
    png_1x1 = (
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8'
        'z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=='
    )
    result = document_to_escpos([{'type': 'image', 'data': png_1x1}])
    # GS v 0 raster image command
    assert b'\x1dv\x00' in result


def test_image_invalid_base64_skips():
    result = document_to_escpos([{'type': 'image', 'data': 'not-valid!!!'}])
    # Should not raise, returns error text or skips
    assert isinstance(result, bytes)


def test_image_url_element():
    png_bytes = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8'
        'z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=='
    )
    with patch('src.document.urllib.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = png_bytes
        mock_urlopen.return_value = mock_response
        result = document_to_escpos([{'type': 'image', 'url': 'https://example.com/img.png'}])
    assert b'\x1dv\x00' in result
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_document.py -v
```

Expected: `ImportError: cannot import name 'document_to_escpos'`

**Step 3: Create `src/document.py`**

```python
# src/document.py
import base64
import urllib.request
from io import BytesIO

from PIL import Image

ESC = b'\x1b'
GS  = b'\x1d'

INIT        = ESC + b'@'
ALIGN_LEFT  = ESC + b'a\x00'
ALIGN_CENTER= ESC + b'a\x01'
ALIGN_RIGHT = ESC + b'a\x02'
BOLD_ON     = ESC + b'E\x01'
BOLD_OFF    = ESC + b'E\x00'
SIZE_NORMAL = GS  + b'!\x00'
SIZE_2X     = GS  + b'!\x11'
SIZE_WIDE   = GS  + b'!\x10'
SIZE_TALL   = GS  + b'!\x01'
CUT         = GS  + b'V\x41\x05'

PRINTER_WIDTH = 384  # pixels, 80mm at 203 DPI
LINE_WIDTH    = 32   # characters for kv dots


def _align(align: str) -> bytes:
    return {'left': ALIGN_LEFT, 'center': ALIGN_CENTER, 'right': ALIGN_RIGHT}.get(align, ALIGN_LEFT)


def _render_title(el: dict) -> bytes:
    d  = ALIGN_CENTER + SIZE_2X + BOLD_ON
    d += (el.get('text', '') + '\n').encode('utf-8', errors='replace')
    d += SIZE_NORMAL + BOLD_OFF + ALIGN_LEFT
    return d


def _render_text(el: dict) -> bytes:
    align = el.get('align', 'left')
    bold  = el.get('bold', False)
    size  = el.get('size', 'normal')
    size_cmd = {'large': SIZE_2X, 'wide': SIZE_WIDE, 'tall': SIZE_TALL}.get(size, SIZE_NORMAL)
    d  = _align(align)
    d += (BOLD_ON if bold else b'')
    d += size_cmd
    d += (el.get('content', '') + '\n').encode('utf-8', errors='replace')
    d += SIZE_NORMAL + BOLD_OFF + ALIGN_LEFT
    return d


def _render_kv(el: dict) -> bytes:
    key   = str(el.get('key', ''))
    value = str(el.get('value', ''))
    dots  = max(1, LINE_WIDTH - len(key) - len(value))
    return ALIGN_LEFT + (key + '.' * dots + value + '\n').encode('utf-8', errors='replace')


def _render_separator(el: dict) -> bytes:
    char = str(el.get('char', '-'))[:1] or '-'
    return ALIGN_LEFT + (char * LINE_WIDTH + '\n').encode('ascii', errors='replace')


def _render_feed(el: dict) -> bytes:
    lines = max(1, int(el.get('lines', 1)))
    return b'\n' * lines


def _render_qr(el: dict) -> bytes:
    url = el.get('url', '').encode('utf-8')
    if not url:
        return b''
    size = min(max(int(el.get('size', 6)), 1), 16)
    ln   = len(url) + 3
    d  = ALIGN_CENTER
    d += GS + b'(k\x04\x00\x31\x41\x32\x00'
    d += GS + b'(k\x03\x00\x31\x43' + bytes([size])
    d += GS + b'(k\x03\x00\x31\x45\x31'
    d += GS + b'(k' + bytes([ln & 0xFF, (ln >> 8) & 0xFF]) + b'\x31\x50\x30' + url
    d += GS + b'(k\x03\x00\x31\x51\x30'
    d += ALIGN_LEFT
    return d


def _image_to_escpos(img: Image.Image) -> bytes:
    w, h = img.size
    if w > PRINTER_WIDTH:
        h = int(h * PRINTER_WIDTH / w)
        w = PRINTER_WIDTH
        img = img.resize((w, h), Image.LANCZOS)
    img = img.convert('1')
    byte_width = (w + 7) // 8
    pixels = img.load()
    raster = bytearray()
    for y in range(h):
        for bx in range(byte_width):
            byte = 0
            for bit in range(8):
                x = bx * 8 + bit
                if x < w and pixels[x, y] == 0:
                    byte |= (1 << (7 - bit))
            raster.append(byte)
    d  = ALIGN_CENTER
    d += GS + b'v\x00\x00'
    d += bytes([byte_width & 0xFF, (byte_width >> 8) & 0xFF])
    d += bytes([h & 0xFF, (h >> 8) & 0xFF])
    d += bytes(raster)
    d += ALIGN_LEFT
    return d


def _render_image(el: dict) -> bytes:
    try:
        if 'data' in el:
            raw = base64.b64decode(el['data'])
        elif 'url' in el:
            req = urllib.request.Request(el['url'], headers={'User-Agent': 'PrinterAPI/1.0'})
            raw = urllib.request.urlopen(req, timeout=10).read()
        else:
            return b''
        return _image_to_escpos(Image.open(BytesIO(raw)))
    except Exception as e:
        return f'[image error: {e}]\n'.encode('utf-8', errors='replace')


def _render_cut(_el: dict) -> bytes:
    return CUT


_RENDERERS = {
    'title':     _render_title,
    'text':      _render_text,
    'kv':        _render_kv,
    'separator': _render_separator,
    'feed':      _render_feed,
    'qr':        _render_qr,
    'image':     _render_image,
    'cut':       _render_cut,
}


def document_to_escpos(elements: list) -> bytes:
    d = INIT
    for el in elements:
        renderer = _RENDERERS.get(el.get('type', ''))
        if renderer:
            d += renderer(el)
    return d
```

**Step 4: Run all tests**

```bash
.venv/bin/pytest tests/test_document.py -v
```

Expected: all 14 tests pass.

**Step 5: Commit**

```bash
git add src/document.py tests/test_document.py
git commit -m "feat: add document_to_escpos converter with all element types"
```

---

### Task 3: Add POST /print/document endpoint (TDD)

**Files:**
- Modify: `src/main.py`
- Modify: `tests/test_main.py`

**Step 1: Add tests to tests/test_main.py**

Append these tests to the existing file:

```python
# append to tests/test_main.py
def test_print_document_success():
    payload = {
        'elements': [
            {'type': 'title', 'text': 'Test'},
            {'type': 'cut'},
        ]
    }
    with patch('src.main.print_raw') as mock_print:
        response = client.post('/print/document', json=payload)
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    mock_print.assert_called_once()
    args = mock_print.call_args[0][0]
    assert isinstance(args, bytes)
    assert b'Test' in args


def test_print_document_empty_elements():
    with patch('src.main.print_raw') as mock_print:
        response = client.post('/print/document', json={'elements': []})
    assert response.status_code == 200
    mock_print.assert_called_once()


def test_print_document_unknown_type_skipped():
    payload = {'elements': [{'type': 'unicorn'}]}
    with patch('src.main.print_raw'):
        response = client.post('/print/document', json=payload)
    assert response.status_code == 200


def test_print_document_printer_failure():
    payload = {'elements': [{'type': 'cut'}]}
    with patch('src.main.print_raw', side_effect=OSError('no device')):
        response = client.post('/print/document', json=payload)
    assert response.status_code == 500
    assert response.json()['detail'] == 'no device'
```

**Step 2: Run new tests to verify they fail**

```bash
.venv/bin/pytest tests/test_main.py::test_print_document_success -v
```

Expected: FAIL with `404 Not Found`

**Step 3: Update src/main.py**

Add after the existing imports and before the `PrintRequest` class:

```python
from typing import Any
from src.document import document_to_escpos
```

Add after the existing `/print` route:

```python
class DocumentElement(BaseModel):
    model_config = {"extra": "allow"}
    type: str


class DocumentRequest(BaseModel):
    elements: list[DocumentElement]


@app.post('/print/document')
def print_document(req: DocumentRequest):
    data = document_to_escpos([el.model_dump() for el in req.elements])
    try:
        print_raw(data)
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'status': 'ok'}
```

**Step 4: Run all tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests pass (6 original + 4 new = 10 total, plus 14 document tests = 24 total).

**Step 5: Commit**

```bash
git add src/main.py tests/test_main.py
git commit -m "feat: add POST /print/document endpoint"
```

---

### Task 4: API documentation

**Files:**
- Create: `docs/API.md`

**Step 1: Create `docs/API.md`**

```markdown
# PrinterAPI — Documentation

Imprimante thermique 80mm connectée à un Raspberry Pi, accessible via HTTP.

## Base URL

```
https://printer.cluzhub.com
```

## Authentification

Tous les endpoints (sauf `/health`) requièrent deux headers Cloudflare Access :

```
CF-Access-Client-Id: <client-id>
CF-Access-Client-Secret: <client-secret>
```

---

## Endpoints

### GET /health

Vérifie que le service est en ligne.

**Réponse :**
```json
{ "status": "ok" }
```

---

### POST /print/document ✅ Recommandé

Imprime un document structuré. C'est l'endpoint principal à utiliser depuis n8n ou tout autre outil.

**Body :**
```json
{
  "elements": [ ... ]
}
```

**Réponse :**
```json
{ "status": "ok" }
```

#### Types d'éléments

##### `title` — Titre en double taille, centré, gras
```json
{ "type": "title", "text": "Mon Titre" }
```

##### `text` — Texte normal
```json
{
  "type": "text",
  "content": "Mon texte",
  "align": "left",   // "left" | "center" | "right"  (défaut: "left")
  "bold": false,     // true | false  (défaut: false)
  "size": "normal"   // "normal" | "large" | "wide" | "tall"  (défaut: "normal")
}
```

##### `kv` — Ligne clé / valeur avec points
```json
{ "type": "kv", "key": "Ajouts", "value": "+247 lignes" }
```
Rendu : `Ajouts......................+247 lignes`

##### `separator` — Ligne de séparation
```json
{ "type": "separator" }
{ "type": "separator", "char": "=" }  // caractère personnalisé
```

##### `feed` — Sauts de ligne
```json
{ "type": "feed", "lines": 2 }
```

##### `qr` — QR code
```json
{
  "type": "qr",
  "url": "https://example.com",
  "size": 6   // 1-16, défaut 6
}
```

##### `image` — Image (logo, graphe, photo)
```json
// Depuis une URL :
{ "type": "image", "url": "https://example.com/logo.png" }

// Encodée en base64 :
{ "type": "image", "data": "<base64-string>" }
```
L'image est automatiquement redimensionnée à 384px de large et convertie en noir/blanc.

##### `cut` — Coupe le papier
```json
{ "type": "cut" }
```

---

### POST /print ⚙️ Avancé

Envoie des bytes ESC/POS bruts (base64). Pour les cas où le document model ne suffit pas.

**Body :**
```json
{ "raw": "<base64-encoded ESC/POS bytes>" }
```

---

## Exemple complet — Reçu de PR GitHub

```json
{
  "elements": [
    { "type": "image", "url": "https://monlogo.com/logo.png" },
    { "type": "feed", "lines": 1 },
    { "type": "title", "text": "Pull Request mergée" },
    { "type": "separator" },
    { "type": "kv", "key": "PR",      "value": "#42" },
    { "type": "kv", "key": "Auteur",  "value": "Jo Cluzet" },
    { "type": "kv", "key": "Repo",    "value": "PrinterAPI" },
    { "type": "kv", "key": "Ajouts",  "value": "+247" },
    { "type": "kv", "key": "Suppres.","value": "-18" },
    { "type": "separator" },
    { "type": "text", "content": "Bien joué !", "align": "center", "bold": true },
    { "type": "feed", "lines": 1 },
    { "type": "qr",  "url": "https://github.com/JCluzet/PrinterAPI/pull/42" },
    { "type": "feed", "lines": 2 },
    { "type": "cut" }
  ]
}
```

## Exemple curl

```bash
curl -X POST https://printer.cluzhub.com/print/document \
  -H "Content-Type: application/json" \
  -H "CF-Access-Client-Id: <client-id>" \
  -H "CF-Access-Client-Secret: <client-secret>" \
  -d '{
    "elements": [
      { "type": "title", "text": "Hello !" },
      { "type": "text",  "content": "Ca marche.", "align": "center" },
      { "type": "cut" }
    ]
  }'
```

## Exemple Python (requests)

```python
import requests

requests.post(
    'https://printer.cluzhub.com/print/document',
    headers={
        'CF-Access-Client-Id': '<client-id>',
        'CF-Access-Client-Secret': '<client-secret>',
    },
    json={
        'elements': [
            {'type': 'title',     'text': 'Hello !'},
            {'type': 'separator'},
            {'type': 'kv',        'key': 'Statut', 'value': 'OK'},
            {'type': 'cut'},
        ]
    }
)
```
```

**Step 2: Commit**

```bash
git add docs/API.md
git commit -m "docs: add full API documentation with examples"
```

---

### Task 5: Push, deploy and live test

**Step 1: Push to GitHub**

```bash
git push origin main
```

**Step 2: Restart service on Pi to pull latest**

```bash
# SSH into the Pi
ssh printer@192.168.1.49
sudo systemctl restart printer-api
# Watch logs
sudo journalctl -u printer-api -f
```

Wait for: `INFO: Application startup complete.`

**Step 3: Live test via Cloudflare — document endpoint**

```bash
curl -s -X POST https://printer.cluzhub.com/print/document \
  -H "Content-Type: application/json" \
  -H "CF-Access-Client-Id: 3f410ca892b75421c8db9239126c564d.access" \
  -H "CF-Access-Client-Secret: b8a5cdb1b07dbf043281c3199b7588240eaadfe8f99a4c1511ee2b8e7cd65efb" \
  -d '{
    "elements": [
      { "type": "title",     "text": "Document API OK" },
      { "type": "separator" },
      { "type": "kv",        "key": "Endpoint", "value": "/print/document" },
      { "type": "kv",        "key": "Status",   "value": "Live" },
      { "type": "feed",      "lines": 1 },
      { "type": "text",      "content": "Envoye depuis Cloudflare", "align": "center" },
      { "type": "qr",        "url": "https://printer.cluzhub.com/health" },
      { "type": "cut" }
    ]
  }'
```

Expected: `{"status":"ok"}` and the printer prints the ticket.
