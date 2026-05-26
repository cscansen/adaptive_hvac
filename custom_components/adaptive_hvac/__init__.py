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
            _LOGGER.info("System coordinator created; zones will be discovered dynamically")

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

            # IMPORTANT: Store coordinator BEFORE async operations to ensure platforms can find it
            hass.data[DOMAIN][entry.entry_id] = coordinator
            _LOGGER.info(f"ZoneCoordinator {zone_name} stored in hass.data[{DOMAIN}][{entry.entry_id}]")
            with open("/config/adaptive_hvac_setup.log", "a") as f:
                f.write(f"[__init__.py] Stored ZoneCoordinator {zone_name} for {entry.entry_id}\n")

            # Now do async initialization
            await coordinator.async_config_entry_first_refresh()
            _LOGGER.debug(f"ZoneCoordinator {zone_name} first refresh complete")
            with open("/config/adaptive_hvac_setup.log", "a") as f:
                f.write(f"[__init__.py] ZoneCoordinator first refresh complete\n")

            # Forward to platforms
            _LOGGER.info(f"Forwarding zone {zone_name} to sensor and switch platforms")
            with open("/config/adaptive_hvac_setup.log", "a") as f:
                f.write(f"[__init__.py] Forwarding zone {zone_name} to platforms\n")
            try:
                await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch"])
                _LOGGER.info(f"Successfully forwarded zone {zone_name} to platforms")
                with open("/config/adaptive_hvac_setup.log", "a") as f:
                    f.write(f"[__init__.py] Successfully forwarded zone to platforms\n")
            except Exception as e:
                _LOGGER.error(f"Failed to forward zone {zone_name} to platforms: {e}", exc_info=True)
                with open("/config/adaptive_hvac_setup.log", "a") as f:
                    f.write(f"[__init__.py] ERROR forwarding: {e}\n")
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
