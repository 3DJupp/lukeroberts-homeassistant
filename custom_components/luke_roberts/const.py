"""Constants for the Luke Roberts integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "luke_roberts"
MANUFACTURER: Final = "Luke Roberts"

# --- Bluetooth LE (Lamp Control API v1.3) -----------------------------------
SERVICE_UUID: Final = "44092840-0567-11e6-b862-0002a5d5c51b"
API_CHAR_UUID: Final = "44092842-0567-11e6-b862-0002a5d5c51b"

# Device Information Service (0x180A)
DIS_MANUFACTURER_UUID: Final = "00002a29-0000-1000-8000-00805f9b34fb"
DIS_MODEL_UUID: Final = "00002a24-0000-1000-8000-00805f9b34fb"
DIS_SERIAL_UUID: Final = "00002a25-0000-1000-8000-00805f9b34fb"
DIS_FIRMWARE_UUID: Final = "00002a26-0000-1000-8000-00805f9b34fb"
DIS_HARDWARE_UUID: Final = "00002a27-0000-1000-8000-00805f9b34fb"
DIS_SOFTWARE_UUID: Final = "00002a28-0000-1000-8000-00805f9b34fb"

# The lamp drops idle links after 8 s (firmware >= 1.1.1). We keep the link
# alive with pings for a short window after the last command so follow-up
# commands are fast, then let go so the Luke Roberts app can connect again.
KEEPALIVE_INTERVAL: Final = 5.0
DEFAULT_LINGER: Final = 30

RESPONSE_TIMEOUT: Final = 5.0

# --- Cloud (Third party REST API v1.0) --------------------------------------
CLOUD_BASE_URL: Final = "https://cloud.luke-roberts.com/api/v1"
CLOUD_APP_URL: Final = "https://cloud.luke-roberts.com/app"

# --- Config entry keys ------------------------------------------------------
CONF_API_KEY: Final = "api_key"
CONF_CLOUD_LAMP_ID: Final = "cloud_lamp_id"
CONF_CONNECTION_MODE: Final = "connection_mode"
CONF_LINGER: Final = "linger"
CONF_DEFAULT_SCENE: Final = "default_scene"

MODE_LOCAL_FIRST: Final = "local_first"
MODE_LOCAL_ONLY: Final = "local_only"
MODE_CLOUD_FIRST: Final = "cloud_first"
MODE_CLOUD_ONLY: Final = "cloud_only"
CONNECTION_MODES: Final = [
    MODE_LOCAL_FIRST,
    MODE_LOCAL_ONLY,
    MODE_CLOUD_FIRST,
    MODE_CLOUD_ONLY,
]

# --- Lamp limits -------------------------------------------------------------
MIN_KELVIN: Final = 2700
MAX_KELVIN: Final = 4000

SCENE_OFF: Final = 0x00
SCENE_DEFAULT: Final = 0xFF

# Cloud API accepts scene ids 0..31; used when names are unknown (cloud only).
CLOUD_MAX_SCENE_ID: Final = 31

# --- Services ----------------------------------------------------------------
SERVICE_IMMEDIATE_LIGHT: Final = "immediate_light"
SERVICE_REFRESH_SCENES: Final = "refresh_scenes"
