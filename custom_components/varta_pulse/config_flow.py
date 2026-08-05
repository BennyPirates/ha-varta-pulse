"""Config flow for VARTA pulse."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import VartaPulseClient, VartaPulseError
from .const import CONF_UNIT_ID, DEFAULT_PORT, DEFAULT_TIMEOUT, DEFAULT_UNIT_ID, DOMAIN


class VartaPulseConfigFlow(  # type: ignore[call-arg]
    config_entries.ConfigFlow, domain=DOMAIN
):
    """Handle a VARTA pulse config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the first setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_UNIT_ID]}"
            )
            self._abort_if_unique_id_configured()
            client = VartaPulseClient(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_UNIT_ID],
                DEFAULT_TIMEOUT,
            )
            try:
                firmware = await self.hass.async_add_executor_job(client.read_identity)
            except VartaPulseError:
                errors["base"] = "cannot_connect"
            except Exception:  # Do not expose low-level library errors in the UI.
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"VARTA pulse ({firmware})", data=user_input
                )
            finally:
                client.close()
        return self.async_show_form(
            step_id="user", data_schema=self._schema(), errors=errors
        )

    @staticmethod
    @callback
    def _schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=255)
                ),
            }
        )
