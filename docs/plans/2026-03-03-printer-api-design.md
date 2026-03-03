# PrinterAPI — Design Document

**Date:** 2026-03-03
**Status:** Approved

## Overview

A minimal REST API running on a Raspberry Pi, connected via USB to a thermal 80mm receipt printer (POS 80mm, auto-cut, 300mm/s). The API receives raw ESC/POS bytes (base64-encoded) via HTTP and writes them directly to the printer device.

## Architecture

```
[Client (PC)]  →  HTTP POST /print  →  [FastAPI on Raspberry Pi]  →  /dev/usb/lp0  →  [Printer]
```

Single stateless Python service. No database. No persistent state. One process, one endpoint.

## API

### POST /print

**Request:**
```json
{
  "raw": "<ESC/POS bytes encoded as base64>"
}
```

**Response (success):**
```json
{ "status": "ok" }
```

**Response (error):**
```json
{ "status": "error", "detail": "..." }
```

The server decodes the base64 string and writes the bytes directly to the printer device (`/dev/usb/lp0` or auto-detected USB device).

The client program uses `python-escpos` (or equivalent) to build the print job as bytes, base64-encodes it, and sends the POST request.

### GET /health

Returns `{ "status": "ok" }` — for liveness checks and Cloudflare Tunnel monitoring.

## Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.11+ |
| Framework | FastAPI |
| ASGI server | Uvicorn |
| Printer access | Direct write to `/dev/usb/lp0` |
| Process manager | systemd service |
| Port | 8000 |

## Authentication

None. The API will be on a private network. Cloudflare Tunnel (added later) provides the network-level access control.

## Deployment

- Runs as a systemd service (`printer-api.service`) — starts on boot, restarts on failure
- Dependencies managed via `requirements.txt`
- Repo cloned on Raspberry Pi, systemd unit installed manually

## Future: Cloudflare Tunnel

A `cloudflared` tunnel will proxy external HTTPS traffic to `localhost:8000`. Added separately once the core API is validated.

## Out of Scope

- Authentication / API keys
- Print queuing / job history
- Multiple printer support
- Template-based printing (client handles all ESC/POS construction)
