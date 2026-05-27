from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import callback

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT): vol.Coerce(int),
        vol.Required(CONF_TOKEN): str,
    }
)


class UpperCoastDoorlockConfigFlow(ConfigFlow, domain=DOMAIN):
    version = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            if not await self._async_check_connection(user_input):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="虚拟门禁系统", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_check_connection(self, user_input: dict[str, str]) -> bool:
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        token = user_input[CONF_TOKEN]
        url = f"http://{host}:{port}/health"

        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=aiohttp.ClientTimeout(total=5),
                )
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("ok", False)
        except Exception:
            pass
        return False


class UpperCoastDoorlockOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self.hass.config_entries.async_update_entry(self._config_entry, data=user_input)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=self._config_entry.data.get(CONF_HOST)): str,
                vol.Required(CONF_PORT, default=self._config_entry.data.get(CONF_PORT)): vol.Coerce(int),
                vol.Required(CONF_TOKEN, default=self._config_entry.data.get(CONF_TOKEN)): str,
            }),
        )