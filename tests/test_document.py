# tests/test_document.py
import base64
import pytest
from unittest.mock import patch, MagicMock
from src.document import document_to_escpos


def test_init_resets_printer():
    result = document_to_escpos([])
    assert result[:2] == b'\x1b@'


def test_title_element():
    result = document_to_escpos([{'type': 'title', 'text': 'Hello'}])
    assert b'Hello' in result
    assert b'\x1d!\x11' in result  # double size


def test_text_element_defaults():
    result = document_to_escpos([{'type': 'text', 'content': 'World'}])
    assert b'World' in result


def test_text_element_bold():
    result = document_to_escpos([{'type': 'text', 'content': 'X', 'bold': True}])
    assert b'\x1bE\x01' in result
    assert b'\x1bE\x00' in result


def test_text_element_align_center():
    result = document_to_escpos([{'type': 'text', 'content': 'X', 'align': 'center'}])
    assert b'\x1ba\x01' in result


def test_kv_element():
    result = document_to_escpos([{'type': 'kv', 'key': 'Foo', 'value': 'Bar'}])
    assert b'Foo' in result
    assert b'Bar' in result
    assert b'.' in result


def test_separator_element():
    result = document_to_escpos([{'type': 'separator'}])
    assert b'---' in result


def test_feed_element():
    result = document_to_escpos([{'type': 'feed', 'lines': 3}])
    assert result.count(b'\n') >= 3


def test_qr_element():
    result = document_to_escpos([{'type': 'qr', 'url': 'https://example.com'}])
    assert b'https://example.com' in result
    assert b'\x1d(k' in result


def test_cut_element():
    result = document_to_escpos([{'type': 'cut'}])
    assert b'\x1dV' in result


def test_unknown_element_skipped():
    result = document_to_escpos([{'type': 'unicorn', 'data': 'whatever'}])
    assert result[:2] == b'\x1b@'


def test_image_base64_element():
    png_1x1 = (
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8'
        'z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=='
    )
    result = document_to_escpos([{'type': 'image', 'data': png_1x1}])
    assert b'\x1dv\x30' in result


def test_image_invalid_base64_skips():
    result = document_to_escpos([{'type': 'image', 'data': 'not-valid!!!'}])
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
    assert b'\x1dv\x30' in result
