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


def _system_schema_dict(defaults: dict) -> dict:
    """Generate system schema with defaults."""
    return {
        vol.Required(
            "thermostat_entity",
            default=defaults.get("thermostat_entity", ""),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="climate")
        ),
        vol.Required(
            "weather_entity",
            default=defaults.get("weather_entity", ""),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="weather")
        ),
        vol.Optional(
            "passive_fan_threshold",
            default=defaults.get("passive_fan_threshold", 70.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=60, max=75, step=0.5, unit_of_measurement="°F")
        ),
        vol.Optional(
            "escalate_enabled_downstairs_temp",
            default=defaults.get("escalate_enabled_downstairs_temp", 68.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=60, max=75, step=0.5, unit_of_measurement="°F")
        ),
        vol.Optional(
            "escalate_enabled_upstairs_temp",
            default=defaults.get("escalate_enabled_upstairs_temp", 74.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=60, max=85, step=0.5, unit_of_measurement="°F")
        ),
        vol.Optional(
            "windows_assumed_open_sensor",
            default=defaults.get("windows_assumed_open_sensor", "binary_sensor.windows_assumed_open"),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor")
        ),
        vol.Optional(
            "sleep_posture_entity",
            default=defaults.get("sleep_posture_entity", ""),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="input_boolean")
        ),
        vol.Optional(
            "occupancy_entities",
            default=defaults.get("occupancy_entities", []),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
        ),
        vol.Optional(
            "solar_entity",
            default=defaults.get("solar_entity", ""),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(
            "ac_setpoint",
            default=defaults.get("ac_setpoint", 68.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=60, max=78, step=1, unit_of_measurement="°F")
        ),
        vol.Optional(
            "heat_setpoint",
            default=defaults.get("heat_setpoint", 68.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=60, max=78, step=1, unit_of_measurement="°F")
        ),
        vol.Optional(
            "heat_threshold",
            default=defaults.get("heat_threshold", 68.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=55, max=72, step=1, unit_of_measurement="°F")
        ),
        vol.Optional(
            "emergency_heat_threshold",
            default=defaults.get("emergency_heat_threshold", 55.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=40, max=60, step=1, unit_of_measurement="°F")
        ),
        vol.Optional(
            "setback_cool_temp",
            default=defaults.get("setback_cool_temp", 76.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=70, max=85, step=1, unit_of_measurement="°F")
        ),
        vol.Optional(
            "setback_heat_temp",
            default=defaults.get("setback_heat_temp", 62.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=55, max=68, step=1, unit_of_measurement="°F")
        ),
        vol.Optional(
            "ac_trigger_solar_watts",
            default=defaults.get("ac_trigger_solar_watts", 2000.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=500, max=10000, step=100, unit_of_measurement="W")
        ),
        vol.Optional(
            "window_fan_speed",
            default=defaults.get("window_fan_speed", 25.0),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
        ),
    }


def _zone_schema_dict(defaults: dict) -> dict:
    """Generate zone schema with defaults."""
    return {
        vol.Optional(
            "temp_sensors",
            default=defaults.get("temp_sensors", []),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", multiple=True)
        ),
        vol.Optional(
            "humidity_sensor",
            default=defaults.get("humidity_sensor", ""),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(
            "window_sensor",
            default=defaults.get("window_sensor", ""),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor")
        ),
        vol.Optional(
            "occupancy_sensor",
            default=defaults.get("occupancy_sensor", ""),
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
            selector.NumberSelectorConfig(min=60, max=85, step=1, unit_of_measurement="°F")
        ),
        vol.Optional(
            "passive_threshold",
            default=defaults.get("passive_threshold", DEFAULT_PASSIVE_THRESHOLD),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=60, max=85, step=1, unit_of_measurement="°F")
        ),
        vol.Optional(
            "escalate_threshold",
            default=defaults.get("escalate_threshold", DEFAULT_ESCALATE_THRESHOLD),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=60, max=85, step=1, unit_of_measurement="°F")
        ),
        vol.Optional(
            "passive_fan_speed",
            default=defaults.get("passive_fan_speed", DEFAULT_PASSIVE_FAN_SPEED),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
        ),
        vol.Optional(
            "escalate_fan_speed",
            default=defaults.get("escalate_fan_speed", DEFAULT_ESCALATE_FAN_SPEED),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
        ),
        vol.Optional(
            "emergency_fan_speed",
            default=defaults.get("emergency_fan_speed", DEFAULT_EMERGENCY_FAN_SPEED),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
        ),
    }


class AdaptiveHVACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Adaptive HVAC."""

    VERSION = 1
    system_data: Dict[str, Any] = {}

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
        """Step 1: Thermostat & Weather (required)."""
        if user_input is not None:
            self.system_data = user_input
            return await self.async_step_system_entities()

        return self.async_show_form(
            step_id="system",
            data_schema=vol.Schema({
                vol.Required(
                    "thermostat_entity",
                    default="",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Required(
                    "weather_entity",
                    default="",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
            }),
            description_placeholders={"step_title": "Step 1/3: Thermostat & Weather"},
        )

    async def async_step_system_entities(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step 2: House-level sensors (optional but recommended)."""
        if user_input is not None:
            self.system_data.update(user_input)
            return await self.async_step_system_thresholds()

        return self.async_show_form(
            step_id="system_entities",
            data_schema=vol.Schema({
                vol.Optional(
                    "windows_assumed_open_sensor",
                    default="binary_sensor.windows_assumed_open",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(
                    "sleep_posture_entity",
                    default="",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="input_boolean")
                ),
                vol.Optional(
                    "occupancy_entities",
                    default=[],
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
                ),
                vol.Optional(
                    "solar_entity",
                    default="",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }),
            description_placeholders={"step_title": "Step 2/3: House-Level Sensors (Optional)"},
        )

    async def async_step_system_thresholds(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step 3a: AC & Heat Setpoints — What temperatures to cool/heat to."""
        if user_input is not None:
            self.system_data.update(user_input)
            return await self.async_step_system_heating()

        return self.async_show_form(
            step_id="system_thresholds",
            data_schema=vol.Schema({
                vol.Optional("ac_setpoint", default=68.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=78, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("heat_setpoint", default=68.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=78, step=1, unit_of_measurement="°F")
                ),
            }),
        )

    async def async_step_system_heating(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step 3b: Heating Triggers — When to activate heat."""
        if user_input is not None:
            self.system_data.update(user_input)
            return await self.async_step_system_passive()

        return self.async_show_form(
            step_id="system_heating",
            data_schema=vol.Schema({
                vol.Optional("heat_threshold", default=68.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=55, max=72, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("emergency_heat_threshold", default=55.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=40, max=60, step=1, unit_of_measurement="°F")
                ),
            }),
        )

    async def async_step_system_passive(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step 3c: Whole-House Fan & Equalization — Fan activation and zone balancing."""
        if user_input is not None:
            self.system_data.update(user_input)
            return await self.async_step_system_setback()

        return self.async_show_form(
            step_id="system_passive",
            data_schema=vol.Schema({
                vol.Optional("passive_fan_threshold", default=70.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=75, step=0.5, unit_of_measurement="°F")
                ),
                vol.Optional("escalate_enabled_downstairs_temp", default=68.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=75, step=0.5, unit_of_measurement="°F")
                ),
                vol.Optional("escalate_enabled_upstairs_temp", default=74.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=85, step=0.5, unit_of_measurement="°F")
                ),
            }),
        )

    async def async_step_system_setback(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step 3d: Away Mode Setback — Temps when house is unoccupied 8+ hours."""
        if user_input is not None:
            self.system_data.update(user_input)
            return await self.async_step_system_other()

        return self.async_show_form(
            step_id="system_setback",
            data_schema=vol.Schema({
                vol.Optional("setback_cool_temp", default=76.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=70, max=85, step=1, unit_of_measurement="°F")
                ),
                vol.Optional("setback_heat_temp", default=62.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=55, max=68, step=1, unit_of_measurement="°F")
                ),
            }),
        )

    async def async_step_system_other(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step 3e: Other — Solar and fan circulation settings."""
        if user_input is not None:
            self.system_data.update(user_input)
            return self.async_create_entry(
                title="Adaptive HVAC System",
                data={
                    "entry_type": ENTRY_TYPE_SYSTEM,
                    **self.system_data,
                },
            )

        return self.async_show_form(
            step_id="system_other",
            data_schema=vol.Schema({
                vol.Optional("ac_trigger_solar_watts", default=2000.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=500, max=10000, step=100, unit_of_measurement="W")
                ),
                vol.Optional("window_fan_speed", default=25.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
                ),
            }),
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
                        **user_input,
                    },
                )

        description_text = """
**Zone Configuration — Per-Room Settings**

**Required**
- Zone name: identifier for this room (e.g., "Upstairs", "Master Bedroom")
- Temperature sensors: 1+ sensor per zone, averaged for decision logic

**Optional Sensors**
- Humidity sensor: if humidity ≥55% AND temp ≥72°F in summer, triggers passive cooling
- Window sensor: zone-specific window (system windows also checked for AC/heat blocking)
- Occupancy sensor: marks zone as "relevant" for equalization logic (closed rooms don't gate AC)
- Fans: which fans this zone controls (leave blank if zone has no fans)

**Temperature Thresholds** (°F) — When to change modes
- Comfort upper: below this, fans off (default 70°F)
- Passive threshold: above this, fans on at passive speed (default 72°F)
- Escalate threshold: above this for 30min, AC activates (default 74°F)

**Fan Speeds** (%) — Speed in each mode
- Comfort: fans off (0%) or leave off entirely
- Passive: fan speed when in passive mode (default 33%)
- Escalate: fan speed when AC is escalating (default 50%)
- Emergency: fan speed above 78°F (default 100%)

**Auto-Control Toggle**
- Accessible after zone is created: switch.adaptive_hvac_{zone_name}_auto
- ON = auto control (system commands fans), OFF = user-only (you control fans)
"""
        return self.async_show_form(
            step_id="zone",
            data_schema=vol.Schema({
                vol.Required("zone_name", default=user_input.get("zone_name", "") if user_input else ""): str,
                **_zone_schema_dict(user_input or {}),
            }),
            description_placeholders={
                "info": description_text
            },
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
            data_schema=vol.Schema(_system_schema_dict(defaults)),
            description_placeholders={
                "info": """
**Required Entities**
- Thermostat: Climate entity that controls heating/cooling
- Weather: Forecast source (for pre-cool/pre-heat logic)

**House-Level Sensors** (Optional)
- Windows: Binary sensor — if ON, AC/heat OFF, fans ON for passive ventilation
- Sleep posture: Master bedroom sleep mode — gates heating during sleep
- Occupancy: When all OFF for 8+ hours, triggers away setback temps
- Solar: Production sensor — high solar triggers AC escalation (system-dependent)

**Temperature Setpoints** (What temps to cool/heat to)
- AC setpoint: Target when cooling (default 68°F)
- Heat setpoint: Target when heating (default 68°F)

**Heating Triggers** (When to activate heat)
- Heat threshold: Below this, heat activates (default 68°F)
- Emergency heat: Always on below this (default 55°F)

**Passive Cooling & Equalization** (Multi-zone balancing)
- Passive fan threshold: Hottest zone above this → whole-house fan ON first (default 70°F)
- Escalate downstairs: Coldest occupied zone must be above this for AC (default 68°F)
- Escalate upstairs: Hottest occupied zone must be above this for AC (default 74°F)

**Away Mode Setback** (Temps when unoccupied 8+ hours)
- Cool setpoint: Away cooling target (default 76°F)
- Heat setpoint: Away heating target (default 62°F)

**Other**
- Solar trigger: Watts above this triggers AC escalation (default 2000W)
- Window fan speed: Circulation speed when windows open (default 25%)
            """
            },
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
            data_schema=vol.Schema(_zone_schema_dict(defaults)),
        )
