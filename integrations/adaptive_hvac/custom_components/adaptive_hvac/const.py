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

# Default thresholds (°F)
DEFAULT_COMFORT_UPPER = 70.0
DEFAULT_PASSIVE_THRESHOLD = 72.0
DEFAULT_ESCALATE_THRESHOLD = 74.0
DEFAULT_EMERGENCY_THRESHOLD = 78.0
DEFAULT_PASSIVE_FAN_SPEED = 33
DEFAULT_ESCALATE_FAN_SPEED = 50
DEFAULT_AC_SETPOINT = 68.0

DEFAULT_HEAT_THRESHOLD = 68.0
DEFAULT_HEAT_SETPOINT = 68.0
DEFAULT_EMERGENCY_HEAT_THRESHOLD = 55.0

DEFAULT_SETBACK_COOL_TEMP = 76.0
DEFAULT_SETBACK_HEAT_TEMP = 62.0
DEFAULT_NIGHT_SETBACK_TEMP = 62.0
DEFAULT_UNOCCUPIED_HOURS = 8

DEFAULT_PRECOOL_TRIGGER = 92.0
DEFAULT_PREHEAT_TRIGGER = 30.0

DEFAULT_SUMMER_THRESHOLD = 75.0
DEFAULT_WINTER_THRESHOLD = 40.0

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

# Option flow keys
CONF_THERMOSTAT = "thermostat_entity"
CONF_WEATHER = "weather_entity"
CONF_SOLAR = "solar_entity"
CONF_SLEEP_POSTURE = "sleep_posture_entity"
CONF_OCCUPANCY = "occupancy_entities"

CONF_ZONE_NAME = "zone_name"
CONF_FLOOR = "floor"
CONF_TEMP_SENSORS = "temp_sensors"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_CEILING_FANS = "ceiling_fans"
CONF_FAN_LOCK_ENTITIES = "fan_lock_entities"
CONF_WINDOW_SENSOR = "window_sensor"
CONF_ZONE_OCCUPANCY = "zone_occupancy_sensor"
