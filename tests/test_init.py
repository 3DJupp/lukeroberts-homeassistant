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
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.luke_roberts import protocol
from custom_components.luke_roberts.const import (
    CLOUD_BASE_URL,
    CONF_API_KEY,
    CONF_CLOUD_LAMP_ID,
    CONF_CONNECTION_MODE,
    CONF_LINGER,
    DOMAIN,
    MODE_CLOUD_ONLY,
    MODE_LOCAL_FIRST,
)
from custom_components.luke_roberts.protocol import Downlight, Uplight

from .common import ADDRESS, FakeLampClient, service_info

LIGHT = "light.esstisch"


@pytest.fixture(autouse=True)
def _bluetooth(mock_bluetooth):
    """Keep the real Bluetooth stack from starting."""


async def _setup_ble(hass: HomeAssistant, client: FakeLampClient) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Esstisch",
        unique_id=ADDRESS.lower(),
        data={CONF_ADDRESS: ADDRESS, CONF_NAME: "Esstisch"},
        options={CONF_CONNECTION_MODE: MODE_LOCAL_FIRST, CONF_LINGER: 0},
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
