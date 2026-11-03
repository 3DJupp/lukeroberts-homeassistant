"""Frame layout tests against the Lamp Control API v1.3 document."""

from __future__ import annotations

import pytest

from custom_components.luke_roberts import protocol
from custom_components.luke_roberts.protocol import Downlight, Uplight


@pytest.mark.parametrize(
    ("frame", "expected"),
    [
        (protocol.ping(), "a0 02 00"),
        (protocol.ping_v1(), "a0 01 00"),
        (protocol.query_scene(0), "a0 01 01 00"),
        (protocol.select_scene(0), "a0 02 05 00"),
        (protocol.select_scene(0xFF), "a0 02 05 ff"),
        (protocol.select_scene(3), "a0 02 05 03"),
        (protocol.brightness(50), "a0 01 03 32"),
        (protocol.brightness(150), "a0 01 03 64"),
        (protocol.color_temperature(3000), "a0 01 04 0b b8"),
        (protocol.color_temperature(2000), "a0 01 04 0a 8c"),
        (protocol.color_temperature(9000), "a0 01 04 0f a0"),
        (protocol.next_scene_by_brightness(1), "a0 02 06 01"),
        (protocol.next_scene_by_brightness(-1), "a0 02 06 ff"),
        (protocol.adjust_color_temperature(-100), "a0 02 07 ff 9c"),
        (protocol.relative_brightness(120), "a0 02 08 78"),
        (protocol.relative_brightness(80), "a0 02 08 50"),
    ],
)
def test_frames(frame: bytes, expected: str) -> None:
    """Every builder produces the documented bytes."""
    assert frame.hex(" ") == expected


def test_immediate_light_downlight() -> None:
    """Same frame as the ESPHome gateway's 'Immediate: Downlight 50% 3000K'."""
    frame = protocol.immediate_light(downlight=Downlight(kelvin=3000, brightness=0x80))
    assert frame.hex(" ") == "a0 01 02 02 00 00 0b b8 80"


def test_immediate_light_both() -> None:
    """Uplight packet comes before the downlight packet, flags 0x03."""
    frame = protocol.immediate_light(
        uplight=Uplight(saturation=255, hue=0x1234, brightness=200),
        downlight=Downlight(kelvin=4000, brightness=255),
        duration_ms=5000,
    )
    assert frame.hex(" ") == "a0 01 02 03 13 88 ff 12 34 c8 0f a0 ff"


def test_immediate_light_requires_content() -> None:
    """At least one sub-packet is needed."""
    with pytest.raises(ValueError):
        protocol.immediate_light()


def test_parse_query_scene() -> None:
    """Scene name with next id and null terminator."""
    info = protocol.parse_query_scene(1, bytes.fromhex("00 01 03") + b"Lesen" + b"\x00")
    assert info == protocol.SceneInfo(scene_id=1, name="Lesen", next_id=3)


def test_parse_query_scene_utf8_without_terminator() -> None:
    """Non-ASCII names decode, missing terminator is tolerated."""
    info = protocol.parse_query_scene(2, bytes([0, 1, 0xFF]) + "Gemütlich".encode())
    assert info.name == "Gemütlich"
    assert info.next_id == 0xFF


def test_parse_ping() -> None:
    """Ping@V=02 returns the API version."""
    assert protocol.parse_ping(bytes([0x00, 0x02])) == 2
    assert protocol.parse_ping(bytes([0x00])) == 1


@pytest.mark.parametrize("status", [0x81, 0x84, 0x87, 0xBC])
def test_error_status(status: int) -> None:
    """Non-OK status raises LampError."""
    with pytest.raises(protocol.LampError) as err:
        protocol.check_status(bytes([status]))
    assert not isinstance(err.value, protocol.LampForbiddenError)
    assert err.value.status == status


def test_forbidden() -> None:
    """0xFC means a security code is set."""
    with pytest.raises(protocol.LampForbiddenError):
        protocol.check_status(bytes([0xFC]))


def test_empty_response() -> None:
    """An empty response is an error."""
    with pytest.raises(protocol.LampError):
        protocol.check_status(b"")
