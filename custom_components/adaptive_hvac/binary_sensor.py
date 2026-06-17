"""Binary sensors for Adaptive HVAC."""

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
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
    if entry.data.get("entry_type") != ENTRY_TYPE_SYSTEM:
        return
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CoolingBlockedSensor(coordinator)])


class CoolingBlockedSensor(CoordinatorEntity, BinarySensorEntity):
    """True when zones demand cooling but all gating paths are blocking AC."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: SystemCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_cooling_blocked"
        self._attr_name = "Adaptive HVAC Cooling Blocked"

    @property
    def is_on(self) -> bool:
        decision = self.coordinator.last_decision
        return bool(decision and decision.cooling_blocked)

    @property
    def extra_state_attributes(self) -> dict:
        decision = self.coordinator.last_decision
        if not decision:
            return {}
        blocked_line = next(
            (r for r in decision.reasoning if "AC BLOCKED" in r), ""
        )
        return {"reason": blocked_line, "status": decision.status}
