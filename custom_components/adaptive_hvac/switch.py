"""Switches for Adaptive HVAC."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTRY_TYPE_SYSTEM, ENTRY_TYPE_ZONE, CONF_AUTO_CONTROL_ENABLED, DEFAULT_AUTO_CONTROL_ENABLED
from .coordinator import SystemCoordinator, ZoneCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    entry_type = entry.data.get("entry_type")

    if entry_type == ENTRY_TYPE_SYSTEM:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        entities = [
            SystemActiveSwitch(coordinator),
            ManualOverrideSwitch(coordinator),
        ]
        async_add_entities(entities)
    elif entry_type == ENTRY_TYPE_ZONE:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        zone_name = entry.data.get("zone_name", "Zone")
        entities = [
            ZoneAutoControlSwitch(hass, coordinator, zone_name, entry),
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


class ZoneAutoControlSwitch(RestoreEntity, SwitchEntity):
    """Switch for per-zone automatic fan control."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ZoneCoordinator,
        zone_name: str,
        config_entry: ConfigEntry,
    ):
        """Initialize zone auto-control switch."""
        self.hass = hass
        self.coordinator = coordinator
        self.zone_name = zone_name
        self.config_entry = config_entry
        self._attr_has_entity_name = True
        self._attr_name = "Auto Control"

        # Entity ID: switch.adaptive_hvac_{zone_slug}_auto
        zone_slug = zone_name.lower().replace(" ", "_")
        self._attr_unique_id = f"{DOMAIN}_{zone_slug}_auto"
        self.entity_id = f"switch.{DOMAIN}_{zone_slug}_auto"

        # Initial state from config, with fallback to default
        self._state = config_entry.data.get(
            CONF_AUTO_CONTROL_ENABLED, DEFAULT_AUTO_CONTROL_ENABLED
        )

    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._state = last_state.state == "on"
        else:
            # Use config entry default if no prior state
            self._state = self.config_entry.data.get(
                CONF_AUTO_CONTROL_ENABLED, DEFAULT_AUTO_CONTROL_ENABLED
            )
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return if auto control is enabled."""
        return self._state

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, f"zone_{self.zone_name}")},
            "name": f"{self.zone_name} HVAC",
            "via_device": (DOMAIN, "system"),
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Enable auto control for this zone."""
        self._state = True
        self.async_write_ha_state()
        # Notify coordinator of state change for next evaluation
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable auto control for this zone."""
        self._state = False
        self.async_write_ha_state()
        # Notify coordinator of state change for next evaluation
        await self.coordinator.async_refresh()
