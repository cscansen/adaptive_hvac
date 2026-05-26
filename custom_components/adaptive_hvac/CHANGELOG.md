# Changelog

All notable changes to the Adaptive HVAC integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
