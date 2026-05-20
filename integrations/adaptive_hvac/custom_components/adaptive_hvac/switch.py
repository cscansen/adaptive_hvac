"""Switches for Adaptive HVAC."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTRY_TYPE_SYSTEM
from .coordinator import SystemCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    if entry.data.get("entry_type") != ENTRY_TYPE_SYSTEM:
        return

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        SystemActiveSwitch(coordinator),
        ManualOverrideSwitch(coordinator),
    ]
    async_add_entities(entities)


class SystemActiveSwitch(CoordinatorEntity, SwitchEntity):
    """Master switch to enable/disable the integration."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.name}_active"
        self._attr_name = "Adaptive HVAC Active"

    @property
    def is_on(self) -> bool:
        """Return if system is active."""
        return self.coordinator.system_config.get("system_active", True)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the system."""
        self.coordinator.system_config["system_active"] = True
        self.async_write_ha_state()
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the system."""
        self.coordinator.system_config["system_active"] = False
        self.async_write_ha_state()
        await self.coordinator.async_refresh()


class ManualOverrideSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to manually override all HVAC automation."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.name}_manual_override"
        self._attr_name = "Adaptive HVAC Manual Override"

    @property
    def is_on(self) -> bool:
        """Return if manual override is active."""
        return self.coordinator.system_config.get("manual_override", False)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on manual override."""
        self.coordinator.system_config["manual_override"] = True
        self.async_write_ha_state()
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off manual override."""
        self.coordinator.system_config["manual_override"] = False
        self.async_write_ha_state()
        await self.coordinator.async_refresh()
