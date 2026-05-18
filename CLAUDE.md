# Home Assistant - Claude Code Context

## Connection
- Internal URL: http://ha.iot.scansenconsulting.com:8123
- External URL: https://homeassistant.scansenconsulting.com
- API token: $HA_TOKEN (loaded from ~/.secrets)
- MCP server: http://ha.iot.scansenconsulting.com:8123/mcp_server/sse

## API Usage
- Get all states: curl -s http://ha.iot.scansenconsulting.com:8123/api/states -H "Authorization: Bearer $HA_TOKEN"
- Get single entity: curl -s http://ha.iot.scansenconsulting.com:8123/api/states/<entity_id> -H "Authorization: Bearer $HA_TOKEN"
- Call service: curl -s -X POST http://ha.iot.scansenconsulting.com:8123/api/services/<domain>/<service> -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d '{"entity_id": "<entity_id>"}'

## API Usage — Additional
- Get automation definition: curl -s http://ha.iot.scansenconsulting.com:8123/api/config/automation/config/<id> -H "Authorization: Bearer $HA_TOKEN"
- Create/update automation: curl -s -X POST http://ha.iot.scansenconsulting.com:8123/api/config/automation/config/<id> -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d @file.json
- Reload automations: curl -s -X POST http://ha.iot.scansenconsulting.com:8123/api/services/automation/reload -H "Authorization: Bearer $HA_TOKEN"

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

### Mode selector
`input_select.irrigation_mode` — options: `seedling`, `summer`, `winter`, `off`

### Zones (Yardian controller)
| Zone | Switch | Soil sensor | Motion sensor |
|------|--------|-------------|---------------|
| East | `switch.yardian_controller_yard_east` | `sensor.east_yard_soil_sensor_humidity` | `binary_sensor.yard_east_motion` |
| Middle | `switch.yardian_controller_yard_middle` | avg(east + west) | `binary_sensor.yard_gazebo_slider_motion` |
| West | `switch.yardian_controller_yard_west` | `sensor.back_yard_soil_sensor_humidity` | `binary_sensor.yard_west_motion` |
| Front | `switch.yardian_controller_front_yard` | `sensor.front_yard_soil_sensor_humidity` | — (no motion check) |

**Soil sensor calibration note (Third Reality sensors, 2026-05-17):** Sensors are accurate to within ~10% across their full range. Currently reading 97–99% (post-watering/saturated). Watering thresholds: normal 25%, seedling 35%.

### Automations
- `germination_watering_program` — 28-day seedling program; 4 cycles/day (6am/10am/2pm/6pm); soil threshold 93%; fallback 4min
- `summer_watering_program` — daily at 5:30am; soil threshold 92%; fallback 6min
- `drip_garden_watering` — drip zone (trees/shrubs/flowers/veg); Tue+Fri base; adds Mon+Thu when forecast >85°F
- `seedling_mode_start` — resets `input_datetime.seedling_start_date` to today when mode set to seedling

### Motion-deferral pattern (germination + summer programs)
- Motion sensors captured once at cycle start as variables (`east_motion`, `middle_motion`, `west_motion`)
- Zone with motion active → skipped, logs "deferred"; other zones proceed
- After all zones complete, retry blocks run for any deferred zone:
  - `while` loop: check sensor → if still active, log attempt number + wait 5min, repeat
  - Once clear → water normally using original soil reading
- Front yard has no motion check
- Fallback (stale sensor) is also suppressed when motion is active

### Dashboard notifications (persistent_notification)
All three automations post plain-English `persistent_notification` cards to the dashboard. Each uses a stable `notification_id` so cards overwrite on every run rather than accumulating.

| Event | notification_id | Example message |
|-------|----------------|-----------------|
| Whole session skipped (rain/wind/soil) | `summer_watering_session` / `germination_watering_session` / `drip_watering_session` | "Today's watering was skipped — it's too windy right now (28mph)." |
| Germination phase-2 cycle-4 skipped | `germination_watering_session` | "The 4th daily cycle is skipped during weeks 2–4." |
| Drip Mon/Thu not hot enough | `drip_watering_session` | "Forecast high is only 72°F — not hot enough to add an extra watering." |
| Zone watered | `summer_watering_east` / `_middle` / `_west` / `_front` (same pattern for germination) | "Watered for 10 minutes. Soil was at 88%." |
| Zone skipped — soil adequate | same per-zone ID | "Soil is already at 94% — above the 92% threshold." |
| Zone delayed — motion | same per-zone ID | "Someone is in the east yard. Watering will happen after other zones finish." |
| Zone still waiting (retry loop) | same per-zone ID | "East yard still occupied (check #2). Will try again in 5 minutes." |
| Zone watered after delay | same per-zone ID | "Watered for 10 minutes after waiting for the yard to clear." |
| Zone sensor fallback | same per-zone ID | "Sensor unavailable or stale (last reading: 85%). Ran a 6-minute safety watering." |

`system_log.write` calls are kept alongside notifications for HA log-file detail. Session-level skips that previously exited silently via top-level `conditions:` are now checked inside the actions block so they can log before stopping.

## HVAC System

### Key entities
| Entity | Role |
|--------|------|
| `climate.downstairs_thermostat` | Single thermostat — controls whole house heat/cool/fan |
| `sensor.caleb_s_office_hygrometer_temperature` | **Primary sensor** — gates all automations; office is hottest/coldest room |
| `sensor.caleb_s_office_hygrometer_humidity` | Used for passive_humid trigger (>55% at ≥70°F) |
| `sensor.downstairs_thermostat_temperature` | Floor-level temp — emergency heat trigger |
| `sensor.meter_pro_2689_temperature` | Master bedroom temp — co-trigger for heat and passive cooling |
| `sensor.meter_pro_2689_humidity` | Master bedroom humidity |
| `input_select.hvac_season` | `summer` / `shoulder` / `winter` — set manually or by `hvac_season_transition` |
| `binary_sensor.windows_assumed_open` | Drives passive cooling mode; blocks heat in summer |
| `input_boolean.hvac_manual_override` | Blocks all HVAC automations when on |
| `input_boolean.hvac_managed_heating` | Tracks whether automation activated heat (for morning restore) |

### Season schedule (auto via `hvac_season_transition`, 00:01 on 1st)
- **May 1** → summer: thermostat off, fan auto, passive cooling active
- **Oct 1** → winter: thermostat heat at 68°F
- **Apr 1** → shoulder: thermostat off, passive only — no normal heat (emergency only)

### Cooling thresholds (summer, windows closed)
| Condition | Action |
|-----------|--------|
| Office < 70°F for 5min | Comfortable: fans off (unless master bedroom > 70°F → fans at 25%) |
| Office > 71.9°F for 2min OR master bedroom > 71.9°F for 5min | Passive: fans at 33%, whole house fan on |
| Office ≥ 70°F + humidity > 55% for 2min | Passive humid: same as passive |
| Office ≥ 74°F + solar > 2kW + 10am–3pm | Escalate solar: fans 50%, AC at 68°F |
| Office > 73.9°F for 30min | Escalate standard: fans 50%, AC at 68°F |
| Office > 77.9°F | Emergency: fans 100%, AC at 68°F |

### Windows open behavior (summer only)
- Open → thermostat off, whole house fan on, office fans at 25%
- Close → whole house fan reset to auto (thermostat stays off until temp triggers re-engage)

### Heating thresholds
| Trigger | Season | Action |
|---------|--------|--------|
| Downstairs < 68°F for 5min | winter | Heat at 68°F |
| Office < 65°F for 5min | winter | Heat at 68°F |
| Master bedroom < 65°F for 5min | winter | Heat at 68°F |
| Downstairs < 55°F | any | Emergency heat at 68°F |
| Office < 50°F | any | Emergency heat at 68°F |
| Master bedroom < 45°F | any | Emergency heat at 68°F |

Emergency heat blocked when: summer + windows open. In summer (windows closed), heat only fires when at least one sensor is below 45°F. Normal heat blocked during sleep posture.

### Setbacks
- **Unoccupied 8h**: cool → 76°F, heat → 62°F
- **Return home**: heat mode → restore 68°F; cool mode → restore 74°F
- **Winter 6am**: restore heat setpoint to 68°F, clear managed_heating flag

### Whole house fan
Thermostat `fan_mode`: `on` = continuous circulation, `auto` = only when HVAC cycles. Controlled on HVAC dashboard (`dashboard-hvac`). Automation sets it to `on` when windows open or passive cooling active; back to `auto` when comfortable.

### Sensor failsafe
`hvac_sensor_failsafe` monitors office sensor (gates automations) and master bedroom sensor (advisory). On office sensor recovery, re-triggers cooling or heating automation if conditions warrant.

## Notes
- Still learning HA — update this file as patterns emerge
- Automations created via API use string IDs (not UUIDs) — choose descriptive IDs
- Binary sensor groups created via UI (Helpers) cannot be updated via `group.set` API — must use HA UI or websocket options flow
- SSH to HA host (`hassio@192.168.255.247`): use `ssh -i ~/.ssh/infra hassio@192.168.255.247`; writes to `/config/` require `sudo`; `root` login denied
- File transfer to HA: SCP/SFTP not supported — use base64 encode/decode over SSH (`echo '<b64>' | base64 -d > /tmp/file`)
- `TODOS.md` in this directory tracks deferred work
