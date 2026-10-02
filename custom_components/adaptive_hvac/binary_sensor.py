"""Binary sensors for Adaptive HVAC."""

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTRY_TYPE_SYSTEM
from .coordinator import SystemCoordinator
from .logic import aqi_category


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if entry.data.get("entry_type") != ENTRY_TYPE_SYSTEM:
        return
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        CoolingBlockedSensor(coordinator),
        HeatingBlockedSensor(coordinator),
        WindowsRecommendedSensor(coordinator),
    ])


class _BlockedSensor(CoordinatorEntity, BinarySensorEntity):
    """True when zones demand conditioning but all gating paths are blocking it.

    Subclasses supply which decision flag to read and which reasoning marker carries
    the human-readable explanation.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    _flag_attr: str
    _marker: str

    def __init__(self, coordinator: SystemCoordinator, unique_suffix: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{unique_suffix}"
        self._attr_name = name

    @property
    def is_on(self) -> bool:
        decision = self.coordinator.last_decision
        return bool(decision and getattr(decision, self._flag_attr))

    @property
    def extra_state_attributes(self) -> dict:
        decision = self.coordinator.last_decision
        if not decision:
            return {}
        blocked_line = next(
            (r for r in decision.reasoning if self._marker in r), ""
        )
        aqi = self.coordinator.last_aqi
        # blocked_reason is a single shared field on the decision, so only surface it on
        # whichever sensor is actually blocked — otherwise the heating sensor advertises
        # a summer reason code (and vice versa) while sitting off.
        return {
            "reason": blocked_line,
            "blocked_reason": decision.blocked_reason if self.is_on else "",
            "status": decision.status,
            "aqi": aqi,
            "aqi_category": aqi_category(aqi),
            "windows_recommended": decision.windows_recommended,
        }


class CoolingBlockedSensor(_BlockedSensor):
    """Summer: zones want cooling, a gate says no."""

    _flag_attr = "cooling_blocked"
    _marker = "AC BLOCKED"

    def __init__(self, coordinator: SystemCoordinator) -> None:
        super().__init__(coordinator, "cooling_blocked", "Adaptive HVAC Cooling Blocked")


class HeatingBlockedSensor(_BlockedSensor):
    """Winter mirror: zones want heat, a gate says no."""

    _flag_attr = "heating_blocked"
    _marker = "Heat BLOCKED"

    def __init__(self, coordinator: SystemCoordinator) -> None:
        super().__init__(coordinator, "heating_blocked", "Adaptive HVAC Heating Blocked")


class WindowsRecommendedSensor(CoordinatorEntity, BinarySensorEntity):
    """Advisory: outdoor air is in the comfort band, calm, dry and clean.

    No device_class — this is a positive signal, not a problem. Deliberately
    season-independent; see logic.windows_are_recommended().
    """

    def __init__(self, coordinator: SystemCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_windows_recommended"
        self._attr_name = "Adaptive HVAC Windows Recommended"
        self._attr_icon = "mdi:window-open-variant"

    @property
    def is_on(self) -> bool:
        decision = self.coordinator.last_decision
        return bool(decision and decision.windows_recommended)

    @property
    def extra_state_attributes(self) -> dict:
        coord = self.coordinator
        aqi = coord.last_aqi
        return {
            "outdoor_temp": coord._read_outdoor_temp(),
            "aqi": aqi,
            "aqi_category": aqi_category(aqi),
            "aqi_ok": coord._aqi_ok(aqi),
            "weather_ok": coord._read_windows_openable(),
            "band_min": coord._effective_setpoint("window_min_outdoor_temp", 60.0),
            "band_max": coord._effective_setpoint("window_max_outdoor_temp", 75.0),
        }
