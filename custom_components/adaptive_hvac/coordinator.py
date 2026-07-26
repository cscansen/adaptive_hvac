"""Data coordinators for Adaptive HVAC zones and system."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from collections import deque

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ENTRY_TYPE_ZONE,
    SCAN_INTERVAL_MINUTES,
    DEFAULT_ZONE_TARGET_TEMP,
    DEFAULT_FAN_SPEED,
    DEFAULT_AC_SETPOINT,
    DEFAULT_HEAT_THRESHOLD,
    DEFAULT_HEAT_SETPOINT,
    DEFAULT_EMERGENCY_HEAT_THRESHOLD,
    DEFAULT_EMERGENCY_COOL_THRESHOLD,

    DEFAULT_WINTER_START_MONTH,
    DEFAULT_WINTER_END_MONTH,
    DEFAULT_COOL_EXTERIOR_THRESHOLD,
    DEFAULT_COOL_INTERIOR_OVERRIDE_DELTA,
    DEFAULT_HEAT_EXTERIOR_THRESHOLD,
    DEFAULT_AUTO_CONTROL_ENABLED,
    DEFAULT_AFFECTS_THERMOSTAT,
    DEFAULT_UPSTAIRS_DEMAND_BOOST,
    DEFAULT_FAN_CIRCULATION_DELTA,
    DEFAULT_NIGHT_AC_SETPOINT,
    DEFAULT_NIGHT_HEAT_SETPOINT,
    DEFAULT_NIGHT_START_HOUR,
    DEFAULT_NIGHT_END_HOUR,
    SEASON_SUMMER,
    SEASON_WINTER,
)
from .logic import (
    ZoneState,
    SystemState,
    ZoneConfig,
    SystemConfig,
    ZoneDecision,
    SystemDecision,
    decide_zone,
    decide_system,
    annotate_zone_decisions,
)

_LOGGER = logging.getLogger(__name__)

TREND_WINDOW_MIN = 30


class ZoneCoordinator(DataUpdateCoordinator):
    """Coordinator for a single HVAC zone."""

    def __init__(
        self,
        hass: HomeAssistant,
        zone_name: str,
        zone_config: dict,
        config_entry: Optional["ConfigEntry"] = None,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=f"Adaptive HVAC - {zone_name}",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
            config_entry=config_entry,
        )
        self.zone_name = zone_name
        self.zone_config = zone_config
        self._temp_samples: deque[float] = deque(maxlen=30 // SCAN_INTERVAL_MINUTES)  # 30-min window
        self.last_decision: Optional[ZoneDecision] = None
        self._mode_entered_at: Optional[datetime] = None
        self._fan_locked: bool = False
        self.runtime_target_temp: float = float(zone_config.get("zone_target_temp", DEFAULT_ZONE_TARGET_TEMP))

    @property
    def zone_slug(self) -> str:
        import re
        return re.sub(r"[^a-z0-9_]", "", self.zone_name.lower().replace(" ", "_"))

    def _read_temp(self) -> float:
        """Read and average zone temperature sensors."""
        temp_entities = self.zone_config.get("temp_sensors", [])
        if not temp_entities:
            _LOGGER.warning(f"Zone {self.zone_name}: no temp_sensors configured")
            return 0.0

        temps = []
        for entity_id in temp_entities:
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    temps.append(float(state.state))
                except ValueError:
                    _LOGGER.warning(f"Zone {self.zone_name}: invalid temp state '{state.state}' from {entity_id}")

        return sum(temps) / len(temps) if temps else 0.0

    def stale_sensors(self) -> list[str]:
        """Return entity IDs of temp sensors that are missing or not reporting (unavailable/unknown)."""
        stale = []
        for entity_id in self.zone_config.get("temp_sensors", []):
            state = self.hass.states.get(entity_id)
            if state is None:
                stale.append(entity_id)
            elif state.state in ("unavailable", "unknown"):
                stale.append(entity_id)
        return stale

    def _read_humidity(self) -> Optional[float]:
        """Read humidity sensor(s) — averaged if multiple."""
        entities = self.zone_config.get("humidity_sensor", [])
        if isinstance(entities, str):
            entities = [entities] if entities else []

        values = []
        for entity_id in entities:
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    values.append(float(state.state))
                except ValueError:
                    pass

        return sum(values) / len(values) if values else None

    def _read_window_open(self) -> bool:
        """True if any zone window sensor is open."""
        entities = self.zone_config.get("window_sensor", [])
        if isinstance(entities, str):
            entities = [entities] if entities else []

        return any(
            self.hass.states.is_state(e, "on") or self.hass.states.is_state(e, "open")
            for e in entities
        )

    def _read_occupancy(self) -> bool:
        """True if any zone occupancy sensor is occupied (default True if none configured)."""
        entities = self.zone_config.get("occupancy_sensor", [])
        if isinstance(entities, str):
            entities = [entities] if entities else []

        if not entities:
            return True

        return any(self.hass.states.is_state(e, "on") for e in entities)

    @property
    def fan_locked(self) -> bool:
        return self._fan_locked

    def set_fan_lock(self, locked: bool) -> None:
        self._fan_locked = locked
        if self.last_decision is not None:
            self.async_set_updated_data(self.last_decision)
        self.hass.async_create_task(self.async_request_refresh())

    @callback
    def _handle_fan_change(self, event) -> None:
        """Lock fan when user manually changes a fan in this zone."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state is None:
            return
        # Skip availability transitions — these are HA startup restores, not user actions.
        if old_state is None or old_state.state in ("unavailable", "unknown"):
            return
        if new_state.state in ("unavailable", "unknown"):
            return
        # Skip our own dispatches: integration service calls have parent_id but no user_id.
        # Physical switch presses and HA UI/app changes should trigger the lock.
        if new_state.context.user_id is None and new_state.context.parent_id is not None:
            return
        self._fan_locked = True
        _LOGGER.debug(f"Zone {self.zone_name}: fan locked by user")
        if self.last_decision is not None:
            self.async_set_updated_data(self.last_decision)

    @callback
    def _midnight_reset(self, now) -> None:
        """Release fan lock at midnight so integration resumes normal control."""
        if self._fan_locked:
            _LOGGER.info(f"Zone {self.zone_name}: midnight reset — releasing fan lock")
            self._fan_locked = False
            if self.last_decision is not None:
                self.async_set_updated_data(self.last_decision)
            self.hass.async_create_task(self.async_request_refresh())

    def _read_auto_control_enabled(self) -> bool:
        """Check if zone auto-control switch is on."""
        auto_entity = f"switch.adaptive_hvac_{self.zone_slug}_auto"
        state = self.hass.states.get(auto_entity)
        if state:
            return state.state == "on"
        return self.zone_config.get("auto_control_enabled", DEFAULT_AUTO_CONTROL_ENABLED)

    def _map_fan_commands(self, fan_commands: dict[str, int | None]) -> dict[str, int | None]:
        """Map zone_name-keyed commands to actual fan entity IDs."""
        fans = self.zone_config.get("fans", [])
        if not fans or self.zone_name not in fan_commands:
            return {}
        speed = fan_commands[self.zone_name]
        if speed is None:
            return {}
        if self._fan_locked and speed > 0:
            return {}
        return {fan_entity: speed for fan_entity in fans}

    def _calculate_trend(self) -> float:
        """Calculate temperature trend in °F/hr over 30-min window (linear regression)."""
        samples = list(self._temp_samples)
        n = len(samples)
        if n < 2:
            return 0.0

        x_mean = (n - 1) / 2.0
        y_mean = sum(samples) / n

        numerator = sum((i - x_mean) * (samples[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return (numerator / denominator) * (60 / SCAN_INTERVAL_MINUTES)  # slope per-sample → per-hour

    async def _async_update_data(self) -> ZoneDecision:
        """Fetch zone state and compute zone decision."""
        temp = self._read_temp()
        if 0 < temp < 200:  # only store valid readings; failsafe values corrupt the trend
            self._temp_samples.append(temp)

        zone = ZoneState(
            zone_name=self.zone_name,
            floor=self.zone_config.get("floor", ""),
            temp=temp,
            temp_trend=self._calculate_trend(),
            humidity=self._read_humidity(),
            fan_locked=self._fan_locked,
            window_open=self._read_window_open(),
            zone_occupied=self._read_occupancy(),
            affects_thermostat=bool(self.zone_config.get("affects_thermostat", DEFAULT_AFFECTS_THERMOSTAT)),
            current_mode=self.last_decision.mode if self.last_decision else "idle",
            zone_target_temp=self.runtime_target_temp,
        )

        cfg = ZoneConfig(
            zone_target_temp=self.runtime_target_temp,
            fan_speed=int(self.zone_config.get("fan_speed", DEFAULT_FAN_SPEED)),
            emergency_cool_threshold=float(self.zone_config.get("emergency_cool_threshold", DEFAULT_EMERGENCY_COOL_THRESHOLD)),
        )

        # Minimal system state for zone-level decisions (system coordinator fills in full state)
        sys_state = SystemState(
            zone_states=[zone],
            outdoor_temp=70.0,
            season=SEASON_SUMMER,
        )
        sys_cfg = SystemConfig()

        decision = decide_zone(zone, sys_state, cfg, sys_cfg)

        auto_control = self._read_auto_control_enabled()
        if auto_control:
            decision.fan_commands = self._map_fan_commands(decision.fan_commands)
        else:
            decision.fan_commands = {}

        self.last_decision = decision
        _LOGGER.debug(f"Zone {self.zone_name}: {decision.mode} — {decision.status}")
        return decision


class SystemCoordinator(DataUpdateCoordinator):
    """Coordinator that aggregates all zones and controls the thermostat."""

    def __init__(
        self,
        hass: HomeAssistant,
        system_config: dict,
        zone_coordinators: list[ZoneCoordinator],
        config_entry: Optional[ConfigEntry] = None,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="Adaptive HVAC - System",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
            config_entry=config_entry,
        )
        self.system_config = dict(system_config)
        self.zone_coordinators = zone_coordinators
        self.last_decision: Optional[SystemDecision] = None
        self._config_entry = config_entry
        self._last_integration_setpoint: Optional[float] = None
        self._last_season: Optional[str] = None
        self._suppress_setpoint_reload: bool = False
        self._failsafe_cycle_count: int = 0
        self._degraded_mode: bool = False
        self._night_mode_manual: bool = False
        self.night_mode_active: bool = False

    def determine_calendar_season(self) -> str:
        """Determine season — respects manual override, otherwise calendar-based."""
        override = self.system_config.get("season_override", "auto")
        if override in (SEASON_SUMMER, SEASON_WINTER):
            return override

        month = dt_util.now().month
        winter_start = int(self.system_config.get("winter_start_month", DEFAULT_WINTER_START_MONTH))
        winter_end = int(self.system_config.get("winter_end_month", DEFAULT_WINTER_END_MONTH))

        # Winter spans the year boundary (e.g., Oct=10 → Apr=4)
        if winter_start > winter_end:
            in_winter = month >= winter_start or month <= winter_end
        else:
            in_winter = winter_start <= month <= winter_end

        return SEASON_WINTER if in_winter else SEASON_SUMMER

    @callback
    def handle_thermostat_state_change(self, event) -> None:
        """Adopt thermostat setpoint changes made by the user (HA UI or app only)."""
        new_state = event.data.get("new_state")
        if not new_state:
            return
        # Only adopt changes triggered by a logged-in HA user (UI or app).
        # Thermostat-internal schedule changes and device boot-up events have user_id=None
        # and would otherwise overwrite the user's configured setpoint.
        if new_state.context.user_id is None:
            return

        new_setpoint = new_state.attributes.get("temperature")
        if new_setpoint is None:
            return

        try:
            new_setpoint = float(new_setpoint)
        except (ValueError, TypeError):
            return

        # Ignore our own dispatches (within 0.5°F tolerance)
        if self._last_integration_setpoint is not None:
            if abs(new_setpoint - self._last_integration_setpoint) < 0.5:
                return

        season = self.determine_calendar_season()
        key = "ac_setpoint" if season == SEASON_SUMMER else "heat_setpoint"

        _LOGGER.info(
            f"User adjusted thermostat to {new_setpoint}°F — adopting as {season} {key}"
        )
        self.system_config[key] = new_setpoint

        # Persist via the HA options API so config_entry.options is updated in-memory
        # immediately (not just on next restart). We suppress the resulting update_listener
        # reload — a setpoint adoption doesn't require tearing down and rebuilding entities.
        if self._config_entry:
            new_options = {**self._config_entry.options, key: new_setpoint}
            self._suppress_setpoint_reload = True
            self.hass.config_entries.async_update_entry(self._config_entry, options=new_options)
            _LOGGER.debug(f"Persisted {key}={new_setpoint} to config entry options")

    def _read_outdoor_temp(self) -> float:
        """Read outdoor temperature — local sensor takes priority over weather entity."""
        # Local sensor: state.state is the temperature value directly
        sensor_entity = self.system_config.get("outdoor_temp_sensor")
        if sensor_entity:
            state = self.hass.states.get(sensor_entity)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    return float(state.state)
                except (ValueError, TypeError):
                    pass

        # Fall back to weather entity attribute
        weather_entity = self.system_config.get("weather_entity")
        if not weather_entity:
            return 70.0

        state = self.hass.states.get(weather_entity)
        if not state:
            return 70.0

        try:
            return float(state.attributes.get("temperature", 70.0))
        except (ValueError, TypeError):
            return 70.0

    def _read_windows_openable(self) -> bool:
        """Return False if rain or high wind makes opening windows impractical."""
        weather_entity = self.system_config.get("weather_entity")
        if not weather_entity:
            return True
        state = self.hass.states.get(weather_entity)
        if not state:
            return True
        rainy_conditions = {"rainy", "pouring", "lightning-rainy", "hail", "snowy-rainy"}
        rainy = state.state in rainy_conditions
        try:
            wind = float(state.attributes.get("wind_speed", 0) or 0)
        except (ValueError, TypeError):
            wind = 0.0
        return not rainy and wind < 20

    def _read_sleep_posture(self) -> bool:
        """Read sleep posture flag (retained for diagnostics/future use)."""
        entity = self.system_config.get("sleep_posture_entity")
        if not entity:
            return False
        state = self.hass.states.get(entity)
        return bool(state and state.state == "on")

    def _read_house_occupancy(self) -> bool:
        """True if any occupancy entity is on."""
        entities = self.system_config.get("occupancy_entities", [])
        if not entities:
            return True
        return any(self.hass.states.is_state(e, "on") for e in entities)

    @property
    def night_mode_manual(self) -> bool:
        return self._night_mode_manual

    def set_night_mode_manual(self, enabled: bool) -> None:
        """Manually toggle night mode via switch.adaptive_hvac_night_mode."""
        self._night_mode_manual = enabled
        if self.last_decision is not None:
            self.async_set_updated_data(self.last_decision)
        self.hass.async_create_task(self.async_refresh())

    def _is_night_mode_active(self) -> bool:
        """Night mode is active if manually toggled on, a configured source entity is on,
        or the current hour falls within the configured night time window."""
        if self._night_mode_manual:
            return True

        source_entity = self.system_config.get("night_mode_source_entity")
        if source_entity and self.hass.states.is_state(source_entity, "on"):
            return True

        start = int(self.system_config.get("night_start_hour", DEFAULT_NIGHT_START_HOUR))
        end = int(self.system_config.get("night_end_hour", DEFAULT_NIGHT_END_HOUR))
        hour = dt_util.now().hour
        if start > end:
            return hour >= start or hour < end
        return start <= hour < end

    def _effective_setpoint(self, key: str, default: float) -> float:
        """Read setpoint: options override > system_config > const default."""
        if self._config_entry:
            val = self._config_entry.options.get(key)
            if val is not None:
                return float(val)
        return float(self.system_config.get(key, default))

    def _reset_setpoints_for_season_change(self, new_season: str) -> None:
        """On season transition, remove user-set override so base config takes effect."""
        if not self._config_entry:
            return

        keys_to_reset = ["ac_setpoint"] if new_season == SEASON_SUMMER else ["heat_setpoint"]
        new_options = {k: v for k, v in self._config_entry.options.items() if k not in keys_to_reset}

        if new_options != self._config_entry.options:
            _LOGGER.info(f"Season changed to {new_season} — resetting {keys_to_reset} to config defaults")
            self.hass.config_entries.async_update_entry(self._config_entry, options=new_options)
            # Also update in-memory value
            for key in keys_to_reset:
                base = self._config_entry.data.get(key, DEFAULT_AC_SETPOINT if key == "ac_setpoint" else DEFAULT_HEAT_SETPOINT)
                self.system_config[key] = base

    async def _async_update_data(self) -> SystemDecision:
        """Aggregate zone decisions and produce system thermostat command."""
        # Dynamically discover zone coordinators
        active_zone_coordinators = [
            self.hass.data[DOMAIN][entry.entry_id]
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data.get("entry_type") == ENTRY_TYPE_ZONE
            and self.hass.data.get(DOMAIN, {}).get(entry.entry_id) is not None
        ]
        self.zone_coordinators = active_zone_coordinators
        _LOGGER.debug(f"System update: {len(self.zone_coordinators)} zone(s)")

        # Refresh all zones
        zone_decisions: list[ZoneDecision] = []
        for coord in self.zone_coordinators:
            try:
                await coord.async_request_refresh()
                if coord.last_decision:
                    zone_decisions.append(coord.last_decision)
            except Exception as e:
                _LOGGER.error(f"Error refreshing zone {coord.zone_name}: {e}", exc_info=True)

        if not zone_decisions:
            decision = SystemDecision(thermostat_hvac_mode="off", status="No zone data available")
            self.last_decision = decision
            return decision

        # Sensor health check: collect unavailable/missing sensors across all zones
        stale_by_zone: dict[str, list[str]] = {}
        for coord in self.zone_coordinators:
            stale = coord.stale_sensors()
            if stale:
                stale_by_zone[coord.zone_name] = stale

        # Degraded-mode detection: all zones in sensor failsafe OR stale sensors found
        all_failsafe = all(d.mode == "sensor_failsafe" for d in zone_decisions)
        system_degraded = all_failsafe or bool(stale_by_zone)

        if system_degraded:
            self._failsafe_cycle_count += 1
            if self._failsafe_cycle_count >= 2 and not self._degraded_mode:
                self._degraded_mode = True
                _LOGGER.warning("Adaptive HVAC: sensor degradation detected — handing thermostat back to auto")
                thermostat = self.system_config.get("thermostat_entity")
                if thermostat:
                    try:
                        await self.hass.services.async_call(
                            "climate", "set_hvac_mode",
                            {"entity_id": thermostat, "hvac_mode": "auto"},
                        )
                    except Exception:
                        _LOGGER.warning("Adaptive HVAC: thermostat does not support 'auto' mode — leaving as-is")

                if stale_by_zone:
                    stale_lines = "\n".join(
                        f"- **{zone}**: {', '.join(sensors)}"
                        for zone, sensors in stale_by_zone.items()
                    )
                    msg = (
                        f"Stale or unavailable sensors detected:\n{stale_lines}\n\n"
                        "The thermostat has been returned to auto mode. "
                        "Adaptive HVAC will resume automatically when sensors recover."
                    )
                else:
                    msg = (
                        "All zone sensors have been unavailable for 2+ evaluation cycles. "
                        "The thermostat has been returned to auto mode and will govern itself. "
                        "Adaptive HVAC will resume automatically when sensors recover."
                    )

                await self.hass.services.async_call(
                    "persistent_notification", "create", {
                        "title": "Adaptive HVAC — Degraded",
                        "message": msg,
                        "notification_id": "adaptive_hvac_degraded",
                    }
                )

            if all_failsafe:
                reason = f"All zone sensors unavailable for {self._failsafe_cycle_count} cycle(s) — thermostat in auto"
            else:
                stale_summary = "; ".join(
                    f"{z}: {', '.join(s)}" for z, s in stale_by_zone.items()
                )
                reason = f"Stale sensors ({self._failsafe_cycle_count} cycle(s)): {stale_summary}"

            decision = SystemDecision(
                thermostat_hvac_mode="off",
                status=f"SYSTEM: DEGRADED ({self._failsafe_cycle_count} cycles)",
                reasoning=[reason],
            )
            self.last_decision = decision
            return decision
        else:
            if self._degraded_mode:
                _LOGGER.info("Adaptive HVAC: sensors recovered — resuming normal control")
                self._degraded_mode = False
                await self.hass.services.async_call(
                    "persistent_notification", "dismiss",
                    {"notification_id": "adaptive_hvac_degraded"},
                )
            self._failsafe_cycle_count = 0

        # Detect season and handle season transitions
        current_season = self.determine_calendar_season()
        if self._last_season and self._last_season != current_season:
            self._reset_setpoints_for_season_change(current_season)
        self._last_season = current_season

        # Read system inputs
        outdoor_temp = self._read_outdoor_temp()
        windows_openable = self._read_windows_openable()
        manual_override = self.system_config.get("manual_override", False)
        system_active = self.system_config.get("system_active", True)

        # Build zone states for system decision
        zone_states = []
        for coord in self.zone_coordinators:
            zone_states.append(ZoneState(
                zone_name=coord.zone_name,
                floor=coord.zone_config.get("floor", ""),
                temp=coord._read_temp(),
                temp_trend=coord._calculate_trend(),
                fan_locked=coord._fan_locked,
                window_open=coord._read_window_open(),
                zone_occupied=coord._read_occupancy(),
                affects_thermostat=bool(coord.zone_config.get("affects_thermostat", DEFAULT_AFFECTS_THERMOSTAT)),
                zone_target_temp=coord.runtime_target_temp,
            ))

        sys_state = SystemState(
            zone_states=zone_states,
            outdoor_temp=outdoor_temp,
            season=current_season,
            sleep_posture=self._read_sleep_posture(),
            house_occupied=self._read_house_occupancy(),
            manual_override=manual_override,
            system_active=system_active,
            windows_openable=windows_openable,
        )

        self.night_mode_active = self._is_night_mode_active()
        if self.night_mode_active:
            ac_setpoint = self._effective_setpoint("night_ac_setpoint", DEFAULT_NIGHT_AC_SETPOINT)
            heat_setpoint = self._effective_setpoint("night_heat_setpoint", DEFAULT_NIGHT_HEAT_SETPOINT)
        else:
            ac_setpoint = self._effective_setpoint("ac_setpoint", DEFAULT_AC_SETPOINT)
            heat_setpoint = self._effective_setpoint("heat_setpoint", DEFAULT_HEAT_SETPOINT)

        cfg = SystemConfig(
            ac_setpoint=ac_setpoint,
            heat_setpoint=heat_setpoint,
            heat_threshold=float(self.system_config.get("heat_threshold", DEFAULT_HEAT_THRESHOLD)),
            emergency_heat_threshold=float(self.system_config.get("emergency_heat_threshold", DEFAULT_EMERGENCY_HEAT_THRESHOLD)),
            cool_exterior_threshold=float(self.system_config.get("cool_exterior_threshold", DEFAULT_COOL_EXTERIOR_THRESHOLD)),
            cool_interior_override_delta=float(self.system_config.get("cool_interior_override_delta", DEFAULT_COOL_INTERIOR_OVERRIDE_DELTA)),
            heat_exterior_threshold=float(self.system_config.get("heat_exterior_threshold", DEFAULT_HEAT_EXTERIOR_THRESHOLD)),
            upstairs_demand_boost=self._effective_setpoint("upstairs_demand_boost", DEFAULT_UPSTAIRS_DEMAND_BOOST),
            fan_circulation_delta=self._effective_setpoint("fan_circulation_delta", DEFAULT_FAN_CIRCULATION_DELTA),
        )

        decision = decide_system(sys_state, zone_decisions, cfg)
        if self.night_mode_active:
            decision.reasoning.insert(1, f"Night mode active — using night setpoints (AC {ac_setpoint:.0f}°F / Heat {heat_setpoint:.0f}°F)")
        self.last_decision = decision

        # Relabel zone decisions to reflect actual system state (passive vs active)
        annotated = annotate_zone_decisions(zone_decisions, decision)
        for coord, ann_decision in zip(self.zone_coordinators, annotated):
            coord.last_decision = ann_decision
            coord.async_update_listeners()  # notify without cancelling refresh schedule

        await self._dispatch_thermostat(decision, cfg)
        await self._dispatch_fans(annotated)

        _LOGGER.info(f"System: {decision.thermostat_hvac_mode} {decision.thermostat_setpoint or 'OFF'} — {decision.status}")
        return decision

    async def _dispatch_thermostat(self, decision: SystemDecision, cfg: SystemConfig) -> None:
        """Send thermostat commands."""
        thermostat = self.system_config.get("thermostat_entity")
        if not thermostat:
            return

        mode = decision.thermostat_hvac_mode
        setpoint = decision.thermostat_setpoint

        if mode == "off":
            await self.hass.services.async_call(
                "climate", "set_hvac_mode",
                {"entity_id": thermostat, "hvac_mode": "off"},
            )
        else:
            await self.hass.services.async_call(
                "climate", "set_hvac_mode",
                {"entity_id": thermostat, "hvac_mode": mode},
            )
            if setpoint is not None:
                self._last_integration_setpoint = setpoint
                await self.hass.services.async_call(
                    "climate", "set_temperature",
                    {"entity_id": thermostat, "temperature": setpoint},
                )

        await self.hass.services.async_call(
            "climate", "set_fan_mode",
            {"entity_id": thermostat, "fan_mode": decision.whole_house_fan_mode},
        )

    async def _dispatch_fans(self, zone_decisions: list[ZoneDecision]) -> None:
        """Send fan speed commands from zone decisions."""
        for zone_decision in zone_decisions:
            for fan_entity, speed_pct in zone_decision.fan_commands.items():
                if speed_pct is None:
                    continue
                if speed_pct == 0:
                    await self.hass.services.async_call(
                        "fan", "turn_off", {"entity_id": fan_entity},
                    )
                else:
                    await self.hass.services.async_call(
                        "fan", "turn_on",
                        {"entity_id": fan_entity, "percentage": speed_pct},
                    )
