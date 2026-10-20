"""Base entity for Luke Roberts."""

from __future__ import annotations

from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import LukeRobertsConfigEntry
from .const import DOMAIN, MANUFACTURER
from .lamp import LukeRobertsLamp


class LukeRobertsEntity(Entity):
    """Common device info and state plumbing."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: LukeRobertsConfigEntry, key: str) -> None:
        self._lamp: LukeRobertsLamp = entry.runtime_data
        assert entry.unique_id is not None
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        address = entry.data.get(CONF_ADDRESS)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            connections=(
                {(dr.CONNECTION_BLUETOOTH, address.upper())} if address else set()
            ),
            manufacturer=MANUFACTURER,
            name=entry.title,
        )

    @property
    def available(self) -> bool:
        """Available while at least one route to the lamp exists."""
        return self._lamp.available

    async def async_added_to_hass(self) -> None:
        """Subscribe to lamp updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self._lamp.add_listener(self.async_write_ha_state))
