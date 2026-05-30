"""Adaptive HVAC integration."""

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, ENTRY_TYPE_SYSTEM, ENTRY_TYPE_ZONE
from .coordinator import ZoneCoordinator, SystemCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final[list[str]] = ["sensor", "switch", "number", "select"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Adaptive HVAC from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    entry_type = entry.data.get("entry_type")

    try:
        if entry_type == ENTRY_TYPE_SYSTEM:
            coordinator = SystemCoordinator(hass, {**entry.data, **entry.options}, [], entry)
            hass.data[DOMAIN][entry.entry_id] = coordinator
            await coordinator.async_config_entry_first_refresh()

            # Listen for thermostat setpoint changes made by the user
            thermostat = entry.data.get("thermostat_entity")
            if thermostat:
                unsub = async_track_state_change_event(
                    hass, [thermostat], coordinator.handle_thermostat_state_change
                )
                entry.async_on_unload(unsub)

            await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch", "number", "select"])
            _register_services(hass, coordinator)

        elif entry_type == ENTRY_TYPE_ZONE:
            zone_name = entry.data.get("zone_name", "Zone")
            zone_config = {**entry.data, **entry.options}
            coordinator = ZoneCoordinator(hass, zone_name, zone_config, config_entry=entry)
            hass.data[DOMAIN][entry.entry_id] = coordinator
            await coordinator.async_config_entry_first_refresh()

            # Fan lock: listen for user-initiated changes on zone fans
            fans = zone_config.get("fans", [])
            if fans:
                unsub = async_track_state_change_event(hass, fans, coordinator._handle_fan_change)
                entry.async_on_unload(unsub)

            # Fan lock: midnight reset
            unsub = async_track_time_change(hass, coordinator._midnight_reset, hour=0, minute=0, second=0)
            entry.async_on_unload(unsub)

            await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch"])

        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        return True

    except Exception as e:
        _LOGGER.error(f"Error setting up Adaptive HVAC entry {entry.entry_id}: {e}", exc_info=True)
        raise


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant, coordinator: SystemCoordinator) -> None:
    async def force_evaluate(call):
        await coordinator.async_refresh()
        _LOGGER.info("Adaptive HVAC: force evaluation complete")

    async def set_manual_override(call):
        coordinator.system_config["manual_override"] = call.data.get("manual_override", False)
        await coordinator.async_refresh()

    hass.services.async_register(DOMAIN, "force_evaluate", force_evaluate)
    hass.services.async_register(DOMAIN, "set_manual_override", set_manual_override)
