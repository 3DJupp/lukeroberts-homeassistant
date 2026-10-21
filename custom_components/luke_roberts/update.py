"""Firmware update entity for Luke Roberts.

Shows the installed firmware (read over Bluetooth) and, with a firmware key in
the lamp options, the newest version from the Luke Roberts firmware server.
Installing stays with the Luke Roberts app.
"""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LukeRobertsConfigEntry, _option
from .const import CONF_FIRMWARE_KEY
from .entity import LukeRobertsEntity
from .firmware import (
    FirmwareError,
    FirmwareRelease,
    async_latest_firmware,
    firmware_query,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Only lamps with Bluetooth know their firmware."""
    if CONF_ADDRESS in entry.data:
        async_add_entities([LukeRobertsFirmware(entry)])


class LukeRobertsFirmware(LukeRobertsEntity, UpdateEntity):
    """Installed and newest firmware of the lamp."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "firmware"
    _attr_should_poll = True

    def __init__(self, entry: LukeRobertsConfigEntry) -> None:
        super().__init__(entry, "firmware")
        self._api_key: str | None = _option(entry, CONF_FIRMWARE_KEY) or None
        self._release: FirmwareRelease | None = None
        self._checked = False

    async def async_added_to_hass(self) -> None:
        """Check as soon as the lamp details were read over Bluetooth."""
        await super().async_added_to_hass()
        self.async_on_remove(self._lamp.add_listener(self._async_lamp_updated))

    @callback
    def _async_lamp_updated(self) -> None:
        if not self._checked and self._api_key and self._query() is not None:
            self._checked = True
            self.async_schedule_update_ha_state(force_refresh=True)

    def _query(self) -> dict[str, str] | None:
        return firmware_query(self._lamp.state.device_info)

    @property
    def available(self) -> bool:
        """Known firmware stays visible when the lamp is out of range."""
        return True

    @property
    def installed_version(self) -> str | None:
        """Firmware version read from the lamp."""
        info = self._lamp.state.device_info
        return info.get("software") or info.get("firmware")

    @property
    def latest_version(self) -> str | None:
        """Newest version from the firmware server, if checked."""
        return self._release.version if self._release is not None else None

    @property
    def release_summary(self) -> str | None:
        """Release notes of the newest version, shortened for the frontend."""
        if self._release is None or not self._release.release_notes:
            return None
        return self._release.release_notes[:255]

    async def async_update(self) -> None:
        """Ask the firmware server."""
        query = self._query()
        if not self._api_key or query is None:
            return
        self._checked = True
        try:
            self._release = await async_latest_firmware(
                async_get_clientsession(self.hass), self._api_key, query
            )
        except FirmwareError as err:
            _LOGGER.debug("%s: firmware check failed: %s", self._lamp.name, err)
