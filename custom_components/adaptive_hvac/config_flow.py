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
                    "thermostat_entity": user_input.get("thermostat"),
                    "weather_entity": user_input.get("weather"),
                },
            )

        schema = vol.Schema({
            vol.Required("thermostat"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="climate")
            ),
            vol.Required("weather"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
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
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return options flow."""
        if config_entry.data.get("entry_type") == ENTRY_TYPE_SYSTEM:
            return SystemOptionsFlow(config_entry)
        return ZoneOptionsFlow(config_entry)


class SystemOptionsFlow(config_entries.OptionsFlow):
    """Options flow for system configuration."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input=None):
        """Handle options for system entry."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self._entry.data, **self._entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    "thermostat_entity",
                    default=defaults.get("thermostat_entity"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Required(
                    "weather_entity",
                    default=defaults.get("weather_entity"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
            }),
        )


class ZoneOptionsFlow(config_entries.OptionsFlow):
    """Options flow for zone configuration."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input=None):
        """Handle options for zone entry."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self._entry.data, **self._entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    "temp_sensors",
                    default=defaults.get("temp_sensors", []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Optional(
                    "humidity_sensor",
                    default=defaults.get("humidity_sensor"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    "window_sensor",
                    default=defaults.get("window_sensor"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(
                    "occupancy_sensor",
                    default=defaults.get("occupancy_sensor"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(
                    "fans",
                    default=defaults.get("fans", []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="fan", multiple=True)
                ),
                vol.Optional(
                    "comfort_upper",
                    default=defaults.get("comfort_upper", DEFAULT_COMFORT_UPPER),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=85, step=0.5, unit_of_measurement="°F")
                ),
                vol.Optional(
                    "passive_threshold",
                    default=defaults.get("passive_threshold", DEFAULT_PASSIVE_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=85, step=0.5, unit_of_measurement="°F")
                ),
                vol.Optional(
                    "escalate_threshold",
                    default=defaults.get("escalate_threshold", DEFAULT_ESCALATE_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=85, step=0.5, unit_of_measurement="°F")
                ),
                vol.Optional(
                    "passive_fan_speed",
                    default=defaults.get("passive_fan_speed", DEFAULT_PASSIVE_FAN_SPEED),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=100, step=5, unit_of_measurement="%")
                ),
                vol.Optional(
                    "escalate_fan_speed",
                    default=defaults.get("escalate_fan_speed", DEFAULT_ESCALATE_FAN_SPEED),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=100, step=5, unit_of_measurement="%")
                ),
                vol.Optional(
                    "emergency_fan_speed",
                    default=defaults.get("emergency_fan_speed", DEFAULT_EMERGENCY_FAN_SPEED),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=100, step=5, unit_of_measurement="%")
                ),
            }),
        )
