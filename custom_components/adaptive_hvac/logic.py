"""Pure decision engine for Adaptive HVAC — no Home Assistant imports."""

import math
from dataclasses import dataclass, field, replace
from typing import Optional


def _round_half_up(value: float) -> float:
    """Round to the nearest whole degree, halves rounding up (not Python's banker's
    rounding) — matches how thermostats round a fractional setpoint they receive."""
    return math.floor(value + 0.5)


# Structured blocked-reason codes. Defined here rather than in const.py because this
# module is deliberately import-free (const.py re-exports them for the entity modules).
REASON_WINDOW_OPEN = "window_open"                  # summer: AC off, window open
REASON_OUTDOOR_COLD = "outdoor_cold"                # summer: below cool_exterior_threshold
REASON_OPEN_WINDOWS_BETTER = "open_windows_better"  # summer: cooler outside, air is clean
REASON_AQI_HOLD = "aqi_hold"                        # summer: cooler outside but smoky

REASON_WINDOW_OPEN_HEAT = "window_open_heat"        # winter: furnace off, window open
REASON_OUTDOOR_WARM = "outdoor_warm"                # winter: above heat_exterior_threshold
REASON_OPEN_WINDOWS_WARM = "open_windows_warm"      # winter: warmer outside, air is clean
REASON_AQI_HOLD_HEAT = "aqi_hold_heat"              # winter: warmer outside but smoky


# US EPA AQI breakpoints — (upper bound inclusive, label)
_AQI_BANDS = [
    (50, "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for Sensitive Groups"),
    (200, "Unhealthy"),
    (300, "Very Unhealthy"),
]


def aqi_category(value: Optional[float]) -> str:
    """Map a US AQI number onto its EPA category label."""
    if value is None:
        return "Unknown"
    for upper, label in _AQI_BANDS:
        if value <= upper:
            return label
    return "Hazardous"


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
    outdoor_aqi: Optional[float] = None  # US AQI, None when unavailable
    # Computed by the coordinator (fail-closed: unknown AQI is not "ok"). Never unblocks
    # the HVAC — it only decides whether "open the windows instead" is honest advice.
    aqi_ok: bool = True


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
    # Winter mirror of the above
    heating_blocked: bool = False
    # Machine-readable companion to the "AC BLOCKED"/"Heat BLOCKED" reasoning line
    blocked_reason: str = ""
    # Advisory only — never gates the thermostat. See windows_are_recommended().
    windows_recommended: bool = False


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
    # Absolute band in which opening the windows is worth recommending (°F)
    window_min_outdoor: float = 60.0
    window_max_outdoor: float = 75.0


def windows_are_recommended(sys_state: SystemState, cfg: SystemConfig) -> bool:
    """Green light to open up: outdoor air is in the comfortable band, no rain or high
    wind, and clean air.

    Deliberately independent of season and of the zone targets. The season model is
    binary and calendar-driven (October reads as "winter"), so a target-relative rule
    would refuse to suggest windows on a 62°F October afternoon — precisely the
    shoulder-season case this is for. Fresh air is the goal; the band decides, not the
    thermostat. Unknown AQI counts as not-green.

    Advisory only: this never gates the thermostat.
    """
    if not sys_state.windows_openable or not sys_state.aqi_ok:
        return False
    return cfg.window_min_outdoor <= sys_state.outdoor_temp <= cfg.window_max_outdoor


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
    """Aggregate zone decisions into a system thermostat command, then stamp the
    advisory windows recommendation onto whichever decision came back.

    The recommendation is computed here rather than inside _decide_system so it lands
    on every return path — it is independent of the gating outcome by design.
    """
    decision = _decide_system(sys_state, zone_decisions, cfg)
    return replace(decision, windows_recommended=windows_are_recommended(sys_state, cfg))


def _decide_system(
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

    # Window open gate — an open window means the house is being aired out on purpose,
    # so neither the AC nor the furnace should fight it. Runs in both seasons; the
    # emergency returns above still take precedence, so a stuck-open sensor can't
    # freeze or bake the house.
    open_zones = [z.zone_name for z in sys_state.zone_states if z.window_open and z.affects_thermostat]
    if open_zones:
        zone_list = ", ".join(open_zones)
        summer = season == "summer"
        label = "AC" if summer else "Heat"
        reasoning.append(f"{label} BLOCKED: window open in {zone_list}")
        # Already season-aware — returns plain fan_mode outside summer.
        fan_mode_open, fan_reasoning_open = _summer_off_fan_mode()
        return SystemDecision(
            thermostat_hvac_mode="off",
            whole_house_fan_mode=fan_mode_open,
            season=season,
            status=f"SYSTEM: OFF (window open — {zone_list})",
            reasoning=reasoning + fan_reasoning_open,
            cooling_blocked=summer,
            heating_blocked=not summer,
            blocked_reason=REASON_WINDOW_OPEN if summer else REASON_WINDOW_OPEN_HEAT,
        )

    # Collect zone requests
    cooling_zones = [d for d in zone_decisions if d.thermal_request == "cool"]
    heating_zones = [d for d in zone_decisions if d.thermal_request == "heat"]

    outdoor = sys_state.outdoor_temp
    reasoning.append(f"Outdoor: {outdoor:.1f}°F")
    blocked_reason = ""

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
                    blocked_reason = REASON_OUTDOOR_COLD
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
                            # Blocked either way — AQI changes the advice, not the outcome.
                            allow_cool = False
                            if sys_state.aqi_ok:
                                blocked_reason = REASON_OPEN_WINDOWS_BETTER
                                reasoning.append(
                                    f"AC BLOCKED: outdoor {outdoor:.1f}°F < zone target {min_target:.1f}°F "
                                    f"— cooler outside, open windows"
                                )
                            else:
                                blocked_reason = REASON_AQI_HOLD
                                aqi_txt = (
                                    f"{sys_state.outdoor_aqi:.0f}"
                                    if sys_state.outdoor_aqi is not None else "unknown"
                                )
                                reasoning.append(
                                    f"AC BLOCKED: outdoor {outdoor:.1f}°F < zone target {min_target:.1f}°F "
                                    f"but AQI {aqi_txt} — keep windows shut"
                                )
                        else:
                            reasoning.append(
                                f"Outdoor {outdoor:.1f}°F < zone target {min_target:.1f}°F "
                                f"but conditions poor (rain/wind) — AC allowed"
                            )

            if allow_cool:
                boost = cfg.upstairs_demand_boost if cooling_zones else 0.0
                # Round to a whole degree — most thermostats only accept integer setpoints and
                # silently round a fractional value themselves, which then no longer matches
                # what the dashboard shows (e.g. 68 - 1.5 = 66.5 silently became 67 on the device).
                adjusted_setpoint = _round_half_up(cfg.ac_setpoint - boost)
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
            blocked_reason=blocked_reason if cooling_zones else "",
        )

    elif season == "winter":
        if heating_zones:
            allow_heat = outdoor <= cfg.heat_exterior_threshold
            if not allow_heat:
                blocked_reason = REASON_OUTDOOR_WARM
                reasoning.append(f"Heat BLOCKED: outdoor {outdoor:.1f}°F > {cfg.heat_exterior_threshold:.1f}°F")
            else:
                reasoning.append(f"Heat allowed: outdoor {outdoor:.1f}°F ≤ {cfg.heat_exterior_threshold:.1f}°F")

                # Relative gate — mirror of the summer one. Uses max() so heat is only
                # withheld once outdoor air exceeds the *warmest* zone still asking;
                # a cooler zone must never be left cold by a warmer one's satisfaction.
                heating_zone_names = {d.zone_name for d in heating_zones}
                requesting_states = [z for z in sys_state.zone_states if z.zone_name in heating_zone_names]
                if requesting_states:
                    max_target = max(z.zone_target_temp for z in requesting_states)
                    if outdoor > max_target:
                        if sys_state.windows_openable:
                            # Blocked either way — AQI changes the advice, not the outcome.
                            allow_heat = False
                            if sys_state.aqi_ok:
                                blocked_reason = REASON_OPEN_WINDOWS_WARM
                                reasoning.append(
                                    f"Heat BLOCKED: outdoor {outdoor:.1f}°F > zone target {max_target:.1f}°F "
                                    f"— warmer outside, open windows"
                                )
                            else:
                                blocked_reason = REASON_AQI_HOLD_HEAT
                                aqi_txt = (
                                    f"{sys_state.outdoor_aqi:.0f}"
                                    if sys_state.outdoor_aqi is not None else "unknown"
                                )
                                reasoning.append(
                                    f"Heat BLOCKED: outdoor {outdoor:.1f}°F > zone target {max_target:.1f}°F "
                                    f"but AQI {aqi_txt} — keep windows shut"
                                )
                        else:
                            reasoning.append(
                                f"Outdoor {outdoor:.1f}°F > zone target {max_target:.1f}°F "
                                f"but conditions poor (rain/wind) — heat allowed"
                            )

            if allow_heat:
                boost = cfg.upstairs_demand_boost if heating_zones else 0.0
                adjusted_setpoint = _round_half_up(cfg.heat_setpoint + boost)
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

        zone_statuses = " | ".join(d.status for d in zone_decisions if d.status)
        return SystemDecision(
            thermostat_hvac_mode="off",
            whole_house_fan_mode=fan_mode,
            season=season,
            status=f"SYSTEM: OFF (winter, no heating) | {zone_statuses}",
            reasoning=reasoning + fan_reasoning,
            # heating_blocked when zones were requesting heat but gates prevented it
            heating_blocked=bool(heating_zones) and any("Heat BLOCKED" in r for r in reasoning),
            blocked_reason=blocked_reason if heating_zones else "",
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
