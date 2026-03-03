# src/printer.py
DEFAULT_DEVICE = '/dev/usb/lp0'


def print_raw(data: bytes, device: str = DEFAULT_DEVICE) -> None:
    """Write raw ESC/POS bytes directly to the printer device."""
    with open(device, 'wb') as f:
        f.write(data)
        f.flush()
