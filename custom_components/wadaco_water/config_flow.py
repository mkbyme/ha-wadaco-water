"""Config flow for Wadaco Nước Sạch integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from . import wadaco_water
from .const import (
    CONF_CUSTOMER_CODE,
    CONF_ERR_UNKNOWN,
    CONF_ORG_CODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SUCCESS,
    DEFAULT_ORG_CODE,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    ORG_CODE_LABELS,
)

_LOGGER = logging.getLogger(__name__)

_ORG_CODE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=code, label=label)
            for code, label in ORG_CODE_LABELS.items()
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
        custom_value=True,
    )
)

_SETUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ORG_CODE, default=DEFAULT_ORG_CODE): _ORG_CODE_SELECTOR,
        vol.Required(CONF_CUSTOMER_CODE): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_HOURS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=48)
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Wadaco Nước Sạch."""

    VERSION = 1

    def __init__(self):
        self._errors = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Single setup step: org code + customer code + password + scan interval.

        The branch code (org_code) is picked from a dropdown (custom values
        allowed) instead of being derived from the login response - the
        login username sent to the API is `<org_code>_<customer_code>`.
        """
        self._errors = {}

        if user_input is not None:
            org_code = user_input[CONF_ORG_CODE].strip()
            customer_code = user_input[CONF_CUSTOMER_CODE].strip()
            password = user_input[CONF_PASSWORD]
            scan_interval = user_input[CONF_SCAN_INTERVAL]

            api = wadaco_water.WadacoAPI(self.hass, True)

            try:
                login_result = await api.login(org_code, customer_code, password)
            except Exception as e:
                _LOGGER.exception("Unexpected login error: %s", e)
                login_result = {"status": CONF_ERR_UNKNOWN}

            status = login_result.get("status")
            if status != CONF_SUCCESS:
                self._errors["base"] = status
            else:
                unique_id = f"{org_code}_{customer_code}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=customer_code,
                    data={
                        CONF_ORG_CODE: org_code,
                        CONF_CUSTOMER_CODE: customer_code,
                        CONF_PASSWORD: password,
                        CONF_SCAN_INTERVAL: scan_interval,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_SETUP_SCHEMA,
            errors=self._errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow to change scan interval after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=48)
                    ),
                }
            ),
        )
