# Adaptive HVAC Integration Status — 2026-05-26 (Updated)

## Current State: SYSTEM COORDINATOR DISCOVERY FIXED, ZONE CONFIG RELOAD PENDING

### ✅ What's Working
- **System coordinator fully deployed** on HA (v0.2.17 with regression fixes)
- **All system entity inputs accessible:** thermostat, weather, windows, occupancy, sleep posture
- **System config UI functional:** Settings → Integrations → Adaptive HVAC → gear icon works
- **Zone entry created:** Caleb's Office zone configured (UI + config storage)
- **Zone auto-control toggle created:** `switch.adaptive_hvac_caleb_s_office_auto` (ON)
- **Zone sensor entities CREATED:** `sensor.caleb_s_office_hvac_status` + `sensor.caleb_s_office_temp_trend` exist
- **Dynamic zone discovery FIXED:** System coordinator now discovers zones at each update (not just startup)
- **Old YAML automations still running** in parallel (hvac_cooling, hvac_heating_normal, etc.)

### 🟡 Current Issue: Zone Coordinator Using Stale Config

Zone sensors exist but show `SENSOR_FAILSAFE` because:
- Zone config on disk was updated to use `sensor.caleb_s_office_hygrometer_temperature` ✓
- But zone coordinator **in memory** still has the old garage sensor config
- Root cause: HA cached the old zone entry; reload/restart didn't pick up the new config

**Next step:** Need to hard-restart HA *Docker container* (not just services) to force config reload from disk

### What Was Fixed This Session
1. **Root cause identified:** System coordinator was discovering zones during its own setup (before zones existed). Fixed by deferring discovery to update time.
2. **Zone sensor entities verified created** with correct unique_id patterns
3. **Zone config corrected on disk** with proper Caleb's office temperature sensor
4. **Code deployed:** Dynamic zone discovery in coordinator.py + cleaner __init__.py

---

## Commits This Session

| Commit | Fix |
|--------|-----|
| 23ae14e | Complete normalization for multi-select fields (v0.2.15→v0.2.17 compat) |
| 072f448 | SystemOptionsFlow 500 error (refactored to multi-step) |
| a19805b | Simplify SystemOptionsFlow to single-step (final fix) |

Plus: Fixed `configuration.yaml` input_select schema error (moved brightness_backup to input_number)

---

## How to Proceed

### Option A: Keep as-is, Use Old YAML
- Old automations are working fine
- Integration is deployed but non-functional (zone data issue)
- Safe to leave running; won't interfere

### Option B: Debug Zone Sensor Creation
Need to investigate:
1. Why sensor platform isn't creating zone entities
2. Check if zone coordinator is in `hass.data[DOMAIN]` at setup time
3. Possible fix: Adjust zone discovery in `__init__.py` to happen AFTER all zones are registered

### Option C: Temporarily Disable Sensor Platform for Zones
Skip zone sensor creation, let system infer state from raw sensor readings
(Workaround while fixing platform issue)

**Recommendation:** Document this as a known limitation, keep old YAML active, plan deeper debugging session for zone sensor platform issue later.
