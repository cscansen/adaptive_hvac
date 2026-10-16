# Adaptive HVAC — Dashboard Setup

The integration builds its own Lovelace dashboard from your live zone configuration
and entity registry. Nothing to copy, no token, no SSH, no restart.

## First-time setup

1. **Settings → Dashboards → Add dashboard → New dashboard from scratch.** Title it
   "HVAC" and set the URL to `dashboard-hvac`.
2. Run the action **`adaptive_hvac.rebuild_dashboard`** (Developer Tools → Actions).
   To use a different URL, pass `dashboard: <url>`.

After that, the dashboard's own **Rebuild dashboard** button (Tuning tab) does the same.
Rebuild whenever you add, remove or rename a zone.

> The rebuild **overwrites the whole dashboard**. Hand edits made in the dashboard
> editor are lost, so change `dashboard.py` instead.

## What you get

**Home tab** — the everyday view:
- Status headline and reasoning. Warning lines (system off, manual override,
  cooling/heating blocked, sweatshirt mode, night mode) appear only while active.
- Thermostat card, plus Sweatshirt mode and Night mode toggles.
- "Open the windows" tile, shown only when it's recommended.
- One section per zone: current temp and status, target temperature, ceiling-fan speed,
  an Automatic toggle, and a "Fan held — tap to release" tile shown only while a manual
  fan change has locked the fan.

**Tuning tab** — system switches (enabled, manual override, season override), setpoints
and thresholds, night schedule, sweatshirt threshold, air & windows band, 6-hour
history, 24-hour logbook, and the Force evaluate / Rebuild dashboard buttons.

> The night mode schedule and setpoint values are `number` entities with no other UI.
> Set them on the Tuning tab before relying on night mode.

Requires a Home Assistant version with the Sections dashboard layout and tile card
features (2024.8+).

## Thermostat fan history (optional template sensor)

The Tuning tab history graph includes `sensor.thermostat_fan_state` (whole-house fan on/off) when it exists.
If that sensor does not exist, add the following to your `templates.yaml`:

```yaml
- sensor:
    - name: "Thermostat Fan State"
      unique_id: thermostat_fan_state
      icon: mdi:fan
      state: >
        {% set m = state_attr('climate.downstairs_thermostat', 'fan_mode') %}
        {% if m == 'on' %}running{% elif m is not none %}auto{% else %}unknown{% endif %}
      availability: >
        {{ states('climate.downstairs_thermostat') not in ['unavailable','unknown'] }}
```

Replace `climate.downstairs_thermostat` with your thermostat entity ID.
After saving, reload template entities (**Developer Tools → Template**).
