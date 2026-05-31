# Adaptive HVAC Integration — Complete Reference

**Version:** v0.3.8  
**Source:** `/custom_components/adaptive_hvac/`  
**Status:** Deployed, replaces old 13-automation YAML system

## Overview

Multi-zone HVAC control integration. Each room gets its own zone entry; a single system entry owns the thermostat. Decision logic lives in a pure Python engine with no HA imports.

Key behaviors:
- Per-zone fan control gated by occupancy
- Thermostat decisions never blocked by occupancy
- System-level AC/heat gating by exterior temperature
- Window sensors block AC on a per-zone basis
- User fan adjustments lock that zone's fans until midnight
- Season derived from calendar (Oct–Apr = winter, May–Sep = summer) with optional override

## Architecture

```
Zone Coordinators (one per room)
  → read temp, occupancy, window, fan lock
  → emit ZoneDecision (fan commands + thermal request)

System Coordinator (one)
  → aggregates zone thermal requests
  → applies exterior gating + window blocking
  → writes thermostat mode/setpoint
```

**Logic engine** (`logic.py`) — pure Python, no HA imports. Used by both the integration and unit tests.

## Configuration

### System entry (`system`)

Settings → Integrations → Adaptive HVAC → Configure (system entry)

| Setting | Default | Purpose |
|---------|---------|---------|
| Thermostat | `climate.downstairs_thermostat` | Controls mode and setpoint |
| Weather entity | `weather.forecast_home` | Exterior temperature source |
| AC setpoint | 68°F | Cooling target |
| Heat setpoint | 68°F | Heating target |
| Heat threshold | 68°F | Zone temp that triggers a heat request |
| Emergency heat threshold | 55°F | Bypasses all gating |
| Cool exterior threshold | 60°F | Min outdoor temp to allow AC (slider: `number.adaptive_hvac_cool_exterior_threshold`) |
| Heat exterior threshold | 60°F | Max outdoor temp to allow heat |
| Cool interior override delta | 5°F | If any zone is this far above its target, bypass exterior gate |

**Current deployed values:** cool exterior threshold = 68°F.

### Zone entry (`zone`)

One per room. Settings → Integrations → Add → Adaptive HVAC

| Setting | Default | Purpose |
|---------|---------|---------|
| Zone name | — | Creates all zone entities (slug used in entity IDs) |
| Floor | — | Informational grouping |
| Temp sensors | — | Averaged for zone decisions (required) |
| Humidity sensor | — | Optional, displayed in status |
| Fans | — | Entity IDs this zone controls |
| Fan speed | 50% | Speed when integration turns fan on |
| Window sensor | — | Open = block AC for this zone only |
| Occupancy sensor | — | Off = fans off (thermostat requests unaffected) |
| Zone target temp | 72°F | Fan turns on above this |
| Emergency cool threshold | 85°F | Bypass all gating, fan 100% |
| Auto-control switch | — | `switch.adaptive_hvac_{zone}_auto` — turns off fan automation |

### Deployed zones (v0.3.7)

| Zone | Temp sensor | Fans | Auto switch | Fan lock switch |
|------|-------------|------|-------------|-----------------|
| Caleb's Office | `sensor.caleb_s_office_hygrometer_temperature` | `fan.caleb_office_ceiling` | `switch.adaptive_hvac_calebs_office_auto_2` | `switch.adaptive_hvac_calebs_office_fan_locked` |
| Tia's Office | `sensor.tias_office_hygrometer_temperature` | `fan.tia_office_ceiling_fan` | `switch.adaptive_hvac_tias_office_auto` | `switch.adaptive_hvac_tias_office_fan_locked` |
| Master Bedroom | `sensor.meter_pro_2689_temperature` | (fans TBD) | `switch.adaptive_hvac_master_bedroom_auto` | `switch.adaptive_hvac_master_bedroom_fan_locked` |
| Garage | `sensor.garage_hygrometer_temperature` | — | `switch.adaptive_hvac_garage_auto` | `switch.adaptive_hvac_garage_fan_locked` |

Note: `switch.adaptive_hvac_calebs_office_auto` (no `_2`) is an orphaned registry entry — unavailable, ignore it.

## Decision Logic

### Zone decision

1. Manual override → no action
2. System inactive → no action
3. Temp sensor invalid (≤0 or ≥200) → failsafe, no action
4. Temp ≥ emergency threshold → fan 100%, request cool (unless fan locked)
5. Temp ≤ emergency heat threshold → request heat, no fan
6. Temp > zone target → fan on at configured speed (if occupied and not locked), request cool/heat per season
7. Temp ≤ zone target AND ≤ heat threshold → request heat, no fan
8. Otherwise → fan off (if not locked), no thermal request

**Fan locked:** if the zone's fan lock is ON, the integration skips all fan commands for that zone. Thermal requests still go through.

### System decision

Aggregates zone thermal requests, then applies gating:

**Cooling allowed if:**
- Outdoor temp ≥ cool exterior threshold, OR
- Any zone is ≥ 5°F above its target (emergency bypass)
- AND no zone window sensor is open (unless emergency)

**Heating allowed if:**
- Outdoor temp ≤ heat exterior threshold

**Season** — calendar only: Oct–Apr = winter, May–Sep = summer. Override: `select.adaptive_hvac_season_override`.

**Setpoint adoption:** if the user adjusts the thermostat faceplate or app, the integration adopts the new value as the seasonal setpoint and persists it to config options. Resets on season change.

## Fan Lock System

Built into the integration since v0.3.6. No external automations or helpers needed.

| Event | Result |
|-------|--------|
| User turns fan ON or changes speed | Lock turns ON, integration stops touching that zone's fans |
| User turns fan OFF | Lock turns ON (integration won't turn it back on) |
| Midnight | All zone locks clear automatically |
| Manual release | Toggle the fan locked switch OFF |

**Edge case:** Physical wall switch presses have no `context.user_id` and bypass the lock trigger. The integration can still override fans set via physical switch.

## Key Entities

### System-level
| Entity | Purpose |
|--------|---------|
| `sensor.adaptive_hvac_status` | Current decision + `reasoning` attribute (full decision tree) |
| `sensor.adaptive_hvac_season` | Active season |
| `sensor.adaptive_hvac_mode` | Current mode |
| `switch.adaptive_hvac_active` | Enable/disable integration |
| `switch.adaptive_hvac_manual_override` | Freeze integration, user controls thermostat directly |
| `number.adaptive_hvac_cool_exterior_threshold` | Live slider for cool exterior gate (currently 68°F) |
| `climate.downstairs_thermostat` | The controlled thermostat |
| `sensor.upstairs_average_temperature` | Avg of Caleb + Tia + Master temps (`templates.yaml`) |

### Per-zone
| Entity pattern | Purpose |
|----------------|---------|
| `sensor.{zone}_hvac_status` | Zone mode + reasoning |
| `switch.adaptive_hvac_{zone}_auto` | Auto-control on/off |
| `switch.adaptive_hvac_{zone}_fan_locked` | Fan lock state (ON = locked) |

## Dashboard

`/dashboard-hvac` — system status, per-zone cards, upstairs temp, thermostat history, logbook, controls, setpoint sliders, force-evaluate button.

## Testing

```bash
# Force immediate evaluation
source ~/.secrets && curl -s -X POST http://ha.iot.scansenconsulting.com:8123/api/services/adaptive_hvac/force_evaluate \
  -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d '{}'

# Read current decision + reasoning
curl -s http://ha.iot.scansenconsulting.com:8123/api/states/sensor.adaptive_hvac_status \
  -H "Authorization: Bearer $HA_TOKEN" | python3 -c "import json,sys; s=json.load(sys.stdin); print(s['state']); print(s['attributes'].get('reasoning'))"
```

## Deployment

```bash
# SSH to HA host
ssh -i ~/.ssh/infra hassio@192.168.255.247

# Copy integration (from devbox)
scp -i ~/.ssh/infra -r custom_components/adaptive_hvac hassio@192.168.255.247:/tmp/
ssh -i ~/.ssh/infra hassio@192.168.255.247 "sudo cp -r /tmp/adaptive_hvac /config/custom_components/"

# Reload
curl -s -X POST http://ha.iot.scansenconsulting.com:8123/api/services/homeassistant/reload_custom_components \
  -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d '{"domain": "adaptive_hvac"}'
```

## Release Checklist (HACS)

**CRITICAL: Never commit after creating a release. HACS downloads the release tag, not HEAD.**

1. Finalize all code on master
2. Update `manifest.json` version
3. Add entry to `CHANGELOG.md`
4. Commit: `git commit -m "..."`
5. Push: `git push origin master`
6. Release: `gh release create vX.Y.Z --title "..." --notes "..."`
7. Verify tag points to HEAD: `git show-ref vX.Y.Z`

## Changelog Summary

| Version | Key change |
|---------|-----------|
| v0.3.8 | Five correctness fixes — see detail below |
| v0.3.7 | Internal: simplified fan lock — replaced `fans_claimed` set with `fan_locked` bool, removed unused `_fan_claimed_speed` |
| v0.3.6 | Native fan lock per zone (`switch.adaptive_hvac_{zone}_fan_locked`), midnight reset, removes all external fan lock automations/helpers |
| v0.3.5 | Removed `windows_assumed_open` sensor and config option |
| v0.3.4 | Per-zone window sensor AC gate + `number.adaptive_hvac_cool_exterior_threshold` entity |
| v0.3.3 and earlier | See `CHANGELOG.md` |

## v0.3.8 — Change log for incident diagnosis

Five bugs were found by code review and fixed on 2026-05-31. If something broke after updating to v0.3.8, this section is your first stop.

---

### Fix 1 — Emergency cooling now overrides fan lock (`logic.py`)

**What changed:** `decide_zone()` emergency cooling branch (`temp ≥ 85°F`) previously returned `fan_commands={}` when a zone's fan was locked. Now it always commands `fan_speed=100%` regardless of lock state.

**Before:** User locks a fan → room hits 85°F → thermostat runs AC, but ceiling fan stays at whatever the user left it (or off). Functionally degraded cooling at the worst moment.

**After:** Emergency threshold overrides the lock. Fans spin at 100%. Lock clears at midnight as normal.

**If this causes a problem:** A user-locked fan spinning up unexpectedly during an emergency. To suppress: lower `emergency_cool_threshold` above any realistic room temp, or use `switch.adaptive_hvac_active` to pause the integration.

---

### Fix 2 — Platform setup order changed for zone entries (`__init__.py`)

**What changed:** For zone config entries, `async_forward_entry_setups()` (which creates entities including `FanLockedSwitch`) now runs **before** `async_config_entry_first_refresh()`. Previously it was the reverse — entities were created after the first coordinator evaluation.

**Before:** On every HA restart, the first evaluation ran with `_fan_locked=False` regardless of persisted state, potentially issuing a fan command that the lock was supposed to suppress.

**After:** `FanLockedSwitch.async_added_to_hass` restores `_fan_locked` before the first evaluation runs.

**If this causes a problem:** Entities may briefly show as unavailable at startup (coordinator has no data yet when entities first appear). They populate on the first refresh, which runs immediately after. If zone entities fail to load, check HA logs for `ConfigEntryNotReady` from the zone coordinator — that indicates a sensor read failure during first refresh, same as before.

---

### Fix 3 — Setpoint adoption uses HA options API (`coordinator.py`)

**What changed:** `handle_thermostat_state_change()` previously wrote directly to the `core.config_entries` JSON file on disk to persist adopted setpoints. This left `config_entry.options` stale in memory for the rest of the session, so `_effective_setpoint()` was silently using the old value. Now it calls `hass.config_entries.async_update_entry()` which updates both the in-memory cache and the persisted storage correctly.

A `_suppress_setpoint_reload` flag prevents the options-change event from triggering a full config-entry reload (which would have briefly made entities unavailable).

**Before:** Adjusting the thermostat from the faceplate or app appeared to be adopted, but `_effective_setpoint()` returned the previous options value for the rest of the session. Only after an HA restart would the adopted value take effect.

**After:** Adopted setpoints are effective immediately and persisted correctly.

**If this causes a problem:** The suppress-reload flag is set to `True` before `async_update_entry` and cleared in the update listener. If the listener fires more than once (e.g., due to a race), only the first call is suppressed — subsequent calls trigger a normal reload. If setpoint adoption is causing unexpected reloads, check `_suppress_setpoint_reload` state in the coordinator.

---

### Fix 4 — Guard against `None` broadcast in fan lock methods (`coordinator.py`)

**What changed:** `set_fan_lock()`, `_handle_fan_change()`, and `_midnight_reset()` now check `if self.last_decision is not None` before calling `async_set_updated_data(self.last_decision)`. Previously, if any of these fired before the first coordinator evaluation completed, `None` would be broadcast to all subscribers.

**Before:** A switch restore, fan event, or (theoretically) a midnight reset at the exact moment of startup could push `None` as coordinator data, causing `AttributeError` in entity property accessors or making entities show unavailable.

**After:** If `last_decision` is None, the immediate notify is skipped; `async_request_refresh()` still runs and will populate data correctly.

**If this causes a problem:** If fan lock state changes aren't reflected immediately in the UI, it means `last_decision` was None at the time of the change and the refresh hasn't completed yet. This is a transient startup condition and self-resolves within one scan interval.

---

### Fix 5 — Fan lock switch shows correct state immediately after restart (`switch.py`)

**What changed:** `FanLockedSwitch.async_added_to_hass()` now calls `self.async_write_ha_state()` after restoring `_fan_locked` from persisted state.

**Before:** After HA restart, the fan lock switch UI showed the wrong state (off/False) for up to one full scan interval (3 minutes) even though the coordinator was correctly enforcing the lock.

**After:** Switch reflects correct state immediately after entity setup completes.

**If this causes a problem:** None expected — `async_write_ha_state()` is a standard HA pattern for RestoreEntity. If the switch flickers on startup, it's likely a coordinator data timing issue, not this change.
