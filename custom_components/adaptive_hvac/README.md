# Adaptive HVAC — Home Assistant Integration

A custom Home Assistant integration for intelligent, adaptive HVAC control based on temperature, humidity, occupancy, and environmental conditions.

## Features

- **System + Zone Architecture**: Global AC/heating/setback config with per-room cooling control
- **System-Level AC/Heat Gating (v0.2.19)**: AC and heat activation controlled at system level based on:
  - Calendar season (customizable: Oct-April winter, May-Sept summer)
  - Exterior weather (won't AC when cool outside, won't heat when warm outside)
  - Interior aggregate temperature (upstairs average)
  - **All thresholds configurable via UI** (no code changes needed)
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

Configure once for the entire system via multi-step UI wizard:

#### Step 1: Thermostat & Weather (Required)
| Setting | Type | Default | Notes |
|---------|------|---------|-------|
| Thermostat | climate entity | `climate.downstairs_thermostat` | Controls mode, setpoint, fan |
| Weather | weather entity | `weather.forecast_home` | For forecast-based triggers |

#### Step 2: House-Level Sensors (Optional)
| Setting | Type | Default | Notes |
|---------|------|---------|-------|
| Windows Sensor | binary_sensor | `binary_sensor.windows_assumed_open` | System-wide window open detection |
| Sleep Posture | input_boolean | — | Block heating during sleep |
| Occupancy Sensors | binary_sensor(s) | — | For unoccupied setback logic |
| Solar Sensor | sensor | — | Solar irradiance for AC escalation |

#### Step 3a: AC & Heat Setpoints
| Setting | Type | Default | Notes |
|---------|------|---------|-------|
| AC Setpoint | number °F | `68` | Target temp when AC activates |
| Heat Setpoint | number °F | `68` | Target temp when heating activates |

#### Step 3b: Heating Triggers
| Setting | Type | Default | Notes |
|---------|------|---------|-------|
| Heat Threshold | number °F | `68` | Zone temp trigger for normal heating |
| Emergency Heat | number °F | `55` | Emergency heating threshold (any season) |

#### Step 3c: Whole-House Fan & Equalization
| Setting | Type | Default | Notes |
|---------|------|---------|-------|
| Passive Fan Threshold | number °F | `70` | Hottest zone temp that triggers whole-house fan |
| Escalate Downstairs Temp | number °F | `68` | Coldest zone must be above this for AC |
| Escalate Upstairs Temp | number °F | `74` | Hottest zone must be above this for AC |

#### Step 3d: Away Mode Setback
| Setting | Type | Default | Notes |
|---------|------|---------|-------|
| Setback Cool | number °F | `76` | Cooling setpoint when unoccupied 8+ hours |
| Setback Heat | number °F | `62` | Heating setpoint when unoccupied 8+ hours |

#### Step 3e: System-Level AC/Heat Gating (v0.2.19)
| Setting | Type | Default | Notes |
|---------|------|---------|-------|
| Winter Start Month | dropdown | `10` (Oct) | Calendar month when winter season begins |
| Winter End Month | dropdown | `4` (Apr) | Calendar month when winter season ends |
| Cool Exterior Threshold | number °F | `70` | Don't AC if outdoor temp below this |
| Cool Interior Threshold | number °F | `74` | Don't AC if upstairs avg below this |
| Heat Exterior Threshold | number °F | `60` | Don't heat if outdoor temp above this |
| Heat Interior Threshold | number °F | `68` | Don't heat if upstairs avg above this |

**Gating Logic** (v0.2.19):
- **Summer** (May-Sept): AC allowed if exterior ≥ cool_exterior_threshold AND upstairs_avg ≥ cool_interior_threshold
- **Winter** (Oct-April): Heat allowed if exterior ≤ heat_exterior_threshold AND upstairs_avg ≤ heat_interior_threshold
- **Shoulder**: System OFF (fans available for zone/manual control)

#### Step 3f: Other Settings
| Setting | Type | Default | Notes |
|---------|------|---------|-------|
| AC Solar Trigger | number W | `2000` | Solar irradiance threshold for AC escalation |
| Window Fan Speed | number % | `25` | Fan speed when windows open (passive mode) |

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

**ZoneCoordinator**: Reads zone temps/humidity/sensors, evaluates cooling decision tree, issues fan commands. Zones operate independently and always contribute to system decisions.

**SystemCoordinator**: 
- Aggregates zone decisions dynamically (discovers zones on each update cycle)
- Applies **system-level AC/heat gating** (v0.2.19): checks calendar season, exterior weather, interior aggregate temp
- Controls thermostat mode/setpoint based on gating + zone requests
- Manages whole-house fan

**System-Level Gating** (v0.2.19):
- Reads calendar month to determine if in winter (Oct-Apr) or summer (May-Sep) season
- Reads exterior temperature from weather entity
- Reads interior aggregate temperature (`sensor.upstairs_average_temperature`)
- Gates AC/heat activation: only sends thermostat commands if thresholds met
- Falls back to system OFF (fans only) if conditions don't allow AC/heat

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
