"""Pure decision engine for Adaptive HVAC — no Home Assistant imports."""

from dataclasses import dataclass, field, replace
from typing import Optional


@dataclass
class ZoneState:
    """Current state of a single zone."""
    zone_name: str
    floor: str
    temp: float                           # °F, averaged across sensors
    temp_trend: float                     # °F/hr over 30-min window
    humidity: Optional[float] = None
    fan_locked: bool = False
    window_open: bool = False
    zone_occupied: bool = True
    affects_thermostat: bool = True      # False = fans only, never calls thermostat
    current_mode: str = "idle"
    zone_target_temp: float = 72.0       # fan trigger temp (°F)


@dataclass
class SystemState:
    """Current system state across all zones."""
    zone_states: list[ZoneState]
    outdoor_temp: float                   # °F (current)
    season: str = "summer"               # "summer" or "winter" (calendar-based)
    sleep_posture: bool = False          # kept for future use, not used for control
    house_occupied: bool = True
    windows_openable: bool = True        # False when rain or high wind makes opening impractical
    manual_override: bool = False
    system_active: bool = True


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
    # True when zones demand cooling but all gating paths block it
    cooling_blocked: bool = False


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
    # Upstairs demand boost: lower AC setpoint by this many °F when zones request cooling
    upstairs_demand_boost: float = 0.0
    # Floor circulation: run thermostat fan when any two floors differ by this many °F
    fan_circulation_delta: float = 2.0


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
    - Emergency heat: evaluated in decide_system() using real configured threshold
    - Temp >= zone_target → fan on if occupied (not locked); fan off if unoccupied; thermostat request if affects_thermostat
    - Temp < zone_target AND winter below heat_threshold → request heat, no fan
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

    # Emergency cooling — fans always 100%; thermostat call only if zone affects thermostat
    if zone.temp >= cfg.emergency_cool_threshold:
        reasoning.append(f"Temp {zone.temp:.1f}°F ≥ emergency {cfg.emergency_cool_threshold:.1f}°F")
        if not zone.affects_thermostat:
            reasoning.append("Zone does not affect thermostat — emergency fans only")
        fan_cmds = {zone.zone_name: 100}
        return ZoneDecision(
            mode="emergency_cooling",
            zone_name=zone.zone_name,
            fan_commands=fan_cmds,
            thermal_request="cool" if zone.affects_thermostat else None,
            urgency=5,
            status=f"{zone.zone_name}: EMERGENCY COOLING {zone.temp:.1f}°F",
            reasoning=reasoning,
        )


    # At or above zone target: fan on if occupied; thermostat request if affects_thermostat
    if zone.temp >= cfg.zone_target_temp:
        reasoning.append(f"Temp {zone.temp:.1f}°F ≥ target {cfg.zone_target_temp:.1f}°F")
        if zone.fan_locked:
            fan_cmds = {}
            reasoning.append("Fan locked by user — not touching")
        elif zone.zone_occupied:
            fan_cmds = {zone.zone_name: cfg.fan_speed}
        else:
            fan_cmds = {zone.zone_name: 0}
            reasoning.append("Zone unoccupied — fan off (thermostat request still active)")
        thermal = "cool" if zone.affects_thermostat else None
        if not zone.affects_thermostat:
            reasoning.append("Zone does not affect thermostat — fans only")
        return ZoneDecision(
            mode="cooling",
            zone_name=zone.zone_name,
            fan_commands=fan_cmds,
            thermal_request=thermal,
            urgency=2,
            status=f"{zone.zone_name}: COOLING {zone.temp:.1f}°F > {cfg.zone_target_temp:.1f}°F (trend {zone.temp_trend:+.1f}°F/h)",
            reasoning=reasoning,
        )

    # Below heat threshold: request heat only if zone affects thermostat
    if zone.temp <= sys_cfg.heat_threshold:
        reasoning.append(f"Temp {zone.temp:.1f}°F ≤ heat threshold {sys_cfg.heat_threshold:.1f}°F")
        thermal = "heat" if zone.affects_thermostat else None
        if not zone.affects_thermostat:
            reasoning.append("Zone does not affect thermostat — fans only")
        return ZoneDecision(
            mode="heating",
            zone_name=zone.zone_name,
            fan_commands={},
            thermal_request=thermal,
            urgency=2,
            status=f"{zone.zone_name}: HEATING {zone.temp:.1f}°F ≤ {sys_cfg.heat_threshold:.1f}°F",
            reasoning=reasoning,
        )

    # Comfortable: fan off
    reasoning.append(f"Comfortable: temp {zone.temp:.1f}°F < target {cfg.zone_target_temp:.1f}°F")
    fan_cmds = {} if (zone.fan_locked and zone.zone_occupied) else {zone.zone_name: 0}
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

    # Floor circulation fan mode — computed before gating so it applies on all off paths.
    # In summer, suppressed when AC is off (circulating warm air without cold supply has no benefit).
    fan_mode, fan_reasoning = _floor_fan_mode(sys_state.zone_states, cfg, sys_state.sleep_posture)

    def _summer_off_fan_mode() -> tuple[str, list[str]]:
        """Return fan_mode/reasoning for a summer system-off decision."""
        if season == "summer" and fan_mode == "on":
            return "auto", fan_reasoning + ["AC not active — floor circulation suppressed (no cold air to distribute)"]
        return fan_mode, fan_reasoning

    # Emergency requests bypass gating (fan stays auto — HVAC fan already runs with compressor/furnace)
    emergency_cool = any(d.mode == "emergency_cooling" for d in zone_decisions)
    # Emergency heat is evaluated here (not in decide_zone) so the real configured threshold is used
    emergency_heat_zones = [
        z for z in sys_state.zone_states
        if z.temp <= cfg.emergency_heat_threshold and z.affects_thermostat
    ]
    emergency_heat = bool(emergency_heat_zones)

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
        trigger = ", ".join(f"{z.zone_name} {z.temp:.1f}°F" for z in emergency_heat_zones)
        reasoning.append(f"Emergency heating active ({trigger}) — bypass gating")
        return SystemDecision(
            thermostat_hvac_mode="heat",
            thermostat_setpoint=cfg.heat_setpoint,
            season=season,
            status=f"SYSTEM: EMERGENCY HEAT → {cfg.heat_setpoint:.0f}°F",
            reasoning=reasoning,
        )

    # Window open gate — block cooling if any zone reports a window open
    if season == "summer":
        open_zones = [z.zone_name for z in sys_state.zone_states if z.window_open and z.affects_thermostat]
        if open_zones:
            zone_list = ", ".join(open_zones)
            reasoning.append(f"AC BLOCKED: window open in {zone_list}")
            off_fan_mode, off_fan_reasoning = _summer_off_fan_mode()
            return SystemDecision(
                thermostat_hvac_mode="off",
                whole_house_fan_mode=off_fan_mode,
                season=season,
                status=f"SYSTEM: OFF (window open — {zone_list})",
                reasoning=reasoning + off_fan_reasoning,
                cooling_blocked=True,
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

            # Relative gate: if outdoor is cooler than the requesting zones' targets AND
            # windows can be opened, natural ventilation is the better tool.
            if allow_cool:
                cooling_zone_names = {d.zone_name for d in cooling_zones}
                requesting_states = [z for z in sys_state.zone_states if z.zone_name in cooling_zone_names]
                if requesting_states:
                    min_target = min(z.zone_target_temp for z in requesting_states)
                    if outdoor < min_target:
                        if sys_state.windows_openable:
                            allow_cool = False
                            reasoning.append(
                                f"AC BLOCKED: outdoor {outdoor:.1f}°F < zone target {min_target:.1f}°F "
                                f"— cooler outside, open windows"
                            )
                        else:
                            reasoning.append(
                                f"Outdoor {outdoor:.1f}°F < zone target {min_target:.1f}°F "
                                f"but conditions poor (rain/wind) — AC allowed"
                            )

            if allow_cool:
                boost = cfg.upstairs_demand_boost if cooling_zones else 0.0
                adjusted_setpoint = cfg.ac_setpoint - boost
                if boost > 0:
                    reasoning.append(
                        f"Upstairs demand boost: setpoint {cfg.ac_setpoint:.0f}°F → {adjusted_setpoint:.0f}°F"
                    )
                zone_statuses = " | ".join(d.status for d in cooling_zones)
                return SystemDecision(
                    thermostat_hvac_mode="cool",
                    thermostat_setpoint=adjusted_setpoint,
                    whole_house_fan_mode=fan_mode,
                    season=season,
                    status=f"SYSTEM: COOL → {adjusted_setpoint:.0f}°F | {zone_statuses}",
                    reasoning=reasoning + fan_reasoning,
                )

        zone_statuses = " | ".join(d.status for d in zone_decisions if d.status)
        off_fan_mode, off_fan_reasoning = _summer_off_fan_mode()
        return SystemDecision(
            thermostat_hvac_mode="off",
            whole_house_fan_mode=off_fan_mode,
            season=season,
            status=f"SYSTEM: OFF (summer, no cooling) | {zone_statuses}",
            reasoning=reasoning + off_fan_reasoning,
            # cooling_blocked when zones were requesting cool but gates prevented it
            cooling_blocked=bool(cooling_zones) and any("AC BLOCKED" in r for r in reasoning),
        )

    elif season == "winter":
        if heating_zones:
            allow_heat = outdoor <= cfg.heat_exterior_threshold
            if allow_heat:
                reasoning.append(f"Heat allowed: outdoor {outdoor:.1f}°F ≤ {cfg.heat_exterior_threshold:.1f}°F")
                boost = cfg.upstairs_demand_boost if heating_zones else 0.0
                adjusted_setpoint = cfg.heat_setpoint + boost
                if boost > 0:
                    reasoning.append(
                        f"Upstairs demand boost: setpoint {cfg.heat_setpoint:.0f}°F → {adjusted_setpoint:.0f}°F"
                    )
                zone_statuses = " | ".join(d.status for d in heating_zones)
                return SystemDecision(
                    thermostat_hvac_mode="heat",
                    thermostat_setpoint=adjusted_setpoint,
                    whole_house_fan_mode=fan_mode,
                    season=season,
                    status=f"SYSTEM: HEAT → {adjusted_setpoint:.0f}°F | {zone_statuses}",
                    reasoning=reasoning + fan_reasoning,
                )
            else:
                reasoning.append(f"Heat BLOCKED: outdoor {outdoor:.1f}°F > {cfg.heat_exterior_threshold:.1f}°F")

        zone_statuses = " | ".join(d.status for d in zone_decisions if d.status)
        return SystemDecision(
            thermostat_hvac_mode="off",
            whole_house_fan_mode=fan_mode,
            season=season,
            status=f"SYSTEM: OFF (winter, no heating) | {zone_statuses}",
            reasoning=reasoning + fan_reasoning,
        )

    # Fallback (shouldn't happen with binary season model)
    return SystemDecision(
        thermostat_hvac_mode="off",
        whole_house_fan_mode=fan_mode,
        season=season,
        status="SYSTEM: OFF",
        reasoning=reasoning + fan_reasoning + ["Unknown season — system off"],
    )


def _floor_fan_mode(
    zone_states: list[ZoneState],
    cfg: SystemConfig,
    sleep_posture: bool,
) -> tuple[str, list[str]]:
    """
    Determine whole-house fan mode based on floor temperature differential.

    Groups zones by their floor ID (zones with no floor are excluded).
    If any two floors differ by >= cfg.fan_circulation_delta, returns "on".
    Otherwise returns "auto". Suppression when AC is off is handled in decide_system().
    """
    floors: dict[str, list[float]] = {}
    for z in zone_states:
        if z.floor and z.temp > 0:
            floors.setdefault(z.floor, []).append(z.temp)

    if len(floors) < 2:
        return "auto", []

    floor_avgs = {f: sum(temps) / len(temps) for f, temps in floors.items()}
    max_avg = max(floor_avgs.values())
    min_avg = min(floor_avgs.values())
    delta = max_avg - min_avg

    if delta >= cfg.fan_circulation_delta:
        hot_floor = max(floor_avgs, key=floor_avgs.__getitem__)
        cool_floor = min(floor_avgs, key=floor_avgs.__getitem__)
        reasoning = [
            f"Floor circulation: {hot_floor} {floor_avgs[hot_floor]:.1f}°F vs "
            f"{cool_floor} {floor_avgs[cool_floor]:.1f}°F "
            f"(Δ{delta:.1f}°F ≥ {cfg.fan_circulation_delta:.1f}°F threshold) — fan ON"
        ]
        return "on", reasoning

    floor_summary = ", ".join(f"{f} {avg:.1f}°F" for f, avg in floor_avgs.items())
    return "auto", [f"Floor circulation: Δ{delta:.1f}°F < threshold ({floor_summary}) — fan auto"]


def annotate_zone_decisions(
    zone_decisions: list[ZoneDecision],
    system_decision: SystemDecision,
) -> list[ZoneDecision]:
    """
    Relabel zone modes to reflect whether the system is actually heating/cooling.

    A zone may request cooling/heating but the system can block it (window open,
    outdoor gate, etc.). In that case the zone is only running its fans — label
    it PASSIVE COOLING/HEATING so the status is honest.
    """
    result = []
    for d in zone_decisions:
        fans_running = any(spd > 0 for spd in d.fan_commands.values())

        if d.thermal_request == "cool" and system_decision.thermostat_hvac_mode != "cool":
            if fans_running:
                # Fans spinning but AC blocked — genuinely passive (airflow without compressor)
                d = replace(
                    d,
                    mode="passive_cooling",
                    status=d.status.replace("COOLING", "PASSIVE COOLING"),
                    reasoning=d.reasoning + ["AC not active — fans only"],
                )
            else:
                # No fans, no AC — zone is warm but nothing is running
                d = replace(
                    d,
                    mode="idle_warm",
                    status=d.status.replace("COOLING", "WARM"),
                    reasoning=d.reasoning + ["AC not active, no fans running"],
                )
        elif d.thermal_request == "heat" and system_decision.thermostat_hvac_mode != "heat":
            if fans_running:
                d = replace(
                    d,
                    mode="passive_heating",
                    status=d.status.replace("HEATING", "PASSIVE HEATING"),
                    reasoning=d.reasoning + ["Heat not active — passive only"],
                )
            else:
                d = replace(
                    d,
                    mode="idle_cold",
                    status=d.status.replace("HEATING", "COLD"),
                    reasoning=d.reasoning + ["Heat not active, no fans running"],
                )
        result.append(d)
    return result
