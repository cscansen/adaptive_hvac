"""Config flow for Adaptive HVAC."""

from typing import Any, Dict, Optional
import json
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    ENTRY_TYPE_SYSTEM,
    ENTRY_TYPE_ZONE,
    # System config keys
    CONF_THERMOSTAT,
    CONF_WEATHER,
    CONF_SOLAR,
    CONF_SLEEP_POSTURE,
    CONF_OCCUPANCY,
    CONF_AC_ENABLED,
    CONF_AC_SETPOINT,
    CONF_AC_TRIGGER_SOLAR_WATTS,
    CONF_AC_SOLAR_WINDOW_START,
    CONF_AC_SOLAR_WINDOW_END,
    CONF_AC_TRIGGER_HUMIDITY,
    CONF_HEAT_THRESHOLD,
    CONF_HEAT_SETPOINT,
    CONF_EMERGENCY_HEAT_THRESHOLD,
    CONF_SETBACK_COOL_TEMP,
    CONF_SETBACK_HEAT_TEMP,
    CONF_UNOCCUPIED_HOURS,
    CONF_RETURN_HOME_COOL_SETPOINT,
    CONF_RETURN_HOME_HEAT_SETPOINT,
    CONF_PRECOOL_TRIGGER,
    CONF_PREHEAT_TRIGGER,
    CONF_WINDOWS_ASSUMED_OPEN_SENSOR,
    CONF_WINDOW_FAN_SPEED,
    CONF_PASSIVE_COOLING_ENABLED,
    CONF_WHOLE_HOUSE_FAN_ENTITY,
    CONF_FAN_POOL,
    # Zone config keys
    CONF_ZONE_NAME,
    CONF_FLOOR,
    CONF_IS_PRIMARY_ZONE,
    CONF_AUTO_CONTROL_ENABLED,
    CONF_TEMP_SENSORS,
    CONF_HUMIDITY_SENSOR,
    CONF_WINDOW_SENSOR,
    CONF_ZONE_OCCUPANCY,
    CONF_COMFORT_UPPER,
    CONF_PASSIVE_THRESHOLD,
    CONF_PASSIVE_HUMID_THRESHOLD,
    CONF_ESCALATE_THRESHOLD,
    CONF_EMERGENCY_THRESHOLD,
    CONF_FAN_CONFIG,
    # Defaults
    DEFAULT_THERMOSTAT,
    DEFAULT_WEATHER,
    DEFAULT_SOLAR,
    DEFAULT_SLEEP_POSTURE,
    DEFAULT_AC_SETPOINT,
    DEFAULT_AC_TRIGGER_SOLAR_WATTS,
    DEFAULT_AC_SOLAR_WINDOW_START,
    DEFAULT_AC_SOLAR_WINDOW_END,
    DEFAULT_AC_TRIGGER_HUMIDITY,
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
    DEFAULT_WINDOWS_SENSOR,
    DEFAULT_WINDOW_FAN_SPEED,
    DEFAULT_PASSIVE_COOLING_ENABLED,
    DEFAULT_WHOLE_HOUSE_FAN_ENTITY,
    DEFAULT_COMFORT_UPPER,
    DEFAULT_PASSIVE_THRESHOLD,
    DEFAULT_PASSIVE_HUMID_THRESHOLD,
    DEFAULT_ESCALATE_THRESHOLD,
    DEFAULT_EMERGENCY_THRESHOLD,
    DEFAULT_IS_PRIMARY_ZONE,
    DEFAULT_AUTO_CONTROL_ENABLED,
)


def _system_schema_dict(defaults: dict) -> dict:
    """Build system configuration schema."""
    return {
        # Thermostat & Sensors
        vol.Required(CONF_THERMOSTAT, default=defaults.get(CONF_THERMOSTAT, DEFAULT_THERMOSTAT)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="climate")
        ),
        vol.Required(CONF_WEATHER, default=defaults.get(CONF_WEATHER, DEFAULT_WEATHER)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="weather")
        ),
        vol.Optional(CONF_SOLAR, default=defaults.get(CONF_SOLAR, DEFAULT_SOLAR)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_SLEEP_POSTURE, default=defaults.get(CONF_SLEEP_POSTURE, DEFAULT_SLEEP_POSTURE)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="input_boolean")
        ),
        vol.Optional(CONF_OCCUPANCY, default=defaults.get(CONF_OCCUPANCY, [])): selector.EntitiesSelector(
            selector.EntitiesSelectorConfig(domain="binary_sensor")
        ),
        # AC Control
        vol.Optional(CONF_AC_ENABLED, default=defaults.get(CONF_AC_ENABLED, True)): selector.BooleanSelector(),
        vol.Optional(CONF_AC_SETPOINT, default=defaults.get(CONF_AC_SETPOINT, DEFAULT_AC_SETPOINT)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=55, max=75, unit_of_measurement="°F")
        ),
        vol.Optional(CONF_AC_TRIGGER_SOLAR_WATTS, default=defaults.get(CONF_AC_TRIGGER_SOLAR_WATTS, DEFAULT_AC_TRIGGER_SOLAR_WATTS)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=500, max=5000, step=100, unit_of_measurement="W")
        ),
        vol.Optional(CONF_AC_SOLAR_WINDOW_START, default=defaults.get(CONF_AC_SOLAR_WINDOW_START, DEFAULT_AC_SOLAR_WINDOW_START)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=23, unit_of_measurement="hour")
        ),
        vol.Optional(CONF_AC_SOLAR_WINDOW_END, default=defaults.get(CONF_AC_SOLAR_WINDOW_END, DEFAULT_AC_SOLAR_WINDOW_END)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=23, unit_of_measurement="hour")
        ),
        vol.Optional(CONF_AC_TRIGGER_HUMIDITY, default=defaults.get(CONF_AC_TRIGGER_HUMIDITY, DEFAULT_AC_TRIGGER_HUMIDITY)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=40, max=80, unit_of_measurement="%")
        ),
        # Heating
        vol.Optional(CONF_HEAT_THRESHOLD, default=defaults.get(CONF_HEAT_THRESHOLD, DEFAULT_HEAT_THRESHOLD)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=50, max=75, unit_of_measurement="°F")
        ),
        vol.Optional(CONF_HEAT_SETPOINT, default=defaults.get(CONF_HEAT_SETPOINT, DEFAULT_HEAT_SETPOINT)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=50, max=75, unit_of_measurement="°F")
        ),
        vol.Optional(CONF_EMERGENCY_HEAT_THRESHOLD, default=defaults.get(CONF_EMERGENCY_HEAT_THRESHOLD, DEFAULT_EMERGENCY_HEAT_THRESHOLD)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=30, max=60, unit_of_measurement="°F")
        ),
        # Setback & Occupancy
        vol.Optional(CONF_SETBACK_COOL_TEMP, default=defaults.get(CONF_SETBACK_COOL_TEMP, DEFAULT_SETBACK_COOL_TEMP)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=70, max=85, unit_of_measurement="°F")
        ),
        vol.Optional(CONF_SETBACK_HEAT_TEMP, default=defaults.get(CONF_SETBACK_HEAT_TEMP, DEFAULT_SETBACK_HEAT_TEMP)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=55, max=70, unit_of_measurement="°F")
        ),
        vol.Optional(CONF_UNOCCUPIED_HOURS, default=defaults.get(CONF_UNOCCUPIED_HOURS, DEFAULT_UNOCCUPIED_HOURS)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=24, step=1, unit_of_measurement="hours")
        ),
        vol.Optional(CONF_RETURN_HOME_COOL_SETPOINT, default=defaults.get(CONF_RETURN_HOME_COOL_SETPOINT, DEFAULT_RETURN_HOME_COOL_SETPOINT)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=68, max=78, unit_of_measurement="°F")
        ),
        vol.Optional(CONF_RETURN_HOME_HEAT_SETPOINT, default=defaults.get(CONF_RETURN_HOME_HEAT_SETPOINT, DEFAULT_RETURN_HOME_HEAT_SETPOINT)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=50, max=75, unit_of_measurement="°F")
        ),
        # Forecast & Conditioning
        vol.Optional(CONF_PRECOOL_TRIGGER, default=defaults.get(CONF_PRECOOL_TRIGGER, DEFAULT_PRECOOL_TRIGGER)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=80, max=110, unit_of_measurement="°F")
        ),
        vol.Optional(CONF_PREHEAT_TRIGGER, default=defaults.get(CONF_PREHEAT_TRIGGER, DEFAULT_PREHEAT_TRIGGER)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=-20, max=50, unit_of_measurement="°F")
        ),
        # Windows & Passive Cooling
        vol.Optional(CONF_WINDOWS_ASSUMED_OPEN_SENSOR, default=defaults.get(CONF_WINDOWS_ASSUMED_OPEN_SENSOR, DEFAULT_WINDOWS_SENSOR)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor")
        ),
        vol.Optional(CONF_WINDOW_FAN_SPEED, default=defaults.get(CONF_WINDOW_FAN_SPEED, DEFAULT_WINDOW_FAN_SPEED)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=100, unit_of_measurement="%")
        ),
        vol.Optional(CONF_PASSIVE_COOLING_ENABLED, default=defaults.get(CONF_PASSIVE_COOLING_ENABLED, DEFAULT_PASSIVE_COOLING_ENABLED)): selector.BooleanSelector(),
    }


def _zone_schema_dict(defaults: dict) -> dict:
    """Build zone configuration schema."""
    return {
        # Room Identity
        vol.Required(CONF_ZONE_NAME, default=defaults.get(CONF_ZONE_NAME, "")): str,
        vol.Optional(CONF_FLOOR, default=defaults.get(CONF_FLOOR, "")): str,
        vol.Optional(CONF_IS_PRIMARY_ZONE, default=defaults.get(CONF_IS_PRIMARY_ZONE, DEFAULT_IS_PRIMARY_ZONE)): selector.BooleanSelector(),
        vol.Optional(CONF_AUTO_CONTROL_ENABLED, default=defaults.get(CONF_AUTO_CONTROL_ENABLED, DEFAULT_AUTO_CONTROL_ENABLED)): selector.BooleanSelector(),
        # Sensors
        vol.Required(CONF_TEMP_SENSORS, default=defaults.get(CONF_TEMP_SENSORS, [])): selector.EntitiesSelector(
            selector.EntitiesSelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_HUMIDITY_SENSOR, default=defaults.get(CONF_HUMIDITY_SENSOR, "")): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_WINDOW_SENSOR, default=defaults.get(CONF_WINDOW_SENSOR, "")): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor")
        ),
        vol.Optional(CONF_ZONE_OCCUPANCY, default=defaults.get(CONF_ZONE_OCCUPANCY, "")): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor")
        ),
        # Cooling Thresholds
        vol.Optional(CONF_COMFORT_UPPER, default=defaults.get(CONF_COMFORT_UPPER, DEFAULT_COMFORT_UPPER)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=65, max=75, unit_of_measurement="°F")
        ),
        vol.Optional(CONF_PASSIVE_THRESHOLD, default=defaults.get(CONF_PASSIVE_THRESHOLD, DEFAULT_PASSIVE_THRESHOLD)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=68, max=78, unit_of_measurement="°F")
        ),
        vol.Optional(CONF_PASSIVE_HUMID_THRESHOLD, default=defaults.get(CONF_PASSIVE_HUMID_THRESHOLD, DEFAULT_PASSIVE_HUMID_THRESHOLD)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=40, max=80, unit_of_measurement="%")
        ),
        vol.Optional(CONF_ESCALATE_THRESHOLD, default=defaults.get(CONF_ESCALATE_THRESHOLD, DEFAULT_ESCALATE_THRESHOLD)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=70, max=80, unit_of_measurement="°F")
        ),
        vol.Optional(CONF_EMERGENCY_THRESHOLD, default=defaults.get(CONF_EMERGENCY_THRESHOLD, DEFAULT_EMERGENCY_THRESHOLD)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=75, max=90, unit_of_measurement="°F")
        ),
    }


class AdaptiveHVACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Adaptive HVAC."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle user step — system entry or zone entry."""
        system_entry = None
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("entry_type") == ENTRY_TYPE_SYSTEM:
                system_entry = entry
                break

        if system_entry is None:
            return await self.async_step_system()

        return await self.async_step_zone()

    async def async_step_system(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step for system-level configuration."""
        errors = {}

        if user_input is not None:
            if not user_input.get(CONF_THERMOSTAT) or not user_input.get(CONF_WEATHER):
                errors["base"] = "required_fields"
            else:
                return self.async_create_entry(
                    title="Adaptive HVAC System",
                    data={
                        "entry_type": ENTRY_TYPE_SYSTEM,
                        **user_input,
                    },
                )

        schema = vol.Schema(_system_schema_dict({}))

        return self.async_show_form(
            step_id="system",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_zone(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step for zone configuration."""
        errors = {}

        if user_input is not None:
            zone_name = user_input.get(CONF_ZONE_NAME, "").strip()
            if not zone_name:
                errors[CONF_ZONE_NAME] = "required"
            elif not user_input.get(CONF_TEMP_SENSORS):
                errors[CONF_TEMP_SENSORS] = "required"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_zone_{zone_name}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=zone_name,
                    data={
                        "entry_type": ENTRY_TYPE_ZONE,
                        **user_input,
                    },
                )

        schema = vol.Schema(_zone_schema_dict({}))

        return self.async_show_form(
            step_id="zone",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return options flow."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Options flow for Adaptive HVAC."""

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Init step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Build options schema based on entry type
        if self.config_entry.data.get("entry_type") == ENTRY_TYPE_SYSTEM:
            defaults = {**self.config_entry.data, **self.config_entry.options}
            schema = vol.Schema(_system_schema_dict(defaults))
        else:
            defaults = {**self.config_entry.data, **self.config_entry.options}
            schema = vol.Schema(_zone_schema_dict(defaults))

        return self.async_show_form(step_id="init", data_schema=schema)
