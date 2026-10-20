"""Diagnostic sensors for Luke Roberts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LukeRobertsConfigEntry
from .entity import LukeRobertsEntity
from .lamp import ROUTE_BLUETOOTH, ROUTE_CLOUD, LukeRobertsLamp


@dataclass(frozen=True, kw_only=True)
class LukeRobertsSensorDescription(SensorEntityDescription):
    """Sensor description with value getter."""

    value_fn: Callable[[LukeRobertsLamp], str | int | None]


SENSORS: tuple[LukeRobertsSensorDescription, ...] = (
    LukeRobertsSensorDescription(
        key="last_route",
        translation_key="last_route",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[ROUTE_BLUETOOTH, ROUTE_CLOUD],
        value_fn=lambda lamp: lamp.state.last_route,
    ),
    LukeRobertsSensorDescription(
        key="last_status",
        translation_key="last_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda lamp: lamp.state.last_status,
    ),
    LukeRobertsSensorDescription(
        key="api_version",
        translation_key="api_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda lamp: lamp.state.api_version,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up diagnostic sensors."""
    async_add_entities(LukeRobertsSensor(entry, description) for description in SENSORS)


class LukeRobertsSensor(LukeRobertsEntity, SensorEntity):
    """Diagnostic value from the lamp object."""

    entity_description: LukeRobertsSensorDescription

    def __init__(
        self, entry: LukeRobertsConfigEntry, description: LukeRobertsSensorDescription
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Diagnostics stay readable even when the lamp is out of range."""
        return True

    @property
    def native_value(self) -> str | int | None:
        """Return the value."""
        return self.entity_description.value_fn(self._lamp)
