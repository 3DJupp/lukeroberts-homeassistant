"""The Luke Roberts integration.

Controls Luke Roberts smart lamps (Model F / Luvo) locally over Bluetooth LE,
using whatever adapters and Bluetooth proxies Home Assistant already has, and
optionally through the Luke Roberts cloud.
"""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .account import (
    async_account_api_key,
    async_account_entry,
    async_link_lamps,
    async_loaded_account,
    async_setup_account,
    is_account_entry,
)
from .ble import BLE_ERRORS, LukeRobertsBle
from .cloud import CloudAuthError, CloudError, LukeRobertsCloud
from .const import (
    CONF_API_KEY,
    CONF_CLOUD_LAMP_ID,
    CONF_CONNECTION_MODE,
    CONF_LINGER,
    DEFAULT_LINGER,
    DOMAIN,
    MODE_CLOUD_ONLY,
    MODE_LOCAL_FIRST,
    MODE_LOCAL_ONLY,
)
from .lamp import LukeRobertsLamp

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.UPDATE,
]

CLOUD_POLL_INTERVAL = timedelta(seconds=60)

type LukeRobertsConfigEntry = ConfigEntry[LukeRobertsLamp]


def _option(entry: ConfigEntry, key: str, default=None):
    """Options override data, so cloud settings can be added later."""
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


async def async_setup_entry(hass: HomeAssistant, entry: LukeRobertsConfigEntry) -> bool:
    """Set up a lamp or the account from a config entry."""
    if is_account_entry(entry):
        return await async_setup_account(hass, entry)

    address: str | None = entry.data.get(CONF_ADDRESS)
    name: str = entry.data.get(CONF_NAME) or entry.title
    default_mode = MODE_LOCAL_FIRST if address else MODE_CLOUD_ONLY
    mode: str = _option(entry, CONF_CONNECTION_MODE, default_mode)
    api_key: str | None = _option(entry, CONF_API_KEY)
    cloud_lamp_id = _option(entry, CONF_CLOUD_LAMP_ID)
    uses_account = False
    if not api_key and cloud_lamp_id is not None:
        api_key = async_account_api_key(hass)
        uses_account = api_key is not None
        if not api_key and not address:
            raise ConfigEntryError(
                "This lamp was added from the Luke Roberts account; "
                "add the account again to control it"
            )

    ble: LukeRobertsBle | None = None
    ble_device = None
    if address:
        ble_device = bluetooth.async_ble_device_from_address(
            hass, address.upper(), connectable=True
        )
        if ble_device is None:
            _LOGGER.info(
                "%s: %s is not seen by any connectable Bluetooth adapter or "
                "proxy. A lamp that is connected to another central (phone "
                "app, an ESP32 running the ESPHome lamp gateway) does not "
                "advertise and accepts no second connection",
                name,
                address,
            )
        if ble_device is None and mode == MODE_LOCAL_ONLY:
            raise ConfigEntryNotReady(
                f"Could not find Luke Roberts lamp {address} via any "
                "Bluetooth adapter or proxy"
            )
        if ble_device is not None:
            ble = LukeRobertsBle(
                ble_device, name, float(_option(entry, CONF_LINGER, DEFAULT_LINGER))
            )

    cloud: LukeRobertsCloud | None = None
    if api_key and cloud_lamp_id is not None:
        cloud = LukeRobertsCloud(async_get_clientsession(hass), api_key)

    lamp = LukeRobertsLamp(
        name=name,
        mode=mode,
        ble=ble,
        cloud=cloud,
        cloud_lamp_id=int(cloud_lamp_id) if cloud_lamp_id is not None else None,
    )
    lamp.ble_present = ble_device is not None
    entry.runtime_data = lamp

    if address:
        _setup_bluetooth_tracking(hass, entry, lamp, address.upper(), name)

    if lamp.has_cloud:
        await _setup_cloud_polling(hass, entry, lamp, uses_account)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    if lamp.has_local and lamp.ble_present:
        entry.async_create_background_task(
            hass,
            _async_initial_local_read(hass, entry),
            f"{entry.title} initial read",
        )
    return True


def _setup_bluetooth_tracking(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    lamp: LukeRobertsLamp,
    address: str,
    name: str,
) -> None:
    """Follow the lamp across adapters/proxies and track its presence."""

    @callback
    def _async_seen(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        if lamp.ble is None:
            linger = float(_option(entry, CONF_LINGER, DEFAULT_LINGER))
            lamp.ble = LukeRobertsBle(service_info.device, name, linger)
            entry.async_create_background_task(
                hass,
                _async_initial_local_read(hass, entry),
                f"{entry.title} initial read",
            )
        else:
            lamp.ble.set_ble_device(service_info.device)
        if not lamp.ble_present:
            lamp.ble_present = True
            lamp.notify()

    @callback
    def _async_unavailable(_service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
        if lamp.ble_present:
            lamp.ble_present = False
            lamp.notify()

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_seen,
            bluetooth.BluetoothCallbackMatcher(address=address, connectable=True),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )
    entry.async_on_unload(
        bluetooth.async_track_unavailable(
            hass, _async_unavailable, address, connectable=True
        )
    )


async def _setup_cloud_polling(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    lamp: LukeRobertsLamp,
    uses_account: bool,
) -> None:
    """Poll the (best effort) cloud state endpoint."""

    @callback
    def _reauth() -> None:
        # A rejected account key is fixed on the account, not on each lamp.
        target = async_account_entry(hass) if uses_account else entry
        if target is not None:
            target.async_start_reauth(hass)

    async def _poll(_now=None) -> None:
        try:
            await lamp.update_from_cloud()
        except CloudAuthError:
            _reauth()
        except CloudError as err:
            _LOGGER.debug("%s: cloud state not available: %s", lamp.name, err)

    try:
        await lamp.update_from_cloud()
    except CloudAuthError as err:
        if uses_account:
            _reauth()
            raise ConfigEntryNotReady(
                "Luke Roberts cloud rejected the account API key"
            ) from err
        raise ConfigEntryAuthFailed("Luke Roberts cloud rejected the API key") from err
    except CloudError as err:
        _LOGGER.debug("%s: cloud state not available: %s", lamp.name, err)

    entry.async_on_unload(async_track_time_interval(hass, _poll, CLOUD_POLL_INTERVAL))


async def _async_initial_local_read(
    hass: HomeAssistant, entry: LukeRobertsConfigEntry
) -> None:
    """Read API version, device information and scene names once."""
    lamp = entry.runtime_data
    if not lamp.has_local:
        return
    try:
        await lamp.ping()
        info = await lamp.read_device_info()
        await lamp.refresh_scenes()
    except (HomeAssistantError, *BLE_ERRORS) as err:
        _LOGGER.info(
            "%s: could not read lamp details over Bluetooth yet (%s); "
            "use the 'Refresh scenes' button once the lamp is reachable",
            lamp.name,
            err,
        )
        return

    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={(DOMAIN, entry.unique_id)})
    if device is not None:
        registry.async_update_device(
            device.id,
            model=info.get("model") or device.model,
            # The app treats 2A28 as firmware and 2A26 as bootloader revision.
            sw_version=info.get("software") or info.get("firmware"),
            hw_version=info.get("hardware"),
            serial_number=info.get("serial_number"),
        )
    if (account := async_loaded_account(hass)) is not None:
        async_link_lamps(hass, account.lamps)


async def _async_update_listener(
    hass: HomeAssistant, entry: LukeRobertsConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: LukeRobertsConfigEntry
) -> bool:
    """Unload a config entry."""
    if is_account_entry(entry):
        return True
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and entry.runtime_data.ble is not None:
        await entry.runtime_data.ble.disconnect()
    return unloaded
