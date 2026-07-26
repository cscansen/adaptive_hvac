# Adaptive HVAC — Dashboard Setup

The dashboard generator script builds a fully populated Lovelace dashboard
from your live zone configuration. When you add, remove, or rename a zone,
re-run the script to regenerate it.

## Prerequisites

- Python 3.10 or newer (no third-party packages required)
- A [Long-Lived Access Token](https://my.home-assistant.io/redirect/profile/) from your HA profile
- The Adaptive HVAC integration loaded with at least one zone configured

## Setup

```bash
export HA_URL=http://homeassistant.local:8123   # adjust to your HA address
export HA_TOKEN=<your long-lived access token>
```

> Tip: add these to a `.env` file or your shell profile so you don't have to
> re-export them each time. Never commit a token to source control.

## Generate and deploy

### Option A — Copy-paste into Raw Config Editor (no SSH required)

```bash
python3 scripts/generate_dashboard.py
# → writes dashboard_hvac.json in the current directory
```

1. In HA: **Settings → Dashboards → HVAC → ⋮ → Edit dashboard → Raw Config Editor**
2. Select all existing content and delete it
3. Paste the contents of `dashboard_hvac.json`
4. Click **Save**

### Option B — SSH deploy (writes directly to HA storage)

If you have SSH access to your HA host:

```bash
python3 scripts/generate_dashboard.py \
  --ssh hassio@homeassistant.local \
  --ssh-key ~/.ssh/id_rsa
```

The script writes `/config/.storage/lovelace.dashboard_hvac` on the HA host
and fires a `lovelace_updated` event so the browser reloads automatically.

> **A full HA restart is required for changes to actually show up**, despite
> the `lovelace_updated` event and a browser refresh. HA appears to hold a
> server-side cached copy of the parsed dashboard config that a raw file
> overwrite doesn't invalidate — confirmed by deploying a change, verifying
> the storage file was byte-for-byte correct, and still seeing stale
> (previously-deleted) cards in the Companion app until HA was restarted.
> Refreshing the client alone is not enough.

### Other flags

| Flag | Description |
|------|-------------|
| `--output FILE` | Write JSON to `FILE` instead of `dashboard_hvac.json` |
| `--stdout` | Print JSON to stdout (useful for piping) |
| `--dry-run` | Show card structure without writing anything |

## What gets generated

The script reads your live entity states to discover zones — no manual
configuration is required. For each configured zone it creates:

- Status, temperature, and fan entity rows
- Auto-control and fan-lock switches
- Correct entity IDs regardless of HA's internal deduplication suffixes

The system section includes season, mode, setpoint, thermostat temperature,
outdoor temperature, humidity, controls, setpoint sliders, a night mode card
(toggle + night setpoint sliders), and a history graph.

## Running directly on the HA host (no token required)

If you have SSH access or are setting up an HA Script to trigger rebuilds from
the dashboard itself, use `--local` mode. This reads config and writes the
dashboard file directly — no network call or token needed.

```bash
python3 /config/scripts/generate_hvac_dashboard.py --local
```

### Wiring up a one-tap "Rebuild Dashboard" button in HA

1. **Copy the script to your HA config:**

   ```bash
   # From a machine with SSH access to HA
   scp scripts/generate_dashboard.py user@ha-host:/config/scripts/generate_hvac_dashboard.py
   ```

2. **Add to `configuration.yaml`:**

   ```yaml
   shell_command:
     rebuild_hvac_dashboard: "python3 /config/scripts/generate_hvac_dashboard.py --local"
   ```

3. **Add to `scripts.yaml`:**

   ```yaml
   rebuild_hvac_dashboard:
     alias: Rebuild HVAC Dashboard
     icon: mdi:view-dashboard-edit
     mode: single
     sequence:
       - action: shell_command.rebuild_hvac_dashboard
       - event: lovelace_updated
         event_data: {}
   ```

4. **Restart HA** (required to load `shell_command` for the first time).

The generated dashboard already includes a **Rebuild Dashboard** button card
that calls `script.rebuild_hvac_dashboard`. After the first manual setup, all
future rebuilds are one tap from the dashboard — still no token required.

## After adding or removing a zone

Re-run the generator and re-deploy (Option A or B). The dashboard reflects
whatever zones are currently active in the integration — nothing to edit by hand.

## Thermostat fan history (optional template sensor)

The history graph shows `sensor.thermostat_fan_state` for fan on/off history.
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
