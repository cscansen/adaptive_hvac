"""Unit tests for dashboard.py — pure builder, no HA required."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dashboard import SYSTEM_DEFAULTS, build_dashboard

ZONE = {
    "title": "Caleb’s Office",
    "status": "sensor.calebs_office_hvac_status",
    "target": "number.calebs_office_target_temp",
    "auto": "switch.adaptive_hvac_calebs_office_auto_2",
    "fan_locked": "switch.adaptive_hvac_calebs_office_fan_locked",
    "temp_sensor": "sensor.office_caleb_hygrometer_temperature",
    "fans": ["fan.office_caleb_ceiling_fan"],
}


def _entities(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "entity" and isinstance(v, str):
                yield v
            else:
                yield from _entities(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _entities(v)


def _build(**kw):
    return build_dashboard([ZONE], {}, "climate.downstairs_thermostat", "sensor.outside_temperature", **kw)


def test_two_section_views_and_home_keeps_old_path():
    views = _build()["views"]
    assert [v["title"] for v in views] == ["Home", "Tuning"]
    assert all(v["type"] == "sections" for v in views)
    assert views[0]["path"] == "hvac"  # existing bookmarks/links keep working


def test_zone_section_uses_resolved_ids():
    home = _build()["views"][0]
    zone = home["sections"][1]
    ids = set(_entities(zone))
    assert ZONE["auto"] in ids  # registry-resolved _2 suffix, not a guessed name
    assert {ZONE["status"], ZONE["target"], ZONE["fan_locked"], ZONE["temp_sensor"]} <= ids
    fan = next(c for c in zone["cards"] if c.get("entity") == ZONE["fans"][0])
    assert fan["features"] == [{"type": "fan-speed"}]


def test_fan_held_tile_only_visible_while_locked():
    zone = _build()["views"][0]["sections"][1]
    held = next(c for c in zone["cards"] if c.get("entity") == ZONE["fan_locked"])
    assert held["visibility"] == [{"condition": "state", "entity": ZONE["fan_locked"], "state": "on"}]
    assert held["tap_action"] == {"action": "toggle"}


def test_registry_ids_override_defaults():
    cfg = build_dashboard([], {"night_mode": "switch.renamed_night"}, "climate.t", "weather.home")
    ids = set(_entities(cfg))
    assert "switch.renamed_night" in ids
    assert SYSTEM_DEFAULTS["night_mode"] not in ids


def test_system_toggles_live_on_tuning_not_home():
    home, tuning = _build()["views"]
    assert SYSTEM_DEFAULTS["active"] not in set(_entities(home))
    assert SYSTEM_DEFAULTS["manual_override"] not in set(_entities(home))
    assert SYSTEM_DEFAULTS["active"] in set(_entities(tuning))


def test_each_entity_once_on_home_view():
    home = _build()["views"][0]
    cards = [c for s in home["sections"] for c in s["cards"]]
    seen = [e for c in cards for e in _entities({k: v for k, v in c.items() if k != "visibility"})]
    assert len(seen) == len(set(seen))


def test_fan_state_sensor_optional():
    assert "sensor.thermostat_fan_state" not in set(_entities(_build()))
    assert "sensor.thermostat_fan_state" in set(_entities(_build(fan_state_sensor="sensor.thermostat_fan_state")))


def test_rebuild_button_targets_own_dashboard_with_confirmation():
    tuning = _build(url_path="my-hvac")["views"][1]
    btn = next(c for s in tuning["sections"] for c in s["cards"] if c.get("name") == "Rebuild dashboard")
    assert btn["tap_action"]["perform_action"] == "adaptive_hvac.rebuild_dashboard"
    assert btn["tap_action"]["data"] == {"dashboard": "my-hvac"}
    assert "confirmation" in btn["tap_action"]


def test_weather_outdoor_badge_shows_temperature():
    cfg = build_dashboard([], {}, "climate.t", "weather.home")
    badge = cfg["views"][0]["sections"][0]["cards"][0]["badges"][0]
    assert badge["entity"] == "weather.home" and badge["state_content"] == "temperature"
