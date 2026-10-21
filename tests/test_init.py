"""End to end setup tests with a simulated lamp."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.select import ATTR_OPTIONS, DOMAIN as SELECT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.luke_roberts import protocol
from custom_components.luke_roberts.const import (
    CLOUD_BASE_URL,
    CONF_ACCOUNT,
    CONF_API_KEY,
    CONF_CLOUD_LAMP_ID,
    CONF_CONNECTION_MODE,
    CONF_FIRMWARE_KEY,
    CONF_LINGER,
    DOMAIN,
    FIRMWARE_BASE_URL,
    MODE_CLOUD_ONLY,
    MODE_LOCAL_FIRST,
)
from custom_components.luke_roberts.protocol import Downlight, Uplight

from .common import ADDRESS, FakeLampClient, service_info

LIGHT = "light.esstisch"


@pytest.fixture(autouse=True)
def _bluetooth(mock_bluetooth):
    """Keep the real Bluetooth stack from starting."""


async def _setup_ble(
    hass: HomeAssistant, client: FakeLampClient, **options
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Esstisch",
        unique_id=ADDRESS.lower(),
        data={CONF_ADDRESS: ADDRESS, CONF_NAME: "Esstisch"},
        options={CONF_CONNECTION_MODE: MODE_LOCAL_FIRST, CONF_LINGER: 0, **options},
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info().device,
        ),
        patch(
            "custom_components.luke_roberts.ble.establish_connection",
            AsyncMock(return_value=client),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def test_ble_setup_and_control(hass: HomeAssistant) -> None:
    """Scenes are read on setup and commands go out over BLE."""
    client = FakeLampClient()
    entry = await _setup_ble(hass, client)

    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, entry.unique_id)}
    )
    assert device is not None
    assert device.model == "Model F"
    assert device.sw_version == "1.3.2"

    state = hass.states.get(LIGHT)
    assert state is not None
    assert state.attributes[ATTR_EFFECT_LIST] == ["Default", "Lesen", "Gemütlich"]
    select = hass.states.get("select.esstisch_scene")
    assert select.attributes[ATTR_OPTIONS] == ["Default", "Off", "Lesen", "Gemütlich"]

    with patch(
        "custom_components.luke_roberts.ble.establish_connection",
        AsyncMock(return_value=client),
    ):
        client.written.clear()
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: LIGHT, ATTR_EFFECT: "Lesen", ATTR_BRIGHTNESS: 128},
            blocking=True,
        )
        assert client.written == [protocol.select_scene(1), protocol.brightness(50)]
        state = hass.states.get(LIGHT)
        assert state.state == STATE_ON
        assert state.attributes[ATTR_EFFECT] == "Lesen"
        assert hass.states.get("select.esstisch_scene").state == "Lesen"
        assert (
            hass.states.get("sensor.esstisch_last_command_route").state == "bluetooth"
        )

        client.written.clear()
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: LIGHT, ATTR_COLOR_TEMP_KELVIN: 3000},
            blocking=True,
        )
        assert client.written == [protocol.color_temperature(3000)]

        client.written.clear()
        await hass.services.async_call(
            DOMAIN,
            "immediate_light",
            {
                ATTR_ENTITY_ID: LIGHT,
                "uplight_hs_color": [180, 100],
                "downlight_kelvin": 2700,
                "downlight_brightness": 100,
                "duration": {"seconds": 5},
            },
            blocking=True,
        )
        assert client.written == [
            protocol.immediate_light(
                Uplight(saturation=255, hue=32768, brightness=255),
                Downlight(kelvin=2700, brightness=255),
                5000,
            )
        ]

        client.written.clear()
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {ATTR_ENTITY_ID: "select.esstisch_scene", "option": "Gemütlich"},
            blocking=True,
        )
        assert client.written == [protocol.select_scene(2)]

        client.written.clear()
        await hass.services.async_call(
            "button",
            "press",
            {ATTR_ENTITY_ID: "button.esstisch_next_dimmer_scene"},
            blocking=True,
        )
        assert client.written == [protocol.next_scene_by_brightness(-1)]

        client.written.clear()
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: LIGHT}, blocking=True
        )
        assert client.written == [protocol.select_scene(0)]
        assert hass.states.get(LIGHT).state == STATE_OFF

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_scene_services(hass: HomeAssistant) -> None:
    """Scenes are created, overwritten and deleted in the lamp."""
    client = FakeLampClient()
    await _setup_ble(hass, client)

    with patch(
        "custom_components.luke_roberts.ble.establish_connection",
        AsyncMock(return_value=client),
    ):
        client.written.clear()
        await hass.services.async_call(
            DOMAIN,
            "save_scene",
            {
                ATTR_ENTITY_ID: LIGHT,
                "name": "Abendessen",
                "uplight_hs_color": [30, 80],
                "uplight_brightness": 50,
                "downlight_kelvin": 3000,
                "downlight_brightness": 80,
                "activate": True,
            },
            blocking=True,
        )
        assert client.written[0] == protocol.static_scene(
            protocol.SCENE_NEW,
            "Abendessen",
            Uplight(saturation=204, hue=5461, brightness=128),
            Downlight(kelvin=3000, brightness=204),
        )
        assert client.written[-1] == protocol.select_scene(3)
        state = hass.states.get(LIGHT)
        assert state.attributes[ATTR_EFFECT_LIST] == [
            "Default",
            "Lesen",
            "Gemütlich",
            "Abendessen",
        ]
        assert state.attributes[ATTR_EFFECT] == "Abendessen"

        client.written.clear()
        await hass.services.async_call(
            DOMAIN,
            "save_scene",
            {ATTR_ENTITY_ID: LIGHT, "name": "Lesen hell", "scene": "Lesen"},
            blocking=True,
        )
        assert client.written[0] == protocol.static_scene(
            1,
            "Lesen hell",
            Uplight(saturation=0, hue=2700, brightness=0),
            Downlight(kelvin=2700, brightness=255),
        )
        assert client.scenes[1] == "Lesen hell"

        client.written.clear()
        await hass.services.async_call(
            DOMAIN,
            "delete_scene",
            {ATTR_ENTITY_ID: LIGHT, "scene": "Abendessen"},
            blocking=True,
        )
        # The active scene is left first, like the app does.
        assert client.written[0] == protocol.select_scene(1)
        assert client.written[1] == protocol.delete_scene(3)
        assert 3 not in client.scenes
        assert "Abendessen" not in hass.states.get(LIGHT).attributes[ATTR_EFFECT_LIST]

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                "delete_scene",
                {ATTR_ENTITY_ID: LIGHT, "scene": "Gibt es nicht"},
                blocking=True,
            )
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                "delete_scene",
                {ATTR_ENTITY_ID: LIGHT, "scene": "Off"},
                blocking=True,
            )


async def test_firmware_entity(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Installed firmware from the lamp, newest from the firmware server."""
    aioclient_mock.get(
        f"{FIRMWARE_BASE_URL}/firmware/latest",
        json={
            "version": "1.4.0",
            "file": "https://example.invalid/fw.zip",
            "history": [{"version": "1.4.0", "releaseNotes": "Faster scenes"}],
        },
    )
    await _setup_ble(hass, FakeLampClient(), **{CONF_FIRMWARE_KEY: "secret"})
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("update.esstisch_firmware")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["installed_version"] == "1.3.2"
    assert state.attributes["latest_version"] == "1.4.0"
    assert state.attributes["release_summary"] == "Faster scenes"
    _method, url, _data, headers = aioclient_mock.mock_calls[0]
    assert url.query["model"] == "Model F"
    assert url.query["firmware"] == "1.3.2"
    assert url.query["bootloader"] == "12"
    assert headers["Api-Key"] == "secret"


async def test_firmware_entity_without_key(hass: HomeAssistant) -> None:
    """Without a key only the installed version is shown."""
    await _setup_ble(hass, FakeLampClient())
    state = hass.states.get("update.esstisch_firmware")
    assert state.attributes["installed_version"] == "1.3.2"
    assert state.attributes["latest_version"] is None


async def test_cloud_only_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A cloud only lamp is controlled through the REST API."""
    aioclient_mock.get(
        f"{CLOUD_BASE_URL}/lamps/12/state",
        json={"on": False, "brightness": 80},
    )
    aioclient_mock.put(f"{CLOUD_BASE_URL}/lamps/12/command", json={})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Esstisch",
        unique_id="cloud_12",
        data={CONF_NAME: "Esstisch", CONF_API_KEY: "key", CONF_CLOUD_LAMP_ID: 12},
        options={CONF_CONNECTION_MODE: MODE_CLOUD_ONLY},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(LIGHT)
    assert state.state == STATE_OFF
    assert hass.states.get("button.esstisch_refresh_scenes") is None

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIGHT, ATTR_EFFECT: "Scene 3"},
        blocking=True,
    )
    puts = [call for call in aioclient_mock.mock_calls if call[0] == "PUT"]
    assert [call[2] for call in puts] == [{"scene": 3}]
    assert hass.states.get(LIGHT).state == STATE_ON
    assert hass.states.get("sensor.esstisch_last_command_route").state == "cloud"


async def test_cloud_auth_failure_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected key puts the entry into reauth."""
    aioclient_mock.get(f"{CLOUD_BASE_URL}/lamps/12/state", status=401)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Esstisch",
        unique_id="cloud_12",
        data={CONF_NAME: "Esstisch", CONF_API_KEY: "key", CONF_CLOUD_LAMP_ID: 12},
        options={CONF_CONNECTION_MODE: MODE_CLOUD_ONLY},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_account_links_and_discovers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The account links the Bluetooth lamp by name and offers the others."""
    aioclient_mock.get(
        f"{CLOUD_BASE_URL}/lamps",
        json=[{"id": 12, "name": "Esstisch"}, {"id": 13, "name": "Flur"}],
    )
    aioclient_mock.get(f"{CLOUD_BASE_URL}/lamps/12/state", json={})
    client = FakeLampClient()
    lamp_entry = await _setup_ble(hass, client)
    assert lamp_entry.runtime_data.cloud is None

    account = MockConfigEntry(
        domain=DOMAIN,
        unique_id="account",
        data={CONF_ACCOUNT: True, CONF_API_KEY: "account-key"},
    )
    account.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info().device,
        ),
        patch(
            "custom_components.luke_roberts.ble.establish_connection",
            AsyncMock(return_value=client),
        ),
    ):
        assert await hass.config_entries.async_setup(account.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert lamp_entry.options[CONF_CLOUD_LAMP_ID] == 12
    assert lamp_entry.runtime_data.has_cloud
    assert lamp_entry.runtime_data.cloud.api_key == "account-key"

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["unique_id"] for flow in flows] == ["cloud_13"]


async def test_account_lamp_uses_account_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A lamp added from the account sends commands with the account key."""
    aioclient_mock.get(f"{CLOUD_BASE_URL}/lamps/12/state", json={"on": True})
    aioclient_mock.put(f"{CLOUD_BASE_URL}/lamps/12/command", json={})
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="account",
        data={CONF_ACCOUNT: True, CONF_API_KEY: "account-key"},
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Esstisch",
        unique_id="cloud_12",
        data={CONF_NAME: "Esstisch", CONF_CLOUD_LAMP_ID: 12},
        options={CONF_CONNECTION_MODE: MODE_CLOUD_ONLY},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: LIGHT}, blocking=True
    )
    put = next(call for call in aioclient_mock.mock_calls if call[0] == "PUT")
    assert put[2] == {"power": "OFF"}
    assert put[3]["Authorization"] == "Bearer account-key"


async def test_account_lamp_without_account(hass: HomeAssistant) -> None:
    """A lamp from a removed account fails setup with a clear error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Esstisch",
        unique_id="cloud_12",
        data={CONF_NAME: "Esstisch", CONF_CLOUD_LAMP_ID: 12},
        options={CONF_CONNECTION_MODE: MODE_CLOUD_ONLY},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_account_auth_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected account key asks for a new one on the account."""
    aioclient_mock.get(f"{CLOUD_BASE_URL}/lamps", status=401)
    account = MockConfigEntry(
        domain=DOMAIN,
        unique_id="account",
        data={CONF_ACCOUNT: True, CONF_API_KEY: "account-key"},
    )
    account.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(account.entry_id)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows)
