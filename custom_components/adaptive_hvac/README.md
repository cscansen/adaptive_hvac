# Adaptive HVAC

A custom Home Assistant integration for simple, reliable whole-house HVAC control. One thermostat, multiple rooms, ceiling fans that actually follow what you want.

## What it does

- Sets the thermostat to **cool** when any room gets too warm, **heat** when any room gets too cold
- Controls **ceiling fans per room** — on when the room is above your target temp, off when it's not
- Circulates air between floors using the whole-house thermostat fan when temperature imbalance exceeds a threshold
- Respects **who owns what**: if you manually set a fan, the integration leaves it alone until midnight
- Falls back to standalone thermostat control if sensors stop reporting, then resumes automatically when they recover
- Never turns the AC off on a cool-but-sunny day when it's 80°F inside (the bug that prompted this rewrite)

## How it decides

**Each room (zone):**
- Above target temp → fan on, request cooling from system
- At or below target temp → fan off
- Room unoccupied → fan off regardless (occupancy never blocks the thermostat)

**System (thermostat):**
- Summer: run AC if any room needs it AND outdoor temp ≥ exterior threshold (default 60°F) AND outdoor temp ≥ zone comfort target — if it's cooler outside than the room's target, open windows instead; no AC
- Winter: run heat if any room needs it AND outdoor temp ≤ heat exterior threshold (default 60°F) AND outdoor temp ≤ the *warmest* zone still asking — if it's warmer outside than that, open windows instead; no heat
- Either season: conditioning is blocked if any zone's window sensor is open (only zones with `affects_thermostat = ON`; emergencies bypass). The house is being aired out on purpose — don't fight it.
- Any room 5°F above its target bypasses the exterior threshold gate (interior override)
- When any zone requests cooling, the AC setpoint is lowered by the **demand boost** amount (default 1°F) to push harder
- All thresholds are configurable via dashboard sliders; no restart required

## Air quality & windows

Two separate things, often confused:

**1. AQI never unblocks the HVAC.** If it's cooler outside than your targets, the AC stays
off whether the air is clean or full of wildfire smoke. What air quality changes is the
*reason code and the message*, so the system stops cheerfully telling you to open the
windows during a smoke event. Point `aqi_sensor` (setup step 1 / Reconfigure) at any
sensor reporting US AQI; `number.adaptive_hvac_aqi_threshold` is the ceiling, default 50
(EPA "Good"). Note that summer ozone routinely pushes AQI past 50 with clean particulates
— raise it if you find the recommendation too shy.

> **Fail closed:** a *configured* AQI sensor that goes unavailable counts as bad air, so a
> dead sensor can never produce an "open your windows" recommendation. With no sensor
> configured at all, behavior is exactly as it was before air quality existed.

**2. `binary_sensor.adaptive_hvac_windows_recommended` is advisory only** — it never gates
the thermostat. It's an **absolute 60-75°F band** (`window_min_outdoor` / `window_max_outdoor`)
requiring no rain, no high wind, and clean air.

It is deliberately **independent of season and of your zone targets**, which is not the
obvious implementation. The season model is binary and calendar-driven — all of October
reads as "winter" — so a target-relative rule would refuse to suggest windows on a 62°F
October afternoon because 62 < the 68°F heat target. That shoulder-season case is the
whole point. `test_windows_recommended_in_october_shoulder_season` guards this.

The one overlap to know about: at 74°F outdoors with a 72°F target, the band still says
"open up" while a zone wants cooling. Slide `window_max_outdoor` down to 72 rather than
expecting logic to resolve it — the two band sliders are the seasonal-feel knobs.

### Blocked reason codes

`binary_sensor.adaptive_hvac_cooling_blocked` and `..._heating_blocked` each carry a
machine-readable `blocked_reason` (surfaced only on whichever one is actually blocked),
so notifications branch per cause instead of string-matching free text:

| Summer | Winter | Meaning |
|---|---|---|
| `window_open` | `window_open_heat` | A window is open; airing out wins |
| `outdoor_cold` | `outdoor_warm` | Past the exterior threshold, no interior override |
| `open_windows_better` | `open_windows_warm` | Outdoor air would do the job, and it's clean |
| `aqi_hold` | `aqi_hold_heat` | Outdoor air would do the job, but it's smoky |

**The smoke-hold trade-off:** `aqi_hold` means the AC is off (cooler outside) *and* opening
up is a bad idea. The house coasts until the 85°F emergency-cool threshold or you step in;
winter mirrors this at 55°F. Both smoke-hold notifications are time-sensitive and carry a
one-tap "Run HVAC anyway" action wired to `switch.adaptive_hvac_manual_override`.

> **Gotcha — the winter relative gate can be unreachable.** `heat_exterior_threshold`
> always fires first, so while it sits *below* every zone target, `open_windows_warm` can
> never happen (you'd need outdoor ≤ threshold and outdoor > target simultaneously). With
> the default 60°F against 68-70°F targets it is inert. Raise
> `number.adaptive_hvac_heat_exterior_threshold` above your warmest zone target to enable it.

**Floor fan circulation:**
- Zones are grouped by their HA floor assignment
- When the average temperature difference between floors exceeds the **floor circulation delta** (default 2°F), the thermostat fan is set to `on` to circulate air — but only while heat or AC is actually running
- With the thermostat idle, circulation is suppressed (no conditioned air to distribute), with one exception: a window is open, outdoor air is cooler than the indoor average, and the coldest floor is still at or above the active heat setpoint — then the fan keeps pulling cool window air through the house

**Degraded mode / failover:**
- If sensors are unavailable or stale for 2 consecutive evaluation cycles (~6 minutes), the integration enters degraded mode
- The thermostat is set to `auto` so it governs itself via its internal schedule
- A persistent HA notification lists exactly which sensors are affected
- Normal control resumes automatically when all sensors recover

## Installation

1. In HACS → Custom Repositories → add `https://github.com/cscansen/adaptive_hvac` as an Integration
2. Install **Adaptive HVAC**
3. Restart Home Assistant
4. Settings → Devices & Services → Add Integration → **Adaptive HVAC**
5. Set up the **System** entry first, then add a **Zone** entry for each room

> **Upgrading from v0.2.x:** Requires fresh setup — delete old integration entries and reconfigure.

## System setup

| Setting | Default | Notes |
|---------|---------|-------|
| Thermostat | — | Required. Your `climate` entity |
| Outdoor temp sensor | — | Optional. Local `sensor` entity; takes priority over weather entity |
| Weather entity | — | Optional. Outdoor temp fallback if no local sensor configured |
| Sleep posture entity | — | Optional. `input_boolean` or binary sensor; suppresses floor fan circulation when on |
| Occupancy sensors | — | Optional. Reserved for future setback logic |
| AC setpoint | 68°F | Target cooling temperature |
| Upstairs demand boost | 1°F | Lower AC setpoint by this much when any zone calls for cooling (0–2°F) |
| Cool exterior threshold | 60°F | Don't run AC if outdoor below this |
| Cool interior override | 5°F | Bypass exterior threshold if any room is this far above its target |
| Emergency cool threshold | 85°F | Always cool above this regardless of gating |
| Heat setpoint | 68°F | Target heating temperature |
| Heat threshold | 68°F | Zone temp that triggers a heat request |
| Heat exterior threshold | 60°F | Don't heat if outdoor above this |
| Emergency heat threshold | 55°F | Always heat below this |
| Floor circulation delta | 2°F | Inter-floor temp difference that triggers whole-house fan |
| Sensor staleness window | 60 min | Flag sensors that haven't reported within this window |
| Winter start month | October | Calendar month winter begins |
| Winter end month | April | Calendar month winter ends |
| Night start hour | 10pm | Hour night mode's time window begins (0–23) |
| Night end hour | 6am | Hour night mode's time window ends (0–23) |
| Night mode source entity | — | Optional. `input_boolean`/`binary_sensor` — when "on", night mode is active regardless of time window |

## Zone setup

| Setting | Default | Notes |
|---------|---------|-------|
| Zone name | — | Required. Used for entity naming |
| Floor | — | Optional. Select from HA floor registry; enables floor fan circulation |
| Temperature sensors | — | Required. Averaged if multiple |
| Humidity sensor | — | Optional |
| Window sensor | — | Optional. When open, blocks AC (only when `affects_thermostat = ON`) |
| Occupancy sensor | — | Optional. Controls local fan only |
| Fans | — | Fan entities this zone controls |
| Zone target temp | 72°F | Fan on above this, fan off at/below |
| Fan speed | 50% | Speed when fan is running |
| Affects thermostat | ON | When OFF, zone controls its fans only — never sends thermal requests or blocks AC via window sensor. Use for unconditioned spaces like garages. |

> **Do not add the thermostat's whole-house fan as a zone fan** — occupancy would turn it off incorrectly. The floor circulation feature manages the whole-house fan automatically.

## Entities created

**System entry:**

| Entity | Description |
|--------|-------------|
| `sensor.adaptive_hvac_status` | Current decision + full reasoning. Attributes include `thermostat_entity`, `outdoor_temp_sensor`, `thermostat_mode`, `thermostat_setpoint`, `whole_house_fan`, `season`, `night_mode_active`, `reasoning` |
| `sensor.adaptive_hvac_mode` | Thermostat mode (cool / heat / off) |
| `sensor.adaptive_hvac_season` | Current season (summer / winter) |
| `select.adaptive_hvac_season_override` | Force summer / winter for testing |
| `switch.adaptive_hvac_active` | Enable / disable the integration |
| `switch.adaptive_hvac_manual_override` | Pause all automation |
| `number.adaptive_hvac_ac_setpoint` | AC setpoint (live adjustable) |
| `number.adaptive_hvac_upstairs_demand_boost` | Setpoint reduction when zones call for cooling (0–2°F) |
| `number.adaptive_hvac_fan_circulation_delta` | Inter-floor delta that triggers whole-house fan (0.5–5°F) |
| `number.adaptive_hvac_cool_exterior_threshold` | Outdoor temp gate for AC (live adjustable) |
| `number.adaptive_hvac_heat_setpoint` | Heat setpoint (live adjustable) |
| `number.adaptive_hvac_heat_threshold` | Heat trigger temp (live adjustable) |
| `number.adaptive_hvac_heat_exterior_threshold` | Outdoor temp gate for heat. Also the ceiling on the winter relative gate — see the gotcha above |
| `number.adaptive_hvac_emergency_cool_threshold` | Emergency cool threshold |
| `number.adaptive_hvac_emergency_heat_threshold` | Emergency heat threshold |
| `binary_sensor.adaptive_hvac_cooling_blocked` | Zones want AC, a gate says no. Attributes: `reason`, `blocked_reason`, `status`, `aqi`, `aqi_category`, `windows_recommended` |
| `binary_sensor.adaptive_hvac_heating_blocked` | Winter mirror of the above |
| `binary_sensor.adaptive_hvac_windows_recommended` | Advisory only — outdoor air is in-band, calm, dry and clean. Attributes: `outdoor_temp`, `aqi`, `aqi_category`, `aqi_ok`, `weather_ok`, `band_min`, `band_max` |
| `sensor.adaptive_hvac_air_quality` | Outdoor US AQI as the engine sees it. Attributes: `category`, `aqi_ok`, `threshold`, `source_entity` |
| `number.adaptive_hvac_aqi_threshold` | AQI ceiling for recommending windows (25–200, default 50) |
| `number.adaptive_hvac_window_min_outdoor` | Bottom of the windows-recommended band (45–70°F, default 60) |
| `number.adaptive_hvac_window_max_outdoor` | Top of the windows-recommended band (65–85°F, default 75) |
| `switch.adaptive_hvac_night_mode` | Manual night mode toggle |
| `number.adaptive_hvac_night_ac_setpoint` | AC setpoint used while night mode is active |
| `number.adaptive_hvac_night_heat_setpoint` | Heat setpoint used while night mode is active |

**Each zone entry:**

| Entity | Description |
|--------|-------------|
| `sensor.{zone}_hvac_status` | Zone mode and reasoning. Attributes include `temp_sensors`, `fans`, `floor`, `affects_thermostat`, `zone_target_temp`, `mode`, `thermal_request`, `urgency`, `reasoning`, `fan_commands` |
| `sensor.{zone}_temp_trend` | Temperature trend in °F/hr (30-minute rolling window) |
| `number.{zone}_target_temp` | Per-zone target temperature (60–85°F, 0.5°F step). Fan on at/above this, fan off below. Adjustable directly from the dashboard; persists across restarts. |
| `switch.adaptive_hvac_{zone}_auto` | Auto-control toggle — OFF means the integration skips this zone entirely |
| `switch.adaptive_hvac_{zone}_fan_locked` | Fan lock — ON means user has claimed the fan; integration hands off until midnight |

## Fan lock

When a user manually adjusts a ceiling fan, the integration detects the change and claims that zone's fans:

- **Fan turned ON** — integration preserves your speed and won't override it
- **Fan adjusted** — new speed stored, integration continues to leave it alone
- **Fan turned OFF** — integration won't turn it back on until midnight
- **Midnight** — all fan locks clear automatically; normal control resumes
- **Manual release** — toggle `switch.adaptive_hvac_{zone}_fan_locked` OFF at any time to release immediately

Physical wall switch presses are detected the same as app or UI adjustments.

## Thermostat setpoint ownership

When you adjust the thermostat setpoint from the **HA app or UI**, the integration adopts it as the new target for the current season and persists it across restarts.

Use the **`number.adaptive_hvac_ac_setpoint` dashboard slider** as the primary way to adjust the cooling target — it persists immediately without waiting for a thermostat interaction.

> **The slider only reaches the physical thermostat once a zone is actively calling for
> cool/heat.** If the system is currently idle, moving the slider updates the stored
> target immediately but the thermostat's own displayed setpoint won't change until the
> next time AC/heat actually engages — this is expected, not a bug. Use **Force Evaluate
> Now** to trigger an immediate decision if you want to confirm the new value took.
>
> The value actually sent to the thermostat is `ac_setpoint − upstairs_demand_boost`
> (or `+ boost` for heat), rounded to the nearest whole degree — so the thermostat's
> displayed setpoint may legitimately differ from the slider by the boost amount.

## Night mode

A separate setpoint pair used whenever night mode is active, so you don't have to
manually push the day setpoint down every evening and back up every morning.

- `number.adaptive_hvac_night_ac_setpoint` / `number.adaptive_hvac_night_heat_setpoint` —
  live-adjustable, same as the day setpoints. Only take effect while night mode is active.
- `number.adaptive_hvac_night_start_hour` / `number.adaptive_hvac_night_end_hour` —
  live-adjustable schedule window (0-23, default 22/6). **Dashboard-only** — there is no
  setup-wizard prompt for these; see "Required: deploy the dashboard" below.
- Night mode activates from **any** of these (first match wins):
  1. `switch.adaptive_hvac_night_mode` — manual toggle, dashboard or automation.
  2. An optional `night_mode_source_entity` (any `input_boolean` or `binary_sensor`) —
     configure this in System → Configure to bind night mode to an existing helper, e.g.
     `input_boolean.downstairs_sleep_posture`.
  3. The configured time window (`night_start_hour`–`night_end_hour`, default 10pm–6am,
     adjustable only via the `number` entities above).
- `sensor.adaptive_hvac_status` exposes `night_mode_active` and notes it in `reasoning`
  when in effect.

## Dashboard

The integration ships with a dashboard generator that builds a fully populated Lovelace HVAC dashboard from your live zone configuration. No manual editing required; re-run whenever zones are added or removed.

### Required: deploy the dashboard

Deploying the generated dashboard isn't optional polish — it's how you set the night mode
schedule and both setpoint pairs. The setup wizard only asks about zones, thresholds, and
which existing entities (if any) should drive night mode; the actual setpoint and schedule
*values* are dashboard-only `number` entities with no other UI (short of Developer Tools →
States, which is unpleasant for everyday use). Right after adding the integration:

1. Follow **[DASHBOARD.md](DASHBOARD.md)** — pick **Option A** (copy-paste into the Raw
   Config Editor, no SSH needed) if you don't have host access, or **Option B** (SSH
   deploy) if you do.
2. Confirm the **Night Mode** card shows the toggle plus all four numbers (AC/Heat
   setpoint, Start/End hour) with sensible values before relying on night mode.

The generated dashboard includes a **Rebuild Dashboard** button that regenerates the dashboard in place without a token — one tap from the UI, for whenever zones change later.

## Zones with compound fan logic (e.g. garage)

The per-zone rule is intentionally simple: one temp threshold, fan on above it. Some
spaces need compound logic the integration doesn't model — e.g. "run the garage fans if
the doors are open, OR if someone's been out there a while and it's hot." Rather than
special-casing that into the integration, turn the zone's own control off and let a
plain HA automation own the fan instead:

1. Turn `switch.adaptive_hvac_{zone}_auto` **off** — the zone's status/temp sensors keep
   reporting for the dashboard, but the integration stops touching its fans.
2. Write a normal HA automation against the fan entity directly, using whatever
   combination of door/cover, occupancy-with-duration, and temperature conditions the
   space needs.

This keeps the integration's zone model simple while letting oddball spaces have
however-complex logic they actually need.

## Diagnosing decisions

The `sensor.adaptive_hvac_status` entity carries a `reasoning` attribute that shows the full decision tree on every poll:

```
Season: summer | Outdoor: 78.0°F | AC allowed | Upstairs demand boost: setpoint 68°F → 67°F | SYSTEM: COOL → 67°F
```

Force an immediate evaluation:
```yaml
service: adaptive_hvac.force_evaluate
```

Or via the dashboard **Force Evaluate Now** button.

## Troubleshooting

**System entities show unavailable after install**
Ensure you are running HA 2024.1.0 or later.

**"No zone data available" or "Initializing..."**
Normal for ~3 minutes after startup — the system coordinator polls on a 3-minute cycle. Use Force Evaluate to trigger immediately.

**Zone shows SENSOR FAILSAFE**
Temperature sensor is returning an invalid value or is unavailable. Check the entity IDs configured for the zone. If the condition persists for 2 cycles, degraded mode activates and the thermostat takes over; a persistent notification lists which sensors are affected.

**AC won't turn on even though it's hot**
Check `sensor.adaptive_hvac_status` reasoning attribute. Common causes:
- Outdoor temp below `cool_exterior_threshold` and no room is 5°F above its target
- A zone's window sensor is reporting open (`affects_thermostat = ON` zones only)
- `switch.adaptive_hvac_active` is off
- `switch.adaptive_hvac_manual_override` is on

**Fan not responding**
- Check the zone's auto-control switch (`switch.adaptive_hvac_{zone}_auto`) is ON
- Check the fan lock switch (`switch.adaptive_hvac_{zone}_fan_locked`) — toggle OFF to release immediately

**Floor fan running when it shouldn't**
- Reduce the `number.adaptive_hvac_fan_circulation_delta` threshold
- Check that zones are assigned to the correct HA floor in zone → Configure → Floor
- Enable your sleep posture entity to suppress circulation at night

**Degraded mode notification keeps firing**
A sensor is consistently unavailable or stale. Check the affected sensors listed in the notification. Increase `sensor_staleness_minutes` in the system config options if sensors report infrequently by design.

## License

MIT — see [LICENSE](LICENSE)
