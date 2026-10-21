"""BLE transport: request/response, keepalive and releasing the link."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from custom_components.luke_roberts import protocol
from custom_components.luke_roberts.ble import LukeRobertsBle
from custom_components.luke_roberts.const import SCENE_CHAR_UUID

from .common import FakeLampClient, service_info


async def test_request_and_linger() -> None:
    """Pings keep the link while active, then it is released for the app."""
    client = FakeLampClient()
    connect = AsyncMock(return_value=client)
    with (
        patch("custom_components.luke_roberts.ble.establish_connection", connect),
        patch("custom_components.luke_roberts.ble.KEEPALIVE_INTERVAL", 0.05),
    ):
        ble = LukeRobertsBle(service_info().device, "Lamp", linger=0.2)
        assert await ble.request(protocol.select_scene(1)) == b"\x00"
        assert ble.connected
        await asyncio.sleep(0.12)
        assert protocol.ping() in client.written
        await asyncio.sleep(0.25)
        assert not ble.connected
        assert not client.is_connected

        # The next command reconnects transparently.
        client.is_connected = True
        await ble.request(protocol.select_scene(0))
        assert connect.await_count == 2
        await ble.disconnect()


async def test_request_many_single_connection() -> None:
    """Several frames share one connection."""
    client = FakeLampClient()
    connect = AsyncMock(return_value=client)
    with patch("custom_components.luke_roberts.ble.establish_connection", connect):
        ble = LukeRobertsBle(service_info().device, "Lamp", linger=0)
        frames = [protocol.select_scene(0xFF), protocol.brightness(10)]
        assert await ble.request_many(frames) == [b"\x00", b"\x00"]
        assert client.written == frames
        assert connect.await_count == 1
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not ble.connected


async def test_device_info() -> None:
    """Device Information Service strings are decoded."""
    client = FakeLampClient()
    with patch(
        "custom_components.luke_roberts.ble.establish_connection",
        AsyncMock(return_value=client),
    ):
        ble = LukeRobertsBle(service_info().device, "Lamp", linger=0)
        assert await ble.read_device_info() == {
            "model": "Model F",
            "firmware": "21.3",
            "software": "1.3.2",
        }
        await ble.disconnect()


async def test_write_record_answer_on_api_char() -> None:
    """Scene records go to their characteristic, the answer comes on the API."""
    client = FakeLampClient()
    with patch(
        "custom_components.luke_roberts.ble.establish_connection",
        AsyncMock(return_value=client),
    ):
        ble = LukeRobertsBle(service_info().device, "Lamp", linger=0)
        answer = await ble.write_record(SCENE_CHAR_UUID, protocol.delete_scene(2))
        assert answer == bytes.fromhex("00 00 00 00 02 02 00")
        assert 2 not in client.scenes
        await ble.disconnect()
