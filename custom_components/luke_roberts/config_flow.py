"""Config flow for Luke Roberts."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .cloud import CloudAuthError, CloudError, CloudLamp, LukeRobertsCloud
from .const import (
    CLOUD_APP_URL,
    CONF_API_KEY,
    CONF_CLOUD_LAMP_ID,
    CONF_CONNECTION_MODE,
    CONF_LINGER,
    DEFAULT_LINGER,
    DOMAIN,
    MODE_CLOUD_FIRST,
    MODE_CLOUD_ONLY,
    MODE_LOCAL_FIRST,
    MODE_LOCAL_ONLY,
    SERVICE_UUID,
)

_LOGGER = logging.getLogger(__name__)

_NAME_HINTS = ("luke", "luvo", "lrbt")

CLOUD_PLACEHOLDERS = {"cloud_url": CLOUD_APP_URL}


def is_luke_roberts(info: BluetoothServiceInfoBleak) -> bool:
    """Match by the control service UUID or a typical advertised name."""
    if SERVICE_UUID in (uuid.lower() for uuid in info.service_uuids):
        return True
    name = (info.name or "").lower()
    return any(hint in name for hint in _NAME_HINTS)


def _default_name(info: BluetoothServiceInfoBleak | None, address: str) -> str:
    if info is not None and info.name and info.name != info.address:
        return info.name
    return f"Luke Roberts {address.replace(':', '')[-4:].upper()}"


async def _fetch_lamps(flow_hass, api_key: str) -> list[CloudLamp]:
    return await LukeRobertsCloud(
        async_get_clientsession(flow_hass), api_key
    ).get_lamps()


def _lamp_selector(lamps: list[CloudLamp]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                {
                    "value": str(lamp.lamp_id),
                    "label": f"{lamp.name} ({lamp.serial_number})"
                    if lamp.serial_number
                    else lamp.name,
                }
                for lamp in lamps
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


API_KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class LukeRobertsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Luke Roberts."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}
        self._api_key: str | None = None
        self._lamps: list[CloudLamp] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return LukeRobertsOptionsFlow()

    # --- Bluetooth discovery --------------------------------------------------

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """A lamp was found by an adapter or a Bluetooth proxy."""
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {
            "name": _default_name(discovery_info, discovery_info.address)
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered lamp."""
        assert self._discovery is not None
        name = _default_name(self._discovery, self._discovery.address)
        if user_input is not None:
            return self._create_local_entry(self._discovery.address, name)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders={"name": name}
        )

    # --- Manual setup ---------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose between Bluetooth and cloud only."""
        return self.async_show_menu(
            step_id="user", menu_options=["pick_device", "cloud"]
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a discovered lamp or type its Bluetooth address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if len(address.split(":")) != 6:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                await self.async_set_unique_id(format_mac(address))
                self._abort_if_unique_id_configured()
                info = self._discovered.get(address)
                return self._create_local_entry(address, _default_name(info, address))

        current = self._async_current_ids(include_ignore=False)
        self._discovered = {
            info.address.upper(): info
            for info in async_discovered_service_info(self.hass, connectable=True)
            if is_luke_roberts(info) and format_mac(info.address) not in current
        }
        if self._discovered:
            field = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": address,
                            "label": f"{_default_name(info, address)} ({address})",
                        }
                        for address, info in self._discovered.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            )
        else:
            field = TextSelector()
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): field}),
            errors=errors,
        )

    @callback
    def _create_local_entry(self, address: str, name: str) -> ConfigFlowResult:
        return self.async_create_entry(
            title=name,
            data={CONF_ADDRESS: address.upper(), CONF_NAME: name},
            options={
                CONF_CONNECTION_MODE: MODE_LOCAL_FIRST,
                CONF_LINGER: DEFAULT_LINGER,
            },
        )

    # --- Cloud only -----------------------------------------------------------

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the personal API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY].strip()
            errors = await self._async_load_lamps()
            if not errors:
                return await self.async_step_cloud_lamp()
        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): API_KEY_SELECTOR}),
            errors=errors,
            description_placeholders=CLOUD_PLACEHOLDERS,
        )

    async def _async_load_lamps(self) -> dict[str, str]:
        assert self._api_key is not None
        try:
            self._lamps = await _fetch_lamps(self.hass, self._api_key)
        except CloudAuthError:
            return {"base": "invalid_auth"}
        except CloudError:
            return {"base": "cannot_connect"}
        if not self._lamps:
            return {"base": "no_lamps"}
        return {}

    async def async_step_cloud_lamp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick one of the account's lamps."""
        if user_input is not None:
            lamp_id = int(user_input[CONF_CLOUD_LAMP_ID])
            lamp = next(lamp for lamp in self._lamps if lamp.lamp_id == lamp_id)
            await self.async_set_unique_id(f"cloud_{lamp_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=lamp.name,
                data={
                    CONF_NAME: lamp.name,
                    CONF_API_KEY: self._api_key,
                    CONF_CLOUD_LAMP_ID: lamp_id,
                },
                options={CONF_CONNECTION_MODE: MODE_CLOUD_ONLY},
            )
        return self.async_show_form(
            step_id="cloud_lamp",
            data_schema=vol.Schema(
                {vol.Required(CONF_CLOUD_LAMP_ID): _lamp_selector(self._lamps)}
            ),
        )

    # --- Reauth -----------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """The cloud rejected the API key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY].strip()
            errors = await self._async_load_lamps()
            if not errors:
                entry = self._get_reauth_entry()
                if CONF_API_KEY in entry.options:
                    self.hass.config_entries.async_update_entry(
                        entry, options={**entry.options, CONF_API_KEY: self._api_key}
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: self._api_key}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): API_KEY_SELECTOR}),
            errors=errors,
        )


class LukeRobertsOptionsFlow(OptionsFlow):
    """Connection mode, keepalive and optional cloud link."""

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}
        self._lamps: list[CloudLamp] = []

    def _current(self, key: str, default: Any = None) -> Any:
        entry = self.config_entry
        return entry.options.get(key, entry.data.get(key, default))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Main options form."""
        has_ble = CONF_ADDRESS in self.config_entry.data
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            mode = user_input.get(CONF_CONNECTION_MODE, MODE_CLOUD_ONLY)
            if mode in (MODE_CLOUD_FIRST, MODE_CLOUD_ONLY) and not api_key:
                errors[CONF_API_KEY] = "api_key_required"
            elif api_key:
                try:
                    self._lamps = await _fetch_lamps(self.hass, api_key)
                except CloudAuthError:
                    errors[CONF_API_KEY] = "invalid_auth"
                except CloudError:
                    errors["base"] = "cannot_connect"
                else:
                    if not self._lamps:
                        errors["base"] = "no_lamps"
            if not errors:
                self._options = {
                    CONF_CONNECTION_MODE: mode,
                    CONF_LINGER: int(user_input.get(CONF_LINGER, DEFAULT_LINGER)),
                }
                if api_key:
                    self._options[CONF_API_KEY] = api_key
                    return await self.async_step_cloud_lamp()
                return self.async_create_entry(data=self._options)

        schema: dict[Any, Any] = {}
        if has_ble:
            schema[
                vol.Required(
                    CONF_CONNECTION_MODE,
                    default=self._current(CONF_CONNECTION_MODE, MODE_LOCAL_FIRST),
                )
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        MODE_LOCAL_FIRST,
                        MODE_LOCAL_ONLY,
                        MODE_CLOUD_FIRST,
                        MODE_CLOUD_ONLY,
                    ],
                    translation_key="connection_mode",
                    mode=SelectSelectorMode.LIST,
                )
            )
            schema[
                vol.Required(
                    CONF_LINGER, default=self._current(CONF_LINGER, DEFAULT_LINGER)
                )
            ] = NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=300,
                    step=1,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            )
        schema[
            vol.Optional(
                CONF_API_KEY,
                description={"suggested_value": self._current(CONF_API_KEY)},
            )
        ] = API_KEY_SELECTOR
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders=CLOUD_PLACEHOLDERS,
        )

    async def async_step_cloud_lamp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Link this entry to one of the account's lamps."""
        if user_input is not None:
            self._options[CONF_CLOUD_LAMP_ID] = int(user_input[CONF_CLOUD_LAMP_ID])
            return self.async_create_entry(data=self._options)

        default = self._current(CONF_CLOUD_LAMP_ID)
        if default is None:
            lamp_obj = getattr(self.config_entry, "runtime_data", None)
            serial = (
                lamp_obj.state.device_info.get("serial_number") if lamp_obj else None
            )
            for lamp in self._lamps:
                if serial and lamp.serial_number == serial:
                    default = lamp.lamp_id
                    break
            else:
                default = self._lamps[0].lamp_id if len(self._lamps) == 1 else None

        key = (
            vol.Required(CONF_CLOUD_LAMP_ID, default=str(default))
            if default is not None
            else vol.Required(CONF_CLOUD_LAMP_ID)
        )
        return self.async_show_form(
            step_id="cloud_lamp",
            data_schema=vol.Schema({key: _lamp_selector(self._lamps)}),
        )
