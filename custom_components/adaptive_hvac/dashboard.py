"""Lovelace dashboard builder — pure, no Home Assistant imports (unit-testable).

`build_dashboard()` returns a Lovelace config (`{"views": [...]}`) with two views:

  Home    — what you look at day to day: status headline, thermostat, one section
            per zone (temp/target/fan/auto), and the sweatshirt/night toggles.
  Tuning  — system switches, setpoints, thresholds, night schedule, air & windows,
            history, logbook and the maintenance buttons.

Entity IDs are resolved by the caller (from the entity registry) and passed in, so a
renamed entity never breaks the dashboard. The `adaptive_hvac.rebuild_dashboard`
service in `__init__.py` does that resolution and saves the result.
"""

from __future__ import annotations

# Default entity IDs for system-level entities, keyed by unique_id suffix. The caller
# overrides these with whatever the entity registry actually holds.
SYSTEM_DEFAULTS: dict[str, str] = {
    "status": "sensor.adaptive_hvac_status",
    "mode": "sensor.adaptive_hvac_mode",
    "season": "sensor.adaptive_hvac_season",
    "air_quality": "sensor.adaptive_hvac_air_quality",
    "active": "switch.adaptive_hvac_active",
    "manual_override": "switch.adaptive_hvac_manual_override",
    "night_mode": "switch.adaptive_hvac_night_mode",
    "sweatshirt_mode": "switch.adaptive_hvac_sweatshirt_mode",
    "season_override": "select.adaptive_hvac_season_override",
    "cooling_blocked": "binary_sensor.adaptive_hvac_cooling_blocked",
    "heating_blocked": "binary_sensor.adaptive_hvac_heating_blocked",
    "windows_recommended": "binary_sensor.adaptive_hvac_windows_recommended",
    "ac_setpoint": "number.adaptive_hvac_ac_setpoint",
    "heat_setpoint": "number.adaptive_hvac_heat_setpoint",
    "heat_threshold": "number.adaptive_hvac_heat_threshold",
    "emergency_heat_threshold": "number.adaptive_hvac_emergency_heat_threshold",
    "emergency_cool_threshold": "number.adaptive_hvac_emergency_cool_threshold",
    "cool_exterior_threshold": "number.adaptive_hvac_cool_exterior_threshold",
    "heat_exterior_threshold": "number.adaptive_hvac_heat_exterior_threshold",
    "sweatshirt_cold_threshold": "number.adaptive_hvac_sweatshirt_cold_threshold",
    "aqi_max_for_windows": "number.adaptive_hvac_aqi_threshold",
    "window_min_outdoor": "number.adaptive_hvac_window_min_outdoor",
    "window_max_outdoor": "number.adaptive_hvac_window_max_outdoor",
    "upstairs_demand_boost": "number.adaptive_hvac_upstairs_demand_boost",
    "fan_circulation_delta": "number.adaptive_hvac_fan_circulation_delta",
    "night_ac_setpoint": "number.adaptive_hvac_night_ac_setpoint",
    "night_heat_setpoint": "number.adaptive_hvac_night_heat_setpoint",
    "night_start_hour": "number.adaptive_hvac_night_start_hour",
    "night_end_hour": "number.adaptive_hvac_night_end_hour",
}

FULL = {"columns": 12}
HALF = {"columns": 6}


def _state_is(entity: str, state: str) -> list[dict]:
    return [{"condition": "state", "entity": entity, "state": state}]


def _toggle_tile(entity: str, name: str, icon: str | None = None, **extra) -> dict:
    card = {"type": "tile", "entity": entity, "name": name, "tap_action": {"action": "toggle"},
            "grid_options": HALF, **extra}
    if icon:
        card["icon"] = icon
    return card


def _rows(ids: dict, *pairs: tuple[str, str]) -> list[dict]:
    return [{"entity": ids[key], "name": name} for key, name in pairs]


# ---------------------------------------------------------------------------
# Home view
# ---------------------------------------------------------------------------

def _status_markdown(ids: dict) -> dict:
    """Headline + reasoning; warning lines appear only while their condition holds."""
    s, sw = ids["status"], ids["sweatshirt_mode"]
    lines = [
        f"### {{{{ states('{s}') }}}}",
        f"{{{{ state_attr('{s}', 'reasoning') or '' }}}}",
        "",
        f"{{% if is_state('{ids['active']}', 'off') %}}> ⛔ **Adaptive HVAC is turned off** — see Tuning\n{{% endif %}}",
        f"{{% if is_state('{ids['manual_override']}', 'on') %}}> ✋ **Manual override** — automation paused\n{{% endif %}}",
        f"{{% if is_state('{ids['cooling_blocked']}', 'on') %}}> ⚠️ Cooling blocked — "
        f"{{{{ state_attr('{ids['cooling_blocked']}', 'reason') or '' }}}}\n{{% endif %}}",
        f"{{% if is_state('{ids['heating_blocked']}', 'on') %}}> ⚠️ Heating blocked — "
        f"{{{{ state_attr('{ids['heating_blocked']}', 'reason') or '' }}}}\n{{% endif %}}",
        f"{{% if is_state('{sw}', 'on') %}}> {{{{ '❄️ Sweatshirt mode suspended — too cold, heat allowed' "
        f"if state_attr('{sw}', 'suspended') else '🧥 Sweatshirt mode — heat off (emergency only)' }}}}\n{{% endif %}}",
        f"{{% if state_attr('{s}', 'night_mode_active') %}}> 🌙 Night mode active\n{{% endif %}}",
    ]
    return {"type": "markdown", "content": "\n".join(lines), "grid_options": FULL}


def _overview_section(ids: dict, thermostat: str, outdoor: str) -> dict:
    outdoor_badge = {"type": "entity", "entity": outdoor, "show_state": True, "show_icon": True,
                     "icon": "mdi:weather-partly-cloudy"}
    if outdoor.startswith("weather."):
        outdoor_badge["state_content"] = "temperature"
    return {
        "type": "grid",
        "cards": [
            {"type": "heading", "heading": "Right now", "icon": "mdi:home-thermometer",
             "badges": [outdoor_badge,
                        {"type": "entity", "entity": ids["season"], "show_state": True, "show_icon": True}]},
            _status_markdown(ids),
            {"type": "thermostat", "entity": thermostat, "grid_options": FULL},
            _toggle_tile(ids["sweatshirt_mode"], "Sweatshirt mode", "mdi:tshirt-crew"),
            _toggle_tile(ids["night_mode"], "Night mode", "mdi:weather-night"),
            {"type": "tile", "entity": ids["windows_recommended"], "name": "Open the windows",
             "icon": "mdi:window-open-variant", "grid_options": FULL,
             "visibility": _state_is(ids["windows_recommended"], "on")},
        ],
    }


def _zone_section(zone: dict) -> dict:
    badges = []
    if zone.get("temp_sensor"):
        badges.append({"type": "entity", "entity": zone["temp_sensor"], "show_state": True, "show_icon": True})
    badges.append({"type": "entity", "entity": zone["status"], "show_state": True, "show_icon": False})
    cards: list[dict] = [
        {"type": "heading", "heading": zone["title"], "badges": badges},
        {"type": "tile", "entity": zone["target"], "name": "Target", "icon": "mdi:thermometer-check",
         "features": [{"type": "numeric-input", "style": "buttons"}], "grid_options": FULL},
    ]
    fans = zone.get("fans", [])
    for fan in fans:
        tile = {"type": "tile", "entity": fan, "features": [{"type": "fan-speed"}], "grid_options": FULL}
        if len(fans) == 1:
            tile["name"] = "Ceiling fan"
        cards.append(tile)
    cards.append(_toggle_tile(zone["auto"], "Automatic", "mdi:robot"))
    # Only shown while a manual fan change has the fan held; tapping releases it.
    cards.append(_toggle_tile(zone["fan_locked"], "Fan held — tap to release", "mdi:lock",
                              visibility=_state_is(zone["fan_locked"], "on")))
    return {"type": "grid", "cards": cards}


# ---------------------------------------------------------------------------
# Tuning view
# ---------------------------------------------------------------------------

def _entities(title: str, rows: list[dict], icon: str | None = None) -> dict:
    card = {"type": "entities", "title": title, "entities": rows, "grid_options": FULL}
    if icon:
        card["icon"] = icon
    return card


def _tuning_sections(ids: dict, thermostat: str, zones: list[dict], fan_state_sensor: str | None,
                     url_path: str) -> list[dict]:
    system = _entities("System", _rows(
        ids, ("active", "Adaptive HVAC enabled"), ("manual_override", "Manual override (pause automation)"),
        ("season_override", "Season override"), ("mode", "Current mode"),
    ), "mdi:cog")
    setpoints = _entities("Setpoints & thresholds", _rows(
        ids, ("ac_setpoint", "AC setpoint"), ("heat_setpoint", "Heat setpoint"),
        ("heat_threshold", "Heat trigger"), ("upstairs_demand_boost", "Upstairs demand boost"),
        ("fan_circulation_delta", "Floor circulation delta"),
        ("cool_exterior_threshold", "AC outdoor gate"), ("heat_exterior_threshold", "Heat outdoor gate"),
        ("emergency_cool_threshold", "Emergency cool"), ("emergency_heat_threshold", "Emergency heat"),
    ), "mdi:tune")
    night = _entities("Night schedule", _rows(
        ids, ("night_ac_setpoint", "Night AC setpoint"), ("night_heat_setpoint", "Night heat setpoint"),
        ("night_start_hour", "Starts at hour"), ("night_end_hour", "Ends at hour"),
    ), "mdi:weather-night")
    sweatshirt = _entities("Sweatshirt mode", [
        {"entity": ids["sweatshirt_cold_threshold"], "name": "Suspend if forecast high below"},
        {"type": "attribute", "entity": ids["sweatshirt_mode"], "attribute": "signal_temp",
         "name": "Today's cold signal", "suffix": "°F"},
    ], "mdi:tshirt-crew")
    air = _entities("Air & windows", [
        *_rows(ids, ("air_quality", "Outdoor AQI"), ("windows_recommended", "Open the windows?"),
               ("cooling_blocked", "Cooling blocked"), ("heating_blocked", "Heating blocked")),
        {"type": "section", "label": "Window advice band"},
        *_rows(ids, ("aqi_max_for_windows", "AQI ceiling"), ("window_min_outdoor", "Outdoor min"),
               ("window_max_outdoor", "Outdoor max")),
    ], "mdi:window-open-variant")

    history = [{"entity": thermostat, "name": "Thermostat"},
               {"entity": ids["ac_setpoint"], "name": "AC setpoint"},
               {"entity": ids["mode"], "name": "Integration mode"}]
    if fan_state_sensor:
        history.insert(2, {"entity": fan_state_sensor, "name": "Whole-house fan"})
    history += [{"entity": fan, "name": f"{z['title']} fan"} for z in zones for fan in z.get("fans", [])]

    buttons = [
        {"type": "button", "name": "Force evaluate now", "icon": "mdi:refresh", "grid_options": HALF,
         "tap_action": {"action": "perform-action", "perform_action": "adaptive_hvac.force_evaluate"}},
        {"type": "button", "name": "Rebuild dashboard", "icon": "mdi:view-dashboard-edit", "grid_options": HALF,
         "tap_action": {"action": "perform-action", "perform_action": "adaptive_hvac.rebuild_dashboard",
                        "data": {"dashboard": url_path},
                        "confirmation": {"text": "Regenerate this dashboard from the current zone setup?"}}},
    ]
    return [
        {"type": "grid", "cards": [system, sweatshirt, *buttons]},
        {"type": "grid", "cards": [setpoints]},
        {"type": "grid", "cards": [night, air]},
        {"type": "grid", "column_span": 2, "cards": [
            {"type": "history-graph", "title": "History (6h)", "hours_to_show": 6, "entities": history,
             "grid_options": FULL}]},
        {"type": "grid", "cards": [
            {"type": "logbook", "title": "Event log (24h)", "hours_to_show": 24,
             "entities": [thermostat, ids["mode"]], "grid_options": FULL}]},
    ]


def build_dashboard(zones: list[dict], system_ids: dict, thermostat: str, outdoor: str,
                    fan_state_sensor: str | None = None, url_path: str = "dashboard-hvac") -> dict:
    """zones: [{title, status, target, auto, fan_locked, temp_sensor?, fans?}] with resolved entity IDs."""
    ids = {**SYSTEM_DEFAULTS, **system_ids}
    return {"views": [
        {"title": "Home", "path": "hvac", "icon": "mdi:thermostat", "type": "sections", "max_columns": 3,
         "sections": [_overview_section(ids, thermostat, outdoor), *map(_zone_section, zones)]},
        {"title": "Tuning", "path": "tuning", "icon": "mdi:tune", "type": "sections", "max_columns": 3,
         "sections": _tuning_sections(ids, thermostat, zones, fan_state_sensor, url_path)},
    ]}
