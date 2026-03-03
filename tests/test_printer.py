# tests/test_printer.py
import pytest
from unittest.mock import patch, MagicMock
from src.printer import print_raw


def test_print_raw_writes_bytes_to_device():
    data = b'\x1b@Hello\n'
    with patch('src.printer.open', MagicMock()) as mock_open:
        mock_file = mock_open.return_value.__enter__.return_value
        print_raw(data, device='/dev/usb/lp0')
        mock_open.assert_called_once_with('/dev/usb/lp0', 'wb')
        mock_file.write.assert_called_once_with(data)
        mock_file.flush.assert_called_once()


def test_print_raw_raises_on_missing_device():
    with pytest.raises(OSError):
        print_raw(b'hello', device='/dev/usb/nonexistent')
