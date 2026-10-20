"""Client for the Luke Roberts Cloud REST API (third party API v1.0).

Authentication uses a personal API key created at
https://cloud.luke-roberts.com/app. Commands are queued by the backend and
forwarded to the lamp asynchronously; there is no confirmation that the lamp
executed them.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

import aiohttp

from .const import CLOUD_BASE_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class CloudError(Exception):
    """Communication with the cloud failed."""


class CloudAuthError(CloudError):
    """The API key was rejected."""


@dataclass(frozen=True, slots=True)
class CloudLamp:
    """A lamp as reported by ``GET /lamps``."""

    lamp_id: int
    name: str
    serial_number: str | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CloudState:
    """Best-effort decoded result of ``GET /lamps/{id}/state``."""

    is_on: bool | None = None
    brightness: int | None = None
    kelvin: int | None = None
    scene_id: int | None = None


class LukeRobertsCloud:
    """Thin async wrapper around the documented endpoints."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    async def _call(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        try:
            async with self._session.request(
                method,
                f"{CLOUD_BASE_URL}{path}",
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise CloudAuthError(f"HTTP {resp.status}")
                if resp.status >= 400:
                    text = await resp.text()
                    raise CloudError(f"HTTP {resp.status}: {text[:200]}")
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CloudError(str(err)) from err
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return text

    async def get_lamps(self) -> list[CloudLamp]:
        """Return all lamps of the account."""
        data = await self._call("GET", "/lamps")
        if isinstance(data, dict):
            data = data.get("lamps") or data.get("data") or []
        lamps: list[CloudLamp] = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict) or "id" not in item:
                continue
            try:
                lamp_id = int(item["id"])
            except (TypeError, ValueError):
                continue
            serial = item.get("serial_number") or item.get("serial")
            lamps.append(
                CloudLamp(
                    lamp_id=lamp_id,
                    name=str(item.get("name") or f"Lamp {lamp_id}"),
                    serial_number=str(serial) if serial else None,
                    raw=item,
                )
            )
        return lamps

    async def send(self, lamp_id: int, payload: dict[str, Any]) -> None:
        """Queue a command, e.g. ``{"power": "ON"}`` or ``{"scene": 3}``."""
        _LOGGER.debug("Cloud lamp %s <- %s", lamp_id, payload)
        await self._call("PUT", f"/lamps/{lamp_id}/command", payload)

    async def power(self, lamp_id: int, on: bool) -> None:
        """Switch on (default scene) or off."""
        await self.send(lamp_id, {"power": "ON" if on else "OFF"})

    async def brightness(self, lamp_id: int, percent: int) -> None:
        """Set the brightness of the current scene, 0..100 %."""
        await self.send(lamp_id, {"brightness": max(0, min(100, int(percent)))})

    async def kelvin(self, lamp_id: int, kelvin: int) -> None:
        """Set the downlight colour temperature, 2700..4000 K."""
        await self.send(lamp_id, {"kelvin": max(2700, min(4000, int(kelvin)))})

    async def scene(self, lamp_id: int, scene_id: int) -> None:
        """Select a scene, 0 is off."""
        await self.send(lamp_id, {"scene": int(scene_id)})

    async def get_state(self, lamp_id: int) -> CloudState:
        """Read the lamp state.

        ``GET /lamps/{id}/state`` is listed in the backend's swagger file but
        not in the third party documentation, so the payload is decoded
        defensively and unknown shapes simply yield an empty state.
        """
        data = await self._call("GET", f"/lamps/{lamp_id}/state")
        _LOGGER.debug("Cloud lamp %s state: %s", lamp_id, data)
        return parse_state(data)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_state(data: Any) -> CloudState:
    """Decode a state payload, tolerating different key names."""
    if not isinstance(data, dict):
        return CloudState()
    if isinstance(data.get("state"), dict):
        data = data["state"]

    is_on: bool | None = None
    if isinstance(data.get("on"), bool):
        is_on = data["on"]
    elif isinstance(data.get("power"), str):
        is_on = data["power"].upper() == "ON"

    kelvin = _as_int(data.get("kelvin"))
    if kelvin is None and isinstance(data.get("color"), dict):
        color = data["color"]
        kelvin = _as_int(color.get("kelvin") or color.get("temperatureK"))

    scene_id = _as_int(data.get("scene", data.get("scene_id")))
    if is_on is None and scene_id is not None:
        is_on = scene_id != 0

    return CloudState(
        is_on=is_on,
        brightness=_as_int(data.get("brightness")),
        kelvin=kelvin,
        scene_id=scene_id,
    )
