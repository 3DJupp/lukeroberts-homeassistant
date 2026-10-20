"""Scene select for Luke Roberts."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LukeRobertsConfigEntry
from .entity import LukeRobertsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the scene select."""
    async_add_entities([LukeRobertsSceneSelect(entry)])


class LukeRobertsSceneSelect(LukeRobertsEntity, SelectEntity):
    """Dropdown filled with the scene names read from the lamp."""

    _attr_translation_key = "scene"

    def __init__(self, entry: LukeRobertsConfigEntry) -> None:
        super().__init__(entry, "scene")

    @property
    def options(self) -> list[str]:
        """Scene names; refreshed whenever the lamp's scene list is read."""
        return list(self._lamp.scene_options())

    @property
    def current_option(self) -> str | None:
        """Last selected scene."""
        return self._lamp.scene_name(self._lamp.state.scene_id)

    async def async_select_option(self, option: str) -> None:
        """Select a scene."""
        scene_id = self._lamp.scene_options().get(option)
        if scene_id is None:
            raise ServiceValidationError(f"Unknown scene '{option}'")
        await self._lamp.select_scene(scene_id)
