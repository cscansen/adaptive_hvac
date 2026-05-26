# Changelog

All notable changes to the Adaptive HVAC integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
