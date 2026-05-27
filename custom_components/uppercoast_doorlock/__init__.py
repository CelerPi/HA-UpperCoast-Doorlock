from __future__ import annotations

import logging
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .api import UpperCoastDoorlockClient
from .const import DOMAIN
from .coordinator import UpperCoastDoorlockCoordinator
from .services import setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Required(CONF_TOKEN): cv.string,
            },
            extra=vol.REMOVE_EXTRA,
        )
    },
    extra=vol.REMOVE_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    token = entry.data[CONF_TOKEN]

    client = UpperCoastDoorlockClient(host, port, token)
    coordinator = UpperCoastDoorlockCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    setup_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, ("binary_sensor", "sensor", "camera"))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_entries(hass, (entry.entry_id,))
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok