# Adaptive HVAC

A dynamic, multi-zone HVAC integration for Home Assistant that replaces static automation with intelligent, coordinated control.

## Overview

**adaptive_hvac** coordinates heating and cooling across multiple zones with a single thermostat, using:
- **Temperature trend awareness** — escalates/throttles based on rate of change, not just absolute temps
- **Forecast-driven pre-cooling and pre-heating** — ventilates before hot days, warms before cold nights
- **Weather-derived seasons** — automatically detects summer/winter/shoulder from 7-day forecasts
- **Full decision transparency** — status sensors show *why* the system is in each mode
- **Dashboard-configurable thresholds** — adjust comfort ranges without editing JSON

## Architecture

**Two entry types:**

1. **System entry** (one per installation)
   - Thermostat entity
   - Weather forecasts
   - Solar production
   - House-level occupancy
   - Global thresholds and seasonal logic

2. **Zone entries** (one per room/floor)
   - Temperature sensors (averaged)
   - Humidity sensor
   - Ceiling fans
   - Window sensor
   - Zone-level occupancy
   - Per-zone threshold overrides

## State Machine

The coordinator runs a prioritized decision tree every 3 minutes:

```
MANUAL_OVERRIDE                       — User manual control
SENSOR_FAILSAFE                       — Primary sensor unavailable
EMERGENCY_COOLING (>78°F)             — Max fans + AC
EMERGENCY_HEATING (<55°F)             — Max heat
SETBACK_UNOCCUPIED (>8h unoccupied)  — Away mode
SETBACK_NIGHT (sleep posture on)     — Night mode
PRE_COOL (forecast >92°F)             — Morning ventilation
PRE_HEAT (forecast <30°F)             — Pre-warm
AC_COOLING (>74°F, escalated)         — Active cooling
PASSIVE_COOLING (>72°F)               — Fans only
PASSIVE_WINDOWS_OPEN                 — Ventilation mode
HEATING_NORMAL (winter, <68°F)       — Normal heat
EQUALIZATION (floor delta >5°F)       — Circulation
IDLE                                  — Comfortable
```

## Entities Exposed

### System-level (Configuration device)
- `sensor.adaptive_hvac_status` — Full reasoning + current mode
- `sensor.adaptive_hvac_mode` — Thermostat mode
- `sensor.adaptive_hvac_season` — Derived season
- `switch.adaptive_hvac` — System active/paused
- `switch.adaptive_hvac_manual_override` — Block all automation
- `select.adaptive_hvac_season_override` — Force summer/winter/shoulder
- `number.adaptive_hvac_*` — 18 configurable thresholds

### Zone-level (per room/floor)
- `sensor.<zone>_hvac_status` — Zone mode + reasoning
- `sensor.<zone>_hvac_temp_trend` — °F/hr trend
- `switch.<zone>_hvac_auto` — Zone automation enabled

## Setup

1. **Create system entry first:**
   - Settings → Integrations → Add → Adaptive HVAC
   - Select thermostat, weather entity, optional solar/occupancy

2. **Add zones:**
   - Settings → Integrations → Add → Adaptive HVAC
   - For each zone: name, temperature sensors, fans, window sensor, occupancy

3. **Configure thresholds (optional):**
   - Dashboard sliders for all comfort ranges, fan speeds, setpoints
   - All changes persist across restarts

## Key Features

### Temperature Trend Awareness
- **Trend > 0.8°F/hr**: Pre-emptively start fans while still comfortable
- **Trend > 1.5°F/hr**: Skip escalation delays, go straight to AC
- **Trend < -0.5°F/hr**: Throttle back from AC, return to passive

### Forecast Integration
- **Pre-cool**: When forecast high >92°F and outdoor is still cooler, ventilate at 6–10am
- **Pre-heat**: When forecast low <30°F, warm house at 4–9pm before cold night
- **Season derivation**: 7-day avg high >75°F = summer, low <40°F = winter (with 3-poll hysteresis)

### Multi-Zone Arbitration
- Each zone independently decides what it needs
- System thermostat responds to most demanding zone
- Hottest zone in summer wins → AC target drops
- Coldest zone in winter wins → heat setpoint rises

### Fan Lock Integration
- Respects user-claimed fans (set by `fan_lock_*` automations)
- Skips claimed fans when dispatching HVAC commands
- Allows manual fan control without breaking automation

## Services

### `adaptive_hvac.force_evaluate`
Trigger immediate decision cycle (skip 3-min poll).

### `adaptive_hvac.set_manual_override`
Enable/disable manual override (blocks all automation).

## Configuration

All thresholds configurable via dashboard number sliders:

| Threshold | Default | Range |
|-----------|---------|-------|
| Comfort upper | 70°F | 60–80 |
| Passive trigger | 72°F | 60–85 |
| Escalate trigger | 74°F | 60–85 |
| Emergency cooling | 78°F | 70–110 |
| AC setpoint | 68°F | 60–78 |
| Heat threshold | 68°F | 50–72 |
| Heat setpoint | 68°F | 55–75 |
| Emergency heat | 55°F | -10–50 |
| Unoccupied cool setback | 76°F | 72–85 |
| Unoccupied heat setback | 62°F | 55–68 |
| Night setback | 62°F | 55–68 |
| Unoccupied duration | 8h | 1–24h |
| Pre-cool forecast trigger | 92°F | 75–110 |
| Pre-heat forecast trigger | 30°F | -20–50 |
| Summer threshold | 75°F | 60–90 |
| Winter threshold | 40°F | -20–60 |
| Passive fan speed | 33% | 0–100 |
| Escalate fan speed | 50% | 0–100 |

## Status Sensor Example

```
SYSTEM: cool 68 | Upstairs 72.4°F (+0.8°F/h), AC 50% | Master Bed 69.1°F (-0.2°F/h), Idle
```

Attributes:
- `thermostat_mode`: cool
- `thermostat_setpoint`: 68
- `whole_house_fan`: on
- `season`: summer
- `reasoning`: Weather forecast shows 95°F high | Upstairs trend rising | Master bed comfortable

## Differences from Old HVAC Automations

| Feature | Old (9 automations) | New (adaptive_hvac) |
|---------|-------------------|---------------------|
| Thresholds | Hardcoded in JSON | Dashboard sliders |
| Decision visibility | None | Status sensor with full reasoning |
| Fan conflicts | hvac_cooling vs hvac_equalization fight | Single coordinator, no conflicts |
| Trend awareness | Only absolute temps | °F/hr with early escalation |
| Forecast use | None | Pre-cool/pre-heat from 7-day forecast |
| Season logic | Calendar dates (May 1, Oct 1, Apr 1) | Weather-derived (7-day avg) |
| State transparency | Multiple flags (`hvac_managed_heating`, etc) | Single mode per zone |

## Running Alongside Old System

The new integration can run **parallel** to old automations with zero interference:

1. Both check same sensors, but process them independently
2. Coordinator reads current thermostat state before deciding
3. Use `switch.adaptive_hvac` to disable integration while testing old system
4. New system still logs to `sensor.adaptive_hvac_status` for debugging

Once validated stable, disable old automations one zone at a time.

## Development

Pure decision engine in `logic.py` — unit testable with no HA imports:

```python
from adaptive_hvac.logic import ZoneState, ZoneConfig, decide_zone

zone = ZoneState(zone_name="Office", temp=73.5, temp_trend=+0.8, ...)
cfg = ZoneConfig(passive_threshold=72.0, escalate_threshold=74.0, ...)
decision = decide_zone(zone, [zone], sys_state, cfg, sys_cfg)

assert decision.mode == "passive_cooling"
assert decision.thermal_request == "off"
```

## TODO / Known Limitations

- **Phase 2:** Lovelace dashboard card
- **Phase 3:** Mode transition history / event log
- **Limitation:** 7-day forecast averaging simplified (uses today's forecast for all days)
- **Limitation:** Occupancy tracking uses binary sensors only (no duration history yet)

## License

Same as Home Assistant.
