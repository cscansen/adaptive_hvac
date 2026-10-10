# Rave Lights — HTD Zone Sync

## What it does

Two automations keep the Govee Rave lights in sync with their HTD audio zones:

| Light | Entity | Zone | Volume cover |
|-------|--------|------|--------------|
| Living Room Rave | `light.h610a` | Main Floor (`media_player.main_floor`) | `cover.volume_main_floor` |
| Family Room Rave | `light.h610a_2` | Second Floor (`media_player.second_floor`) | `cover.volume_second_floor` |

## Behavior

- **Zone turns on** → light turns on at brightness mapped to current volume
- **Zone turns off** → light turns off
- **Volume changes while zone is on** → brightness updates in real time

## Brightness mapping

Volume (0–100%) maps to brightness (70–100%):

```
brightness_pct = 70 + (volume_position × 0.3)
```

| Volume | Brightness |
|--------|-----------|
| 0% | 70% |
| 60% | 88% |
| 80% | 94% |
| 100% | 100% |

The floor is 70% so the lights are never distractingly dim at normal listening volumes.

## Automation IDs

- `rave_lights_main_floor_sync`
- `rave_lights_second_floor_sync`

Mode: `restart` — rapid volume changes cancel the previous action rather than queuing.

## Notes

- On HA restart or automation reload, lights won't sync until the next zone/volume state change. Trigger manually via Developer Tools → Automations if needed.
- The Govee h610a is branded "Lively" by Govee; named "Rave" internally.
