"""
Unit tests for adaptive_hvac logic.py — pure decision engine, no HA required.

Coverage priorities:
  - Emergency heat uses REAL configured threshold (not SystemConfig() default)
  - Fan lock blocks all commands; fans track temperature not occupancy
  - Sensor failsafe on temp = 0 or >= 200
  - Emergency cool still evaluated at zone level
  - Summer/winter gating, exterior threshold, window gate
  - Floor circulation fan mode
  - annotate_zone_decisions passive relabeling
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from logic import (
    ZoneState,
    ZoneConfig,
    ZoneDecision,
    SystemState,
    SystemConfig,
    SystemDecision,
    decide_zone,
    decide_system,
    annotate_zone_decisions,
    _floor_fan_mode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def zone(
    name="Office",
    temp=72.0,
    floor="main",
    occupied=True,
    fan_locked=False,
    window_open=False,
    affects_thermostat=True,
    target=72.0,
    trend=0.0,
):
    return ZoneState(
        zone_name=name,
        floor=floor,
        temp=temp,
        temp_trend=trend,
        zone_occupied=occupied,
        fan_locked=fan_locked,
        window_open=window_open,
        affects_thermostat=affects_thermostat,
        zone_target_temp=target,
    )


def sys_state(zones, outdoor=75.0, season="summer", sleep=False, occupied=True, windows_openable=True):
    return SystemState(
        zone_states=zones,
        outdoor_temp=outdoor,
        season=season,
        sleep_posture=sleep,
        house_occupied=occupied,
        windows_openable=windows_openable,
    )


def zone_cfg(target=72.0, fan_speed=50, emergency_cool=85.0):
    return ZoneConfig(
        zone_target_temp=target,
        fan_speed=fan_speed,
        emergency_cool_threshold=emergency_cool,
    )


def sys_cfg(
    ac_setpoint=68.0,
    heat_setpoint=68.0,
    heat_threshold=68.0,
    emergency_heat_threshold=45.0,  # user-configured value
    cool_exterior_threshold=60.0,
    heat_exterior_threshold=60.0,
    cool_interior_override_delta=5.0,
    fan_circulation_delta=2.0,
):
    return SystemConfig(
        ac_setpoint=ac_setpoint,
        heat_setpoint=heat_setpoint,
        heat_threshold=heat_threshold,
        emergency_heat_threshold=emergency_heat_threshold,
        cool_exterior_threshold=cool_exterior_threshold,
        heat_exterior_threshold=heat_exterior_threshold,
        cool_interior_override_delta=cool_interior_override_delta,
        fan_circulation_delta=fan_circulation_delta,
    )


# ---------------------------------------------------------------------------
# THE BUG THAT BROKE PROD: emergency heat uses SystemConfig() default (55°F)
# not the user-configured value (45°F). A zone at 55°F should NOT trigger
# emergency heat when threshold is 45°F.
# ---------------------------------------------------------------------------

class TestEmergencyHeatThreshold:

    def test_55f_does_not_trigger_emergency_heat_at_45f_threshold(self):
        """Core regression: 55°F room temp with 45°F threshold → no emergency heat."""
        z = zone(name="Living Room", temp=55.0)
        ss = sys_state([z], outdoor=55.0)
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg(emergency_heat_threshold=45.0))]
        decision = decide_system(ss, zone_decisions, sys_cfg(emergency_heat_threshold=45.0))
        assert decision.thermostat_hvac_mode != "heat" or "EMERGENCY" not in decision.status

    def test_44f_triggers_emergency_heat_at_45f_threshold(self):
        """44°F IS below the configured 45°F threshold → emergency heat fires."""
        z = zone(name="Living Room", temp=44.0)
        ss = sys_state([z], outdoor=30.0)
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg(emergency_heat_threshold=45.0))]
        decision = decide_system(ss, zone_decisions, sys_cfg(emergency_heat_threshold=45.0))
        assert decision.thermostat_hvac_mode == "heat"
        assert "EMERGENCY HEAT" in decision.status

    def test_emergency_heat_respects_configured_threshold_not_default(self):
        """SystemConfig default is 55°F. Configured is 45°F. Test that configured wins."""
        z = zone(name="Zone", temp=50.0)
        ss = sys_state([z], outdoor=50.0)
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg(emergency_heat_threshold=45.0))]

        # With threshold=45, 50°F should NOT trigger emergency heat
        decision_real = decide_system(ss, zone_decisions, sys_cfg(emergency_heat_threshold=45.0))
        assert "EMERGENCY HEAT" not in decision_real.status

        # With threshold=55 (the old default that caused the bug), 50°F WOULD trigger
        decision_default = decide_system(ss, zone_decisions, sys_cfg(emergency_heat_threshold=55.0))
        assert "EMERGENCY HEAT" in decision_default.status

    def test_emergency_heat_only_triggers_on_zones_affecting_thermostat(self):
        """Zones with affects_thermostat=False should not trigger emergency heat."""
        z = zone(name="Garage", temp=30.0, affects_thermostat=False)
        ss = sys_state([z])
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg(emergency_heat_threshold=45.0))]
        decision = decide_system(ss, zone_decisions, sys_cfg(emergency_heat_threshold=45.0))
        assert "EMERGENCY HEAT" not in decision.status

    def test_emergency_heat_status_includes_zone_name_and_temp(self):
        """Status message should identify which zone triggered emergency heat."""
        z = zone(name="Basement", temp=40.0)
        ss = sys_state([z])
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg(emergency_heat_threshold=45.0))]
        decision = decide_system(ss, zone_decisions, sys_cfg(emergency_heat_threshold=45.0))
        assert "Basement" in " ".join(decision.reasoning)
        assert "40.0" in " ".join(decision.reasoning)


# ---------------------------------------------------------------------------
# Fan behavior: fans track temperature, occupancy only gates the thermostat call
# ---------------------------------------------------------------------------

class TestFanLock:

    def test_locked_fan_blocks_command_when_occupied(self):
        """Fan locked + zone occupied → no fan command (don't disturb user lock)."""
        z = zone(temp=78.0, fan_locked=True, occupied=True)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg())
        assert d.mode == "cooling"
        assert d.fan_commands == {}

    def test_locked_fan_blocks_command_when_unoccupied(self):
        """Fan locked + zone unoccupied → still no fan command (lock respected regardless)."""
        z = zone(temp=78.0, fan_locked=True, occupied=False)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg())
        assert d.mode == "cooling"
        assert d.fan_commands == {}

    def test_locked_fan_idle_occupied_no_fan_command(self):
        """Locked fan + idle + occupied → no fan command (don't disturb)."""
        z = zone(temp=70.0, fan_locked=True, occupied=True)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg())
        assert d.mode == "idle"
        assert d.fan_commands == {}

    def test_locked_fan_idle_unoccupied_turns_off(self):
        """Locked fan + idle + unoccupied → turn off."""
        z = zone(temp=70.0, fan_locked=True, occupied=False)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg())
        assert d.mode == "idle"
        assert d.fan_commands.get("Office") == 0

    def test_unlocked_fan_runs_when_warm_and_occupied(self):
        """Unlocked fan, warm, occupied → fan runs at configured speed, thermostat called."""
        z = zone(temp=78.0, fan_locked=False, occupied=True)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(target=72.0, fan_speed=60), sys_cfg())
        assert d.mode == "cooling"
        assert d.fan_commands.get("Office") == 60
        assert d.thermal_request == "cool"

    def test_unlocked_fan_off_when_warm_and_unoccupied(self):
        """Unlocked fan, warm, unoccupied → fan off; thermostat request still active."""
        z = zone(temp=78.0, fan_locked=False, occupied=False)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(target=72.0, fan_speed=50), sys_cfg())
        assert d.mode == "cooling"
        assert d.fan_commands.get("Office") == 0
        assert d.thermal_request == "cool"

    def test_fan_on_at_exactly_zone_target_occupied(self):
        """At exactly zone_target temp + occupied → fan on (>= boundary)."""
        z = zone(temp=72.0, fan_locked=False, occupied=True)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(target=72.0, fan_speed=50), sys_cfg())
        assert d.mode == "cooling"
        assert d.fan_commands.get("Office") == 50

    def test_fan_off_just_below_zone_target(self):
        """Just below zone_target → comfortable/idle, fan off."""
        z = zone(temp=71.9, fan_locked=False, occupied=True)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg())
        assert d.mode == "idle"
        assert d.fan_commands.get("Office") == 0

    def test_fan_runs_when_warm_windows_open_occupied(self):
        """Window open blocks AC but ceiling fan should still run when warm and occupied."""
        z = zone(temp=76.0, occupied=True, window_open=True)
        ss = sys_state([z], outdoor=65.0)
        zone_d = decide_zone(z, ss, zone_cfg(target=72.0, fan_speed=50), sys_cfg())
        system_d = decide_system(ss, [zone_d], sys_cfg())
        assert system_d.thermostat_hvac_mode != "cool"
        assert zone_d.fan_commands.get("Office") == 50


# ---------------------------------------------------------------------------
# Sensor failsafe
# ---------------------------------------------------------------------------

class TestSensorFailsafe:

    def test_zero_temp_is_failsafe(self):
        """_read_temp() returns 0.0 when all sensors unavailable → failsafe."""
        z = zone(temp=0.0)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(), sys_cfg())
        assert d.mode == "sensor_failsafe"

    def test_negative_temp_is_failsafe(self):
        z = zone(temp=-1.0)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(), sys_cfg())
        assert d.mode == "sensor_failsafe"

    def test_200f_is_failsafe(self):
        z = zone(temp=200.0)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(), sys_cfg())
        assert d.mode == "sensor_failsafe"

    def test_valid_temp_at_boundary_is_not_failsafe(self):
        z = zone(temp=1.0)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(), sys_cfg())
        assert d.mode != "sensor_failsafe"


# ---------------------------------------------------------------------------
# Emergency cool (still at zone level)
# ---------------------------------------------------------------------------

class TestEmergencyCool:

    def test_emergency_cool_fires_at_threshold(self):
        z = zone(temp=85.0)
        ss = sys_state([z], outdoor=90.0)
        d = decide_zone(z, ss, zone_cfg(emergency_cool=85.0), sys_cfg())
        assert d.mode == "emergency_cooling"
        assert d.fan_commands.get("Office") == 100

    def test_emergency_cool_fans_only_when_not_affects_thermostat(self):
        z = zone(temp=90.0, affects_thermostat=False)
        ss = sys_state([z])
        d = decide_zone(z, ss, zone_cfg(emergency_cool=85.0), sys_cfg())
        assert d.mode == "emergency_cooling"
        assert d.thermal_request is None
        assert d.fan_commands.get("Office") == 100

    def test_emergency_cool_propagates_through_decide_system(self):
        z = zone(temp=90.0)
        ss = sys_state([z], outdoor=95.0)
        zone_decisions = [decide_zone(z, ss, zone_cfg(emergency_cool=85.0), sys_cfg())]
        decision = decide_system(ss, zone_decisions, sys_cfg())
        assert decision.thermostat_hvac_mode == "cool"
        assert "EMERGENCY COOL" in decision.status


# ---------------------------------------------------------------------------
# Summer cooling gating
# ---------------------------------------------------------------------------

class TestSummerCooling:

    def test_cool_blocked_when_outdoor_below_threshold(self):
        z = zone(temp=78.0)
        ss = sys_state([z], outdoor=50.0, season="summer")
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg(cool_exterior_threshold=60.0))]
        decision = decide_system(ss, zone_decisions, sys_cfg(cool_exterior_threshold=60.0))
        assert decision.thermostat_hvac_mode == "off"

    def test_cool_allowed_when_outdoor_above_threshold(self):
        z = zone(temp=78.0)
        ss = sys_state([z], outdoor=75.0, season="summer")
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg(cool_exterior_threshold=60.0))]
        decision = decide_system(ss, zone_decisions, sys_cfg(cool_exterior_threshold=60.0))
        assert decision.thermostat_hvac_mode == "cool"

    def test_cool_allowed_via_interior_override_when_outdoor_cold(self):
        """
        Interior override fires (zone 10°F above target) but the relative outdoor gate
        then blocks AC because outdoor (50°F) < zone target (72°F) — opening windows
        would achieve comfort. The relative gate wins over the interior override.
        This is correct behavior: don't run a compressor when 50°F air is available.
        """
        z = zone(temp=82.0, target=72.0)
        ss = sys_state([z], outdoor=50.0, season="summer")
        zone_decisions = [decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg(
            cool_exterior_threshold=60.0, cool_interior_override_delta=5.0
        ))]
        decision = decide_system(ss, zone_decisions, sys_cfg(
            cool_exterior_threshold=60.0, cool_interior_override_delta=5.0
        ))
        # Relative gate (outdoor 50°F < zone target 72°F) overrides interior override
        assert decision.thermostat_hvac_mode == "off"
        assert "open windows" in " ".join(decision.reasoning)

    def test_cool_blocked_when_outdoor_cooler_than_zone_target(self):
        """Outdoor cooler than zone target → open a window, don't run AC."""
        z = zone(temp=78.0, target=72.0)
        ss = sys_state([z], outdoor=65.0, season="summer")
        zone_decisions = [decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg(cool_exterior_threshold=60.0))]
        decision = decide_system(ss, zone_decisions, sys_cfg(cool_exterior_threshold=60.0))
        assert decision.thermostat_hvac_mode == "off"

    def test_window_open_blocks_cooling(self):
        z = zone(temp=80.0, window_open=True)
        ss = sys_state([z], outdoor=80.0, season="summer")
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg())]
        decision = decide_system(ss, zone_decisions, sys_cfg())
        assert decision.thermostat_hvac_mode == "off"
        assert "window open" in decision.status

    def test_relative_gate_blocks_ac_when_windows_openable(self):
        """Outdoor cooler than zone target + windows can be opened → AC blocked."""
        z = zone(temp=75.0, occupied=True)
        ss = sys_state([z], outdoor=68.0, season="summer", windows_openable=True)
        zone_decisions = [decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg())]
        decision = decide_system(ss, zone_decisions, sys_cfg())
        assert decision.thermostat_hvac_mode == "off"
        assert any("open windows" in r for r in decision.reasoning)

    def test_relative_gate_allows_ac_when_windows_not_openable(self):
        """Outdoor cooler than zone target but rain/wind → AC allowed."""
        z = zone(temp=75.0, occupied=True)
        ss = sys_state([z], outdoor=68.0, season="summer", windows_openable=False)
        zone_decisions = [decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg())]
        decision = decide_system(ss, zone_decisions, sys_cfg())
        assert decision.thermostat_hvac_mode == "cool"
        assert any("conditions poor" in r for r in decision.reasoning)

    def test_demand_boost_setpoint_rounds_to_whole_degree(self):
        """
        A fractional demand boost (e.g. 1.5°F) must not produce a fractional
        dispatched setpoint (e.g. 66.5°F) — most thermostats only accept whole
        degrees and silently round it themselves, which then no longer matches
        what the dashboard displays. The integration must round before dispatch.
        """
        z = zone(temp=78.0, target=72.0)
        ss = sys_state([z], outdoor=75.0, season="summer")
        cfg = SystemConfig(ac_setpoint=68.0, upstairs_demand_boost=1.5, cool_exterior_threshold=60.0)
        zone_decisions = [decide_zone(z, ss, zone_cfg(target=72.0), cfg)]
        decision = decide_system(ss, zone_decisions, cfg)
        assert decision.thermostat_hvac_mode == "cool"
        assert decision.thermostat_setpoint == 67.0  # round(68.0 - 1.5) == 67, not 66.5
        assert decision.thermostat_setpoint == int(decision.thermostat_setpoint)


# ---------------------------------------------------------------------------
# Winter heating gating
# ---------------------------------------------------------------------------

class TestWinterHeating:

    def test_heat_allowed_when_outdoor_below_threshold(self):
        z = zone(temp=62.0)
        ss = sys_state([z], outdoor=40.0, season="winter")
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg(
            heat_threshold=68.0, heat_exterior_threshold=60.0
        ))]
        decision = decide_system(ss, zone_decisions, sys_cfg(
            heat_threshold=68.0, heat_exterior_threshold=60.0
        ))
        assert decision.thermostat_hvac_mode == "heat"

    def test_heat_blocked_when_outdoor_above_threshold(self):
        z = zone(temp=62.0)
        ss = sys_state([z], outdoor=70.0, season="winter")
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg(
            heat_threshold=68.0, heat_exterior_threshold=60.0
        ))]
        decision = decide_system(ss, zone_decisions, sys_cfg(
            heat_threshold=68.0, heat_exterior_threshold=60.0
        ))
        assert decision.thermostat_hvac_mode == "off"


# ---------------------------------------------------------------------------
# Manual override / system inactive
# ---------------------------------------------------------------------------

class TestOverrideAndInactive:

    def test_manual_override_returns_off(self):
        z = zone(temp=90.0)
        ss = sys_state([z], outdoor=95.0)
        ss.manual_override = True
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg())]
        decision = decide_system(ss, zone_decisions, sys_cfg())
        assert decision.thermostat_hvac_mode == "off"
        assert "MANUAL OVERRIDE" in decision.status

    def test_system_inactive_returns_off(self):
        z = zone(temp=90.0)
        ss = sys_state([z], outdoor=95.0)
        ss.system_active = False
        zone_decisions = [decide_zone(z, ss, zone_cfg(), sys_cfg())]
        decision = decide_system(ss, zone_decisions, sys_cfg())
        assert decision.thermostat_hvac_mode == "off"
        assert "INACTIVE" in decision.status

    def test_zone_manual_override_propagates(self):
        z = zone(temp=90.0)
        ss = sys_state([z])
        ss.manual_override = True
        d = decide_zone(z, ss, zone_cfg(), sys_cfg())
        assert d.mode == "manual_override"


# ---------------------------------------------------------------------------
# Floor circulation fan
# ---------------------------------------------------------------------------

class TestFloorCirculation:

    def test_fan_on_when_floors_differ_above_threshold(self):
        zones = [
            zone(name="A", temp=75.0, floor="upstairs"),
            zone(name="B", temp=70.0, floor="downstairs"),
        ]
        mode, reasoning = _floor_fan_mode(zones, sys_cfg(fan_circulation_delta=2.0), sleep_posture=False)
        assert mode == "on"

    def test_fan_auto_when_floors_within_threshold(self):
        zones = [
            zone(name="A", temp=71.0, floor="upstairs"),
            zone(name="B", temp=70.0, floor="downstairs"),
        ]
        mode, _ = _floor_fan_mode(zones, sys_cfg(fan_circulation_delta=2.0), sleep_posture=False)
        assert mode == "auto"

    def test_sleep_posture_no_longer_suppresses_fan(self):
        """sleep_posture no longer suppresses floor fan — AC-off does instead."""
        zones = [
            zone(name="A", temp=80.0, floor="upstairs"),
            zone(name="B", temp=65.0, floor="downstairs"),
        ]
        mode, _ = _floor_fan_mode(zones, sys_cfg(fan_circulation_delta=2.0), sleep_posture=True)
        assert mode == "on"

    def test_floor_fan_suppressed_when_ac_off_summer(self):
        """Summer + AC blocked by exterior gate → floor fan suppressed even if floors differ."""
        # outdoor=40°F < cool_exterior_threshold=60°F; zones only 1°F above target (< override delta)
        zones = [
            zone(name="A", temp=73.0, floor="upstairs"),
            zone(name="B", temp=68.0, floor="downstairs"),
        ]
        ss = sys_state(zones, outdoor=40.0, season="summer")
        zone_decisions = [decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg()) for z in zones]
        sys_dec = decide_system(ss, zone_decisions, sys_cfg(cool_exterior_threshold=60.0))
        assert sys_dec.thermostat_hvac_mode == "off"
        assert sys_dec.whole_house_fan_mode == "auto"
        assert any("AC not active" in r for r in sys_dec.reasoning)

    def test_floor_fan_active_when_ac_cooling(self):
        """Summer + AC actively cooling → floor fan follows circulation delta."""
        zones = [
            zone(name="A", temp=80.0, floor="upstairs"),
            zone(name="B", temp=70.0, floor="downstairs"),
        ]
        ss = sys_state(zones, outdoor=90.0, season="summer")
        zone_decisions = [decide_zone(z, ss, zone_cfg(target=72.0), sys_cfg()) for z in zones]
        sys_dec = decide_system(ss, zone_decisions, sys_cfg(fan_circulation_delta=2.0))
        assert sys_dec.thermostat_hvac_mode == "cool"
        assert sys_dec.whole_house_fan_mode == "on"

    def test_single_floor_returns_auto(self):
        zones = [zone(name="A", temp=75.0, floor="main"), zone(name="B", temp=70.0, floor="main")]
        mode, _ = _floor_fan_mode(zones, sys_cfg(), sleep_posture=False)
        assert mode == "auto"


# ---------------------------------------------------------------------------
# annotate_zone_decisions
# ---------------------------------------------------------------------------

class TestAnnotateZoneDecisions:

    def test_cooling_zone_relabeled_passive_when_ac_off(self):
        z_decision = ZoneDecision(
            mode="cooling",
            zone_name="Office",
            fan_commands={"Office": 50},
            thermal_request="cool",
            status="Office: COOLING 78.0°F > 72.0°F",
        )
        sys_dec = SystemDecision(thermostat_hvac_mode="off")
        annotated = annotate_zone_decisions([z_decision], sys_dec)
        assert annotated[0].mode == "passive_cooling"
        assert "PASSIVE COOLING" in annotated[0].status

    def test_cooling_zone_relabeled_idle_warm_when_no_fans_and_ac_off(self):
        z_decision = ZoneDecision(
            mode="cooling",
            zone_name="Office",
            fan_commands={},
            thermal_request="cool",
            status="Office: COOLING 78.0°F > 72.0°F",
        )
        sys_dec = SystemDecision(thermostat_hvac_mode="off")
        annotated = annotate_zone_decisions([z_decision], sys_dec)
        assert annotated[0].mode == "idle_warm"

    def test_cooling_zone_not_relabeled_when_ac_active(self):
        z_decision = ZoneDecision(
            mode="cooling",
            zone_name="Office",
            fan_commands={"Office": 50},
            thermal_request="cool",
            status="Office: COOLING 78.0°F > 72.0°F",
        )
        sys_dec = SystemDecision(thermostat_hvac_mode="cool")
        annotated = annotate_zone_decisions([z_decision], sys_dec)
        assert annotated[0].mode == "cooling"

    def test_heating_zone_relabeled_idle_cold_when_heat_off(self):
        z_decision = ZoneDecision(
            mode="heating",
            zone_name="Office",
            fan_commands={},
            thermal_request="heat",
            status="Office: HEATING 62.0°F ≤ 68.0°F",
        )
        sys_dec = SystemDecision(thermostat_hvac_mode="off")
        annotated = annotate_zone_decisions([z_decision], sys_dec)
        assert annotated[0].mode == "idle_cold"
