# Changelog

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
