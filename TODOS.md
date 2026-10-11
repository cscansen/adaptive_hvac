# Home Assistant — Deferred TODOs

## Naming cleanup (started 2026-10-10) — IN PROGRESS

Convention: areas "Group - Specific" (Office - Caleb, Master - Bath, Yard - East, Crawl Space - IT); devices
"<Area> <Thing>"; straight apostrophes. Log in infrastructure/CHANGES.md.
- [x] Batch 1 — areas (renamed + aliases; Tech Closet merged; Crawl Space - Water Closet created)
- [x] Batch 2a — Office - Caleb/Tia + Master device names + entity display overrides
- [x] Batch 2b — Living/Family/Kitchen/Dining (+ FP2s/zones, WiiM×3, THEUNIT; retired MSS110s deleted)
- [x] Batch 2c — outdoor/utility areas, no-area devices, Eve → Roof, MyZone6–12 + SwitchBot hub disabled
- [x] Yardian "Drip/Garden" zone → Yard - West (area id `yard`; verified 2026-10-10)
      + ~20 devices with no area (Hubitat hygrometers/Garage Fans/Yard Middle Moisture, HVAC zone devices, hubs)
- [x] Step 1 — 50 automation-referenced entity IDs renamed + all refs rewritten (2026-10-10, see CHANGES.md)
- [x] Step 2 — 7 HomeKit-bridged renames done 2026-10-10. Bridge include lists were rewritten in the same stop/start,
      accessory IDs were verified unchanged, and every bridge's accessory count held.
- [x] Step 3 — 194 primary IDs on renamed devices + Matter eve dupes disabled (2026-10-10, see CHANGES.md)
- [x] Step 4 — 610 config/diagnostic IDs + bed Tia/Caleb side labels, live, no restart (2026-10-10, see CHANGES.md).
      Left as-is: UniFi client trackers, Spook system sensors, Yardian zone flags (no entity name), OneDrive `_2` dupes.
- [ ] Leviton master bath dimmer (homekit_controller `LEVDS-MotDim-DC8A`) in setup_retry / unavailable since ≤12:00
      UTC 10-10 — pre-existing, needs re-pair or a power-cycle
- [ ] WiiM Pro is in HA via 3 integrations (wiim, linkplay, cast) — pick one during batch 3
- [ ] Decide: Bond `light.light` (unavailable, unreferenced) — remove in Bond app
- [x] MSS560 dimmers re-added to meross_lan (they'd been ignored) and given the original light IDs; HomeKit twins
      renamed `*_homekit` and their entries disabled (2026-10-10). Delete the disabled twins once the Meross ones prove out.
- [ ] Default dashboard `strategy.areas.order` has stale ids (tech_closet, guest_bathroom, work_bench, home_gym)

## Adaptive HVAC — "No zone data available" for ~3 min after every HA start — PENDING (seen 2026-10-10)

- After the 14:40 UTC restart, `sensor.adaptive_hvac_status` read "No zone data available" 14:41:09 → 14:44:09, then
  recovered on its own (the user saw it as "HVAC completely broke"). Zone coordinators apparently don't populate until
  their first scheduled refresh. Fix: run `async_config_entry_first_refresh()` / an immediate zone refresh at setup, or
  have the system coordinator wait for the zones before computing status.
- Same window: `sensor.adaptive_hvac_season` reads **summer** for ~3 min after every start, then goes back to winter (seen
  4× on 10-10). Probably defaults to summer before data arrives. Could drive the wrong heat/cool decision if the system
  is active at boot, so make the default "unknown/hold last" (RestoreEntity) instead of summer.

## Opus review follow-ups (2026-10-09) — HIGH

- [x] **Off-site backups failing since 10-09** — OneDrive Personal quota full. FIXED 2026-10-09:
      OneDrive for Business (Entra app 65b09b13…, see infrastructure/CHANGES.md) is now the
      off-site agent (949 GiB free); Personal removed from create list.
- [x] 10-10 backup to OneDrive for Business confirmed by user. Client secret expires ~2028-10 — rotate before.
- [x] Backup encryption key rotated by user 2026-10-10.
- [~] **Presence → Apple Home** (2026-10-09): `input_boolean.caleb_home_apple` / `tia_home_apple`
      exposed on HASS Bridge:21064; user created 4 Home app People Arrive/Leave automations;
      `binary_sensor.caleb_home`/`tia_home` templates now read only those booleans (backup
      `templates.yaml.bak.*_apple_presence`). **Verify** on the next real leave/arrive that the
      boolean flips. Deer deterrents (`yard_*_deer_deterrent_night`, still disabled for season)
      switched from `person.*: not_home` to `binary_sensor.nobody_home: on` (2026-10-10). No
      `person.*` / `group.people` refs remain in automations/scripts/templates.
- [x] HASS Bridge:21064 now explicit include (was `include_domains: [input_boolean]`) —
      dropped christmas_time, master_bath_dimmer_sync, lightshow_running from HomeKit (2026-10-09).
- [x] **Auto-lock dead trigger** — FIXED 2026-10-10: `automation 1771124383892` nobody_home
      trigger repointed from nonexistent `group.people` to `binary_sensor.nobody_home` off→on
      (Apple-driven). Rides on the presence verification above.
- [x] **Duplicate automations** — FIXED 2026-10-09: Evening Lights ON (anchor) / OFF (3× literal)
      deduped by text surgery, empty "Back Field Animal" stub removed; 84 unique, semantically
      verified unchanged. Backup `automations.yaml.bak.*_dedupe`. Likely mechanism: blocks were
      literally triplicated after 08-04, then an API/UI save of the ON one replaced every same-id
      entry with one object → PyYAML emitted `&id001`/`*id001`.
- [x] `from: on` added to *TV Backlight - Follow TV Power* and *Garage - Stop ATV when amp
      turns off* (2026-10-09).
- [x] LocalTuya cleanup (2026-10-09): 9 dead/retired devices removed (Dimmer Switch 2/3/4, Lamp, Dining Room
      Lamps, Entry Lights, Upper Cabinet 1/2/3) + switch_as_x "Caleb's Office - Lamp" wrapper auto-removed.
      Root cause of the noise: DHCP had reassigned their saved IPs (.149 shared by Dimmer 3 + Desk → wrong-key
      errors; .228 → an iPad). Full configs incl. local_keys archived to
      `devbox-shared/secrets/localtuya-retired-2026-10-09.json.age` (decrypt: `age -d -i ~/.config/age/key.txt`).
      11 devices remain. Christmas Trees stays (seasonal, unplugged → expected connect warnings).
- [x] LocalTuya "DPS mismatch" — CLOSED 2026-10-10, mapping was never wrong. Desk (Amazon Basics 12V RGBWW,
      v3.3) + Flag use std Tuya v2 light DPS: 20 power, 21 mode, 22 bright 10–1000, 23 CT 0–1000, 24 HSV hex.
      "Unknown DPS 21" / failed `{22: 1000}` writes were Dimmer Switch 3 sharing `.149`; stopped when it was
      removed (last warning 07:28:50). Live test on/50%/3000K/red/100%/off: no errors, user confirmed.
      Cosmetic only: HA shows CT kelvin = None and a 2000–6535 K range. If IPs drift again → DHCP reservations.
- [x] Deleted all 9 `/homeassistant/configuration.yaml.bak*` (May 15 → Oct 9, every one held the
      plaintext Schluter password) — user-approved 2026-10-10.
- [x] Schluter password rotated 2026-10-11 (user) — the copies in the deleted backups are dead.
- [x] Spook repairs cleared 2026-10-10 (5 → 0): area humidity for Garage/Living Room/Master Bedroom
      repointed to live sensors; WLED retired → `light.eve_lights_wled` group deleted + stripped from 17
      holiday scenes and Evening Lights ON/OFF; orphaned FP2 light-level stats cleared. Adaptive HVAC
      unaffected (zone options override the stale setup `data` refs; 36/36 entities healthy).
- [ ] Irrigation (next season): `_fetch_weather` uses forecast[0] only — can't skip
      watering ahead of tomorrow's rain.

## Irrigation v0.8.0 — Deployment & Cutover — HIGH (branch pushed 2026-08-10)

Branch `v0.8.0-interval-model-and-cooling` is pushed to
`github.com/cscansen/adaptive-irrigation` but **not merged, not tagged, not deployed**.
Code changes are complete; everything below needs a human.

Full rationale is in the repo's `CHANGELOG.md`. Short version: watering inverted from
"adapt the duration, water often" to "adapt the interval, soak deep", and heat-stress
cooling moved from the Yardian into HA so it can trigger on measured root-zone
temperature per zone instead of one clock for all zones.

**Ordered cutover steps:**
- [ ] Merge branch to `main`, tag `v0.8.0`, push tags (0.6.9–0.7.3 were never tagged;
      this would be the first tag since v0.6.8)
- [ ] Update via HACS, restart HA
- [ ] **Clear the contaminated calibration rates** — all four are corrupt (2.75 / 4.16 /
      0.90 %/min; physically impossible). `sudo rm /homeassistant/.storage/adaptive_irrigation_*_calibration`
      then restart. If a rate reappears, the `RestoreEntity` put it back — also scrub
      those entities from `core.restore_state`. Back up first.
- [ ] Set the new per-zone options (see table below). **`fill_target` especially** —
      the 70% default is unreachable for East (tops ~62) and Front (~55), so those zones
      would soak for `max_duration` every single run.
- [ ] Set `Soak Cycles` back to 3 — cycling is correct on a 45-min run, it was only
      harmful on the short runs the old duration bug produced
- [ ] Verify cooling fires on West and Middle for 1–2 days; confirm `Last Cooling Delta`
      is negative
- [ ] **Only then** disable the Yardian 3pm cooling program. Disabling it before HA
      cooling is proven leaves West with no heat protection in the worst stretch.
- [ ] Confirm what the Yardian is actually running — `binary_sensor.yardian_controller_standby`
      is on and `sensor.yardian_controller_rain_delay` reads 21600, so its current
      schedule state is ambiguous
- [ ] Apply `dashboard.yaml` from the repo via Raw configuration editor
      (storage-mode dashboards need a **full HA restart**, not just a refresh)

**Per-zone starting values (derived from 14 days of probe history, 2026-08-10):**

| Zone | Temp sensor | Refill | Fill | Cool at | Max dur | Fallback |
|---|---|---|---|---|---|---|
| Yard West | `sensor.yard_west_soil_sensor_temperature` | 45 | 70 | 93°F | 60 | 45 |
| Yard Middle | `sensor.yard_west_middle_soil_sensor_temperature` | 45 | 66 | 100°F | 60 | 45 |
| Front Yard | `sensor.yard_front_soil_sensor_temperature` | 48 | 55 | 95°F | 45 | 35 |
| Yard East | `sensor.yard_east_soil_sensor_temperature` | 52 | 62 | 95°F | 45 | 35 |

West's refill is deliberately **above** the 40 default: that turf is heat-stressed, so it
should water sooner, not later. Do not lower it until soil temperatures drop.

---

## Irrigation — Verify East & Front Probe Placement — PENDING

Both probes plateau instead of continuing to dry — Front sits at 48–49 for days, East moves
only ~4 points a week — which usually means the probe is at or below the active root zone.
West and Middle show clean dry-down curves by contrast.

Until this is confirmed, East and Front refill/fill numbers are guesses and their zones
can't be trusted to drive an interval model. Check insertion depth and angle against West's
(all are supposed to be at 45° targeting the root zone).

---

## Irrigation — West Side Heat Stress — SEASONAL, revisit 2026-09

**Root cause established 2026-08-10: this is a heat problem, not a watering problem.**
Root-zone temperatures over 5 days:

| Zone | Peak | % of day ≥85°F |
|---|---|---|
| Yard Middle | 108–114°F | 45–47% |
| Yard West | 97–114°F | 36–44% |
| Front Yard | 92–98°F | ~20% |
| Yard East | 90–94°F | ~18–26% |

Cool-season grass stops root growth around 80°F and loses root mass above ~85°F. West and
Middle are above that line nearly half of every day. Roots die back faster than the plant
rebuilds them, the reservoir shrinks, and it *presents* as underwatering. Adding water does
not break that loop.

**Note Middle is as bad as West or worse** — 108–114°F every day — but its moisture curve
looks healthy so it has never flagged as a problem. Walk it before it declines visibly.

Mowing height is already at deck max, so the best free lever is spent.

**September work (do not start early — deliberate depletion on stressed turf in August
accelerates dieback):**
- [ ] Aerate West and Middle
- [ ] Compost topdressing — organic matter buffers both moisture and temperature
- [ ] Overseed
- [ ] Only after the above, and only once root-zone temps hold under 80°F, begin lowering
      refill points to deepen roots (the deferred root-training controller in the repo's
      `TODOS.md` is gated on exactly this)
- [ ] Avoid nitrogen until soil cools; iron for colour without pushing growth the plant
      can't support

**Longer horizon, if West keeps losing ground after a proper fall:** East gets ~2 hours of
midday shade and runs ~20°F cooler at the root zone — a large return for a small amount of
shade. A shade sail or tree on the west exposure is a physical fix for what is fundamentally
a physical problem. Failing that, the answer is species: tall fescue handles that exposure
far better than bluegrass, and buffalo grass / blue grama are Front Range natives that
genuinely thrive in it.

---

## Whole-House PTT Intercom — DESIGN (not started)

Push-to-talk button per zone: hold on phone PWA → voice plays live in that HTD zone → releases back to whatever Dynamic Central Audio (DCA) had the zone doing. Full design, confirmed hardware facts, and required DCA integration changes written up in `/mnt/nas/ai-workspace/documentation/homeassistant/ptt_intercom_plan.md` — read that before starting, several architectural decisions already made there (e.g. HTD zone switching needs zero new code, DCA needs a new `_ptt_active` override extending the existing `_atv_excluded_by` pattern).

**Open blockers before implementation starts:**
- [x] ~~Physically trace which `Source N` on the HTD amp the HA box's headphone-out (`card1`, Realtek ALC255) is wired to~~ — confirmed `Source 3` (2026-07-19, via temporary AirPlay2 add-on test)
- [ ] Decide local playback sink: Music Assistant local player vs custom mpv-based add-on
- [ ] Decide whether PTT baseline volume is static per-zone config or dashboard-slider-authoritative
- [ ] Uninstall the test "AirPlay2" add-on (`ghcr.io/johannvr/amd64-ha-airplay2`) via Settings → Add-ons, and remove the paired "Shairport Sync Media Player" integration entry — do via UI, not SSH/docker (Supervisor-managed)

---

## HVAC Adaptive System — DONE (v0.3.0 shipped; v0.4.0 as of 2026-08-03)

Delivered as the `adaptive_hvac` custom integration (`custom_components/adaptive_hvac/`). The old
13-automation YAML system is fully replaced — **do not re-enable it**. The "design decision needed"
below was resolved in favour of a custom integration. Every goal listed is implemented: continuous
monitoring, per-zone targets and fan speeds, outdoor/indoor delta awareness (the relative gates), and
occupancy handling — though note occupancy deliberately gates *local fans only*, never the thermostat.
As of v0.4.0 outdoor air quality also gates the "open the windows" advice. Humidity is read per zone
but remains display-only; that is the one item from the original goal list not acted on.

Original text kept below for the record.

---

Current HVAC is fully rule-based automations (`hvac_cooling.json`, etc.) with hardcoded thresholds — snap decisions, no continuity. This breaks down in edge cases (e.g., windows open with cold outside air, temperature swings, multi-zone comfort balance).

**Goal:** Replace automations with an adaptive HVAC system (custom HACS integration or refactored template-based approach) similar to `adaptive_irrigation`:
- Continuous comfort monitoring instead of discrete trigger states
- Dynamic fan speed/setpoint based on how far from target
- Outdoor/indoor temp delta awareness (don't push cooler outside air when already below target)
- Humidity + occupancy factored in
- Smooth transitions instead of on/off/escalate snap states

**Design decision needed:** 
- Build custom integration (full control, more complex)?
- Refactor automations with templates + numerical helpers (faster, 80% of the way)?

---

## Adaptive HVAC — Winter Relative Gate — DEFERRED until Oct 2026 (before season flip)

**Revisit by: 2026-10-01** — that is when `winter_start_month = 10` flips the season and the winter
path starts actually running. Nothing to do before then; it cannot fire in summer either way.

**What's true today (2026-08-03):** the v0.4.0 winter relative gate ("warmer outside than the warmest
zone still asking → open windows instead of running heat") is implemented, unit-tested, deployed, and
**unreachable in production**. `heat_exterior_threshold` is evaluated first and sits at 60°F while
every zone target is 68–70°F, so reaching the relative gate would need `outdoor ≤ 60` **and**
`outdoor > 68` at once. Configuration, not a defect. Cooling has no equivalent problem: its 60°F
threshold sits *below* the 68–70°F targets, leaving a live 60–68°F window where its gate fires.

Left at the 60°F default deliberately rather than changed unilaterally — it directly changes when the
furnace runs, and that is a comfort/cost call, not a code call.

**When you come back to it, the decision is one of two:**

- **(a) Enable it** — raise `number.adaptive_hvac_heat_exterior_threshold` to ~72–75°F (dashboard
  slider, live, no restart). Effect: on a mild fall/spring day where it is warmer outside than the
  warmest room still asking for heat, the furnace holds off and you get an "open the windows" push
  instead. Watch for it being *too* eager in shoulder season — a 70°F afternoon following a 45°F
  morning could block heat while the house is still cold, though the zone still has to be below its
  target to be asking at all, which limits the damage.
- **(b) Leave it** — accept that `open_windows_warm` / `aqi_hold_heat` never fire, and the winter
  path stays window-sensor + exterior-threshold only. The feature is harmless dead weight in that
  case; do **not** delete the code, the unit tests are what document the intent.

**Verification recipe (works any time of year):** flip `select.adaptive_hvac_season_override` to
`winter`, override the outdoor sensor via `POST /api/states/sensor.outside_temperature`, then
`POST /api/services/adaptive_hvac/force_evaluate` and read `blocked_reason` off
`binary_sensor.adaptive_hvac_heating_blocked`. **Caveat:** toggling the season override walks
`_reset_setpoints_for_season_change`, which clears setpoint overrides — record
`number.adaptive_hvac_ac_setpoint` / `heat_setpoint` first and set them back after. It bit me on
2026-08-03 (AC setpoint silently went 72 → 68).

Already verified live 2026-08-03: the other three winter branches (`window_open_heat`, `outdoor_warm`,
and heat-allowed) all fire correctly, including the new behavior where an open window shuts the
furnace off.

---

## Adaptive HVAC — AQI Ceiling May Be Too Strict — PENDING (tune with real data)

`number.adaptive_hvac_aqi_threshold` defaults to **50** (EPA "Good"), which is what was asked for
("green"). Early evidence says that may be too shy: on deploy day (2026-08-03) local AQI read **59
with PM2.5 at only 4.4 µg/m³** — that is ozone driving the number, not smoke. Summer ozone will
routinely park the reading in the 50s–70s on days with genuinely clean air, suppressing
`binary_sensor.adaptive_hvac_windows_recommended` when opening up would have been fine.

**No change made** — the 50 was a deliberate user choice, and one data point is not a trend.

**When you come back:** watch how often `windows_recommended` is off *purely* because of AQI (its
attributes carry `aqi`, `aqi_ok`, `weather_ok` and both band edges, so the reason is visible). If
ozone is the recurring culprit, either raise the ceiling to ~75 (Moderate) or switch the gate to
PM2.5 — `sensor.outdoor_pm2_5` is already being collected by the same Open-Meteo REST call and is the
metric that actually matters for wildfire smoke. The PM2.5 option would need a small code change in
`coordinator._read_aqi()` / `_aqi_ok()`; the threshold change is just a slider.

## Security Dashboard — Gate Contact Sensors — PENDING

New `dashboard-security` Lovelace dashboard (2026-07-19) shows per-camera `picture-glance` cards for Front Porch, Garage bays/man door, Driveway, Back Field, Alley, Gazebo/Slider, Shed/Yard, Yard East, Yard West. See `/mnt/nas/ai-workspace/documentation/homeassistant/security_dashboard.md` for full layout and entity mapping.

**Gap:** none of the yard gates (Alley, Yard East, Yard West, Driveway, Back Field, Gazebo slider) have a physical contact sensor today — those cards currently only show camera motion/CO detection, no open/closed state or lock button.

**Install priority (user-set, 2026-07-19):**
1. [ ] Front Door — supplement existing `lock.front_porch_door_lock`/actuator with a dedicated contact sensor
2. [ ] Gazebo / Slider
3. [ ] Yard East
4. [ ] Yard West
5. [ ] Driveway
6. [ ] Fridge/Doors (garage man door + garage-to-house entrance)
7. [ ] Garage bay doors (Lexus/Pony) — last, lowest priority (covers already report open/closed via `cover` entity)

**Next steps once hardware is installed (per gate, in priority order above):**
- [ ] Pair contact sensor, run `entities_by_area.md` `refresh.sh` to confirm entity ID/area
- [ ] Add the new `binary_sensor` to the matching `picture-glance` card's entity list
- [ ] Update `security_dashboard.md` entity table
- [ ] Consider promoting frequently-checked gates to the dashboard's top status tile row (same treatment as the existing locks/covers)

---

## Speaker Zones Follow-Me Audio — HIGH PRIORITY

Current implementation is a single 404-line `speaker_zones_follow_updated.json` automation with 10 triggers and complex nested templates. Manual per-zone occupancy handling with hardcoded linger delays (main_floor 10min, second_floor 15min, etc.). Apple TV exclusion logic mixed into routing templates. Adding a zone or changing follow-me behavior requires template surgery.

**Goal:** Simplify audio routing and occupancy follow-me logic:
- Per-zone helper entities instead of monolithic template logic
- Configurable linger delays per zone (not hardcoded in automation)
- Separate source-routing logic from occupancy tracking
- Explicit Apple TV exclusion handling
- Service-based approach or custom integration for easier zone expansion

**Design options:**
- Refactor into modular per-zone automations + shared source-routing service
- Custom HACS integration (similar to irrigation) that owns occupancy → routing
- Leverage existing HA media router integrations if available

---

## Irrigation — Per-Zone Watering Windows — DONE (2026-05-17)

Currently the summer watering window is enforced globally (trigger at 5:30am, retry cutoff at 10am). Each zone should eventually have its own configurable window. This matters when e.g. the front yard should run later to avoid foot traffic, or a zone needs a different time due to sun exposure.

**Design sketch:**
- Add `input_datetime.irrigation_window_start_<zone>` and `input_datetime.irrigation_window_end_<zone>` helpers per zone
- Or a simpler `input_number.irrigation_window_end_hour_<zone>` (integer hour, e.g. 10)
- Change each zone's retry `if` condition and while loop to use the per-zone cutoff instead of hardcoded `now().hour < 10`
- Summer trigger remains at 5:30am; window start is implicitly "whenever the automation runs"
- Drip / garden watering (`drip_garden_watering`) also runs at 6am but timing hasn't been reviewed for this constraint

---

## Irrigation — Yard Middle Soil Sensor — IN PROGRESS

`sensor.middle_yard_soil_humidity` is unavailable (physical sensor dead/offline). Yard Middle zone (`adaptive_irrigation`) was reading from it → `sensor.adaptive_irrigation_yard_middle_moisture: unknown`.

**Fix applied:** Updated Yard Middle config entry options via `/api/config/config_entries/options/flow` to use `sensor.yard_east_soil_moisture` + `sensor.yard_west_soil_moisture` (average of East + West). Options are saved correctly in `core.config_entries`.

**Current blocker:** After options flow triggered the update_listener reload, a subsequent call to `homeassistant/reload_config_entry` service caused a second HA-managed reload that left all Yard Middle entities `unavailable`. The update_listener path (our custom `async_reload_entry`) works; the HA service-managed reload fails silently (entities unavailable, entry state shows `loaded`).

**Next steps:**
- [ ] Trigger fresh reload via options change (trivial value change → revert) to use the working update_listener path — do NOT call `homeassistant/reload_config_entry` afterward
- [ ] Verify `sensor.adaptive_irrigation_yard_middle_moisture` shows ~78% (avg of East 79% + West 77%)
- [ ] Investigate root cause: why does HA-managed reload fail for Yard Middle but not East/West? Likely `async_config_entry_first_refresh()` timing issue — consider wrapping first_refresh exceptions in `async_setup_entry` with retry logic
- [ ] Long-term: replace unavailable `sensor.middle_yard_soil_humidity` with a template sensor that computes E+W average, so the zone has a "real" sensor entity (allows removing the multi-sensor workaround)

**Status check (2026-08-03):** `sensor.yard_west_middle_soil_moisture` is live and reporting (75% at 15:55 UTC); `sensor.middle_yard_soil_humidity` is still `unavailable` (last update 06:54 UTC). The coordinator averages available sensors, so Yard Middle currently reads correctly off the one surviving sensor — the zone is not blind today.

**New dependency (2026-08-03):** `script.backyard_recovery_deep_soak` (Recovery Catchup Soak) now gates each zone on `adaptive_irrigation_<zone>_moisture < <zone>_soil_threshold`, **fail-open** on bad data. If Yard Middle's remaining sensor also drops, the zone will be watered on every catchup run with no gate protection. That raises the priority of the "replace the dead sensor with a template E+W average" item above — it restores redundancy, not just a nicer entity.

---

## Irrigation — East Sensor Staleness — PENDING

East yard soil sensor (`sensor.yard_east_soil_moisture`) stopped reporting overnight (last update ~11pm MDT), causing the 5:30am automation to see it as stale and fall back to a 6-minute survival dose. Sensor hardware is fine; Zigbee integration dropped the connection.

Also: `sensor.east_yard_soil_sensor_evapotranspiration` goes `unknown` when the parent sensor is stale — this is a calculated value from the Third Reality integration.

**Staleness window extended from 4h → 8h as a workaround.** Long-term: investigate why the Zigbee sensor drops overnight. Check coordinator health, sensor battery, and reporting interval config in the Zigbee integration.

---

## HVAC Fan Lock — DONE (2026-05-16)

Implemented via counter-automation pattern (no YAML surgery). Helpers in `configuration.yaml`. Automations:
- `fan_lock_set_claimed` — user turns on/adjusts fan → sets flag + stores speed
- `fan_lock_clear_claimed` — fan turns off → clears flag
- `fan_lock_restore` — HVAC overrides a claimed fan → restores user speed (detects via context.parent_id)
- `hvac_living_room_fan_comfort` + `garage_fan_cooling_on/off` — updated with fan_user_claimed condition

**Known edge case:** Physical switch presses (no user_id, no parent_id) are NOT treated as user claims — they bypass the lock. If this becomes an issue, revisit context detection.

---

## Garage Occupied Group — DONE (2026-05-16)

User manually updated via HA UI. `binary_sensor.garage_occupied` now includes `binary_sensor.garage_presence_presence`.

---

## Irrigation Dashboard — Run All Zones Button — DONE (2026-05-16)

Button card added to irrigation dashboard (`dashboard-irrigation`) via websocket API. Calls `script.run_all_zones_5min` (East → Middle → West → Front, 5 min each, 10s gap). REST API returned 404 for this dashboard — websocket `lovelace/config/save` is the correct method.

---

## Garage Apple TV — Entity Rename — DONE

`media_player.garage_apple_tv` rename confirmed complete by user.

---

## Adaptive HVAC v0.3.3 — Pending

### Cleanup
- [x] Stale `switch.adaptive_hvac_calebs_office_auto` (no `_2`) — already in `deleted_entities` (verified 2026-10-10)
- [ ] Rename `binary_sensor.windows_assumed_open_2` → `windows_assumed_open` in entity registry now that the old broken one is deleted

### Deferred features (parking lot)
- [ ] **Occupancy setback** — away 8h+ → cool to 76°F / heat to 62°F; parked from v0.3.0, low priority
- [ ] **Fan lock integration** — zone coordinator reads `fan_config` entries with `fan_lock_entity` flags; verify fan lock automations (`fan_lock_set_claimed`, etc.) still work with v0.3.x fan dispatch
- [ ] **Winter heating test** — verify heat gating works when outdoor drops below 60°F; season override select can force "winter" for testing
- [ ] **Zone performance analyzer** — diagnostic tool for reviewing per-zone thermal trends; see `memory/zone_performance_analyzer_plan.md`

---

## Master Bath — Shower-Triggered 100% Underlights — IDEA (analysis done 2026-08-09, not built)

**Goal:** Tia manually pushes `light.master_bath_underlights` to 100% when showering because Adaptive
Lighting dims it after sundown. That manual push is what trips AL's `take_over_control` lock
(`autoreset_control_seconds: 0`), which is the root cause of the recurring "underlights
unexpectedly dim" bug. Automating the boost removes the manual push, and with it the lockout.

### Decide this first (blocks everything below)
- [ ] **IDEA: When is Tia actually reaching for the dimmer — at 90% or at 20%?** Determines
      whether any of the Flume work is needed at all.
  - If the pain is the **evening 90%**: the whole feature collapses to a one-line config change,
    `min_brightness: 90 → 100` on the Master Bathroom AL entry
    (`entry_id 01KDV372PDFT13NQJGM6CXHV3Q`). AL then never dims while awake, `sleep_brightness: 20`
    still covers night trips, no shower detection needed.
  - If the pain is the **post-bedtime 20%** (AL sleep mode on): needs an actual trigger, gated on
    `switch.adaptive_lighting_sleep_mode_master_bathroom` being on — NOT a clock window.
  - Middle option: `min_brightness: 100` **plus** a dumb sleep-mode rule (bath occupied 2+ min
    while AL sleep mode on → 100%). Responds in ~2 min vs ~6, no cloud-API dependency.

### Flume shower detector (validated, only needed for the sleep-mode case)
Backtested over 11.6 days of recorder history (Jul 29 – Aug 8), 10 bedtime events:
- Signature: **2.0–3.8 gal/min sustained, 12–19 min, 41–55 gal**, with a distinctive two-stage
  profile (~3.5 gal/min for 5–8 min, then a flat ~2.25 gal/min).
- Shower **ends 8–15 min before** `input_boolean.master_suite_sleep_posture` flips on, every
  night except Aug 1 — tighter predictor than start time.
- Live rule: `sensor.flume_sensor_billings_home_current` >= 2.0 for 4 min
  + `binary_sensor.master_bathroom_presence` on
  + (sun below horizon OR AL sleep mode on)
  → **10/10 showers caught, 2 false positives** (both plausibly real showers). Daytime false
  positives are harmless no-ops because AL is already at 100% when the sun is up.
- [ ] **Known weakness: latency.** Flume polls ~60s and the API reports on a lag, so a 4-min
      sustain lands the boost ~5-6 min into a 12-19 min shower. Fine for evening showers,
      too slow for anything short.

### Implementation notes (if built)
- [ ] Boost MUST be guarded by a flag (new `input_boolean.master_bath_shower_boost`), mirroring
      the existing `input_boolean.master_bath_dimmer_sync` pattern.
- [ ] Release MUST call `adaptive_lighting.set_manual_control` (`manual_control: false`) then
      `adaptive_lighting.apply` — otherwise the boost itself recreates the lockout it exists to
      prevent.
- [ ] Add `master_bath_shower_boost` = off as a condition on
      `automation.master_bath_reassert_adaptive_brightness_on_external_command` (id
      `1785024035854`) so it doesn't fight the boost.
- [ ] Needs a safety release (flag on > 45 min) so a stuck flag can't pin the lights at 100%.

### Side findings
- [ ] **`switch.adaptive_lighting_master_bathroom` is currently locked out** —
      `manual_control: ['light.master_bath_underlights']` as of 2026-08-09. The 2026-07-26 bug is live
      right now; underlights will not adapt until cleared. Check
      `automation.master_bath_detect_unexpected_dim_underlights_diagnostic` for the cause.
- [ ] The daily 05:05–05:25 water flow is **irrigation, not a morning shower** (same minute daily,
      consistent 16–22 gal, no bath presence). All real showers in the sample are evening.
- [ ] Recorder only retains ~11 days, not 14 — sample is 10 showers. Re-validate on more data
      before trusting the thresholds hard.

## Under-Bed Light — Redesign to State-Driven — PENDING (planned 2026-08-10)

Full plan: `/home/cscansen/.claude/plans/agile-weaving-umbrella.md`

`automation.master_bedroom_under_bed_night_motion` (id `1769916429783`) is edge-driven, so every
fix this session added another trigger or branch. Currently 5 triggers, 3 branches, 1 known hole.
Rewrite it as a single invariant: *during night mode the under-bed light is on exactly when
someone who is home is out of bed and inside the suite.*

- [ ] Add template binary sensor `master_suite_night_light_needed` to `/homeassistant/templates.yaml`
      (`posture and here and (tia_out or caleb_out)`), `delay_on: 20s` / `delay_off: 5s`.
- [ ] Add template binary sensor `master_suite_all_in_bed` (`posture and not someone_out`, no
      `here`), `delay_on: 5s` / `delay_off: 20s` — drives the bath-light kill.
- [ ] Rewrite automation `1769916429783` to 3 triggers, **0 conditions** (posture moves inside the
      sensors, which is what kills the 45s arming race).

### Why this shape
- Per-person entities already exist and are unused: `bed_occupied_left` = Tia, `_right` = Caleb,
  plus `tia_home` / `caleb_home`. Knowing *who* is out of bed closes the "both up, one returns"
  hole with no state-tracking.
- `binary_sensor.master_bedroom_occupied` is a group that **includes** `master_bathroom_presence`
  and **excludes** the bed — so "in the suite" already covers bathroom trips and going downstairs.

### Constraints that must survive the rewrite
- [ ] `light.turn_on` carries **no brightness** — under-bed is an Adaptive Lighting member
      (`take_over_control: true`, `autoreset_control_seconds: 0`); any brightness locks AL out
      permanently, same trap as the 2026-07-26 master bath bug.
- [ ] **No `transition`** on any light call.
- [ ] Do not touch the 4 existing `master_bed_*_in_bed` templates (consumed by posture arming and
      the bath automation), and do not touch daytime behavior (under-bed is in
      `light.master_bedroom_manual_lights`, driven by `automation.master_bedroom_occupancy_lights`).

### Known-good baseline (deployed 2026-08-10, works, just fragile)
- Raw bed sensors with `for:` 20s leaving / 5s returning. The `master_bed_*_in_bed` templates are
  unusable as triggers here — `delay_off` 90s/120s would light the room two minutes after you got up.
- Bath lights die only on `return_couple`; `return_solo` can fire while a partner is still in the
  bathroom and `automation.master_bath_underlights_occupancy_lux` cannot recover (its `mb_on` needs
  a presence off→on edge that never comes while they stand there).
