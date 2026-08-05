"""Read-only public VARTA pulse sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import REGISTERS, RegisterDefinition
from .coordinator import VartaPulseCoordinator
from .entity import VartaPulseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create entities for documented VARTA pulse data points."""
    coordinator: VartaPulseCoordinator = entry.runtime_data
    async_add_entities(
        VartaPulseSensor(coordinator, entry, register) for register in REGISTERS
    )


class VartaPulseSensor(VartaPulseEntity, SensorEntity):
    """One VARTA pulse read-only sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: VartaPulseCoordinator,
        entry: ConfigEntry,
        register: RegisterDefinition,
    ) -> None:
        super().__init__(coordinator, entry)
        self._register = register
        self.entity_description = SensorEntityDescription(
            key=register.key,
            translation_key=register.key,
            native_unit_of_measurement=register.unit,
            device_class=register.device_class,
            state_class=register.state_class,
            icon=register.icon,
        )
        self._attr_unique_id = f"{entry.entry_id}_{register.key}"
        if register.key in {"battery_power", "grid_power"}:
            self._attr_suggested_unit_of_measurement = UnitOfPower.WATT

    @property
    def available(self) -> bool:
        """Only expose values that have passed conservative plausibility checks."""
        item = self.coordinator.data.get(self._register.key)
        return super().available and item is not None and item.plausible

    @property
    def native_value(self) -> int | float | str | None:
        """Return decoded public register value."""
        item = self.coordinator.data.get(self._register.key)
        return item.value if item and item.plausible else None

    @property
    def extra_state_attributes(self) -> dict[str, int | bool]:
        """Retain the raw read-only evidence for diagnostics."""
        item = self.coordinator.data.get(self._register.key)
        return {
            "register": self._register.address,
            "raw_value": item.raw_value if item else 0,
            "plausible": item.plausible if item else False,
            "modbus_function": 3,
            "read_only": True,
        }
