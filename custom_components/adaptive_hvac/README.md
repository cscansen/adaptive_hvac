# Adaptive HVAC

A custom Home Assistant integration for simple, reliable whole-house HVAC control. One thermostat, multiple rooms, ceiling fans that actually follow what you want.

## What it does

- Sets the thermostat to **cool** when any room gets too warm, **heat** when any room gets too cold
- Controls **ceiling fans per room** — on when the room is above your target temp, off when it's not
- Respects **who owns what**: if you manually set a fan, the integration leaves it alone until midnight
- Lets you (or Tia) adjust the thermostat setpoint from the faceplate or app — it adopts your setting and keeps using it
- Never turns the AC off on a cool-but-sunny day when it's 80°F inside (the bug that prompted this rewrite)

## How it decides

**Each room (zone):**
- Above target temp → fan on, request cooling from system
- At or below target temp → fan off
- Room unoccupied → fan off regardless (occupancy never blocks the thermostat)

**System (thermostat):**
- Summer: run AC if any room needs it AND outdoor temp ≥ exterior threshold (default 60°F, raise to 65–68°F for "windows open" weather) — or any room is 5°F above its target (indoor override bypasses the threshold)
- Summer: AC also blocked if any zone's window sensor is open (actual contact sensor; emergencies bypass this)
- Winter: run heat if any room needs it AND outdoor temp ≤ 60°F
- All thresholds are configurable; exterior threshold is a live dashboard slider

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
| Weather | — | Optional. Used for outdoor temp |
| Sleep posture | — | Optional. Tracked but not used for control |
| Occupancy sensors | — | Optional. For future setback (not yet active) |
| AC setpoint | 68°F | What to cool to |
| Cool exterior threshold | 60°F | Don't AC if outdoor below this — raise to 65–68°F for "windows open" weather |
| Cool interior override | 5°F | Bypass exterior threshold if any room is this many °F above its target |
| Emergency cool threshold | 85°F | Always cool above this regardless of gating |
| Heat setpoint | 68°F | What to heat to |
| Heat threshold | 68°F | Zone temp that triggers a heat request |
| Heat exterior threshold | 60°F | Don't heat if outdoor above this |
| Emergency heat threshold | 55°F | Always heat below this regardless of gating |
| Winter start month | October | Calendar month winter begins |
| Winter end month | April | Calendar month winter ends (summer = everything else) |

## Zone setup

| Setting | Default | Notes |
|---------|---------|-------|
| Zone name | — | Required. Used for entity naming |
| Temperature sensors | — | Required. Averaged if multiple |
| Humidity sensor | — | Optional |
| Window sensor | — | Optional. When open, blocks AC system-wide (emergencies bypass) |
| Occupancy sensor | — | Optional. Controls local fan only |
| Fans | — | Fan entities this zone controls |
| Zone target temp | 72°F | Fan on above this, fan off at/below |
| Fan speed | 50% | Speed when fan is running |

> **Do not add the thermostat's whole-house fan as a zone fan** — occupancy would turn it off incorrectly.

## Entities created

**System entry:**
| Entity | Description |
|--------|-------------|
| `sensor.adaptive_hvac_status` | Current decision + full reasoning |
| `sensor.adaptive_hvac_mode` | Thermostat mode (cool/heat/off) |
| `sensor.adaptive_hvac_season` | Current season (summer/winter) |
| `select.adaptive_hvac_season_override` | Force summer/winter for testing |
| `switch.adaptive_hvac_active` | Enable/disable the integration |
| `switch.adaptive_hvac_manual_override` | Pause all automation |
| `number.adaptive_hvac_ac_setpoint` | AC setpoint (live adjustable) |
| `number.adaptive_hvac_cool_exterior_threshold` | Outdoor temp below which AC is blocked (live adjustable, 40–80°F) |
| `number.adaptive_hvac_heat_setpoint` | Heat setpoint (live adjustable) |
| `number.adaptive_hvac_heat_threshold` | Heat trigger temp (live adjustable) |
| `number.adaptive_hvac_emergency_cool_threshold` | Emergency cool threshold |
| `number.adaptive_hvac_emergency_heat_threshold` | Emergency heat threshold |

**Each zone entry:**
| Entity | Description |
|--------|-------------|
| `sensor.{zone}_hvac_status` | Zone mode and current temp |
| `sensor.{zone}_temp_trend` | Temperature trend (°F/hr) |
| `switch.adaptive_hvac_{zone}_auto` | Auto-control toggle (OFF = integration skips this zone entirely) |
| `switch.adaptive_hvac_{zone}_fan_locked` | Fan lock — ON means user has claimed the fan; integration hands off until midnight |

## Fan lock

When a user manually turns on, adjusts, or turns off a ceiling fan, the integration detects the change (via `context.user_id`) and claims that zone's fans:

- **Fan turned ON** — integration preserves your speed and won't override it
- **Fan adjusted** — new speed stored, integration continues to leave it alone
- **Fan turned OFF** — integration won't turn it back on (suppressed until midnight)
- **Midnight** — all fan locks clear automatically; normal control resumes
- **Manual release** — toggle `switch.adaptive_hvac_{zone}_fan_locked` OFF at any time to release immediately

> **Physical switch presses** (wall dimmer, etc.) have no HA context — they are not detected and do not set the lock. The integration can still override a fan set via physical switch.

## Thermostat setpoint ownership

When you adjust the thermostat setpoint from a physical control, the app, or HomeKit, the integration detects the change and adopts it as the new target for the current season. It persists across restarts. When the season changes (e.g., summer → winter), it resets to your configured default so you don't carry a summer cooling target into winter.

## Diagnosing decisions

The `sensor.adaptive_hvac_status` entity carries a `reasoning` attribute that shows the full decision tree on every poll:

```
Season: summer | Outdoor: 78.0°F | AC allowed: outdoor 78.0°F ≥ 60.0°F
```

Force an immediate evaluation:
```yaml
service: adaptive_hvac.force_evaluate
```

Or via curl:
```bash
curl -s -X POST http://homeassistant.local:8123/api/services/adaptive_hvac/force_evaluate \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" -d '{}'
```

## Troubleshooting

**System entities show unavailable after install**
Ensure you are running HA 2024.1.0 or later. The coordinator requires `config_entry` to be passed in `DataUpdateCoordinator.__init__` — older HA versions are not supported.

**"No zone data available"**
Normal for ~3 minutes after startup — the system coordinator polls on a 3-minute cycle. Use Force Evaluate to trigger immediately.

**Zone shows SENSOR FAILSAFE**
Temperature sensor is returning 0 or unavailable. Check the entity IDs configured for the zone and confirm the sensors are reporting.

**AC won't turn on even though it's hot**
Check `sensor.adaptive_hvac_status` reasoning attribute. Common causes:
- Outdoor temp below `cool_exterior_threshold` AND no room is 5°F above its target
- A zone's window sensor is reporting open
- `switch.adaptive_hvac_active` is off
- `switch.adaptive_hvac_manual_override` is on

**Fan not responding**
- Check zone's auto-control switch (`switch.adaptive_hvac_{zone}_auto`) is ON
- Check if the fan lock switch (`switch.adaptive_hvac_{zone}_fan_locked`) is ON — toggle it OFF to release

## License

MIT — see [LICENSE](LICENSE)
