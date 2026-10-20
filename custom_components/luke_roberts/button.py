"""Buttons for Luke Roberts."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LukeRobertsConfigEntry
from .entity import LukeRobertsEntity
from .lamp import LukeRobertsLamp


@dataclass(frozen=True, kw_only=True)
class LukeRobertsButtonDescription(ButtonEntityDescription):
    """Button description with its action."""

    press_fn: Callable[[LukeRobertsLamp], Awaitable[Any]]
    local_only: bool = True


BUTTONS: tuple[LukeRobertsButtonDescription, ...] = (
    LukeRobertsButtonDescription(
        key="next_brighter_scene",
        translation_key="next_brighter_scene",
        press_fn=lambda lamp: lamp.next_scene(1),
    ),
    LukeRobertsButtonDescription(
        key="next_dimmer_scene",
        translation_key="next_dimmer_scene",
        press_fn=lambda lamp: lamp.next_scene(-1),
    ),
    LukeRobertsButtonDescription(
        key="brighter",
        translation_key="brighter",
        press_fn=lambda lamp: lamp.relative_brightness(120),
    ),
    LukeRobertsButtonDescription(
        key="dimmer",
        translation_key="dimmer",
        press_fn=lambda lamp: lamp.relative_brightness(80),
    ),
    LukeRobertsButtonDescription(
        key="refresh_scenes",
        translation_key="refresh_scenes",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda lamp: lamp.refresh_scenes(),
    ),
    LukeRobertsButtonDescription(
        key="ping",
        translation_key="ping",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        press_fn=lambda lamp: lamp.ping(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons (all of them need Bluetooth)."""
    if entry.runtime_data.has_local or entry.data.get("address"):
        async_add_entities(
            LukeRobertsButton(entry, description) for description in BUTTONS
        )


class LukeRobertsButton(LukeRobertsEntity, ButtonEntity):
    """A one-shot lamp action."""

    entity_description: LukeRobertsButtonDescription

    def __init__(
        self, entry: LukeRobertsConfigEntry, description: LukeRobertsButtonDescription
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """These actions only exist on the Bluetooth API."""
        return self._lamp.has_local and self._lamp.ble_present

    async def async_press(self) -> None:
        """Run the action."""
        await self.entity_description.press_fn(self._lamp)
