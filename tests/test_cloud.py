"""Cloud client tests."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.luke_roberts.cloud import (
    CloudAuthError,
    CloudError,
    CloudState,
    LukeRobertsCloud,
    parse_state,
)
from custom_components.luke_roberts.const import CLOUD_BASE_URL


async def test_get_lamps(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Lamps are parsed and the bearer token is sent."""
    aioclient_mock.get(
        f"{CLOUD_BASE_URL}/lamps",
        json=[
            {"id": 12, "name": "Esstisch", "serial_number": "ABC123"},
            {"id": "13"},
            {"name": "broken"},
        ],
    )
    cloud = LukeRobertsCloud(async_get_clientsession(hass), "secret")
    lamps = await cloud.get_lamps()
    assert [(lamp.lamp_id, lamp.name, lamp.serial_number) for lamp in lamps] == [
        (12, "Esstisch", "ABC123"),
        (13, "Lamp 13", None),
    ]
    headers = aioclient_mock.mock_calls[0][3]
    assert headers["Authorization"] == "Bearer secret"


async def test_send_command(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Commands are PUT as JSON."""
    aioclient_mock.put(f"{CLOUD_BASE_URL}/lamps/12/command", json={})
    cloud = LukeRobertsCloud(async_get_clientsession(hass), "secret")
    await cloud.kelvin(12, 5000)
    await cloud.scene(12, 3)
    assert aioclient_mock.mock_calls[0][2] == {"kelvin": 4000}
    assert aioclient_mock.mock_calls[1][2] == {"scene": 3}


@pytest.mark.parametrize(("status", "exc"), [(401, CloudAuthError), (500, CloudError)])
async def test_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status: int, exc: type
) -> None:
    """HTTP errors map to exceptions."""
    aioclient_mock.get(f"{CLOUD_BASE_URL}/lamps", status=status)
    cloud = LukeRobertsCloud(async_get_clientsession(hass), "secret")
    with pytest.raises(exc):
        await cloud.get_lamps()


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {"on": True, "brightness": 40, "color": {"temperatureK": 3000}},
            CloudState(is_on=True, brightness=40, kelvin=3000),
        ),
        ({"state": {"power": "OFF"}}, CloudState(is_on=False)),
        ({"scene": 0}, CloudState(is_on=False, scene_id=0)),
        (
            {"scene_id": 4, "kelvin": "2700"},
            CloudState(is_on=True, kelvin=2700, scene_id=4),
        ),
        ("unexpected", CloudState()),
    ],
)
def test_parse_state(payload, expected: CloudState) -> None:
    """Different payload shapes are tolerated."""
    assert parse_state(payload) == expected
