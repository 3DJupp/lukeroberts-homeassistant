"""Config flow tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luke_roberts.cloud import CloudAuthError, CloudLamp
from custom_components.luke_roberts.const import (
    CONF_API_KEY,
    CONF_CLOUD_LAMP_ID,
    CONF_CONNECTION_MODE,
    CONF_LINGER,
    DOMAIN,
    MODE_CLOUD_ONLY,
    MODE_LOCAL_FIRST,
)

from .common import ADDRESS, service_info

LAMPS = [CloudLamp(lamp_id=12, name="Esstisch", serial_number="ABC123", raw={})]


@pytest.fixture(autouse=True)
def _bluetooth(mock_bluetooth):
    """Keep the real Bluetooth stack from starting."""


@pytest.fixture
def no_setup():
    """Do not actually set up created entries."""
    with patch(
        "custom_components.luke_roberts.async_setup_entry", return_value=True
    ) as mock:
        yield mock


async def test_bluetooth_discovery(hass: HomeAssistant, no_setup) -> None:
    """A lamp seen by a proxy is offered and created as a local entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info(),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Luke Roberts Model F"
    assert result["data"] == {CONF_ADDRESS: ADDRESS, CONF_NAME: "Luke Roberts Model F"}
    assert result["options"][CONF_CONNECTION_MODE] == MODE_LOCAL_FIRST
    assert result["result"].unique_id == ADDRESS.lower()


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Known lamps are not offered again."""
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS.lower()).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info(),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_pick_discovered(hass: HomeAssistant, no_setup) -> None:
    """Manual setup lists discovered lamps."""
    with patch(
        "custom_components.luke_roberts.config_flow.async_discovered_service_info",
        return_value=[service_info()],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "pick_device"}
        )
        assert result["step_id"] == "pick_device"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == ADDRESS


async def test_user_manual_address(hass: HomeAssistant, no_setup) -> None:
    """Without discoveries a Bluetooth address can be typed in."""
    with patch(
        "custom_components.luke_roberts.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "pick_device"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: "nonsense"}
        )
        assert result["errors"] == {CONF_ADDRESS: "invalid_address"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: "aa:bb:cc:dd:ee:01"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Luke Roberts EE01"
    assert result["data"][CONF_ADDRESS] == "AA:BB:CC:DD:EE:01"


async def test_cloud_only(hass: HomeAssistant, no_setup) -> None:
    """Cloud only entry: API key, then lamp."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cloud"}
    )
    with patch(
        "custom_components.luke_roberts.config_flow._fetch_lamps",
        AsyncMock(side_effect=CloudAuthError("401")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "bad"}
        )
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "custom_components.luke_roberts.config_flow._fetch_lamps",
        AsyncMock(return_value=LAMPS),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: " good "}
        )
    assert result["step_id"] == "cloud_lamp"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CLOUD_LAMP_ID: "12"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Esstisch"
    assert result["data"][CONF_API_KEY] == "good"
    assert result["data"][CONF_CLOUD_LAMP_ID] == 12
    assert result["options"][CONF_CONNECTION_MODE] == MODE_CLOUD_ONLY
    assert result["result"].unique_id == "cloud_12"


async def test_options_add_cloud(hass: HomeAssistant, no_setup) -> None:
    """A local lamp can be linked to the cloud later."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS.lower(),
        data={CONF_ADDRESS: ADDRESS, CONF_NAME: "Lamp"},
        options={CONF_CONNECTION_MODE: MODE_LOCAL_FIRST, CONF_LINGER: 30},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_CONNECTION_MODE: "cloud_only", CONF_LINGER: 10},
    )
    assert result["errors"] == {CONF_API_KEY: "api_key_required"}

    with patch(
        "custom_components.luke_roberts.config_flow._fetch_lamps",
        AsyncMock(return_value=LAMPS),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_CONNECTION_MODE: MODE_LOCAL_FIRST,
                CONF_LINGER: 10,
                CONF_API_KEY: "k",
            },
        )
    assert result["step_id"] == "cloud_lamp"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CLOUD_LAMP_ID: "12"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_CONNECTION_MODE: MODE_LOCAL_FIRST,
        CONF_LINGER: 10,
        CONF_API_KEY: "k",
        CONF_CLOUD_LAMP_ID: 12,
    }
