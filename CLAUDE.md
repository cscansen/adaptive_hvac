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
- automations.json — exported automation states (refresh as needed)
- speaker_zones_follow_updated.json — main indoor speaker zone follow automation (ID: 1768126562712)
- outdoor_gazebo_zone_follow.json — outdoor gazebo zone automation (ID: outdoor_gazebo_zone_yard_person_presence)
- germination_watering_program.json — germination watering automation (ID: germination_watering_program)
- summer_watering_program.json — summer watering automation (ID: summer_watering_program)
- mode_a_exit_al_sleep_mode.json — Mode A exit AL sleep mode automation (ID: 1771230477164)
- hvac_cooling.json — cooling decision tree (ID: hvac_cooling)
- hvac_heating_normal.json — heating triggers (ID: hvac_heating_normal)
- hvac_setback_unoccupied.json — away setback (ID: hvac_setback_unoccupied)
- hvac_sensor_failsafe.json — sensor monitoring (ID: hvac_sensor_failsafe)
- garage_fan_door_ventilation.json — door ventilation automation (ID: garage_fan_door_ventilation)
- All files in this directory are project context for Claude

## Working Patterns
- For analysis/review: export to local JSON files first, then analyze
- For real-time control: use MCP or direct API calls
- Always source ~/.secrets before API calls
- Automation JSON files use the format of speaker_zones_follow_updated.json; POST to /api/config/automation/config/<id> then reload
- Lovelace named dashboard config (e.g. `dashboard-hvac`) is NOT accessible via REST API — use websocket: `{"type": "lovelace/config", "url_path": "dashboard-hvac"}` to read, `{"type": "lovelace/config/save", ...}` to write. See Python websockets pattern used in this project.

## Audio Zone System

### Indoor Zones (managed by speaker_zones_follow_updated.json)
- `media_player.main_floor` — auto flag: `input_boolean.auto_audio_main_floor` — occupancy: `binary_sensor.main_floor_common_area_occupied`
- `media_player.second_floor` — auto flag: `input_boolean.auto_audio_second_floor` — occupancy: family_room + caleb/tia offices
- `media_player.master_bedroom` — auto flag: `input_boolean.auto_audio_master_bedroom`
- `media_player.garage` — auto flag: `input_boolean.auto_audio_garage` — amp: `switch.extra1`

### Outdoor Zones (managed by outdoor_gazebo_zone_follow.json)
- `media_player.gazebo` — auto flag: `input_boolean.auto_audio_gazebo` — presence: `binary_sensor.yard_gazebo_slider_person_detected`
- `media_player.front_porch` — auto flag: `input_boolean.auto_audio_front_porch` — no presence automation yet

### Apple TV Zone Exclusion
When the garage ATV plays, it always overrides the HTD zone (no AirPlay exception). Other ATVs drop their zone only when AirPlay is not active. Auto flag is restored when the ATV stops.
- Garage ATV (`media_player.garage_apple_tv`) → disables `input_boolean.auto_audio_garage`, turns off `media_player.garage`, turns on `switch.extra1` (amp). Restores after 5min idle if still occupied; `garage_empty_audio_off` handles cleanup if garage empties first.
- Tia's Office ATV (`media_player.tias_office_apple_tv`) OR Family Room ATV (`media_player.family_room_apple_tv`) → disables second floor zone; restores only when both stop
- Master Bedroom ATV (`media_player.master_bedroom_apple_tv`) → disables master bedroom zone
- Automations: `garage_atv_zone_off_independent`, `garage_atv_zone_restore`, `audio_zone_second_floor_atv_off`, `audio_zone_second_floor_atv_restore`, `audio_zone_master_bedroom_atv_off`, `audio_zone_master_bedroom_atv_restore`

### Audio Routing
- AirPlay source: `media_player.airplay_downstairs` (state must be 'playing')
- Apple TV source: `media_player.living_room_apple_tv` + `input_boolean.living_room_appl_tv_audio_follow_me_mode` must be ON
- Volume policy (auto zones only): `automation.speaker_zones_volume_policy_auto_only` (ID: 1768687730669) — AirPlay→80%, Apple TV→50%
- Volume per zone stored in: `input_number.htd_vol_<zone>` (e.g. htd_vol_gazebo, htd_vol_front_porch)

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
- Audio off automation: `garage_empty_audio_off` — turns off ATV + amp + restores `auto_audio_garage` after 10min empty; condition: ATV playing OR amp on
- Automations: `garage_atv_zone_off_independent`, `garage_atv_zone_restore`, `garage_fan_cooling_on`, `garage_fan_cooling_off`, `garage_empty_audio_off`, `garage_fan_door_ventilation`

## Fan Lock System
When a user manually turns on or adjusts a fan, that fan is "claimed" and HVAC automations will not override it until the user turns it off.

### How it works
- `fan_lock_set_claimed` — fires when user (`context.user_id` set) turns on/adjusts a fan; sets flag + stores speed
- `fan_lock_clear_claimed` — fires when any tracked fan turns off; clears flag unconditionally
- `fan_lock_restore` — fires when an automation (`context.user_id = none`, `context.parent_id` set) changes a claimed fan; restores user's speed

### Tracked fans and helpers
| Fan | Claimed flag | Speed store |
|---|---|---|
| `fan.tia_office_ceiling_fan` | `input_boolean.fan_user_claimed_tia_office` | `input_number.fan_claimed_speed_tia_office` |
| `fan.caleb_office_ceiling` | `input_boolean.fan_user_claimed_caleb_office` | `input_number.fan_claimed_speed_caleb_office` |
| `fan.fan` (family room) | `input_boolean.fan_user_claimed_family_room` | `input_number.fan_claimed_speed_family_room` |
| `fan.master_ceiling_fan` | `input_boolean.fan_user_claimed_master` | `input_number.fan_claimed_speed_master` |
| `fan.living_room_ceiling_fan` | `input_boolean.fan_user_claimed_living_room` | — (HVAC only turns it off) |
| `switch.garage_fans` | `input_boolean.fan_user_claimed_garage` | — (on/off switch) |

### HVAC automations that respect the lock
- `hvac_living_room_fan_comfort` — conditions on `fan_user_claimed_living_room = off`
- `garage_fan_cooling_on` / `garage_fan_cooling_off` — condition on `fan_user_claimed_garage = off`
- `hvac_cooling`, `hvac_equalization`, `hvac_season_transition`, `night_mode_master_bedroom_fan_control` — handled by `fan_lock_restore` counter-automation (YAML automations, not patchable via API)

### Known edge case
Physical switch presses have no `context.user_id` and no `context.parent_id` — they bypass the claim system. HVAC can still override a fan set via physical switch.

### Helpers defined in
`/config/configuration.yaml` — `input_boolean` and `input_number` sections (SSH to edit, then `input_boolean.reload` + `input_number.reload` via API)

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

**Adaptive HVAC v0.3.3** — custom HACS integration. Old 13-automation YAML system is fully replaced. Do not re-enable old automations.

### Architecture
- **System entry** — owns the thermostat, reads weather, dispatches heat/cool/off
- **Zone entries** — one per room; each reads temp sensors, controls local fans, emits thermal requests
- **Season** — calendar-based only (Oct–Apr = winter, May–Sept = summer); override via `select.adaptive_hvac_season_override`

### Decision logic
- Zone: if `temp > zone_target_temp` → fan on (occupied only) + request cool; if `temp ≤ zone_target_temp` → fan off
- System: cooling allowed if `outdoor ≥ cool_exterior_threshold` (60°F) OR any zone is 5°F+ above its target; heat allowed if `outdoor ≤ heat_exterior_threshold` (60°F)
- Occupancy gates **local fans only** — thermostat decisions are never blocked by occupancy
- User thermostat adjustments (faceplate/app) are adopted as the new seasonal setpoint and persisted to config entry options; reset on season change

### Zones (v0.3.3)
| Zone | Status sensor | Temp sensor | Auto switch |
|------|--------------|-------------|-------------|
| Caleb's Office | `sensor.calebs_office_hvac_status` | `sensor.caleb_s_office_hygrometer_temperature` | `switch.adaptive_hvac_calebs_office_auto_2` |
| Tia's Office | `sensor.tias_office_hvac_status` | `sensor.tias_office_hygrometer_temperature` | `switch.adaptive_hvac_tias_office_auto` |
| Master Bedroom | `sensor.master_bedroom_hvac_status` | `sensor.meter_pro_2689_temperature` | `switch.adaptive_hvac_master_bedroom_auto` |
| Garage | `sensor.garage_hvac_status` | `sensor.garage_hygrometer_temperature` | `switch.adaptive_hvac_garage_auto` |

### Key entities
- Thermostat: `climate.downstairs_thermostat`
- System status: `sensor.adaptive_hvac_status` (state = status string, `reasoning` attribute = full decision tree)
- Season: `sensor.adaptive_hvac_season`
- Mode: `sensor.adaptive_hvac_mode`
- Windows (informational only, does NOT block AC): `binary_sensor.windows_assumed_open_2` — on when outdoor 58–68°F
- Active switch: `switch.adaptive_hvac_active`
- Manual override: `switch.adaptive_hvac_manual_override`
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
