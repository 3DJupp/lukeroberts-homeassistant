"""One Luke Roberts lamp, reachable locally (BLE) and/or through the cloud.

This class behaves like the Luke Roberts app: it talks to the lamp directly
over Bluetooth when it is in range and can fall back to the cloud. The lamp
cannot report its state over BLE, so the state kept here is what was last
sent (assumed state), optionally refreshed from the cloud.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from . import protocol
from .ble import BLE_ERRORS, LukeRobertsBle
from .cloud import CloudAuthError, CloudError, CloudState, LukeRobertsCloud
from .const import (
    CLOUD_MAX_SCENE_ID,
    MODE_CLOUD_FIRST,
    MODE_CLOUD_ONLY,
    MODE_LOCAL_ONLY,
    SCENE_CHAR_UUID,
    SCENE_DEFAULT,
    SCENE_OFF,
)

_LOGGER = logging.getLogger(__name__)

ROUTE_BLUETOOTH = "bluetooth"
ROUTE_CLOUD = "cloud"


@dataclass
class LampState:
    """Assumed lamp state."""

    is_on: bool | None = None
    brightness: int | None = None  # percent 0..100
    kelvin: int | None = None
    scene_id: int | None = None
    scenes: dict[int, str] = field(default_factory=dict)
    api_version: int | None = None
    device_info: dict[str, str] = field(default_factory=dict)
    last_route: str | None = None
    last_status: str | None = None


class LukeRobertsLamp:
    """Routes commands to BLE or cloud and keeps the assumed state."""

    def __init__(
        self,
        name: str,
        mode: str,
        ble: LukeRobertsBle | None,
        cloud: LukeRobertsCloud | None,
        cloud_lamp_id: int | None,
    ) -> None:
        self.name = name
        self.mode = mode
        self.ble = ble
        self.cloud = cloud
        self.cloud_lamp_id = cloud_lamp_id
        self.state = LampState()
        self.ble_present = ble is not None
        self._listeners: list[Callable[[], None]] = []

    # --- Listener plumbing ----------------------------------------------------

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register an entity update callback."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def notify(self) -> None:
        """Tell all entities to write their state."""
        for listener in list(self._listeners):
            listener()

    # --- Capabilities ---------------------------------------------------------

    @property
    def has_local(self) -> bool:
        """BLE is configured and allowed by the connection mode."""
        return self.ble is not None and self.mode != MODE_CLOUD_ONLY

    @property
    def has_cloud(self) -> bool:
        """Cloud is configured and allowed by the connection mode."""
        return (
            self.cloud is not None
            and self.cloud_lamp_id is not None
            and self.mode != MODE_LOCAL_ONLY
        )

    @property
    def available(self) -> bool:
        """At least one route can be tried."""
        return (self.has_local and self.ble_present) or self.has_cloud

    def scene_options(self) -> dict[str, int]:
        """Map display names to scene ids for selects and light effects."""
        options: dict[str, int] = {"Default": SCENE_DEFAULT}
        if self.state.scenes:
            names = list(self.state.scenes.values())
            for scene_id, name in self.state.scenes.items():
                label = name or f"Scene {scene_id}"
                if names.count(name) > 1 or label in options:
                    label = f"{label} ({scene_id})"
                options[label] = scene_id
        else:
            options["Off"] = SCENE_OFF
            upper = CLOUD_MAX_SCENE_ID if not self.has_local else 15
            for scene_id in range(1, upper + 1):
                options[f"Scene {scene_id}"] = scene_id
        return options

    def scene_name(self, scene_id: int | None) -> str | None:
        """Return the display name of a scene id."""
        if scene_id is None:
            return None
        for label, sid in self.scene_options().items():
            if sid == scene_id:
                return label
        return None

    # --- Routing ----------------------------------------------------------------

    async def _run(
        self,
        local: Callable[[LukeRobertsBle], Awaitable[Any]] | None,
        cloud: Callable[[LukeRobertsCloud, int], Awaitable[Any]] | None,
    ) -> Any:
        """Execute via the preferred route, falling back if allowed."""
        routes: list[str] = []
        if self.mode in (MODE_CLOUD_FIRST, MODE_CLOUD_ONLY):
            routes = [ROUTE_CLOUD, ROUTE_BLUETOOTH]
        else:
            routes = [ROUTE_BLUETOOTH, ROUTE_CLOUD]

        errors: list[str] = []
        for route in routes:
            if route == ROUTE_BLUETOOTH:
                if local is None or not self.has_local:
                    continue
                assert self.ble is not None
                try:
                    result = await local(self.ble)
                except protocol.LampForbiddenError as err:
                    errors.append(
                        "the lamp has a security code set in the Luke Roberts "
                        "app and rejects local commands"
                    )
                    self.state.last_status = protocol.status_name(err.status)
                    continue
                except protocol.LampError as err:
                    self.state.last_status = protocol.status_name(err.status)
                    raise HomeAssistantError(
                        f"{self.name}: lamp rejected command ({err})"
                    ) from err
                except BLE_ERRORS as err:
                    errors.append(f"bluetooth: {err or type(err).__name__}")
                    _LOGGER.debug("%s: BLE failed: %r", self.name, err)
                    continue
                self.state.last_route = ROUTE_BLUETOOTH
                self.state.last_status = "OK"
                return result
            if cloud is None or not self.has_cloud:
                continue
            assert self.cloud is not None and self.cloud_lamp_id is not None
            try:
                result = await cloud(self.cloud, self.cloud_lamp_id)
            except CloudAuthError as err:
                errors.append(f"cloud: API key rejected ({err})")
                continue
            except CloudError as err:
                errors.append(f"cloud: {err}")
                continue
            self.state.last_route = ROUTE_CLOUD
            self.state.last_status = "Queued"
            return result

        if not errors:
            raise HomeAssistantError(
                f"{self.name}: this action needs a Bluetooth connection to the lamp"
            )
        raise HomeAssistantError(f"{self.name}: " + "; ".join(errors))

    # --- Commands -----------------------------------------------------------------

    async def turn_on(
        self,
        brightness: int | None = None,
        kelvin: int | None = None,
        scene_id: int | None = None,
    ) -> None:
        """Switch on, optionally selecting a scene and adjusting it."""
        select: int | None = scene_id
        if select is None and not self.state.is_on:
            select = SCENE_DEFAULT

        frames: list[bytes] = []
        if select is not None:
            frames.append(protocol.select_scene(select))
        if brightness is not None:
            frames.append(protocol.brightness(brightness))
        if kelvin is not None:
            frames.append(protocol.color_temperature(kelvin))
        if not frames:
            return

        async def local(ble: LukeRobertsBle) -> None:
            for response in await ble.request_many(frames):
                protocol.check_status(response)

        async def cloud(api: LukeRobertsCloud, lamp_id: int) -> None:
            if select == SCENE_DEFAULT:
                await api.power(lamp_id, True)
            elif select is not None:
                await api.scene(lamp_id, select)
            if brightness is not None:
                await api.brightness(lamp_id, brightness)
            if kelvin is not None:
                await api.kelvin(lamp_id, kelvin)

        await self._run(local, cloud)
        if select is not None:
            self.state.scene_id = select
            # A newly selected scene brings its own brightness and colour.
            self.state.brightness = 100
            self.state.kelvin = None
        self.state.is_on = True
        if brightness is not None:
            self.state.brightness = brightness
        if kelvin is not None:
            self.state.kelvin = kelvin
        self.notify()

    async def turn_off(self) -> None:
        """Select the Off scene."""

        async def local(ble: LukeRobertsBle) -> None:
            protocol.check_status(await ble.request(protocol.select_scene(SCENE_OFF)))

        async def cloud(api: LukeRobertsCloud, lamp_id: int) -> None:
            await api.power(lamp_id, False)

        await self._run(local, cloud)
        self.state.is_on = False
        self.state.scene_id = SCENE_OFF
        self.notify()

    async def select_scene(self, scene_id: int) -> None:
        """Select a scene by id (0 = off, 255 = default)."""
        if scene_id == SCENE_OFF:
            await self.turn_off()
        else:
            await self.turn_on(scene_id=scene_id)

    async def next_scene(self, direction: int) -> None:
        """Step to the next brighter (+1) or dimmer (-1) scene. BLE only."""

        async def local(ble: LukeRobertsBle) -> None:
            protocol.check_status(
                await ble.request(protocol.next_scene_by_brightness(direction))
            )

        await self._run(local, None)
        self.state.is_on = True
        self.state.scene_id = None
        self.state.brightness = 100
        self.notify()

    async def relative_brightness(self, percent: int) -> None:
        """Scale the current brightness. BLE only."""

        async def local(ble: LukeRobertsBle) -> None:
            protocol.check_status(
                await ble.request(protocol.relative_brightness(percent))
            )

        await self._run(local, None)
        if self.state.brightness is not None:
            self.state.brightness = max(
                0, min(100, round(self.state.brightness * percent / 100))
            )
        self.notify()

    async def immediate_light(
        self,
        uplight: protocol.Uplight | None,
        downlight: protocol.Downlight | None,
        duration_ms: int,
    ) -> None:
        """Send a transient Immediate Light command. BLE only."""
        frame = protocol.immediate_light(uplight, downlight, duration_ms)

        async def local(ble: LukeRobertsBle) -> None:
            protocol.check_status(await ble.request(frame))

        await self._run(local, None)
        if duration_ms == 0:
            self.state.is_on = True
            if downlight is not None:
                self.state.kelvin = downlight.kelvin
        self.notify()

    async def save_scene(
        self,
        name: str,
        uplight: protocol.Uplight | list[protocol.Uplight],
        downlight: protocol.Downlight | list[int],
        scene_id: int | None = None,
    ) -> int:
        """Store a static scene in the lamp, new or overwriting one. BLE only.

        Returns the id of the scene, assigned by the lamp for new scenes.
        """
        if scene_id in (SCENE_OFF, SCENE_DEFAULT):
            raise HomeAssistantError(f"{self.name}: this scene cannot be changed")
        record = protocol.static_scene(
            protocol.SCENE_NEW if scene_id is None else scene_id,
            name,
            uplight,
            downlight,
        )

        async def local(ble: LukeRobertsBle) -> protocol.SceneWrite:
            return protocol.parse_scene_write(
                await ble.write_record(SCENE_CHAR_UUID, record)
            )

        result = await self._run_scene_write(local)
        saved_id = result.scene_id if result.scene_id is not None else scene_id
        _LOGGER.debug("%s: scene '%s' stored as %s", self.name, name, saved_id)
        await self._refresh_scenes_after_write()
        if saved_id is None:
            # Old firmware without id in the answer: find it by name.
            saved_id = next(
                (sid for sid, label in self.state.scenes.items() if label == name),
                None,
            )
        if saved_id is None:
            raise HomeAssistantError(
                f"{self.name}: the lamp did not report the id of the new scene"
            )
        return saved_id

    async def delete_scene(self, scene_id: int) -> None:
        """Delete a scene from the lamp. BLE only."""
        if scene_id in (SCENE_OFF, SCENE_DEFAULT):
            raise HomeAssistantError(f"{self.name}: this scene cannot be deleted")
        if self.state.is_on and self.state.scene_id == scene_id:
            # The app switches to another scene before deleting the active one.
            other = next(
                (sid for sid in self.state.scenes if sid not in (SCENE_OFF, scene_id)),
                None,
            )
            if other is not None:
                await self.select_scene(other)
        record = protocol.delete_scene(scene_id)

        async def local(ble: LukeRobertsBle) -> protocol.SceneWrite:
            return protocol.parse_scene_write(
                await ble.write_record(SCENE_CHAR_UUID, record)
            )

        await self._run_scene_write(local)
        await self._refresh_scenes_after_write()

    async def _run_scene_write(
        self, local: Callable[[LukeRobertsBle], Awaitable[protocol.SceneWrite]]
    ) -> protocol.SceneWrite:
        try:
            return await self._run(local, None)
        except HomeAssistantError as err:
            if (
                isinstance(err.__cause__, protocol.LampError)
                and err.__cause__.status == protocol.Status.MEMORY_FULL
            ):
                raise HomeAssistantError(
                    f"{self.name}: the lamp has no room for another scene"
                ) from err
            raise

    async def _refresh_scenes_after_write(self) -> None:
        try:
            await self.refresh_scenes()
        except HomeAssistantError as err:
            _LOGGER.debug("%s: reading scenes after write failed: %s", self.name, err)

    async def ping(self) -> int:
        """Ping the lamp and return its highest supported API version."""
        if self.ble is None:
            raise HomeAssistantError(f"{self.name}: no Bluetooth device configured")
        try:
            version = protocol.parse_ping(await self.ble.request(protocol.ping()))
        except protocol.LampError:
            # Firmware older than 1.0.7 only knows Ping@V=01.
            protocol.check_status(await self.ble.request(protocol.ping_v1()))
            version = 1
        self.state.api_version = version
        return version

    async def refresh_scenes(self) -> dict[int, str]:
        """Walk the scene list with Query Scene. BLE only."""
        if self.ble is None:
            raise HomeAssistantError(
                f"{self.name}: scene names can only be read over Bluetooth"
            )
        scenes: dict[int, str] = {}
        scene_id = 0
        try:
            while scene_id != 0xFF and scene_id not in scenes:
                response = await self.ble.request(protocol.query_scene(scene_id))
                info = protocol.parse_query_scene(scene_id, response)
                scenes[scene_id] = info.name
                if info.next_id == scene_id:
                    break
                scene_id = info.next_id
        except protocol.LampForbiddenError as err:
            raise HomeAssistantError(
                f"{self.name}: the lamp has a security code set and rejects "
                "local commands"
            ) from err
        except protocol.LampError as err:
            if not scenes:
                raise HomeAssistantError(
                    f"{self.name}: reading scenes failed ({err})"
                ) from err
        except BLE_ERRORS as err:
            raise HomeAssistantError(
                f"{self.name}: lamp not reachable over Bluetooth ({err})"
            ) from err
        self.state.scenes = scenes
        self.state.last_route = ROUTE_BLUETOOTH
        self.notify()
        return scenes

    async def read_device_info(self) -> dict[str, str]:
        """Read the Device Information Service. BLE only."""
        if self.ble is None:
            return {}
        info = await self.ble.read_device_info()
        self.state.device_info = info
        return info

    async def update_from_cloud(self) -> CloudState | None:
        """Refresh the assumed state from the cloud, if configured."""
        if not self.has_cloud:
            return None
        assert self.cloud is not None and self.cloud_lamp_id is not None
        cloud_state = await self.cloud.get_state(self.cloud_lamp_id)
        changed = False
        for attr in ("is_on", "brightness", "kelvin", "scene_id"):
            value = getattr(cloud_state, attr)
            if value is not None and getattr(self.state, attr) != value:
                setattr(self.state, attr, value)
                changed = True
        if changed:
            self.notify()
        return cloud_state
