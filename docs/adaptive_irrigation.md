# Adaptive Irrigation Integration — Complete Reference

**Version:** v0.6.9+  
**Source:** `/custom_components/adaptive_irrigation/` (custom HACS integration)  
**Status:** Deployed, active watering system

## Overview

The Adaptive Irrigation integration provides data-driven watering decisions for landscape zones. It replaces manual automation-based watering with:
- **Soil moisture sensing** — monitors volumetric water content in real-time
- **Weather-aware logic** — adjusts watering based on forecast rain, wind, evapotranspiration
- **Per-zone control** — each zone has independent thresholds and schedules
- **Budget tracking** — daily gallon cap for water conservation
- **Seedling mode** — automatic mode switch for newly planted areas (expires after 30 days)

## Configuration

### System Config (Entry Type: `system`)
Settings → Integrations → Adaptive Irrigation → Configure

| Setting | Default | Purpose |
|---------|---------|---------|
| **Weather entity** | `weather.forecast_home` | Forecast data for rain/wind/ET |
| **Watering window start** | 5:30 AM | Daily earliest watering time |
| **Watering window end** | 10:00 AM | Daily latest watering time (retry cutoff) |
| **Water meter** | — | Optional; tracks consumption |
| **Daily budget** | 0 (unlimited) | Daily gallon cap (0 = no limit) |

### Zone Config (Entry Type: `zone`)
One per irrigation zone. Settings → Integrations → Add → Adaptive Irrigation

| Setting | Default | Purpose |
|---------|---------|---------|
| **Zone name** | — | Identifier (e.g., "Yard East", "Drip Zone") |
| **Valve switch** | — | Switch entity that opens/closes water valve (required) |
| **Soil sensor** | — | Optional; `sensor.*_humidity` entity for real-time moisture |
| **Motion sensor** | — | Optional; `binary_sensor.*_motion` for irrigation deferrals |
| **Soil threshold** | 25% | Moisture % below which normal watering triggers (10–99%) |
| **Seedling threshold** | 35% | Moisture % below which seedling-mode watering triggers (10–99%) |
| **Max duration** | — | Max watering duration cap (minutes) |
| **Flow rate** | — | Gallons/min (for daily budget tracking) |
| **Water interval** | — | Base watering interval for sensor-free zones (days) |
| **Seedling expires** | Auto-set to now+30d | Date when seedling mode auto-expires (editable) |

## Zones

| Zone | Valve Switch | Soil Sensor | Motion Sensor | Notes |
|------|-------------|-------------|---------------|-------|
| **Yard East** | `switch.yardian_controller_yard_east` | `sensor.yard_east_soil_moisture` | `binary_sensor.yard_east_motion` | Alley-facing; use motion for traffic deferrals |
| **Yard Middle** | `switch.yardian_controller_yard_middle` | avg(east + west) | `binary_sensor.yard_gazebo_slider_motion` | Gazebo area |
| **Yard West** | `switch.yardian_controller_yard_west` | `sensor.yard_west_soil_moisture` | `binary_sensor.yard_west_motion` | Alley-facing; use motion for traffic deferrals |
| **Front Yard** | `switch.yardian_controller_front_yard` | `sensor.yard_front_soil_moisture` | — | No motion sensor yet |
| **Drip Zone** | `switch.yardian_controller_drip` | — | — | Sensor-free; peer trend only |

### Soil Sensor Calibration (Third Reality, 2026-05-17)
Accurate within ~10% across full range. Currently reading 97–99% (saturated post-watering).
- **Normal threshold:** 25% moisture
- **Seedling threshold:** 35% moisture
- All sensors report `sensor.*_humidity` (percentage)

## Decision Logic

### Watering Decision Cycle
Runs every 15 minutes. Startup guard skips first cycle; real decisions begin on second poll (~15 min after HA start).

For each zone:
1. **Check conditions:**
   - Soil moisture above threshold? → skip (idle)
   - Current time outside watering window? → defer to next window
   - Motion detected? → defer (person in area)
   - Forecast rain > threshold? → skip (natural watering)
   - Daily budget exceeded? → pause all zones

2. **Calculate duration:**
   - Base on soil moisture deficit and flow rate
   - Cap at `max_duration` setting
   - Respect daily gallon budget

3. **Execute:** Open valve for calculated duration, then close

### Per-Zone Status Entities
| Entity Pattern | Description |
|---------------|-------------|
| `sensor.*_status` | Current decision: watering / skipped / idle / paused |
| `sensor.*_moisture` | Live soil moisture % |
| `sensor.*_moisture_trend` | %/hr trend (linear regression over 6h) |
| `sensor.*_last_watered` | Timestamp of last valve close |
| `sensor.*_et_today` | Evapotranspiration today (inches) |
| `sensor.*_rain_forecast` | Forecast precip (inches) |
| `sensor.*_wind_forecast` | Forecast wind (mph) |
| `switch.*_auto_watering` | Enable/disable automated watering for zone |
| `switch.*_seedling_mode` | Seedling mode toggle |
| `number.*_soil_threshold` | Moisture % trigger for normal watering (adjustable) |
| `number.*_seedling_threshold` | Moisture % trigger for seedling watering (adjustable) |
| `number.*_max_duration` | Max watering duration cap (adjustable) |
| `number.*_flow_rate` | Gallons/min (adjustable) |
| `number.*_water_interval` | Base interval for sensor-free zones (adjustable) |
| `number.*_soak_cycles` | Number of soak/cycle runs (1 = single run, 2–5 = split with pauses) |
| `number.*_soak_pause_minutes` | Minutes between soak cycles (default 30) |
| `datetime.*_seedling_expires` | Auto-set 30 days after seedling mode activates; editable |

### System-Level Entities
| Entity | Description |
|--------|-------------|
| `switch.adaptive_irrigation` | Master system ON/OFF |
| `switch.adaptive_irrigation_water_restriction` | Emergency block (drought/HOA restrictions) |
| `select.configuration_watering_window_start` / `_end` | Daily watering window (time labels) |
| `number.adaptive_irrigation_daily_water_budget` | Daily gallon cap (0 = unlimited) |
| `sensor.adaptive_irrigation_daily_water_used` | Gallons used today |
| `sensor.configuration_weather_source` | Active weather entity |

## Seedling Mode

**Activation:** Turn on `switch.{zone}_seedling_mode` from dashboard or automation.

**Behavior:**
- Uses `seedling_threshold` (default 35%) instead of `soil_threshold` (default 25%)
- More frequent watering to support young plants
- All zones use the same configurable watering window (no separate time gates)
- `datetime.*_seedling_expires` auto-sets to now+30 days on first poll after mode activates
- Editable from dashboard; when expiry passes, mode is turned off automatically + notification posted

## Services

### `adaptive_irrigation.water_zone`
Manually trigger a zone to water immediately.
- `zone_id` — zone identifier (e.g., "Yard East" or "yard_east")
- `duration_minutes` — watering duration in minutes

### `adaptive_irrigation.evaluate_now`
Force immediate decision cycle for a zone (skips 15-minute wait).
- `zone_id` — zone identifier

**Zone ID format:** Accepts both "Yard East" and "yard_east" forms.

## Poll Cycle & Startup Behavior
- **Default interval:** 15 minutes
- **Startup guard:** Skips watering decisions on first poll; real decisions begin on second poll (~15 min after HA start)
- **Override:** Use `evaluate_now` service to force immediately

## External Consumers of Zone Entities

`script.backyard_recovery_deep_soak` (the dashboard's "Recovery Catchup Soak") reads
`sensor.adaptive_irrigation_<zone>_moisture` and `number.adaptive_irrigation_<zone>_soil_threshold`
directly to decide which zones to run, re-checked before each of its 3 cycles. It bypasses
the coordinator entirely and drives the Yardian valve switches itself, so it is **not**
subject to `min_interval`, the daily water budget, or motion deferral.

Renaming or removing those two entity patterns will silently break that gate — it fails
open, so the breakage manifests as every zone watering rather than an error. Full
behavior documented in `/mnt/nas/ai-workspace/documentation/homeassistant/irrigation.md`.

## Known Issues & Workarounds

### East Sensor Staleness (2026-05-17)
`sensor.yard_east_soil_moisture` drops offline overnight (last update ~11pm). Zigbee integration loses connection; hardware is fine. 
- **Workaround:** Staleness window extended from 4h → 8h
- **Long-term fix:** Investigate Zigbee coordinator health, sensor battery, reporting interval config

## Deferred Work

See `../TODOS.md` for irrigation-related enhancements (per-zone watering windows, sensor redundancy, etc.).
