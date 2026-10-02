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
    aqi_category,
    windows_are_recommended,
    _floor_fan_mode,
    REASON_WINDOW_OPEN,
    REASON_OUTDOOR_COLD,
    REASON_OPEN_WINDOWS_BETTER,
    REASON_AQI_HOLD,
    REASON_WINDOW_OPEN_HEAT,
    REASON_OUTDOOR_WARM,
    REASON_OPEN_WINDOWS_WARM,
    REASON_AQI_HOLD_HEAT,
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


def sys_state(
    zones,
    outdoor=75.0,
    season="summer",
    sleep=False,
    occupied=True,
    windows_openable=True,
    aqi=None,
    aqi_ok=True,
):
    return SystemState(
        zone_states=zones,
        outdoor_temp=outdoor,
        season=season,
        sleep_posture=sleep,
        house_occupied=occupied,
        windows_openable=windows_openable,
        outdoor_aqi=aqi,
        aqi_ok=aqi_ok,
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
    window_min_outdoor=60.0,
    window_max_outdoor=75.0,
):
    return SystemConfig(
        window_min_outdoor=window_min_outdoor,
        window_max_outdoor=window_max_outdoor,
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


# ---------------------------------------------------------------------------
# Air quality: AQI never unblocks the HVAC — it only changes the advice.
# ---------------------------------------------------------------------------

class TestAirQualityGating:

    def _cool_request(self, outdoor, **ss_kw):
        z = zone(temp=74.0, target=72.0)
        ss = sys_state([z], outdoor=outdoor, season="summer", **ss_kw)
        zd = [decide_zone(z, ss, zone_cfg(), sys_cfg())]
        return ss, zd

    def test_relative_gate_still_blocks_ac_when_aqi_bad(self):
        """REGRESSION GUARD for an explicit product decision: smoke does NOT buy you AC.
        Cooler outside still blocks cooling; only the reason code and message change."""
        ss, zd = self._cool_request(68.0, aqi=152.0, aqi_ok=False)
        decision = decide_system(ss, zd, sys_cfg())
        assert decision.thermostat_hvac_mode == "off"
        assert decision.cooling_blocked is True
        assert decision.blocked_reason == REASON_AQI_HOLD
        assert "keep windows shut" in " ".join(decision.reasoning)

    def test_relative_gate_reason_code_when_aqi_good(self):
        ss, zd = self._cool_request(68.0, aqi=20.0, aqi_ok=True)
        decision = decide_system(ss, zd, sys_cfg())
        assert decision.thermostat_hvac_mode == "off"
        assert decision.blocked_reason == REASON_OPEN_WINDOWS_BETTER
        assert "open windows" in " ".join(decision.reasoning)

    def test_aqi_hold_message_survives_unknown_aqi_value(self):
        """aqi_ok False with no numeric reading must not crash the f-string."""
        ss, zd = self._cool_request(68.0, aqi=None, aqi_ok=False)
        decision = decide_system(ss, zd, sys_cfg())
        assert decision.blocked_reason == REASON_AQI_HOLD
        assert "AQI unknown" in " ".join(decision.reasoning)

    def test_window_open_reason_code_summer(self):
        z = zone(temp=74.0, target=72.0, window_open=True)
        ss = sys_state([z], outdoor=80.0, season="summer")
        zd = [decide_zone(z, ss, zone_cfg(), sys_cfg())]
        decision = decide_system(ss, zd, sys_cfg())
        assert decision.blocked_reason == REASON_WINDOW_OPEN
        assert decision.cooling_blocked is True
        assert decision.heating_blocked is False

    def test_outdoor_cold_reason_code(self):
        """Below the exterior threshold, no interior override, windows not openable
        so the relative gate can't claim it."""
        z = zone(temp=73.0, target=72.0)
        ss = sys_state([z], outdoor=50.0, season="summer", windows_openable=False)
        zd = [decide_zone(z, ss, zone_cfg(), sys_cfg())]
        decision = decide_system(ss, zd, sys_cfg())
        assert decision.blocked_reason == REASON_OUTDOOR_COLD
        assert decision.cooling_blocked is True

    def test_aqi_category_breakpoints(self):
        assert aqi_category(0) == "Good"
        assert aqi_category(50) == "Good"
        assert aqi_category(51) == "Moderate"
        assert aqi_category(100) == "Moderate"
        assert aqi_category(101) == "Unhealthy for Sensitive Groups"
        assert aqi_category(150) == "Unhealthy for Sensitive Groups"
        assert aqi_category(151) == "Unhealthy"
        assert aqi_category(200) == "Unhealthy"
        assert aqi_category(201) == "Very Unhealthy"
        assert aqi_category(300) == "Very Unhealthy"
        assert aqi_category(301) == "Hazardous"
        assert aqi_category(None) == "Unknown"


# ---------------------------------------------------------------------------
# Windows recommendation — absolute band, deliberately season-independent
# ---------------------------------------------------------------------------

class TestWindowsRecommended:

    def test_recommended_in_band_clean_and_calm(self):
        ss = sys_state([zone(temp=74.0)], outdoor=64.0, aqi=22.0, aqi_ok=True)
        assert windows_are_recommended(ss, sys_cfg()) is True

    def test_recommended_in_october_shoulder_season(self):
        """REGRESSION GUARD for the deliberate choice to make the band season-independent.
        The calendar season model is binary, so October reads as 'winter' and the furnace
        wants to run at 62°F — but 62°F is exactly when you open the windows.
        A future 'optimization' back to a target-relative rule breaks here, loudly."""
        z = zone(temp=66.0, target=68.0)
        ss = sys_state([z], outdoor=62.0, season="winter", aqi=18.0, aqi_ok=True)
        assert windows_are_recommended(ss, sys_cfg()) is True

    def test_not_recommended_when_aqi_bad(self):
        ss = sys_state([zone()], outdoor=64.0, aqi=160.0, aqi_ok=False)
        assert windows_are_recommended(ss, sys_cfg()) is False

    def test_not_recommended_when_aqi_unknown(self):
        """Fail closed — a dead AQI sensor must never produce 'open your windows'."""
        ss = sys_state([zone()], outdoor=64.0, aqi=None, aqi_ok=False)
        assert windows_are_recommended(ss, sys_cfg()) is False

    def test_not_recommended_in_rain_or_wind(self):
        ss = sys_state([zone()], outdoor=64.0, aqi=22.0, aqi_ok=True, windows_openable=False)
        assert windows_are_recommended(ss, sys_cfg()) is False

    def test_not_recommended_below_band(self):
        ss = sys_state([zone()], outdoor=55.0, aqi=22.0, aqi_ok=True)
        assert windows_are_recommended(ss, sys_cfg()) is False

    def test_not_recommended_above_band(self):
        ss = sys_state([zone()], outdoor=82.0, aqi=22.0, aqi_ok=True)
        assert windows_are_recommended(ss, sys_cfg()) is False

    def test_band_edges_are_inclusive(self):
        cfg = sys_cfg()
        for edge in (60.0, 75.0):
            ss = sys_state([zone()], outdoor=edge, aqi=10.0, aqi_ok=True)
            assert windows_are_recommended(ss, cfg) is True

    def test_stamped_onto_every_decision_path(self):
        """decide_system wraps _decide_system so the advisory lands even on
        early-return paths like manual override."""
        z = zone(temp=74.0)
        ss = sys_state([z], outdoor=64.0, aqi=20.0, aqi_ok=True)
        ss.manual_override = True
        decision = decide_system(ss, [], sys_cfg())
        assert decision.status == "SYSTEM: MANUAL OVERRIDE"
        assert decision.windows_recommended is True


# ---------------------------------------------------------------------------
# Winter gating — previously untested; the window gate is a behavior change.
# ---------------------------------------------------------------------------

class TestWinterGating:

    def _heat_request(self, outdoor, zones=None, **ss_kw):
        zones = zones or [zone(temp=62.0, target=68.0)]
        cfg = sys_cfg(heat_threshold=68.0, heat_exterior_threshold=60.0)
        ss = sys_state(zones, outdoor=outdoor, season="winter", **ss_kw)
        zd = [decide_zone(z, ss, zone_cfg(target=z.zone_target_temp), cfg) for z in zones]
        return ss, zd, cfg

    def test_window_open_blocks_heat(self):
        """NEW BEHAVIOR: an open window now shuts the furnace off, as originally intended."""
        ss, zd, cfg = self._heat_request(40.0, zones=[zone(temp=62.0, target=68.0, window_open=True)])
        decision = decide_system(ss, zd, cfg)
        assert decision.thermostat_hvac_mode == "off"
        assert decision.heating_blocked is True
        assert decision.cooling_blocked is False
        assert decision.blocked_reason == REASON_WINDOW_OPEN_HEAT
        assert "Heat BLOCKED: window open" in " ".join(decision.reasoning)

    def test_emergency_heat_bypasses_window_gate(self):
        """Safety guarantee for the change above — a stuck-open sensor can't freeze the house."""
        ss, zd, cfg = self._heat_request(20.0, zones=[zone(temp=40.0, target=68.0, window_open=True)])
        decision = decide_system(ss, zd, cfg)
        assert decision.thermostat_hvac_mode == "heat"
        assert decision.heating_blocked is False

    def test_garage_window_does_not_block_heat(self):
        """affects_thermostat=False zones stay excluded, mirroring the summer fix."""
        zones = [
            zone(name="Garage", temp=62.0, target=68.0, window_open=True, affects_thermostat=False),
            zone(name="Office", temp=62.0, target=68.0),
        ]
        ss, zd, cfg = self._heat_request(40.0, zones=zones)
        decision = decide_system(ss, zd, cfg)
        assert decision.thermostat_hvac_mode == "heat"

    def test_relative_gate_blocks_heat_when_warmer_outside(self):
        zones = [zone(name="A", temp=62.0, target=68.0), zone(name="B", temp=64.0, target=70.0)]
        # Exterior threshold raised out of the way so the relative gate is what fires,
        # not the pre-existing outdoor > heat_exterior_threshold block.
        cfg = sys_cfg(heat_threshold=75.0, heat_exterior_threshold=80.0)
        ss = sys_state(zones, outdoor=72.0, season="winter", aqi=15.0, aqi_ok=True)
        zd = [decide_zone(z, ss, zone_cfg(target=z.zone_target_temp), cfg) for z in zones]
        decision = decide_system(ss, zd, cfg)
        assert decision.thermostat_hvac_mode == "off"
        assert decision.heating_blocked is True
        assert decision.blocked_reason == REASON_OPEN_WINDOWS_WARM
        assert "warmer outside, open windows" in " ".join(decision.reasoning)

    def test_relative_gate_uses_max_target_not_min(self):
        """Outdoor 69°F with targets {66, 70}: the 70°F zone is still cold, so heat must
        be ALLOWED. Guards max() vs min() — min() here would leave that zone cold."""
        zones = [zone(name="A", temp=64.0, target=66.0), zone(name="B", temp=64.0, target=70.0)]
        cfg = sys_cfg(heat_threshold=75.0, heat_exterior_threshold=80.0)
        ss = sys_state(zones, outdoor=69.0, season="winter", aqi=15.0, aqi_ok=True)
        zd = [decide_zone(z, ss, zone_cfg(target=z.zone_target_temp), cfg) for z in zones]
        decision = decide_system(ss, zd, cfg)
        assert decision.thermostat_hvac_mode == "heat"

    def test_relative_gate_allows_heat_when_windows_not_openable(self):
        zones = [zone(name="A", temp=62.0, target=68.0)]
        cfg = sys_cfg(heat_threshold=75.0, heat_exterior_threshold=80.0)
        ss = sys_state(zones, outdoor=72.0, season="winter", windows_openable=False)
        zd = [decide_zone(z, ss, zone_cfg(target=68.0), cfg) for z in zones]
        decision = decide_system(ss, zd, cfg)
        assert decision.thermostat_hvac_mode == "heat"
        assert "conditions poor (rain/wind) — heat allowed" in " ".join(decision.reasoning)

    def test_relative_gate_reason_when_aqi_bad(self):
        """Winter mirror of the summer rule: still blocked, different advice."""
        zones = [zone(name="A", temp=62.0, target=68.0)]
        cfg = sys_cfg(heat_threshold=75.0, heat_exterior_threshold=80.0)
        ss = sys_state(zones, outdoor=72.0, season="winter", aqi=180.0, aqi_ok=False)
        zd = [decide_zone(z, ss, zone_cfg(target=68.0), cfg) for z in zones]
        decision = decide_system(ss, zd, cfg)
        assert decision.thermostat_hvac_mode == "off"
        assert decision.heating_blocked is True
        assert decision.blocked_reason == REASON_AQI_HOLD_HEAT

    def test_outdoor_warm_sets_heating_blocked(self):
        """The pre-existing 'Heat BLOCKED: outdoor > threshold' path now raises the flag."""
        ss, zd, cfg = self._heat_request(70.0)
        decision = decide_system(ss, zd, cfg)
        assert decision.thermostat_hvac_mode == "off"
        assert decision.heating_blocked is True
        assert decision.blocked_reason == REASON_OUTDOOR_WARM

    def test_no_heat_demand_leaves_heating_blocked_false(self):
        """A warm winter day with no zone asking for heat is not a 'blocked' state."""
        ss, zd, cfg = self._heat_request(70.0, zones=[zone(temp=70.0, target=68.0)])
        decision = decide_system(ss, zd, cfg)
        assert decision.heating_blocked is False
        assert decision.blocked_reason == ""
