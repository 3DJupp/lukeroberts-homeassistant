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
from homeassistant.helpers import device_registry as dr
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

SCAN_INTERVAL = timedelta(hours=6)


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
        self._checked_version: str | None = None
        self._up_to_date = False
        self._last_error: str | None = None

    async def async_added_to_hass(self) -> None:
        """Check right away, and again once the lamp was read over Bluetooth."""
        await super().async_added_to_hass()
        self.async_on_remove(self._lamp.add_listener(self._async_lamp_updated))
        if self._api_key:
            self.async_schedule_update_ha_state(force_refresh=True)

    @callback
    def _async_lamp_updated(self) -> None:
        installed = self.installed_version
        if self._api_key and installed and installed != self._checked_version:
            self.async_schedule_update_ha_state(force_refresh=True)

    def _device_info(self) -> dict[str, str]:
        """Details read over Bluetooth, else what the device registry kept."""
        info = dict(self._lamp.state.device_info)
        if info.get("software") or self.registry_entry is None:
            return info
        device_id = self.registry_entry.device_id
        device = dr.async_get(self.hass).async_get(device_id) if device_id else None
        if device is not None:
            for key, value in (
                ("software", device.sw_version),
                ("model", device.model),
                ("hardware", device.hw_version),
                ("serial_number", device.serial_number),
            ):
                if value and key not in info:
                    info[key] = value
        return info

    @property
    def available(self) -> bool:
        """Known firmware stays visible when the lamp is out of range."""
        return True

    @property
    def installed_version(self) -> str | None:
        """Firmware version read from the lamp."""
        info = self._device_info()
        return info.get("software") or info.get("firmware")

    @property
    def latest_version(self) -> str | None:
        """Newest version from the firmware server, if checked."""
        if self._release is not None:
            return self._release.version
        return self.installed_version if self._up_to_date else None

    @property
    def release_summary(self) -> str | None:
        """Release notes of the newest version, shortened for the frontend."""
        if self._release is None or not self._release.release_notes:
            return None
        return self._release.release_notes[:255]

    async def async_update(self) -> None:
        """Ask the firmware server."""
        query = firmware_query(self._device_info())
        if not self._api_key or query is None:
            return
        self._checked_version = query["firmware"]
        try:
            release = await async_latest_firmware(
                async_get_clientsession(self.hass), self._api_key, query
            )
        except FirmwareError as err:
            if str(err) != self._last_error:
                _LOGGER.warning("%s: firmware check failed: %s", self._lamp.name, err)
            self._last_error = str(err)
            return
        self._last_error = None
        self._release = release
        self._up_to_date = release is None
