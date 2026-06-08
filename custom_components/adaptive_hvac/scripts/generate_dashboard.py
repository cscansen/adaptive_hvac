#!/usr/bin/env python3
"""
Adaptive HVAC — Dashboard Generator

Two modes:

  --local   Runs ON the HA host. Reads config directly from HA storage files.
            No token or network access required. Writes the dashboard file in
            place. Intended to be called from an HA shell_command; the HA
            Script entity fires lovelace_updated after this exits.

  (remote)  Runs on any machine with network access to HA. Reads zone config
            via the REST API (requires HA_TOKEN). Deploys via file output or
            SSH.

Usage — local (on HA host, no token needed):
    python3 generate_dashboard.py --local

Usage — remote (from a dev machine):
    export HA_URL=http://homeassistant.local:8123
    export HA_TOKEN=<long-lived access token>
    python3 generate_dashboard.py [--output FILE | --stdout | --ssh USER@HOST]

Options:
    --local           Read/write HA storage files directly (no auth required)
    --ha-config DIR   HA config directory for --local (default: /config)
    --output FILE     Write JSON to FILE (default: dashboard_hvac.json)
    --stdout          Print JSON to stdout
    --ssh USER@HOST   Deploy via SSH to HA host
    --ssh-key FILE    SSH key for --ssh (default: ~/.ssh/id_rsa)
    --dry-run         Show card structure without writing anything
"""

import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from itertools import zip_longest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

args = sys.argv[1:]
LOCAL_MODE = "--local" in args
DRY_RUN = "--dry-run" in args
TO_STDOUT = "--stdout" in args
OUTPUT_FILE = "dashboard_hvac.json"
SSH_TARGET = None
SSH_KEY = os.path.expanduser("~/.ssh/id_rsa")
HA_CONFIG_DIR = "/config"

for i, a in enumerate(args):
    if a == "--output" and i + 1 < len(args):
        OUTPUT_FILE = args[i + 1]
    if a == "--ssh" and i + 1 < len(args):
        SSH_TARGET = args[i + 1]
    if a == "--ssh-key" and i + 1 < len(args):
        SSH_KEY = args[i + 1]
    if a == "--ha-config" and i + 1 < len(args):
        HA_CONFIG_DIR = args[i + 1]

DASHBOARD_KEY = "lovelace.dashboard_hvac"
STORAGE_DIR = os.path.join(HA_CONFIG_DIR, ".storage")
DASHBOARD_PATH = os.path.join(STORAGE_DIR, DASHBOARD_KEY)

# Remote-mode settings from environment
HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")


# ---------------------------------------------------------------------------
# Shared utility
# ---------------------------------------------------------------------------

def zone_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_"))


# ---------------------------------------------------------------------------
# LOCAL MODE — read directly from HA storage files (no token needed)
# ---------------------------------------------------------------------------

def local_read_config_entries() -> list[dict]:
    path = os.path.join(STORAGE_DIR, "core.config_entries")
    with open(path) as f:
        data = json.load(f)
    return [
        e for e in data["data"]["entries"]
        if e["domain"] == "adaptive_hvac"
    ]


def local_read_entity_registry() -> list[dict]:
    path = os.path.join(STORAGE_DIR, "core.entity_registry")
    with open(path) as f:
        data = json.load(f)
    return data["data"]["entities"]


def local_get_config(entry: dict) -> dict:
    return {**entry.get("data", {}), **entry.get("options", {})}


def local_discover_zones(entries: list[dict], entity_registry: list[dict]) -> list[dict]:
    """Build zone list from config entries + entity registry (no live state needed)."""
    zone_entries = [e for e in entries if local_get_config(e).get("entry_type") == "zone"]
    all_entity_ids = {e["entity_id"] for e in entity_registry}

    zones = []
    for entry in zone_entries:
        cfg = local_get_config(entry)
        name = entry["title"]
        slug = zone_slug(name)
        zones.append({
            "title": name,
            "slug": slug,
            "attrs": {
                "temp_sensors": cfg.get("temp_sensors", []),
                "fans": cfg.get("fans", []),
                "floor": cfg.get("floor", ""),
                "affects_thermostat": cfg.get("affects_thermostat", True),
                "zone_target_temp": cfg.get("zone_target_temp", 72.0),
            },
            "all_ids": all_entity_ids,
        })
    return zones


def local_get_system_cfg(entries: list[dict]) -> dict:
    system = next(
        (e for e in entries if local_get_config(e).get("entry_type") == "system"), {}
    )
    cfg = local_get_config(system)
    return {
        "thermostat": cfg.get("thermostat_entity", "climate.downstairs_thermostat"),
        "outdoor": cfg.get("outdoor_temp_sensor") or cfg.get("weather_entity", "weather.home"),
    }


# ---------------------------------------------------------------------------
# REMOTE MODE — REST API
# ---------------------------------------------------------------------------

def ha_get(path: str) -> object:
    if not HA_TOKEN:
        sys.exit("HA_TOKEN is not set.\n  export HA_TOKEN=<long-lived access token>")
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        headers={"Authorization": f"Bearer {HA_TOKEN}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HA API error {e.code} on {path}: {e.read().decode()}")


def ha_post(path: str, data: dict = None) -> None:
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        print(f"  Warning: POST {path} returned {e.code}", file=sys.stderr)


def remote_discover_zones(states: list[dict]) -> list[dict]:
    all_ids = {s["entity_id"] for s in states}
    auto_switches = {s["entity_id"] for s in states if "_auto" in s["entity_id"] and "adaptive_hvac" in s["entity_id"]}

    zones = []
    for s in states:
        entity_id = s["entity_id"]
        if not (entity_id.startswith("sensor.") and entity_id.endswith("_hvac_status") and "adaptive_hvac" not in entity_id):
            continue
        slug = entity_id.removeprefix("sensor.").removesuffix("_hvac_status")
        if not any(f"adaptive_hvac_{slug}_auto" in sw for sw in auto_switches):
            continue
        attrs = s.get("attributes", {})
        raw = attrs.get("friendly_name", slug.replace("_", " ").title())
        title = re.sub(r"\s+HVAC\s+Status$", "", raw, flags=re.IGNORECASE).strip()
        zones.append({"title": title, "slug": slug, "attrs": attrs, "all_ids": all_ids})
    return zones


def remote_get_system_cfg(states: list[dict]) -> dict:
    system = next((s for s in states if s["entity_id"] == "sensor.adaptive_hvac_status"), {})
    attrs = system.get("attributes", {})
    return {
        "thermostat": attrs.get("thermostat_entity", "climate.downstairs_thermostat"),
        "outdoor": attrs.get("outdoor_temp_sensor") or attrs.get("weather_entity", "weather.home"),
    }


# ---------------------------------------------------------------------------
# Entity resolution
# ---------------------------------------------------------------------------

def resolve_switch(slug: str, suffix: str, all_ids: set[str]) -> str:
    base = f"switch.adaptive_hvac_{slug}_{suffix}"
    for candidate in [base, f"{base}_2", f"{base}_3"]:
        if candidate in all_ids:
            return candidate
    return base


# ---------------------------------------------------------------------------
# Card builders
# ---------------------------------------------------------------------------

def markdown_card(zones: list[dict]) -> dict:
    lines = [
        "## Adaptive HVAC",
        "**Status:** {{ states('sensor.adaptive_hvac_status') }}",
        "",
        "**Fan:** {{ states('sensor.thermostat_fan_state') | upper }}",
        "",
        "**Reasoning:** {{ state_attr('sensor.adaptive_hvac_status', 'reasoning') or '—' }}",
    ]
    for z in zones:
        lines.append(f"\n**{z['title']}:** {{{{ states('sensor.{z['slug']}_hvac_status') }}}}")
    return {"type": "markdown", "content": "\n".join(lines)}


def system_glance_card(sys_cfg: dict) -> dict:
    thermostat = sys_cfg["thermostat"]
    outdoor = sys_cfg["outdoor"]
    base = thermostat.removeprefix("climate.")
    outdoor_entry = (
        {"entity": outdoor, "name": "Outdoor", "attribute": "temperature", "icon": "mdi:weather-partly-cloudy"}
        if outdoor.startswith("weather.")
        else {"entity": outdoor, "name": "Outdoor", "icon": "mdi:weather-partly-cloudy"}
    )
    return {
        "type": "glance",
        "title": "System",
        "show_name": True,
        "show_icon": True,
        "entities": [
            {"entity": "sensor.adaptive_hvac_season", "name": "Season", "icon": "mdi:calendar"},
            {"entity": "sensor.adaptive_hvac_mode", "name": "Mode", "icon": "mdi:hvac"},
            {"entity": thermostat, "name": "Setpoint", "attribute": "temperature", "icon": "mdi:thermometer"},
            {"entity": f"sensor.{base}_temperature", "name": "Therm Temp", "icon": "mdi:thermometer-lines"},
            {"entity": f"sensor.{base}_humidity", "name": "Humidity", "icon": "mdi:water-percent"},
            outdoor_entry,
            {"entity": thermostat, "name": "Fan", "attribute": "fan_mode", "icon": "mdi:fan"},
        ],
    }


def zone_card(zone: dict) -> dict:
    slug = zone["slug"]
    attrs = zone["attrs"]
    all_ids = zone["all_ids"]

    entities = [{"entity": f"sensor.{slug}_hvac_status", "name": "Status"}]

    for sensor in attrs.get("temp_sensors", [])[:1]:
        entities.append({"entity": sensor, "name": "Temp"})

    for fan in attrs.get("fans", []):
        entities.append({"entity": fan, "name": "Fan"})

    entities.append({"entity": resolve_switch(slug, "auto", all_ids), "name": "Auto"})
    entities.append({"entity": resolve_switch(slug, "fan_locked", all_ids), "name": "Fan Locked"})

    return {"type": "entities", "title": zone["title"], "entities": entities}


def zone_pairs(zone_cards: list[dict]) -> list[dict]:
    return [
        {"type": "horizontal-stack", "cards": [a] if b is None else [a, b]}
        for a, b in zip_longest(zone_cards[::2], zone_cards[1::2])
    ]


def floor_temps_glance(zones: list[dict]) -> dict:
    by_floor: dict[str, list] = {}
    no_floor = []
    for z in zones:
        sensors = z["attrs"].get("temp_sensors", [])
        if not sensors:
            continue
        floor = z["attrs"].get("floor", "")
        item = {"entity": sensors[0], "name": z["title"].split()[0]}
        (by_floor.setdefault(floor, []) if floor else no_floor).append(item)

    entities = [e for f in sorted(by_floor) for e in by_floor[f]] + no_floor
    return {"type": "glance", "title": "Zone Temperatures", "show_name": True, "entities": entities}


def history_graph_card(thermostat: str) -> dict:
    return {
        "type": "history-graph",
        "title": "Thermostat History (6h)",
        "hours_to_show": 6,
        "entities": [
            {"entity": thermostat, "name": "HVAC Mode"},
            {"entity": "number.adaptive_hvac_ac_setpoint", "name": "AC Setpoint"},
            {"entity": "sensor.thermostat_fan_state", "name": "Fan"},
            {"entity": "sensor.adaptive_hvac_mode", "name": "Integration Mode"},
        ],
    }


def controls_card() -> dict:
    return {
        "type": "entities",
        "title": "Controls",
        "entities": [
            {"entity": "switch.adaptive_hvac_active", "name": "Active"},
            {"entity": "switch.adaptive_hvac_manual_override", "name": "Manual Override"},
            {"entity": "select.adaptive_hvac_season_override", "name": "Season Override"},
        ],
    }


def setpoints_card() -> dict:
    return {
        "type": "entities",
        "title": "Setpoints & Thresholds",
        "entities": [
            {"entity": "number.adaptive_hvac_ac_setpoint", "name": "AC Setpoint"},
            {"entity": "number.adaptive_hvac_upstairs_demand_boost", "name": "Demand Boost"},
            {"entity": "number.adaptive_hvac_fan_circulation_delta", "name": "Floor Circ. Delta"},
            {"entity": "number.adaptive_hvac_cool_exterior_threshold", "name": "AC Exterior Gate"},
            {"entity": "number.adaptive_hvac_heat_setpoint", "name": "Heat Setpoint"},
            {"entity": "number.adaptive_hvac_heat_threshold", "name": "Heat Trigger"},
            {"entity": "number.adaptive_hvac_emergency_cool_threshold", "name": "Emergency Cool"},
            {"entity": "number.adaptive_hvac_emergency_heat_threshold", "name": "Emergency Heat"},
        ],
    }


def logbook_card(thermostat: str) -> dict:
    return {
        "type": "logbook",
        "title": "Event Log (24h)",
        "hours_to_show": 24,
        "entities": [thermostat, "sensor.adaptive_hvac_mode"],
    }


def force_evaluate_button() -> dict:
    return {
        "type": "button",
        "name": "Force Evaluate Now",
        "icon": "mdi:refresh",
        "tap_action": {"action": "call-service", "service": "adaptive_hvac.force_evaluate", "data": {}},
    }


def rebuild_dashboard_button() -> dict:
    return {
        "type": "button",
        "name": "Rebuild Dashboard",
        "icon": "mdi:view-dashboard-edit",
        "tap_action": {"action": "call-service", "service": "script.rebuild_hvac_dashboard", "data": {}},
    }


# ---------------------------------------------------------------------------
# Dashboard assembler
# ---------------------------------------------------------------------------

def build_dashboard(zones: list[dict], sys_cfg: dict) -> dict:
    thermostat = sys_cfg["thermostat"]
    z_cards = [zone_card(z) for z in zones]
    cards = [
        markdown_card(zones),
        system_glance_card(sys_cfg),
        *zone_pairs(z_cards),
        floor_temps_glance(zones),
        history_graph_card(thermostat),
        controls_card(),
        setpoints_card(),
        logbook_card(thermostat),
        force_evaluate_button(),
        rebuild_dashboard_button(),
    ]
    return {
        "version": 1,
        "minor_version": 1,
        "key": DASHBOARD_KEY,
        "data": {"config": {"views": [{"title": "HVAC", "path": "hvac", "icon": "mdi:thermostat", "cards": cards}]}},
    }


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

def write_local(dashboard: dict) -> None:
    payload = json.dumps(dashboard, indent=2, ensure_ascii=False)
    with open(DASHBOARD_PATH, "w") as f:
        f.write(payload)
    print(f"Wrote {DASHBOARD_PATH}")
    print("(HA Script will fire lovelace_updated — refresh your browser)")


def write_file(dashboard: dict) -> None:
    payload = json.dumps(dashboard, indent=2, ensure_ascii=False)
    with open(OUTPUT_FILE, "w") as f:
        f.write(payload)
    print(f"Wrote {OUTPUT_FILE}")
    print()
    print("Next steps — pick one:")
    print("  A) Settings → Dashboards → HVAC → ⋮ → Edit → Raw Config Editor, paste file contents")
    print("  B) python3 generate_dashboard.py --ssh user@ha-host --ssh-key ~/.ssh/id_rsa")


def deploy_ssh(dashboard: dict) -> None:
    payload = json.dumps(dashboard, indent=2, ensure_ascii=False)
    encoded = base64.b64encode(payload.encode()).decode()
    cmd = ["ssh"]
    if SSH_KEY:
        cmd += ["-i", SSH_KEY]
    cmd += [SSH_TARGET, f"echo '{encoded}' | base64 -d | sudo tee {DASHBOARD_PATH} > /dev/null"]
    subprocess.run(cmd, check=True)
    print(f"Wrote {DASHBOARD_PATH} on {SSH_TARGET}")
    ha_post("/api/events/lovelace_updated", {})
    print("Fired lovelace_updated — refresh your browser")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if LOCAL_MODE:
        print("Local mode — reading HA storage files directly (no token needed)")
        entries = local_read_config_entries()
        registry = local_read_entity_registry()
        zones = local_discover_zones(entries, registry)
        sys_cfg = local_get_system_cfg(entries)
    else:
        print("Remote mode — fetching from HA REST API...")
        states = ha_get("/api/states")
        print(f"  {len(states)} entities")
        zones = remote_discover_zones(states)
        sys_cfg = remote_get_system_cfg(states)

    if not zones:
        print("Warning: no zones found.", file=sys.stderr)
    for z in zones:
        floor = z["attrs"].get("floor") or "no floor"
        print(f"  • {z['title']} (floor={floor})")

    print(f"  thermostat={sys_cfg['thermostat']}, outdoor={sys_cfg['outdoor']}")
    dashboard = build_dashboard(zones, sys_cfg)
    card_count = len(dashboard["data"]["config"]["views"][0]["cards"])
    print(f"Building dashboard — {len(zones)} zones, {card_count} cards total")

    if DRY_RUN:
        for i, c in enumerate(dashboard["data"]["config"]["views"][0]["cards"]):
            if c["type"] == "horizontal-stack":
                print(f"  [{i}] stack: {[x.get('title') for x in c.get('cards', [])]}")
            else:
                print(f"  [{i}] {c['type']}: {c.get('title', c.get('name', ''))}")
        return

    if TO_STDOUT:
        print(json.dumps(dashboard, indent=2, ensure_ascii=False))
        return

    if LOCAL_MODE:
        write_local(dashboard)
    elif SSH_TARGET:
        deploy_ssh(dashboard)
    else:
        write_file(dashboard)


if __name__ == "__main__":
    main()
