"""Config flow for Adaptive HVAC."""

from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN, ENTRY_TYPE_SYSTEM, ENTRY_TYPE_ZONE,
    DEFAULT_AC_SETPOINT, DEFAULT_HEAT_SETPOINT, DEFAULT_HEAT_THRESHOLD,
    DEFAULT_EMERGENCY_HEAT_THRESHOLD, DEFAULT_EMERGENCY_COOL_THRESHOLD,
    DEFAULT_COOL_EXTERIOR_THRESHOLD, DEFAULT_COOL_INTERIOR_OVERRIDE_DELTA,
    DEFAULT_HEAT_EXTERIOR_THRESHOLD,
    DEFAULT_WINTER_START_MONTH, DEFAULT_WINTER_END_MONTH,
    DEFAULT_ZONE_TARGET_TEMP, DEFAULT_FAN_SPEED,
)


@staticmethod
def _month_name(month: int) -> str:
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return months[month] if 1 <= month <= 12 else ""


def _month_selector(default: int) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(options=[
            selector.SelectOptionDict(value=str(i), label=f"{_month_name(i)}")
            for i in range(1, 13)
        ])
    )


def _zone_schema_dict(defaults: dict) -> dict:
    return {
        vol.Optional("temp_sensors", default=defaults.get("temp_sensors", [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", multiple=True)
        ),
        vol.Optional("humidity_sensor", default=defaults.get("humidity_sensor", [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", multiple=True)
        ),
        vol.Optional("window_sensor", default=defaults.get("window_sensor", [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["binary_sensor", "cover"], multiple=True)
        ),
        vol.Optional("occupancy_sensor", default=defaults.get("occupancy_sensor", [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
        ),
        vol.Optional("fans", default=defaults.get("fans", [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="fan", multiple=True)
        ),
        vol.Optional("zone_target_temp", default=defaults.get("zone_target_temp", DEFAULT_ZONE_TARGET_TEMP)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=60, max=85, step=1, unit_of_measurement="°F")
        ),
        vol.Optional("fan_speed", default=defaults.get("fan_speed", DEFAULT_FAN_SPEED)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=10, max=100, step=5, unit_of_measurement="%")
        ),
        vol.Optional("affects_thermostat", default=defaults.get("affects_thermostat", True)): selector.BooleanSelector(),
        vol.Optional("floor", default=defaults.get("floor", "")): selector.FloorSelector(),
    }


class AdaptiveHVACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Adaptive HVAC."""

    VERSION = 1
    _system_data: Dict[str, Any] = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Choose system or zone setup."""
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

    # ── System setup: Step 1 — Thermostat & Weather ──────────────────────────

    async def async_step_system(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        if user_input is not None:
            self._system_data = user_input
            return await self.async_step_system_sensors()

        return self.async_show_form(
            step_id="system",
            data_schema=vol.Schema({
                vol.Required("thermostat_entity", default=""): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Optional("outdoor_temp_sensor", default=""): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("weather_entity", default=""): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
            }),
            description_placeholders={"step_title": "Step 1/4: Thermostat & Weather"},
        )

    # ── System setup: Step 2 — House-level sensors ────────────────────────────

    async def async_step_system_sensors(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        if user_input is not None:
            self._system_data.update(user_input)
            return await self.async_step_system_cooling()

        return self.async_show_form(
            step_id="system_sensors",
            data_schema=vol.Schema({
                vol.Optional("sleep_posture_entity", default=""): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="input_boolean")
                ),
                vol.Optional("occupancy_entities", default=[]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
                ),
            }),
            description_placeholders={"step_title": "Step 2/4: House-Level Sensors (Optional)"},
        )

    # ── System setup: Step 3 — Cooling ───────────────────────────────────────

    async def async_step_system_cooling(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        if user_input is not None:
            self._system_data.update(user_input)
            return await self.async_step_system_heating()

        return self.async_show_form(
            step_id="system_cooling",
            data_schema=vol.Schema({
                vol.Optional("ac_setpoint", default=DEFAULT_AC_SETPOINT): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=78, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("cool_exterior_threshold", default=DEFAULT_COOL_EXTERIOR_THRESHOLD): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=40, max=80, step=1, unit_of_measurement="°F",
                                                  mode=selector.NumberSelectorMode.SLIDER)
                ),
                vol.Optional("cool_interior_override_delta", default=DEFAULT_COOL_INTERIOR_OVERRIDE_DELTA): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=15, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("emergency_cool_threshold", default=DEFAULT_EMERGENCY_COOL_THRESHOLD): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=78, max=110, step=1, unit_of_measurement="°F")
                ),
            }),
            description_placeholders={"step_title": "Step 3/4: Cooling Settings"},
        )

    # ── System setup: Step 4 — Heating & Season ──────────────────────────────

    async def async_step_system_heating(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        if user_input is not None:
            self._system_data.update(user_input)
            return self.async_create_entry(
                title="Adaptive HVAC System",
                data={"entry_type": ENTRY_TYPE_SYSTEM, **self._system_data},
            )

        return self.async_show_form(
            step_id="system_heating",
            data_schema=vol.Schema({
                vol.Optional("heat_setpoint", default=DEFAULT_HEAT_SETPOINT): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=78, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("heat_threshold", default=DEFAULT_HEAT_THRESHOLD): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=55, max=72, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("heat_exterior_threshold", default=DEFAULT_HEAT_EXTERIOR_THRESHOLD): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=40, max=80, step=1, unit_of_measurement="°F",
                                                  mode=selector.NumberSelectorMode.SLIDER)
                ),
                vol.Optional("emergency_heat_threshold", default=DEFAULT_EMERGENCY_HEAT_THRESHOLD): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-10, max=60, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("winter_start_month", default=str(DEFAULT_WINTER_START_MONTH)): _month_selector(DEFAULT_WINTER_START_MONTH),
                vol.Optional("winter_end_month", default=str(DEFAULT_WINTER_END_MONTH)): _month_selector(DEFAULT_WINTER_END_MONTH),
            }),
            description_placeholders={"step_title": "Step 4/4: Heating & Season"},
        )

    # ── Zone setup ────────────────────────────────────────────────────────────

    async def async_step_zone(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        if user_input is not None:
            zone_name = user_input.get("zone_name", "").strip()
            if zone_name:
                await self.async_set_unique_id(f"{DOMAIN}_zone_{zone_name}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=zone_name,
                    data={"entry_type": ENTRY_TYPE_ZONE, "zone_name": zone_name, **user_input},
                )

        return self.async_show_form(
            step_id="zone",
            data_schema=vol.Schema({
                vol.Required("zone_name", default=""): str,
                **_zone_schema_dict(user_input or {}),
            }),
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        if config_entry.data.get("entry_type") == ENTRY_TYPE_SYSTEM:
            return SystemOptionsFlow(config_entry)
        return ZoneOptionsFlow(config_entry)


class SystemOptionsFlow(config_entries.OptionsFlow):
    """Options flow for system configuration."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        d = {**self._entry.data, **self._entry.options}

        # Normalize list fields
        occ = d.get("occupancy_entities", [])
        if isinstance(occ, str):
            d["occupancy_entities"] = [occ] if occ else []

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("thermostat_entity", default=d.get("thermostat_entity", "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Optional("outdoor_temp_sensor", default=d.get("outdoor_temp_sensor", "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("weather_entity", default=d.get("weather_entity", "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Optional("sleep_posture_entity", default=d.get("sleep_posture_entity", "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="input_boolean")
                ),
                vol.Optional("occupancy_entities", default=d.get("occupancy_entities", [])): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
                ),
                vol.Optional("ac_setpoint", default=d.get("ac_setpoint", DEFAULT_AC_SETPOINT)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=78, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("cool_exterior_threshold", default=d.get("cool_exterior_threshold", DEFAULT_COOL_EXTERIOR_THRESHOLD)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=40, max=80, step=1, unit_of_measurement="°F",
                                                  mode=selector.NumberSelectorMode.SLIDER)
                ),
                vol.Optional("cool_interior_override_delta", default=d.get("cool_interior_override_delta", DEFAULT_COOL_INTERIOR_OVERRIDE_DELTA)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=15, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("emergency_cool_threshold", default=d.get("emergency_cool_threshold", DEFAULT_EMERGENCY_COOL_THRESHOLD)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=78, max=110, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("heat_setpoint", default=d.get("heat_setpoint", DEFAULT_HEAT_SETPOINT)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=78, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("heat_threshold", default=d.get("heat_threshold", DEFAULT_HEAT_THRESHOLD)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=55, max=72, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("heat_exterior_threshold", default=d.get("heat_exterior_threshold", DEFAULT_HEAT_EXTERIOR_THRESHOLD)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=40, max=80, step=1, unit_of_measurement="°F",
                                                  mode=selector.NumberSelectorMode.SLIDER)
                ),
                vol.Optional("emergency_heat_threshold", default=d.get("emergency_heat_threshold", DEFAULT_EMERGENCY_HEAT_THRESHOLD)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-10, max=60, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("winter_start_month", default=str(d.get("winter_start_month", DEFAULT_WINTER_START_MONTH))): _month_selector(DEFAULT_WINTER_START_MONTH),
                vol.Optional("winter_end_month", default=str(d.get("winter_end_month", DEFAULT_WINTER_END_MONTH))): _month_selector(DEFAULT_WINTER_END_MONTH),
            }),
        )


class ZoneOptionsFlow(config_entries.OptionsFlow):
    """Options flow for zone configuration."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        d = {**self._entry.data, **self._entry.options}

        # Normalize list fields
        for field in ["temp_sensors", "humidity_sensor", "window_sensor", "occupancy_sensor", "fans"]:
            val = d.get(field)
            if val is None or (isinstance(val, str) and not val):
                d[field] = []
            elif isinstance(val, str):
                d[field] = [val]
        # Normalize floor (optional string — None → "")
        if d.get("floor") is None:
            d["floor"] = ""

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(_zone_schema_dict(d)),
        )
