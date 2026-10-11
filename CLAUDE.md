# Home Assistant - Claude Code Context

## Connection
- Internal URL: http://ha.iot.scansenconsulting.com:8123
- External URL: https://homeassistant.scansenconsulting.com
- API token: $HA_TOKEN (loaded from ~/.secrets)
- MCP server: http://ha.iot.scansenconsulting.com:8123/mcp_server/sse

## API Usage
- Get all states: `curl -s http://ha.iot.scansenconsulting.com:8123/api/states -H "Authorization: Bearer $HA_TOKEN"`
- Get single entity: `curl -s http://ha.iot.scansenconsulting.com:8123/api/states/<entity_id> -H "Authorization: Bearer $HA_TOKEN"`
- Call service: `curl -s -X POST http://ha.iot.scansenconsulting.com:8123/api/services/<domain>/<service> -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d '{"entity_id": "<entity_id>"}'`
- Get automation: `curl -s http://ha.iot.scansenconsulting.com:8123/api/config/automation/config/<id> -H "Authorization: Bearer $HA_TOKEN"`
- Create/update automation: `curl -s -X POST http://ha.iot.scansenconsulting.com:8123/api/config/automation/config/<id> -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d @file.json`
- Reload automations: `curl -s -X POST http://ha.iot.scansenconsulting.com:8123/api/services/automation/reload -H "Authorization: Bearer $HA_TOKEN"`

## Local Files
- germination_watering_program.json — germination watering automation (ID: germination_watering_program)
- summer_watering_program.json — summer watering automation (ID: summer_watering_program)
- mode_a_exit_al_sleep_mode.json — Mode A exit AL sleep mode automation (ID: 1771230477164)
- garage_fan_door_ventilation.json — door ventilation automation (ID: garage_fan_door_ventilation)
- automations/other/front_porch_ambiance_cans_string.json — Front Porch ambiance automation (ID: front_porch_ambiance_cans_string)
- automations/other/security_lights_perimeter_loiter_boost.json — Perimeter loiter security automation (ID: security_lights_perimeter_loiter_boost)
- All files in this directory are project context for Claude

## Working Patterns
- For analysis/review: export to local JSON files first, then analyze
- For real-time control: use MCP or direct API calls
- Always source ~/.secrets before API calls
- Automation JSON files use the format exported by GET /api/config/automation/config/<id>; POST back to same endpoint then reload
- Lovelace named dashboard config (e.g. `dashboard-hvac`) is NOT accessible via REST API — use websocket: `{"type": "lovelace/config", "url_path": "dashboard-hvac"}` to read, `{"type": "lovelace/config/save", ...}` to write. See Python websockets pattern used in this project.

## Audio Zone System

**Dynamic Central Audio (DCA) v0.5.2** — custom HACS integration. Fully replaces the old automation-based zone follow, volume readback/authority, ATV exclusion, and HTD cover stack. Do not re-enable old automations.

### Party Mode (v0.5.0+, redesigned from the original v0.4.x AirPlay 2 approach)
- **Not AirPlay 2 grouping** — that approach (`pyatv`/`pyatv_bridge.py`) was tried in v0.4.0–0.4.4 and abandoned: it requires MRP protocol credentials, and none of this household's paired Apple TVs have them (confirmed directly against live `core.config_entries` — only AirPlay/Companion/RAOP creds exist), and HA's `apple_tv` integration's reconfigure flow offers no way to add MRP. Don't re-attempt AirPlay grouping without first re-pairing the Apple TVs with MRP included (may not even be offered anymore — check before spending time on it).
- **What it actually does:** a plain flag that suspends a zone's ATV-exclusion gate, so central audio keeps routing to that zone's HTD amp even while its local ATV plays — instead of the local ATV excluding the zone as before. Central and the local ATV play **independently and unsynced** (no shared clock, no AirPlay group) — that's an accepted limitation, not a bug.
- System-level: `switch.dynamic_central_audio_central_audio_party_mode` (suspends every zone's exclusion; auto-trigger app-allowlisted via `party_mode_trigger_apps`, default AirPlay/Music, configured in the system's options flow). Zone-level: `switch.dynamic_central_audio_<zone>_party_mode` (suspends just that zone; manual toggle only, no config).
- Garage is amp-only with an `amp_switch` (`switch.garage_amp`) — its ATV exclusion is intentionally **not** suspended by Party Mode (would drive the same speakers from two amps); unaffected either way.
- Party Mode clears automatically when System Active or a zone's Follow Me turns off, and always starts off after an HA restart (not restored). See `PARTY_MODE.md` in the repo for full design/history.
- Requires a full HA restart after HACS updates this integration — new Python modules and `manifest.json` requirements (`pyatv`) don't take effect on a config reload alone.

### Zones
| Zone | Status sensor | Follow-Me switch | Volume offset |
|------|--------------|-----------------|---------------|
| Main Floor | `sensor.dynamic_central_audio_main_floor_status` | `switch.dynamic_central_audio_main_floor_follow_me` | `number.dynamic_central_audio_main_floor_volume_offset` |
| Family Room / Tia's Office | `sensor.dynamic_central_audio_family_room_and_tias_office_status` | `switch.dynamic_central_audio_family_room_and_tias_office_follow_me` | `number.dynamic_central_audio_family_room_and_tias_office_volume_offset` |
| Master Bed & Bath | `sensor.dynamic_central_audio_master_bed_and_bath_status` | `switch.dynamic_central_audio_master_bed_and_bath_follow_me` | `number.dynamic_central_audio_master_bed_and_bath_volume_offset` |
| Gazebo & Yard | `sensor.dynamic_central_audio_gazebo_and_yard_status` | `switch.dynamic_central_audio_gazebo_and_yard_follow_me` | `number.dynamic_central_audio_gazebo_and_yard_volume_offset` |
| Garage | `sensor.dynamic_central_audio_garage_status` | `switch.dynamic_central_audio_garage_follow_me` | `number.dynamic_central_audio_garage_volume_offset` |
| Front Porch | `sensor.dynamic_central_audio_front_porch_status` | `switch.dynamic_central_audio_front_porch_follow_me` | `number.dynamic_central_audio_front_porch_volume_offset` |

### Key entities
- System status: `sensor.dynamic_central_audio_central_audio_status`
- Active switch: `switch.dynamic_central_audio_central_audio_active`
- AirPlay follow-me: `switch.dynamic_central_audio_central_audio_airplay_central_follow_me`
- Apple TV follow-me: `switch.dynamic_central_audio_central_audio_apple_tv_living_room_follow_me`

### Sources
- AirPlay: `media_player.central_airplay` — always active (no app filter)
- Apple TV: `media_player.living_room_apple_tv` — app filter: `com.apple.TVMusic` only (music triggers follow-me; video does not)
- Volume per zone is set by DCA directly via `media_player.volume_set` using `base_volume + volume_offset` — no helper entities involved

### Garage zone (amp-only)
- No media player — DCA manages `switch.garage_amp` (amp) directly via ATV exclusion
- ATV exclusion: `media_player.garage_apple_tv` → amp on/off; restore: `all_stopped` + 30s delay
- No `bypass_app_ids` — garage ATV always drives local amp regardless of app
- Automation `garage_atv_stop_on_amp_off`: amp turns off → ATV stops (no conditions)

### Camera Sensors (UniFi Protect + Reolink)
Most yard/perimeter cameras are UniFi Protect and expose both a motion sensor and an AI person-detection sensor. Reolink cameras (Front Door, Back Field) also expose person detection. UniFi Protect does NOT expose per-camera motion zones as separate entities — zone granularity lives only inside the Protect app. Plain `Yard` (as opposed to Yard East/West) and the Gazebo/Slider, Lexus, and Pony cameras do NOT have person-detection — motion only.

| Area | Platform | Motion | Person detected |
|------|----------|--------|----------------|
| Yard East | UniFi | `binary_sensor.yard_east_motion` | `binary_sensor.yard_east_person_detected` |
| Yard West | UniFi | `binary_sensor.yard_west_motion` | `binary_sensor.yard_west_person_detected` |
| Yard (plain) | UniFi | `binary_sensor.yard_motion` | — (no person detection) |
| Yard Middle / Gazebo-Slider | UniFi | `binary_sensor.yard_gazebo_slider_motion` | `binary_sensor.yard_gazebo_slider_person_detected` |
| Driveway | UniFi | `binary_sensor.driveway_motion` | `binary_sensor.driveway_person_detected` |
| Front Door | Reolink | `binary_sensor.front_door_motion_2` | `binary_sensor.front_door_person_detected` |
| Back Field | Reolink | `binary_sensor.back_field_motion` | `binary_sensor.back_field_person` |
| Lexus / Pony (garage entry) | — | `binary_sensor.lexus_motion` / `binary_sensor.pony_motion` | — (no person detection) |

- `binary_sensor.yard_motion` — whole-yard motion group (OR across cameras, not person-specific)
- East/West sensors face alleys — can pick up street traffic; use motion (not person) for irrigation deferrals
- The five person-detection sensors (Yard East, Yard West, Driveway, Front Door, Back Field) feed `automation.security_lights_perimeter_loiter_boost` — see Front Porch Lighting below

## Garage
- Presence sensor (mmWave): `binary_sensor.garage_presence_presence` (+ `_moving_target`, `_still_target`)
- Occupied group: `binary_sensor.garage_occupied` — OR of mmWave presence + pony/lexus/fridge camera motion
- Fan switch: `switch.garage_fans`
- Apple TV: `media_player.garage_apple_tv`
- Amp: `switch.garage_amp` (powers ATV speakers only — HTD zone has its own amp)
- Temperature/humidity: `sensor.garage_hygrometer_temperature` / `sensor.garage_hygrometer_humidity`
- Fan cooling automation: on after 2min presence + outdoor temp >80°F (`weather.forecast_home` temperature attribute); off after 15min mmWave empty
- Fan door ventilation automation (`garage_fan_door_ventilation`): on when both bay doors open 5+ min + garage temp >60°F, 6am–9am only; off when both doors closed and garage empty
- Automation `garage_atv_stop_on_amp_off`: amp (`switch.garage_amp`) turns off → immediately stops garage ATV (no conditions)
- DCA handles amp on/off via zone occupancy + ATV exclusion; the automation is the cleanup link
- Automations: `garage_fan_cooling_on`, `garage_fan_cooling_off`, `garage_atv_stop_on_amp_off`, `garage_fan_door_ventilation`

## Fan Lock System
Built natively into the Adaptive HVAC integration (v0.3.6+). Each zone gets a `switch.adaptive_hvac_<zone>_fan_locked` entity. No external automations or helpers required.

### How it works
- User turns fan ON or adjusts speed → lock switch turns ON, speed stored in coordinator memory
- User turns fan OFF → lock switch stays ON (speed=0) — integration won't turn it back on
- **Midnight** → all zone fan locks clear automatically, normal control resumes
- Manual release: toggle `switch.adaptive_hvac_<zone>_fan_locked` OFF at any time

### Fan lock switches
| Zone | Lock switch |
|---|---|
| Caleb's Office | `switch.adaptive_hvac_calebs_office_fan_locked` |
| Tia's Office | `switch.adaptive_hvac_tias_office_fan_locked` |
| Master Bedroom | `switch.adaptive_hvac_master_bedroom_fan_locked` |
| Living Room | `switch.adaptive_hvac_living_room_fan_locked` |

### What sets the lock
Any fan change except the integration's own commands (tagged with an integration-owned `Context`, v0.4.2) and automation-originated calls (`parent_id` set, no `user_id`). Physical switch presses and HA UI/app/HomeKit changes all lock.

**Pre-v0.4.2 bug:** the integration's own fan dispatches had no `parent_id`, so it locked its own fans — an integration-started fan showed "Fan locked by user" and was never turned back off until midnight. If a lock turns on in the same second as an integration fan command, that's this bug regressing.

## Master Bathroom Lights

- Dimmer: `light.master_bath_dimmer` — physical switch
- LEDs: `light.master_bath_underlights` — 0-10V strip
- Always in sync via bidirectional pair: **Dimmer drives 0-10V** (ID: 1767225558095) + **0-10V reflects to dimmer** (ID: 1767248157121). Physical switch use propagates unconditionally — no block conditions on the sync pair.
- Occupancy automation: **Master Bath - Underlights (Occupancy + Lux)** (ID: 1771288057410, `automations/other/master_bath_underlights_occupancy_lux.json`)
  - Turns on when occupied 2s + NOT both in bed + (sun down OR daytime lux < 300)
  - Lux threshold 300 chosen from sensor data: cloudy days peak ~130 lux; sunny afternoons run 400–800+ lux
  - Turns off after 2 min unoccupied
  - Block condition: `binary_sensor.master_bed_both_in_bed = on` — suppresses mmWave-triggered turn-on while both are asleep; either person out of bed lifts the block

## Front Porch Lighting (added 2026-07-11)

Two separate automations, deliberately kept apart — ambiance (cozy sitting) and security (perimeter loitering) are different concerns and were tangled together in earlier drafts before landing on this split.

### Ambiance: Front Cans + String Lights
`automation.front_porch_ambiance_cans_string` (`automations/other/front_porch_ambiance_cans_string.json`) — turns on `light.front_porch_cans` + the String Lights switch (`switch.front_porch_string_lights`) when Caleb/Tia are sitting on the stoop or in the porch chairs after dark. No time-of-day cutoff — if they're out there at 1am they still want the lights.
- Triggers: `binary_sensor.front_porch_stoop_presence` (template — actually just `binary_sensor.front_door_motion_2` + wind gate, **not** AI loiter-filtered, correcting an earlier wrong assumption) OR `binary_sensor.front_porch_presence_still_target` (mmWave/ESP32 radar, gate-based) → `on`, **held for 60s continuous** before firing (see "mmWave false positives" below for why), gated to after dusk (-15min).
- Off: only once **both** sensors have been `off` for 10 minutes — avoids killing the lights just because one sensor cleared while the other still shows occupied.
- The mmWave sensor family also exposes `_moving_target` and blanket `_presence` — deliberately NOT used here (too broad/close-range; see Perimeter Security below for why mmWave isn't used for property-line detection).
- **Do not wire this automation to `binary_sensor.front_porch_swings_occupied` / `front_porch_stoop_occupied`** (in `templates.yaml`) — those predate this work and were built for the DCA audio follow-me system, not lighting. They tolerate rapid flicker fine for audio zone routing but are NOT reliable occupancy signals for a visible light — confirmed `swings_occupied` flickers on/off every few seconds even with wind well under its 12mph gate. Don't repurpose shared-subsystem templates for a new consumer without checking who else depends on their exact behavior.

#### mmWave false positives (found + fixed 2026-07-11/12)
Engineering-mode diagnostics (`switch.front_porch_presence_engineering_mode`) exposed per-gate (g0-g8, 0.75m/gate) move/still energy + thresholds. With the porch empty, nearly every gate except g8 exceeded its threshold at some point over a 2-hour window; g2 (~1.5-2.25m) was chronically over. Chairs sit 8-15ft out (~gates 3-6), which overlaps the noisiest gates — so noise and signal share the same amplitude range and simple threshold-raising has a ceiling (noise saturates to the sensor's max reading, same as real presence would). Raised the worst-offending gate thresholds anyway (g2→95, g3→50, g4→50, g5→99, g6→99, g7→50 via their `number.front_porch_front_porch_presence_g*_still_threshold` entities) as a floor-level improvement, but the actual fix was moving the noise-filtering to the automation: require 60s continuous `on` before treating either sensor as real occupancy (of 567 `swings_occupied` on-spans sampled, only 56 exceeded 60s — most noise is brief).

### Perimeter Security: reactive per-zone lighting
`automation.security_lights_perimeter_loiter_boost` (`automations/other/security_lights_perimeter_loiter_boost.json`) — when a camera's AI person-detection fires for a given zone (see Camera Sensors table above) and it's dark out, turns on the real fixture(s) nearest that zone. Off ~10 min after **all** sensors feeding that fixture have cleared (mode: `queued`, since multiple zones can trigger close together and `single` mode would drop overlapping detections).

| Zone sensor | Fixture(s) turned on |
|---|---|
| `binary_sensor.front_door_person_detected` | `light.front_porch_cans` |
| `binary_sensor.back_field_person` | `light.back_field_floodlight` |
| `binary_sensor.driveway_person_detected` | Shed Exterior Outlet + `light.back_field_floodlight` |
| `binary_sensor.yard_west_person_detected` | Shed Exterior Outlet |
| `binary_sensor.yard_east_person_detected` | `light.gazebo_lights` + Sliding Glass Doors switch + `light.front_porch_cans` |

mmWave (`front_porch_front_porch_presence_*`) is porch-only/close-range and was explicitly ruled out for perimeter/property-line detection ("mmWave is too close — that means they're in my property"); only camera AI person-detection feeds this automation.

### Label semantics (restructured 2026-07-11)
- **`security_lights`** label — now **only** `light.front_door_entry_lights_outlet`. Unconditional dusk(-30min)/dawn(+30min) schedule via `automation.security_lights_on`/`security_lights_off` — stays on all night regardless of activity, by design (aesthetic/entry visibility, not motion-reactive).
- **`dynamic_security_lighting`** label — Sliding Glass Doors switch, `light.back_field_floodlight`, `light.gazebo_lights`, and the Shed Exterior Outlet (was already tagged here before this work, previously unused by any automation). These were moved OFF the fixed dusk/dawn schedule and are now purely reactive via `security_lights_perimeter_loiter_boost`, to save energy vs. running all night.
- Do not add entities back to `security_lights` expecting reactive behavior — that label is schedule-only. Reactive/motion-triggered fixtures belong in `dynamic_security_lighting`.

### Known residual risk
The 60s hold cuts most false triggers but isn't perfect — 56 of 567 sampled noise spans exceeded 60s, some as long as ~9.5 minutes (likely sustained wind or a stubborn reflective object, not a person). Watch `logbook` for the ambiance automation; if cans/string still trigger with nobody present, consider raising the hold further (90-120s) at the cost of slower response when someone actually sits down.

### STATUS as of 2026-07-12 — investigation paused, not resolved
The 60s hold (above) is deployed and live, but the underlying cause of the mmWave false positives is still open. Caleb's physical explanation: **the porch seats are swings, and they physically sway in wind — that motion looks like presence to the radar.** Worth investigating further:
- Checked wind at the two known false-positive windows (2026-07-11 ~05:35 UTC, 2026-07-12 ~12:33-13:19 UTC): `weather.home` wind_speed was only 1-5mph both times — well under any reasonable "windy" gate, and too low to explain sway by itself. Either the swings are sensitive enough to move in near-calm air, or `weather.home` (forecast-sourced, not a local anemometer) is too coarse/infrequent to catch the actual gust.
- Live-watched gate 2 during an active false-positive: `g2_still_energy` swung 22-90 (well past its still threshold) while `g2_move_energy` stayed flat at 2-8 (well under its move threshold of 40) the whole time. If the swing were visibly/mechanically swaying, expected some correlated rise in move energy — didn't see it. Could mean the sway is too slow/low-velocity for this radar's "moving" classification to catch, or the noise source isn't swing motion at all.
- **Next step (not yet done):** live ground-truth test — have someone actually sit in the swing for 30-60s while watching gate 2 still/move energy live, to get a real "occupied" signature to compare against the noise floor characterized above. This is the highest-value next action; without it we're still guessing between "duration hold is enough," "need a wind gate," or "swing itself needs a physical damper / sensor needs repositioning."
- Gate threshold changes from the engineering-mode tuning pass (g2→95, g3→50, g4→50, g5→99, g6→99, g7→50) are still in place and didn't get reverted — they affect the device's own onboard `still_target`/`presence` computation, which the automation no longer directly gates on (now uses the 60s-hold wrapper instead), so leaving them is harmless.

## Master Bedroom Lights

- Lights: `light.master_bedroom_manual_lights`, `light.master_bedroom_nightstands`
- Under-bed: `light.master_bedroom_under_bed_light` — night-motion only (see Under Bed Night Motion below)
- **Occupancy automation** (ID: 1768187945725, `automations/other/master_bedroom_occupancy_lights.json`):
  - ON when occupied + sleep posture off + no one in bed + (sun down OR bathroom lux < 300)
  - Uses `sensor.master_bathroom_illuminance` as daytime lux gate — bedroom FP2 light sensor caps at 9 lx and is unusable for daylight detection
  - OFF after 5 min unoccupied
- **Under Bed Night Motion** (ID: 1769916429783): fires only when sleep posture ON; turns on when occupied + not both in bed; off after 30s unoccupied

## Master Suite Sleep System

### Canonical state
`input_boolean.master_suite_sleep_posture` is the single source of truth. AL sleep mode switches for bedroom/bathroom/closet are always derived from it via `mode_a_apply_master_suite_sleep_posture_to_mbr`. Never toggle the AL switches directly for sleep posture — go through the posture flag.

### Automation flow (updated 2026-07-13)
- **Arm** (`mode_a_arm_master_suite_sleep_posture`) — posture OFF, then either path:
  - `master_bed_anyone_in_bed` ON + `master_bedroom_occupied` OFF for **15s+** (debounce added 2026-07-13), settling into the original 2-min "suite quiet" trigger — solo-sleeper path, deliberately the slower/debounced one (filters false positives like folding laundry on the bed)
  - `master_bedroom_bed_presence_bed_occupied_both` ON for **45s** (bypass added 2026-07-06 at 5min, retimed 2026-07-13) — arms fast once both pressure pads confirm occupancy; two people settling in together is decisive and shouldn't wait as long as the solo path
  - → sets posture ON
- **Apply** (`mode_a_apply_master_suite_sleep_posture_to_mbr`) — fires on any posture state change → bedroom + closet AL sleep mode switches sync immediately, both directions. **Bathroom's ON transition is now conditional** (2026-07-13): only flips on immediately if `binary_sensor.master_bathroom_presence` reads clear at arm time; if occupied, it's left off and handled by the new Apply Deferred Bathroom automation below. Bathroom's OFF transition (waking up) still happens immediately here with the rest.
- **Apply Deferred Bathroom Sleep Mode** (`mode_a_apply_deferred_bathroom_sleep_mode`, new 2026-07-13) — if posture arms while the bathroom is occupied, this fires the next time `binary_sensor.master_bathroom_presence` clears (15s debounce) while posture is still on, turning the bathroom AL sleep-mode switch on then — implements "the lights dim when it's empty next" instead of dimming while still in use.
- **Disarm** (`mode_a_disarm_master_suite_sleep_posture`) — fires when `master_bed_anyone_in_bed` OFF for 5 min + `master_bedroom_occupied` OFF for **15s+** (debounce added 2026-07-13) + posture ON → sets posture OFF
- **Exit** (`mode_a_exit_al_sleep_mode_master_bedroom_and_closet`, ID: 1771230477164) — two paths:
  - Sunrise+30: directly turns off bathroom + closet AL sleep mode only (bedroom stays dimmed longer)
  - Bed empty 5 min: turns off `master_suite_sleep_posture` → Apply cascades to all rooms; this ensures Arm can re-engage when they return to bed

### Design rationale: "occupied" and "in bed" must stay independent signals (2026-07-13)
Considered folding bed presence into `master_bedroom_occupied` (i.e. treating "in bed" as a form of "occupied") — rejected. The two signals answer different questions on purpose: `master_bedroom_occupied` (motion/presence) = "is anyone up and moving," `master_bed_anyone_in_bed`/`both_in_bed` (pressure pads) = "is a body on the mattress." Arm's solo path depends on their independence — it requires `anyone_in_bed == on` AND `master_bedroom_occupied == off` (someone's in bed AND nobody's moving = actually settling to sleep). If bed presence counted toward occupied, that condition would be self-contradicting (occupied could never read off while anyone's in bed), permanently disabling the solo arm path — only the both-in-bed bypass could ever fire, meaning one person going to bed alone (partner not home yet, staggered bedtimes) would never get sleep posture through the normal mechanism. It would also risk the under-bed light false-triggering for someone lying in bed alone (occupied forced on by their own bed presence, both_in_bed still off). Keep them separate.

### Re-arm on return (dog-puke pattern)
Both out of bed 5+ min → Exit sets posture OFF → posture is now OFF → they return to bed → Arm re-fires once `master_bedroom_occupied` clears → posture ON → Apply restores all sleep modes.

### Arm bypass rationale (2026-07-06, retimed 2026-07-13)
`master_bedroom_occupied` (group: closet motion + master bathroom occupancy + FP2 mmWave presence) intermittently flaps once someone is lying still in bed — the FP2 sensor in particular can cycle on/off every ~1s, which kept resetting the original path's 2-min "OFF" timer and prevented Arm from ever firing on nights it happened. The `bed_occupied_both` bypass sidesteps this since it's pressure-based and unaffected by that flapping — it only bounces during brief/transient bed contact (e.g. folding laundry on the bed). Originally held 5min to clear that transient case; **retimed to 45s on 2026-07-13** since both-in-bed is meant to be the fast path relative to the (now debounced) solo path, not the same order of magnitude. Pre-change config backed up at `/mnt/nas/ai-workspace/documentation/homeassistant/automation_backups/mode_a_arm_master_suite_sleep_posture_20260706_024229.json` (2026-07-06 change) and `/mnt/nas/ai-workspace/homeassistant/backups/pre_sleep_mode_rebuild_20260713T032420Z/` (2026-07-13 change, covers Arm/Disarm/Apply/Under-Bed/Closet-Motion + the group helper).

### `master_bedroom_occupied` group helper — fixed manually 2026-07-13
Bathroom member repointed `binary_sensor.master_bath_occupancy` → `binary_sensor.master_bathroom_presence` (root cause of the 2026-07-12 false-arm incident; the Matter sensor chatters continuously per live history, presence sensor holds state cleanly). Done via Settings > Devices & Services > Helpers, since group helper config entries have no REST write endpoint (`GET /api/config/config_entries/entry/<id>` returns 405 — options-flow/frontend only).

**Second latent bug found and fixed in the same edit**: the bedroom-motion member had been `binary_sensor.family_room_fp2_master_bedroom` — docs-labeled "Master Bedroom" but actually a zone of the `fp2_0d3d` device, which is the **family room/downstairs** FP2 sensor (other zones: Family Room, Laundry Room, Stairs, Tia's Office, Walkway). The suite-occupied signal had been reading a downstairs zone this whole time, not the bedroom's own sensor. Now uses all three zones of `fp2_6685`, the actual master-bedroom-dedicated FP2 device: `presence_sensor_fp2_6685_presence_sensor_{1,2,3}` ("Master Bed Presence All" / "Master Bed Presence" / "Master Bedroom Presence Walkways").

Group logic confirmed OR (`"all": false`, checked directly against `/homeassistant/.storage/core.config_entries` via SSH 2026-07-14) — not AND, occupancy detection intact.

**Membership has moved twice** — as of 2026-07-14 it's `binary_sensor.master_closet_motion`, `binary_sensor.presence_sensor_fp2_6685_presence_sensor_{2,3}`, `binary_sensor.master_bathroom_presence`, `binary_sensor.family_room_fp2_master_bedroom`. Note `fp2_6685_presence_sensor_1` ("Master Bed Presence All") has been dropped and `fp2_0d3d_presence_sensor_5` (the downstairs/family-room-device zone flagged above as mislabeled) is back in — unclear if intentional. Re-verify membership before trusting this note; it drifts.

### Bed presence sensor
Device: `device_tracker.bed_presence_2c0bd4` (ElevatedSens, IP 192.168.255.17, VLAN 500), response speed: Slow
- Left side (Tia): `sensor.master_bedroom_bed_tia_side_pressure` — occupied: 45%, trigger: 43.75%, unoccupied: 40%
- Right side (Caleb): `sensor.master_bedroom_bed_caleb_side_pressure` — occupied: 87%, trigger: 81.5%, **unoccupied: 50%** (lowered from 65% 2026-05-16 to prevent false negatives from position shifts)
- Calibration buttons: `button.master_bedroom_bed_{tia,caleb}_side_calibrate_{occupied,unoccupied}`; thresholds `number.master_bedroom_bed_{tia,caleb}_side_{trigger,occupied,unoccupied}_pressure` (left = Tia, right = Caleb)
- `binary_sensor.master_bed_{caleb,tia,anyone,both}_in_bed` — named wrappers; `master_bedroom_bed_presence_bed_occupied_{left,right,either,both}` — raw device sensors

### Revert instructions (2026-07-13 rebuild)
Pre-rebuild config for every automation touched (Arm/Disarm/Apply/Exit, Under Bed Night Motion, Occupancy Lights Day, Master Closet Motion Light) plus the `master_bedroom_occupied` group helper is saved at `/mnt/nas/ai-workspace/homeassistant/backups/pre_sleep_mode_rebuild_20260713T032420Z/` (see that folder's `README.md` for exact curl/UI steps). Native HA `backup.create_automatic` returned HTTP 500 on this instance (backup agent/location likely not configured — separate infra issue, not fixed this session); the timestamped folder is the working fallback restore point. Full incident writeup: `/home/cscansen/.claude/plans/diagnostics-time-look-at-goofy-unicorn.md`.

## Irrigation System

**Adaptive Irrigation v0.6.9+** — custom HACS integration for data-driven watering decisions.

**Quick reference:**
- 5 zones (Yard East, Middle, West; Front; Drip) with soil moisture sensing
- Per-zone thresholds, max duration, flow rate (all configurable via UI)
- Seedling mode auto-expires after 30 days
- Daily watering window (5:30 AM – 10:00 AM default) + daily gallon budget
- Services: `adaptive_irrigation.water_zone`, `adaptive_irrigation.evaluate_now`

**For complete configuration and troubleshooting:** See `docs/adaptive_irrigation.md`

## HVAC System

**Adaptive HVAC v0.4.2** — custom HACS integration (`custom_components/adaptive_hvac/`). Old 13-automation YAML system is fully replaced. Do not re-enable old automations. Full docs: `custom_components/adaptive_hvac/README.md` + `CHANGELOG.md`.

### Architecture
- **System entry** — owns the thermostat, reads weather, dispatches heat/cool/off
- **Zone entries** — one per room; each reads temp sensors, controls local fans, emits thermal requests
- **Season** — calendar-based only (Oct–Apr = winter, May–Sept = summer); override via `select.adaptive_hvac_season_override`
- **Night mode** (added 2026-07-26) — separate `number.adaptive_hvac_night_ac_setpoint`/`night_heat_setpoint` used instead of the day setpoints. Activates via `switch.adaptive_hvac_night_mode` (manual), an optional configured source entity (input_boolean/binary_sensor), or the `night_start_hour`/`night_end_hour` time window (default 10pm–6am, not yet customized on this install). `sensor.adaptive_hvac_status` exposes `night_mode_active`.

### Decision logic
- Zone: if `temp > zone_target_temp` → fan on (occupied only) + request cool; if `temp ≤ zone_target_temp` → fan off
- System: cooling allowed if `outdoor ≥ cool_exterior_threshold` OR any zone is 5°F+ above its target; heat allowed if `outdoor ≤ heat_exterior_threshold`
- System: cooling **and heating** blocked if any zone's window sensor is open (actual contact sensor); emergencies bypass this. Heat was exempt until v0.4.0 — the gate was wrapped in `if season == "summer"`, so the furnace fought open windows all winter
- Relative gates (both seasons): AC withheld when outdoor < the *coolest* requesting zone's target; heat withheld when outdoor > the *warmest* requesting zone's target. `min()` vs `max()` is deliberate — each protects the zone that's still unsatisfied
- **The winter relative gate is currently inert on this install.** `heat_exterior_threshold` (60°F) is checked first and sits below every zone target (68–70°F), so `outdoor ≤ 60` and `outdoor > 68` can never both hold. Raise `number.adaptive_hvac_heat_exterior_threshold` above the warmest target to enable it. Not a defect — configuration
- **AQI never unblocks the HVAC** (v0.4.0). Cooler outside still blocks AC whether the air is clean or smoky; bad air only changes `blocked_reason` from `open_windows_better` to `aqi_hold` and rewrites the message. Guarded by `test_relative_gate_still_blocks_ac_when_aqi_bad`
- **`binary_sensor.adaptive_hvac_windows_recommended` is an absolute 60–75°F band, independent of season and zone targets** — deliberately, because the calendar season model reads all of October as "winter" and a target-relative rule would refuse to suggest windows on a 62°F fall afternoon. Advisory only, never gates the thermostat. Guarded by `test_windows_recommended_in_october_shoulder_season`
- Dispatched AC/heat setpoint = `ac_setpoint − upstairs_demand_boost` (or `+ boost` for heat), **rounded to a whole degree** (v0.3.33+) — a fractional value used to get silently re-rounded by the thermostat itself, making the displayed setpoint diverge from the dashboard slider
- Setpoint sliders only push to the thermostat once a zone is actively calling for cool/heat — moving them while idle updates the stored target only, no visible effect until AC/heat next engages (not a bug, just non-obvious)
- Occupancy gates **local fans only** — thermostat decisions are never blocked by occupancy
- User fan changes claim that zone's fans until midnight (see Fan Lock System)
- User thermostat adjustments (faceplate/app) are adopted as the new seasonal setpoint and persisted to config entry options; reset on season change

### Zones (v0.3.33) — Garage removed 2026-07-26, see below
| Zone | Status sensor | Temp sensor | Auto switch | Fan lock switch |
|------|--------------|-------------|-------------|-----------------|
| Caleb's Office | `sensor.calebs_office_hvac_status` | `sensor.office_caleb_hygrometer_temperature` | `switch.adaptive_hvac_calebs_office_auto_2` | `switch.adaptive_hvac_calebs_office_fan_locked` |
| Tia's Office | `sensor.tias_office_hvac_status` | `sensor.office_tia_hygrometer_temperature` | `switch.adaptive_hvac_tias_office_auto` | `switch.adaptive_hvac_tias_office_fan_locked` |
| Master Bedroom | `sensor.master_bedroom_hvac_status` | `sensor.master_bedroom_hygrometer_temperature` | `switch.adaptive_hvac_master_bedroom_auto` | `switch.adaptive_hvac_master_bedroom_fan_locked` |
| Living Room | `sensor.living_room_hvac_status` | `sensor.downstairs_thermostat_temperature` | `switch.adaptive_hvac_living_room_auto` | `switch.adaptive_hvac_living_room_fan_locked` |

### Garage fan control — plain automation, not an HVAC zone
Removed from Adaptive HVAC entirely (2026-07-26) — it was `affects_thermostat: false` anyway, so this only changes fan control, not AC/heat behavior. Garage fans needed compound logic (door state OR sustained occupancy+heat) the integration's single-threshold-per-zone model doesn't fit; see README's "Zones with compound fan logic" section for the general pattern this is the worked example of.

- `automation.garage_fans_door_occupancy_cooling` (`automations/garage/garage_fans_door_occupancy_cooling.json`) — fans on when both `cover.garage_door_lexus` + `cover.garage_door_pony` are open, OR `binary_sensor.garage_occupied` has been on 10+ min AND `sensor.garage_hygrometer_temperature` ≥ `input_number.garage_fan_hot_threshold` (75°F default, dashboard-adjustable slider). Off otherwise. Controls `fan.garage_fans` (confirmed same physical device as `switch.garage_fans`, just presented as a fan entity).
- Replaced `garage_fan_door_ventilation` (deleted) — that one only ran 6am–9am, had no occupancy branch, and gated on a legacy `input_boolean.fan_user_claimed_garage` helper left over from before the integration got native fan lock (v0.3.6). It was still live and fighting the new automation over the same fans until found and removed.
- Garage temp/humidity (`sensor.garage_hygrometer_temperature`/`_humidity_2`) still shown on the separate `dashboard_temperatures` dashboard — unrelated to Adaptive HVAC, unaffected by the zone removal.

### Key entities
- Thermostat: `climate.downstairs_thermostat`
- System status: `sensor.adaptive_hvac_status` (state = status string, `reasoning`/`night_mode_active` attributes = full decision tree)
- Season: `sensor.adaptive_hvac_season`
- Mode: `sensor.adaptive_hvac_mode`
- Active switch: `switch.adaptive_hvac_active`
- Manual override: `switch.adaptive_hvac_manual_override`
- Cooling blocked: `binary_sensor.adaptive_hvac_cooling_blocked` (`reason`/`blocked_reason`/`status`/`aqi` attributes)
- Heating blocked: `binary_sensor.adaptive_hvac_heating_blocked` (winter mirror, added v0.4.0)
- Windows recommended: `binary_sensor.adaptive_hvac_windows_recommended` (advisory)
- Air quality: `sensor.adaptive_hvac_air_quality` ← `sensor.outdoor_aqi` (Open-Meteo REST sensor in `configuration.yaml`, keyless; also `sensor.outdoor_pm2_5` / `sensor.outdoor_pm10`)
- AQI/band sliders: `number.adaptive_hvac_aqi_threshold` (50), `_window_min_outdoor` (60), `_window_max_outdoor` (75), `_heat_exterior_threshold` (60)
- `blocked_reason` codes: summer `window_open` / `outdoor_cold` / `open_windows_better` / `aqi_hold`; winter `window_open_heat` / `outdoor_warm` / `open_windows_warm` / `aqi_hold_heat`. Surfaced only on whichever sensor is actually blocked
- Notifications: `hvac_cooling_blocked_notify` + `hvac_heating_blocked_notify` branch on `blocked_reason` via `choose:`; `hvac_windows_recommended_notify` (2h rate limit); `hvac_notification_action_handler` backs the "Run HVAC anyway" button
- Upstairs average: `sensor.upstairs_average_temperature` (Caleb + Tia + Master avg, in `templates.yaml`)

### Dashboard
`/dashboard-hvac` — system status + reasoning (now including Night Mode + Cooling Blocked lines in the markdown card), per-zone cards, zone temp glance, thermostat history, logbook, controls, setpoint sliders (incl. Night Mode card), force-evaluate button. Regenerate via `scripts/generate_dashboard.py` (see `DASHBOARD.md`); also mirrored on-host at `/config/scripts/generate_hvac_dashboard.py` for the in-dashboard "Rebuild Dashboard" button — **keep both copies in sync manually**, they drifted out of sync for over a month before being caught and re-synced 2026-07-26.

**Deploying dashboard changes (SSH or Raw Config Editor) requires a full HA restart to actually take effect** — firing `lovelace_updated` and refreshing the browser is not enough; HA appears to hold a server-side cached copy of the parsed dashboard that a raw storage-file overwrite doesn't invalidate. Confirmed by verifying the deployed file byte-for-byte correct while the Companion app still showed stale cards until an actual restart. This is unlike custom-component Python changes, which *also* need a restart (module caching) — so in practice, any adaptive_hvac change (code or dashboard) needs one.

### Testing
```bash
# Force immediate evaluation
source ~/.secrets && curl -s -X POST http://ha.iot.scansenconsulting.com:8123/api/services/adaptive_hvac/force_evaluate \
  -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d '{}'

# Read current decision + reasoning
curl -s http://ha.iot.scansenconsulting.com:8123/api/states/sensor.adaptive_hvac_status \
  -H "Authorization: Bearer $HA_TOKEN" | python3 -c "import json,sys; s=json.load(sys.stdin); print(s['state']); print(s['attributes'].get('reasoning'))"
```

### Known stale entities
`switch.adaptive_hvac_calebs_office_auto` (no `_2`) — orphaned registry entry, unavailable, safe to ignore. The `_2` variant is the live one.

## Notes
- Still learning HA — update this file as patterns emerge
- Automations created via API use string IDs (not UUIDs) — choose descriptive IDs
- Binary sensor groups created via UI (Helpers) cannot be updated via `group.set` API — must use HA UI or websocket options flow
- SSH to HA host (`hassio@192.168.255.247`): use `ssh -i ~/.ssh/infra hassio@192.168.255.247`; writes to `/config/` require `sudo`; `root` login denied
- File transfer to HA: SCP/SFTP not supported — use base64 encode/decode over SSH (`echo '<b64>' | base64 -d > /tmp/file`)
- `TODOS.md` in this directory tracks deferred work
