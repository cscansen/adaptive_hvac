# Home Assistant — Deferred TODOs

## HVAC Adaptive System — HIGH PRIORITY

Current HVAC is fully rule-based automations (`hvac_cooling.json`, etc.) with hardcoded thresholds — snap decisions, no continuity. This breaks down in edge cases (e.g., windows open with cold outside air, temperature swings, multi-zone comfort balance).

**Goal:** Replace automations with an adaptive HVAC system (custom HACS integration or refactored template-based approach) similar to `adaptive_irrigation`:
- Continuous comfort monitoring instead of discrete trigger states
- Dynamic fan speed/setpoint based on how far from target
- Outdoor/indoor temp delta awareness (don't push cooler outside air when already below target)
- Humidity + occupancy factored in
- Smooth transitions instead of on/off/escalate snap states

**Design decision needed:** 
- Build custom integration (full control, more complex)?
- Refactor automations with templates + numerical helpers (faster, 80% of the way)?

---

## Speaker Zones Follow-Me Audio — HIGH PRIORITY

Current implementation is a single 404-line `speaker_zones_follow_updated.json` automation with 10 triggers and complex nested templates. Manual per-zone occupancy handling with hardcoded linger delays (main_floor 10min, second_floor 15min, etc.). Apple TV exclusion logic mixed into routing templates. Adding a zone or changing follow-me behavior requires template surgery.

**Goal:** Simplify audio routing and occupancy follow-me logic:
- Per-zone helper entities instead of monolithic template logic
- Configurable linger delays per zone (not hardcoded in automation)
- Separate source-routing logic from occupancy tracking
- Explicit Apple TV exclusion handling
- Service-based approach or custom integration for easier zone expansion

**Design options:**
- Refactor into modular per-zone automations + shared source-routing service
- Custom HACS integration (similar to irrigation) that owns occupancy → routing
- Leverage existing HA media router integrations if available

---

## Irrigation — Per-Zone Watering Windows — DONE (2026-05-17)

Currently the summer watering window is enforced globally (trigger at 5:30am, retry cutoff at 10am). Each zone should eventually have its own configurable window. This matters when e.g. the front yard should run later to avoid foot traffic, or a zone needs a different time due to sun exposure.

**Design sketch:**
- Add `input_datetime.irrigation_window_start_<zone>` and `input_datetime.irrigation_window_end_<zone>` helpers per zone
- Or a simpler `input_number.irrigation_window_end_hour_<zone>` (integer hour, e.g. 10)
- Change each zone's retry `if` condition and while loop to use the per-zone cutoff instead of hardcoded `now().hour < 10`
- Summer trigger remains at 5:30am; window start is implicitly "whenever the automation runs"
- Drip / garden watering (`drip_garden_watering`) also runs at 6am but timing hasn't been reviewed for this constraint

---

## Irrigation — East Sensor Staleness — PENDING

East yard soil sensor (`sensor.east_yard_soil_sensor_humidity`) stopped reporting overnight (last update ~11pm MDT), causing the 5:30am automation to see it as stale and fall back to a 6-minute survival dose. Sensor hardware is fine; Zigbee integration dropped the connection.

Also: `sensor.east_yard_soil_sensor_evapotranspiration` goes `unknown` when the parent sensor is stale — this is a calculated value from the Third Reality integration.

**Staleness window extended from 4h → 8h as a workaround.** Long-term: investigate why the Zigbee sensor drops overnight. Check coordinator health, sensor battery, and reporting interval config in the Zigbee integration.

---

## HVAC Fan Lock — DONE (2026-05-16)

Implemented via counter-automation pattern (no YAML surgery). Helpers in `configuration.yaml`. Automations:
- `fan_lock_set_claimed` — user turns on/adjusts fan → sets flag + stores speed
- `fan_lock_clear_claimed` — fan turns off → clears flag
- `fan_lock_restore` — HVAC overrides a claimed fan → restores user speed (detects via context.parent_id)
- `hvac_living_room_fan_comfort` + `garage_fan_cooling_on/off` — updated with fan_user_claimed condition

**Known edge case:** Physical switch presses (no user_id, no parent_id) are NOT treated as user claims — they bypass the lock. If this becomes an issue, revisit context detection.

---

## Garage Occupied Group — DONE (2026-05-16)

User manually updated via HA UI. `binary_sensor.garage_occupied` now includes `binary_sensor.garage_presence_sensor_presence`.

---

## Irrigation Dashboard — Run All Zones Button — DONE (2026-05-16)

Button card added to irrigation dashboard (`dashboard-irrigation`) via websocket API. Calls `script.run_all_zones_5min` (East → Middle → West → Front, 5 min each, 10s gap). REST API returned 404 for this dashboard — websocket `lovelace/config/save` is the correct method.

---

## Garage Apple TV — Entity Rename — DONE

`media_player.garage_apple_tv` rename confirmed complete by user.

---

## Adaptive HVAC v0.3.3 — Pending

### Cleanup
- [ ] Clean up stale `switch.adaptive_hvac_calebs_office_auto` (no `_2`) entity registry entry — orphaned, safe to delete via Settings → Entities
- [ ] Rename `binary_sensor.windows_assumed_open_2` → `windows_assumed_open` in entity registry now that the old broken one is deleted

### Deferred features (parking lot)
- [ ] **Occupancy setback** — away 8h+ → cool to 76°F / heat to 62°F; parked from v0.3.0, low priority
- [ ] **Fan lock integration** — zone coordinator reads `fan_config` entries with `fan_lock_entity` flags; verify fan lock automations (`fan_lock_set_claimed`, etc.) still work with v0.3.x fan dispatch
- [ ] **Winter heating test** — verify heat gating works when outdoor drops below 60°F; season override select can force "winter" for testing
- [ ] **Zone performance analyzer** — diagnostic tool for reviewing per-zone thermal trends; see `memory/zone_performance_analyzer_plan.md`
