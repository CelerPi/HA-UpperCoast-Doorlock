from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant, ServiceCall

from .api import UpperCoastDoorlockClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_services(hass: HomeAssistant) -> None:
    """注册门禁服务调用。"""

    async def async_call_unlock(service: ServiceCall) -> None:
        entry_data = _get_entry_data(hass)
        if not entry_data:
            _LOGGER.warning("uppercoast_doorlock 未配置，无法执行解锁")
            return

        client: UpperCoastDoorlockClient = entry_data["client"]
        target_ip = service.data.get("target_ip")
        try:
            result = await client.async_unlock(target_ip or "")
            if result.get("ok"):
                _LOGGER.info("解锁成功: %s", target_ip)
            else:
                _LOGGER.warning("解锁失败: %s", result.get("error"))
        except Exception as exc:
            _LOGGER.error("解锁请求异常: %s", exc)

    async def async_call_answer(service: ServiceCall) -> None:
        entry_data = _get_entry_data(hass)
        if not entry_data:
            _LOGGER.warning("uppercoast_doorlock 未配置，无法执行接听")
            return

        client: UpperCoastDoorlockClient = entry_data["client"]
        target_ip = service.data.get("target_ip")
        try:
            result = await client.async_answer(target_ip or "")
            if result.get("ok"):
                _LOGGER.info("接听成功: %s", target_ip)
            else:
                _LOGGER.warning("接听失败: %s", result.get("error"))
        except Exception as exc:
            _LOGGER.error("接听请求异常: %s", exc)

    async def async_call_hangup(service: ServiceCall) -> None:
        entry_data = _get_entry_data(hass)
        if not entry_data:
            _LOGGER.warning("uppercoast_doorlock 未配置，无法执行挂断")
            return

        client: UpperCoastDoorlockClient = entry_data["client"]
        target_ip = service.data.get("target_ip")
        try:
            result = await client.async_hangup(target_ip or "")
            if result.get("ok"):
                _LOGGER.info("挂断成功: %s", target_ip)
            else:
                _LOGGER.warning("挂断失败: %s", result.get("error"))
        except Exception as exc:
            _LOGGER.error("挂断请求异常: %s", exc)

    async def async_call_monitor_start(service: ServiceCall) -> None:
        entry_data = _get_entry_data(hass)
        if not entry_data:
            _LOGGER.warning("uppercoast_doorlock 未配置，无法执行监控")
            return

        client: UpperCoastDoorlockClient = entry_data["client"]
        target_ip = service.data.get("target_ip")
        if not target_ip:
            _LOGGER.warning("监控需要指定 target_ip")
            return
        try:
            result = await client.async_monitor_start(target_ip)
            if result.get("ok"):
                _LOGGER.info("开始监控: %s", target_ip)
            else:
                _LOGGER.warning("开始监控失败: %s", result.get("error"))
        except Exception as exc:
            _LOGGER.error("开始监控请求异常: %s", exc)

    async def async_call_monitor_stop(service: ServiceCall) -> None:
        entry_data = _get_entry_data(hass)
        if not entry_data:
            _LOGGER.warning("uppercoast_doorlock 未配置，无法执行停止监控")
            return

        client: UpperCoastDoorlockClient = entry_data["client"]
        target_ip = service.data.get("target_ip")
        if not target_ip:
            _LOGGER.warning("停止监控需要指定 target_ip")
            return
        try:
            result = await client.async_monitor_stop(target_ip)
            if result.get("ok"):
                _LOGGER.info("停止监控: %s", target_ip)
            else:
                _LOGGER.warning("停止监控失败: %s", result.get("error"))
        except Exception as exc:
            _LOGGER.error("停止监控请求异常: %s", exc)

    hass.services.async_register(DOMAIN, "unlock", async_call_unlock)
    hass.services.async_register(DOMAIN, "answer", async_call_answer)
    hass.services.async_register(DOMAIN, "hangup", async_call_hangup)
    hass.services.async_register(DOMAIN, "monitor_start", async_call_monitor_start)
    hass.services.async_register(DOMAIN, "monitor_stop", async_call_monitor_stop)


def _get_entry_data(hass: HomeAssistant) -> dict[str, Any] | None:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return None
    return hass.data[DOMAIN].get(entries[0].entry_id)