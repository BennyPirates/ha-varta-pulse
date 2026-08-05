"""Data coordinator for VARTA pulse."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VartaPulseClient, VartaPulseError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .registers import VartaValue

_LOGGER = logging.getLogger(__name__)


class VartaPulseCoordinator(DataUpdateCoordinator[dict[str, VartaValue]]):
    """Collect public VARTA data through one rate-limited client."""

    def __init__(self, hass: HomeAssistant, client: VartaPulseClient) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, VartaValue]:
        try:
            return await self.hass.async_add_executor_job(self.client.read_all)
        except VartaPulseError as error:
            raise UpdateFailed(str(error)) from error
