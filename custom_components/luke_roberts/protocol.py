"""Frame builders and parsers for the Luke Roberts Lamp Control API v1.3.

Pure Python, no Home Assistant or Bluetooth imports, so it can be unit tested
on its own. All multi-byte numbers are big endian. Every command starts with
the prefix ``A0`` followed by the API version byte (``01`` or ``02``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import struct

PREFIX = 0xA0


class Status(IntEnum):
    """Status codes delivered in byte 0 of every response."""

    OK = 0x00
    INVALID_PARAMETERS = 0x81
    INVALID_ID = 0x84
    MEMORY_FULL = 0x85
    INVALID_VERSION = 0x87
    BAD_COMMAND = 0xBC
    FORBIDDEN = 0xFC
    LOCKED = 0xFD


class Opcode(IntEnum):
    """External API opcodes."""

    PING = 0x00
    QUERY_SCENE = 0x01
    IMMEDIATE_LIGHT = 0x02
    BRIGHTNESS = 0x03
    COLOR_TEMPERATURE = 0x04
    SELECT_SCENE = 0x05
    NEXT_SCENE_BY_BRIGHTNESS = 0x06
    ADJUST_COLOR_TEMPERATURE = 0x07
    RELATIVE_BRIGHTNESS = 0x08


# Undocumented single byte command that returns the light state, see
# ``query_state``. It has no ``A0`` prefix and no version byte.
QUERY_STATE = 0x09
STATE_MAGIC = bytes([0x00, 0x88, 0xF4, 0x18, 0x71])
STATE_LENGTH = 9


class LampError(Exception):
    """The lamp answered with a non-OK status."""

    def __init__(self, status: int) -> None:
        self.status = status
        try:
            name = Status(status).name
        except ValueError:
            name = "UNKNOWN"
        super().__init__(f"Lamp returned status 0x{status:02X} ({name})")


class LampForbiddenError(LampError):
    """The lamp has a security code set and rejects API commands (0xFC/0xFD)."""


def status_name(status: int) -> str:
    """Return a readable name for a status byte."""
    try:
        return Status(status).name
    except ValueError:
        return f"0x{status:02X}"


def check_status(response: bytes) -> None:
    """Raise if the response carries an error status."""
    if not response:
        raise LampError(-1)
    status = response[0]
    if status in (Status.FORBIDDEN, Status.LOCKED):
        raise LampForbiddenError(status)
    if status != Status.OK:
        raise LampError(status)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


# --- Command builders --------------------------------------------------------


def ping() -> bytes:
    """Ping@V=02, response ``00 VV`` with the highest supported API version."""
    return bytes([PREFIX, 0x02, Opcode.PING])


def ping_v1() -> bytes:
    """Ping@V=01 for firmware older than 1.0.7."""
    return bytes([PREFIX, 0x01, Opcode.PING])


def query_scene(scene_id: int) -> bytes:
    """01 Query Scene."""
    return bytes([PREFIX, 0x01, Opcode.QUERY_SCENE, scene_id & 0xFF])


def select_scene(scene_id: int) -> bytes:
    """05 Select Scene. ``0x00`` is off, ``0xFF`` the default (power-up) scene."""
    return bytes([PREFIX, 0x02, Opcode.SELECT_SCENE, scene_id & 0xFF])


def brightness(percent: int) -> bytes:
    """03 Modify Brightness of the current scene, 0..100 %."""
    return bytes([PREFIX, 0x01, Opcode.BRIGHTNESS, _clamp(percent, 0, 100)])


def color_temperature(kelvin: int) -> bytes:
    """04 Modify Color Temperature of the downlight, 2700..4000 K."""
    return bytes([PREFIX, 0x01, Opcode.COLOR_TEMPERATURE]) + struct.pack(
        ">H", _clamp(kelvin, 2700, 4000)
    )


def next_scene_by_brightness(direction: int) -> bytes:
    """06 Next Scene by Brightness, +1 brighter, -1 dimmer."""
    return bytes([PREFIX, 0x02, Opcode.NEXT_SCENE_BY_BRIGHTNESS]) + struct.pack(
        ">b", 1 if direction >= 0 else -1
    )


def adjust_color_temperature(increment: int) -> bytes:
    """07 Adjust Color Temperature by a signed Kelvin increment."""
    return bytes([PREFIX, 0x02, Opcode.ADJUST_COLOR_TEMPERATURE]) + struct.pack(
        ">h", _clamp(increment, -32768, 32767)
    )


def relative_brightness(delta: int) -> bytes:
    """08 Relative Brightness, signed change of the current brightness.

    The API document says the brightness is multiplied by PP/100; on the lamp
    the byte is a signed change in percentage points, as the app 2.4.0 uses it.
    """
    return bytes([PREFIX, 0x02, Opcode.RELATIVE_BRIGHTNESS]) + struct.pack(
        ">b", _clamp(delta, -128, 127)
    )


def query_state() -> bytes:
    """Undocumented ``09``: ask for brightness, colour temperature and on/off.

    Not part of the Lamp Control API v1.3. Taken from
    github.com/martgras/LukeRobertsControl and confirmed on a Model F with
    firmware 1.2.2, see ``parse_state`` for the answer.
    """
    return bytes([QUERY_STATE])


@dataclass(frozen=True, slots=True)
class Uplight:
    """Uplight sub-packet of Immediate Light (indirect, colour capable)."""

    saturation: int  # 0..255, 0 = white light using ``hue`` as Kelvin
    hue: int  # 0..65535, or Kelvin 2700..4000 when saturation is 0
    brightness: int  # 0..255


@dataclass(frozen=True, slots=True)
class Downlight:
    """Downlight sub-packet of Immediate Light (direct, white only)."""

    kelvin: int  # 2700..4000
    brightness: int  # 0..255


def immediate_light(
    uplight: Uplight | None = None,
    downlight: Downlight | None = None,
    duration_ms: int = 0,
) -> bytes:
    """02 Immediate Light, a transient modification of the current scene.

    ``duration_ms`` 0 means infinite, otherwise the lamp reverts afterwards.
    """
    if uplight is None and downlight is None:
        raise ValueError("At least one of uplight or downlight is required")
    flags = 0
    payload = b""
    if uplight is not None:
        flags |= 0x01
        payload += struct.pack(
            ">BHB",
            _clamp(uplight.saturation, 0, 255),
            _clamp(uplight.hue, 0, 0xFFFF),
            _clamp(uplight.brightness, 0, 255),
        )
    if downlight is not None:
        flags |= 0x02
        payload += struct.pack(
            ">HB",
            _clamp(downlight.kelvin, 2700, 4000),
            _clamp(downlight.brightness, 0, 255),
        )
    return (
        bytes([PREFIX, 0x01, Opcode.IMMEDIATE_LIGHT, flags])
        + struct.pack(">H", _clamp(duration_ms, 0, 0xFFFF))
        + payload
    )


# --- Response parsers ---------------------------------------------------------


def parse_ping(response: bytes) -> int:
    """Return the highest API version from a Ping@V=02 response (1 if absent)."""
    check_status(response)
    return response[1] if len(response) > 1 else 1


@dataclass(frozen=True, slots=True)
class SceneInfo:
    """One entry of the scene list."""

    scene_id: int
    name: str
    next_id: int


def parse_query_scene(scene_id: int, response: bytes) -> SceneInfo:
    """Parse ``00 01 NN <utf-8 name> 00``."""
    check_status(response)
    if len(response) < 3:
        raise LampError(Status.INVALID_PARAMETERS)
    next_id = response[2]
    raw = response[3:]
    end = raw.find(b"\x00")
    if end >= 0:
        raw = raw[:end]
    name = raw.decode("utf-8", errors="replace").strip()
    return SceneInfo(scene_id=scene_id, name=name, next_id=next_id)


@dataclass(frozen=True, slots=True)
class LightState:
    """State reported by the lamp in answer to ``query_state``."""

    is_on: bool
    brightness: int  # percent 0..100, same scale as opcode 03
    kelvin: int  # same value as opcode 04 sets


def parse_state(response: bytes) -> LightState | None:
    """Parse ``00 88 F4 18 71 KK KK BB FF``, None for any other answer.

    ``KK KK`` is the colour temperature in Kelvin, little endian (unlike the
    rest of the API), ``BB`` the brightness in percent and ``FF`` ``01`` while
    the lamp is on and ``00`` while it is off (brightness then reads 0). Only
    this exact shape is accepted, so firmware that answers differently keeps
    the assumed state.
    """
    if len(response) != STATE_LENGTH or not response.startswith(STATE_MAGIC):
        return None
    kelvin = struct.unpack_from("<H", response, 5)[0]
    level = response[7]
    flag = response[8]
    if flag not in (0x00, 0x01) or level > 100:
        return None
    return LightState(is_on=flag == 0x01, brightness=level, kelvin=kelvin)
