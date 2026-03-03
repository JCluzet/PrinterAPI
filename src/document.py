# src/document.py
import base64
import logging
import urllib.request
from io import BytesIO

from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

try:
    import cairosvg
    _SVG_SUPPORT = True
except (ImportError, OSError):
    _SVG_SUPPORT = False

ESC = b'\x1b'
GS  = b'\x1d'

INIT         = ESC + b'@'
ALIGN_LEFT   = ESC + b'a\x00'
ALIGN_CENTER = ESC + b'a\x01'
ALIGN_RIGHT  = ESC + b'a\x02'
BOLD_ON      = ESC + b'E\x01'
BOLD_OFF     = ESC + b'E\x00'
SIZE_NORMAL  = GS  + b'!\x00'
SIZE_2X      = GS  + b'!\x11'
SIZE_WIDE    = GS  + b'!\x10'
SIZE_TALL    = GS  + b'!\x01'
CUT          = GS  + b'V\x41\x05'

PRINTER_WIDTH = 384
MAX_HEIGHT    = 2000
LINE_WIDTH    = 32


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
    try:
        lines = max(1, int(el.get('lines', 1)))
    except (ValueError, TypeError):
        lines = 1
    return b'\n' * lines


def _render_qr(el: dict) -> bytes:
    url = el.get('url', '').encode('utf-8')
    if not url:
        return b''
    try:
        size = min(max(int(el.get('size', 6)), 1), 16)
    except (ValueError, TypeError):
        size = 6
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
    if h > MAX_HEIGHT:
        w = int(w * MAX_HEIGHT / h)
        h = MAX_HEIGHT
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


def _svg_to_png(raw: bytes) -> bytes:
    if not _SVG_SUPPORT:
        raise RuntimeError('cairosvg not available')
    return cairosvg.svg2png(bytestring=raw, output_width=PRINTER_WIDTH)


def _render_image(el: dict) -> bytes:
    try:
        if 'data' in el:
            raw = base64.b64decode(el['data'])
        elif 'url' in el:
            url_str = el['url']
            if not url_str.startswith(('http://', 'https://')):
                return b'[image error: invalid URL scheme]\n'
            req = urllib.request.Request(url_str, headers={'User-Agent': 'PrinterAPI/1.0'})
            raw = urllib.request.urlopen(req, timeout=10).read()
        else:
            return b''
        # Convert SVG to PNG first
        is_svg = (
            raw.lstrip()[:5] in (b'<?xml', b'<svg ') or
            raw.lstrip()[:4] == b'<svg' or
            el.get('url', '').lower().endswith('.svg')
        )
        if is_svg:
            raw = _svg_to_png(raw)
        return _image_to_escpos(Image.open(BytesIO(raw)))
    except Exception as e:
        logging.getLogger(__name__).warning('image render error: %s', e)
        return b'[image error]\n'


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
