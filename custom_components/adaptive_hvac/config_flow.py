"""Config flow for Adaptive HVAC."""

from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN, ENTRY_TYPE_SYSTEM, ENTRY_TYPE_ZONE,
    DEFAULT_COMFORT_UPPER, DEFAULT_PASSIVE_THRESHOLD, DEFAULT_ESCALATE_THRESHOLD,
    DEFAULT_PASSIVE_FAN_SPEED, DEFAULT_ESCALATE_FAN_SPEED, DEFAULT_EMERGENCY_FAN_SPEED,
)


class AdaptiveHVACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Adaptive HVAC."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle user step — choose system or zone."""
        if user_input is not None:
            if user_input.get("setup_type") == "system":
                return await self.async_step_system()
            else:
                return await self.async_step_zone()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("setup_type"): vol.In(["system", "zone"]),
            }),
        )

    async def async_step_system(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step for system-level configuration."""
        if user_input is not None:
            return self.async_create_entry(
                title="Adaptive HVAC System",
                data={
                    "entry_type": ENTRY_TYPE_SYSTEM,
                    "thermostat_entity": user_input.get("thermostat", "climate.downstairs_thermostat"),
                    "weather_entity": user_input.get("weather", "weather.forecast_home"),
                },
            )

        schema = vol.Schema({
            vol.Required("thermostat", default="climate.downstairs_thermostat"): str,
            vol.Required("weather", default="weather.forecast_home"): str,
        })

        return self.async_show_form(
            step_id="system",
            data_schema=schema,
        )

    async def async_step_zone(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step for zone configuration."""
        if user_input is not None:
            zone_name = user_input.get("zone_name", "").strip()
            if zone_name:
                await self.async_set_unique_id(f"{DOMAIN}_zone_{zone_name}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=zone_name,
                    data={
                        "entry_type": ENTRY_TYPE_ZONE,
                        "zone_name": zone_name,
                    },
                )

        schema = vol.Schema({
            vol.Required("zone_name"): str,
        })

        return self.async_show_form(
            step_id="zone",
            data_schema=schema,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return options flow."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Options flow for Adaptive HVAC."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Init step."""
        entry_type = self.config_entry.data.get("entry_type")

        if entry_type == ENTRY_TYPE_ZONE:
            return await self.async_step_zone_config()
        elif entry_type == ENTRY_TYPE_SYSTEM:
            return await self.async_step_system_config()

        return self.async_abort(reason="unknown_entry_type")

    async def async_step_zone_config(self, user_input=None):
        """Configure zone sensors and fans."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options or {}
        schema = vol.Schema({
            vol.Optional(
                "temp_sensors",
                description={"suggested_value": current.get("temp_sensors", [])},
            ): selector.EntityMultiSelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=True)
            ),
            vol.Optional(
                "humidity_sensor",
                description={"suggested_value": current.get("humidity_sensor")},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                "window_sensor",
                description={"suggested_value": current.get("window_sensor")},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(
                "occupancy_sensor",
                description={"suggested_value": current.get("occupancy_sensor")},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor")
            ),
            vol.Optional(
                "fans",
                description={"suggested_value": current.get("fans", [])},
            ): selector.EntityMultiSelector(
                selector.EntitySelectorConfig(domain="fan", multiple=True)
            ),
            vol.Optional(
                "comfort_upper",
                default=current.get("comfort_upper", DEFAULT_COMFORT_UPPER),
            ): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
            vol.Optional(
                "passive_threshold",
                default=current.get("passive_threshold", DEFAULT_PASSIVE_THRESHOLD),
            ): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
            vol.Optional(
                "escalate_threshold",
                default=current.get("escalate_threshold", DEFAULT_ESCALATE_THRESHOLD),
            ): vol.All(vol.Coerce(float), vol.Range(min=60, max=85)),
            vol.Optional(
                "passive_fan_speed",
                default=current.get("passive_fan_speed", DEFAULT_PASSIVE_FAN_SPEED),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                "escalate_fan_speed",
                default=current.get("escalate_fan_speed", DEFAULT_ESCALATE_FAN_SPEED),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                "emergency_fan_speed",
                default=current.get("emergency_fan_speed", DEFAULT_EMERGENCY_FAN_SPEED),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        })

        return self.async_show_form(
            step_id="zone_config",
            data_schema=schema,
        )

    async def async_step_system_config(self, user_input=None):
        """Configure system options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options or {}
        schema = vol.Schema({
            vol.Optional(
                "thermostat_entity",
                description={"suggested_value": current.get("thermostat_entity")},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="climate")
            ),
            vol.Optional(
                "weather_entity",
                description={"suggested_value": current.get("weather_entity")},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
        })

        return self.async_show_form(
            step_id="system_config",
            data_schema=schema,
        )
