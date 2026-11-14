"""Config flow for the Logia Weather Underground relay integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers import config_validation as cv

from .const import CONF_NAME, CONF_URL, DEFAULT_NAME, DOMAIN
from .sensor import fetch_payload

try:  # Home Assistant >= 2024.4
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # pragma: no cover - older Home Assistant
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


class LogiaRelayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a Logia relay."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the URL of the payload written by the relay."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_URL])
            self._abort_if_unique_id_configured()

            payload = await self.hass.async_add_executor_job(
                fetch_payload, user_input[CONF_URL]
            )
            if payload is None:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                    data={
                        CONF_URL: user_input[CONF_URL],
                        CONF_NAME: user_input.get(CONF_NAME) or DEFAULT_NAME,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a relay configured in configuration.yaml.

        Connectivity is not checked here: an import must not fail because the
        relay happens to be offline, the sensors can recover later.
        """
        await self.async_set_unique_id(import_data[CONF_URL])
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Importing YAML configuration for %s", import_data[CONF_URL])

        return self.async_create_entry(
            title=import_data.get(CONF_NAME) or DEFAULT_NAME,
            data={
                CONF_URL: import_data[CONF_URL],
                CONF_NAME: import_data.get(CONF_NAME) or DEFAULT_NAME,
            },
        )
