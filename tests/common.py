"""Shared helpers for Luke Roberts tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import time

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from custom_components.luke_roberts.const import SCENE_CHAR_UUID, SERVICE_UUID

ADDRESS = "AA:BB:CC:DD:EE:FF"


def service_info(
    address: str = ADDRESS, name: str = "Luke Roberts Model F"
) -> BluetoothServiceInfoBleak:
    """Build an advertisement as seen through an adapter or proxy."""
    device = BLEDevice(address, name, {})
    adv = AdvertisementData(
        local_name=name,
        manufacturer_data={},
        service_data={},
        service_uuids=[SERVICE_UUID],
        tx_power=-127,
        rssi=-60,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[SERVICE_UUID],
        source="esphome-proxy",
        device=device,
        advertisement=adv,
        connectable=True,
        time=time.monotonic(),
        tx_power=-127,
    )


class FakeLampClient:
    """Minimal BleakClient stand-in that answers like a lamp."""

    SCENES = {0: (1, "Off"), 1: (2, "Lesen"), 2: (0xFF, "Gemütlich")}

    def __init__(self) -> None:
        self.is_connected = True
        self.written: list[bytes] = []
        self.scenes: dict[int, str] = {
            scene_id: name for scene_id, (_next, name) in self.SCENES.items()
        }
        self.sync_version = 1
        self.software = b"1.3.2\x00"
        self._callback: Callable[[object, bytearray], None] | None = None

    async def start_notify(self, _uuid: str, callback) -> None:
        self._callback = callback

    async def write_gatt_char(self, uuid: str, data: bytes, response: bool) -> None:
        self.written.append(bytes(data))
        if uuid == SCENE_CHAR_UUID:
            reply = self.store_scene(bytes(data))
        else:
            reply = self.respond(bytes(data))
        assert self._callback is not None
        asyncio.get_running_loop().call_soon(self._callback, None, bytearray(reply))

    def respond(self, frame: bytes) -> bytes:
        opcode = frame[2]
        if opcode == 0x00:
            return bytes([0x00, 0x02])
        if opcode == 0x01:
            ids = sorted(self.scenes)
            index = ids.index(frame[3])
            next_id = ids[index + 1] if index + 1 < len(ids) else 0xFF
            return (
                bytes([0x00, 0x01, next_id]) + self.scenes[frame[3]].encode() + b"\x00"
            )
        return b"\x00"

    def store_scene(self, record: bytes) -> bytes:
        """Scene records like the lamp: new ids are assigned, type 0 deletes."""
        scene_id, scene_type = record[1], record[3]
        if scene_type == 0:
            self.scenes.pop(scene_id, None)
        else:
            if scene_id == 0xFE:
                scene_id = max(self.scenes) + 1
            self.scenes[scene_id] = record[-20:].split(b"\x00", 1)[0].decode()
        self.sync_version += 1
        return b"\x00" + self.sync_version.to_bytes(4, "big") + bytes([scene_id, 0])

    async def read_gatt_char(self, uuid: str) -> bytes:
        return {
            "00002a24-0000-1000-8000-00805f9b34fb": b"Model F\x00",
            "00002a26-0000-1000-8000-00805f9b34fb": b"21.3",
            "00002a28-0000-1000-8000-00805f9b34fb": self.software,
        }.get(uuid, b"")

    async def disconnect(self) -> None:
        self.is_connected = False
