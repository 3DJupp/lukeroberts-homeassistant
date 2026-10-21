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


def test_static_scene_record() -> None:
    """Scene record layout of the Luke Roberts app 2.4.0."""
    record = protocol.static_scene(
        protocol.SCENE_NEW,
        "Abend",
        Uplight(saturation=0, hue=3000, brightness=0x80),
        Downlight(kelvin=2900, brightness=0xFF),
    )
    assert len(record) == 178
    assert record[:8].hex(" ") == "01 fe 00 01 00 00 00 00"
    assert record[8:10].hex(" ") == "0b 54"
    assert record[10:14].hex(" ") == "00 0b b8 80"  # white segment, Kelvin
    assert record[10:74] == record[10:14] * 16
    assert record[74:158] == b"\xff" * 84
    assert record[158:] == b"Abend" + b"\x00" * 15


def test_static_scene_colour_and_lists() -> None:
    """Colour segments carry hue, per spot downlight keeps 2700 K."""
    segments = [Uplight(saturation=255, hue=0x8000, brightness=10)] * 16
    record = protocol.static_scene(3, "x" * 30, segments, list(range(84)))
    assert record[1] == 3
    assert record[8:10].hex(" ") == "0a 8c"
    assert record[10:14].hex(" ") == "ff 80 00 0a"
    assert record[74:158] == bytes(range(84))
    assert record[158:] == b"x" * 20
    with pytest.raises(ValueError):
        protocol.static_scene(3, "x", segments[:2], list(range(84)))


def test_scene_name_does_not_split_characters() -> None:
    """A multi-byte character at the limit is dropped, not cut."""
    record = protocol.static_scene(
        3, "a" * 19 + "ü", Uplight(0, 2700, 0), Downlight(2700, 0)
    )
    assert record[158:] == b"a" * 19 + b"\x00"


def test_delete_scene_record() -> None:
    """Deleting is a header with type 0."""
    assert protocol.delete_scene(4).hex(" ") == "01 04 00 00 00 00 00 00"


def test_parse_scene_write() -> None:
    """The lamp answers with sync version, scene id and sort index."""
    result = protocol.parse_scene_write(bytes.fromhex("00 00 00 00 07 05 02"))
    assert result == protocol.SceneWrite(sync_version=7, scene_id=5, sort_index=2)
    assert protocol.parse_scene_write(b"\x00").scene_id is None
    with pytest.raises(protocol.LampError):
        protocol.parse_scene_write(b"\x85")
    with pytest.raises(protocol.LampForbiddenError):
        protocol.parse_scene_write(b"\xfd")
