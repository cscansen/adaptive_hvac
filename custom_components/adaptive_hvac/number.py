"""Number entities for Adaptive HVAC thresholds."""

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ENTRY_TYPE_SYSTEM,
    DEFAULT_COMFORT_UPPER,
    DEFAULT_PASSIVE_THRESHOLD,
    DEFAULT_ESCALATE_THRESHOLD,
    DEFAULT_EMERGENCY_THRESHOLD,
    DEFAULT_PASSIVE_FAN_SPEED,
    DEFAULT_ESCALATE_FAN_SPEED,
    DEFAULT_AC_SETPOINT,
    DEFAULT_HEAT_THRESHOLD,
    DEFAULT_HEAT_SETPOINT,
    DEFAULT_EMERGENCY_HEAT_THRESHOLD,
    DEFAULT_SETBACK_COOL_TEMP,
    DEFAULT_SETBACK_HEAT_TEMP,
    DEFAULT_NIGHT_SETBACK_TEMP,
    DEFAULT_UNOCCUPIED_HOURS,
    DEFAULT_PRECOOL_TRIGGER,
    DEFAULT_PREHEAT_TRIGGER,
    DEFAULT_SUMMER_THRESHOLD,
    DEFAULT_WINTER_THRESHOLD,
)
from .coordinator import SystemCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    if entry.data.get("entry_type") != ENTRY_TYPE_SYSTEM:
        return

    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        # Cooling thresholds
        ComfortUpperNumber(coordinator),
        PassiveThresholdNumber(coordinator),
        EscalateThresholdNumber(coordinator),
        EmergencyThresholdNumber(coordinator),
        PassiveFanSpeedNumber(coordinator),
        EscalateFanSpeedNumber(coordinator),
        ACSetpointNumber(coordinator),
        # Heating thresholds
        HeatThresholdNumber(coordinator),
        HeatSetpointNumber(coordinator),
        EmergencyHeatThresholdNumber(coordinator),
        # Setbacks
        SetbackCoolTempNumber(coordinator),
        SetbackHeatTempNumber(coordinator),
        NightSetbackTempNumber(coordinator),
        UnoccupiedHoursNumber(coordinator),
        # Forecast triggers
        PrecoolTriggerNumber(coordinator),
        PreheatTriggerNumber(coordinator),
        # Season thresholds
        SummerThresholdNumber(coordinator),
        WinterThresholdNumber(coordinator),
    ]

    async_add_entities(entities)


class ComfortUpperNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Comfortable upper temperature threshold."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_comfort_upper"
        self._attr_name = "Adaptive HVAC Comfort Upper"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 60.0
        self._attr_native_max_value = 80.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("comfort_upper", DEFAULT_COMFORT_UPPER)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["comfort_upper"] = value
        self.async_write_ha_state()


class PassiveThresholdNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Passive cooling trigger threshold."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_passive_threshold"
        self._attr_name = "Adaptive HVAC Passive Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 60.0
        self._attr_native_max_value = 85.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("passive_threshold", DEFAULT_PASSIVE_THRESHOLD)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["passive_threshold"] = value
        self.async_write_ha_state()


class EscalateThresholdNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """AC escalation trigger threshold."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_escalate_threshold"
        self._attr_name = "Adaptive HVAC Escalate Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 60.0
        self._attr_native_max_value = 85.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("escalate_threshold", DEFAULT_ESCALATE_THRESHOLD)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["escalate_threshold"] = value
        self.async_write_ha_state()


class EmergencyThresholdNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Emergency cooling threshold."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_emergency_threshold"
        self._attr_name = "Adaptive HVAC Emergency Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 70.0
        self._attr_native_max_value = 110.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("emergency_threshold", DEFAULT_EMERGENCY_THRESHOLD)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["emergency_threshold"] = value
        self.async_write_ha_state()


class PassiveFanSpeedNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Fan speed for passive cooling mode."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_passive_fan_speed"
        self._attr_name = "Adaptive HVAC Passive Fan Speed"
        self._attr_native_unit_of_measurement = "%"
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 5.0

    @property
    def native_value(self) -> float:
        """Return current value."""
        return float(self.coordinator.system_config.get("passive_fan_speed", DEFAULT_PASSIVE_FAN_SPEED))

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["passive_fan_speed"] = int(value)
        self.async_write_ha_state()


class EscalateFanSpeedNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Fan speed for escalated cooling mode."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_escalate_fan_speed"
        self._attr_name = "Adaptive HVAC Escalate Fan Speed"
        self._attr_native_unit_of_measurement = "%"
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 5.0

    @property
    def native_value(self) -> float:
        """Return current value."""
        return float(self.coordinator.system_config.get("escalate_fan_speed", DEFAULT_ESCALATE_FAN_SPEED))

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["escalate_fan_speed"] = int(value)
        self.async_write_ha_state()


class ACSetpointNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """AC cooling setpoint."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_ac_setpoint"
        self._attr_name = "Adaptive HVAC AC Setpoint"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 60.0
        self._attr_native_max_value = 78.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("ac_setpoint", DEFAULT_AC_SETPOINT)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["ac_setpoint"] = value
        self.async_write_ha_state()


# Heating entities
class HeatThresholdNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Normal heating trigger threshold."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_heat_threshold"
        self._attr_name = "Adaptive HVAC Heat Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 50.0
        self._attr_native_max_value = 72.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("heat_threshold", DEFAULT_HEAT_THRESHOLD)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["heat_threshold"] = value
        self.async_write_ha_state()


class HeatSetpointNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Heat mode setpoint."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_heat_setpoint"
        self._attr_name = "Adaptive HVAC Heat Setpoint"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 55.0
        self._attr_native_max_value = 75.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("heat_setpoint", DEFAULT_HEAT_SETPOINT)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["heat_setpoint"] = value
        self.async_write_ha_state()


class EmergencyHeatThresholdNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Emergency heating threshold."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_emergency_heat_threshold"
        self._attr_name = "Adaptive HVAC Emergency Heat Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = -10.0
        self._attr_native_max_value = 50.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("emergency_heat_threshold", DEFAULT_EMERGENCY_HEAT_THRESHOLD)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["emergency_heat_threshold"] = value
        self.async_write_ha_state()


# Setback entities
class SetbackCoolTempNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Unoccupied cool setpoint."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_setback_cool_temp"
        self._attr_name = "Adaptive HVAC Setback Cool Temp"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 72.0
        self._attr_native_max_value = 85.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("setback_cool_temp", DEFAULT_SETBACK_COOL_TEMP)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["setback_cool_temp"] = value
        self.async_write_ha_state()


class SetbackHeatTempNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Unoccupied heat setpoint."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_setback_heat_temp"
        self._attr_name = "Adaptive HVAC Setback Heat Temp"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 55.0
        self._attr_native_max_value = 68.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("setback_heat_temp", DEFAULT_SETBACK_HEAT_TEMP)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["setback_heat_temp"] = value
        self.async_write_ha_state()


class NightSetbackTempNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Sleep mode setback temperature."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_night_setback_temp"
        self._attr_name = "Adaptive HVAC Night Setback Temp"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 55.0
        self._attr_native_max_value = 68.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("night_setback_temp", DEFAULT_NIGHT_SETBACK_TEMP)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["night_setback_temp"] = value
        self.async_write_ha_state()


class UnoccupiedHoursNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Hours before setback triggers."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_unoccupied_hours"
        self._attr_name = "Adaptive HVAC Unoccupied Hours"
        self._attr_native_unit_of_measurement = "h"
        self._attr_native_min_value = 1.0
        self._attr_native_max_value = 24.0
        self._attr_native_step = 0.5

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("unoccupied_hours", DEFAULT_UNOCCUPIED_HOURS)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["unoccupied_hours"] = value
        self.async_write_ha_state()


# Forecast entities
class PrecoolTriggerNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Forecast high that triggers pre-cooling."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_precool_trigger"
        self._attr_name = "Adaptive HVAC Precool Trigger"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 75.0
        self._attr_native_max_value = 110.0
        self._attr_native_step = 1.0

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("precool_trigger", DEFAULT_PRECOOL_TRIGGER)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["precool_trigger"] = value
        self.async_write_ha_state()


class PreheatTriggerNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Forecast low that triggers pre-heating."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_preheat_trigger"
        self._attr_name = "Adaptive HVAC Preheat Trigger"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = -20.0
        self._attr_native_max_value = 50.0
        self._attr_native_step = 1.0

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("preheat_trigger", DEFAULT_PREHEAT_TRIGGER)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["preheat_trigger"] = value
        self.async_write_ha_state()


# Season entities
class SummerThresholdNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """7-day avg high that triggers summer."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_summer_threshold"
        self._attr_name = "Adaptive HVAC Summer Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 60.0
        self._attr_native_max_value = 90.0
        self._attr_native_step = 1.0

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("summer_threshold", DEFAULT_SUMMER_THRESHOLD)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["summer_threshold"] = value
        self.async_write_ha_state()


class WinterThresholdNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """7-day avg low that triggers winter."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_winter_threshold"
        self._attr_name = "Adaptive HVAC Winter Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = -20.0
        self._attr_native_max_value = 60.0
        self._attr_native_step = 1.0

    @property
    def native_value(self) -> float:
        """Return current value."""
        return self.coordinator.system_config.get("winter_threshold", DEFAULT_WINTER_THRESHOLD)

    async def async_set_native_value(self, value: float) -> None:
        """Update value."""
        self.coordinator.system_config["winter_threshold"] = value
        self.async_write_ha_state()
