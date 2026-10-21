"""Firmware lookup helpers."""

from __future__ import annotations

import pytest

from custom_components.luke_roberts.firmware import (
    FirmwareError,
    FirmwareRelease,
    firmware_query,
    parse_bootloader,
    parse_release,
)


def test_parse_bootloader() -> None:
    """Units first, then tens, the fourth character is the HomeKit state."""
    assert parse_bootloader("21.3") == (12, 3)
    assert parse_bootloader("1.0.7") == (0, 0)
    assert parse_bootloader(None) == (0, 0)


def test_firmware_query() -> None:
    """Device information maps to the parameters the app sends."""
    assert firmware_query({"model": "LRF02"}) is None
    assert firmware_query({"software": "1.2.2"})["model"] == ""
    assert firmware_query(
        {
            "model": "LRF02",
            "software": "1.3.2",
            "firmware": "21.3",
            "hardware": "C",
            "serial_number": "ABC",
        }
    ) == {
        "app": "Android",
        "model": "LRF02",
        "firmware": "1.3.2",
        "revision": "C",
        "serial": "ABC",
        "bootloader": "12",
        "homekit": "3",
    }


def test_parse_release() -> None:
    """Release notes come from the history entry of the newest version."""
    assert parse_release(
        {
            "version": "1.4.0",
            "file": "https://example.invalid/fw.zip",
            "history": [
                {"version": "1.3.2", "releaseNotes": "old"},
                {"version": "1.4.0", "releaseNotes": "new"},
            ],
        }
    ) == FirmwareRelease("1.4.0", "https://example.invalid/fw.zip", "new")
    assert parse_release({}) is None  # up to date
    with pytest.raises(FirmwareError):
        parse_release({"error": "nope"})
    with pytest.raises(FirmwareError):
        parse_release([])
