"""Data coordinators for Adaptive HVAC zones and system."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from collections import deque

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SCAN_INTERVAL_MINUTES,
    DEFAULT_COMFORT_UPPER,
    DEFAULT_PASSIVE_THRESHOLD,
    DEFAULT_ESCALATE_THRESHOLD,
    DEFAULT_EMERGENCY_THRESHOLD,
    DEFAULT_PASSIVE_FAN_SPEED,
    DEFAULT_ESCALATE_FAN_SPEED,
    DEFAULT_AC_SETPOINT,
    DEFAULT_HEAT_THRESHOLD,
    DEFAULT_HEAT_SETPOINT,
    DEFAULT_EMERGENCY_HEAT_THRESHOLD,
    DEFAULT_SETBACK_COOL_TEMP,
    DEFAULT_SETBACK_HEAT_TEMP,
    DEFAULT_NIGHT_SETBACK_TEMP,
    DEFAULT_UNOCCUPIED_HOURS,
    DEFAULT_PRECOOL_TRIGGER,
    DEFAULT_PREHEAT_TRIGGER,
    DEFAULT_SUMMER_THRESHOLD,
    DEFAULT_WINTER_THRESHOLD,
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
)
from .season import SeasonState, derive_season

_LOGGER = logging.getLogger(__name__)

TREND_WINDOW_MIN = 30  # Calculate trend over last 30 minutes


class ZoneCoordinator(DataUpdateCoordinator):
    """Coordinator for a single HVAC zone."""

    def __init__(
        self,
        hass: HomeAssistant,
        zone_name: str,
        zone_config: dict,
    ):
        """Initialize zone coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Adaptive HVAC - {zone_name}",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self.zone_name = zone_name
        self.zone_config = zone_config
        self._temp_samples = deque(maxlen=30)  # 30 min of 1-sample/min
        self.last_decision: Optional[ZoneDecision] = None
        self._mode_entered_at: Optional[datetime] = None

    def _read_temp(self) -> float:
        """Read and average zone temperature sensors."""
        temp_entities = self.zone_config.get("temp_sensors", [])
        if not temp_entities:
            return 0.0

        temps = []
        for entity_id in temp_entities:
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    temps.append(float(state.state))
                except ValueError:
                    pass

        return sum(temps) / len(temps) if temps else 0.0

    def _read_humidity(self) -> Optional[float]:
        """Read humidity sensor."""
        humidity_entity = self.zone_config.get("humidity_sensor")
        if not humidity_entity:
            return None

        state = self.hass.states.get(humidity_entity)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                return float(state.state)
            except ValueError:
                pass
        return None

    def _read_window_open(self) -> bool:
        """Check if zone window is open."""
        window_entity = self.zone_config.get("window_sensor")
        if not window_entity:
            return False

        state = self.hass.states.get(window_entity)
        return state and state.state == "on" if state else False

    def _read_occupancy(self) -> bool:
        """Check if zone is occupied."""
        occupancy_entity = self.zone_config.get("zone_occupancy_sensor")
        if not occupancy_entity:
            return True  # Default to occupied if not specified

        state = self.hass.states.get(occupancy_entity)
        return state and state.state == "on" if state else True

    def _read_fan_claims(self) -> set[str]:
        """Get set of claimed fan entity IDs."""
        claimed = set()
        fan_locks = self.zone_config.get("fan_lock_entities", [])
        for lock_entity in fan_locks:
            state = self.hass.states.get(lock_entity)
            if state and state.state == "on":
                claimed.add(lock_entity)
        return claimed

    def _calculate_trend(self) -> float:
        """
        Calculate temperature trend in °F/hr over 30-min window.

        Uses simple linear regression if enough samples.
        """
        if len(self._temp_samples) < 2:
            return 0.0

        samples = list(self._temp_samples)
        n = len(samples)

        # Simple linear regression
        x = list(range(n))
        y = samples

        x_mean = sum(x) / n
        y_mean = sum(y) / n

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        slope_per_min = numerator / denominator
        slope_per_hour = slope_per_min * 60

        return slope_per_hour

    async def _async_update_data(self) -> ZoneDecision:
        """Fetch and compute zone decision."""
        temp = self._read_temp()
        self._temp_samples.append(temp)

        humidity = self._read_humidity()
        window_open = self._read_window_open()
        zone_occupied = self._read_occupancy()
        fans_claimed = self._read_fan_claims()
        trend = self._calculate_trend()

        # Build zone state
        zone = ZoneState(
            zone_name=self.zone_name,
            floor=self.zone_config.get("floor", ""),
            temp=temp,
            temp_trend=trend,
            humidity=humidity,
            fans_claimed=fans_claimed,
            window_open=window_open,
            zone_occupied=zone_occupied,
            current_mode=self.last_decision.mode if self.last_decision else "idle",
        )

        # Track mode age
        if self.last_decision and self.last_decision.mode != zone.current_mode:
            self._mode_entered_at = datetime.now()
        elif not self._mode_entered_at:
            self._mode_entered_at = datetime.now()

        zone.mode_age_min = (datetime.now() - self._mode_entered_at).total_seconds() / 60

        # Build config
        cfg = ZoneConfig(
            comfort_upper=self.zone_config.get("comfort_upper", DEFAULT_COMFORT_UPPER),
            passive_threshold=self.zone_config.get("passive_threshold", DEFAULT_PASSIVE_THRESHOLD),
            escalate_threshold=self.zone_config.get("escalate_threshold", DEFAULT_ESCALATE_THRESHOLD),
            emergency_threshold=self.zone_config.get("emergency_threshold", DEFAULT_EMERGENCY_THRESHOLD),
            passive_fan_speed=self.zone_config.get("passive_fan_speed", DEFAULT_PASSIVE_FAN_SPEED),
            escalate_fan_speed=self.zone_config.get("escalate_fan_speed", DEFAULT_ESCALATE_FAN_SPEED),
            ac_setpoint=self.zone_config.get("ac_setpoint", DEFAULT_AC_SETPOINT),
            heat_threshold=self.zone_config.get("heat_threshold", DEFAULT_HEAT_THRESHOLD),
            heat_setpoint=self.zone_config.get("heat_setpoint", DEFAULT_HEAT_SETPOINT),
            emergency_heat_threshold=self.zone_config.get("emergency_heat_threshold", DEFAULT_EMERGENCY_HEAT_THRESHOLD),
            setback_cool_temp=self.zone_config.get("setback_cool_temp", DEFAULT_SETBACK_COOL_TEMP),
            setback_heat_temp=self.zone_config.get("setback_heat_temp", DEFAULT_SETBACK_HEAT_TEMP),
            night_setback_temp=self.zone_config.get("night_setback_temp", DEFAULT_NIGHT_SETBACK_TEMP),
            unoccupied_hours=self.zone_config.get("unoccupied_hours", DEFAULT_UNOCCUPIED_HOURS),
            precool_trigger=self.zone_config.get("precool_trigger", DEFAULT_PRECOOL_TRIGGER),
            preheat_trigger=self.zone_config.get("preheat_trigger", DEFAULT_PREHEAT_TRIGGER),
        )

        # Placeholder: system state (will be filled by SystemCoordinator)
        sys_state = SystemState(
            zone_states=[zone],
            outdoor_temp=70.0,
            forecast_high=85.0,
            forecast_low=65.0,
            forecast_high_7day_avg=75.0,
            forecast_low_7day_avg=55.0,
            solar_w=1000,
        )

        sys_cfg = SystemConfig(
            summer_threshold=DEFAULT_SUMMER_THRESHOLD,
            winter_threshold=DEFAULT_WINTER_THRESHOLD,
            precool_trigger=DEFAULT_PRECOOL_TRIGGER,
            preheat_trigger=DEFAULT_PREHEAT_TRIGGER,
        )

        # Decide
        decision = decide_zone(zone, [zone], sys_state, cfg, sys_cfg)
        self.last_decision = decision

        _LOGGER.debug(f"Zone {self.zone_name} decision: {decision.mode} - {decision.status}")

        return decision


class SystemCoordinator(DataUpdateCoordinator):
    """Coordinator that aggregates all zones and controls the thermostat."""

    def __init__(
        self,
        hass: HomeAssistant,
        system_config: dict,
        zone_coordinators: list[ZoneCoordinator],
    ):
        """Initialize system coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Adaptive HVAC - System",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self.system_config = system_config
        self.zone_coordinators = zone_coordinators
        self.last_decision: Optional[SystemDecision] = None
        self._season_state = SeasonState()

    def _read_weather(self) -> tuple[float, float, float, float]:
        """Read weather entity for forecast."""
        weather_entity = self.system_config.get("weather_entity")
        if not weather_entity:
            return 70.0, 85.0, 65.0, 75.0

        state = self.hass.states.get(weather_entity)
        if not state:
            return 70.0, 85.0, 65.0, 75.0

        # Extract forecast attributes (HomeAssistant weather service)
        attrs = state.attributes
        try:
            outdoor_temp = float(attrs.get("temperature", 70.0))
            forecast_high = float(attrs.get("forecast", [{}])[0].get("temperature", 85.0))
            forecast_low = float(attrs.get("forecast", [{}])[0].get("templow", 65.0))
            # 7-day average (simplified: use today's forecast)
            forecast_high_7day = forecast_high
            forecast_low_7day = forecast_low
        except (ValueError, TypeError, IndexError):
            return 70.0, 85.0, 65.0, 75.0

        return outdoor_temp, forecast_high, forecast_low, forecast_high_7day

    def _read_solar(self) -> float:
        """Read solar production sensor."""
        solar_entity = self.system_config.get("solar_entity")
        if not solar_entity:
            return 0.0

        state = self.hass.states.get(solar_entity)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                return float(state.state)
            except ValueError:
                pass
        return 0.0

    def _read_sleep_posture(self) -> bool:
        """Read sleep posture state."""
        sleep_entity = self.system_config.get("sleep_posture_entity")
        if not sleep_entity:
            return False

        state = self.hass.states.get(sleep_entity)
        return state and state.state == "on" if state else False

    def _read_house_occupancy(self) -> tuple[bool, float]:
        """
        Read house-level occupancy.

        Returns tuple of (is_occupied, unoccupied_hours)
        """
        occupancy_entities = self.system_config.get("occupancy_entities", [])
        if not occupancy_entities:
            return True, 0.0

        occupied = any(
            self.hass.states.is_state(entity, "on")
            for entity in occupancy_entities
        )

        # Simplified: if any occupied, unoccupied_hours = 0
        # In real implementation, would track last occupancy timestamp
        return occupied, 0.0 if occupied else 8.0

    async def _async_update_data(self) -> SystemDecision:
        """Fetch zone decisions and compute system decision."""
        # Get all zone decisions (trigger zone coordinators)
        zone_decisions = []
        for coord in self.zone_coordinators:
            try:
                decision = await coord.async_request_refresh()
                if decision:
                    zone_decisions.append(coord.last_decision)
            except Exception as e:
                _LOGGER.error(f"Error updating zone {coord.zone_name}: {e}")

        # If no zone decisions, return safe idle
        if not zone_decisions:
            return SystemDecision(
                thermostat_hvac_mode="off",
                thermostat_setpoint=None,
                status="No zone data available",
            )

        # Read system inputs
        outdoor_temp, forecast_high, forecast_low, forecast_high_7day = self._read_weather()
        forecast_low_7day = forecast_low  # Simplified
        solar_w = self._read_solar()
        sleep_posture = self._read_sleep_posture()
        house_occupied, unoccupied_hours = self._read_house_occupancy()

        # Read configuration flags
        manual_override = self.system_config.get("manual_override", False)
        system_active = self.system_config.get("system_active", True)
        season_override = self.system_config.get("season_override", "auto")

        # Derive season from forecast
        derived_season, self._season_state = derive_season(
            forecast_high_7day,
            forecast_low_7day,
            self.system_config.get("summer_threshold", DEFAULT_SUMMER_THRESHOLD),
            self.system_config.get("winter_threshold", DEFAULT_WINTER_THRESHOLD),
            self._season_state,
        )

        # Build system state
        zone_states = [d.mode for d in zone_decisions]  # Placeholder
        sys_state = SystemState(
            zone_states=zone_states,
            outdoor_temp=outdoor_temp,
            forecast_high=forecast_high,
            forecast_low=forecast_low,
            forecast_high_7day_avg=forecast_high_7day,
            forecast_low_7day_avg=forecast_low_7day,
            solar_w=solar_w,
            sleep_posture=sleep_posture,
            house_occupied=house_occupied,
            unoccupied_hours=unoccupied_hours,
            manual_override=manual_override,
            system_active=system_active,
            hour_of_day=dt_util.now().hour,
            season=derived_season,
            season_override=season_override,
        )

        cfg = SystemConfig(
            summer_threshold=self.system_config.get("summer_threshold", DEFAULT_SUMMER_THRESHOLD),
            winter_threshold=self.system_config.get("winter_threshold", DEFAULT_WINTER_THRESHOLD),
        )

        # Decide
        decision = decide_system(sys_state, zone_decisions, cfg)
        self.last_decision = decision

        # Dispatch thermostat commands
        await self._dispatch_thermostat(decision)
        await self._dispatch_fans(decision, zone_decisions)

        _LOGGER.debug(f"System decision: {decision.thermostat_hvac_mode} {decision.thermostat_setpoint}°F - {decision.status}")

        return decision

    async def _dispatch_thermostat(self, decision: SystemDecision):
        """Send thermostat commands."""
        thermostat = self.system_config.get("thermostat_entity")
        if not thermostat:
            return

        if decision.thermostat_hvac_mode == "off":
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {"entity_id": thermostat, "hvac_mode": "off"},
            )
        else:
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {"entity_id": thermostat, "hvac_mode": decision.thermostat_hvac_mode},
            )

            if decision.thermostat_setpoint:
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {"entity_id": thermostat, "temperature": decision.thermostat_setpoint},
                )

        # Set whole-house fan mode
        await self.hass.services.async_call(
            "climate",
            "set_fan_mode",
            {"entity_id": thermostat, "fan_mode": decision.whole_house_fan_mode},
        )

    async def _dispatch_fans(self, sys_decision: SystemDecision, zone_decisions: list[ZoneDecision]):
        """Send fan commands for each zone."""
        for zone_decision in zone_decisions:
            for fan_entity, speed_pct in zone_decision.fan_commands.items():
                if speed_pct is None:
                    # Skip this fan
                    continue

                if speed_pct == 0:
                    await self.hass.services.async_call(
                        "fan",
                        "turn_off",
                        {"entity_id": fan_entity},
                    )
                else:
                    await self.hass.services.async_call(
                        "fan",
                        "turn_on",
                        {"entity_id": fan_entity, "percentage": speed_pct},
                    )
