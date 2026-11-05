"""Scene select for Luke Roberts."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LukeRobertsConfigEntry
from .const import RELATIVE_MODES
from .entity import LukeRobertsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the scene select and, with Bluetooth, the relative mode select."""
    entities: list[SelectEntity] = [LukeRobertsSceneSelect(entry)]
    if entry.runtime_data.has_local or entry.data.get("address"):
        entities.append(LukeRobertsRelativeModeSelect(entry))
    async_add_entities(entities)


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


class LukeRobertsRelativeModeSelect(LukeRobertsEntity, SelectEntity, RestoreEntity):
    """How the Brighter / Dimmer buttons encode opcode 08 (test setting)."""

    _attr_translation_key = "relative_brightness_mode"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = RELATIVE_MODES

    def __init__(self, entry: LukeRobertsConfigEntry) -> None:
        super().__init__(entry, "relative_brightness_mode")

    async def async_added_to_hass(self) -> None:
        """Restore the chosen mode after a restart."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None and (
            last.state in RELATIVE_MODES
        ):
            self._lamp.relative_mode = last.state

    @property
    def available(self) -> bool:
        """Always settable; it only changes what the buttons send."""
        return True

    @property
    def current_option(self) -> str:
        """The active mode."""
        return self._lamp.relative_mode

    async def async_select_option(self, option: str) -> None:
        """Switch the mode."""
        self._lamp.relative_mode = option
        self._lamp.notify()
