# Changelog

## Unreleased

- Brand images: the neutral lamp drawing is replaced by the Luke Roberts logo
  (icon and logo, with dark mode variants) in `brand/`.

## 0.2.3

No changes to the integration itself. Release for the submission to the
HACS default repository.

- Validate workflow: the HACS check runs without ignores (the brands check
  passes with the bundled `brand/icon.png`), and both HACS and hassfest
  validation also run daily.

## 0.2.2

- Firmware check: a lamp that is up to date showed no newest version, because
  the firmware server answers `{}` then. It now shows "up to date".
- Firmware check runs right after start and every 6 hours (was 12). After a
  restart it uses the firmware version stored on the device, so the lamp
  does not have to be reachable over Bluetooth first.
- Failed firmware checks are logged as a warning instead of only at debug
  level.
- Lamp details (model, firmware, scenes) are read again when the first
  attempt timed out, as soon as a connection succeeds, and when the lamp shows
  up again after a gap (for example a firmware update with the app). Before,
  they were only read once per start.

## 0.2.1

- **Scenes from Home Assistant** (experimental): `luke_roberts.save_scene`
  creates or overwrites a scene in the lamp, `luke_roberts.delete_scene`
  removes one. Record format from the Luke Roberts app 2.4.0.
- **Firmware entity**: installed firmware, and with a firmware check key in
  the lamp options the newest version and release notes from the Luke Roberts
  firmware server
- Device page shows the firmware version (2A28) instead of the bootloader
  revision (2A26)
- Diagnostics list what the Bluetooth adapters and proxies last saw of the
  lamp; setup logs a hint when no connectable scanner sees it (for example
  while an ESPHome gateway or the phone app holds the connection)
- Status `0xFD` (locked) is treated like a security code, `0x85` reports a
  full scene memory

## 0.2.0

- **Luke Roberts account**: add the API key once. Bluetooth lamps are linked
  to their cloud lamp automatically (serial number or name) and the other
  lamps of the account are offered as discovered devices. This replaces the
  "cloud only" setup per lamp; existing entries keep working.
- A rejected account key asks for a new key once on the account instead of
  on every lamp
- Discovery also matches lamps by advertised name (`LRBT…`, `Luvo…`), for
  proxies that do not see the service UUID in passive scans
- Integration icon shipped in `brand/` (Home Assistant 2026.3+)
- Ko-fi / Buy Me a Coffee links, issue templates, Dependabot for actions

## 0.1.0 (first preview)

First public preview. Expect bugs and breaking changes before 1.0.

- Local control over Bluetooth LE through Home Assistant adapters and
  Bluetooth proxies (ESPHome, Shelly, ...), with automatic discovery
- Optional Luke Roberts cloud fallback via personal API key, four
  connection modes
- Light entity with brightness, colour temperature and scenes as effects
- Scene select with the names stored in the lamp
- Buttons for next brighter/dimmer scene, brighter/dimmer, refresh scenes,
  ping
- `luke_roberts.immediate_light` action for uplight colour and downlight
- Diagnostics download, English and German translations
