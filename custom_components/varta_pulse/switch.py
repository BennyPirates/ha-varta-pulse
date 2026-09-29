"""Opt-in discharge hold for VARTA pulse neo."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import VartaPulseCoordinator
from .entity import VartaPulseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Offer an explicitly enabled experimental control switch."""
    coordinator: VartaPulseCoordinator = entry.runtime_data
    async_add_entities([VartaDischargeHoldSwitch(coordinator, entry)])


class VartaDischargeHoldSwitch(VartaPulseEntity, SwitchEntity):
    """Keep the battery from discharging until released."""

    _attr_translation_key = "discharge_hold"
    _attr_icon = "mdi:battery-lock"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: VartaPulseCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_discharge_hold"

    @property
    def is_on(self) -> bool:
        """Return whether this integration is maintaining the hold."""
        return self.coordinator.client.discharge_hold

    async def async_turn_on(self, **kwargs: object) -> None:
        """Begin holding the current charge for later use."""
        await self.coordinator.async_set_discharge_hold(True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Restore the limit that was present before this hold."""
        await self.coordinator.async_set_discharge_hold(False)
