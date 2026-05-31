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
- All files in this directory are project context for Claude

## Working Patterns
- For analysis/review: export to local JSON files first, then analyze
- For real-time control: use MCP or direct API calls
- Always source ~/.secrets before API calls
- Automation JSON files use the format exported by GET /api/config/automation/config/<id>; POST back to same endpoint then reload
- Lovelace named dashboard config (e.g. `dashboard-hvac`) is NOT accessible via REST API — use websocket: `{"type": "lovelace/config", "url_path": "dashboard-hvac"}` to read, `{"type": "lovelace/config/save", ...}` to write. See Python websockets pattern used in this project.

## Audio Zone System

**Dynamic Central Audio (DCA) v0.3.7** — custom HACS integration. Fully replaces the old automation-based zone follow, volume readback/authority, ATV exclusion, and HTD cover stack. Do not re-enable old automations.

### Zones
| Zone | Status sensor | Follow-Me switch | Volume offset |
|------|--------------|-----------------|---------------|
| Main Floor | `sensor.dynamic_central_audio_main_floor_status` | `switch.dynamic_central_audio_main_floor_follow_me` | `number.dynamic_central_audio_main_floor_volume_offset` |
| Family Room / Tia's Office | `sensor.dynamic_central_audio_family_room_and_tias_office_status` | `switch.dynamic_central_audio_family_room_and_tias_office_follow_me` | `number.dynamic_central_audio_family_room_and_tias_office_volume_offset` |
| Master Bed & Bath | `sensor.dynamic_central_audio_master_bed_and_bath_status` | `switch.dynamic_central_audio_master_bed_and_bath_follow_me` | `number.dynamic_central_audio_master_bed_and_bath_volume_offset` |
| Gazebo & Yard | `sensor.dynamic_central_audio_gazebo_and_yard_status` | `switch.dynamic_central_audio_gazebo_and_yard_follow_me` | `number.dynamic_central_audio_gazebo_and_yard_volume_offset` |
| Garage | `sensor.dynamic_central_audio_garage_status` | `switch.dynamic_central_audio_garage_follow_me` | `number.dynamic_central_audio_garage_volume_offset` |
| Front Porch | `sensor.dynamic_central_audio_front_porch_status` | `switch.dynamic_central_audio_front_porch_follow_me` | `number.dynamic_central_audio_front_porch_volume_offset` |
| Garage Gym | `sensor.dynamic_central_audio_garage_gym_zone_status` | `switch.dynamic_central_audio_garage_gym_zone_follow_me` | `number.dynamic_central_audio_garage_gym_zone_volume_offset` |

### Key entities
- System status: `sensor.dynamic_central_audio_central_audio_status`
- Active switch: `switch.dynamic_central_audio_central_audio_active`
- AirPlay follow-me: `switch.dynamic_central_audio_central_audio_airplay_central_follow_me`
- Apple TV follow-me: `switch.dynamic_central_audio_central_audio_apple_tv_living_room_follow_me`

### Sources
- AirPlay: `media_player.airplay_downstairs`
- Apple TV: `media_player.living_room_apple_tv`
- Volume per zone is set by DCA directly via `media_player.volume_set` using `base_volume + volume_offset` — no helper entities involved

### Camera Sensors (UniFi Protect)
Each yard camera exposes both a motion sensor and a person-detection sensor. UniFi Protect does NOT expose per-camera motion zones as separate entities — zone granularity lives only inside the Protect app.

| Area | Motion | Person detected |
|------|--------|----------------|
| Yard East (alley) | `binary_sensor.yard_east_motion` | `binary_sensor.yard_east_person_detected` |
| Yard Middle / Gazebo-Slider | `binary_sensor.yard_gazebo_slider_motion` | `binary_sensor.yard_gazebo_slider_person_detected` |
| Yard West (alley) | `binary_sensor.yard_west_motion` | `binary_sensor.yard_west_person_detected` |
| Front door | — | `binary_sensor.front_door_person_detected_2` |
| Driveway | — | `binary_sensor.driveway_person_detected` |

- `binary_sensor.yard_motion` — whole-yard motion group (OR across cameras, not person-specific)
- East/West sensors face alleys — can pick up street traffic; use motion (not person) for irrigation deferrals

## Garage
- Presence sensor (mmWave): `binary_sensor.garage_presence_sensor_presence` (+ `_moving_target`, `_still_target`)
- Occupied group: `binary_sensor.garage_occupied` — OR of mmWave presence + pony/lexus/fridge camera motion
- Fan switch: `switch.garage_fans`
- Apple TV: `media_player.garage_apple_tv`
- Amp: `switch.extra1` (powers ATV speakers only — HTD zone has its own amp)
- Temperature/humidity: `sensor.garage_hygrometer_temperature` / `sensor.garage_hygrometer_humidity`
- Fan cooling automation: on after 2min presence + outdoor temp >80°F (`weather.forecast_home` temperature attribute); off after 15min mmWave empty
- Fan door ventilation automation (`garage_fan_door_ventilation`): on when both bay doors open 5+ min + garage temp >60°F, 6am–9am only; off when both doors closed and garage empty
- Audio off automation: `garage_empty_audio_off` — turns off ATV + amp after 10min empty; condition: ATV playing OR amp on
- Automations: `garage_fan_cooling_on`, `garage_fan_cooling_off`, `garage_empty_audio_off`, `garage_fan_door_ventilation`

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
| Garage | `switch.adaptive_hvac_garage_fan_locked` |

### Known edge case
Physical switch presses have no `context.user_id` — they bypass the claim system. HVAC can still override a fan set via physical switch.

## Master Bathroom Lights

- Dimmer: `light.master_bath_dimmer` — physical switch
- LEDs: `light.led_underlights` — 0-10V strip
- Always in sync via bidirectional pair: **Dimmer drives 0-10V** (ID: 1767225558095) + **0-10V reflects to dimmer** (ID: 1767248157121). Uses `input_boolean.master_bath_dimmer_sync` as mutex. Physical switch use propagates unconditionally — no block conditions on the sync pair.
- Occupancy automation: **Master Bath - Underlights (Occupancy + Lux)** (ID: 1771288057410, `automations/other/master_bath_underlights_occupancy_lux.json`)
  - Turns on when occupied 2s + NOT both in bed + (sun down OR daytime lux < 300)
  - Lux threshold 300 chosen from sensor data: cloudy days peak ~130 lux; sunny afternoons run 400–800+ lux
  - Turns off after 2 min unoccupied
  - Block condition: `binary_sensor.master_bed_both_in_bed = on` — suppresses mmWave-triggered turn-on while both are asleep; either person out of bed lifts the block

## Master Bedroom Lights

- Lights: `light.master_bedroom_manual_lights`, `light.master_bedroom_nightstands`
- Under-bed: `light.master_under_bed_light` — night-motion only (see Under Bed Night Motion below)
- **Occupancy automation** (ID: 1768187945725, `automations/other/master_bedroom_occupancy_lights.json`):
  - ON when occupied + sleep posture off + no one in bed + (sun down OR bathroom lux < 300)
  - Uses `sensor.master_bathroom_illuminance` as daytime lux gate — bedroom FP2 light sensor caps at 9 lx and is unusable for daylight detection
  - OFF after 5 min unoccupied
- **Under Bed Night Motion** (ID: 1769916429783): fires only when sleep posture ON; turns on when occupied + not both in bed; off after 30s unoccupied

## Master Suite Sleep System

### Canonical state
`input_boolean.master_suite_sleep_posture` is the single source of truth. AL sleep mode switches for bedroom/bathroom/closet are always derived from it via `mode_a_apply_master_suite_sleep_posture_to_mbr`. Never toggle the AL switches directly for sleep posture — go through the posture flag.

### Automation flow
- **Arm** (`mode_a_arm_master_suite_sleep_posture`) — fires when `master_bed_anyone_in_bed` ON + `master_bedroom_occupied` OFF for 2 min + posture OFF → sets posture ON
- **Apply** (`mode_a_apply_master_suite_sleep_posture_to_mbr`) — fires on any posture state change → syncs bedroom + bathroom + closet AL sleep mode switches
- **Disarm** (`mode_a_disarm_master_suite_sleep_posture`) — fires when `master_bed_anyone_in_bed` OFF for 5 min + `master_bedroom_occupied` OFF + posture ON → sets posture OFF
- **Exit** (`mode_a_exit_al_sleep_mode_master_bedroom_and_closet`, ID: 1771230477164) — two paths:
  - Sunrise+30: directly turns off bathroom + closet AL sleep mode only (bedroom stays dimmed longer)
  - Bed empty 5 min: turns off `master_suite_sleep_posture` → Apply cascades to all rooms; this ensures Arm can re-engage when they return to bed

### Re-arm on return (dog-puke pattern)
Both out of bed 5+ min → Exit sets posture OFF → posture is now OFF → they return to bed → Arm re-fires once `master_bedroom_occupied` clears → posture ON → Apply restores all sleep modes.

### Bed presence sensor
Device: `device_tracker.bed_presence_2c0bd4` (ElevatedSens, IP 192.168.255.17, VLAN 500), response speed: Slow
- Left side (Tia): `sensor.master_bedroom_bed_presence_left_pressure` — occupied: 45%, trigger: 43.75%, unoccupied: 40%
- Right side (Caleb): `sensor.master_bedroom_bed_presence_right_pressure` — occupied: 87%, trigger: 81.5%, **unoccupied: 50%** (lowered from 65% 2026-05-16 to prevent false negatives from position shifts)
- Calibration buttons: `button.master_bedroom_bed_presence_calibrate_{left,right}_{occupied,unoccupied}`
- `binary_sensor.master_bed_{caleb,tia,anyone,both}_in_bed` — named wrappers; `master_bedroom_bed_presence_bed_occupied_{left,right,either,both}` — raw device sensors

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

**Adaptive HVAC v0.3.7** — custom HACS integration. Old 13-automation YAML system is fully replaced. Do not re-enable old automations.

### Architecture
- **System entry** — owns the thermostat, reads weather, dispatches heat/cool/off
- **Zone entries** — one per room; each reads temp sensors, controls local fans, emits thermal requests
- **Season** — calendar-based only (Oct–Apr = winter, May–Sept = summer); override via `select.adaptive_hvac_season_override`

### Decision logic
- Zone: if `temp > zone_target_temp` → fan on (occupied only) + request cool; if `temp ≤ zone_target_temp` → fan off
- System: cooling allowed if `outdoor ≥ cool_exterior_threshold` (default 60°F, currently set to 68°F) OR any zone is 5°F+ above its target; heat allowed if `outdoor ≤ heat_exterior_threshold` (60°F)
- System: cooling blocked if any zone's window sensor is open (actual contact sensor); emergencies bypass this
- Occupancy gates **local fans only** — thermostat decisions are never blocked by occupancy
- User fan changes claim that zone's fans until midnight (see Fan Lock System)
- User thermostat adjustments (faceplate/app) are adopted as the new seasonal setpoint and persisted to config entry options; reset on season change

### Zones (v0.3.7)
| Zone | Status sensor | Temp sensor | Auto switch | Fan lock switch |
|------|--------------|-------------|-------------|-----------------|
| Caleb's Office | `sensor.calebs_office_hvac_status` | `sensor.caleb_s_office_hygrometer_temperature` | `switch.adaptive_hvac_calebs_office_auto_2` | `switch.adaptive_hvac_calebs_office_fan_locked` |
| Tia's Office | `sensor.tias_office_hvac_status` | `sensor.tias_office_hygrometer_temperature` | `switch.adaptive_hvac_tias_office_auto` | `switch.adaptive_hvac_tias_office_fan_locked` |
| Master Bedroom | `sensor.master_bedroom_hvac_status` | `sensor.meter_pro_2689_temperature` | `switch.adaptive_hvac_master_bedroom_auto` | `switch.adaptive_hvac_master_bedroom_fan_locked` |
| Garage | `sensor.garage_hvac_status` | `sensor.garage_hygrometer_temperature` | `switch.adaptive_hvac_garage_auto` | `switch.adaptive_hvac_garage_fan_locked` |

### Key entities
- Thermostat: `climate.downstairs_thermostat`
- System status: `sensor.adaptive_hvac_status` (state = status string, `reasoning` attribute = full decision tree)
- Season: `sensor.adaptive_hvac_season`
- Mode: `sensor.adaptive_hvac_mode`
- Active switch: `switch.adaptive_hvac_active`
- Manual override: `switch.adaptive_hvac_manual_override`
- Cool exterior threshold: `number.adaptive_hvac_cool_exterior_threshold` (currently 68°F — live dashboard slider)
- Upstairs average: `sensor.upstairs_average_temperature` (Caleb + Tia + Master avg, in `templates.yaml`)

### Dashboard
`/dashboard-hvac` — system status + reasoning, per-zone cards, upstairs temp glance, thermostat history, logbook with last-off attribution, controls, setpoint sliders, force-evaluate button.

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

**For complete configuration:** See `docs/adaptive_hvac.md`

## Notes
- Still learning HA — update this file as patterns emerge
- Automations created via API use string IDs (not UUIDs) — choose descriptive IDs
- Binary sensor groups created via UI (Helpers) cannot be updated via `group.set` API — must use HA UI or websocket options flow
- SSH to HA host (`hassio@192.168.255.247`): use `ssh -i ~/.ssh/infra hassio@192.168.255.247`; writes to `/config/` require `sudo`; `root` login denied
- File transfer to HA: SCP/SFTP not supported — use base64 encode/decode over SSH (`echo '<b64>' | base64 -d > /tmp/file`)
- `TODOS.md` in this directory tracks deferred work
