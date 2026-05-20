# HVAC Automation Plan

## Context

Build a whole-home HVAC automation that keeps the house at ~68°F across all seasons without requiring manual thermostat intervention. Philosophy: passive/natural first (windows, fans, circulation), then active (AC/heat) only when passive fails. Caleb's office temp sensor acts as the upstairs proxy gate — the indicator that upstairs needs attention drives the whole-house response.

---

## Entity Inventory

| Role | Entity | Notes |
|---|---|---|
| Only thermostat | `climate.downstairs_thermostat` | Controls whole house HVAC |
| Master bath thermostat | `climate.bathroom` | Not in scope for main automation |
| Upstairs temp gate | `sensor.caleb_s_office_hygrometer_temperature` | No actual thermostat in office |
| Downstairs temp | `sensor.downstairs_thermostat_temperature` | |
| Outside temp/weather | `weather.home` | Has temp, precip, wind attributes |
| Upstairs fans (auto) | `fan.caleb_office_ceiling`, `fan.tia_office_ceiling_fan` | |
| Master fan (excluded) | `fan.master_ceiling_fan` | Managed by Night Mode automation — do not touch |
| Main floor fan | `fan.family_room_ceiling_fan` | |
| Downstairs fan | `fan.living_room_ceiling_fan` | |
| Caleb occupancy | `binary_sensor.calebs_office_occupancy` | |
| Night mode flag | `input_boolean.master_suite_sleep_posture` | |
| Manual override | `input_boolean.hvac_manual_override` | (to create) |
| Managed cooling flag | `input_boolean.hvac_managed_cooling` | (to create) |
| Managed heating flag | `input_boolean.hvac_managed_heating` | (to create) |
| Windows assumed open | `binary_sensor.windows_assumed_open` | Template sensor (derived from weather, not physical) |

**Window state is inferred:** outside ≤ 70°F + wind < 10 mph + summer months → assumed open → AC suppressed.  
**Whole-house fan = thermostat FAN mode** on `climate.downstairs_thermostat` (air handler circulates without heat/cool).  
**Master bedroom temp sensor is unreliable** — SwitchBot Bluetooth via gateway, returns unstable/unknown values. Not usable as fallback.  
**Whole-house humidifier** — coupled to heat cycles, not independently controllable. Treat as read-only; use humidity sensor to adjust thresholds.

---

## Season Gates

| Season | Months | Mode Allowed |
|---|---|---|
| Winter | Oct – Mar | Heating only |
| Summer | May – Sep | Cooling only |
| Shoulder | April only | Passive only (no AC, no heat unless emergency) |

Season state is stored in **`input_select.hvac_season`** (winter / summer / shoulder) — authoritative source used by all automations. One dedicated `hvac_season_transition` automation updates it when the month flips to a boundary month. Using an input_select (rather than deriving from `now().month` everywhere) allows manual override from the dashboard without editing automations.

---

## Target Temperatures

| Scenario | Target |
|---|---|
| Tia comfort (heat & cool) | 68°F |
| House floor (never go below) | 55°F |
| "Hot" upstairs threshold | 74°F (72°F if office humidity > 55%) |
| Passive cooling try zone | 72°F–74°F (fans before AC) |
| AC escalation threshold | 76°F if passive fails for 30 min |
| Occupancy setback (AC) | 76°F |
| Night setback / unoccupied (heat) | 62°F |
| Emergency heat | 50°F upstairs / 55°F anywhere |

---

## Cooling Logic (Summer: May–Sep)

**Check first: `binary_sensor.windows_assumed_open`**  
If true (outside ≤ 70°F + wind < 10 mph + no precip): suppress AC, run fans at low speed, done. Natural air handles it.

Otherwise (windows not assumed open):

1. **Comfortable** — office temp < 72°F (or < 70°F if humidity > 55%) → do nothing
2. **Warm** (office 72–74°F):
   - Run upstairs fans at 33%
   - Set thermostat to FAN mode (air handler circulates without heat/cool)
3. **Hot** (office ≥ 74°F):
   - Run upstairs fans at 50–100% (proportional to temp)
   - Air handler FAN mode continuous
   - **Solar fast-track**: if `sensor.power_production_now` > 2 kW AND time 10am–3pm → skip wait, go straight to AC at 68°F (using surplus solar)
   - Otherwise: wait 30 min → if office hasn't dropped ≥ 1°F → escalate to AC (cool, 68°F)
4. **Emergency** — office ≥ 78°F → AC immediately (no 30 min wait, regardless of solar)
5. **May exception** — passive cooling only in May; AC still permitted at ≥ 78°F emergency threshold

---

## Heating Logic (Winter: Oct–Mar)

1. **Comfortable** — downstairs temp ≥ 68°F AND office temp ≥ 65°F → do nothing
2. **Normal heat** — downstairs temp < 68°F → set thermostat to heat, 68°F
3. **Equalization** — if office temp < (downstairs temp - 5°F) → run upstairs fans to pull warm air up
4. **Floor constraint** — house temp < 55°F → emergency heat, priority override
5. **Night setback** — sleep posture ON (winter only) → heat setpoint 62°F
6. **Morning warmup** — 6am → restore 68°F

---

## Floor Equalization

**Trigger:** `abs(sensor.caleb_s_office_hygrometer_temperature - sensor.downstairs_thermostat_temperature) ≥ 5°F`  
**Applies:** year-round (any season, any time)

**When upstairs is HOT relative to downstairs** (office ≥ downstairs + 5°F):
- Run upstairs fans at 50% to push hot air toward the stairwell and circulate
- Set thermostat to FAN mode to pull air through the system
- Goal: draw cooler downstairs air up through the house

**When upstairs is COLD relative to downstairs** (downstairs ≥ office + 5°F):
- Run upstairs fans at 33% to pull warm air that's risen from below
- Set thermostat to FAN mode
- Goal: distribute the heat that naturally rose downstairs but stalled

**Turn off** equalization fans when delta drops below 3°F (2°F hysteresis to prevent chatter).

**Constraints:**
- Master bedroom fan excluded (managed by Night Mode automation)
- Does not override `hvac_manual_override`
- Does not fight active AC or heat cycles — if HVAC is actively conditioning, equalization fans run alongside (complementary, not competing)

Automation: `hvac_equalization`

---

## Window Logic (Derived — No Sensors)

**`binary_sensor.windows_assumed_open`** = true when ALL of:
- Season = Summer (May–Sep)
- Outside temp ≤ 70°F
- Wind speed < 10 mph
- No active precipitation (`weather.home`)

When true:
- Suppress AC entirely
- Run upstairs fans at 25–33% to assist airflow
- If AC was already running → turn off, set thermostat to fan-only
- Takes priority over passive→active escalation path

When conditions flip: resume normal cooling logic automatically.

---

## Shoulder Month (April)

- No heat unless downstairs < 55°F or office < 50°F (emergency only)
- No AC unless office > 78°F (emergency only)
- Fans + window logic available for passive cooling

---

## Occupancy & Setbacks

### Unoccupied Setback (8-hour no-motion)
- Trigger: no motion in **both** upstairs AND downstairs zones for 8 consecutive hours
- "No motion" = no one home, including dogs (presence sensors will catch them)
- AC setback → 76°F
- Heat setback → 62°F
- Restore immediately on any motion

### Night Mode (Winter only — Oct–Mar)
- `input_boolean.master_suite_sleep_posture` ON → heat setback to 62°F
- 6am → restore heat to 68°F
- No effect on cooling

### Zone Occupancy Sensors

**Upstairs:**
- `binary_sensor.calebs_office_occupancy`
- `binary_sensor.calebs_office_presence_sensor`
- `binary_sensor.tias_office_presence_motion`
- `binary_sensor.presence_sensor_fp2_6685_presence_sensor_1` (Master bedroom)
- `binary_sensor.master_bathroom_occupancy`

**Downstairs:**
- `binary_sensor.presence_sensor_fp2_9699_presence_sensor_1` (Living Room — All Areas)
- `binary_sensor.presence_sensor_fp2_0d3d_presence_sensor_1` (Family Room — All Areas)
- `binary_sensor.presence_sensor_fp2_a5e5_presence_sensor_1` (Kitchen — All Areas)
- `binary_sensor.stairwell_motion_sensor_motion` (Stairwell)

Group strategy: `binary_sensor.upstairs_occupied` and `binary_sensor.downstairs_occupied` as OR groups. Unoccupied = BOTH groups OFF for 8 hrs.

---

## Automation Structure

All under group tag `HVAC`, deployed via API POST to `/api/config/automation/config/<id>` then reload.

**Helpers to create:**
- `input_select.hvac_season` — winter / summer / shoulder (manual override point)
- `input_boolean.hvac_managed_cooling`
- `input_boolean.hvac_managed_heating`
- `input_boolean.hvac_manual_override`
- `binary_sensor.upstairs_occupied` — OR group of upstairs presence sensors
- `binary_sensor.downstairs_occupied` — OR group of downstairs presence sensors
- `binary_sensor.windows_assumed_open` — template sensor from weather

**Automations:**
1. `hvac_season_transition` — fires 1st of May/Oct/Apr; sets input_select, mode, setpoint, clears flags
2. `hvac_sensor_failsafe` — office sensor unavailable → freeze automation + notify
3. `hvac_cooling_passive` — fan logic in warm zone (72–74°F)
4. `hvac_cooling_escalate` — fan-to-AC escalation after 30 min (or immediately with solar)
5. `hvac_cooling_emergency` — immediate AC at ≥ 78°F
6. `hvac_heating_normal` — standard heat triggers
7. `hvac_equalization` — upstairs/downstairs delta ≥ 5°F → fans to equalize (year-round)
8. `hvac_setback_unoccupied` — 8-hour no-motion → AC 76°F / heat 62°F
9. `hvac_setback_night` — night mode → heat 62°F (winter only)
10. `hvac_morning_restore` — 6am → restore 68°F
11. `hvac_living_room_fan_comfort` — living room occupied > 5 min → turn off fan, keep off while occupied

---

## Sensor Failsafe

The office hygrometer (`sensor.caleb_s_office_hygrometer_temperature`) is the sole reliable upstairs sensor. Master bedroom sensor is unreliable (SwitchBot Bluetooth gateway — unstable values). No offset-based fallback — guessing is riskier than pausing.

When office sensor goes `unavailable`:
- Freeze all HVAC automation (no setpoint changes)
- Hold thermostat in its current state
- Send notification: "HVAC automation paused — office sensor unavailable"
- Resume automatically when sensor recovers

Automation: `hvac_sensor_failsafe`

---

## Season Transition

`hvac_season_transition` fires on the 1st of each boundary month (May, Oct, and Apr):

1. Set `input_select.hvac_season` to new value
2. Set thermostat mode explicitly (heat ↔ cool ↔ fan_only)
3. Reset setpoint to 68°F
4. Clear `input_boolean.hvac_managed_cooling`, `hvac_managed_heating`, `hvac_manual_override`
5. Send notification: "Season changed to [X] — [mode] active"

Manual season override: change `input_select.hvac_season` directly from the dashboard. All automations read from the select, so the change takes effect immediately.

---

## Manual Override

`input_boolean.hvac_manual_override` — set automatically when the thermostat setpoint or mode changes via a source other than this automation (i.e., a human touched it).

- When ON: all HVAC automations back off entirely
- Does not auto-expire — user clears it manually (or via dashboard button)
- Consider: add a "Resume automation" button to the dashboard that clears the flag

---

## Humidifier

Whole-house humidifier runs during heat cycles only — not independently controllable. Read-only integration:
- `sensor.caleb_s_office_hygrometer_humidity` informs summer cooling threshold (> 55% humidity → lower fan trigger from 72°F to 70°F)
- No action taken on the humidifier itself in this automation

---

## Master Bathroom (Phase 2 — Future)

Electric in-floor radiant heat under tile. Currently schedule-based. Not in scope for Phase 1.

**Future behavior-based design:**
- Occupied (`binary_sensor.master_bathroom_occupancy` ON) → warm to 72°F
- Unoccupied → setback to 60°F or off
- Tile holds heat well — doesn't need to run constantly
- Keep fully independent from main HVAC automation

---

## Dashboard

Suggested layout for a single Lovelace card (or section):

```
HVAC Status
────────────────────────────────────────
Season: [Summer ▼]   Mode: Passive Cooling

Upstairs (Office):  74.2°F  ↑ rising
Downstairs:         71.0°F
Outside:            68°F  💨 7 mph  ☀️

Windows assumed open: YES
Thermostat: fan_only   Setpoint: —

Upstairs fans: ON (50%)
Air handler fan: ON

Occupied: YES    Override: OFF
Solar now: 3.2 kW
────────────────────────────────────────
[Resume Automation]  (clears hvac_manual_override)
```

Key entities to expose:
- `input_select.hvac_season` (editable — for manual season override)
- Both temp sensors + trend
- `weather.home` conditions (temp, wind, precip)
- `binary_sensor.windows_assumed_open`
- Thermostat mode + setpoint
- Fan states (upstairs + air handler)
- `input_boolean.hvac_manual_override` + clear button
- `sensor.power_production_now`

---

## Fan Comfort Overrides

### Living Room Fan
`fan.living_room_ceiling_fan` must **never run** when the living room is occupied (TV watching, couch use — fan on people = grounds for divorce).

- If living room presence detected for > 5 minutes → turn fan off, keep off
- HVAC automation must not turn this fan on while living room is occupied
- 5-minute threshold avoids false triggers from someone walking through

Implementation: dedicated automation `hvac_living_room_fan_comfort` that watches living room presence sensors and turns fan off when occupied > 5 min. Takes priority over any equalization or cooling logic that would otherwise turn it on.

Presence sensors for living room:
- `binary_sensor.presence_sensor_fp2_9699_presence_sensor_5` (Living Room Presence)
- `binary_sensor.presence_sensor_fp2_a5e5_presence_sensor_4` (Living Room Presence)

Fan may run freely when living room is unoccupied.

### Master Bedroom Fan
`fan.master_ceiling_fan` — **fully excluded** from all HVAC automation. Managed only by the existing Night Mode automation. Do not touch under any circumstances.

---

## Open Questions

None outstanding.

---

## Decisions Log

| Decision | Answer |
|---|---|
| Whole-house fan | Thermostat FAN mode on `climate.downstairs_thermostat` |
| Window logic | Inferred: outside ≤ 70°F + wind < 10 mph + summer → assumed open |
| Wind threshold | 10 mph |
| "Hot" threshold | 74°F |
| Office thermostat | No thermostat — temp sensor `sensor.caleb_s_office_hygrometer_temperature` gates decisions |
| Unoccupied setback timer | 8 hours no motion |
| Unoccupied setbacks | AC → 76°F, heat → 62°F |
| Night mode scope | Winter only (Oct–Mar); heat 62°F until 6am |
| Floor equalization trigger | ≥ 5°F delta between floors; fans off when delta < 3°F |
| Sensor failsafe | Office sensor unavailable → freeze automation + notify |
| Season state | `input_select.hvac_season` — manually overridable from dashboard |
| Solar fast-track | `sensor.power_production_now` > 2 kW, 10am–3pm → skip 30-min passive wait |
| Humidity adjustment | Office humidity > 55% → lower fan trigger from 72°F to 70°F |
| Master bathroom | Phase 2 only — behavior-based electric in-floor, separate from main automation |
| Living room fan | Never run when occupied > 5 min; master bedroom fan fully excluded from automation |
| Family room fan | Included in equalization and cooling — primary air mixer between floors, no comfort restrictions |
