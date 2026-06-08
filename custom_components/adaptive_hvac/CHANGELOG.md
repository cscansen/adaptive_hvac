# Changelog

All notable changes to the Adaptive HVAC integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3.25] - 2026-06-08

### Added
- **Cover entities supported as window sensors** — the zone window sensor selector now accepts
  both `binary_sensor` and `cover` domains. Cover entities report `open`/`closed` rather than
  `on`/`off`; the open-window check now matches either state so both types work correctly.

## [0.3.24] - 2026-06-08

### Fixed
- **False degraded-mode on stable sensors** — the stale-sensor check was using `last_updated` to
  detect sensors that hadn't reported within 60 minutes. For passive BLE sensors (e.g. Govee
  hygrometers), HA only writes a new state when the value changes, so a room holding a steady
  temperature would be falsely flagged as stale after an hour. The time-based check has been
  removed entirely: a sensor is now only considered non-reporting if HA marks it `unavailable`
  or `unknown`, which is the correct signal for a genuinely dead or disconnected sensor.

## [0.3.23] - 2026-06-08

### Fixed
- **Outdoor temp entity in dashboard generator** — `system_glance_card` was using a hardcoded
  `sensor.adaptive_hvac_outdoor_temp` entity that doesn't exist. The system status sensor now
  exposes `thermostat_entity` and `outdoor_temp_sensor` as attributes so the generator can read
  the correct entity in both `--local` and remote modes. Weather entities receive the `temperature`
  attribute selector automatically; sensor entities are referenced directly.

### Changed
- **README overhauled** — documents floor fan circulation, affects_thermostat zone flag, demand
  boost, sensor failover / degraded mode, sensor staleness, dashboard generator, and all entity
  attributes. Removed outdated and personal references.

## [0.3.22] - 2026-06-08

### Added
- **Zone status sensor now exposes configuration attributes** — `temp_sensors`, `fans`, `floor`,
  `affects_thermostat`, and `zone_target_temp` are included in each zone's status sensor
  attributes. This enables the dashboard generator to work via the HA REST API alone with no
  SSH or file-system access to the HA host.
- **Dashboard generator script** (`scripts/generate_dashboard.py`) — reads your live zone
  configuration from HA and regenerates the full Lovelace dashboard automatically. Zones are
  discovered from entity states; no manual configuration required. Supports file output (for
  paste into Raw Config Editor) and SSH deploy. Re-run whenever zones are added or removed.
- **DASHBOARD.md** — step-by-step setup guide for the dashboard generator, covering both
  the no-SSH (copy-paste) and SSH deploy paths, plus the optional thermostat fan state
  template sensor for the history graph.

## [0.3.21] - 2026-06-08

### Added
- **Stale sensor detection and failover** — each zone coordinator checks its configured temp
  sensors every evaluation cycle. A sensor is flagged stale if it is missing, in
  `unavailable`/`unknown` state, or has not updated its value within `sensor_staleness_minutes`
  (default 60 min). Stale sensors trigger the same 2-cycle degraded-mode failover as total
  sensor loss: thermostat is set to `auto` after 2 consecutive cycles with any stale sensor,
  a persistent HA notification lists exactly which sensors in which zones are affected, and
  normal control resumes automatically when all sensors recover.

## [0.3.20] - 2026-06-08

### Added
- **Thermostat failover when all sensors go unavailable** — if every zone reports `SENSOR FAILSAFE`
  for 2 consecutive evaluation cycles (6 minutes), the integration enters degraded mode:
  the thermostat is set to `auto` so it governs itself via its internal schedule, and a
  persistent HA notification is fired. When any zone sensor recovers, normal adaptive
  control resumes automatically and the notification is dismissed. The startup transient
  (sensors unavailable for <3 min after HA restart) does not trigger degraded mode.

## [0.3.19] - 2026-06-08

### Fixed
- **Temperature trend no longer shows thousands of °F/hr** — two bugs in `_calculate_trend()`:
  1. Failsafe readings (0.0°F, returned when sensors are unavailable on startup) were being
     stored in the sample history. When a real reading arrived (e.g. 72°F), the regression saw
     a 0→72 jump and extrapolated to ~2160°F/hr. Invalid readings are now skipped.
  2. The per-hour conversion used `× 60` (assumes 1 sample/minute) but the scan interval is
     3 minutes — corrected to `× 20`. The history window was also 90 minutes (maxlen=30 at
     3 min/sample); corrected to maxlen=10 for a true 30-minute window.

## [0.3.18] - 2026-06-08

### Fixed
- **Garage window sensor no longer blocks AC** — the window open gate in `decide_system()` was
  checking all zones regardless of `affects_thermostat`. Zones with `affects_thermostat=OFF`
  (e.g. garage) now correctly have no influence on the AC gate, consistent with the v0.3.13
  design intent stated in the changelog.

## [0.3.17] - 2026-06-08

### Changed
- **Floor circulation suppressed during sleep posture** — when the sleep posture entity is active,
  the whole-house fan stays in `auto` and will not turn on for temperature equalization. Reasoning
  includes "Floor circulation suppressed — sleep posture active".

## [0.3.16] - 2026-06-08

### Added
- **Floor-based whole-house fan circulation** — zones can now be assigned to an HA floor (via
  Settings → Integrations → zone → Configure → Floor, using HA's native floor registry). When
  any two floors differ by ≥ `fan_circulation_delta` (default 2°F), the thermostat fan is set
  to `on` to circulate air and equalize temperatures without running the compressor or furnace.
  Fan returns to `auto` when floors are within threshold. Works in both summer and winter.
  Blocked during manual override and system inactive states.
- **`number.adaptive_hvac_fan_circulation_delta`** — live-adjustable floor differential threshold
  (0.5–5°F, step 0.5°F, default 2°F).

## [0.3.15] - 2026-06-07

### Fixed
- **Zone status no longer says "PASSIVE COOLING" for unoccupied zones** — passive cooling requires
  fans actually running. Unoccupied zones have fans at 0, so they now show `WARM` / `idle_warm`
  (above target, no fans, no AC) instead. `PASSIVE COOLING` is reserved for occupied zones where
  fans are spinning but AC is blocked. Same logic applies on the heat side: `COLD` / `idle_cold`
  vs `PASSIVE HEATING`.

## [0.3.14] - 2026-06-07

### Changed
- **Zone status now distinguishes passive vs active cooling/heating** — when a zone is above its
  target but the system thermostat is blocked (window open, outdoor gate, etc.), the zone mode
  is now `passive_cooling` / `passive_heating` with status "PASSIVE COOLING / PASSIVE HEATING"
  instead of the misleading "COOLING / HEATING". Active modes only show when the thermostat is
  actually running. Reasoning includes "AC not active — fans only" or "Heat not active — passive only".

## [0.3.13] - 2026-06-07

### Added
- **Per-zone "Affects thermostat" toggle** — new boolean in zone config (default ON). When turned
  OFF, the zone controls its local fans based on temperature vs target as normal, but never sends
  a cooling or heating request to the system thermostat. Use this for unconditioned spaces (garage,
  workshop) where you want fan automation without the zone influencing AC or heat calls.
  Window sensor on these zones also has no effect on the system AC gate.

## [0.3.12] - 2026-06-07

### Changed
- **Upstairs demand boost now applies in both seasons** — in winter, when zones request heat, the
  dispatched heat setpoint is raised by `upstairs_demand_boost` (same entity, default 1°F) so the
  furnace runs harder/longer to push warm air upstairs through the single duct. Emergency heat uses
  the base `heat_setpoint` and is unaffected. Previously the boost only applied to summer cooling.

## [0.3.11] - 2026-06-07

### Added
- **Local outdoor temperature sensor support** — new optional `outdoor_temp_sensor` field in
  system setup and options flow (any `sensor` entity). When configured, the local sensor reading
  is used instead of the weather entity, giving real-time outdoor temperature without the
  update delay inherent in weather integrations. Falls back to `weather_entity` if the sensor
  is unavailable or not configured. Both fields remain optional; the local sensor takes priority.

## [0.3.10] - 2026-06-07

### Fixed
- **AC no longer runs when it's cooler outside than the zone target** — added a relative outdoor
  gate: if the outdoor temperature is below the comfort target of any zone requesting cooling,
  AC is blocked (opening windows would achieve comfort more efficiently). The absolute
  `cool_exterior_threshold` gate (60°F) and interior override remain; this gate applies after
  both and cannot be bypassed except by emergency cooling (≥85°F).

## [0.3.9] - 2026-06-07

### Fixed
- **Fan auto-claim now triggers on physical switch presses** — `_handle_fan_change` previously
  required `context.user_id` (only set by HA UI/app), ignoring wall switch events. Now uses
  `context.parent_id` to distinguish: skips lock only when `user_id=None` AND `parent_id!=None`
  (integration's own dispatch); locks for all other sources including physical switches.
- **Auto-control switch now works for zones with special characters in their name** —
  `_read_auto_control_enabled` was using `.replace(" ", "_")` to build the entity slug, keeping
  apostrophes that HA strips from entity IDs. Now uses the same `re.sub(r"[^a-z0-9_]", "", ...)`
  sanitizer as the switch entity. Caleb's Office auto-control toggle was silently ignored; now works.
- **AC setpoint set via dashboard slider now persists across restarts** — `ACSetpointNumber`
  (and all system number entities) previously only wrote to in-memory `system_config`. Because
  `_effective_setpoint` reads `config_entry.options` first, an in-memory write was shadowed by
  any previously adopted options value. Number entities now write through to `config_entry.options`
  via the same suppress-reload path used by thermostat setpoint adoption.
- **Thermostat setpoint adoption restricted to HA UI/app actions** — `handle_thermostat_state_change`
  previously adopted any setpoint change > 0.5°F from the last integration dispatch, including the
  thermostat's own internal schedule. Adoption now requires `context.user_id` to be set, meaning
  only explicit HA UI or app adjustments are adopted. Use the dashboard AC Setpoint slider for
  adjusting the target; it now persists correctly across restarts.

### Added
- **Upstairs demand boost** — when any zone requests cooling, the dispatched AC setpoint is
  automatically reduced by a configurable amount (default 1°F, range 0–2°F, step 0.5°F). This
  makes the AC run longer/harder per cycle, pushing more cold air through the duct to upstairs
  rooms via the single zone thermostat. Configurable via `number.adaptive_hvac_upstairs_demand_boost`
  on the HVAC dashboard. Boost is included in the system status reasoning attribute. Emergency
  cooling uses the base `ac_setpoint` and is unaffected.

## [0.3.8] - 2026-05-31

### Fixed
- **Emergency cooling now overrides fan lock** — fans always spin at 100% when a zone hits the emergency threshold (≥85°F), regardless of user fan lock state. Thermostat cooling request was going through already; now local fans do too.
- **Fan lock state restored before first evaluation on HA restart** — platform setup now runs before `async_config_entry_first_refresh()` so `FanLockedSwitch` restores persisted lock state before the first coordinator cycle, preventing a spurious fan command on every restart.
- **Setpoint adoption now persists correctly in-session** — replaced fragile direct disk write of `core.config_entries` with `config_entries.async_update_entry()`. Adopted setpoints are now effective immediately (not only after a restart) and are properly persisted. The resulting options-update event is suppressed so no entity reload is triggered.
- **Eliminated None broadcast in fan lock methods** — `set_fan_lock`, `_handle_fan_change`, and `_midnight_reset` now guard against calling `async_set_updated_data(None)` before the first coordinator evaluation completes.
- **Fan lock switch shows correct state immediately after HA restart** — `FanLockedSwitch.async_added_to_hass` now calls `async_write_ha_state()` after restoring persisted state, so the switch UI reflects the correct locked/unlocked state without waiting for the next coordinator tick.

## [0.3.7] - 2026-05-31

### Changed
- Simplified fan lock internals: replaced `fans_claimed: set[str]` with `fan_locked: bool` in `ZoneState`; removed unused `_fan_claimed_speed` and `_read_fan_claims()`. No behavior change.

## [0.3.6] - 2026-05-30

### Added
- Native fan lock per zone: `switch.adaptive_hvac_<zone>_fan_locked`. When a user manually turns on, adjusts, or turns off a ceiling fan, the integration claims it and stops overriding it. Releases at midnight.
- Fan off suppression: if a user turns the fan off, the integration won't turn it back on until midnight.
- Manual release: turn the fan locked switch OFF at any time to immediately hand control back.

### Changed
- Fan lock is now handled entirely inside the integration — external `fan_lock_set_claimed`, `fan_lock_clear_claimed`, `fan_lock_restore` automations and all `input_boolean.fan_user_claimed_*` / `input_number.fan_claimed_speed_*` helpers can be removed.
- `_map_fan_commands` simplified: removed the unused `fan_config` code path.

### Removed
- `CONF_FAN_CONFIG` constant (dead code).

## [0.3.5] - 2026-05-30

### Removed
- `binary_sensor.windows_assumed_open_2` template sensor — replaced by actual window sensors on zones + configurable exterior threshold.
- `windows_assumed_open_sensor` config option from system setup and options flow.
- `windows_assumed_open` field from `ZoneState` and `SystemState`.

## [0.3.4] - 2026-05-30

### Added
- AC is now blocked when any zone's configured window sensor reports open (actual contact/reed sensor, not the assumed-open estimate). Emergencies bypass this gate. Reasoning includes which zone's window triggered the block.
- `number.adaptive_hvac_cool_exterior_threshold` entity — the outdoor temperature below which AC is blocked can now be adjusted live from the dashboard (default 60°F, range 40–80°F). Raise this to 65°F+ to match real "windows open" weather conditions.

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
