# Changelog

All notable changes to the Adaptive HVAC integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3.3] - 2026-05-29

### Changed
- `windows_assumed_open` no longer blocks AC — sensor is informational only; removed the thermostat-off gate from `decide_system`
- Updated `windows_assumed_open` template: threshold tightened to 58–68°F (was 60–75°F) and removed dependency on the old `input_select.hvac_season` entity

## [0.3.2] - 2026-05-29

### Changed
- Zone occupancy now controls **local fans only** — if a zone is unoccupied, its ceiling fans are turned off, but the zone still issues a thermal request to the system thermostat. Thermostat and whole-house fan decisions are never affected by zone occupancy.
- **Warning:** do not add the whole-house fan (thermostat fan) as a zone fan entity — occupancy would incorrectly turn it off.

## [0.3.1] - 2026-05-29

### Fixed
- `DataUpdateCoordinator` now receives `config_entry=` in both `SystemCoordinator` and `ZoneCoordinator` — required by HA 2026.x; without it `async_config_entry_first_refresh` raised `ConfigEntryError` and all system entities stayed unavailable
- Zone entity IDs sanitized to strip apostrophes and other non-`[a-z0-9_]` characters — zone names like "Caleb's Office" previously produced invalid entity IDs
- `async_create_task(async_update_entry(...))` TypeError in thermostat state change listener — `async_update_entry` is synchronous, called directly now

## [0.3.0] - 2026-05-29

### Breaking Changes
- Requires fresh setup (remove old integration entries and reconfigure)
- Zone config keys changed: `comfort_upper`, `passive_threshold`, `escalate_threshold` replaced by `zone_target_temp`
- System config keys removed: `cool_interior_threshold`, `upstairs_average_temp_entity`, `summer_threshold`, `winter_threshold`, `precool_trigger`, `preheat_trigger`, `escalate_enabled_downstairs_temp`, `escalate_enabled_upstairs_temp`

### Fixed
- **AC kept turning off when hot** — exterior threshold (70°F) was too high for spring solar-gain days; lowered default to 60°F and added interior override so AC is always allowed when a zone is 5°F+ above its target regardless of exterior temp
- **Sleep posture caused heat request in summer** — `setback_night` mode no longer exists; sleep posture flag is read but does not affect fan or thermostat decisions
- **Dual season systems conflicting** — removed forecast-based season detection (`derive_season`, `season.py`); calendar-based season is the single authority
- **Equalization check blocked AC when downstairs was cool** — removed `escalate_enabled_downstairs/upstairs_temp` gating from `decide_system`
- **Debug log files cluttering /config/** — all `/config/adaptive_hvac_*.log` writes removed

### Changed
- **Simplified zone logic** — single `zone_target_temp` replaces 4-tier threshold chain; fans on when temp > target, fans off when ≤ target
- **User owns thermostat** — if user adjusts setpoint via faceplate or app, integration adopts it as the new `ac_setpoint`/`heat_setpoint` for the season and persists it to config entry options; resets to base config on season change
- **Season model** — summer/winter only (no shoulder); configured as winter start/end months
- **Exterior gating** — `cool_exterior_threshold` default lowered 70→60°F; new `cool_interior_override_delta` (default 5°F) bypasses exterior gate when zone is significantly hot
- **Config flow simplified** — system: 4 steps instead of 7; zone: single target temp + fan speed

### Removed
- `season.py` — forecast-based season derivation deleted
- Pre-cool and pre-heat modes
- Equalization mode
- Passive/humidity cooling tiers
- Solar trigger logic
- All debug file writes
- 13 number entities reduced to 5 (AC setpoint, heat setpoint, heat threshold, emergency cool, emergency heat)

## [0.2.19] - 2026-05-26

### Changed
- **Architecture:** Move AC/heat gating logic from zone-based (primary zone) to system-level
- **System-level decision making:** Uses aggregated temperature sensor + exterior weather for thermostat gating
- **Season-aware thresholds:** Different AC/heat trigger temps based on time of year (customizable: default Oct-April = winter, May-Sept = summer)
- **Zone responsibilities simplified:** Zones control local fans and make local decisions; system controls thermostat based on aggregate signal
- **Thermostat dispatch:** Now applies system-level gating before sending commands; blocks AC/heat if thresholds not met
- **All season dates and thresholds now configurable** via UI (Settings → Integrations → Adaptive HVAC → Configure)

### Added
- Support for exterior temperature consideration in AC/heat gating (reads `weather.forecast_home`)
- Calendar-based season detection with **customizable month ranges** (default: Oct-April = winter, May-Sept = summer)
- **Configurable season dates** in system config:
  - `winter_start_month` (default: 10)
  - `winter_end_month` (default: 4)
  - `summer_start_month` (default: 5)
  - `summer_end_month` (default: 9)
- **Configurable AC/heat gating thresholds** in system config:
  - `cool_exterior_threshold` (default: 70°F)
  - `cool_interior_threshold` (default: 74°F)
  - `heat_exterior_threshold` (default: 60°F)
  - `heat_interior_threshold` (default: 68°F)
- Config UI with month dropdown selectors and temperature threshold sliders
- Upstairs average temperature sensor reading (`sensor.upstairs_average_temperature` — aggregated: Caleb + Tia + Master)
- Detailed gating logs in `/config/adaptive_hvac_coordinator.log` for diagnostics

### Fixed
- Primary zone selection logic: replaced with system-level aggregate signal (more predictable, cleaner)
- Zone aggregation (v0.2.18): fixed zone decision collection from refresh return values

## [0.2.18] - 2026-05-26

### Fixed
- **Zone aggregation working:** SystemCoordinator now correctly collects zone decisions by accessing `coord.last_decision` instead of treating `async_request_refresh()` return value as the decision
- **Dynamic multi-zone support:** System discovers and aggregates decisions from multiple zones on each update cycle (tested with Caleb's Office + Tia's Office)
- **System decision making:** End-to-end HVAC decision pipeline: zones → system aggregation → thermostat/fan dispatch

### Changed
- Enhanced logging in `_async_update_data()` to trace zone discovery and decision aggregation for diagnostics

### Notes
- Zone aggregation now fully functional and tested with 2 zones
- Dynamic primary zone selection logic may need tuning for multi-zone scenarios
- Integration ready for A/B testing against existing YAML automations

## [0.2.17] - 2026-05-26

### Fixed
- Complete normalization for all multi-select zone fields (v0.2.15→v0.2.17 compat)
- Better normalization of defaults for multi-select fields
- SystemOptionsFlow 500 error (refactored to multi-step)

### Added
- Multi-select zone sensors with backwards-compatible defaults

## [0.2.15] - earlier

### Earlier versions
See git history for changelog prior to v0.2.15.
