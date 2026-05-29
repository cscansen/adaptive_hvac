"""Pure decision engine for Adaptive HVAC — no Home Assistant imports."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ZoneState:
    """Current state of a single zone."""
    zone_name: str
    floor: str
    temp: float                           # °F, averaged across sensors
    temp_trend: float                     # °F/hr over 30-min window
    humidity: Optional[float] = None
    fans_claimed: set[str] = field(default_factory=set)  # entity IDs user claimed
    window_open: bool = False
    zone_occupied: bool = True
    current_mode: str = "idle"
    windows_assumed_open: bool = False    # global windows sensor state
    zone_target_temp: float = 72.0       # fan trigger temp (°F)


@dataclass
class SystemState:
    """Current system state across all zones."""
    zone_states: list[ZoneState]
    outdoor_temp: float                   # °F (current)
    season: str = "summer"               # "summer" or "winter" (calendar-based)
    sleep_posture: bool = False          # kept for future use, not used for control
    house_occupied: bool = True
    manual_override: bool = False
    system_active: bool = True
    windows_assumed_open: bool = False


@dataclass
class ZoneDecision:
    """Zone-level decision output."""
    mode: str
    zone_name: str = ""
    fan_commands: dict[str, int | None] = field(default_factory=dict)
    thermal_request: Optional[str] = None  # "cool" | "heat" | None
    urgency: int = 0                        # 0-5
    status: str = ""
    reasoning: list[str] = field(default_factory=list)


@dataclass
class SystemDecision:
    """System-level decision output."""
    thermostat_hvac_mode: str = "off"    # "heat" | "cool" | "off"
    thermostat_setpoint: Optional[float] = None
    whole_house_fan_mode: str = "auto"
    season: str = "summer"
    status: str = ""
    reasoning: list[str] = field(default_factory=list)


@dataclass
class ZoneConfig:
    """Configuration for a single zone."""
    zone_target_temp: float = 72.0       # fan on above this, fan off at/below
    fan_speed: int = 50                  # % when running
    emergency_cool_threshold: float = 85.0  # safety valve — force cool regardless


@dataclass
class SystemConfig:
    """System-level configuration."""
    ac_setpoint: float = 68.0
    heat_setpoint: float = 68.0
    heat_threshold: float = 68.0
    emergency_heat_threshold: float = 55.0

    # Exterior gating: don't AC if outside is below this
    cool_exterior_threshold: float = 60.0
    # Interior override: if any zone is this many °F above its target, bypass exterior gate
    cool_interior_override_delta: float = 5.0
    # Heat gating: don't heat if outside is above this
    heat_exterior_threshold: float = 60.0


def decide_zone(
    zone: ZoneState,
    sys_state: SystemState,
    cfg: ZoneConfig,
    sys_cfg: SystemConfig,
) -> ZoneDecision:
    """
    Decide zone-level fan action and thermal request.

    Rules:
    - Manual override / system inactive → no action
    - Sensor failsafe → no action
    - Emergency cool (≥ cfg.emergency_cool_threshold) → fan 100%, request cool
    - Emergency heat (≤ sys_cfg.emergency_heat_threshold) → request heat, no fan
    - Temp > zone_target → fan on at cfg.fan_speed, request cool (summer) or none (winter)
    - Temp ≤ zone_target AND winter below heat_threshold → request heat, no fan
    - Otherwise → fan off, no thermal request
    """
    reasoning: list[str] = []

    if sys_state.manual_override:
        return ZoneDecision(
            mode="manual_override",
            zone_name=zone.zone_name,
            status=f"{zone.zone_name}: MANUAL OVERRIDE",
            reasoning=["Manual override active"],
        )

    if not sys_state.system_active:
        return ZoneDecision(
            mode="system_inactive",
            zone_name=zone.zone_name,
            status=f"{zone.zone_name}: SYSTEM INACTIVE",
            reasoning=["System paused via switch"],
        )

    if zone.temp <= 0 or zone.temp >= 200:
        return ZoneDecision(
            mode="sensor_failsafe",
            zone_name=zone.zone_name,
            status=f"{zone.zone_name}: SENSOR FAILSAFE",
            reasoning=["Temp reading invalid"],
        )

    # Emergency cooling — bypass all gating
    if zone.temp >= cfg.emergency_cool_threshold:
        reasoning.append(f"Temp {zone.temp:.1f}°F ≥ emergency {cfg.emergency_cool_threshold:.1f}°F")
        fan_cmds = {} if zone.fans_claimed else {zone.zone_name: 100}
        return ZoneDecision(
            mode="emergency_cooling",
            zone_name=zone.zone_name,
            fan_commands=fan_cmds,
            thermal_request="cool",
            urgency=5,
            status=f"{zone.zone_name}: EMERGENCY COOLING {zone.temp:.1f}°F",
            reasoning=reasoning,
        )

    # Emergency heating — bypass all gating
    if zone.temp <= sys_cfg.emergency_heat_threshold:
        reasoning.append(f"Temp {zone.temp:.1f}°F ≤ emergency heat {sys_cfg.emergency_heat_threshold:.1f}°F")
        return ZoneDecision(
            mode="emergency_heating",
            zone_name=zone.zone_name,
            thermal_request="heat",
            urgency=5,
            status=f"{zone.zone_name}: EMERGENCY HEATING {zone.temp:.1f}°F",
            reasoning=reasoning,
        )

    # Above zone target: request cooling always; local fan only if occupied
    if zone.temp > cfg.zone_target_temp:
        reasoning.append(f"Temp {zone.temp:.1f}°F > target {cfg.zone_target_temp:.1f}°F")
        if zone.fans_claimed:
            fan_cmds = {}
            reasoning.append("Fan claimed by user — not touching")
        elif zone.zone_occupied:
            fan_cmds = {zone.zone_name: cfg.fan_speed}
        else:
            fan_cmds = {zone.zone_name: 0}
            reasoning.append("Zone unoccupied — fan off (thermostat request still active)")
        return ZoneDecision(
            mode="cooling",
            zone_name=zone.zone_name,
            fan_commands=fan_cmds,
            thermal_request="cool",
            urgency=2,
            status=f"{zone.zone_name}: COOLING {zone.temp:.1f}°F > {cfg.zone_target_temp:.1f}°F (trend {zone.temp_trend:+.1f}°F/h)",
            reasoning=reasoning,
        )

    # Below heat threshold: request heat (season filtering happens in decide_system)
    if zone.temp <= sys_cfg.heat_threshold:
        reasoning.append(f"Temp {zone.temp:.1f}°F ≤ heat threshold {sys_cfg.heat_threshold:.1f}°F")
        return ZoneDecision(
            mode="heating",
            zone_name=zone.zone_name,
            fan_commands={},
            thermal_request="heat",
            urgency=2,
            status=f"{zone.zone_name}: HEATING {zone.temp:.1f}°F ≤ {sys_cfg.heat_threshold:.1f}°F",
            reasoning=reasoning,
        )

    # Comfortable: fan off
    reasoning.append(f"Comfortable: temp {zone.temp:.1f}°F ≤ target {cfg.zone_target_temp:.1f}°F")
    fan_cmds = {} if zone.fans_claimed else {zone.zone_name: 0}
    return ZoneDecision(
        mode="idle",
        zone_name=zone.zone_name,
        fan_commands=fan_cmds,
        thermal_request=None,
        urgency=0,
        status=f"{zone.zone_name}: IDLE {zone.temp:.1f}°F",
        reasoning=reasoning,
    )


def decide_system(
    sys_state: SystemState,
    zone_decisions: list[ZoneDecision],
    cfg: SystemConfig,
) -> SystemDecision:
    """
    Aggregate zone decisions into a system thermostat command.

    Gating rules:
    - Manual override / inactive → off
    - Windows open (summer) → off, whole-house fan on
    - Emergency requests bypass all gating
    - Summer cooling: allowed if outdoor ≥ cool_exterior_threshold OR any zone is
      cool_interior_override_delta above its target
    - Winter heating: allowed if outdoor ≤ heat_exterior_threshold
    """
    reasoning: list[str] = []
    season = sys_state.season
    reasoning.append(f"Season: {season}")

    if sys_state.manual_override:
        return SystemDecision(
            thermostat_hvac_mode="off",
            season=season,
            status="SYSTEM: MANUAL OVERRIDE",
            reasoning=["Manual override active"],
        )

    if not sys_state.system_active:
        return SystemDecision(
            thermostat_hvac_mode="off",
            season=season,
            status="SYSTEM: INACTIVE",
            reasoning=["System paused via switch"],
        )

    # Emergency requests bypass gating
    emergency_cool = any(d.mode == "emergency_cooling" for d in zone_decisions)
    emergency_heat = any(d.mode == "emergency_heating" for d in zone_decisions)

    if emergency_cool:
        reasoning.append("Emergency cooling active — bypass gating")
        return SystemDecision(
            thermostat_hvac_mode="cool",
            thermostat_setpoint=cfg.ac_setpoint,
            season=season,
            status=f"SYSTEM: EMERGENCY COOL → {cfg.ac_setpoint:.0f}°F",
            reasoning=reasoning,
        )

    if emergency_heat:
        reasoning.append("Emergency heating active — bypass gating")
        return SystemDecision(
            thermostat_hvac_mode="heat",
            thermostat_setpoint=cfg.heat_setpoint,
            season=season,
            status=f"SYSTEM: EMERGENCY HEAT → {cfg.heat_setpoint:.0f}°F",
            reasoning=reasoning,
        )

    # Collect zone requests
    cooling_zones = [d for d in zone_decisions if d.thermal_request == "cool"]
    heating_zones = [d for d in zone_decisions if d.thermal_request == "heat"]

    outdoor = sys_state.outdoor_temp
    reasoning.append(f"Outdoor: {outdoor:.1f}°F")

    if season == "summer":
        if cooling_zones:
            # Check exterior gate
            allow_cool = outdoor >= cfg.cool_exterior_threshold
            if allow_cool:
                reasoning.append(f"AC allowed: outdoor {outdoor:.1f}°F ≥ {cfg.cool_exterior_threshold:.1f}°F")
            else:
                # Interior override: any zone significantly above its target?
                for zone in sys_state.zone_states:
                    delta = zone.temp - zone.zone_target_temp
                    if delta >= cfg.cool_interior_override_delta:
                        allow_cool = True
                        reasoning.append(
                            f"AC allowed: {zone.zone_name} is {delta:.1f}°F above target "
                            f"(override threshold {cfg.cool_interior_override_delta:.1f}°F) "
                            f"despite outdoor {outdoor:.1f}°F < {cfg.cool_exterior_threshold:.1f}°F"
                        )
                        break

                if not allow_cool:
                    reasoning.append(
                        f"AC BLOCKED: outdoor {outdoor:.1f}°F < {cfg.cool_exterior_threshold:.1f}°F "
                        f"and no zone exceeds interior override delta"
                    )

            if allow_cool:
                zone_statuses = " | ".join(d.status for d in cooling_zones)
                return SystemDecision(
                    thermostat_hvac_mode="cool",
                    thermostat_setpoint=cfg.ac_setpoint,
                    season=season,
                    status=f"SYSTEM: COOL → {cfg.ac_setpoint:.0f}°F | {zone_statuses}",
                    reasoning=reasoning,
                )

        zone_statuses = " | ".join(d.status for d in zone_decisions if d.status)
        return SystemDecision(
            thermostat_hvac_mode="off",
            season=season,
            status=f"SYSTEM: OFF (summer, no cooling) | {zone_statuses}",
            reasoning=reasoning,
        )

    elif season == "winter":
        if heating_zones:
            allow_heat = outdoor <= cfg.heat_exterior_threshold
            if allow_heat:
                reasoning.append(f"Heat allowed: outdoor {outdoor:.1f}°F ≤ {cfg.heat_exterior_threshold:.1f}°F")
                zone_statuses = " | ".join(d.status for d in heating_zones)
                return SystemDecision(
                    thermostat_hvac_mode="heat",
                    thermostat_setpoint=cfg.heat_setpoint,
                    season=season,
                    status=f"SYSTEM: HEAT → {cfg.heat_setpoint:.0f}°F | {zone_statuses}",
                    reasoning=reasoning,
                )
            else:
                reasoning.append(f"Heat BLOCKED: outdoor {outdoor:.1f}°F > {cfg.heat_exterior_threshold:.1f}°F")

        zone_statuses = " | ".join(d.status for d in zone_decisions if d.status)
        return SystemDecision(
            thermostat_hvac_mode="off",
            season=season,
            status=f"SYSTEM: OFF (winter, no heating) | {zone_statuses}",
            reasoning=reasoning,
        )

    # Fallback (shouldn't happen with binary season model)
    return SystemDecision(
        thermostat_hvac_mode="off",
        season=season,
        status="SYSTEM: OFF",
        reasoning=reasoning + ["Unknown season — system off"],
    )
