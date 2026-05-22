"""Config flow for Adaptive HVAC."""

from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    ENTRY_TYPE_SYSTEM,
    ENTRY_TYPE_ZONE,
    # System config
    CONF_THERMOSTAT,
    CONF_WEATHER,
    CONF_SOLAR,
    CONF_SLEEP_POSTURE,
    CONF_OCCUPANCY,
    CONF_AC_ENABLED,
    CONF_AC_SETPOINT,
    CONF_HEAT_THRESHOLD,
    CONF_HEAT_SETPOINT,
    CONF_EMERGENCY_HEAT_THRESHOLD,
    CONF_SETBACK_COOL_TEMP,
    CONF_SETBACK_HEAT_TEMP,
    CONF_UNOCCUPIED_HOURS,
    CONF_WINDOWS_ASSUMED_OPEN_SENSOR,
    CONF_WINDOW_FAN_SPEED,
    CONF_PASSIVE_COOLING_ENABLED,
    # Zone config
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
    # Defaults
    DEFAULT_THERMOSTAT,
    DEFAULT_WEATHER,
    DEFAULT_SOLAR,
    DEFAULT_SLEEP_POSTURE,
    DEFAULT_AC_SETPOINT,
    DEFAULT_HEAT_THRESHOLD,
    DEFAULT_HEAT_SETPOINT,
    DEFAULT_EMERGENCY_HEAT_THRESHOLD,
    DEFAULT_SETBACK_COOL_TEMP,
    DEFAULT_SETBACK_HEAT_TEMP,
    DEFAULT_UNOCCUPIED_HOURS,
    DEFAULT_WINDOWS_SENSOR,
    DEFAULT_WINDOW_FAN_SPEED,
    DEFAULT_PASSIVE_COOLING_ENABLED,
    DEFAULT_COMFORT_UPPER,
    DEFAULT_PASSIVE_THRESHOLD,
    DEFAULT_PASSIVE_HUMID_THRESHOLD,
    DEFAULT_ESCALATE_THRESHOLD,
    DEFAULT_EMERGENCY_THRESHOLD,
    DEFAULT_IS_PRIMARY_ZONE,
    DEFAULT_AUTO_CONTROL_ENABLED,
)


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

        schema = vol.Schema({
            vol.Required(CONF_THERMOSTAT, default=DEFAULT_THERMOSTAT): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="climate")
            ),
            vol.Required(CONF_WEATHER, default=DEFAULT_WEATHER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_SOLAR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_SLEEP_POSTURE, default=DEFAULT_SLEEP_POSTURE): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="input_boolean")
            ),
            vol.Optional(CONF_OCCUPANCY, default=[]): selector.EntitiesSelector(
                selector.EntitiesSelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(CONF_AC_ENABLED, default=True): selector.BooleanSelector(),
            vol.Optional(CONF_AC_SETPOINT, default=DEFAULT_AC_SETPOINT): selector.NumberSelector(
                selector.NumberSelectorConfig(min=55, max=75, unit_of_measurement="°F")
            ),
            vol.Optional(CONF_HEAT_THRESHOLD, default=DEFAULT_HEAT_THRESHOLD): selector.NumberSelector(
                selector.NumberSelectorConfig(min=50, max=75, unit_of_measurement="°F")
            ),
            vol.Optional(CONF_HEAT_SETPOINT, default=DEFAULT_HEAT_SETPOINT): selector.NumberSelector(
                selector.NumberSelectorConfig(min=50, max=75, unit_of_measurement="°F")
            ),
            vol.Optional(CONF_EMERGENCY_HEAT_THRESHOLD, default=DEFAULT_EMERGENCY_HEAT_THRESHOLD): selector.NumberSelector(
                selector.NumberSelectorConfig(min=30, max=60, unit_of_measurement="°F")
            ),
            vol.Optional(CONF_SETBACK_COOL_TEMP, default=DEFAULT_SETBACK_COOL_TEMP): selector.NumberSelector(
                selector.NumberSelectorConfig(min=70, max=85, unit_of_measurement="°F")
            ),
            vol.Optional(CONF_SETBACK_HEAT_TEMP, default=DEFAULT_SETBACK_HEAT_TEMP): selector.NumberSelector(
                selector.NumberSelectorConfig(min=55, max=70, unit_of_measurement="°F")
            ),
            vol.Optional(CONF_UNOCCUPIED_HOURS, default=DEFAULT_UNOCCUPIED_HOURS): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=24, step=1, unit_of_measurement="hours")
            ),
            vol.Optional(CONF_WINDOWS_ASSUMED_OPEN_SENSOR, default=DEFAULT_WINDOWS_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(CONF_WINDOW_FAN_SPEED, default=DEFAULT_WINDOW_FAN_SPEED): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, unit_of_measurement="%")
            ),
            vol.Optional(CONF_PASSIVE_COOLING_ENABLED, default=DEFAULT_PASSIVE_COOLING_ENABLED): selector.BooleanSelector(),
        })

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

        schema = vol.Schema({
            vol.Required(CONF_ZONE_NAME): str,
            vol.Optional(CONF_FLOOR, default=""): str,
            vol.Optional(CONF_IS_PRIMARY_ZONE, default=DEFAULT_IS_PRIMARY_ZONE): selector.BooleanSelector(),
            vol.Optional(CONF_AUTO_CONTROL_ENABLED, default=DEFAULT_AUTO_CONTROL_ENABLED): selector.BooleanSelector(),
            vol.Required(CONF_TEMP_SENSORS): selector.EntitiesSelector(
                selector.EntitiesSelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_HUMIDITY_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_WINDOW_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(CONF_ZONE_OCCUPANCY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(CONF_COMFORT_UPPER, default=DEFAULT_COMFORT_UPPER): selector.NumberSelector(
                selector.NumberSelectorConfig(min=65, max=75, unit_of_measurement="°F")
            ),
            vol.Optional(CONF_PASSIVE_THRESHOLD, default=DEFAULT_PASSIVE_THRESHOLD): selector.NumberSelector(
                selector.NumberSelectorConfig(min=68, max=78, unit_of_measurement="°F")
            ),
            vol.Optional(CONF_PASSIVE_HUMID_THRESHOLD, default=DEFAULT_PASSIVE_HUMID_THRESHOLD): selector.NumberSelector(
                selector.NumberSelectorConfig(min=40, max=80, unit_of_measurement="%")
            ),
            vol.Optional(CONF_ESCALATE_THRESHOLD, default=DEFAULT_ESCALATE_THRESHOLD): selector.NumberSelector(
                selector.NumberSelectorConfig(min=70, max=80, unit_of_measurement="°F")
            ),
            vol.Optional(CONF_EMERGENCY_THRESHOLD, default=DEFAULT_EMERGENCY_THRESHOLD): selector.NumberSelector(
                selector.NumberSelectorConfig(min=75, max=90, unit_of_measurement="°F")
            ),
        })

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

        entry_type = self.config_entry.data.get("entry_type")
        defaults = {**self.config_entry.data, **self.config_entry.options}

        if entry_type == ENTRY_TYPE_SYSTEM:
            schema = vol.Schema({
                vol.Optional(CONF_AC_SETPOINT, default=defaults.get(CONF_AC_SETPOINT, DEFAULT_AC_SETPOINT)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=55, max=75, unit_of_measurement="°F")
                ),
                vol.Optional(CONF_HEAT_THRESHOLD, default=defaults.get(CONF_HEAT_THRESHOLD, DEFAULT_HEAT_THRESHOLD)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=50, max=75, unit_of_measurement="°F")
                ),
                vol.Optional(CONF_HEAT_SETPOINT, default=defaults.get(CONF_HEAT_SETPOINT, DEFAULT_HEAT_SETPOINT)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=50, max=75, unit_of_measurement="°F")
                ),
                vol.Optional(CONF_SETBACK_COOL_TEMP, default=defaults.get(CONF_SETBACK_COOL_TEMP, DEFAULT_SETBACK_COOL_TEMP)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=70, max=85, unit_of_measurement="°F")
                ),
                vol.Optional(CONF_SETBACK_HEAT_TEMP, default=defaults.get(CONF_SETBACK_HEAT_TEMP, DEFAULT_SETBACK_HEAT_TEMP)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=55, max=70, unit_of_measurement="°F")
                ),
            })
        else:
            schema = vol.Schema({
                vol.Optional(CONF_COMFORT_UPPER, default=defaults.get(CONF_COMFORT_UPPER, DEFAULT_COMFORT_UPPER)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=65, max=75, unit_of_measurement="°F")
                ),
                vol.Optional(CONF_PASSIVE_THRESHOLD, default=defaults.get(CONF_PASSIVE_THRESHOLD, DEFAULT_PASSIVE_THRESHOLD)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=68, max=78, unit_of_measurement="°F")
                ),
                vol.Optional(CONF_ESCALATE_THRESHOLD, default=defaults.get(CONF_ESCALATE_THRESHOLD, DEFAULT_ESCALATE_THRESHOLD)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=70, max=80, unit_of_measurement="°F")
                ),
            })

        return self.async_show_form(step_id="init", data_schema=schema)
