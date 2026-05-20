# HVAC Automation Review

**Automation Group Tag:** `HVAC`  
**Implemented:** May 2026  
**Summer Review:** August 1, 2026  
**Heating Review:** December 1, 2026  

---

## What This Automation Does

Single-zone HVAC management with passive-first cooling philosophy:

1. **Free cooling** — when outside < inside and outside < 68°F, fans run to draw in cool air
2. **Passive cooling** — when outside ≥ 68°F but still cooler than inside, fans + air handler circulate
3. **Active cooling** — AC engages only when passive cooling fails (30 min, <1°F drop) AND outside > inside + 10°F AND outside > 82°F
4. **Heating** — Oct–Mar, triggers at 50°F inside (emergency floor any time); fan circulation equalizes upstairs/downstairs delta
5. **Setbacks** — unoccupied 12hr → AC 76°F / heat 62°F; night mode → heat 62°F; 6am warmup → 68°F

Fan speed gradient: 25% at 65°F → linear 33–100% from 72–78°F → off below 65°F  
Master bedroom fan excluded (managed by Night Mode: Master Bedroom Fan Control)

---

## Success Criteria

### Cooling Season (review August 1, 2026)

| Metric | Target | How to Check |
|---|---|---|
| AC hours per hot day (outside > 82°F) | < 4 hrs/day average | HA energy dashboard or thermostat history |
| Office temp during occupied hours | ≤ 76°F without AC running | `sensor.caleb_s_office_hygrometer_temperature` history |
| Passive cooling success rate | Office drops ≥ 1°F OR upstairs/downstairs delta shrinks ≥ 1°F within 30 min, at least 60% of triggers | Automation trace logs |
| Manual AC overrides | < 3 per month | `input_boolean.hvac_manual_override` history |
| False AC activations | 0 — AC should never run when outside < inside | Verify in automation traces |
| Upstairs/downstairs delta during AC | < 5°F while AC + fans running | Compare office vs thermostat temp sensors |

### Heating Season (review December 1, 2026)

| Metric | Target | How to Check |
|---|---|---|
| Upstairs/downstairs delta while heating | < 5°F with fan circulation on | Temp sensor history |
| Emergency heat triggers (office < 50°F) | 0 — heat should engage before that in Oct–Mar | Automation trace logs |
| Morning warmup (6am to 68°F) | Reaches 68°F within 45 min | Thermostat temp history |
| Night setback comfort | No manual overrides of 62°F setback | `hvac_manual_override` history |
| Manual heat overrides | < 2 per month | Override flag history |

### Year-Round

| Metric | Target |
|---|---|
| Automation fights (this vs night mode fan) | 0 — master bedroom fan must be fully independent |
| Thermostat left in wrong mode | 0 — seasonal gate transitions (Apr, May, Oct) should be clean |
| House occupied flag accuracy | Matches actual occupancy — no false 12hr setbacks when home |

---

## Tuning Knobs (adjust before declaring failure)

Before calling something broken, try adjusting these first:

- **Fan turn-on temp** — currently 72°F; lower if cooling feels too slow to start
- **Passive cooling window** — currently 30 min; shorten if house heats up fast
- **AC fallback delta** — currently outside > inside + 10°F; if AC never triggers on genuinely hot days, lower to +7°F
- **Heating circulation delta** — currently 5°F upstairs vs downstairs; tighten to 3°F if second floor stays cold
- **Occupancy setback timer** — currently 12 hrs; shorten if house is frequently unoccupied mid-day

---

## Observations Log

*Add notes here as the season progresses.*

### May–July 2026
- 

### August 2026 Review Notes
- 

### October–November 2026
- 

### December 2026 Review Notes
- 

---

## Entities Reference

| Role | Entity |
|---|---|
| Upstairs temp (primary) | `sensor.caleb_s_office_hygrometer_temperature` |
| Downstairs temp | `sensor.downstairs_thermostat_temperature` |
| Outside temp | `weather.home` (temperature attribute) |
| Thermostat | `climate.downstairs_thermostat` |
| Upstairs fans | `fan.caleb_office_ceiling`, `fan.tia_office_ceiling_fan` |
| Night mode | `input_boolean.master_suite_sleep_posture` |
| Manual override flag | `input_boolean.hvac_manual_override` |
| Managed cooling flag | `input_boolean.hvac_managed_cooling` |
| Managed heating flag | `input_boolean.hvac_managed_heating` |
| House occupied | `input_boolean.house_occupied` |
