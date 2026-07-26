"""Constants for the Adaptive HVAC integration."""

DOMAIN = "adaptive_hvac"

# Entry types
ENTRY_TYPE_SYSTEM = "system"
ENTRY_TYPE_ZONE = "zone"

# State machine modes (v0.3.0 simplified)
MODE_MANUAL_OVERRIDE = "manual_override"
MODE_SYSTEM_INACTIVE = "system_inactive"
MODE_SENSOR_FAILSAFE = "sensor_failsafe"
MODE_EMERGENCY_COOLING = "emergency_cooling"
MODE_EMERGENCY_HEATING = "emergency_heating"
MODE_COOLING = "cooling"
MODE_PASSIVE_COOLING = "passive_cooling"
MODE_IDLE_WARM = "idle_warm"
MODE_HEATING = "heating"
MODE_PASSIVE_HEATING = "passive_heating"
MODE_IDLE_COLD = "idle_cold"
MODE_IDLE = "idle"

ALL_MODES = [
    MODE_MANUAL_OVERRIDE,
    MODE_SYSTEM_INACTIVE,
    MODE_SENSOR_FAILSAFE,
    MODE_EMERGENCY_COOLING,
    MODE_EMERGENCY_HEATING,
    MODE_COOLING,
    MODE_PASSIVE_COOLING,
    MODE_IDLE_WARM,
    MODE_HEATING,
    MODE_PASSIVE_HEATING,
    MODE_IDLE_COLD,
    MODE_IDLE,
]

# Seasons
SEASON_SUMMER = "summer"
SEASON_WINTER = "winter"

ALL_SEASONS = [SEASON_SUMMER, SEASON_WINTER]

# Poll interval (minutes)
SCAN_INTERVAL_MINUTES = 3

# ===== DEFAULTS (SYSTEM) =====

# System — AC control
DEFAULT_AC_SETPOINT = 68.0

# System — Heating
DEFAULT_HEAT_THRESHOLD = 68.0
DEFAULT_HEAT_SETPOINT = 68.0
DEFAULT_EMERGENCY_HEAT_THRESHOLD = 55.0

# System — Cooling emergency
DEFAULT_EMERGENCY_COOL_THRESHOLD = 85.0

# System — Season gating thresholds (v0.3.0)
# AC: don't run if exterior below this — unless interior override kicks in
DEFAULT_COOL_EXTERIOR_THRESHOLD = 60.0   # °F (lowered from 70°F in v0.2.x)
# Interior override: if any zone is this many degrees above its target, bypass exterior threshold
DEFAULT_COOL_INTERIOR_OVERRIDE_DELTA = 5.0  # °F
# Heat: don't run if exterior above this
DEFAULT_HEAT_EXTERIOR_THRESHOLD = 60.0   # °F

# System — Season calendar dates
DEFAULT_WINTER_START_MONTH = 10  # October
DEFAULT_WINTER_END_MONTH = 4     # April

# System — Upstairs demand boost: lower AC setpoint by this many °F when zones request cooling
DEFAULT_UPSTAIRS_DEMAND_BOOST = 1.0  # °F

# System — Floor circulation: run thermostat fan when floor temp differential exceeds this
DEFAULT_FAN_CIRCULATION_DELTA = 2.0  # °F
CONF_FAN_CIRCULATION_DELTA = "fan_circulation_delta"

# System — Whole-house fan entity (thermostat fan mode)
DEFAULT_WHOLE_HOUSE_FAN_ENTITY = "climate.downstairs_thermostat"

# System — Night mode: separate setpoints used while night mode is active
DEFAULT_NIGHT_AC_SETPOINT = 70.0   # °F
DEFAULT_NIGHT_HEAT_SETPOINT = 66.0  # °F
CONF_NIGHT_AC_SETPOINT = "night_ac_setpoint"
CONF_NIGHT_HEAT_SETPOINT = "night_heat_setpoint"

# System — Night mode: time window (used when no manual toggle / source entity is on)
DEFAULT_NIGHT_START_HOUR = 22  # 10pm
DEFAULT_NIGHT_END_HOUR = 6     # 6am
CONF_NIGHT_START_HOUR = "night_start_hour"
CONF_NIGHT_END_HOUR = "night_end_hour"

# System — Night mode: optional external boolean that also activates night mode when "on"
CONF_NIGHT_MODE_SOURCE_ENTITY = "night_mode_source_entity"

# ===== DEFAULTS (ZONE) =====

# Zone — Target temp (single threshold: fan on above this, fan off at/below)
DEFAULT_ZONE_TARGET_TEMP = 72.0  # °F

# Zone — Fan speed when running
DEFAULT_FAN_SPEED = 50  # %

# Zone — Flags
DEFAULT_IS_PRIMARY_ZONE = False
DEFAULT_AUTO_CONTROL_ENABLED = True

# ===== CONFIG FLOW KEYS =====

# System — Identity & sensors
CONF_THERMOSTAT = "thermostat_entity"
CONF_WEATHER = "weather_entity"
CONF_OUTDOOR_TEMP_SENSOR = "outdoor_temp_sensor"
# System — AC control
CONF_AC_SETPOINT = "ac_setpoint"

# System — Heating
CONF_HEAT_THRESHOLD = "heat_threshold"
CONF_HEAT_SETPOINT = "heat_setpoint"
CONF_EMERGENCY_HEAT_THRESHOLD = "emergency_heat_threshold"

# System — Cooling emergency
CONF_EMERGENCY_COOL_THRESHOLD = "emergency_cool_threshold"

# System — Gating thresholds (v0.3.0)
CONF_COOL_EXTERIOR_THRESHOLD = "cool_exterior_threshold"
CONF_COOL_INTERIOR_OVERRIDE_DELTA = "cool_interior_override_delta"
CONF_HEAT_EXTERIOR_THRESHOLD = "heat_exterior_threshold"

# System — Season calendar
CONF_WINTER_START_MONTH = "winter_start_month"
CONF_WINTER_END_MONTH = "winter_end_month"

# Zone — Identity
CONF_ZONE_NAME = "zone_name"
CONF_FLOOR = "floor"
CONF_IS_PRIMARY_ZONE = "is_primary_zone"
CONF_AUTO_CONTROL_ENABLED = "auto_control_enabled"

# Zone — Sensors
CONF_TEMP_SENSORS = "temp_sensors"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_WINDOW_SENSOR = "window_sensor"
CONF_ZONE_OCCUPANCY = "zone_occupancy_sensor"

# Zone — Target and fan
CONF_ZONE_TARGET_TEMP = "zone_target_temp"
CONF_FAN_SPEED = "fan_speed"
CONF_AFFECTS_THERMOSTAT = "affects_thermostat"

# Zone — Flags
DEFAULT_AFFECTS_THERMOSTAT = True

# Attributes
ATTR_STATUS = "status"
ATTR_MODE = "mode"
ATTR_SEASON = "season"
ATTR_THERMAL_REQUEST = "thermal_request"
ATTR_REASONING = "reasoning"

# Service names
SERVICE_FORCE_EVALUATE = "force_evaluate"
SERVICE_SET_MANUAL_OVERRIDE = "set_manual_override"
