# Changelog

All notable changes to the Adaptive HVAC integration are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.3] - 2026-05-22

### Fixed
- Fixed `ImportError: cannot import name 'DEFAULT_NIGHT_SETBACK_TEMP'` by removing obsolete constant reference in `number.py` and mapping to `setback_heat_temp` config key

## [0.2.2] - 2026-05-22

### Fixed
- Fixed `ModuleNotFoundError: No module named 'homeassistant.helpers.restore_entity'` by correcting import in `number.py` to use `homeassistant.helpers.restore_state`

## [0.2.1] - 2026-05-22

### Fixed
- Fixed 500 Internal Server Error in config flow by replacing invalid `EntitiesSelector` with `EntitySelector(multiple=True)` for multi-entity selections

### Changed
- Improved selector API compatibility for Home Assistant 2024.1+

## [0.2.0] - 2026-05-22

### Added
- **Per-Zone Auto-Control Switch**: Toggle automatic fan control per zone (like sleep mode in dynamic lighting)
  - Entity: `switch.adaptive_hvac_{zone}_auto`
  - When OFF: zone operates in user-only control mode (no automatic fan commands)
  - Persists across Home Assistant restarts via RestoreEntity
- **Primary Zone Gating**: Only primary zone's thermal request gates AC activation
  - Secondary zones provide advisory status but don't trigger thermostat
  - Configurable `is_primary_zone` flag per zone
- **Nullable Fan Speeds**: Per-mode per-fan speed control with granular skip/off/percentage options
  - `null` = skip this mode for this fan
  - `0` = explicitly turn fan off at this step
  - `1-100` = set to percentage speed
- **System-Level Windows Behavior**: Global windows sensor integration
  - When windows open (summer only): thermostat OFF, whole-house fan ON
  - Room fans commanded to `window_fan_speed` (passive circulation only)
  - Supports both per-zone and system-wide window sensors
- **Humidity-Based Passive Cooling**: Third pathway to passive mode
  - Activates when humidity ≥ 55% AND temp ≥ 72°F (summer)
  - Useful in high-humidity climates to dehumidify without AC
- **Windows State Wired to All Zones**: Each zone independently reads global windows sensor
  - Enables system-level windows logic in per-zone decisions
  - Zone coordinator reads `binary_sensor.windows_assumed_open` state

### Changed
- Restructured configuration to separate global (system) from per-room (zone) config
- System entry now owns: thermostat, AC control, heating, setback, windows, passive cooling, whole-house fan
- Zone entry now owns: temperature sensors, humidity sensor, window sensor, occupancy, cooling thresholds, fan speeds
- Refactored `ZoneDecision` to include `zone_name` and `is_primary_zone` for routing
- Refactored `SystemCoordinator.decide_system()` to implement primary zone gating
- Added fan command mapping from placeholder fan_id to real entity IDs via fan_config
- Improved logging to show auto-control state and zone names in debug output

### Documentation
- Added comprehensive CLAUDE.md section with full architecture, config, and testing instructions
- Added integration-level README.md with setup, configuration, usage, and troubleshooting

## [0.1.0] - 2026-05-16

### Added
- Initial release: Adaptive HVAC integration for Home Assistant
- **Global & Per-Room Control**: System-level AC and heating configuration with per-room cooling thresholds
- **Config Flow**: User-friendly setup wizard for system and zone entries
- **ZoneCoordinator**: Per-zone temperature evaluation and fan command generation
- **SystemCoordinator**: Aggregates zone decisions and controls thermostat + whole-house fan
- **Pure Logic Layer**: No Home Assistant imports in decision logic (easy to test and extend)
- **Cooling Decision Tree**: Comfort → Passive → AC Escalation → Emergency based on temperature
- **Passive Cooling**: Whole-house fan integration based on temperature and passivity conditions
- **Temperature Trend Analysis**: Preemptive passive cooling activation based on rate of change
- **Occupancy-Based Setback**: Unoccupied duration tracking and setback temperature control
- **Seasonal Logic**: Automatic summer/shoulder/winter mode derivation from weather forecast
- **Sensor Entities**: Per-zone status sensor and temperature trend sensor
- **Fan Lock Integration**: Respects existing `input_boolean.fan_user_claimed_*` pattern

### Architecture
- `__init__.py`: Entry point, service registration, platform setup
- `config_flow.py`: ConfigFlow for system and zone setup
- `coordinator.py`: ZoneCoordinator and SystemCoordinator (DataUpdateCoordinator pattern)
- `logic.py`: Pure decision engine (ZoneState, SystemState, ZoneDecision, SystemDecision, decide_zone, decide_system)
- `season.py`: Seasonal mode derivation logic
- `sensor.py`: Home Assistant sensor entity implementations
- `switch.py`: Home Assistant switch entity implementations
- `number.py`: Home Assistant number entity implementations
- `select.py`: Home Assistant select entity implementations

---

## Release Notes

### Version 0.2.1
**Bug fix release**: Config flow now loads without 500 error. Upgraded selector API for Home Assistant 2024.1+ compatibility.

### Version 0.2.0
**Major feature release**: Added per-zone auto-control toggle, primary zone gating, system-level windows behavior, humidity-based cooling trigger, and nullable fan speeds. Restructured global + per-room configuration matching adaptive_irrigation pattern.

### Version 0.1.0
**Initial release**: Full Adaptive HVAC integration with ZoneCoordinator, SystemCoordinator, and pure logic layer.
