"""VARTA pulse integration setup."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .api import VartaPulseClient, VartaPulseError
from .const import CONF_UNIT_ID, DEFAULT_TIMEOUT, PLATFORMS
from .coordinator import VartaPulseCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VARTA pulse from a config entry."""
    client = VartaPulseClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_UNIT_ID],
        DEFAULT_TIMEOUT,
    )
    coordinator = VartaPulseCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the VARTA pulse config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        client = entry.runtime_data.client
        try:
            await hass.async_add_executor_job(client.set_discharge_hold, False)
        except VartaPulseError:
            # The device watchdog releases the hold if HA cannot reach it.
            _LOGGER.warning("Could not release VARTA discharge hold during unload")
        finally:
            await hass.async_add_executor_job(client.close)
    return unloaded
