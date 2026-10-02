# Adaptive HVAC Integration — Complete Reference

**Version:** v0.4.1  
**Source:** `/custom_components/adaptive_hvac/`  
**Status:** Deployed, replaces old 13-automation YAML system

## Overview

Multi-zone HVAC control integration. Each room gets its own zone entry; a single system entry owns the thermostat. Decision logic lives in a pure Python engine with no HA imports.

Key behaviors:
- Per-zone fan control gated by occupancy
- Thermostat decisions never blocked by occupancy
- System-level AC/heat gating by exterior temperature and relative outdoor temp
- Window sensors block AC on a per-zone basis
- User fan adjustments lock that zone's fans until midnight
- Season derived from calendar (Oct–Apr = winter, May–Sep = summer) with optional override
- Per-zone "affects thermostat" flag — garages and unconditioned spaces control fans only

## Architecture

```
Zone Coordinators (one per room)
  → read temp, occupancy, window, fan lock
  → emit ZoneDecision (fan commands + thermal request)

System Coordinator (one)
  → aggregates zone thermal requests
  → applies exterior gating + window blocking
  → writes thermostat mode/setpoint
  → annotates zone decisions to reflect actual system state (passive vs active)
```

**Logic engine** (`logic.py`) — pure Python, no HA imports. Used by both the integration and unit tests.

## Configuration

### System entry (`system`)

Settings → Integrations → Adaptive HVAC → Configure (system entry)

| Setting | Default | Purpose |
|---------|---------|---------|
| Thermostat | `climate.downstairs_thermostat` | Controls mode and setpoint |
| Outdoor temp sensor | — | Optional local `sensor` entity; takes priority over weather entity |
| Weather entity | `weather.forecast_home` | Exterior temperature fallback if no local sensor |
| AC setpoint | 68°F | Cooling target (`number.adaptive_hvac_ac_setpoint`) |
| Upstairs demand boost | 1°F | Subtract from AC setpoint when any zone calls for cooling (`number.adaptive_hvac_upstairs_demand_boost`, 0–2°F) |
| Heat setpoint | 68°F | Heating target |
| Heat threshold | 68°F | Zone temp that triggers a heat request |
| Emergency heat threshold | 55°F | Bypasses all gating |
| Cool exterior threshold | 60°F | Min outdoor temp to allow AC (`number.adaptive_hvac_cool_exterior_threshold`) |
| Heat exterior threshold | 60°F | Max outdoor temp to allow heat (`number.adaptive_hvac_heat_exterior_threshold`). Also caps the winter relative gate — see the note under System decision |
| Cool interior override delta | 5°F | If any zone is this far above its target, bypass exterior gate |
| AQI sensor | — | Optional `sensor` reporting US AQI. On this install: `sensor.outdoor_aqi` (Open-Meteo REST, keyless, in `configuration.yaml`) |
| AQI ceiling | 50 | Above this, windows stop being good advice (`number.adaptive_hvac_aqi_threshold`, 25–200) |
| Window band min | 60°F | Bottom of the windows-recommended band (`number.adaptive_hvac_window_min_outdoor`) |
| Window band max | 75°F | Top of the same band (`number.adaptive_hvac_window_max_outdoor`) |

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
| Window sensor | — | Open = block conditioning (AC **and** heat as of v0.4.0) |
| Occupancy sensor | — | Off = fans off (thermostat requests unaffected) |
| Zone target temp | 72°F | Fan turns on above this |
| Emergency cool threshold | 85°F | Bypass all gating, fan 100% |
| Affects thermostat | ON | OFF = fans only; zone never sends cooling/heating request to thermostat. Use for garages, workshops, or any space not served by the HVAC duct |
| Auto-control switch | — | `switch.adaptive_hvac_{zone}_auto` — turns off fan automation |

### Deployed zones (v0.4.0)

| Zone | Temp sensor | Fans | Affects thermostat | Auto switch | Fan lock switch |
|------|-------------|------|--------------------|-------------|-----------------|
| Caleb's Office | `sensor.caleb_s_office_hygrometer_temperature` | `fan.caleb_office_ceiling` | Yes | `switch.adaptive_hvac_calebs_office_auto_2` | `switch.adaptive_hvac_calebs_office_fan_locked` |
| Tia's Office | `sensor.tias_office_hygrometer_temperature` | `fan.tia_office_ceiling_fan` | Yes | `switch.adaptive_hvac_tias_office_auto` | `switch.adaptive_hvac_tias_office_fan_locked` |
| Master Bedroom | `sensor.meter_pro_2689_temperature` | (fans TBD) | Yes | `switch.adaptive_hvac_master_bedroom_auto` | `switch.adaptive_hvac_master_bedroom_fan_locked` |
| Living Room | `sensor.downstairs_thermostat_temperature` | — | Yes | `switch.adaptive_hvac_living_room_auto` | `switch.adaptive_hvac_living_room_fan_locked` |

The Garage was removed as a zone on 2026-07-26 — it was `affects_thermostat: false` anyway, so this
changed only fan control. Its compound door-OR-occupancy logic now lives in
`automation.garage_fans_door_occupancy_cooling`.

Note: `switch.adaptive_hvac_calebs_office_auto` (no `_2`) is an orphaned registry entry — unavailable, safe to delete in Settings → Entities.

## Decision Logic

### Zone decision

1. Manual override → no action
2. System inactive → no action
3. Temp sensor invalid (≤0 or ≥200) → failsafe, no action
4. Temp ≥ emergency threshold → fan 100%, request cool (if `affects_thermostat`)
5. Temp ≤ emergency heat threshold → request heat (if `affects_thermostat`), no fan
6. Temp > zone target → fan on at configured speed (if occupied and not locked); request cool (if `affects_thermostat`)
7. Temp ≤ zone target AND ≤ heat threshold → request heat (if `affects_thermostat`), no fan
8. Otherwise → fan off (if not locked), no thermal request

**Fan locked:** if the zone's fan lock is ON, the integration skips all fan commands for that zone. Thermal requests still go through.

**Affects thermostat:** if OFF, the zone controls its local fans normally but never sends a thermal request to the system. Window sensor also has no effect on the AC gate. Use for garages or any space not served by the HVAC duct.

### Zone status annotation

After the system decision is made, zone statuses are relabeled to reflect reality:

| Zone requested | System thermostat | Fans running | Label |
|---|---|---|---|
| cool | cool | any | COOLING (active) |
| cool | off/heat | yes | PASSIVE COOLING (fans only, no AC) |
| cool | off/heat | no | WARM (above target, nothing running) |
| heat | heat | any | HEATING (active) |
| heat | off/cool | yes | PASSIVE HEATING |
| heat | off/cool | no | COLD (below threshold, nothing running) |

### System decision

Aggregates zone thermal requests, then applies gating:

**Cooling allowed if ALL of:**
- No zone window sensor is open (unless emergency)
- Outdoor temp ≥ cool exterior threshold (60°F default) — OR any zone is ≥ 5°F above its target (interior override)
- Outdoor temp ≥ the **coolest** requesting zone's target — if it's cooler outside than the room needs to be, open windows instead

**Heating allowed if ALL of:**
- No zone window sensor is open (unless emergency) — *new in v0.4.0; the furnace previously ignored open windows entirely*
- Outdoor temp ≤ heat exterior threshold (60°F default)
- Outdoor temp ≤ the **warmest** requesting zone's target — if it's warmer outside than that, open windows instead

`min()` for cooling and `max()` for heating is deliberate: each protects the zone that is still
unsatisfied, so no room is left uncomfortable because a different room got what it wanted.

> **The winter relative gate can be unreachable.** `heat_exterior_threshold` is evaluated first,
> so while it sits *below* every zone target the relative gate can never fire — you would need
> `outdoor ≤ 60` and `outdoor > 68` at once. With this install's 60°F threshold against 68–70°F
> targets it is inert by configuration, not by defect. Raise
> `number.adaptive_hvac_heat_exterior_threshold` above the warmest zone target to enable it.
> Cooling has no such problem: the 60°F cool threshold sits below the 68–70°F targets, leaving a
> live 60–68°F window where the relative gate fires.

**When cooling runs:** dispatched setpoint = `ac_setpoint − upstairs_demand_boost` (default 1°F reduction, pushes more cold air upstairs through the single duct).

**When heating runs:** dispatched setpoint = `heat_setpoint + upstairs_demand_boost` (same entity, raises target so furnace runs harder/longer, pushing more warm air upstairs).

### Air quality (v0.4.0)

**AQI never unblocks the HVAC.** If it is cooler outside than the targets, cooling stays off whether
the air is clean or full of wildfire smoke — the relative gates above are unchanged. Air quality only
selects which `blocked_reason` and which message the decision carries, so the system stops advising
you to open the windows during a smoke event.

Fail-closed rule: a *configured* AQI sensor that reads `unavailable` counts as bad air, so a dead
sensor can never generate an "open your windows" recommendation. With no AQI sensor configured at
all, behavior is identical to pre-0.4.0.

### Blocked reason codes

Both `binary_sensor.adaptive_hvac_cooling_blocked` and `..._heating_blocked` expose a
machine-readable `blocked_reason` — surfaced only on whichever sensor is actually blocked — so
notifications branch per cause rather than string-matching free text.

| Summer | Winter | Meaning |
|--------|--------|---------|
| `window_open` | `window_open_heat` | A window is open; the house is being aired out on purpose |
| `outdoor_cold` | `outdoor_warm` | Past the exterior threshold, no interior override |
| `open_windows_better` | `open_windows_warm` | Outdoor air would do the job, and it is clean |
| `aqi_hold` | `aqi_hold_heat` | Outdoor air would do the job, but it is smoky |

**The smoke-hold trade-off:** `aqi_hold` means conditioning is off (better outside) *and* opening up
is a bad idea. The house coasts until the 85°F emergency-cool threshold — 55°F for the winter
mirror — or until you intervene. Both smoke-hold notifications are time-sensitive and carry a
one-tap "Run HVAC anyway" action wired to `switch.adaptive_hvac_manual_override`.

### Windows recommendation — advisory only

`binary_sensor.adaptive_hvac_windows_recommended` never gates the thermostat. It is an **absolute
60–75°F band** requiring no rain, no high wind, and clean air.

It deliberately ignores season *and* zone targets, which is not the obvious implementation. The
season model is binary and calendar-driven — all of October reads as "winter" — so a target-relative
rule would refuse to suggest windows on a 62°F October afternoon because 62 < the 68°F heat target.
That shoulder-season case is the entire point of the feature.
`test_windows_recommended_in_october_shoulder_season` guards this against future "simplification".

Known overlap: at 74°F outdoors against a 72°F target, the band still says "open up" while a zone
wants cooling. Slide `window_max_outdoor` down to 72 rather than adding logic — the two band
sliders exist to be tuned by feel across the year.

**Emergency:** any zone ≥ emergency cool threshold (83°F default) or ≤ emergency heat threshold (55°F) bypasses all gating.

**Season** — calendar only: Oct–Apr = winter, May–Sep = summer. Override: `select.adaptive_hvac_season_override`. Note that toggling the override walks the season-transition path and clears setpoint overrides — record `number.adaptive_hvac_ac_setpoint`/`heat_setpoint` before using it for testing.

**Setpoint adoption:** if the user adjusts the setpoint via the **HA UI or app** (`context.user_id` set), the integration adopts the new value as the seasonal setpoint and persists it to config options. Resets on season change. Use `number.adaptive_hvac_ac_setpoint` on the dashboard as the primary adjustment mechanism.

## Notifications

All four are plain HA automations, not integration code, so they can be retuned without a restart.
Edit via `GET`/`POST /api/config/automation/config/<id>` — send the **full** JSON, partial payloads
drop fields — then `check_config` and `automation/reload`.

| ID | Trigger | Purpose |
|----|---------|---------|
| `hvac_cooling_blocked_notify` | `cooling_blocked` on for 10 min | Branches on `blocked_reason` via `choose:` — four distinct messages |
| `hvac_heating_blocked_notify` | `heating_blocked` on for 10 min | Winter mirror, four branches |
| `hvac_windows_recommended_notify` | `windows_recommended` on for 10 min | Shoulder-season fresh-air nudge; suppressed when a window is already open and rate-limited to once per 2h so a band-edge wobble can't nag |
| `hvac_notification_action_handler` | `mobile_app_notification_action` = `AHVAC_OVERRIDE` | Backs the "Run HVAC anyway" button on the smoke-hold alerts |

All notify via `notify.all_phones` and are gated on `binary_sensor.anyone_home`.

## Fan Lock System

Built into the integration since v0.3.6. No external automations or helpers needed.

| Event | Result |
|-------|--------|
| User turns fan ON or changes speed | Lock turns ON, integration stops touching that zone's fans |
| User turns fan OFF | Lock turns ON (integration won't turn it back on) |
| Midnight | All zone locks clear automatically |
| Manual release | Toggle the fan locked switch OFF |

Physical wall switch presses are detected and set the fan lock (uses `context.parent_id` to distinguish integration's own dispatches from all other sources).

## Key Entities

### System-level
| Entity | Purpose |
|--------|---------|
| `sensor.adaptive_hvac_status` | Current decision + `reasoning` attribute (full decision tree) |
| `sensor.adaptive_hvac_season` | Active season |
| `sensor.adaptive_hvac_mode` | Current mode |
| `switch.adaptive_hvac_active` | Enable/disable integration |
| `switch.adaptive_hvac_manual_override` | Freeze integration, user controls thermostat directly |
| `number.adaptive_hvac_ac_setpoint` | AC cooling setpoint (live adjustable) |
| `number.adaptive_hvac_upstairs_demand_boost` | Setpoint reduction when zones call for cooling (0–2°F, default 1°F) |
| `number.adaptive_hvac_cool_exterior_threshold` | Live slider for cool exterior gate |
| `number.adaptive_hvac_heat_exterior_threshold` | Live slider for heat exterior gate; also caps the winter relative gate |
| `binary_sensor.adaptive_hvac_cooling_blocked` | Zones want AC, a gate says no. Attributes: `reason`, `blocked_reason`, `status`, `aqi`, `aqi_category`, `windows_recommended` |
| `binary_sensor.adaptive_hvac_heating_blocked` | Winter mirror of the above (v0.4.0) |
| `binary_sensor.adaptive_hvac_windows_recommended` | Advisory: outdoor air in-band, calm, dry, clean. Attributes: `outdoor_temp`, `aqi`, `aqi_category`, `aqi_ok`, `weather_ok`, `band_min`, `band_max` |
| `sensor.adaptive_hvac_air_quality` | Outdoor US AQI as the engine sees it. Attributes: `category`, `aqi_ok`, `threshold`, `source_entity` |
| `number.adaptive_hvac_aqi_threshold` | AQI ceiling for recommending windows (25–200, default 50) |
| `number.adaptive_hvac_window_min_outdoor` | Bottom of the windows-recommended band (45–70°F, default 60) |
| `number.adaptive_hvac_window_max_outdoor` | Top of the windows-recommended band (65–85°F, default 75) |
| `sensor.outdoor_aqi` / `sensor.outdoor_pm2_5` / `sensor.outdoor_pm10` | Open-Meteo REST sensors in `configuration.yaml` (keyless, 15-min poll) — the AQI source |
| `climate.downstairs_thermostat` | The controlled thermostat |
| `sensor.upstairs_average_temperature` | Avg of Caleb + Tia + Master temps (`templates.yaml`) |

### Per-zone
| Entity pattern | Purpose |
|----------------|---------|
| `sensor.{zone}_hvac_status` | Zone mode + reasoning |
| `switch.adaptive_hvac_{zone}_auto` | Auto-control on/off |
| `switch.adaptive_hvac_{zone}_fan_locked` | Fan lock state (ON = locked) |

## Dashboard

`/dashboard-hvac` — system status, per-zone cards, upstairs temp, thermostat history, logbook,
controls, setpoint sliders, the **Air & Windows** card (AQI, windows-recommended, both blocked
sensors, and the three tuning sliders), and the force-evaluate button.

Generated by `scripts/generate_dashboard.py`, mirrored on-host at
`/config/scripts/generate_hvac_dashboard.py` for the in-dashboard "Rebuild Dashboard" button —
**keep both copies in sync manually.** Dashboard changes need a full HA restart to take effect;
firing `lovelace_updated` is not enough.

## Testing

```bash
# Force immediate evaluation
source ~/.secrets && curl -s -X POST http://<ha-host>:8123/api/services/adaptive_hvac/force_evaluate \
  -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d '{}'

# Read current decision + reasoning
curl -s http://<ha-host>:8123/api/states/sensor.adaptive_hvac_status \
  -H "Authorization: Bearer $HA_TOKEN" | python3 -c "import json,sys; s=json.load(sys.stdin); print(s['state']); print(s['attributes'].get('reasoning'))"
```

## Deployment

```bash
# HA SSH rejects SCP subsystem — use base64 tar instead
source ~/.secrets
tar czf - -C /path/to/custom_components adaptive_hvac \
  | base64 \
  | ssh -i ~/.ssh/infra <ha-user>@<ha-host-ip> \
    "base64 -d > /tmp/adaptive_hvac.tar.gz && \
     sudo tar xzf /tmp/adaptive_hvac.tar.gz -C /config/custom_components/ && \
     sudo rm -rf /config/custom_components/adaptive_hvac/__pycache__ && \
     echo deployed"

# Full HA restart required for Python module changes (clears import cache)
curl -s -X POST http://<ha-host>:8123/api/services/homeassistant/restart \
  -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d '{}'
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
| v0.4.1 | Whole-house fan circulation only runs while heat/AC is active, or with windows open when outdoor is cooler than indoor and the coldest floor is still at/above the heat setpoint — fixes the fan running on an idle winter thermostat |
| v0.4.0 | Outdoor AQI gates the "open the windows" advice (never the HVAC itself); `windows_recommended` absolute 60–75°F band; winter made symmetric — open windows now block heat, winter relative gate, `heating_blocked` sensor; structured `blocked_reason` codes driving per-cause notifications |
| v0.3.34 | Night mode schedule moved from config flow to live `number` entities |
| v0.3.15 | Unoccupied zones show WARM/COLD (not PASSIVE COOLING/HEATING) — passive labels require fans actually running |
| v0.3.14 | Zone statuses distinguish passive vs active — PASSIVE COOLING when AC blocked but fans spinning; COOLING only when compressor active |
| v0.3.13 | Per-zone "Affects thermostat" toggle — unconditioned zones (garage) control fans only, never call AC/heat |
| v0.3.12 | Upstairs demand boost applies in winter too — raises heat setpoint when zones request heat |
| v0.3.11 | Local outdoor temp sensor support — `outdoor_temp_sensor` field; takes priority over weather entity |
| v0.3.10 | Relative outdoor gate — AC blocked when outdoor < requesting zone's comfort target (open windows instead) |
| v0.3.9 | Fan auto-claim fixed for physical switches; auto-control slug fix for zones with apostrophes; AC setpoint slider now persists; thermostat adoption restricted to HA UI/app; upstairs demand boost feature |
| v0.3.8 | Five correctness fixes — emergency fan lock override, platform setup order, setpoint adoption API, None broadcast guard, switch state on restart |
| v0.3.7 | Internal: simplified fan lock — replaced `fans_claimed` set with `fan_locked` bool |
| v0.3.6 | Native fan lock per zone, midnight reset, removes all external fan lock automations/helpers |
| v0.3.5 | Removed `windows_assumed_open` sensor and config option |
| v0.3.4 | Per-zone window sensor AC gate + `number.adaptive_hvac_cool_exterior_threshold` entity |
| v0.3.3 and earlier | See `CHANGELOG.md` |

## Troubleshooting

**AC won't turn on even though it's hot inside**
Check `sensor.adaptive_hvac_status` reasoning. Common blocks:
- Outdoor temp < zone's comfort target ("cooler outside, open windows") — expected behavior
- Outdoor temp < `cool_exterior_threshold` (60°F) and no zone exceeds interior override delta
- A zone window sensor is reporting open
- `switch.adaptive_hvac_active` is off or `switch.adaptive_hvac_manual_override` is on

**AC runs when it shouldn't (outdoor cooler than inside)**
Update to v0.3.10+. The relative outdoor gate blocks AC when outdoor temp is below the requesting zone's comfort target.

**Setpoint keeps resetting**
Use `number.adaptive_hvac_ac_setpoint` on the dashboard — it persists to config options immediately. Thermostat adoption only fires for HA UI/app adjustments (requires `context.user_id`); the thermostat's own schedule changes are ignored.

**Fan lock not triggering on wall switch**
Update to v0.3.9+. Earlier versions required `context.user_id` which physical switches don't set. v0.3.9+ uses `context.parent_id` to correctly identify the integration's own dispatches.

**"No zone data available" after restart**
Normal for ~3 minutes — the system coordinator polls on a 3-minute cycle. Use Force Evaluate to trigger immediately:
```bash
source ~/.secrets
curl -s -X POST http://<ha-host>:8123/api/services/adaptive_hvac/force_evaluate \
  -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d '{}'
```

**Zone entries show `not_loaded` after HA restart**
Zone entries start `not_loaded` until the system entry loads and discovers them. After HA restarts, manually reload the system entry to cascade:
```bash
source ~/.secrets
curl -s -X POST http://<ha-host>:8123/api/config/config_entries/entry/<system-entry-id>/reload \
  -H "Authorization: Bearer $HA_TOKEN"
```

**A zone is stuck in `failed_unload`**
Usually caused by a previous deployment error leaving the zone in a bad state. A full HA restart followed by a system entry reload clears it. Cannot be reloaded directly while in `failed_unload` state.
