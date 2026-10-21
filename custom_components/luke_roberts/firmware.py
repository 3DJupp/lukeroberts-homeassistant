"""Latest firmware lookup, the way the Luke Roberts app 2.4.0 does it.

The app asks ``GET /firmware/latest`` with the Device Information of the lamp
and an ``Api-Key`` header. The answer names the newest version, a download
link to a Nordic DFU package and release notes. Installing is left to the
app: a failed update can leave the lamp in its bootloader.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import aiohttp

from .const import FIRMWARE_BASE_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class FirmwareError(Exception):
    """The firmware lookup failed."""


@dataclass(frozen=True, slots=True)
class FirmwareRelease:
    """Answer of the firmware lookup."""

    version: str
    file: str | None
    release_notes: str | None


def parse_bootloader(revision: str | None) -> tuple[int, int]:
    """Decode the bootloader string of characteristic 2A26 like the app.

    Four characters ``<units><tens>?<homekit>``; anything else counts as 0.
    """
    if not revision or len(revision) != 4:
        return 0, 0
    raw = revision.encode("latin-1", errors="replace")
    version = (raw[0] - 48) + (raw[1] - 48) * 10
    homekit = raw[3] - 48
    return version, homekit


def firmware_query(device_info: dict[str, str]) -> dict[str, str] | None:
    """Query parameters for a lamp, None while its details are unknown."""
    model = device_info.get("model")
    firmware = device_info.get("software")
    if not model or not firmware:
        return None
    bootloader, homekit = parse_bootloader(device_info.get("firmware"))
    return {
        "app": "Android",
        "model": model,
        "firmware": firmware,
        "revision": device_info.get("hardware", ""),
        "serial": device_info.get("serial_number", ""),
        "bootloader": str(bootloader),
        "homekit": str(homekit),
    }


def parse_release(data: Any) -> FirmwareRelease:
    """Decode ``{version, file, history: [{version, releaseNotes}]}``."""
    if not isinstance(data, dict) or not data.get("version"):
        raise FirmwareError(f"Unexpected answer: {str(data)[:200]}")
    version = str(data["version"])
    notes = None
    for item in data.get("history") or []:
        if isinstance(item, dict) and str(item.get("version")) == version:
            notes = item.get("releaseNotes")
            break
    return FirmwareRelease(
        version=version,
        file=data.get("file"),
        release_notes=str(notes) if notes else None,
    )


async def async_latest_firmware(
    session: aiohttp.ClientSession, api_key: str, query: dict[str, str]
) -> FirmwareRelease:
    """Ask the firmware server for the newest version for this lamp."""
    try:
        async with session.get(
            f"{FIRMWARE_BASE_URL}/firmware/latest",
            params=query,
            headers={"Api-Key": api_key, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise FirmwareError(f"HTTP {resp.status}: {text[:200]}")
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise FirmwareError(str(err)) from err
    _LOGGER.debug("Firmware lookup %s: %s", query.get("model"), data)
    return parse_release(data)
