# Adaptive HVAC Integration Status — 2026-05-26

## Current State: SYSTEM RUNNING, ZONES CONFIGURED

### ✅ What's Working
- **System coordinator fully deployed** on HA (v0.2.17 with regression fixes)
- **All system entity inputs accessible:** thermostat, weather, windows, occupancy, sleep posture
- **System config UI functional:** Settings → Integrations → Adaptive HVAC → gear icon works
- **Zone entry created:** Caleb's Office zone configured with temp sensor
- **Zone auto-control toggle created:** `switch.adaptive_hvac_caleb_s_office_auto` (ON)
- **Old YAML automations still running** in parallel (hvac_cooling, hvac_heating_normal, etc.)

### 🟡 Blocking Issue: Zone Sensor Entities Not Created

Zone sensors are **not being created** even though zone coordinator should exist:
- ✗ Missing: `sensor.adaptive_hvac_calebs_office_status` (zone decision/mode)
- ✗ Missing: `sensor.adaptive_hvac_calebs_office_trend` (temp trend)
- System status stuck in `"Initializing..."` because it's waiting for zone decision data

**Root Cause:** Unknown — sensor platform async_setup_entry not creating zone entities
- Zone switch created OK, so zone entry is recognized
- Likely issue: Zone coordinator not accessible in `hass.data[DOMAIN]` when sensor platform runs, OR sensor platform not being called for zone entry

**Investigation needed:** Check HA entity registry and platform setup logs (requires deeper debugging)

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
