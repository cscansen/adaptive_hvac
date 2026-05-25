# Changelog

All notable changes to the Adaptive HVAC integration are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.13] - 2026-05-25

### Fixed
- Fixed config flow EntitySelector implementation by refactoring to match `adaptive_irrigation` pattern: schema generation moved to helper functions (`_system_schema_dict`, `_zone_schema_dict`) that take defaults dict as parameter. EntitySelector now properly handles defaults for both single and multi-select entity fields.

## [0.2.12] - 2026-05-25

### Fixed
- Fixed 500 error when clicking gear icon on zone entries by removing problematic custom `__init__` override in OptionsFlow class. OptionsFlow now properly inherits parent initialization, allowing HA config flow lifecycle to work correctly.

## [0.2.11] - 2026-05-25

### Added
- **System-wide window override**: If ANY window (system + any zone) is open, AC/heat is blocked; whole-house fan activates for passive ventilation. Enforcement happens at dispatch time, overriding all decision logic.

### Changed
- Coordinator passes per-zone window states to `decide_system` via aggregated `zone_states` for system-level override logic

## [0.2.10] - 2026-05-25

### Added
- **Zone-to-system auto-discovery**: System coordinator automatically discovers and registers all zone coordinators at startup (no manual linking needed)
- **Dynamic primary zone selection**: Primary zone is now selected at runtime based on occupancy + sleep mode, not as a static config:
  - Occupied zones are "active"; master bedroom is always active during sleep mode
  - Among active zones, picks highest-urgency (or configured primary if active)
  - System OFF if no active zones
  - Enables "Caleb's office gates AC when occupied; downstairs takes over when empty" patterns without hardcoding
- **Zone-level entity selectors**: Config flow now offers entity selectors (multi-select for temps/fans, single for humidity/window/occupancy)
  - Per-zone window sensors feed into system-wide window override
  - No more empty zone configs — all settings available via UI
- **Occupancy tracking in system state**: Collects zone occupancy booleans for active zone computation

### Changed
- `SystemCoordinator._async_update_data` now builds proper `ZoneState` objects with occupancy info for each zone (previously placeholder)
- `decide_system` now takes occupancy info via `sys_state.zone_states[*].zone_occupied`
- Config flow moved from placeholder text fields to proper entity selectors
- Improved logging: system decision now includes reason for primary zone selection

### Fixed
- Fixed 500 errors in options flow by using entity selectors instead of text inputs
- Fixed system coordinator trying to iterate empty `zone_coordinators` list at startup

## [0.2.9] - 2026-05-24

### Fixed
- Fixed dataclass field ordering error: `SystemDecision.thermostat_hvac_mode` now has default value `"off"` (was missing default before required fields)

## [0.2.8] - 2026-05-22

### Fixed
- Fixed 400 Bad Request in config flow by correcting BooleanSelector instantiation (requires dict argument, not null) and removing invalid `step` parameter from NumberSelectorConfig

## [0.2.7] - 2026-05-22

### Fixed
- Fixed OptionsFlow initialization by explicitly defining `__init__` method to accept config_entry parameter

## [0.2.6] - 2026-05-22

### Changed
- Disabled options flow (returns `options_not_supported`) — configuration is read-only from the UI. Edit config entries by recreating them or modifying `config.json` directly. This eliminates selector complexity that was causing 500 errors.

## [0.2.5] - 2026-05-22

### Fixed
- Fixed 500 error in options flow by making OptionsFlow more defensive with try/except error handling and explicit None checks for default value extraction

## [0.2.4] - 2026-05-22

### Fixed
- Fixed 500 error in options flow by correcting NumberSelectorConfig parameter from `unit_of_measurement=` to `unit=` for Home Assistant 2024.1+ compatibility

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
