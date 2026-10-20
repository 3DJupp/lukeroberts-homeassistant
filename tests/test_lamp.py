"""Routing and assumed state of LukeRobertsLamp."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from bleak.exc import BleakError
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.luke_roberts import protocol
from custom_components.luke_roberts.const import (
    MODE_CLOUD_FIRST,
    MODE_LOCAL_FIRST,
    MODE_LOCAL_ONLY,
)
from custom_components.luke_roberts.lamp import (
    ROUTE_BLUETOOTH,
    ROUTE_CLOUD,
    LukeRobertsLamp,
)

OK = b"\x00"


def _ble(responses: list[bytes] | Exception | None = None) -> MagicMock:
    ble = MagicMock()
    if isinstance(responses, Exception):
        ble.request = AsyncMock(side_effect=responses)
        ble.request_many = AsyncMock(side_effect=responses)
    else:
        ble.request = AsyncMock(side_effect=responses or [OK] * 10)
        ble.request_many = AsyncMock(side_effect=lambda frames: [OK] * len(frames))
    return ble


def _lamp(mode: str, ble: MagicMock | None, cloud: MagicMock | None) -> LukeRobertsLamp:
    return LukeRobertsLamp(
        name="Test", mode=mode, ble=ble, cloud=cloud, cloud_lamp_id=7 if cloud else None
    )


async def test_turn_on_local_selects_default_then_adjusts() -> None:
    """From off: default scene, brightness, colour temperature in one go."""
    ble = _ble()
    lamp = _lamp(MODE_LOCAL_FIRST, ble, None)
    await lamp.turn_on(brightness=40, kelvin=3000)
    ble.request_many.assert_awaited_once_with(
        [
            protocol.select_scene(0xFF),
            protocol.brightness(40),
            protocol.color_temperature(3000),
        ]
    )
    assert lamp.state.is_on
    assert lamp.state.brightness == 40
    assert lamp.state.kelvin == 3000
    assert lamp.state.last_route == ROUTE_BLUETOOTH


async def test_turn_on_while_on_only_adjusts() -> None:
    """When already on, only the changed attribute is sent."""
    ble = _ble()
    lamp = _lamp(MODE_LOCAL_FIRST, ble, None)
    lamp.state.is_on = True
    await lamp.turn_on(brightness=70)
    ble.request_many.assert_awaited_once_with([protocol.brightness(70)])


async def test_fallback_to_cloud_when_ble_fails() -> None:
    """Local first: a Bluetooth error falls back to the cloud."""
    ble = _ble(BleakError("out of range"))
    cloud = MagicMock(power=AsyncMock(), brightness=AsyncMock(), scene=AsyncMock())
    lamp = _lamp(MODE_LOCAL_FIRST, ble, cloud)
    await lamp.turn_on(brightness=55)
    cloud.power.assert_awaited_once_with(7, True)
    cloud.brightness.assert_awaited_once_with(7, 55)
    assert lamp.state.last_route == ROUTE_CLOUD


async def test_forbidden_falls_back_to_cloud() -> None:
    """A lamp with a security code still works through the cloud."""
    ble = MagicMock(request=AsyncMock(return_value=b"\xfc"))
    cloud = MagicMock(power=AsyncMock())
    lamp = _lamp(MODE_LOCAL_FIRST, ble, cloud)
    await lamp.turn_off()
    cloud.power.assert_awaited_once_with(7, False)
    assert lamp.state.is_on is False


async def test_local_only_does_not_use_cloud() -> None:
    """Local only never touches the cloud and surfaces the error."""
    ble = _ble(BleakError("gone"))
    cloud = MagicMock(power=AsyncMock())
    lamp = _lamp(MODE_LOCAL_ONLY, ble, cloud)
    with pytest.raises(HomeAssistantError, match="bluetooth"):
        await lamp.turn_off()
    cloud.power.assert_not_awaited()


async def test_cloud_first() -> None:
    """Cloud first uses the cloud even when BLE would work."""
    ble = _ble()
    cloud = MagicMock(scene=AsyncMock())
    lamp = _lamp(MODE_CLOUD_FIRST, ble, cloud)
    await lamp.select_scene(4)
    cloud.scene.assert_awaited_once_with(7, 4)
    ble.request_many.assert_not_awaited()
    assert lamp.state.scene_id == 4


async def test_ble_only_action_without_ble() -> None:
    """Next scene needs Bluetooth."""
    lamp = _lamp(MODE_LOCAL_FIRST, None, MagicMock())
    with pytest.raises(HomeAssistantError, match="needs a Bluetooth"):
        await lamp.next_scene(1)


async def test_lamp_error_is_raised() -> None:
    """Invalid id is reported, not silently retried via cloud."""
    ble = MagicMock(request=AsyncMock(return_value=b"\x84"))
    cloud = MagicMock(scene=AsyncMock())
    lamp = _lamp(MODE_LOCAL_FIRST, ble, cloud)
    with pytest.raises(HomeAssistantError, match="INVALID_ID"):
        await lamp.next_scene(1)
    assert lamp.state.last_status == "INVALID_ID"


async def test_refresh_scenes_walks_list() -> None:
    """Query Scene is repeated with the next id until 0xFF."""

    def scene(next_id: int, name: str) -> bytes:
        return bytes([0, 1, next_id]) + name.encode() + b"\x00"

    ble = MagicMock(
        request=AsyncMock(
            side_effect=[scene(3, "Off"), scene(1, "Lesen"), scene(0xFF, "Kino")]
        )
    )
    lamp = _lamp(MODE_LOCAL_FIRST, ble, None)
    scenes = await lamp.refresh_scenes()
    assert scenes == {0: "Off", 3: "Lesen", 1: "Kino"}
    assert [c.args[0] for c in ble.request.await_args_list] == [
        protocol.query_scene(0),
        protocol.query_scene(3),
        protocol.query_scene(1),
    ]
    assert lamp.scene_options() == {"Default": 0xFF, "Off": 0, "Lesen": 3, "Kino": 1}


def test_scene_options_duplicates() -> None:
    """Duplicate names get their id appended so they stay addressable."""
    lamp = _lamp(MODE_LOCAL_FIRST, _ble(), None)
    lamp.state.scenes = {0: "Off", 1: "Hell", 2: "Hell"}
    assert lamp.scene_options() == {
        "Default": 0xFF,
        "Off": 0,
        "Hell (1)": 1,
        "Hell (2)": 2,
    }


def test_scene_options_cloud_only() -> None:
    """Without names, cloud only offers ids 1..31."""
    lamp = _lamp("cloud_only", None, MagicMock())
    options = lamp.scene_options()
    assert options["Scene 31"] == 31
    assert options["Off"] == 0


async def test_ping_falls_back_to_v1() -> None:
    """Old firmware rejects Ping@V=02 with Invalid Version."""
    ble = MagicMock(request=AsyncMock(side_effect=[b"\x87", b"\x00"]))
    lamp = _lamp(MODE_LOCAL_FIRST, ble, None)
    assert await lamp.ping() == 1
