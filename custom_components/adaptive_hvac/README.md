# Adaptive HVAC — Home Assistant Integration

A custom Home Assistant integration for intelligent, adaptive HVAC control based on temperature, humidity, occupancy, and environmental conditions.

## Features

- **System + Zone Architecture**: Global AC/heating/setback config with per-room cooling control
- **Primary Zone Gating**: Only primary zone can activate AC; others are advisory
- **Per-Zone Auto-Control**: Toggle automatic fan control on/off per room (e.g., user-only mode for Tia's office)
- **Nullable Fan Speeds**: Skip specific cooling steps per fan (null = skip, 0 = off, 1-100 = %)
- **Passive Cooling**: Whole-house fan + room circulation based on temperature and humidity
- **Windows Open Detection**: System-wide and per-zone window sensors for natural ventilation
- **Humidity-Based Cooling**: Triggers passive mode when humidity exceeds threshold
- **Occupancy-Based Setback**: Cool/heat setbacks when unoccupied for configurable hours
- **Seasonal Logic**: Summer (AC), shoulder (passive only), winter (heat)
- **Temperature Trend Analysis**: Preemptive passive cooling based on rate of change
- **Pure Decision Logic**: No Home Assistant imports in logic layer — easy to test and extend

## Installation

1. **Custom Repositories** (via HACS):
   - Settings → Devices & Services → Integrations (menu) → Custom Repositories
   - URL: `https://github.com/cscansen/adaptive_hvac`
   - Category: Integration
   - Install `Adaptive HVAC`

2. **Restart Home Assistant**

3. **Add Integration**:
   - Settings → Devices & Services → Integrations → Create Integration
   - Search for "Adaptive HVAC"
   - Follow setup wizard (system entry first, then zone entries)

## Configuration

### System Entry (Global)

Configure once for the entire system:

| Setting | Type | Default | Notes |
|---------|------|---------|-------|
| Thermostat | climate entity | `climate.downstairs_thermostat` | Controls mode, setpoint, fan |
| Weather | weather entity | `weather.forecast_home` | For forecast-based triggers |
| Solar (optional) | sensor entity | — | Solar irradiance for AC escalation |
| Sleep Posture (optional) | input_boolean | — | Block heating during sleep |
| Occupancy Sensors (optional) | binary_sensor(s) | — | For unoccupied setback logic |
| AC Enabled | boolean | `true` | Master AC on/off |
| AC Setpoint | number °F | `68` | Thermostat setpoint when AC activates |
| Heat Threshold | number °F | `68` | Trigger heating when below this |
| Heat Setpoint | number °F | `68` | Target heating temperature |
| Emergency Heat | number °F | `55` | Emergency heating (any season) |
| Setback Cool | number °F | `76` | Cooling setpoint when unoccupied |
| Setback Heat | number °F | `62` | Heating setpoint when unoccupied |
| Unoccupied Hours | number | `8` | Hours before setback activates |
| Windows Sensor | binary_sensor | — | System-wide window open sensor |
| Window Fan Speed | number % | `25` | Fan speed when windows open |
| Passive Cooling | boolean | `true` | Enable whole-house fan |

### Zone Entry (Per Room)

Add one entry per room/zone:

| Setting | Type | Default | Required |
|---------|------|---------|----------|
| Zone Name | string | — | ✓ |
| Floor | string | — | — |
| Primary Zone | boolean | `false` | — |
| Auto-Control Enabled | boolean | `true` | — |
| Temperature Sensors | sensor(s) | — | ✓ |
| Humidity Sensor | sensor | — | — |
| Window Sensor | binary_sensor | — | — |
| Occupancy Sensor | binary_sensor | — | — |
| **Comfort Upper** | number °F | `70` | — |
| **Passive Threshold** | number °F | `72` | — |
| **Humidity Trigger** | number % | `55` | — |
| **Escalate Threshold** | number °F | `74` | — |
| **Emergency Threshold** | number °F | `78` | — |

**Thresholds define the cooling decision tree:**
- Below comfort → fans off
- Between comfort and passive → moderate circulation
- At/above passive → passive cooling (whole-house fan)
- At/above escalate → AC activation (if primary zone)
- At/above emergency → maximum cooling

## Entities Created

### Sensor Entities
- `sensor.adaptive_hvac_{zone}_status` — Current mode and reasoning
- `sensor.adaptive_hvac_{zone}_trend` — Temperature trend (°F/hr)

### Switch Entities
- `switch.adaptive_hvac_{zone}_auto` — Auto-control toggle (ON = auto, OFF = user-only)

## Usage

### Dashboard Monitoring

Check real-time state in Developer Tools → States:
- `sensor.adaptive_hvac_*_status` — Zone status + mode
- `switch.adaptive_hvac_*_auto` — Auto-control state

### Disable Auto-Control for a Zone

Toggle the zone's auto switch OFF to operate in user-only mode (fan commands suppressed).

### Force Evaluation

Call service to trigger immediate HVAC decision cycle:
```
Service: adaptive_hvac.force_evaluate
```

### Manual Override

Create an input_boolean and use in automations to gate the integration:
```yaml
condition: state
entity_id: input_boolean.hvac_manual_override
state: 'off'
```

## Architecture

**ZoneCoordinator**: Reads zone temps/humidity/sensors, evaluates cooling decision tree, issues fan commands.

**SystemCoordinator**: Aggregates zone decisions, applies primary zone gating, controls thermostat mode/setpoint and whole-house fan.

**Logic Engine**: Pure decision functions (`decide_zone()`, `decide_system()`) with no Home Assistant imports — easy to test independently.

## Cooling Decision Tree (Summer)

1. **Comfort** (`< 70°F`) → fans off
2. **Passive** (`≥ 72°F` OR `humidity ≥ 55%` at `≥ 72°F`) → fans at passive_speed (33%)
3. **Windows Open** (system sensor OR per-zone sensor) → fans at window_speed (25%), thermostat OFF
4. **Escalate** (`≥ 74°F` for 30+ min OR trend `> 1.5°F/hr`) → fans 50%, AC at 68°F (if primary zone)
5. **Emergency** (`≥ 78°F`) → fans 100%, AC at 68°F

**Primary Zone Gating**: Only primary zone's "escalate" or "emergency" request activates thermostat AC. Secondary zones get fan commands but don't trigger AC.

## Three-Layer Fan Control

| Layer | Entity | Effect |
|-------|--------|--------|
| Zone auto-control | `switch.adaptive_hvac_{zone}_auto` | If OFF: no fan commands for entire zone |
| Fan lock | `input_boolean.fan_user_claimed_*` | If ON: skip this specific fan |
| Per-step speed | fan_config `null` value | If null: don't command fan at this mode |

Example: Tia's office has auto-control OFF → integration never touches its fans, she controls them manually.

## Troubleshooting

**Config flow won't load (500 error)**
- Ensure HA version ≥ 2024.1.0
- Check if adaptive_hvac folder exists in `/config/custom_components/`
- Reload integration or restart HA

**Zone not responding to temperature changes**
- Verify temp sensor entity IDs are correct
- Check that zone's auto-control switch is ON
- Use Developer Tools → States to confirm sensor values are updating
- Call `adaptive_hvac.force_evaluate` to trigger immediate cycle

**AC won't activate**
- Confirm primary zone is set for one zone
- Check that primary zone's decision includes cool request
- Verify thermostat entity is correct
- Check AC setpoint is reasonable (default 68°F)

**Fans not turning on**
- Verify fan entity IDs are correct
- Check zone's auto-control switch is ON
- Confirm no fan lock is active for those fans
- Check zone's comfort/passive/escalate thresholds

## Known Limitations

- Equalization mode not yet implemented
- Fan pool configuration requires manual JSON editing (UI pending)
- Per-fan speed overrides (nullable) require config entry rebuild to change

## Contributing

Issues and PRs welcome at https://github.com/cscansen/adaptive_hvac

## License

MIT License — see LICENSE file.
