"""Adaptive HVAC integration."""

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, ENTRY_TYPE_SYSTEM, ENTRY_TYPE_ZONE
from .coordinator import ZoneCoordinator, SystemCoordinator
from .dashboard import build_dashboard

DEFAULT_DASHBOARD = "dashboard-hvac"

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final[list[str]] = ["sensor", "switch", "number", "select", "binary_sensor"]


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

            await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch", "number", "select", "binary_sensor"])
            _register_services(hass, coordinator)

        elif entry_type == ENTRY_TYPE_ZONE:
            zone_name = entry.data.get("zone_name", "Zone")
            zone_config = {**entry.data, **entry.options}
            coordinator = ZoneCoordinator(hass, zone_name, zone_config, config_entry=entry)
            hass.data[DOMAIN][entry.entry_id] = coordinator

            # Fan lock: listen for user-initiated changes on zone fans
            fans = zone_config.get("fans", [])
            if fans:
                unsub = async_track_state_change_event(hass, fans, coordinator._handle_fan_change)
                entry.async_on_unload(unsub)

            # Fan lock: midnight reset
            unsub = async_track_time_change(hass, coordinator._midnight_reset, hour=0, minute=0, second=0)
            entry.async_on_unload(unsub)

            # Platform setup first — FanLockedSwitch.async_added_to_hass restores
            # _fan_locked from persisted state before the first coordinator evaluation runs
            await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch", "number"])
            await coordinator.async_config_entry_first_refresh()
            # The system entry usually finishes setup before the zones; without this its status reads
            # "No zone data available" until the next scheduled refresh (~3 min after every HA start).
            _request_system_refresh(hass)

        if entry_type == ENTRY_TYPE_SYSTEM:
            # Wrap the reload listener so setpoint adoptions don't trigger a full reload
            async def _options_updated(h: HomeAssistant, e: ConfigEntry) -> None:
                coord = h.data.get(DOMAIN, {}).get(e.entry_id)
                if coord is not None and getattr(coord, "_suppress_setpoint_reload", False):
                    coord._suppress_setpoint_reload = False
                    return
                await async_reload_entry(h, e)
            entry.async_on_unload(entry.add_update_listener(_options_updated))
        else:
            entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        return True

    except Exception as e:
        _LOGGER.error(f"Error setting up Adaptive HVAC entry {entry.entry_id}: {e}", exc_info=True)
        raise


def _request_system_refresh(hass: HomeAssistant) -> None:
    """Ask the system coordinator (if already set up) to re-aggregate; its debouncer coalesces zone bursts."""
    for e in hass.config_entries.async_entries(DOMAIN):
        coord = hass.data.get(DOMAIN, {}).get(e.entry_id)
        if e.data.get("entry_type") == ENTRY_TYPE_SYSTEM and coord is not None:
            hass.async_create_task(coord.async_request_refresh())


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

    async def rebuild_dashboard(call):
        await async_rebuild_dashboard(hass, coordinator, call.data.get("dashboard", DEFAULT_DASHBOARD))

    hass.services.async_register(DOMAIN, "force_evaluate", force_evaluate)
    hass.services.async_register(DOMAIN, "set_manual_override", set_manual_override)
    hass.services.async_register(DOMAIN, "rebuild_dashboard", rebuild_dashboard)


def _strip_prefix(unique_id: str, *prefixes: str) -> str:
    for p in prefixes:
        if unique_id.startswith(p):
            return unique_id[len(p):]
    return unique_id


async def async_rebuild_dashboard(hass: HomeAssistant, coordinator: SystemCoordinator, url_path: str) -> None:
    """Build the HVAC dashboard from live config + entity registry and save it to a storage dashboard.

    Saving through lovelace (not by writing .storage) updates HA's in-memory copy and notifies open
    frontends, so the new layout shows up on refresh — no HA restart.
    """
    registry = er.async_get(hass)
    lovelace = hass.data.get("lovelace")
    dashboards = getattr(lovelace, "dashboards", None)
    if dashboards is None and isinstance(lovelace, dict):
        dashboards = lovelace.get("dashboards")
    target = (dashboards or {}).get(url_path)
    if target is None or not hasattr(target, "async_save") or getattr(target, "mode", "storage") != "storage":
        raise HomeAssistantError(
            f"No UI-managed dashboard at '/{url_path}'. Create one (Settings → Dashboards → Add, "
            f"URL '{url_path}') and run this again."
        )

    system_ids: dict[str, str] = {}
    zones: list[dict] = []
    system_cfg: dict = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        cfg = {**entry.data, **entry.options}
        ids = {
            _strip_prefix(e.unique_id, f"{DOMAIN}_", f"{coordinator.name}_"): e.entity_id
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        if cfg.get("entry_type") == ENTRY_TYPE_SYSTEM:
            system_ids, system_cfg = ids, cfg
        elif cfg.get("entry_type") == ENTRY_TYPE_ZONE:
            by_suffix = {
                suffix: next((eid for uid, eid in ids.items() if uid.endswith(f"_{suffix}")), None)
                for suffix in ("status", "target_temp", "auto", "fan_locked")
            }
            if not all(by_suffix.values()):
                _LOGGER.warning("Adaptive HVAC dashboard: skipping zone %s, entities missing: %s", entry.title, by_suffix)
                continue
            zones.append({
                "title": entry.title,
                "status": by_suffix["status"],
                "target": by_suffix["target_temp"],
                "auto": by_suffix["auto"],
                "fan_locked": by_suffix["fan_locked"],
                "temp_sensor": (cfg.get("temp_sensors") or [None])[0],
                "fans": cfg.get("fans", []),
            })

    thermostat = system_cfg.get("thermostat_entity", "climate.downstairs_thermostat")
    outdoor = system_cfg.get("outdoor_temp_sensor") or system_cfg.get("weather_entity", "weather.home")
    fan_state = "sensor.thermostat_fan_state" if hass.states.get("sensor.thermostat_fan_state") else None
    config = build_dashboard(zones, system_ids, thermostat, outdoor, fan_state, url_path)
    await target.async_save(config)
    _LOGGER.info("Adaptive HVAC: rebuilt dashboard /%s (%d zones)", url_path, len(zones))
