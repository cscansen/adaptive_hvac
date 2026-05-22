"""Select entities for Adaptive HVAC."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTRY_TYPE_SYSTEM, ALL_SEASONS
from .coordinator import SystemCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    if entry.data.get("entry_type") != ENTRY_TYPE_SYSTEM:
        return

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        SeasonOverrideSelect(coordinator),
    ]
    async_add_entities(entities)


class SeasonOverrideSelect(CoordinatorEntity, SelectEntity):
    """Select entity for season override."""

    def __init__(self, coordinator: SystemCoordinator):
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_season_override"
        self._attr_name = "Adaptive HVAC Season Override"
        self._attr_options = ["auto", "summer", "shoulder", "winter"]

    @property
    def current_option(self) -> str:
        """Return current season override."""
        return self.coordinator.system_config.get("season_override", "auto")

    async def async_select_option(self, option: str) -> None:
        """Update season override."""
        self.coordinator.system_config["season_override"] = option
        self.async_write_ha_state()
        await self.coordinator.async_refresh()
