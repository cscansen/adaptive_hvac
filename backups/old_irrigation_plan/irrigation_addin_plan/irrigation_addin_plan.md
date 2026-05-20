i # Plan: Adaptive Irrigation Integration

## Context

The current irrigation system is three 700-line JSON automations. Logic is hardcoded: thresholds, durations, weather rules, motion deferrals, fallbacks. Adding a zone or tuning behavior means editing deeply nested JSON. There's no historical data — every decision starts fresh with no memory of how fast soil dries, how much a minute of watering actually moves the needle, or whether the 92% threshold is right for this specific yard.

The goal is a Home Assistant custom integration (`adaptive_irrigation`) that:
- Manages zones, sensors, and watering logic in one place
- Uses HA-native storage (recorder history, RestoreEntity) — no external database
- Makes water-minimizing decisions based on soil trend + ET + weather forecast
- Exposes clean HA entities and services so automations become trivial (or unnecessary)
- Eventually replaces the current JSON automations entirely
- Distributed via HACS (private GitHub repo)

Reference architecture: `basnijholt/adaptive-lighting` — ConfigEntry per zone, background coordinator loop, switch/sensor entities per instance. Like adaptive-lighting, no external dependencies beyond HA itself.

---

## Architecture Overview

```
HA custom_components/adaptive_irrigation/
    __init__.py          — integration setup, config entry lifecycle
    config_flow.py       — UI: add/edit/delete zones
    coordinator.py       — DataUpdateCoordinator: poll sensors, decide, water
    sensor.py            — Virtual sensors: moisture_trend, et_today, status, last_watered, calibration
    switch.py            — Per-zone enable/disable switch
    logic.py             — Watering decision engine + ET calculation
    const.py             — Config keys, defaults
    manifest.json
    hacs.json
    services.yaml

HA-native storage (no external dependencies):
    Recorder history     — soil moisture trend (last 6h, queried via recorder.history API)
    RestoreEntity        — last_watered timestamp + calibration rate persist across restarts
    persistent_notification — per-zone run summaries (existing pattern from current automations)
```

---

## Phase 1 — Integration Skeleton + Passive Observation

**Goal:** Install the integration, create entities, observe sensor data. No watering logic yet. Current automations keep running.

### 1a. GitHub repo + HACS setup

- Create private GitHub repo: `cscansen/adaptive-irrigation`
- Add `hacs.json`:
```json
{
  "name": "Adaptive Irrigation",
  "content_type": "integration",
  "config_flow": true
}
```
- Add repo as custom HACS repository in HA (HACS → Integrations → ⋮ → Custom repositories)
- Dev workflow: edit source on NAS at `/mnt/nas/ai-workspace/homeassistant/adaptive_irrigation/`, push to GitHub, HACS update in HA UI

### 1b. Integration skeleton

**`manifest.json`**
```json
{
  "domain": "adaptive_irrigation",
  "name": "Adaptive Irrigation",
  "version": "0.1.0",
  "requirements": [],
  "dependencies": ["recorder"],
  "codeowners": ["@cscansen"],
  "iot_class": "local_polling",
  "config_flow": true
}
```

**`const.py`** — zone config keys:
- `CONF_ZONE_NAME`, `CONF_VALVE_SWITCH`, `CONF_SOIL_SENSORS` (list), `CONF_MOTION_SENSOR` (optional)
- `CONF_SOIL_THRESHOLD` (default 92), `CONF_MAX_DURATION` (default 20 min), `CONF_FALLBACK_DURATION` (default 6 min)
- `CONF_CROP_COEFFICIENT` — selector: lawn/0.8, mixed/0.9, garden/1.0, drip/0.6, custom
- `CONF_SENSOR_REQUIRED` (bool, default True) — False for drip zone (no soil sensor)
- `CONF_MIN_INTERVAL` (default 45 min) — prevents double-watering on restart
- `CONF_ENABLED` (bool)

**`config_flow.py`** — one step per zone:
- Zone name, valve switch entity, soil sensor(s), optional motion sensor, thresholds, crop coefficient, sensor_required flag
- No global step needed (no external service to configure)

**`coordinator.py`** — `DataUpdateCoordinator` subclass, polls every 15 min:
- Reads all soil sensors from HA state machine
- Computes moisture trend from recorder history (last 6h slope)
- Does NOT make watering decisions yet (Phase 1)

**`switch.py`** — `AdaptiveIrrigationZoneSwitch`:
- `switch.adaptive_irrigation_<zone_name>` — enable/disable auto-watering
- State persisted via HA entity registry

**`sensor.py`** — `AdaptiveIrrigationSensor` (RestoreEntity subclass) per zone:
- `sensor.adaptive_irrigation_<zone>_moisture` — current avg soil %
- `sensor.adaptive_irrigation_<zone>_trend` — %/hour computed from recorder history
- `sensor.adaptive_irrigation_<zone>_status` — human-readable text ("Idle", "Watered 2h ago", etc.)
- `sensor.adaptive_irrigation_<zone>_last_watered` — datetime, restored across restarts
- `sensor.adaptive_irrigation_<zone>_calibration` — moisture rise %/min, restored across restarts

### 1c. Recorder history query (trend calculation)

```python
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states

async def get_moisture_trend(hass, entity_id, hours=6) -> float | None:
    start = dt_util.utcnow() - timedelta(hours=hours)
    states = await get_instance(hass).async_add_executor_job(
        get_significant_states, hass, start, None, [entity_id]
    )
    readings = [(s.last_updated.timestamp(), float(s.state))
                for s in states.get(entity_id, [])
                if s.state not in ("unknown", "unavailable")]
    if len(readings) < 3:
        return None
    # linear regression slope in %/hour
    xs, ys = zip(*readings)
    n = len(xs)
    slope = (n*sum(x*y for x,y in zip(xs,ys)) - sum(xs)*sum(ys)) / \
            (n*sum(x**2 for x in xs) - sum(xs)**2)
    return slope * 3600  # convert per-second to per-hour
```

### 1d. Verification (Phase 1)
- Install via HACS → add integration via HA UI → config flow succeeds
- Zone switch + sensor entities appear in HA
- `sensor.adaptive_irrigation_east_trend` updates every 15 min with a non-null slope
- `sensor.adaptive_irrigation_east_moisture` matches raw sensor values

---

## Phase 2 — Smart Decision Engine (replaces current automations)

**Goal:** Integration makes all watering decisions. Current JSON automations are disabled.

### 2a. ET calculation (`logic.py`)

Use **Hargreaves-Samani** (simplified, no solar sensor needed):

```python
def hargreaves_et(temp_max_f, temp_min_f, lat, day_of_year) -> float:
    # Returns mm/day reference ET
    # Inputs from weather.home forecast attributes
```

Input from `weather.home` forecast: `temperature` (high), `templow` (low), `precipitation`, `wind_speed`, `humidity`.  
Home latitude from HA `homeassistant.config` (already in HA).

Net ET per zone = `reference_ET * crop_coefficient` (Kc) — Kc stored per zone in config (lawn=0.8, garden=1.0, drip/trees=0.6).

### 2b. Watering decision logic (`coordinator.py`)

Per zone, every 15-min poll:

```
1. If zone switch disabled → skip
2. Read current soil moisture (avg of zone's sensors)
3. If sensor unavailable/stale (>4h) → fallback mode: water CONF_FALLBACK_DURATION, log warning
4. If motion detected in zone → defer (record defer, retry next poll)
5. Compute moisture_trend from InfluxDB (last 6h slope)
6. Compute ET for today from weather forecast
7. Compute forecast_precip for next 24h
8. Decision:
   - If soil >= threshold AND trend >= 0: SKIP (wet enough, not drying)
   - If soil >= threshold AND trend < -0.5%/hr: MONITOR (will water before hitting threshold)
   - If soil < threshold: WATER
   - If forecast_precip >= 0.15in AND soil > 85%: SKIP (rain coming, soil ok)
   - If wind > 25mph: DEFER to next poll
9. Duration = calibrated_rate ? (target - current) / rate : base_duration + weather_adjustments
10. Post notification + write watering_event to InfluxDB
```

### 2c. Self-calibration (HA-native)

After each watering event, use `async_call_later(hass, 1800, callback)` to schedule a 30-min follow-up read:
- Compute `rise = soil_after - soil_before`, `rate = rise / duration_min`
- Update `sensor.adaptive_irrigation_<zone>_calibration` with exponential moving average: `new_cal = 0.8 * old_cal + 0.2 * rate` (weighted toward history until enough data exists)
- RestoreEntity persists `calibration` value across HA restarts
- Bootstrap: if `calibration` state is `unknown` (first run), use `CONF_FALLBACK_DURATION` instead of calibrated duration; log "calibration pending"

### 2d. Sensor entities (`sensor.py`)

Per zone (all defined in Phase 1, populated with real values in Phase 2):
- `sensor.adaptive_irrigation_<zone>_moisture` — current avg soil %
- `sensor.adaptive_irrigation_<zone>_et_today` — mm/day
- `sensor.adaptive_irrigation_<zone>_trend` — %/hour (from recorder history)
- `sensor.adaptive_irrigation_<zone>_last_watered` — datetime (RestoreEntity)
- `sensor.adaptive_irrigation_<zone>_calibration` — %/min rise rate (RestoreEntity)
- `sensor.adaptive_irrigation_<zone>_status` — text: "Watered 10 min ago", "Skipped — rain forecast", etc.

### 2e. Services (`services.yaml`)

```yaml
adaptive_irrigation.water_zone:
  fields: {zone_id, duration_minutes}  # manual override

adaptive_irrigation.evaluate_now:
  fields: {zone_id}  # force immediate evaluation

adaptive_irrigation.set_zone_config:
  fields: {zone_id, threshold, crop_coefficient, max_duration}  # runtime tuning
```

### 2f. Retire current automations

- Set `summer_watering_program`, `germination_watering_program`, `drip_garden_watering` to **disabled** in HA
- Keep JSON files in repo for reference
- Dashboard: replace "automation.summer_watering_program" entity rows with `sensor.adaptive_irrigation_*` entities

---

## Phase 3 — Dashboard + Optional Analytics

**Goal:** Close the loop with visibility into why decisions were made.

### 3a. HA irrigation dashboard updates
- Replace current markdown card with `sensor.adaptive_irrigation_*_status` entity cards
- Add history-graph cards per zone (soil moisture, trend) — powered by HA recorder, no external DB needed
- Add statistics cards: last watered, calibration rate, ET today

### 3b. Grafana (optional, add later)
If long-term trend analysis beyond HA recorder retention is wanted:
- Add InfluxDB as a HA add-on (Supervisor → Add-on Store → InfluxDB) — runs on HA host, no firewall changes
- Add optional `CONF_INFLUX_ENABLED` flag to coordinator; writes are additive and non-blocking
- Add Grafana as a HA add-on alongside InfluxDB
- This is a future enhancement, not required for v1

### 3c. Germination mode
- Add a `CONF_PROGRAM` option per zone: `summer | seedling | drip | off`
- Seedling: higher frequency (4x/day check instead of 1x), higher threshold (93%), lower max duration
- Handled inside coordinator decision loop — no separate automation needed

---

## File Locations

| Path | Purpose |
|------|---------|
| `/mnt/nas/ai-workspace/homeassistant/adaptive_irrigation/` | Dev source (NAS mount, git-tracked) |
| `github.com/cscansen/adaptive-irrigation` | Distribution repo (HACS source) |
| `/config/custom_components/adaptive_irrigation/` | Installed by HACS on HA host |
| `/mnt/nas/ai-workspace/homeassistant/summer_watering_program.json` | Kept for reference, disabled in HA after pilot |

## Implementation Order

1. Create GitHub repo, add `hacs.json`, add as custom HACS repo in HA
2. Write integration skeleton (manifest, const, config_flow, switch, sensor shells)
3. Install via HACS → verify config flow and entity creation
4. Wire up coordinator: soil sensor reads + recorder history trend
5. Implement ET calculation (`logic.py`) — test with `evaluate_now` on east zone
6. Implement decision engine — pilot east zone for 2 weeks alongside old automations
7. Implement calibration (RestoreEntity + async_call_later follow-up)
8. Expand to remaining zones one at a time, disable old automations last
9. Build HA dashboard with history-graph + status cards
10. Add seedling mode, drip zone (sensor-free) support
11. (Optional future) Add InfluxDB + Grafana as HA add-ons for long-term analytics

---

## Design Holes — Identified and Resolved

This section documents gaps found during planning review. Each item has a resolution so implementation can proceed without re-deriving these decisions.

### H1 — Firewall: IOT → Infra path missing
~~**Resolution:** Add firewall rule...~~  
**MOOT:** InfluxDB moved to HA add-on (runs on same host as HA). No cross-VLAN traffic. Connection is localhost:8086.

### H2 — InfluxDB v1/v2 query syntax confusion
**MOOT:** InfluxDB dropped entirely from v1. No Flux queries needed. HA recorder history API used instead.

### H3 — HA weather forecast API changed
**Problem:** Plan assumed forecast data in `weather.home` state attributes. HA 2024.x moved forecasts to a service call.  
**Resolution:** Call `weather.get_forecasts` via HA REST API: `POST /api/services/weather/get_forecasts` with `{"entity_id": "weather.home", "type": "daily"}`. Returns forecast list in service response. Do this once per coordinator cycle and cache the result.

### H4 — Blocking InfluxDB calls in async context
**MOOT:** No InfluxDB in v1. Recorder history query already uses `async_add_executor_job` pattern (shown in Phase 1c code).

### H5 — MONITOR state undefined
**Problem:** Decision logic named a MONITOR state but defined no action for it.  
**Resolution:** MONITOR means pre-emptive watering. When `soil >= threshold AND trend < -0.5%/hr`: compute hours until soil hits `threshold - 5%` at current trend; if <3h away, water now using calibrated duration. Otherwise log "monitoring — drying fast" and re-evaluate next poll. Prevents dry-out from happening between polls.

### H6 — Stale sensor detection
**Problem:** Checking `>4h` by value alone misidentifies stable soil as stale.  
**Resolution:** Check `state.last_updated` from the HA state object, not the value. If `now - last_updated > 4h`, treat as stale. Use `hass.states.get(entity_id).last_updated` in the coordinator.

### H7 — 30-min calibration follow-up scheduling
**Problem:** "Schedule a follow-up read" was undefined; `asyncio.sleep()` would block the event loop.  
**Resolution:** Use `async_call_later(hass, 1800, self._calibration_followup_callback)` immediately after a watering event completes. Callback reads current soil, computes rise/min, writes to InfluxDB calibration measurement.

### H8 — Germination "4x/day" vs 15-min poll rate
**Problem:** Seedling mode described as "higher frequency" but the coordinator already polls 96x/day. Frequency isn't the right lever.  
**Resolution:** Implement as time-window gates. In seedling mode, the coordinator only attempts watering during 4 windows: 06:00–06:30, 10:00–10:30, 14:00–14:30, 18:00–18:30 local time. Outside those windows the coordinator still runs (for sensor writes to InfluxDB) but skips the watering decision. Use `dt_util.now()` for timezone-aware comparison.

### H9 — Restart double-water risk
**Problem:** On HA restart, coordinator polls immediately; a recently-watered zone could get watered again.  
**Resolution:** On coordinator startup, call `query_last_watering(zone_id)` for each zone. If `now - last_watered < CONF_MIN_INTERVAL` (default: 45 min), skip watering decision on the first cycle. Log "skipped — watered N minutes ago at startup."

### H10 — Drip zone has no soil sensor
**Problem:** Integration architecture assumes soil sensors as core input; drip zone has none.  
**Resolution:** Add `CONF_SENSOR_REQUIRED` boolean to zone config (default: `True`). When `False`, skip moisture check entirely — decision based on ET + calendar (days since last watering vs. ET-derived interval). Config flow shows a "sensor-free mode" warning. Drip zone sets this `False` until a sensor is added.

### H11 — Crop coefficient (Kc) missing from config_flow
**Problem:** `CONF_CROP_COEFFICIENT` referenced in ET math but absent from the zone config step.  
**Resolution:** Add to zone config step. Present as a selector: `lawn (0.8)`, `mixed lawn+shrubs (0.9)`, `garden/vegetables (1.0)`, `drip/trees (0.6)`, `custom`. Custom allows float entry. Store in config entry options so it persists across restarts and is editable via the HA "Configure" button.

### H12 — Calibration bootstrap (no data for first 30 days)
**Resolution (updated):** RestoreEntity `calibration` sensor starts as `unknown`. Coordinator checks: if state is `unknown`, use `CONF_FALLBACK_DURATION`. After first watering event + follow-up read, exponential moving average begins. No minimum event count needed — EMA starts immediately and improves over time.

### H13 — InfluxDB unreachability
**MOOT:** No InfluxDB in v1. Recorder history is local and always available. If recorder returns no data (e.g., fresh HA install), trend returns `None` and coordinator falls back to threshold-only logic — same graceful degradation, zero external dependency.

### H14 — Two sources of truth (HA recorder vs InfluxDB)
**MOOT:** Single source of truth: HA recorder. Integration sensors are recorded automatically by HA. History-graph cards use recorder. No duplication.

### H15 — High-risk cutover
**Problem:** Disabling all three watering automations simultaneously risks the whole yard.  
**Resolution:** Pilot on east zone only for 2 weeks while `summer_watering_program` keeps running for middle/west/front. Compare integration watering events vs. old automation logs. Expand one zone at a time. Disable old automations only after all zones are verified on the integration.

### H16 — `influxdb-client` version pin
**Problem:** Hard pin `==1.44.0` risks conflicts with other integrations.  
**Resolution:** Use `influxdb-client>=1.40.0,<2.0.0`. The `<2.0.0` cap prevents accidental upgrade into the breaking v2 API series.

### H17 — No testing strategy
**Problem:** No test plan; custom integrations are easy to break silently.  
**Resolution:** Add `pytest-homeassistant-custom-component` as dev dependency. Unit-test `logic.py` (ET calculation, decision engine) as pure Python with no HA dependency. Integration tests use the custom-component harness to mock HA state machine. Minimum test surface: ET formula for known inputs, all 6 decision outcomes, calibration fallback behavior.

### H18 — Deployment: HACS custom repository
**Resolution:** Use HACS — same pattern as `adaptive-lighting`. Private GitHub repo (`cscansen/adaptive-irrigation`). Workflow: develop on NAS → push to GitHub → HACS update in HA UI. Semantic version tags for releases. `hacs.json` included in repo root. No manual file transfer needed.

---

## Open Questions (decide before starting Phase 2)

1. **Crop coefficient per zone** — Kc values needed: east/middle/west (lawn → 0.8), front (lawn+shrubs → 0.9), drip (trees/garden → 0.6). Confirm or adjust before wiring ET calculation.
2. **Drip zone** — no soil sensor. Will run ET + calendar only (`CONF_SENSOR_REQUIRED = False`). Add a soil sensor later or keep sensor-free permanently?
3. **Recorder retention** — default HA recorder purge is 10 days. Trend calc only needs 6h so this is fine. Calibration uses RestoreEntity (survives purge). No change needed unless you want longer soil history in HA UI.
4. **Grafana / long-term analytics** — optional Phase 3b. Decide after pilot phase whether the HA history-graph cards are sufficient or whether Grafana is worth adding.
