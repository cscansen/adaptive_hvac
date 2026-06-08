"""Number entities for Adaptive HVAC live-adjustable thresholds."""

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ENTRY_TYPE_SYSTEM,
    DEFAULT_AC_SETPOINT,
    DEFAULT_HEAT_SETPOINT,
    DEFAULT_HEAT_THRESHOLD,
    DEFAULT_EMERGENCY_HEAT_THRESHOLD,
    DEFAULT_EMERGENCY_COOL_THRESHOLD,
    DEFAULT_COOL_EXTERIOR_THRESHOLD,
    DEFAULT_UPSTAIRS_DEMAND_BOOST,
    DEFAULT_FAN_CIRCULATION_DELTA,
)
from .coordinator import SystemCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for the system entry only."""
    if entry.data.get("entry_type") != ENTRY_TYPE_SYSTEM:
        return

    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        ACSetpointNumber(coordinator),
        HeatSetpointNumber(coordinator),
        HeatThresholdNumber(coordinator),
        EmergencyHeatThresholdNumber(coordinator),
        EmergencyCoolThresholdNumber(coordinator),
        CoolExteriorThresholdNumber(coordinator),
        UpstairsDemandBoostNumber(coordinator),
        FanCirculationDeltaNumber(coordinator),
    ])


class _BaseSystemNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Base class for system-level number entities."""

    _config_key: str
    _default: float

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)

    @property
    def native_value(self) -> float:
        # Read options first so displayed value matches what _effective_setpoint dispatches.
        if self.coordinator._config_entry:
            val = self.coordinator._config_entry.options.get(self._config_key)
            if val is not None:
                return float(val)
        return float(self.coordinator.system_config.get(self._config_key, self._default))

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.system_config[self._config_key] = value
        if self.coordinator._config_entry:
            new_options = {**self.coordinator._config_entry.options, self._config_key: value}
            self.coordinator._suppress_setpoint_reload = True
            self.coordinator.hass.config_entries.async_update_entry(
                self.coordinator._config_entry, options=new_options
            )
        self.async_write_ha_state()
        await self.coordinator.async_refresh()


class ACSetpointNumber(_BaseSystemNumber):
    """AC cooling setpoint."""
    _config_key = "ac_setpoint"
    _default = DEFAULT_AC_SETPOINT

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_ac_setpoint"
        self._attr_name = "Adaptive HVAC AC Setpoint"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 60.0
        self._attr_native_max_value = 78.0
        self._attr_native_step = 1.0


class HeatSetpointNumber(_BaseSystemNumber):
    """Heat mode setpoint."""
    _config_key = "heat_setpoint"
    _default = DEFAULT_HEAT_SETPOINT

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_heat_setpoint"
        self._attr_name = "Adaptive HVAC Heat Setpoint"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 55.0
        self._attr_native_max_value = 75.0
        self._attr_native_step = 1.0


class HeatThresholdNumber(_BaseSystemNumber):
    """Zone temperature below which heating is requested (winter)."""
    _config_key = "heat_threshold"
    _default = DEFAULT_HEAT_THRESHOLD

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_heat_threshold"
        self._attr_name = "Adaptive HVAC Heat Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 50.0
        self._attr_native_max_value = 72.0
        self._attr_native_step = 1.0


class EmergencyHeatThresholdNumber(_BaseSystemNumber):
    """Emergency heating threshold — bypasses all gating."""
    _config_key = "emergency_heat_threshold"
    _default = DEFAULT_EMERGENCY_HEAT_THRESHOLD

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_emergency_heat_threshold"
        self._attr_name = "Adaptive HVAC Emergency Heat Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = -10.0
        self._attr_native_max_value = 50.0
        self._attr_native_step = 1.0


class EmergencyCoolThresholdNumber(_BaseSystemNumber):
    """Emergency cooling threshold — bypasses all gating."""
    _config_key = "emergency_cool_threshold"
    _default = DEFAULT_EMERGENCY_COOL_THRESHOLD

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_emergency_cool_threshold"
        self._attr_name = "Adaptive HVAC Emergency Cool Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 78.0
        self._attr_native_max_value = 110.0
        self._attr_native_step = 1.0


class CoolExteriorThresholdNumber(_BaseSystemNumber):
    """Minimum outdoor temp for AC to run (below this = AC blocked unless interior override)."""
    _config_key = "cool_exterior_threshold"
    _default = DEFAULT_COOL_EXTERIOR_THRESHOLD

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_cool_exterior_threshold"
        self._attr_name = "Adaptive HVAC Cool Exterior Threshold"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 40.0
        self._attr_native_max_value = 80.0
        self._attr_native_step = 1.0


class UpstairsDemandBoostNumber(_BaseSystemNumber):
    """Degrees to lower AC setpoint when upstairs zones request cooling."""
    _config_key = "upstairs_demand_boost"
    _default = DEFAULT_UPSTAIRS_DEMAND_BOOST

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_upstairs_demand_boost"
        self._attr_name = "Adaptive HVAC Upstairs Demand Boost"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 2.0
        self._attr_native_step = 0.5


class FanCirculationDeltaNumber(_BaseSystemNumber):
    """Floor temp differential that triggers whole-house fan circulation."""
    _config_key = "fan_circulation_delta"
    _default = DEFAULT_FAN_CIRCULATION_DELTA

    def __init__(self, coordinator: SystemCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_fan_circulation_delta"
        self._attr_name = "Adaptive HVAC Fan Circulation Delta"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_native_min_value = 0.5
        self._attr_native_max_value = 5.0
        self._attr_native_step = 0.5
