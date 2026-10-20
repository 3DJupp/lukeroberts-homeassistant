"""Diagnostics for Luke Roberts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import LukeRobertsConfigEntry
from .account import is_account_entry
from .const import CONF_API_KEY

TO_REDACT = {CONF_API_KEY, "serial_number"}


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
    return {
        "entry": entry_info,
        "mode": lamp.mode,
        "has_local": lamp.has_local,
        "has_cloud": lamp.has_cloud,
        "ble_present": lamp.ble_present,
        "ble_connected": lamp.ble.connected if lamp.ble else None,
        "state": async_redact_data(asdict(lamp.state), TO_REDACT),
    }
