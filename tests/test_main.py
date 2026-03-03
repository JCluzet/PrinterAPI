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
    body = response.json()
    assert any('base64' in str(err.get('msg', '')) for err in body.get('detail', []))


def test_print_returns_error_on_printer_failure():
    payload = {'raw': base64.b64encode(b'test').decode()}
    with patch('src.main.print_raw', side_effect=OSError('device busy')):
        response = client.post('/print', json=payload)
    assert response.status_code == 500
    assert response.json()['detail'] == 'device busy'


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
