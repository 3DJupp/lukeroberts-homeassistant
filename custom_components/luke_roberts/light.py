"""Light platform for Luke Roberts."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.color import brightness_to_value, value_to_brightness
import voluptuous as vol

from . import LukeRobertsConfigEntry
from .const import (
    MAX_KELVIN,
    MIN_KELVIN,
    SCENE_OFF,
    SERVICE_DELETE_SCENE,
    SERVICE_IMMEDIATE_LIGHT,
    SERVICE_SAVE_SCENE,
)
from .entity import LukeRobertsEntity
from .protocol import Downlight, Uplight

PERCENT_SCALE = (1, 100)

ATTR_DURATION = "duration"
ATTR_UPLIGHT_HS_COLOR = "uplight_hs_color"
ATTR_UPLIGHT_KELVIN = "uplight_kelvin"
ATTR_UPLIGHT_BRIGHTNESS = "uplight_brightness"
ATTR_DOWNLIGHT_KELVIN = "downlight_kelvin"
ATTR_DOWNLIGHT_BRIGHTNESS = "downlight_brightness"
ATTR_NAME = "name"
ATTR_SCENE = "scene"
ATTR_ACTIVATE = "activate"

IMMEDIATE_LIGHT_SCHEMA = {
    vol.Optional(ATTR_UPLIGHT_HS_COLOR): vol.All(
        vol.Coerce(tuple),
        vol.ExactSequence(
            (
                vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
                vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            )
        ),
    ),
    vol.Optional(ATTR_UPLIGHT_KELVIN): vol.All(
        vol.Coerce(int), vol.Range(min=MIN_KELVIN, max=MAX_KELVIN)
    ),
    vol.Optional(ATTR_UPLIGHT_BRIGHTNESS): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100)
    ),
    vol.Optional(ATTR_DOWNLIGHT_KELVIN): vol.All(
        vol.Coerce(int), vol.Range(min=MIN_KELVIN, max=MAX_KELVIN)
    ),
    vol.Optional(ATTR_DOWNLIGHT_BRIGHTNESS): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100)
    ),
    vol.Optional(ATTR_DURATION, default=0): vol.All(
        cv.time_period, cv.positive_timedelta
    ),
}

SAVE_SCENE_SCHEMA = {
    vol.Required(ATTR_NAME): vol.All(cv.string, vol.Length(min=1, max=20)),
    vol.Optional(ATTR_SCENE): vol.Any(vol.Coerce(int), cv.string),
    **{
        key: value
        for key, value in IMMEDIATE_LIGHT_SCHEMA.items()
        if key != ATTR_DURATION
    },
    vol.Optional(ATTR_ACTIVATE, default=False): cv.boolean,
}

DELETE_SCENE_SCHEMA = {
    vol.Required(ATTR_SCENE): vol.Any(vol.Coerce(int), cv.string),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light."""
    async_add_entities([LukeRobertsLight(entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_IMMEDIATE_LIGHT,
        IMMEDIATE_LIGHT_SCHEMA,
        "async_immediate_light",
    )
    platform.async_register_entity_service(
        SERVICE_SAVE_SCENE, SAVE_SCENE_SCHEMA, "async_save_scene"
    )
    platform.async_register_entity_service(
        SERVICE_DELETE_SCENE, DELETE_SCENE_SCHEMA, "async_delete_scene"
    )


def _pct_to_byte(percent: int) -> int:
    return round(percent * 255 / 100)


def _uplight(kwargs: dict[str, Any]) -> Uplight | None:
    """Uplight from hs colour or Kelvin plus brightness, None if not given."""
    if ATTR_UPLIGHT_HS_COLOR not in kwargs and ATTR_UPLIGHT_KELVIN not in kwargs:
        return None
    brightness = _pct_to_byte(kwargs.get(ATTR_UPLIGHT_BRIGHTNESS, 100))
    if ATTR_UPLIGHT_HS_COLOR in kwargs:
        hue, sat = kwargs[ATTR_UPLIGHT_HS_COLOR]
        return Uplight(
            # Saturation 0 would mean "white, hue is Kelvin"; the app sends 1.
            saturation=max(1, round(sat * 255 / 100)),
            hue=round(hue * 65535 / 360) & 0xFFFF,
            brightness=brightness,
        )
    return Uplight(saturation=0, hue=kwargs[ATTR_UPLIGHT_KELVIN], brightness=brightness)


class LukeRobertsLight(LukeRobertsEntity, LightEntity, RestoreEntity):
    """The lamp as one light: scenes as effects, brightness and white tone."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    def __init__(self, entry: LukeRobertsConfigEntry) -> None:
        super().__init__(entry, "light")

    async def async_added_to_hass(self) -> None:
        """Restore the last assumed state after a restart."""
        await super().async_added_to_hass()
        state = self._lamp.state
        if (
            state.is_on is not None
            or (last := await self.async_get_last_state()) is None
        ):
            return
        state.is_on = last.state == STATE_ON
        if (brightness := last.attributes.get(ATTR_BRIGHTNESS)) is not None:
            state.brightness = round(brightness_to_value(PERCENT_SCALE, brightness))
        if (kelvin := last.attributes.get(ATTR_COLOR_TEMP_KELVIN)) is not None:
            state.kelvin = int(kelvin)
        if (effect := last.attributes.get(ATTR_EFFECT)) is not None:
            state.scene_id = self._lamp.scene_options().get(effect)

    @property
    def is_on(self) -> bool | None:
        """Return the assumed on/off state."""
        return self._lamp.state.is_on

    @property
    def brightness(self) -> int | None:
        """Return brightness relative to the current scene."""
        percent = self._lamp.state.brightness
        if percent is None:
            return None
        if percent == 0:
            return 0
        return value_to_brightness(PERCENT_SCALE, percent)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the last set downlight colour temperature."""
        return self._lamp.state.kelvin

    @property
    def effect_list(self) -> list[str]:
        """Scenes from the lamp (Off is not an effect)."""
        return [
            label
            for label, sid in self._lamp.scene_options().items()
            if sid != SCENE_OFF
        ]

    @property
    def effect(self) -> str | None:
        """Return the active scene, if known."""
        return self._lamp.scene_name(self._lamp.state.scene_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on, optionally with scene, brightness and colour temperature."""
        scene_id: int | None = None
        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            scene_id = self._lamp.scene_options().get(effect)
            if scene_id is None:
                raise ServiceValidationError(f"Unknown scene '{effect}'")

        brightness: int | None = None
        if (value := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            brightness = round(brightness_to_value(PERCENT_SCALE, value))
            if value > 0:
                brightness = max(1, brightness)

        await self._lamp.turn_on(
            brightness=brightness,
            kelvin=kwargs.get(ATTR_COLOR_TEMP_KELVIN),
            scene_id=scene_id,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off (select the Off scene)."""
        await self._lamp.turn_off()

    async def async_immediate_light(self, **kwargs: Any) -> None:
        """Handle the immediate_light entity service."""
        uplight = _uplight(kwargs)
        if uplight is None and ATTR_UPLIGHT_BRIGHTNESS in kwargs:
            raise ServiceValidationError(
                "uplight_brightness needs uplight_hs_color or uplight_kelvin"
            )

        downlight: Downlight | None = None
        if ATTR_DOWNLIGHT_KELVIN in kwargs or ATTR_DOWNLIGHT_BRIGHTNESS in kwargs:
            downlight = Downlight(
                kelvin=kwargs.get(
                    ATTR_DOWNLIGHT_KELVIN, self._lamp.state.kelvin or MAX_KELVIN
                ),
                brightness=_pct_to_byte(kwargs.get(ATTR_DOWNLIGHT_BRIGHTNESS, 100)),
            )

        if uplight is None and downlight is None:
            raise ServiceValidationError("Provide uplight and/or downlight settings")

        duration_ms = int(kwargs[ATTR_DURATION].total_seconds() * 1000)
        if duration_ms > 0xFFFF:
            raise ServiceValidationError("duration must be at most 65 seconds")
        await self._lamp.immediate_light(uplight, downlight, duration_ms)

    def _scene_id(self, value: int | str) -> int:
        """Scene id from an id or a name of the scene list."""
        options = self._lamp.scene_options()
        if isinstance(value, int) or str(value).isdigit():
            scene_id = int(value)
            if scene_id in options.values():
                return scene_id
        elif str(value) in options:
            return options[str(value)]
        raise ServiceValidationError(
            f"Unknown scene '{value}', refresh the scenes if it was just created"
        )

    async def async_save_scene(self, **kwargs: Any) -> None:
        """Store a scene in the lamp (new, or overwrite ``scene``)."""
        scene_id: int | None = None
        if (value := kwargs.get(ATTR_SCENE)) is not None:
            scene_id = self._scene_id(value)
        downlight_kelvin = kwargs.get(ATTR_DOWNLIGHT_KELVIN, MIN_KELVIN)
        uplight = _uplight(kwargs) or Uplight(
            saturation=0,
            hue=downlight_kelvin,
            brightness=_pct_to_byte(kwargs.get(ATTR_UPLIGHT_BRIGHTNESS, 0)),
        )
        downlight = Downlight(
            kelvin=downlight_kelvin,
            brightness=_pct_to_byte(kwargs.get(ATTR_DOWNLIGHT_BRIGHTNESS, 100)),
        )
        saved_id = await self._lamp.save_scene(
            kwargs[ATTR_NAME], uplight, downlight, scene_id
        )
        if kwargs[ATTR_ACTIVATE]:
            await self._lamp.select_scene(saved_id)

    async def async_delete_scene(self, **kwargs: Any) -> None:
        """Delete a scene from the lamp."""
        await self._lamp.delete_scene(self._scene_id(kwargs[ATTR_SCENE]))
