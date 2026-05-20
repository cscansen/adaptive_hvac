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
    CONF_THERMOSTAT,
    CONF_WEATHER,
    CONF_SOLAR,
    CONF_SLEEP_POSTURE,
    CONF_OCCUPANCY,
    CONF_ZONE_NAME,
    CONF_FLOOR,
    CONF_TEMP_SENSORS,
    CONF_HUMIDITY_SENSOR,
    CONF_CEILING_FANS,
    CONF_FAN_LOCK_ENTITIES,
    CONF_WINDOW_SENSOR,
    CONF_ZONE_OCCUPANCY,
    DEFAULT_THERMOSTAT,
    DEFAULT_WEATHER,
    DEFAULT_SOLAR,
    DEFAULT_SLEEP_POSTURE,
)


class AdaptiveHVACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Adaptive HVAC."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle user step — system entry or zone entry."""
        # Check if system entry exists
        system_entry = None
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("entry_type") == ENTRY_TYPE_SYSTEM:
                system_entry = entry
                break

        if system_entry is None:
            # No system entry — guide user to create one
            return await self.async_step_system()

        # System entry exists — go straight to zone setup
        return await self.async_step_zone()

    async def async_step_system(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step for system-level configuration."""
        errors = {}

        if user_input is not None:
            # Validate required fields
            if not user_input.get(CONF_THERMOSTAT):
                errors[CONF_THERMOSTAT] = "required"
            elif not user_input.get(CONF_WEATHER):
                errors[CONF_WEATHER] = "required"

            if not errors:
                return self.async_create_entry(
                    title="Adaptive HVAC System",
                    data={
                        "entry_type": ENTRY_TYPE_SYSTEM,
                        **user_input,
                    },
                )

        # Build schema
        schema = vol.Schema({
            vol.Required(CONF_THERMOSTAT, default=DEFAULT_THERMOSTAT): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="climate")
            ),
            vol.Required(CONF_WEATHER, default=DEFAULT_WEATHER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_SOLAR, default=DEFAULT_SOLAR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_SLEEP_POSTURE, default=DEFAULT_SLEEP_POSTURE): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="input_boolean")
            ),
            vol.Optional(CONF_OCCUPANCY): selector.EntitiesSelector(
                selector.EntitiesSelectorConfig(domain="binary_sensor")
            ),
        })

        return self.async_show_form(
            step_id="system",
            data_schema=schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_zone(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step for zone configuration."""
        errors = {}

        if user_input is not None:
            # Validate required fields
            if not user_input.get(CONF_ZONE_NAME):
                errors[CONF_ZONE_NAME] = "required"
            elif not user_input.get(CONF_TEMP_SENSORS):
                errors[CONF_TEMP_SENSORS] = "required"

            if not errors:
                return self.async_create_entry(
                    title=user_input.get(CONF_ZONE_NAME, "Zone"),
                    data={
                        "entry_type": ENTRY_TYPE_ZONE,
                        **user_input,
                    },
                )

        # Build schema
        schema = vol.Schema({
            vol.Required(CONF_ZONE_NAME): str,
            vol.Optional(CONF_FLOOR, default=""): str,
            vol.Required(CONF_TEMP_SENSORS): selector.EntitiesSelector(
                selector.EntitiesSelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_HUMIDITY_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_CEILING_FANS): selector.EntitiesSelector(
                selector.EntitiesSelectorConfig(domain="fan")
            ),
            vol.Optional(CONF_FAN_LOCK_ENTITIES): selector.EntitiesSelector(
                selector.EntitiesSelectorConfig(domain="input_boolean")
            ),
            vol.Optional(CONF_WINDOW_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(CONF_ZONE_OCCUPANCY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
        })

        return self.async_show_form(
            step_id="zone",
            data_schema=schema,
            errors=errors,
            description_placeholders={},
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
            schema = vol.Schema({
                vol.Optional("summer_threshold", default=75): vol.Range(min=50, max=100),
                vol.Optional("winter_threshold", default=40): vol.Range(min=-20, max=60),
                vol.Optional("precool_trigger", default=92): vol.Range(min=70, max=110),
                vol.Optional("preheat_trigger", default=30): vol.Range(min=-20, max=50),
            })
        else:
            schema = vol.Schema({
                vol.Optional("comfort_upper", default=70): vol.Range(min=60, max=80),
                vol.Optional("passive_threshold", default=72): vol.Range(min=60, max=80),
                vol.Optional("escalate_threshold", default=74): vol.Range(min=60, max=80),
                vol.Optional("emergency_threshold", default=78): vol.Range(min=70, max=90),
                vol.Optional("passive_fan_speed", default=33): vol.Range(min=0, max=100),
                vol.Optional("escalate_fan_speed", default=50): vol.Range(min=0, max=100),
            })

        return self.async_show_form(step_id="init", data_schema=schema)
