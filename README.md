# Adaptive HVAC

An intelligent, occupancy-aware HVAC integration for Home Assistant. Dynamically selects the primary thermostat based on which rooms are occupied, enforces system-wide window overrides, and respects user fan claims. **Pure decision logic with zero Home Assistant imports** — easily testable and reusable.

## Features

### Occupancy-Driven Primary Zone Selection (v0.2.10+)
- **Dynamic primary zone**: Automatically picks which zone controls the thermostat based on real-time occupancy
- **Occupied zones take priority**: If Caleb's office is occupied and hot, it gates AC; if he leaves, downstairs takes over
- **Sleep-mode aware**: Master bedroom can demand cooling even when unoccupied if you're in bed
- **Fallback to highest urgency**: If no occupied rooms, all zones contribute equally

### System-Wide Window Override (v0.2.10+)
- **Any window open → no AC/heat**: Dispatch-time check blocks cooling/heating when any window is open
- **Passive ventilation instead**: Whole-house fan activates for air circulation without conditioning
- **Per-zone + system sensors**: Monitors both global `windows_assumed_open` and per-zone contact sensors
- **Real-time enforcement**: Window open at any point blocks AC immediately (even mid-cool cycle)

### Per-Room Autonomy
- **Individual temperature sensors**: Each room averages its own sensors for independent decisions
- **Zone-level humidity triggers**: Dehumidify with passive cooling (no AC) when humidity is high
- **Room-specific fan control**: Each room has its own auto/manual toggle via `switch.adaptive_hvac_{zone}_auto`
- **Per-fan configuration**: Assign specific fans to rooms, control their speeds per mode

### Passive & Active Cooling
- **Comfort mode** (< 70°F): Fans off
- **Passive mode** (≥ 72°F or high humidity): Room fans at 33%, whole-house fan ON
- **Escalate** (≥ 74°F sustained or rising temp): Room fans at 50%, AC at 68°F
- **Emergency** (≥ 78°F): Room fans at 100%, AC at 68°F

### Heating with Occupancy & Sleep Integration
- **Global heat threshold**: Configurable per system (default 68°F in winter)
- **Emergency heat**: Activates below 55°F regardless of season
- **Sleep mode blocks heat**: When master suite sleep posture is ON, heating is suppressed (unless emergency cold)
- **Occupancy setback**: Cool/heat to offset temps when unoccupied for 8+ hours

### Seasonal Logic
- **Summer** (May 1): AC enabled, passive cooling active
- **Shoulder** (Apr 1, Oct 1): AC/heat off, passive cooling only (no normal heating)
- **Winter** (Oct 1): Heating enabled, AC off
- **Automatic transitions**: Based on 7-day forecast or manual override

### Fan Lock Integration
- **Respects user claims**: If you manually adjust a fan, HVAC won't override it until you turn it off
- **Per-fan speed storage**: Remembers your speed and restores it when auto-control resumes
- **Fully compatible**: Works with existing `input_boolean.fan_user_claimed_*` pattern

### Architecture That Stands Alone
- **Pure logic layer** (`logic.py`): Zero Home Assistant imports — can be unit tested, ported to other systems
- **Coordinator pattern**: ZoneCoordinator evaluates rooms; SystemCoordinator aggregates and controls thermostat
- **Modular config**: No hardcoded entity IDs — every room, thermostat, and sensor is configurable via UI
- **Easy to extend**: Decision trees are top-to-bottom, no hidden state — add new modes without breaking existing ones

## Installation

### Via HACS (Recommended)
1. **Settings** → **Devices & Services** → **Integrations** (⋯ menu)
2. **Custom Repositories**
3. **Repository**: `https://github.com/cscansen/adaptive_hvac`
4. **Category**: Integration
5. **Install**, restart Home Assistant
6. **Settings** → **Integrations** → **Create Integration** → search "Adaptive HVAC"

### Manual Install
1. Copy `custom_components/adaptive_hvac/` to `config/custom_components/`
2. Restart Home Assistant
3. **Settings** → **Integrations** → **Create Integration** → search "Adaptive HVAC"

## Quick Start

### 1. Create System Entry
- **Settings** → **Integrations** → **Adaptive HVAC** → **Add entry** → choose "system"
- **Thermostat entity**: Select your climate device (e.g., `climate.downstairs_thermostat`)
- **Weather entity**: Select your weather integration (e.g., `weather.forecast_home`)

### 2. Create Zone Entries
- **Add entry** → choose "zone" for each room (upstairs, downstairs, garage, etc.)
- **Zone name**: e.g., "Upstairs", "Living Room", "Master Bedroom"

### 3. Configure Each Zone (Click ⚙️)
- **Temperature sensors**: Select 1+ temp sensors; system averages them (required)
- **Humidity sensor**: Optional; triggers passive cooling if humidity ≥ 55% at ≥ 72°F
- **Window sensor**: Optional contact sensor to detect open windows per room
- **Occupancy sensor**: Optional; zone considered "active" if occupied
- **Fans**: Select which fans this zone controls
- **Thresholds**: Comfort, passive, escalate, emergency temps (or use defaults)
- **Fan speeds**: Comfort (%), passive (%), escalate (%), emergency (%)

### 4. Monitor
- **Developer Tools** → **States** → search `adaptive_hvac`
- `sensor.adaptive_hvac_status` — system decision + reasoning
- `sensor.adaptive_hvac_{zone}_status` — per-room mode + fans
- `switch.adaptive_hvac_{zone}_auto` — toggle auto-control per room

## Configuration Examples

### Scenario: Caleb's Office Gates AC (Without Hardcoding)
1. Create zone "Caleb's Office" with `sensor.caleb_office_temp`
2. Mark as primary zone: In zone options, set `is_primary_zone=true`
3. Create zone "Rest of House" with main floor sensors (secondary)
4. Result: Caleb's office temp triggers AC; rest of house gets fans only

### Scenario: Tia's Office Manual-Only (User Controls Fans)
1. Create zone "Tia's Office" with her ceiling fan
2. Set `switch.adaptive_hvac_tia_office_auto` to OFF
3. Automation still runs, displays status, but doesn't touch the fan
4. Tia controls her fan manually; HVAC provides context

### Scenario: Open Window = No Cooling
1. Add contact sensors to all windows as zone options
2. System coordinator automatically detects ANY open window
3. When open: thermostat OFF, whole-house fan ON (passive circulation)
4. When closed: normal HVAC logic resumes

## Entities Created

### System-Level
- `sensor.adaptive_hvac_status` — system decision, thermostat mode, setpoint, whole-house fan mode, full reasoning
- `sensor.adaptive_hvac_mode` — current mode: cool, heat, or off
- `sensor.adaptive_hvac_season` — derived season: summer, shoulder, winter

### Per-Zone
- `sensor.adaptive_hvac_{zone}_status` — zone mode, fan commands, urgency, reasoning
- `sensor.adaptive_hvac_{zone}_trend` — temperature trend °F/hr (30-min window)
- `switch.adaptive_hvac_{zone}_auto` — ON = auto fan control, OFF = user-only

## Debugging

### Check Integration Loaded
- **Settings** → **Integrations** → search "Adaptive HVAC"
- Should show system entry + all zone entries

### View Decisions
- **Developer Tools** → **States** → filter "adaptive_hvac"
- Read `status` and `reasoning` attributes to see why a decision was made

### Force Immediate Evaluation
```bash
curl -X POST http://ha.local:8123/api/services/adaptive_hvac/force_evaluate \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Reload After Config Change
- **Settings** → **Integrations** → **Adaptive HVAC** → ⋯ menu → **Reload**
- Applies changes without restarting Home Assistant

## Performance & Polling

- **Poll interval**: 3 minutes (configurable in `const.py`)
- **Zone coordinator**: Runs independently, calculates trend, checks claims
- **System coordinator**: Aggregates zones, decides thermostat, dispatches commands
- **Lightweight**: Decision engine runs in ~10ms; no blocking calls

## Testing the Decision Logic

The `logic.py` file is pure Python with zero HA imports. You can unit test it:

```python
from logic import decide_zone, ZoneState, ZoneConfig

zone = ZoneState(zone_name="Office", temp=75.0, ...)
config = ZoneConfig(escalate_threshold=74.0, ...)
decision = decide_zone(zone, [...], {...}, config)
assert decision.mode == "escalate"
```

## Known Limitations

- **Equalization mode**: Floor-to-floor delta balancing not yet implemented
- **Pre-cool / pre-heat**: Use simple forecast thresholds, no solar irradiance gating
- **Fan pool UI**: Fans configured via JSON in zone options; full config flow pending
- **Dashboard**: Status sensors exist, but no custom Lovelace cards yet
- **Multi-thermostat**: Architecture supports it, single thermostat tested

## Contributing

Issues and pull requests welcome. Before submitting:
1. Ensure `manifest.json` version is incremented
2. Update `CHANGELOG.md` with your changes
3. Test config flow loads without errors
4. If touching `logic.py`, add a unit test (no HA imports needed)

## License

MIT License — see LICENSE file.

## Credits

Inspired by the existing automation-based HVAC system but fully rewritten as a pure, reusable decision engine. Designed to be intuitive for Home Assistant users while remaining testable and portable.
