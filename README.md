<p align="center">
  <img src="https://raw.githubusercontent.com/3DJupp/lukeroberts-homeassistant/main/custom_components/luke_roberts/brand/icon@2x.png" alt="Luke Roberts logo" width="128">
</p>

# Luke Roberts for Home Assistant

> Home Assistant integration for **Luke Roberts Model F and Luvo** smart lamps.
> Local control over Bluetooth through the adapters, ESPHome and Shelly
> Bluetooth proxies you already have, with scenes, brightness, colour
> temperature, uplight colour and the Luke Roberts cloud as optional fallback.
> Installable via HACS, no extra hardware, no extra firmware.

[![Validate](https://github.com/3DJupp/lukeroberts-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/3DJupp/lukeroberts-homeassistant/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![GitHub release](https://img.shields.io/github/v/release/3DJupp/lukeroberts-homeassistant?include_prereleases)](https://github.com/3DJupp/lukeroberts-homeassistant/releases)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-support-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/3djupp)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-support-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/3djupp)

> [!WARNING]
> **Early version (0.x).** This integration is new. It has been tested on
> real hardware, but setups vary. Expect rough edges and breaking
> changes before 1.0. Use it at your own risk and please
> [open an issue](https://github.com/3DJupp/lukeroberts-homeassistant/issues)
> when something does not work, ideally with the diagnostics download and a
> debug log attached.
>
> This is an independent community project. It is **not affiliated with,
> endorsed or supported by Luke Roberts GmbH**. See
> [Credits and trademarks](#credits-and-trademarks).

This is a native Home Assistant integration. It behaves like the Luke Roberts
smartphone app: when a Bluetooth adapter or proxy (ESPHome, Shelly, a USB
dongle on the HA host, ...) can reach the lamp, commands go straight to it over
Bluetooth LE. If the lamp is out of range and you added your Luke Roberts
account, the command is sent through the Luke Roberts cloud instead.

## Features

- **Auto discovery** of lamps through every Bluetooth adapter and proxy
- **Luke Roberts account**: enter the API key once, Bluetooth lamps are linked
  to the cloud automatically and lamps out of range are offered as discovered
  devices, just like the phone app shows all lamps of the account
- **Light entity**: on/off, brightness, colour temperature (2700 K to 4000 K),
  scenes as effects
- **Scene select** filled with the scene names stored in the lamp (read with
  `Query Scene` on startup, refresh with a button)
- Buttons for next brighter / dimmer scene, brighter / dimmer (relative
  brightness), refresh scenes and ping
- `luke_roberts.immediate_light` action for the transient Immediate Light
  command, including the **coloured uplight** (hue/saturation) and the
  downlight, with optional automatic revert
- **Create, change and delete scenes** in the lamp from Home Assistant
  (`luke_roberts.save_scene`, `luke_roberts.delete_scene`), experimental
- **Firmware entity** with the installed version and, with a firmware check
  key, the newest version from the Luke Roberts firmware server
- **Connection modes**: Bluetooth first with cloud fallback, Bluetooth only,
  cloud first, cloud only
- Short lived Bluetooth connections: the link is kept alive with pings for a
  configurable time after the last command, then released so the Luke Roberts
  app can connect again
- Lamps with a security code (status `FC Forbidden`) automatically fall back to
  the cloud if configured
- Device info (model, firmware, hardware revision) read from the lamp
- Diagnostics download with the API key redacted
- English and German translations

## Requirements

- Home Assistant 2025.2 or newer with the Bluetooth integration set up
- At least one connectable Bluetooth adapter or proxy within range of the lamp.
  ESPHome proxies need `bluetooth_proxy: active: true`; Shelly Gen2+ devices
  need Bluetooth gateway enabled with active scanning.
- Optional: a personal API key from <https://cloud.luke-roberts.com/app> for
  the Luke Roberts account (cloud fallback)
- The integration icon is shown from Home Assistant 2026.3 on (older versions
  just show a placeholder)

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=3DJupp&repository=lukeroberts-homeassistant&category=integration)

Or by hand:

1. Open HACS, click the three dots in the top right and choose
   *Custom repositories*.
2. Add `https://github.com/3DJupp/lukeroberts-homeassistant` with type
   *Integration*.
3. Search for **Luke Roberts**, install it and restart Home Assistant.

HACS offers updates automatically whenever a new release is published.

### Manual

Copy `custom_components/luke_roberts` into `<config>/custom_components/` and
restart Home Assistant.

## Setup

Lamps in range show up under *Settings → Devices & services → Discovered*.
Otherwise use *Add integration → Luke Roberts* and choose:

- **Lamp via Bluetooth**: pick a discovered lamp or type its Bluetooth address
- **Luke Roberts account**: sign in once with your personal API key, like the
  phone app. Home Assistant then
  - links every Bluetooth lamp to its cloud lamp (matched by serial number,
    otherwise by identical name), so it gets the cloud fallback without
    further setup,
  - offers all other lamps of the account under *Discovered*. Those are
    controlled through the cloud only.

The account cannot use your app e-mail and password: Luke Roberts only
documents the personal API key for third party use. Create one at
<https://cloud.luke-roberts.com/app>.

Each lamp's **Configure** dialog sets the connection mode, how long the
Bluetooth link is kept after the last command (default 30 s, 0 disconnects
immediately) and which cloud lamp it is linked to. An API key entered there
overrides the account for that lamp only.

### How lamps are recognised

A Bluetooth advertisement is treated as a Luke Roberts lamp when it contains
the control service UUID `44092840-0567-11E6-B862-0002A5D5C51B` or when its
advertised name starts with `LRBT` (e.g. `LRBTLAMP`) or `Luvo`. Once a lamp is
set up it is followed by its Bluetooth address, across all adapters and
proxies.

## Entities

| Entity | Description |
| --- | --- |
| `light.<lamp>` | On/off, brightness, colour temperature, scenes as effects |
| `select.<lamp>_scene` | Scene picker with the names from the lamp |
| `button.<lamp>_next_brighter_scene` / `_next_dimmer_scene` | Opcode `06` |
| `button.<lamp>_brighter` / `_dimmer` | Relative brightness ×1.2 / ×0.8 (opcode `08`) |
| `button.<lamp>_refresh_scenes` | Re-read scene names (diagnostic) |
| `button.<lamp>_ping` | Ping (diagnostic, disabled by default) |
| `sensor.<lamp>_last_command_route` | `bluetooth` or `cloud` (diagnostic) |
| `sensor.<lamp>_last_response` | Last status from the lamp (diagnostic) |
| `sensor.<lamp>_api_version` | API version from Ping (diagnostic, disabled by default) |
| `update.<lamp>_firmware` | Installed firmware, newest version if a firmware check key is set (diagnostic) |

Buttons only work over Bluetooth, the cloud API has no equivalent.

### How state works

The lamp cannot report its current state over Bluetooth, so the integration
keeps an *assumed state* based on the commands it sent (like the ESPHome
gateway did). Brightness is relative to the active scene: 100 % is the scene as
designed in the app. Changes made with the app or the lamp's click detection
are not visible locally. If the cloud is linked, the integration also polls
`GET /lamps/{id}/state` every minute to correct the assumed state.

### Immediate light example

```yaml
action: luke_roberts.immediate_light
target:
  entity_id: light.esstisch
data:
  uplight_hs_color: [30, 80]   # hue 0-360, saturation 0-100
  uplight_brightness: 60       # %
  downlight_kelvin: 2700
  downlight_brightness: 40     # %
  duration:
    seconds: 10                # 0 = keep until the next scene change
```

### Scenes from Home Assistant (experimental)

Scenes are stored in the lamp, so the Luke Roberts app and the lamp's click
detection see them too. The record format comes from the Luke Roberts app
2.4.0, it is not part of the published API. Uplight and downlight are set
evenly for all segments. Bluetooth only.

```yaml
action: luke_roberts.save_scene
target:
  entity_id: light.esstisch
data:
  name: Abendessen          # up to 20 bytes
  uplight_hs_color: [30, 80]
  uplight_brightness: 50
  downlight_kelvin: 2900
  downlight_brightness: 70
  activate: true            # select it right away
```

Add `scene: Lesen` (name or id) to overwrite an existing scene instead of
adding one. `luke_roberts.delete_scene` with `scene: Abendessen` removes it.
Scenes 0 (Off) and the default scene cannot be changed.

### Firmware

`update.<lamp>_firmware` shows the firmware read from the lamp. To also see
whether a newer version exists, enter a firmware check key in the lamp's
**Configure** dialog. The integration then asks the Luke Roberts firmware
server every 6 hours, the same way the app does. The key is the `Api-Key`
the Luke Roberts app uses for that server; it is not published here. Updates
are installed with the Luke Roberts app.

### Dashboard example

```yaml
type: vertical-stack
cards:
  - type: tile
    entity: light.esstisch
    features:
      - type: light-brightness
      - type: light-color-temp
  - type: tile
    entity: select.esstisch_scene
    features:
      - type: select-options
```

## Coming from the ESPHome gateway?

The first approach was a dedicated ESP32 per lamp running ESPHome:
**[3DJupp/lukeroberts-esphome-lampcontrol](https://github.com/3DJupp/lukeroberts-esphome-lampcontrol)**.
It works well, but it needs its own firmware, one board per lamp and a pile of
template buttons and helper automations for scene names.

This integration moves the protocol into Home Assistant itself. Everything the
ESPHome gateway learned about the lamp (frame layout, the 8 second idle
disconnect, scene discovery via Query Scene, ping keepalive) is reused here,
but the radio part is left to Home Assistant's Bluetooth stack. That means:

| | ESPHome gateway | This integration |
| --- | --- | --- |
| Extra hardware | one ESP32 per lamp | none, any existing adapter or proxy |
| Firmware to maintain | yes | no |
| Lamp entity | buttons and sensors | one `light` with brightness, colour temperature and scenes as effects |
| Scene dropdown with real names | needs the HA package from that repo | built in, updates automatically |
| Cloud fallback | no | optional |
| Multiple lamps | one config per lamp | add as many as you like |

If you already run the ESPHome gateway on an ESP32, you can keep using that
board as a plain [Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html)
for this integration.

## Protocols

Both documents were provided by Luke Roberts GmbH and are included with their
permission. Copyright stays with Luke Roberts GmbH or its successor company.

- [Lamp Control API v1.3](https://raw.githubusercontent.com/3DJupp/lukeroberts-homeassistant/main/docs/Lamp%20Control%20API%20v1.3.pdf) (Bluetooth LE,
  2019-07-09)
- [Third party REST API v1.0 draft](https://raw.githubusercontent.com/3DJupp/lukeroberts-homeassistant/main/docs/LR%20Cloud%20REST%20API%20v1.0.pdf)
  (cloud)

### Bluetooth LE

Service `44092840-0567-11E6-B862-0002A5D5C51B`, commands are written to
characteristic `44092842-0567-11E6-B862-0002A5D5C51B` and answered with an
indication on the same characteristic. Every frame starts with `A0` and the API
version.

| Action | Opcode | Frame |
| --- | :---: | --- |
| Ping | 00 | `A0 02 00` → `00 VV` |
| Query Scene | 01 | `A0 01 01 II` → `00 01 NN <name> 00` |
| Immediate Light | 02 | `A0 01 02 XX DDDD [SS HHHH BB] [KKKK BB]` |
| Brightness | 03 | `A0 01 03 PP` |
| Colour temperature | 04 | `A0 01 04 KKKK` |
| Select Scene | 05 | `A0 02 05 II` (`00` off, `FF` default) |
| Next scene by brightness | 06 | `A0 02 06 DD` |
| Adjust colour temperature | 07 | `A0 02 07 KKKK` |
| Relative brightness | 08 | `A0 02 08 PP` |

Status codes: `00` OK, `81` invalid parameters, `84` invalid id, `87` invalid
version, `BC` bad command, `FC` forbidden (security code set in the app).

### Cloud

`https://cloud.luke-roberts.com/api/v1`, `Authorization: Bearer <api key>`.
`GET /lamps` lists the lamps, `PUT /lamps/{id}/command` takes
`{"power": "ON"|"OFF"}`, `{"brightness": 0..100}`, `{"kelvin": 2700..4000}` or
`{"scene": 0..31}`. Commands are queued; there is no confirmation that the lamp
executed them.

## FAQ

### The lamp is not found / stays unavailable, but the ESPHome gateway works

A Luke Roberts lamp accepts only one Bluetooth connection and stops
advertising while it is connected. An ESP32 that still runs the
[ESPHome lamp gateway](https://github.com/3DJupp/lukeroberts-esphome-lampcontrol)
keeps that connection open, so Home Assistant neither discovers the lamp nor
can connect to it. Remove the `ble_client` from that ESP32 (keep it as a plain
`bluetooth_proxy` if you like) and the lamp shows up again. The same applies
while the phone app is connected.

To check what Home Assistant sees, download the diagnostics of the lamp: the
`bluetooth` section lists the last advertisement (source, RSSI, UUIDs) and
all scanners. For a debug log add:

```yaml
logger:
  logs:
    custom_components.luke_roberts: debug
    homeassistant.components.bluetooth: debug
```

A lamp whose firmware update failed stays in its bootloader and only
advertises `0000FE59`; open the Luke Roberts app to recover it.

**Can I control a Luke Roberts lamp from Home Assistant without the app?**
Yes. The lamp is controlled directly over Bluetooth LE. The app is only needed
to design scenes, which are stored in the lamp and then show up in Home
Assistant by name.

**Does it work without the Luke Roberts cloud?**
Yes. Bluetooth control is fully local. The cloud is optional and only used as
fallback when no adapter or proxy reaches the lamp.

**Do I need an ESP32 per lamp?**
No. Any Bluetooth adapter on the Home Assistant host or any ESPHome or Shelly
Bluetooth proxy within range is enough. One proxy can serve several lamps.

**Which lamps are supported?**
Luke Roberts Model F and Luvo, firmware 1.0.7 or newer for the full command
set.

**Can I change the uplight colour?**
Yes, with the `luke_roberts.immediate_light` action (hue, saturation and
brightness for the uplight, colour temperature and brightness for the
downlight).

**Does it work with Alexa, Google Home or Assist?**
The lamp is a normal Home Assistant light entity, so everything that can switch
and dim Home Assistant lights can control it.

**The Luke Roberts app shows "In Use" or "Waiting".**
Home Assistant is holding the Bluetooth connection. Lower *Keep Bluetooth
connection after the last command* in the options, 0 releases it right after
each command.

**I already have another Luke Roberts integration installed. Can I run both?**
No. Several community integrations use the same `luke_roberts` domain, and
Home Assistant only loads one integration per domain. Remove the other one
(and its folder in `custom_components`) before installing this one.

## Support the project

This integration is a hobby project. If it saves you an ESP32 per lamp or just
makes your evenings nicer, you can say thanks with a coffee:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/3djupp)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-3djupp-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/3djupp)

Bug reports with diagnostics and debug logs help just as much.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt ruff
pytest
ruff check . && ruff format --check .
```

The protocol layer (`protocol.py`) has no Home Assistant imports and is tested
against the byte sequences from the API document. `tests/test_init.py` runs the
full integration against a simulated lamp.

## Kurzfassung (Deutsch)

Native Home Assistant Integration für Luke Roberts Lampen (Model F und Luvo),
lokal steuern ohne App und ohne Cloud. Gesteuert wird lokal
per Bluetooth über die vorhandenen Adapter und Bluetooth Proxies (ESPHome,
Shelly, ...), optional mit der Luke Roberts Cloud als Rückfallebene, also so wie
die Smartphone App. Der erste Ansatz mit einem eigenen ESP32 pro Lampe liegt in
[lukeroberts-esphome-lampcontrol](https://github.com/3DJupp/lukeroberts-esphome-lampcontrol);
ein vorhandener ESP32 kann einfach als Bluetooth Proxy weiterverwendet werden.
Installation über HACS (Custom Repository), danach erscheinen Lampen in
Reichweite automatisch unter *Entdeckt*. Erkannt wird eine Lampe an der Service
UUID `44092840-…` oder am Bluetooth Namen (`LRBT…`, `Luvo…`). Optional fügst
du einmal dein **Luke Roberts Konto** (persönlicher API Key von
<https://cloud.luke-roberts.com/app>) hinzu: Bluetooth Lampen werden dann
automatisch mit der Cloud verknüpft und alle übrigen Lampen des Kontos werden
angeboten, so wie in der App.

Gefällt dir das Projekt? Über [Ko-fi](https://ko-fi.com/3djupp) oder
[Buy Me a Coffee](https://buymeacoffee.com/3djupp) kannst du es unterstützen.

**Hinweis:** Das ist eine frühe Version (0.1.x). Fehler und Änderungen bis zur
1.0 sind wahrscheinlich, Nutzung auf eigene Gefahr. Rückmeldungen gerne als
Issue. Das Projekt ist unabhängig und steht in keiner Verbindung zur Luke
Roberts GmbH. Name, Marken und Produkte gehören Luke Roberts bzw. der
Nachfolgefirma.

## Credits and trademarks

- **Luke Roberts GmbH** designed these lamps and kindly provided the Bluetooth
  *Lamp Control API* and the *Third party REST API* documentation, and gave
  permission to publish both documents in this repository. Thank you!
- "Luke Roberts", "Model F", "Luvo", the product names, logos and the lamps
  themselves are trademarks and property of Luke Roberts GmbH or its
  successor company. They are used here only to describe compatibility.
- The documents in [`docs/`](https://github.com/3DJupp/lukeroberts-homeassistant/tree/main/docs) remain the copyright of Luke Roberts GmbH
  or its successor company. The MIT license of this repository covers the
  integration code only, not those documents.
- The images in `custom_components/luke_roberts/brand/` are the Luke Roberts
  logo, a trademark of Luke Roberts GmbH or its successor company. They are
  used here only to show which lamps the integration works with.
- The Home Assistant Bluetooth stack and `bleak-retry-connector` make proxy
  based control possible.
- Earlier ESPHome approach:
  [lukeroberts-esphome-lampcontrol](https://github.com/3DJupp/lukeroberts-esphome-lampcontrol).

## License

Integration code: MIT, see [LICENSE](https://github.com/3DJupp/lukeroberts-homeassistant/blob/main/LICENSE). The API documents in `docs/`
are excluded, see above.
