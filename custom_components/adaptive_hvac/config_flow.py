"""Config flow for Adaptive HVAC."""

from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN, ENTRY_TYPE_SYSTEM, ENTRY_TYPE_ZONE


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
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_abort(reason="options_not_supported")
