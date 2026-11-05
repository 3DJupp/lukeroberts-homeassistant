# Dashboard

A complete dashboard for one lamp, built only from core Home Assistant cards.
Replace `esstisch` with the entity id of your lamp. Entity ids follow the
language Home Assistant was set to when the lamp was added, for example
`button.esstisch_dunkler` instead of `button.esstisch_dimmer` in German.
**Settings → Devices & services → Luke Roberts → your lamp** lists them.

## Control

The controls are shown while the lamp is reachable over Bluetooth (the
buttons only exist on the Bluetooth API and turn *unavailable* otherwise).

```yaml
type: vertical-stack
cards:
  - type: heading
    heading: Luke Roberts Lamp
    icon: mdi:lamp
  - type: tile
    entity: light.esstisch
    features:
      - type: light-brightness
      - type: light-color-temp
  - type: conditional
    conditions:
      - condition: state
        entity: button.esstisch_brighter
        state: unavailable
    card:
      type: markdown
      content: >
        **Lamp not reachable over Bluetooth.**


        Waiting for the lamp to advertise. If this persists, check that the
        lamp has power and that a Bluetooth adapter or proxy is in range.
  - type: conditional
    conditions:
      - condition: state
        entity: button.esstisch_brighter
        state_not: unavailable
    card:
      type: vertical-stack
      cards:
        - type: grid
          columns: 2
          square: false
          cards:
            - type: button
              entity: light.esstisch
              name: "Off"
              icon: mdi:lamp-outline
              show_state: false
              tap_action:
                action: perform-action
                perform_action: light.turn_off
                target:
                  entity_id: light.esstisch
            - type: button
              entity: light.esstisch
              name: Default
              icon: mdi:restore
              show_state: false
              tap_action:
                action: perform-action
                perform_action: light.turn_on
                target:
                  entity_id: light.esstisch
        - type: tile
          entity: select.esstisch_scene
          features:
            - type: select-options
        - type: grid
          columns: 2
          square: false
          cards:
            - type: button
              entity: button.esstisch_next_dimmer_scene
              name: Dimmer scene
              icon: mdi:arrow-down-bold
              show_state: false
              tap_action:
                action: perform-action
                perform_action: button.press
                target:
                  entity_id: button.esstisch_next_dimmer_scene
            - type: button
              entity: button.esstisch_next_brighter_scene
              name: Brighter scene
              icon: mdi:arrow-up-bold
              show_state: false
              tap_action:
                action: perform-action
                perform_action: button.press
                target:
                  entity_id: button.esstisch_next_brighter_scene
        - type: grid
          columns: 3
          square: false
          cards:
            - type: button
              entity: button.esstisch_dimmer
              name: Dimmer
              icon: mdi:brightness-3
              show_state: false
              tap_action:
                action: perform-action
                perform_action: button.press
                target:
                  entity_id: button.esstisch_dimmer
            - type: button
              entity: light.esstisch
              name: 50 %
              icon: mdi:brightness-5
              show_state: false
              tap_action:
                action: perform-action
                perform_action: light.turn_on
                target:
                  entity_id: light.esstisch
                data:
                  brightness_pct: 50
            - type: button
              entity: button.esstisch_brighter
              name: Brighter
              icon: mdi:brightness-7
              show_state: false
              tap_action:
                action: perform-action
                perform_action: button.press
                target:
                  entity_id: button.esstisch_brighter
```

### Lamp behind a switchable power supply

If the lamp hangs on a relay (an ESPHome relay or any other `switch` or
`light` entity), add the relay to the stack and to both conditions, so the
hint only appears while the lamp has power:

```yaml
  - type: tile
    entity: switch.esstisch_power
    name: Power
    icon: mdi:power-plug
```

```yaml
    conditions:
      - condition: state
        entity: switch.esstisch_power
        state: "on"
      - condition: state
        entity: button.esstisch_brighter
        state: unavailable
```

## Diagnostics

`button.esstisch_ping` and `sensor.esstisch_api_version` are disabled by
default; enable them on the entity page first or remove them from the card.

```yaml
type: entities
title: Diagnostics
show_header_toggle: false
entities:
  - entity: select.esstisch_relative_brightness_mode
    name: Brighter / Dimmer mode
    icon: mdi:flask-outline
  - entity: button.esstisch_refresh_scenes
    name: Refresh scenes
    icon: mdi:numeric-10-box-multiple-outline
  - entity: button.esstisch_ping
    name: Ping
    icon: mdi:access-point
  - entity: sensor.esstisch_last_command_route
    name: Last command route
  - entity: sensor.esstisch_last_response
    name: Last response
    icon: mdi:message-reply-text
  - entity: sensor.esstisch_api_version
    name: API version
  - entity: update.esstisch_firmware
    name: Firmware
```

## Testing Brighter / Dimmer

It is not confirmed yet how the lamp firmware reads the Relative Brightness
command (opcode `08`). The Lamp Control API v1.3 says it multiplies the
current brightness by `PP / 100`; the Luke Roberts app 2.4.0 labels the same
byte as a signed change ("+20 % brighter", "−20 % darker").
`select.esstisch_relative_brightness_mode` switches between both:

| Mode | Dimmer | Brighter |
| --- | --- | --- |
| `multiply` (default) | `A0 02 08 50` (×0.8) | `A0 02 08 7D` (×1.25) |
| `delta` | `A0 02 08 EC` (−20) | `A0 02 08 14` (+20) |

To find out which one your lamp understands:

1. Select a scene and set the light to 100 %.
2. Press **Dimmer** a few times, then **Brighter** a few times.
3. Switch the mode, select the scene again and repeat.

The right mode dims step by step and brightens back up to the scene's
brightness. With the wrong one the buttons do nothing or the opposite
(Dimmer brightens, Brighter dims sharply). Note that in both modes the lamp never goes brighter than the
scene itself. Please report the result in the issue tracker together with
the firmware version.
