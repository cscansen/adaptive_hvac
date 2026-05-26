"""Constants for the Adaptive HVAC integration."""

DOMAIN = "adaptive_hvac"

# Entry types
ENTRY_TYPE_SYSTEM = "system"
ENTRY_TYPE_ZONE = "zone"

# State machine modes
MODE_MANUAL_OVERRIDE = "manual_override"
MODE_SENSOR_FAILSAFE = "sensor_failsafe"
MODE_EMERGENCY_COOLING = "emergency_cooling"
MODE_EMERGENCY_HEATING = "emergency_heating"
MODE_SETBACK_UNOCCUPIED = "setback_unoccupied"
MODE_SETBACK_NIGHT = "setback_night"
MODE_PRE_COOL = "pre_cool"
MODE_PRE_HEAT = "pre_heat"
MODE_AC_COOLING = "ac_cooling"
MODE_PASSIVE_COOLING = "passive_cooling"
MODE_PASSIVE_WINDOWS_OPEN = "passive_windows_open"
MODE_HEATING_NORMAL = "heating_normal"
MODE_EQUALIZATION = "equalization"
MODE_IDLE = "idle"

ALL_MODES = [
    MODE_MANUAL_OVERRIDE,
    MODE_SENSOR_FAILSAFE,
    MODE_EMERGENCY_COOLING,
    MODE_EMERGENCY_HEATING,
    MODE_SETBACK_UNOCCUPIED,
    MODE_SETBACK_NIGHT,
    MODE_PRE_COOL,
    MODE_PRE_HEAT,
    MODE_AC_COOLING,
    MODE_PASSIVE_COOLING,
    MODE_PASSIVE_WINDOWS_OPEN,
    MODE_HEATING_NORMAL,
    MODE_EQUALIZATION,
    MODE_IDLE,
]

# Seasons
SEASON_SUMMER = "summer"
SEASON_SHOULDER = "shoulder"
SEASON_WINTER = "winter"

ALL_SEASONS = [SEASON_SUMMER, SEASON_SHOULDER, SEASON_WINTER]

# Poll interval (minutes)
SCAN_INTERVAL_MINUTES = 3

# ===== DEFAULTS (SYSTEM) =====

# System — AC control
DEFAULT_AC_ENABLED = True
DEFAULT_AC_SETPOINT = 68.0
DEFAULT_AC_TRIGGER_SOLAR_WATTS = 2000
DEFAULT_AC_SOLAR_WINDOW_START = 10  # 10am
DEFAULT_AC_SOLAR_WINDOW_END = 15  # 3pm
DEFAULT_AC_TRIGGER_HUMIDITY = 55

# System — Heating
DEFAULT_HEAT_THRESHOLD = 68.0
DEFAULT_HEAT_SETPOINT = 68.0
DEFAULT_EMERGENCY_HEAT_THRESHOLD = 55.0

# System — Setback
DEFAULT_SETBACK_COOL_TEMP = 76.0
DEFAULT_SETBACK_HEAT_TEMP = 62.0
DEFAULT_UNOCCUPIED_HOURS = 8
DEFAULT_RETURN_HOME_COOL_SETPOINT = 74.0
DEFAULT_RETURN_HOME_HEAT_SETPOINT = 68.0

# System — Forecast
DEFAULT_PRECOOL_TRIGGER = 92.0
DEFAULT_PREHEAT_TRIGGER = 30.0

# System — Windows & passive
DEFAULT_WINDOWS_SENSOR = "binary_sensor.windows_assumed_open"
DEFAULT_WINDOW_FAN_SPEED = 25
DEFAULT_PASSIVE_COOLING_ENABLED = True
DEFAULT_WHOLE_HOUSE_FAN_ENTITY = "climate.downstairs_thermostat"

# System — Season thresholds (forecast-based)
DEFAULT_SUMMER_THRESHOLD = 75.0
DEFAULT_WINTER_THRESHOLD = 40.0

# System — Season calendar dates (for calendar-based gating, not forecast)
DEFAULT_WINTER_START_MONTH = 10  # October
DEFAULT_WINTER_END_MONTH = 4    # April
DEFAULT_SUMMER_START_MONTH = 5   # May
DEFAULT_SUMMER_END_MONTH = 9    # September

# System — AC/Heat gating thresholds (v0.2.19)
DEFAULT_COOL_EXTERIOR_THRESHOLD = 70.0  # °F, don't AC if below this
DEFAULT_COOL_INTERIOR_THRESHOLD = 74.0  # °F, don't AC if below this
DEFAULT_HEAT_EXTERIOR_THRESHOLD = 60.0  # °F, don't heat if above this
DEFAULT_HEAT_INTERIOR_THRESHOLD = 68.0  # °F, don't heat if above this

# ===== DEFAULTS (ZONE) =====

# Zone — Cooling thresholds
DEFAULT_COMFORT_UPPER = 70.0
DEFAULT_PASSIVE_THRESHOLD = 72.0
DEFAULT_PASSIVE_HUMID_THRESHOLD = 55
DEFAULT_ESCALATE_THRESHOLD = 74.0
DEFAULT_EMERGENCY_THRESHOLD = 78.0

# Zone — Fan speeds (per mode)
DEFAULT_COMFORT_SPEED = 0
DEFAULT_PASSIVE_FAN_SPEED = 33
DEFAULT_WINDOW_FAN_SPEED = 25
DEFAULT_PRECOOL_FAN_SPEED = 25
DEFAULT_ESCALATE_FAN_SPEED = 50
DEFAULT_EMERGENCY_FAN_SPEED = 100

# Zone — Flags
DEFAULT_IS_PRIMARY_ZONE = False
DEFAULT_AUTO_CONTROL_ENABLED = True

# Temperature trend thresholds (°F/hr)
TREND_PREEMPTIVE_PASSIVE = 0.8
TREND_AGGRESSIVE_ESCALATE = 1.5
TREND_THROTTLE_BACK = -0.5

# Hysteresis for season transitions (consecutive polls)
SEASON_HYSTERESIS_POLLS = 3

# Default entity IDs for system entry (single-thermostat whole-house)
DEFAULT_THERMOSTAT = "climate.downstairs_thermostat"
DEFAULT_WEATHER = "weather.forecast_home"
DEFAULT_SOLAR = "sensor.power_production_now"
DEFAULT_SLEEP_POSTURE = "input_boolean.master_suite_sleep_posture"

DEFAULT_CEILING_FANS = {
    "caleb_office": "fan.caleb_office_ceiling",
    "tia_office": "fan.tia_office_ceiling_fan",
    "family_room": "fan.fan",
}

# Attributes
ATTR_STATUS = "status"
ATTR_MODE = "mode"
ATTR_SEASON = "season"
ATTR_THERMAL_REQUEST = "thermal_request"
ATTR_URGENCY = "urgency"
ATTR_REASONING = "reasoning"

# Service names
SERVICE_FORCE_EVALUATE = "force_evaluate"
SERVICE_SET_MANUAL_OVERRIDE = "set_manual_override"

# ===== CONFIG FLOW KEYS =====

# System (global) — Identity & sensors
CONF_THERMOSTAT = "thermostat_entity"
CONF_WEATHER = "weather_entity"
CONF_SOLAR = "solar_entity"
CONF_SLEEP_POSTURE = "sleep_posture_entity"
CONF_OCCUPANCY = "occupancy_entities"

# System — AC control
CONF_AC_ENABLED = "ac_enabled"
CONF_AC_SETPOINT = "ac_setpoint"
CONF_AC_TRIGGER_SOLAR_WATTS = "ac_trigger_solar_watts"
CONF_AC_SOLAR_WINDOW_START = "ac_solar_window_start"
CONF_AC_SOLAR_WINDOW_END = "ac_solar_window_end"
CONF_AC_TRIGGER_HUMIDITY = "ac_trigger_humidity"

# System — Heating (global, not per-zone)
CONF_HEAT_THRESHOLD = "heat_threshold"
CONF_HEAT_SETPOINT = "heat_setpoint"
CONF_EMERGENCY_HEAT_THRESHOLD = "emergency_heat_threshold"

# System — Setback & occupancy
CONF_SETBACK_COOL_TEMP = "setback_cool_temp"
CONF_SETBACK_HEAT_TEMP = "setback_heat_temp"
CONF_UNOCCUPIED_HOURS = "unoccupied_hours"
CONF_RETURN_HOME_COOL_SETPOINT = "return_home_cool_setpoint"
CONF_RETURN_HOME_HEAT_SETPOINT = "return_home_heat_setpoint"

# System — Forecast & pre-conditioning
CONF_PRECOOL_TRIGGER = "precool_trigger"
CONF_PREHEAT_TRIGGER = "preheat_trigger"

# System — Windows & passive cooling
CONF_WINDOWS_ASSUMED_OPEN_SENSOR = "windows_assumed_open_sensor"
CONF_WINDOW_FAN_SPEED = "window_fan_speed"
CONF_PASSIVE_COOLING_ENABLED = "passive_cooling_enabled"

# System — Season calendar dates (v0.2.19)
CONF_WINTER_START_MONTH = "winter_start_month"
CONF_WINTER_END_MONTH = "winter_end_month"
CONF_SUMMER_START_MONTH = "summer_start_month"
CONF_SUMMER_END_MONTH = "summer_end_month"

# System — AC/Heat gating thresholds (v0.2.19)
CONF_COOL_EXTERIOR_THRESHOLD = "cool_exterior_threshold"
CONF_COOL_INTERIOR_THRESHOLD = "cool_interior_threshold"
CONF_HEAT_EXTERIOR_THRESHOLD = "heat_exterior_threshold"
CONF_HEAT_INTERIOR_THRESHOLD = "heat_interior_threshold"

# System — Fan pool definition
CONF_WHOLE_HOUSE_FAN_ENTITY = "whole_house_fan_entity"
CONF_FAN_POOL = "fan_pool"  # List of {id, entity_id, label}

# Zone (room) — Identity
CONF_ZONE_NAME = "zone_name"
CONF_FLOOR = "floor"
CONF_IS_PRIMARY_ZONE = "is_primary_zone"
CONF_AUTO_CONTROL_ENABLED = "auto_control_enabled"  # Default for auto-control switch

# Zone — Sensors
CONF_TEMP_SENSORS = "temp_sensors"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_WINDOW_SENSOR = "window_sensor"
CONF_ZONE_OCCUPANCY = "zone_occupancy_sensor"

# Zone — Cooling thresholds (per-room)
CONF_COMFORT_UPPER = "comfort_upper"
CONF_PASSIVE_THRESHOLD = "passive_threshold"
CONF_PASSIVE_HUMID_THRESHOLD = "passive_humid_threshold"
CONF_ESCALATE_THRESHOLD = "escalate_threshold"
CONF_EMERGENCY_THRESHOLD = "emergency_threshold"

# Zone — Fan configuration
CONF_FAN_CONFIG = "fan_config"  # JSON list of fan entries
