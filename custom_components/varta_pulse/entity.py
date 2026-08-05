"""Shared VARTA pulse entity helpers."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VartaPulseCoordinator


class VartaPulseEntity(CoordinatorEntity[VartaPulseCoordinator]):
    """Base entity associated with one VARTA pulse device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VartaPulseCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="VARTA pulse",
            manufacturer="VARTA AG",
            model="VARTA pulse",
        )
