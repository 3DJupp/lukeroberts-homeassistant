"""Diagnostics for Luke Roberts."""

from __future__ import annotations

from dataclasses import asdict
import time
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import LukeRobertsConfigEntry
from .account import is_account_entry
from .const import CONF_API_KEY, CONF_FIRMWARE_KEY

TO_REDACT = {CONF_API_KEY, CONF_FIRMWARE_KEY, "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LukeRobertsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_info = {
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
    }
    if is_account_entry(entry):
        return {
            "entry": entry_info,
            "lamps": [
                {"id": lamp.lamp_id, "name": lamp.name}
                for lamp in entry.runtime_data.lamps
            ],
        }
    lamp = entry.runtime_data
    address = entry.data.get(CONF_ADDRESS)
    return {
        "entry": entry_info,
        "mode": lamp.mode,
        "has_local": lamp.has_local,
        "has_cloud": lamp.has_cloud,
        "ble_present": lamp.ble_present,
        "ble_connected": lamp.ble.connected if lamp.ble else None,
        "state": async_redact_data(asdict(lamp.state), TO_REDACT),
        "bluetooth": _bluetooth_info(hass, address) if address else None,
    }


def _bluetooth_info(hass: HomeAssistant, address: str) -> dict[str, Any]:
    """What the adapters and proxies last saw of the lamp."""
    result: dict[str, Any] = {}
    for key, connectable in (("connectable", True), ("any", False)):
        info = bluetooth.async_last_service_info(
            hass, address.upper(), connectable=connectable
        )
        result[key] = (
            {
                "name": info.name,
                "source": info.source,
                "rssi": info.rssi,
                "connectable": info.connectable,
                "service_uuids": info.service_uuids,
                "age_s": round(time.monotonic() - info.time, 1),
            }
            if info is not None
            else None
        )
    result["scanners"] = {
        scanner.source: {
            "name": scanner.name,
            "connectable": scanner.connectable,
        }
        for scanner in bluetooth.async_current_scanners(hass)
    }
    return result
