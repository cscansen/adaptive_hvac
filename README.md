# Adaptive HVAC

A Home Assistant integration for adaptive, intelligent HVAC control based on temperature, occupancy, and environmental conditions.

## Features

- **Global & Per-Room Control**: System-level AC, heating, and setback configuration with per-room cooling thresholds
- **Primary Zone Gating**: Only primary zone triggers system-level AC decisions; others are advisory
- **Per-Room Auto-Control**: Toggle automatic fan control on/off per room (e.g., Tia's office manual-only)
- **Nullable Fan Speeds**: Skip specific cooling steps per fan (e.g., no passive stage, jump straight to escalate)
- **Passive Cooling**: Whole-house fan + room circulation based on temperature and humidity
- **Windows Open Detection**: System-wide sensor gates passive/emergency cooling behavior
- **Occupancy-Based Setback**: Cool/heat setbacks when unoccupied for configurable hours
- **Seasonal Logic**: Summer (AC), shoulder (passive only), winter (heat) with forecast-based triggers
- **Trend Analysis**: Temperature trends inform preemptive passive cooling activation

## Installation

Add as a custom repository in HACS:

1. **Settings** → **Devices & Services** → **Integrations** (menu)
2. **Custom Repositories**
3. URL: `https://github.com/cscansen/adaptive_hvac`
4. Category: **Integration**

## Configuration

### System Setup
Configure globally:
- Thermostat, weather, solar, sleep mode sensors
- AC setpoint, solar trigger, humidity threshold
- Heating thresholds (global, applies to all zones)
- Setback temperatures and unoccupied duration
- Windows open sensor, passive cooling toggle

### Room Setup
Per room, configure:
- Zone name, floor, occupancy sensor
- Temperature sensors (primary triggers decisions)
- Cooling thresholds (comfort, passive, escalate, emergency)
- Auto-control toggle (e.g., **off** for Tia's office = user-only control)
- Fan configuration (linked to global fan pool with per-mode speeds)

## Architecture

**ZoneCoordinator**: Evaluates each room's temperature and issues fan commands based on cooling thresholds and mode speeds.

**SystemCoordinator**: Aggregates zone decisions, applies primary zone gating, manages thermostat mode/setpoint, and controls whole-house fan.

**Logic Engine**: Pure decision trees (no HA imports) — easy to test, reason about, and extend.

## Debugging

Check `Developer Tools` → `States` for:
- `sensor.adaptive_hvac_<zone>_status` — current mode per room
- `sensor.adaptive_hvac_<zone>_decision` — reasoning and fan commands
- `switch.adaptive_hvac_<zone>_auto` — auto-control toggle

Reload integration to apply config changes without restarting HA.

## License

MIT License — see LICENSE file.

## Contributing

Issues and PRs welcome. Please ensure manifests are valid and integration loads cleanly after changes.
