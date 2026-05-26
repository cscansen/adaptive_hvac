"""Sensors for Adaptive HVAC."""

import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTRY_TYPE_SYSTEM, ENTRY_TYPE_ZONE
from .coordinator import ZoneCoordinator, SystemCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    entry_type = entry.data.get("entry_type")

    # Write debug log to file for visibility
    with open("/config/adaptive_hvac_sensor_setup.log", "a") as f:
        f.write(f"[sensor.py] async_setup_entry called for {entry_type} entry {entry.entry_id}\n")

    _LOGGER.info(f"Setting up sensors for {entry_type} entry: {entry.entry_id}")

    try:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        _LOGGER.debug(f"Found coordinator in hass.data: {type(coordinator).__name__}")
        with open("/config/adaptive_hvac_sensor_setup.log", "a") as f:
            f.write(f"  -> Coordinator found: {type(coordinator).__name__}\n")
    except KeyError as e:
        _LOGGER.error(f"Coordinator NOT found in hass.data[{DOMAIN}][{entry.entry_id}]")
        with open("/config/adaptive_hvac_sensor_setup.log", "a") as f:
            f.write(f"  -> ERROR: Coordinator not in hass.data: {e}\n")
        return

    entities = []

    if entry_type == ENTRY_TYPE_SYSTEM:
        _LOGGER.info("Creating system-level sensors")
        with open("/config/adaptive_hvac_sensor_setup.log", "a") as f:
            f.write(f"  -> Creating system sensors\n")
        entities.append(SystemStatusSensor(coordinator))
        entities.append(SystemModeSensor(coordinator))
        entities.append(SeasonSensor(coordinator))
    elif entry_type == ENTRY_TYPE_ZONE:
        zone_name = entry.data.get("zone_name", "Zone")
        _LOGGER.info(f"Creating zone sensors for {zone_name}")
        with open("/config/adaptive_hvac_sensor_setup.log", "a") as f:
            f.write(f"  -> Creating zone sensors for {zone_name}\n")
        entities.append(ZoneStatusSensor(coordinator, zone_name))
        entities.append(ZoneTrendSensor(coordinator, zone_name))
    else:
        _LOGGER.warning(f"Unknown entry_type: {entry_type}")
        with open("/config/adaptive_hvac_sensor_setup.log", "a") as f:
            f.write(f"  -> Unknown entry_type: {entry_type}\n")
        return

    with open("/config/adaptive_hvac_sensor_setup.log", "a") as f:
        f.write(f"  -> Adding {len(entities)} entities\n")
    _LOGGER.info(f"Adding {len(entities)} entities for {entry.entry_id}")
    async_add_entities(entities)
    with open("/config/adaptive_hvac_sensor_setup.log", "a") as f:
        f.write(f"  -> Successfully added {len(entities)} entities\n")
    _LOGGER.info(f"Successfully added {len(entities)} entities")


class SystemStatusSensor(CoordinatorEntity, SensorEntity):
    """System-level status sensor showing full reasoning."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.name}_status"
        self._attr_name = "Adaptive HVAC Status"

    @property
    def native_value(self) -> str:
        """Return status string with reasoning."""
        decision = self.coordinator.last_decision
        if not decision:
            return "Initializing..."

        return decision.status

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        decision = self.coordinator.last_decision
        if not decision:
            return {}

        return {
            "thermostat_mode": decision.thermostat_hvac_mode,
            "thermostat_setpoint": decision.thermostat_setpoint,
            "whole_house_fan": decision.whole_house_fan_mode,
            "season": decision.season,
            "reasoning": " | ".join(decision.reasoning),
        }


class SystemModeSensor(CoordinatorEntity, SensorEntity):
    """Current system HVAC mode."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.name}_mode"
        self._attr_name = "Adaptive HVAC Mode"

    @property
    def native_value(self) -> str:
        """Return current thermostat mode."""
        decision = self.coordinator.last_decision
        if not decision:
            return "unknown"

        return decision.thermostat_hvac_mode


class SeasonSensor(CoordinatorEntity, SensorEntity):
    """Current season (summer, shoulder, winter)."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.name}_season"
        self._attr_name = "Adaptive HVAC Season"

    @property
    def native_value(self) -> str:
        """Return current season."""
        decision = self.coordinator.last_decision
        if not decision:
            return "shoulder"

        return decision.season


class ZoneStatusSensor(CoordinatorEntity, SensorEntity):
    """Zone-level status sensor."""

    def __init__(self, coordinator: ZoneCoordinator, zone_name: str):
        """Initialize."""
        super().__init__(coordinator)
        self.zone_name = zone_name
        self._attr_unique_id = f"{DOMAIN}_{zone_name}_status"
        self._attr_name = f"{zone_name} HVAC Status"

    @property
    def native_value(self) -> str:
        """Return status string."""
        decision = self.coordinator.last_decision
        if not decision:
            return "Initializing..."

        return decision.status

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        decision = self.coordinator.last_decision
        if not decision:
            return {}

        return {
            "mode": decision.mode,
            "thermal_request": decision.thermal_request,
            "urgency": decision.urgency,
            "reasoning": " | ".join(decision.reasoning),
            "fan_commands": decision.fan_commands,
        }


class ZoneTrendSensor(CoordinatorEntity, SensorEntity):
    """Zone temperature trend in °F/hr."""

    def __init__(self, coordinator: ZoneCoordinator, zone_name: str):
        """Initialize."""
        super().__init__(coordinator)
        self.zone_name = zone_name
        self._attr_unique_id = f"{DOMAIN}_{zone_name}_trend"
        self._attr_name = f"{zone_name} Temp Trend"
        self._attr_native_unit_of_measurement = "°F/h"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self) -> float:
        """Return temperature trend."""
        decision = self.coordinator.last_decision
        if not decision:
            return 0.0

        # Return trend from reasoning (simplified)
        # In full implementation, would track trend state separately
        return 0.0
