"""Sensors for Adaptive HVAC."""

import logging
from homeassistant.components.sensor import SensorEntity
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
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not coordinator:
        _LOGGER.error(f"Coordinator not found for entry {entry.entry_id}")
        return

    if entry_type == ENTRY_TYPE_SYSTEM:
        async_add_entities([
            SystemStatusSensor(coordinator),
            SystemModeSensor(coordinator),
            SeasonSensor(coordinator),
        ])
    elif entry_type == ENTRY_TYPE_ZONE:
        zone_name = entry.data.get("zone_name", "Zone")
        async_add_entities([
            ZoneStatusSensor(coordinator, zone_name),
            ZoneTrendSensor(coordinator, zone_name),
        ])


class SystemStatusSensor(CoordinatorEntity, SensorEntity):
    """System status sensor — shows current decision and reasoning."""

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.name}_status"
        self._attr_name = "Adaptive HVAC Status"

    @property
    def native_value(self) -> str:
        decision = self.coordinator.last_decision
        return decision.status if decision else "Initializing..."

    @property
    def extra_state_attributes(self) -> dict:
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
    """Current system HVAC mode (cool / heat / off)."""

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.name}_mode"
        self._attr_name = "Adaptive HVAC Mode"

    @property
    def native_value(self) -> str:
        decision = self.coordinator.last_decision
        return decision.thermostat_hvac_mode if decision else "unknown"


class SeasonSensor(CoordinatorEntity, SensorEntity):
    """Current calendar season (summer / winter)."""

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.name}_season"
        self._attr_name = "Adaptive HVAC Season"

    @property
    def native_value(self) -> str:
        decision = self.coordinator.last_decision
        if decision:
            return decision.season
        return self.coordinator.determine_calendar_season()


class ZoneStatusSensor(CoordinatorEntity, SensorEntity):
    """Zone-level status sensor."""

    def __init__(self, coordinator: ZoneCoordinator, zone_name: str):
        super().__init__(coordinator)
        self.zone_name = zone_name
        self._attr_unique_id = f"{DOMAIN}_{zone_name}_status"
        self._attr_name = f"{zone_name} HVAC Status"

    @property
    def native_value(self) -> str:
        decision = self.coordinator.last_decision
        return decision.status if decision else "Initializing..."

    @property
    def extra_state_attributes(self) -> dict:
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
        super().__init__(coordinator)
        self.zone_name = zone_name
        self._attr_unique_id = f"{DOMAIN}_{zone_name}_trend"
        self._attr_name = f"{zone_name} Temp Trend"
        self._attr_native_unit_of_measurement = "°F/h"

    @property
    def native_value(self) -> float:
        return self.coordinator._calculate_trend()
