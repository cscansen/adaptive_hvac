"""Pure decision engine for HVAC control — no Home Assistant imports."""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ThermostatMode(Enum):
    """Thermostat HVAC modes."""
    HEAT = "heat"
    COOL = "cool"
    OFF = "off"


class FanMode(Enum):
    """Fan circulation modes."""
    ON = "on"
    AUTO = "auto"


class WholeFanMode(Enum):
    """Whole-house fan modes."""
    ON = "on"
    AUTO = "auto"
    OFF = "off"


@dataclass
class ZoneState:
    """Current state of a single zone."""
    zone_name: str
    floor: str
    temp: float                           # °F, averaged across sensors
    temp_trend: float                     # °F/hr over 30-min window
    humidity: Optional[float] = None      # %, optional
    fans_claimed: set[str] = field(default_factory=set)  # entity IDs user claimed
    window_open: bool = False
    zone_occupied: bool = True
    mode_age_min: float = 0.0             # minutes in current mode
    current_mode: str = "idle"


@dataclass
class SystemState:
    """Current system state across all zones."""
    zone_states: list[ZoneState]
    outdoor_temp: float                   # °F
    forecast_high: float                  # today's forecast high (°F)
    forecast_low: float                   # tonight's forecast low (°F)
    forecast_high_7day_avg: float         # 7-day average high (°F)
    forecast_low_7day_avg: float          # 7-day average low (°F)
    solar_w: float                        # current solar production (W)
    sleep_posture: bool = False           # master suite sleep mode
    house_occupied: bool = True
    unoccupied_hours: float = 0.0         # hours since last occupancy
    manual_override: bool = False
    system_active: bool = True
    hour_of_day: int = 0
    season: str = "shoulder"              # derived season
    season_override: str = "auto"         # auto or explicit override


@dataclass
class ZoneDecision:
    """Zone-level decision output."""
    mode: str                                       # state machine mode
    fan_commands: dict[str, int | None] = field(default_factory=dict)  # entity → speed% or None
    thermal_request: Optional[str] = None          # "heat_68" | "cool_68" | "cool_74" | None
    urgency: int = 0                               # 0–5, drives thermostat priority
    status: str = ""                               # human-readable status
    reasoning: list[str] = field(default_factory=list)


@dataclass
class SystemDecision:
    """System-level decision output."""
    thermostat_hvac_mode: str           # "heat" | "cool" | "off"
    thermostat_setpoint: Optional[float] = None
    whole_house_fan_mode: str = "auto"
    season: str = "shoulder"
    status: str = ""
    reasoning: list[str] = field(default_factory=list)


@dataclass
class ZoneConfig:
    """Configuration for a zone."""
    # Comfort thresholds (°F)
    comfort_upper: float = 70.0
    passive_threshold: float = 72.0
    escalate_threshold: float = 74.0
    emergency_threshold: float = 78.0

    # Fan speeds (%)
    passive_fan_speed: int = 33
    escalate_fan_speed: int = 50
    window_fan_speed: int = 25
    precool_fan_speed: int = 25

    # Setpoints (°F)
    ac_setpoint: float = 68.0
    heat_threshold: float = 68.0
    heat_setpoint: float = 68.0
    emergency_heat_threshold: float = 55.0

    # Setbacks (°F)
    setback_cool_temp: float = 76.0
    setback_heat_temp: float = 62.0
    night_setback_temp: float = 62.0

    # Durations (minutes)
    unoccupied_hours: float = 8.0

    # Forecast triggers (°F)
    precool_trigger: float = 92.0
    preheat_trigger: float = 30.0


@dataclass
class SystemConfig:
    """Configuration for the system."""
    # Season thresholds (°F)
    summer_threshold: float = 75.0
    winter_threshold: float = 40.0

    # Forecast triggers
    precool_trigger: float = 92.0
    preheat_trigger: float = 30.0

    # Hysteresis (polls)
    season_hysteresis_polls: int = 3


def derive_effective_season(state: SystemState, cfg: SystemConfig) -> str:
    """
    Derive effective season considering override.

    Args:
        state: Current system state
        cfg: System configuration

    Returns:
        Effective season: "summer", "shoulder", or "winter"
    """
    if state.season_override != "auto":
        return state.season_override
    return state.season


def decide_zone(
    zone: ZoneState,
    all_zones: list[ZoneState],
    sys_state: SystemState,
    cfg: ZoneConfig,
    sys_cfg: SystemConfig,
) -> ZoneDecision:
    """
    Decide zone-level HVAC state and fan actions.

    Args:
        zone: Target zone state
        all_zones: All zones (for equalization logic)
        sys_state: System state
        cfg: Zone configuration
        sys_cfg: System configuration

    Returns:
        ZoneDecision with mode, fan commands, thermal request, status
    """
    reasoning = []

    # Highest priority: manual override or system inactive
    if sys_state.manual_override:
        return ZoneDecision(
            mode="manual_override",
            fan_commands={},
            status=f"{zone.zone_name}: MANUAL OVERRIDE",
            reasoning=["Manual override active"],
        )

    if not sys_state.system_active:
        return ZoneDecision(
            mode="manual_override",
            fan_commands={},
            status=f"{zone.zone_name}: SYSTEM INACTIVE",
            reasoning=["System paused via switch"],
        )

    # Sensor failsafe: if primary sensor unavailable, safe fallback
    if zone.temp <= 0 or zone.temp >= 200:  # impossible values
        reasoning.append("Sensor unavailable/invalid")
        return ZoneDecision(
            mode="sensor_failsafe",
            fan_commands={},
            status=f"{zone.zone_name}: SENSOR FAILSAFE",
            reasoning=reasoning,
        )

    season = derive_effective_season(sys_state, sys_cfg)

    # Emergency cooling (any season)
    if zone.temp >= cfg.emergency_threshold:
        reasoning.append(f"Temp {zone.temp:.1f}°F ≥ emergency {cfg.emergency_threshold}°F")
        fan_cmds = {f: 100 for f in (zone.zone_name,) if f not in zone.fans_claimed}
        return ZoneDecision(
            mode="emergency_cooling",
            fan_commands=fan_cmds,
            thermal_request="cool_68",
            urgency=5,
            status=f"{zone.zone_name}: EMERGENCY COOLING {zone.temp:.1f}°F",
            reasoning=reasoning,
        )

    # Emergency heating (any season)
    if zone.temp <= cfg.emergency_heat_threshold:
        reasoning.append(f"Temp {zone.temp:.1f}°F ≤ emergency heat {cfg.emergency_heat_threshold}°F")
        return ZoneDecision(
            mode="emergency_heating",
            fan_commands={},
            thermal_request="heat_68",
            urgency=5,
            status=f"{zone.zone_name}: EMERGENCY HEATING {zone.temp:.1f}°F",
            reasoning=reasoning,
        )

    # Setback: unoccupied 8+ hours
    if sys_state.unoccupied_hours >= cfg.unoccupied_hours:
        reasoning.append(f"Unoccupied {sys_state.unoccupied_hours:.1f}h ≥ {cfg.unoccupied_hours}h")
        if season == "summer":
            reasoning.append(f"Summer setback: cool to {cfg.setback_cool_temp}°F")
            return ZoneDecision(
                mode="setback_unoccupied",
                fan_commands={},
                thermal_request=f"cool_{cfg.setback_cool_temp:.0f}",
                urgency=1,
                status=f"{zone.zone_name}: SETBACK UNOCCUPIED {zone.temp:.1f}°F",
                reasoning=reasoning,
            )
        elif season == "winter":
            reasoning.append(f"Winter setback: heat to {cfg.setback_heat_temp}°F")
            return ZoneDecision(
                mode="setback_unoccupied",
                fan_commands={},
                thermal_request=f"heat_{cfg.setback_heat_temp:.0f}",
                urgency=1,
                status=f"{zone.zone_name}: SETBACK UNOCCUPIED {zone.temp:.1f}°F",
                reasoning=reasoning,
            )

    # Night setback (sleep posture on)
    if sys_state.sleep_posture:
        reasoning.append("Sleep posture active")
        reasoning.append(f"Night setback to {cfg.night_setback_temp}°F")
        return ZoneDecision(
            mode="setback_night",
            fan_commands={},
            thermal_request=f"heat_{cfg.night_setback_temp:.0f}",
            urgency=2,
            status=f"{zone.zone_name}: NIGHT SETBACK {zone.temp:.1f}°F",
            reasoning=reasoning,
        )

    # Pre-cool: morning ventilation on hot days
    if (
        sys_state.hour_of_day in range(6, 11)  # 6am-10am
        and sys_state.forecast_high > cfg.precool_trigger
        and sys_state.outdoor_temp < zone.temp
        and season == "summer"
    ):
        reasoning.append(f"Forecast {sys_state.forecast_high:.0f}°F > precool {cfg.precool_trigger:.0f}°F")
        reasoning.append(f"Outdoor {sys_state.outdoor_temp:.1f}°F < zone {zone.temp:.1f}°F — ventilate now")
        fan_cmds = {f: cfg.precool_fan_speed for f in (zone.zone_name,) if f not in zone.fans_claimed}
        return ZoneDecision(
            mode="pre_cool",
            fan_commands=fan_cmds,
            thermal_request="off",
            urgency=2,
            status=f"{zone.zone_name}: PRE-COOL {zone.temp:.1f}°F (outdoor {sys_state.outdoor_temp:.1f}°F)",
            reasoning=reasoning,
        )

    # Pre-heat: pre-warm before cold night
    if (
        sys_state.hour_of_day in range(16, 22)  # 4pm-9pm
        and sys_state.forecast_low < cfg.preheat_trigger
        and season == "winter"
    ):
        reasoning.append(f"Forecast low {sys_state.forecast_low:.0f}°F < preheat {cfg.preheat_trigger:.0f}°F")
        reasoning.append("Pre-heating before cold night")
        return ZoneDecision(
            mode="pre_heat",
            fan_commands={},
            thermal_request="heat_68",
            urgency=2,
            status=f"{zone.zone_name}: PRE-HEAT (cold night forecast)",
            reasoning=reasoning,
        )

    # AC cooling: escalated cooling (thresholds + escalation delay)
    if zone.temp >= cfg.escalate_threshold and zone.mode_age_min >= 30:
        reasoning.append(f"Temp {zone.temp:.1f}°F ≥ escalate {cfg.escalate_threshold}°F for {zone.mode_age_min:.0f}m")
        fan_cmds = {f: cfg.escalate_fan_speed for f in (zone.zone_name,) if f not in zone.fans_claimed}
        return ZoneDecision(
            mode="ac_cooling",
            fan_commands=fan_cmds,
            thermal_request=f"cool_{cfg.ac_setpoint:.0f}",
            urgency=3,
            status=f"{zone.zone_name}: AC COOLING {zone.temp:.1f}°F (trend {zone.temp_trend:+.2f}°F/h)",
            reasoning=reasoning,
        )

    # AC cooling: aggressive escalation if trend is rising fast
    if zone.temp >= cfg.escalate_threshold and zone.temp_trend >= 1.5:
        reasoning.append(f"Temp {zone.temp:.1f}°F ≥ escalate, trend {zone.temp_trend:+.2f}°F/h (aggressive)")
        fan_cmds = {f: cfg.escalate_fan_speed for f in (zone.zone_name,) if f not in zone.fans_claimed}
        return ZoneDecision(
            mode="ac_cooling",
            fan_commands=fan_cmds,
            thermal_request=f"cool_{cfg.ac_setpoint:.0f}",
            urgency=4,
            status=f"{zone.zone_name}: AC COOLING (FAST RISE) {zone.temp:.1f}°F/h",
            reasoning=reasoning,
        )

    # Passive cooling (windows open)
    if zone.window_open and zone.temp >= cfg.passive_threshold and season == "summer":
        reasoning.append(f"Windows open, temp {zone.temp:.1f}°F ≥ passive {cfg.passive_threshold}°F")
        fan_cmds = {f: cfg.window_fan_speed for f in (zone.zone_name,) if f not in zone.fans_claimed}
        return ZoneDecision(
            mode="passive_windows_open",
            fan_commands=fan_cmds,
            thermal_request="off",
            urgency=2,
            status=f"{zone.zone_name}: PASSIVE (WINDOWS OPEN) {zone.temp:.1f}°F",
            reasoning=reasoning,
        )

    # Passive cooling (closed windows, summer)
    if (
        zone.temp >= cfg.passive_threshold
        and not zone.window_open
        and season == "summer"
    ):
        reasoning.append(f"Temp {zone.temp:.1f}°F ≥ passive {cfg.passive_threshold}°F")
        if zone.temp_trend > 0.8:
            reasoning.append(f"Trend {zone.temp_trend:+.2f}°F/h — pre-emptive passive")
        fan_cmds = {f: cfg.passive_fan_speed for f in (zone.zone_name,) if f not in zone.fans_claimed}
        return ZoneDecision(
            mode="passive_cooling",
            fan_commands=fan_cmds,
            thermal_request="off",
            urgency=2,
            status=f"{zone.zone_name}: PASSIVE COOLING {zone.temp:.1f}°F (trend {zone.temp_trend:+.2f}°F/h)",
            reasoning=reasoning,
        )

    # Normal heating (winter)
    if zone.temp <= cfg.heat_threshold and season == "winter":
        reasoning.append(f"Winter: temp {zone.temp:.1f}°F ≤ heat threshold {cfg.heat_threshold}°F")
        return ZoneDecision(
            mode="heating_normal",
            fan_commands={},
            thermal_request=f"heat_{cfg.heat_setpoint:.0f}",
            urgency=2,
            status=f"{zone.zone_name}: HEATING {zone.temp:.1f}°F",
            reasoning=reasoning,
        )

    # Equalization: temperature delta between zones too high
    if len(all_zones) > 1:
        temps = [z.temp for z in all_zones if z.temp > 0]
        if temps:
            max_temp = max(temps)
            min_temp = min(temps)
            delta = max_temp - min_temp
            if delta >= 5.0 and zone.temp == min_temp and season != "winter":
                reasoning.append(f"Floor delta {delta:.1f}°F (max {max_temp:.1f}°F, this zone {zone.temp:.1f}°F)")
                reasoning.append("Equalization: zone is coldest, start fans")
                fan_cmds = {f: cfg.passive_fan_speed for f in (zone.zone_name,) if f not in zone.fans_claimed}
                return ZoneDecision(
                    mode="equalization",
                    fan_commands=fan_cmds,
                    thermal_request="off",
                    urgency=1,
                    status=f"{zone.zone_name}: EQUALIZATION {zone.temp:.1f}°F (delta {delta:.1f}°F)",
                    reasoning=reasoning,
                )

    # Idle: comfortable
    reasoning.append(f"Comfortable: temp {zone.temp:.1f}°F in range")
    return ZoneDecision(
        mode="idle",
        fan_commands={},
        status=f"{zone.zone_name}: IDLE {zone.temp:.1f}°F",
        reasoning=reasoning,
    )


def decide_system(
    sys_state: SystemState,
    zone_decisions: list[ZoneDecision],
    cfg: SystemConfig,
) -> SystemDecision:
    """
    Aggregate zone decisions into system thermostat command.

    Args:
        sys_state: System state
        zone_decisions: Decisions from all zones
        cfg: System configuration

    Returns:
        SystemDecision with thermostat mode/setpoint, whole-house fan, season, status
    """
    reasoning = []
    season = derive_effective_season(sys_state, cfg)
    reasoning.append(f"Season: {season}")

    # Manual override takes precedence
    if sys_state.manual_override:
        reasoning.append("Manual override active")
        return SystemDecision(
            thermostat_hvac_mode="off",
            thermostat_setpoint=None,
            whole_house_fan_mode="auto",
            season=season,
            status="SYSTEM: MANUAL OVERRIDE",
            reasoning=reasoning,
        )

    if not sys_state.system_active:
        reasoning.append("System inactive")
        return SystemDecision(
            thermostat_hvac_mode="off",
            thermostat_setpoint=None,
            whole_house_fan_mode="auto",
            season=season,
            status="SYSTEM: INACTIVE",
            reasoning=reasoning,
        )

    # Aggregate requests by urgency
    max_urgency = max((d.urgency for d in zone_decisions), default=0)
    highest_urgency_decisions = [d for d in zone_decisions if d.urgency == max_urgency]

    # Extract thermal requests from highest urgency
    heat_requests = [d.thermal_request for d in highest_urgency_decisions if d.thermal_request and d.thermal_request.startswith("heat_")]
    cool_requests = [d.thermal_request for d in highest_urgency_decisions if d.thermal_request and d.thermal_request.startswith("cool_")]

    # Decide thermostat mode based on strongest request
    thermostat_hvac_mode = "off"
    thermostat_setpoint = None
    whf_mode = "auto"

    if heat_requests:
        thermostat_hvac_mode = "heat"
        setpoints = [float(r.split("_")[1]) for r in heat_requests]
        thermostat_setpoint = max(setpoints)  # coldest zone wins
        reasoning.append(f"Heat request: {thermostat_setpoint:.0f}°F")
    elif cool_requests:
        thermostat_hvac_mode = "cool"
        setpoints = [float(r.split("_")[1]) for r in cool_requests]
        thermostat_setpoint = min(setpoints)  # hottest zone wins
        reasoning.append(f"Cool request: {thermostat_setpoint:.0f}°F")
    else:
        reasoning.append("No thermal requests — holding current setpoint")

    # Whole-house fan control
    pre_cool_active = any(d.mode == "pre_cool" for d in zone_decisions)
    passive_active = any(d.mode in ["passive_cooling", "passive_windows_open"] for d in zone_decisions)
    equalization_active = any(d.mode == "equalization" for d in zone_decisions)

    if pre_cool_active:
        whf_mode = "on"
        reasoning.append("Pre-cooling: whole-house fan ON")
    elif passive_active or equalization_active:
        whf_mode = "on"
        reasoning.append("Passive/equalization: whole-house fan ON")
    else:
        whf_mode = "auto"

    # Build status string
    zone_statuses = [d.status for d in zone_decisions if d.status]
    zone_summary = " | ".join(zone_statuses) if zone_statuses else "No zones"

    status = f"SYSTEM: {thermostat_hvac_mode.upper()} {thermostat_setpoint or 'OFF'} | {zone_summary}"

    return SystemDecision(
        thermostat_hvac_mode=thermostat_hvac_mode,
        thermostat_setpoint=thermostat_setpoint,
        whole_house_fan_mode=whf_mode,
        season=season,
        status=status,
        reasoning=reasoning,
    )
