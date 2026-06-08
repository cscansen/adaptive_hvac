#!/usr/bin/env python3
"""
Adaptive HVAC — Dashboard Generator

Reads your live Adaptive HVAC zone configuration from Home Assistant via the
REST API and generates a fully populated Lovelace dashboard.

Usage:
    export HA_URL=http://homeassistant.local:8123
    export HA_TOKEN=<your long-lived access token>
    python3 generate_dashboard.py [options]

Options:
    --output FILE     Write dashboard JSON to FILE (default: dashboard_hvac.json)
    --stdout          Print JSON to stdout instead of writing a file
    --ssh USER@HOST   Deploy directly to HA via SSH (writes storage file + reloads)
    --ssh-key FILE    SSH private key to use with --ssh (default: ~/.ssh/id_rsa)
    --dry-run         Build and print the card structure without writing anything

Requirements:
    Python 3.10+, no third-party libraries required.

Deployment options after running (see DASHBOARD.md for details):
    1. Raw Config Editor — paste the generated JSON into your dashboard's raw editor
    2. SSH deploy       — use --ssh to write the storage file directly
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
# Config from environment
# ---------------------------------------------------------------------------

HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
DASHBOARD_KEY = "lovelace.dashboard_hvac"


# ---------------------------------------------------------------------------
# CLI flags
# ---------------------------------------------------------------------------

args = sys.argv[1:]
DRY_RUN = "--dry-run" in args
TO_STDOUT = "--stdout" in args
OUTPUT_FILE = "dashboard_hvac.json"
SSH_TARGET = None
SSH_KEY = os.path.expanduser("~/.ssh/id_rsa")

for i, a in enumerate(args):
    if a == "--output" and i + 1 < len(args):
        OUTPUT_FILE = args[i + 1]
    if a == "--ssh" and i + 1 < len(args):
        SSH_TARGET = args[i + 1]
    if a == "--ssh-key" and i + 1 < len(args):
        SSH_KEY = args[i + 1]


# ---------------------------------------------------------------------------
# HA REST API helpers
# ---------------------------------------------------------------------------

def ha_get(path: str) -> object:
    if not HA_TOKEN:
        sys.exit("HA_TOKEN is not set. Export it before running:\n  export HA_TOKEN=<token>")
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


# ---------------------------------------------------------------------------
# Zone discovery via entity states
# ---------------------------------------------------------------------------

def zone_slug(name: str) -> str:
    """Match the slug produced by the integration's entity setup."""
    return re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_"))


def discover_zones(states: list[dict]) -> list[dict]:
    """
    Discover zones by finding all *_hvac_status sensors that belong to the
    adaptive_hvac integration and reading their config attributes.
    Returns list of zone dicts with keys: title, slug, attrs.
    """
    status_sensors = [
        s for s in states
        if s["entity_id"].endswith("_hvac_status")
        and "adaptive_hvac" not in s["entity_id"]  # exclude system sensor
        and s["entity_id"].startswith("sensor.")
    ]

    # Cross-reference: a valid zone sensor will have a matching auto switch
    auto_switches = {s["entity_id"] for s in states if "_auto" in s["entity_id"] and "adaptive_hvac" in s["entity_id"]}

    zones = []
    for sensor in status_sensors:
        entity_id = sensor["entity_id"]
        # sensor.calebs_office_hvac_status → calebs_office
        slug = entity_id.removeprefix("sensor.").removesuffix("_hvac_status")
        # Confirm a matching auto switch exists
        has_auto = any(f"adaptive_hvac_{slug}_auto" in sw for sw in auto_switches)
        if not has_auto:
            continue
        attrs = sensor.get("attributes", {})
        raw_name = attrs.get("friendly_name", slug.replace("_", " ").title())
        title = re.sub(r"\s+HVAC\s+Status$", "", raw_name, flags=re.IGNORECASE).strip()
        zones.append({"title": title, "slug": slug, "attrs": attrs, "entity_id": entity_id})

    return zones


def resolve_switch(slug: str, suffix: str, all_ids: set[str]) -> str:
    """Find the live entity ID, handling HA's _2/_3 dedup suffix."""
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


def system_glance_card(system_state: dict) -> dict:
    attrs = system_state.get("attributes", {})
    thermostat = attrs.get("thermostat_entity", "climate.downstairs_thermostat")
    thermostat_base = thermostat.removeprefix("climate.")

    entities = [
        {"entity": "sensor.adaptive_hvac_season", "name": "Season", "icon": "mdi:calendar"},
        {"entity": "sensor.adaptive_hvac_mode", "name": "Mode", "icon": "mdi:hvac"},
        {"entity": thermostat, "name": "Setpoint", "attribute": "temperature", "icon": "mdi:thermometer"},
        {"entity": f"sensor.{thermostat_base}_temperature", "name": "Therm Temp", "icon": "mdi:thermometer-lines"},
        {"entity": "sensor.adaptive_hvac_outdoor_temp", "name": "Outdoor", "icon": "mdi:weather-partly-cloudy"},
        {"entity": f"sensor.{thermostat_base}_humidity", "name": "Humidity", "icon": "mdi:water-percent"},
        {"entity": thermostat, "name": "Fan", "attribute": "fan_mode", "icon": "mdi:fan"},
    ]
    return {
        "type": "glance",
        "title": "System",
        "show_name": True,
        "show_icon": True,
        "entities": entities,
    }


def zone_card(zone: dict, all_ids: set[str]) -> dict:
    slug = zone["slug"]
    attrs = zone["attrs"]

    entities = [{"entity": f"sensor.{slug}_hvac_status", "name": "Status"}]

    for sensor in attrs.get("temp_sensors", [])[:1]:
        entities.append({"entity": sensor, "name": "Temp"})

    # fans controlled by the integration for this zone
    for fan in attrs.get("fans", []):
        entities.append({"entity": fan, "name": "Fan"})

    entities.append({"entity": resolve_switch(slug, "auto", all_ids), "name": "Auto"})
    entities.append({"entity": resolve_switch(slug, "fan_locked", all_ids), "name": "Fan Locked"})

    return {"type": "entities", "title": zone["title"], "entities": entities}


def zone_pairs(zone_cards: list[dict]) -> list[dict]:
    stacks = []
    for a, b in zip_longest(zone_cards[::2], zone_cards[1::2]):
        stacks.append({"type": "horizontal-stack", "cards": [a] if b is None else [a, b]})
    return stacks


def floor_temps_glance(zones: list[dict]) -> dict:
    by_floor: dict[str, list] = {}
    no_floor = []

    for z in zones:
        sensors = z["attrs"].get("temp_sensors", [])
        if not sensors:
            continue
        floor = z["attrs"].get("floor", "")
        item = {"entity": sensors[0], "name": z["title"].split()[0]}
        if floor:
            by_floor.setdefault(floor, []).append(item)
        else:
            no_floor.append(item)

    entities = []
    for floor in sorted(by_floor):
        entities.extend(by_floor[floor])
    entities.extend(no_floor)

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
        "tap_action": {
            "action": "call-service",
            "service": "adaptive_hvac.force_evaluate",
            "data": {},
        },
    }


# ---------------------------------------------------------------------------
# Dashboard assembler
# ---------------------------------------------------------------------------

def build_dashboard(states: list[dict]) -> dict:
    all_ids = {s["entity_id"] for s in states}

    system_state = next(
        (s for s in states if s["entity_id"] == "sensor.adaptive_hvac_status"), {}
    )
    sys_attrs = system_state.get("attributes", {})
    thermostat = sys_attrs.get("thermostat_entity", "climate.downstairs_thermostat")

    zones = discover_zones(states)
    if not zones:
        print("Warning: no zones found. Is the integration loaded and have zones configured?", file=sys.stderr)

    z_cards = [zone_card(z, all_ids) for z in zones]

    cards = [
        markdown_card(zones),
        system_glance_card(system_state),
        *zone_pairs(z_cards),
        floor_temps_glance(zones),
        history_graph_card(thermostat),
        controls_card(),
        setpoints_card(),
        logbook_card(thermostat),
        force_evaluate_button(),
    ]

    return {
        "version": 1,
        "minor_version": 1,
        "key": DASHBOARD_KEY,
        "data": {
            "config": {
                "views": [
                    {
                        "title": "HVAC",
                        "path": "hvac",
                        "icon": "mdi:thermostat",
                        "cards": cards,
                    }
                ]
            }
        },
    }


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

def deploy_ssh(dashboard: dict) -> None:
    payload = json.dumps(dashboard, indent=2, ensure_ascii=False)
    encoded = base64.b64encode(payload.encode()).decode()

    ssh_cmd = ["ssh"]
    if SSH_KEY:
        ssh_cmd += ["-i", SSH_KEY]
    ssh_cmd.append(SSH_TARGET)
    ssh_cmd.append(
        f"echo '{encoded}' | base64 -d | sudo tee /config/.storage/{DASHBOARD_KEY} > /dev/null"
    )

    subprocess.run(ssh_cmd, check=True)
    print(f"Wrote /config/.storage/{DASHBOARD_KEY} on {SSH_TARGET}")

    ha_post("/api/events/lovelace_updated", {})
    print("Fired lovelace_updated — refresh your browser")


def deploy_file(dashboard: dict) -> None:
    payload = json.dumps(dashboard, indent=2, ensure_ascii=False)
    with open(OUTPUT_FILE, "w") as f:
        f.write(payload)
    print(f"Wrote {OUTPUT_FILE}")
    print()
    print("Next steps — pick one:")
    print("  A) Raw Config Editor:")
    print("     Settings → Dashboards → HVAC → ⋮ → Edit → Raw Config Editor")
    print("     Paste the contents of the generated file.")
    print()
    print("  B) SSH deploy (if you have SSH access to HA):")
    print(f"     python3 generate_dashboard.py --ssh user@ha-host --ssh-key ~/.ssh/id_rsa")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Fetching entity states from HA...")
    states = ha_get("/api/states")
    print(f"  {len(states)} entities")

    print("Discovering zones...")
    zones = discover_zones(states)
    for z in zones:
        floor = z["attrs"].get("floor") or "no floor"
        print(f"  • {z['title']} (slug={z['slug']}, floor={floor})")

    if not zones:
        print("  No zones found. Check that adaptive_hvac is loaded.", file=sys.stderr)

    print("Building dashboard...")
    dashboard = build_dashboard(states)
    card_count = len(dashboard["data"]["config"]["views"][0]["cards"])
    print(f"  {len(zones)} zone cards, {card_count} total cards")

    if DRY_RUN:
        cards = dashboard["data"]["config"]["views"][0]["cards"]
        for i, c in enumerate(cards):
            if c["type"] == "horizontal-stack":
                names = [x.get("title", "?") for x in c.get("cards", [])]
                print(f"  [{i}] horizontal-stack: {names}")
            else:
                print(f"  [{i}] {c['type']}: {c.get('title', '')}")
        return

    if TO_STDOUT:
        print(json.dumps(dashboard, indent=2, ensure_ascii=False))
        return

    if SSH_TARGET:
        deploy_ssh(dashboard)
    else:
        deploy_file(dashboard)


if __name__ == "__main__":
    main()
