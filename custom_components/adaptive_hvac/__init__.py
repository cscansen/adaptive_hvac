"""Adaptive HVAC integration."""

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, ENTRY_TYPE_SYSTEM, ENTRY_TYPE_ZONE
from .coordinator import ZoneCoordinator, SystemCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final[list[str]] = ["sensor", "switch", "number", "select"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Adaptive HVAC integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Adaptive HVAC from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    entry_type = entry.data.get("entry_type")

    try:
        if entry_type == ENTRY_TYPE_SYSTEM:
            # Set up system entry
            coordinator = SystemCoordinator(hass, entry.data, [])
            hass.data[DOMAIN][entry.entry_id] = coordinator

            # Discover and register zone coordinators
            zone_coordinators = [
                hass.data[DOMAIN][zone_entry.entry_id]
                for zone_entry in hass.config_entries.async_entries(DOMAIN)
                if zone_entry.data.get("entry_type") == ENTRY_TYPE_ZONE
                and zone_entry.entry_id in hass.data[DOMAIN]
            ]
            coordinator.zone_coordinators = zone_coordinators
            _LOGGER.info(f"Registered {len(zone_coordinators)} zone coordinator(s) with system")

            await coordinator.async_config_entry_first_refresh()

            # Forward to platforms
            await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch"])

            # Register services
            _register_services(hass, coordinator)

        elif entry_type == ENTRY_TYPE_ZONE:
            # Set up zone entry
            zone_name = entry.data.get("zone_name", "Zone")
            zone_config = {**entry.data, **entry.options}
            _LOGGER.info(f"Setting up zone: {zone_name} (entry_id: {entry.entry_id})")
            coordinator = ZoneCoordinator(hass, zone_name, zone_config)
            _LOGGER.debug(f"ZoneCoordinator created for {zone_name}")
            await coordinator.async_config_entry_first_refresh()
            hass.data[DOMAIN][entry.entry_id] = coordinator
            _LOGGER.info(f"ZoneCoordinator {zone_name} stored in hass.data[{DOMAIN}][{entry.entry_id}]")

            # Forward to platforms
            _LOGGER.info(f"Forwarding zone {zone_name} to sensor and switch platforms")
            try:
                await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch"])
                _LOGGER.info(f"Successfully forwarded zone {zone_name} to platforms")
            except Exception as e:
                _LOGGER.error(f"Failed to forward zone {zone_name} to platforms: {e}", exc_info=True)
                raise

        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        return True
    except Exception as e:
        _LOGGER.error(f"Error setting up Adaptive HVAC entry {entry.entry_id}: {e}", exc_info=True)
        raise


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


def _register_services(hass: HomeAssistant, coordinator: SystemCoordinator):
    """Register services."""

    async def force_evaluate_service(call):
        """Force immediate evaluation."""
        await coordinator.async_refresh()
        _LOGGER.info("Adaptive HVAC force evaluation completed")

    async def set_manual_override_service(call):
        """Set manual override."""
        manual_override = call.data.get("manual_override", False)
        coordinator.system_config["manual_override"] = manual_override
        await coordinator.async_refresh()
        _LOGGER.info(f"Adaptive HVAC manual override set to {manual_override}")

    hass.services.async_register(
        DOMAIN,
        "force_evaluate",
        force_evaluate_service,
    )

    hass.services.async_register(
        DOMAIN,
        "set_manual_override",
        set_manual_override_service,
    )
