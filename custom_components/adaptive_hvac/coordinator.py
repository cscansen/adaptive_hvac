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
    ENTRY_TYPE_ZONE,
    SCAN_INTERVAL_MINUTES,
    DEFAULT_COMFORT_UPPER,
    DEFAULT_PASSIVE_THRESHOLD,
    DEFAULT_PASSIVE_HUMID_THRESHOLD,
    DEFAULT_ESCALATE_THRESHOLD,
    DEFAULT_EMERGENCY_THRESHOLD,
    DEFAULT_COMFORT_SPEED,
    DEFAULT_PASSIVE_FAN_SPEED,
    DEFAULT_WINDOW_FAN_SPEED,
    DEFAULT_PRECOOL_FAN_SPEED,
    DEFAULT_ESCALATE_FAN_SPEED,
    DEFAULT_EMERGENCY_FAN_SPEED,
    DEFAULT_WINDOWS_SENSOR,
    DEFAULT_AC_SETPOINT,
    DEFAULT_HEAT_THRESHOLD,
    DEFAULT_HEAT_SETPOINT,
    DEFAULT_EMERGENCY_HEAT_THRESHOLD,
    DEFAULT_SETBACK_COOL_TEMP,
    DEFAULT_SETBACK_HEAT_TEMP,
    DEFAULT_UNOCCUPIED_HOURS,
    DEFAULT_RETURN_HOME_COOL_SETPOINT,
    DEFAULT_RETURN_HOME_HEAT_SETPOINT,
    DEFAULT_PRECOOL_TRIGGER,
    DEFAULT_PREHEAT_TRIGGER,
    DEFAULT_AC_TRIGGER_SOLAR_WATTS,
    DEFAULT_AC_SOLAR_WINDOW_START,
    DEFAULT_AC_SOLAR_WINDOW_END,
    DEFAULT_AC_TRIGGER_HUMIDITY,
    DEFAULT_WINDOW_FAN_SPEED,
    DEFAULT_PASSIVE_COOLING_ENABLED,
    DEFAULT_WHOLE_HOUSE_FAN_ENTITY,
    DEFAULT_SUMMER_THRESHOLD,
    DEFAULT_WINTER_THRESHOLD,
    DEFAULT_IS_PRIMARY_ZONE,
    DEFAULT_AUTO_CONTROL_ENABLED,
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

        # Log zone config for debugging
        _LOGGER.info(f"ZoneCoordinator init for {zone_name}")
        _LOGGER.info(f"  zone_config keys: {list(zone_config.keys())}")
        _LOGGER.info(f"  temp_sensors: {zone_config.get('temp_sensors')}")
        with open("/config/adaptive_hvac_coordinator.log", "a") as f:
            f.write(f"[ZoneCoordinator.__init__] {zone_name}\n")
            f.write(f"  zone_config keys: {list(zone_config.keys())}\n")
            f.write(f"  temp_sensors: {zone_config.get('temp_sensors')}\n")

    def _read_temp(self) -> float:
        """Read and average zone temperature sensors."""
        temp_entities = self.zone_config.get("temp_sensors", [])
        _LOGGER.debug(f"_read_temp for {self.zone_name}: temp_entities={temp_entities}")
        if not temp_entities:
            _LOGGER.warning(f"_read_temp {self.zone_name}: NO temp_entities configured!")
            with open("/config/adaptive_hvac_coordinator.log", "a") as f:
                f.write(f"[_read_temp] {self.zone_name}: NO temp_entities\n")
            return 0.0

        temps = []
        for entity_id in temp_entities:
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    temp_val = float(state.state)
                    temps.append(temp_val)
                    _LOGGER.debug(f"  {entity_id}={temp_val}°F")
                except ValueError as e:
                    _LOGGER.warning(f"  {entity_id}: invalid state '{state.state}': {e}")
            else:
                # Sensor not available yet - this might be a startup timing issue
                # Return None to indicate data is unavailable, not 0.0 (which triggers failsafe)
                state_info = f"state={state.state if state else 'NOT FOUND'}"
                _LOGGER.info(f"  {entity_id}: {state_info} (sensor may not be loaded yet)")
                with open("/config/adaptive_hvac_coordinator.log", "a") as f:
                    f.write(f"  {entity_id}: {state_info}\n")

        result = sum(temps) / len(temps) if temps else 0.0
        _LOGGER.debug(f"_read_temp {self.zone_name}: avg temp={result}°F from {len(temps)} sensors")
        return result

    def _read_humidity(self) -> Optional[float]:
        """Read humidity sensor(s) — average if multiple."""
        humidity_entities = self.zone_config.get("humidity_sensor", [])
        if not humidity_entities:
            return None

        # Handle both single entity (string) and multiple (list) for backwards compatibility
        if isinstance(humidity_entities, str):
            humidity_entities = [humidity_entities]

        humidity_values = []
        for entity in humidity_entities:
            state = self.hass.states.get(entity)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    humidity_values.append(float(state.state))
                except ValueError:
                    pass

        return sum(humidity_values) / len(humidity_values) if humidity_values else None

    def _read_window_open(self) -> bool:
        """Check if zone window(s) are open — True if ANY window is open."""
        window_entities = self.zone_config.get("window_sensor", [])
        if not window_entities:
            return False

        # Handle both single entity (string) and multiple (list) for backwards compatibility
        if isinstance(window_entities, str):
            window_entities = [window_entities]

        for entity in window_entities:
            state = self.hass.states.get(entity)
            if state and state.state == "on":
                return True
        return False

    def _read_occupancy(self) -> bool:
        """Check if zone is occupied — True if ANY occupancy sensor is occupied."""
        occupancy_entities = self.zone_config.get("occupancy_sensor", [])
        if not occupancy_entities:
            return True  # Default to occupied if not specified

        # Handle both single entity (string) and multiple (list) for backwards compatibility
        if isinstance(occupancy_entities, str):
            occupancy_entities = [occupancy_entities]

        for entity in occupancy_entities:
            state = self.hass.states.get(entity)
            if state and state.state == "on":
                return True
        return False

    def _read_fan_claims(self) -> set[str]:
        """Get set of claimed fan entity IDs (from per-fan lock entities in fan_config)."""
        claimed = set()
        fan_config = self.zone_config.get("fan_config", [])
        for fan_entry in fan_config:
            lock_entity = fan_entry.get("fan_lock_entity")
            if lock_entity:
                state = self.hass.states.get(lock_entity)
                if state and state.state == "on":
                    claimed.add(fan_entry.get("fan_id"))
        return claimed

    def _read_auto_control_enabled(self) -> bool:
        """Check if zone auto-control switch is on."""
        auto_control_entity = f"switch.adaptive_hvac_{self.zone_name.lower().replace(' ', '_')}_auto"
        state = self.hass.states.get(auto_control_entity)
        if state:
            return state.state == "on"
        return self.zone_config.get("auto_control_enabled", DEFAULT_AUTO_CONTROL_ENABLED)

    def _read_windows_assumed_open(self) -> bool:
        """Read global windows open sensor."""
        windows_entity = DEFAULT_WINDOWS_SENSOR
        if not windows_entity:
            return False

        state = self.hass.states.get(windows_entity)
        return state and state.state == "on" if state else False

    def _map_fan_commands(self, fan_commands: dict[str, int | None]) -> dict[str, int | None]:
        """Map placeholder fan commands to real entity IDs from fan_config."""
        mapped = {}
        fan_config = self.zone_config.get("fan_config", [])
        fans_claimed = self._read_fan_claims()

        for fan_entry in fan_config:
            fan_id = fan_entry.get("fan_id")
            fan_entity = fan_entry.get("fan_entity")

            # Skip if fan is claimed by user or entity not defined
            if not fan_entity or fan_id in fans_claimed:
                continue

            # Get speed from the placeholder command
            if fan_id in fan_commands:
                speed = fan_commands[fan_id]
                # Only add if speed is not None (None = skip this mode for this fan)
                if speed is not None:
                    mapped[fan_entity] = speed

        return mapped

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
        windows_assumed_open = self._read_windows_assumed_open()
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
            is_primary_zone=self.zone_config.get("is_primary_zone", DEFAULT_IS_PRIMARY_ZONE),
            windows_assumed_open=windows_assumed_open,
        )

        # Track mode age
        if self.last_decision and self.last_decision.mode != zone.current_mode:
            self._mode_entered_at = datetime.now()
        elif not self._mode_entered_at:
            self._mode_entered_at = datetime.now()

        zone.mode_age_min = (datetime.now() - self._mode_entered_at).total_seconds() / 60

        # Build zone config (cooling thresholds + per-mode fan speeds only; heating is global)
        cfg = ZoneConfig(
            comfort_upper=self.zone_config.get("comfort_upper", DEFAULT_COMFORT_UPPER),
            passive_threshold=self.zone_config.get("passive_threshold", DEFAULT_PASSIVE_THRESHOLD),
            passive_humid_threshold=self.zone_config.get("passive_humid_threshold", DEFAULT_PASSIVE_HUMID_THRESHOLD),
            escalate_threshold=self.zone_config.get("escalate_threshold", DEFAULT_ESCALATE_THRESHOLD),
            emergency_threshold=self.zone_config.get("emergency_threshold", DEFAULT_EMERGENCY_THRESHOLD),
            comfort_speed=self.zone_config.get("comfort_speed", DEFAULT_COMFORT_SPEED),
            passive_fan_speed=self.zone_config.get("passive_fan_speed", DEFAULT_PASSIVE_FAN_SPEED),
            window_fan_speed=self.zone_config.get("window_fan_speed", DEFAULT_WINDOW_FAN_SPEED),
            precool_fan_speed=self.zone_config.get("precool_fan_speed", DEFAULT_PRECOOL_FAN_SPEED),
            escalate_fan_speed=self.zone_config.get("escalate_fan_speed", DEFAULT_ESCALATE_FAN_SPEED),
            emergency_fan_speed=self.zone_config.get("emergency_fan_speed", DEFAULT_EMERGENCY_FAN_SPEED),
            ac_setpoint=self.zone_config.get("ac_setpoint", DEFAULT_AC_SETPOINT),
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

        # Check if auto-control is enabled for this zone
        auto_control_enabled = self._read_auto_control_enabled()

        # Decide
        decision = decide_zone(zone, [zone], sys_state, cfg, sys_cfg)

        # Map placeholder fan commands to real entity IDs from fan_config
        if auto_control_enabled:
            decision.fan_commands = self._map_fan_commands(decision.fan_commands)
        else:
            # If auto-control is disabled, suppress fan commands but keep mode/status for diagnostics
            decision.fan_commands = {}

        self.last_decision = decision

        _LOGGER.debug(
            f"Zone {self.zone_name} decision: {decision.mode} - {decision.status}"
            f" (auto_control={'on' if auto_control_enabled else 'off'})"
        )

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

    def _read_windows_assumed_open(self) -> bool:
        """Read global windows open sensor."""
        windows_entity = self.system_config.get("windows_assumed_open_sensor", DEFAULT_WINDOWS_SENSOR)
        if not windows_entity:
            return False

        state = self.hass.states.get(windows_entity)
        return state and state.state == "on" if state else False

    async def _async_update_data(self) -> SystemDecision:
        """Fetch zone decisions and compute system decision."""
        # Dynamically discover zone coordinators (in case new zones were added since startup)
        active_zones = [
            self.hass.data.get(DOMAIN, {}).get(entry.entry_id)
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data.get("entry_type") == ENTRY_TYPE_ZONE
            and self.hass.data.get(DOMAIN, {}).get(entry.entry_id) is not None
        ]
        self.zone_coordinators = [z for z in active_zones if z is not None]
        _LOGGER.info(f"System coordinator update: found {len(self.zone_coordinators)} active zone(s)")
        with open("/config/adaptive_hvac_coordinator.log", "a") as f:
            f.write(f"[SystemCoordinator._async_update_data] {len(self.zone_coordinators)} zones\n")
            for z in self.zone_coordinators:
                f.write(f"  - {z.zone_name}\n")

        # Get all zone decisions (trigger zone coordinators)
        zone_decisions = []
        for coord in self.zone_coordinators:
            try:
                decision = await coord.async_request_refresh()
                if decision:
                    zone_decisions.append(coord.last_decision)
            except Exception as e:
                _LOGGER.error(f"Error updating zone {coord.zone_name}: {e}")

        # If no zone decisions, return safe idle (but set last_decision)
        if not zone_decisions:
            decision = SystemDecision(
                thermostat_hvac_mode="off",
                thermostat_setpoint=None,
                status="No zone data available",
            )
            self.last_decision = decision
            _LOGGER.info("System coordinator: no zone data available")
            return decision

        # Read system inputs
        outdoor_temp, forecast_high, forecast_low, forecast_high_7day = self._read_weather()
        forecast_low_7day = forecast_low  # Simplified
        solar_w = self._read_solar()
        sleep_posture = self._read_sleep_posture()
        house_occupied, unoccupied_hours = self._read_house_occupancy()
        windows_assumed_open = self._read_windows_assumed_open()

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

        # Build zone states for system decision (with occupancy for active zone calc)
        zone_states = []
        for coord, decision in zip(self.zone_coordinators, zone_decisions):
            zone_state = ZoneState(
                zone_name=coord.zone_name,
                floor=coord.zone_config.get("floor", ""),
                temp=coord._read_temp(),
                temp_trend=coord._calculate_trend(),
                humidity=coord._read_humidity(),
                fans_claimed=coord._read_fan_claims(),
                window_open=coord._read_window_open(),
                zone_occupied=coord._read_occupancy(),
                current_mode=decision.mode,
                is_primary_zone=decision.is_primary_zone,
                windows_assumed_open=windows_assumed_open,
                mode_age_min=0,
            )
            zone_states.append(zone_state)

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
            windows_assumed_open=windows_assumed_open,
        )

        cfg = SystemConfig(
            summer_threshold=self.system_config.get("summer_threshold", DEFAULT_SUMMER_THRESHOLD),
            winter_threshold=self.system_config.get("winter_threshold", DEFAULT_WINTER_THRESHOLD),
            ac_enabled=self.system_config.get("ac_enabled", True),
            ac_setpoint=self.system_config.get("ac_setpoint", DEFAULT_AC_SETPOINT),
            ac_trigger_solar_watts=self.system_config.get("ac_trigger_solar_watts", DEFAULT_AC_TRIGGER_SOLAR_WATTS),
            ac_solar_window_start=self.system_config.get("ac_solar_window_start", DEFAULT_AC_SOLAR_WINDOW_START),
            ac_solar_window_end=self.system_config.get("ac_solar_window_end", DEFAULT_AC_SOLAR_WINDOW_END),
            ac_trigger_humidity=self.system_config.get("ac_trigger_humidity", DEFAULT_AC_TRIGGER_HUMIDITY),
            heat_threshold=self.system_config.get("heat_threshold", DEFAULT_HEAT_THRESHOLD),
            heat_setpoint=self.system_config.get("heat_setpoint", DEFAULT_HEAT_SETPOINT),
            emergency_heat_threshold=self.system_config.get("emergency_heat_threshold", DEFAULT_EMERGENCY_HEAT_THRESHOLD),
            setback_cool_temp=self.system_config.get("setback_cool_temp", DEFAULT_SETBACK_COOL_TEMP),
            setback_heat_temp=self.system_config.get("setback_heat_temp", DEFAULT_SETBACK_HEAT_TEMP),
            unoccupied_hours=self.system_config.get("unoccupied_hours", DEFAULT_UNOCCUPIED_HOURS),
            return_home_cool_setpoint=self.system_config.get("return_home_cool_setpoint", DEFAULT_RETURN_HOME_COOL_SETPOINT),
            return_home_heat_setpoint=self.system_config.get("return_home_heat_setpoint", DEFAULT_RETURN_HOME_HEAT_SETPOINT),
            precool_trigger=self.system_config.get("precool_trigger", DEFAULT_PRECOOL_TRIGGER),
            preheat_trigger=self.system_config.get("preheat_trigger", DEFAULT_PREHEAT_TRIGGER),
            window_fan_speed=self.system_config.get("window_fan_speed", DEFAULT_WINDOW_FAN_SPEED),
            passive_cooling_enabled=self.system_config.get("passive_cooling_enabled", DEFAULT_PASSIVE_COOLING_ENABLED),
            passive_fan_threshold=self.system_config.get("passive_fan_threshold", 70.0),
            escalate_enabled_downstairs_temp=self.system_config.get("escalate_enabled_downstairs_temp", 68.0),
            escalate_enabled_upstairs_temp=self.system_config.get("escalate_enabled_upstairs_temp", 74.0),
        )

        # Decide
        decision = decide_system(sys_state, zone_decisions, cfg)
        self.last_decision = decision

        # Dispatch thermostat commands
        await self._dispatch_thermostat(decision)
        await self._dispatch_fans(decision, zone_decisions)

        _LOGGER.debug(f"System decision: {decision.thermostat_hvac_mode} {decision.thermostat_setpoint}°F - {decision.status}")

        return decision

    def _check_any_window_open(self) -> bool:
        """Check if any window is open (system-wide + per-zone)."""
        # Check system windows sensor
        windows_entity = self.system_config.get("windows_assumed_open_sensor", DEFAULT_WINDOWS_SENSOR)
        state = self.hass.states.get(windows_entity)
        if state and state.state == "on":
            return True

        # Check per-zone window sensors
        for coord in self.zone_coordinators:
            if coord._read_window_open():
                return True

        return False

    async def _dispatch_thermostat(self, decision: SystemDecision):
        """Send thermostat commands."""
        thermostat = self.system_config.get("thermostat_entity")
        if not thermostat:
            return

        # Override: if ANY window open, no AC/heat
        any_window_open = self._check_any_window_open()
        if any_window_open:
            _LOGGER.debug("Window(s) open — blocking AC/heat, enabling whole-house fan for passive ventilation")
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {"entity_id": thermostat, "hvac_mode": "off"},
            )
            await self.hass.services.async_call(
                "climate",
                "set_fan_mode",
                {"entity_id": thermostat, "fan_mode": "on"},
            )
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
