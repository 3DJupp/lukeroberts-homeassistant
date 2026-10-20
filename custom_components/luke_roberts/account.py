"""The Luke Roberts account: one API key for every lamp, like the phone app.

The account entry holds the personal API key. When it is set up it lists the
lamps of the account, links Bluetooth lamps that are already configured to
their cloud counterpart (by serial number or name) and offers the remaining
lamps as discovered devices. Lamp entries without an API key of their own use
the account key for the cloud fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import (
    SOURCE_INTEGRATION_DISCOVERY,
    ConfigEntry,
    ConfigEntryState,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, discovery_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .cloud import CloudAuthError, CloudError, CloudLamp, LukeRobertsCloud
from .const import CONF_ACCOUNT, CONF_API_KEY, CONF_CLOUD_LAMP_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class LukeRobertsAccount:
    """Runtime data of the account entry."""

    cloud: LukeRobertsCloud
    lamps: list[CloudLamp]


type LukeRobertsAccountEntry = ConfigEntry[LukeRobertsAccount]


def is_account_entry(entry: ConfigEntry) -> bool:
    """The entry is the account, not a lamp."""
    return bool(entry.data.get(CONF_ACCOUNT))


@callback
def async_account_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the enabled account entry, if one was added."""
    for entry in hass.config_entries.async_entries(DOMAIN, include_ignore=False):
        if is_account_entry(entry) and entry.disabled_by is None:
            return entry
    return None


@callback
def async_account_api_key(hass: HomeAssistant) -> str | None:
    """The account API key, readable before the account entry is loaded."""
    entry = async_account_entry(hass)
    return entry.data.get(CONF_API_KEY) if entry else None


@callback
def async_loaded_account(hass: HomeAssistant) -> LukeRobertsAccount | None:
    """Return the account runtime data once it is set up."""
    entry = async_account_entry(hass)
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        return None
    return entry.runtime_data


def _lamp_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN, include_ignore=False)
        if not is_account_entry(entry)
    ]


def _linked_id(entry: ConfigEntry) -> int | None:
    value = entry.options.get(CONF_CLOUD_LAMP_ID, entry.data.get(CONF_CLOUD_LAMP_ID))
    return int(value) if value is not None else None


@callback
def async_linked_lamp_ids(hass: HomeAssistant) -> set[int]:
    """Cloud lamp ids that already belong to a lamp entry."""
    return {
        lamp_id
        for entry in _lamp_entries(hass)
        if (lamp_id := _linked_id(entry)) is not None
    }


@callback
def _abort_discovery(hass: HomeAssistant, lamp_id: int) -> None:
    for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        context = flow["context"]
        if (
            context.get("source") == SOURCE_INTEGRATION_DISCOVERY
            and context.get("unique_id") == f"cloud_{lamp_id}"
        ):
            hass.config_entries.flow.async_abort(flow["flow_id"])


@callback
def async_link_lamps(hass: HomeAssistant, lamps: list[CloudLamp]) -> None:
    """Link unlinked Bluetooth lamps to their cloud lamp.

    Matches on the serial number read from the lamp, then on a unique name.
    Lamps with an API key of their own are left alone, the user manages them.
    """
    linked = async_linked_lamp_ids(hass)
    candidates = [lamp for lamp in lamps if lamp.lamp_id not in linked]
    if not candidates:
        return
    registry = dr.async_get(hass)
    for entry in _lamp_entries(hass):
        if (
            CONF_ADDRESS not in entry.data
            or _linked_id(entry) is not None
            or CONF_API_KEY in entry.options
        ):
            continue
        device = registry.async_get_device(identifiers={(DOMAIN, entry.unique_id)})
        serial = (device.serial_number or "").strip().casefold() if device else ""
        match = next(
            (
                lamp
                for lamp in candidates
                if serial and (lamp.serial_number or "").strip().casefold() == serial
            ),
            None,
        )
        if match is None:
            name = (entry.data.get(CONF_NAME) or entry.title).strip().casefold()
            named = [lamp for lamp in candidates if lamp.name.casefold() == name]
            match = named[0] if len(named) == 1 else None
        if match is None:
            continue
        _LOGGER.info("Linking %s to cloud lamp %s", entry.title, match.lamp_id)
        candidates.remove(match)
        _abort_discovery(hass, match.lamp_id)
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_CLOUD_LAMP_ID: match.lamp_id}
        )


async def async_setup_account(
    hass: HomeAssistant, entry: LukeRobertsAccountEntry
) -> bool:
    """Load the lamp list, link known lamps and offer the others."""
    api_key: str = entry.data[CONF_API_KEY]
    cloud = LukeRobertsCloud(async_get_clientsession(hass), api_key)
    try:
        lamps = await cloud.get_lamps()
    except CloudAuthError as err:
        raise ConfigEntryAuthFailed("Luke Roberts cloud rejected the API key") from err
    except CloudError as err:
        raise ConfigEntryNotReady(f"Luke Roberts cloud not reachable: {err}") from err
    entry.runtime_data = LukeRobertsAccount(cloud=cloud, lamps=lamps)

    async_link_lamps(hass, lamps)

    linked = async_linked_lamp_ids(hass)
    for lamp in lamps:
        if lamp.lamp_id in linked:
            continue
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_CLOUD_LAMP_ID: lamp.lamp_id, CONF_NAME: lamp.name},
        )

    # Linked lamps that were set up without the account, or with an older
    # account key, pick up the current one.
    for lamp_entry in _lamp_entries(hass):
        if (
            lamp_entry.state is ConfigEntryState.LOADED
            and CONF_API_KEY not in lamp_entry.options
            and CONF_API_KEY not in lamp_entry.data
            and _linked_id(lamp_entry) is not None
            and (
                lamp_entry.runtime_data.cloud is None
                or lamp_entry.runtime_data.cloud.api_key != api_key
            )
        ):
            hass.config_entries.async_schedule_reload(lamp_entry.entry_id)
    return True
