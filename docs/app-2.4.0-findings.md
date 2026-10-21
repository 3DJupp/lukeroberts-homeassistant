# Luke Roberts Android app 2.4.0: findings

Static analysis of `eu.lukeroberts.lukeroberts` 2.4.0 (version code 273),
decompiled with jadx. Nothing was executed. Native Kotlin app, R8
obfuscated. Statements marked *guess* are not verified on a lamp.

## Servers

| Host | Purpose |
| --- | --- |
| `https://cloud.luke-roberts.com` | App backend: OAuth, phone as "bridge", state reports, scene sharing |
| `https://luke-roberts-firmware.firebaseapp.com` | Firmware lookup (needs an app specific `Api-Key` header) |
| `https://luke-roberts-support.firebaseapp.com` | Support form, user lookup |

Cloud paths used by the app (not the public third party API):

* `POST api/v1/bridges`, `DELETE api/v1/bridges/{bridgeId}`
* `PUT` / `DELETE api/v1/bridges/{bridgeId}/lamps/{serial}`
* `PUT api/v1/lamps/by_serial_number/{serial}/state` with
  `{color_temperature, brightness, is_on}`
* `POST api/v1/scenes`, `GET api/v1/scenes/{uuid}` (scene sharing)
* OAuth: `oauth/authorize` (scope `lamp-control`, redirect `lr-auth://success`),
  `POST oauth/token`

No `/api/v2` paths exist. The public `/lamps` and `/command` endpoints are not
used by the app.

## Firmware

* `GET api/v1/firmware/latest?app=Android&model=&firmware=&revision=&serial=&bootloader=&homekit=`
  returns `{version, file, releaseNotes}`; `file` is a URL to a Nordic DFU ZIP.
* `GET api/v1/firmware/recovery?id=`, `POST api/v1/firmware/usedby/{serial}`.
* The endpoint needs an API key embedded in the app. It is not reproduced
  here; using it from Home Assistant would need permission from Luke Roberts.
* OTA runs over BLE: indications on `8E400001-F315-4F60-9FB8-838830DAEA50`,
  write `0x01`, the lamp reboots into the Nordic Secure DFU bootloader
  (advertises `0000FE59`) and the Nordic DFU library flashes the ZIP.

A lamp stuck in the bootloader after a failed update only advertises
`0000FE59`, not the control service. Home Assistant will not discover it then.

## Bluetooth

The app scans for service `44092840-0567-11e6-b862-0002a5d5c51b` or
`0000FE59` (bootloader). It does not filter on name or manufacturer data.

| UUID `4409284x-0567-11e6-b862-0002a5d5c51b` | Purpose |
| --- | --- |
| `…41` | Settings record (read/write, 36 bytes) |
| `…42` | External API; response notification for every write |
| `…43` | Scene records |
| `…44` | Selected scene id (1 byte; notify/read/write) |
| `…45` | Live light model / scene preview |
| `…46` | PIN unlock and change |
| `…47` | Status, errors, events |
| `…48` | Orientation |

Writes to any of these characteristics are answered by a notification on
`…42`; byte 0 is the status (`0x00` OK, `0x85` scene memory full,
`0xFC`/`0xFD` locked).

API frame: `A0 <api> <opcode|flags> [PIN u16 if flag 0x40] [id u16 if flag 0x80] <data>`.

## Scenes

Scenes are written as raw records to `…43`, big endian:

* Header (8 bytes): `01, sceneId, sortIndex, wireType, int32 groupId`
* wireType 1, static scene (178 bytes): header, u16 downlight kelvin,
  uplight 16 segments × `[sat, u16 hue*65535 (or kelvin if sat=0), bri]`,
  downlight 84 bytes per spot brightness (rings of 0/3/6/…/21), 20 byte name
* wireType 2 (108 bytes): header, 80 zero bytes, name (*guess*: dynamic scene)
* wireType 3 (28 bytes): header and name
* wireType 0: delete
* New scenes are written with sceneId 254.

Reading: Sync command on `…42`, settings arrive on `…41`, scene records on
`…43`. Preview without saving: write `64, u16 kelvin, 64 B uplight, 84 B
downlight` to `…45`.

## Security

* "Protected" mode rejects commands without the security code. Unlock: write
  `00 <u16 PIN>` to `…46`. Remote commands carry the PIN with flag `0x40`.
* Bonding is not required by default. The app has a "Force bonding" option
  for lamps that loop between Offline and Synchronizing, so some lamps may
  only deliver notifications after bonding (*guess*).
