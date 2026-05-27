from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from typing import ClassVar

from .coordinator import UpperCoastDoorlockCoordinator
from .const import DOMAIN
from homeassistant.config_entries import ConfigEntry


class UpperCoastDoorlockButtonUnlock(ButtonEntity):
    """解锁按钮。"""

    _attr_name = "门禁解锁"
    _attr_icon = "mdi:door-open"
    _attr_unique_id: ClassVar[str] = "uppercoast_doorlock_button_unlock"

    def __init__(self, coordinator: UpperCoastDoorlockCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "doorlock")},
            name="虚拟门禁系统",
            manufacturer="UpperCoast",
            model="麦驰可视对讲",
        )

    async def async_press(self) -> None:
        data = self.coordinator.data or {}
        target_ip = data.get("target_ip", "")
        if target_ip:
            client = self.coordinator._client
            await client.async_unlock(target_ip)


class UpperCoastDoorlockButtonAnswer(ButtonEntity):
    """接听按钮。"""

    _attr_name = "门禁接听"
    _attr_icon = "mdi:phone"
    _attr_unique_id: ClassVar[str] = "uppercoast_doorlock_button_answer"

    def __init__(self, coordinator: UpperCoastDoorlockCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "doorlock")},
            name="虚拟门禁系统",
            manufacturer="UpperCoast",
            model="麦驰可视对讲",
        )

    async def async_press(self) -> None:
        data = self.coordinator.data or {}
        target_ip = data.get("target_ip", "")
        if target_ip:
            client = self.coordinator._client
            await client.async_answer(target_ip)


class UpperCoastDoorlockButtonHangup(ButtonEntity):
    """挂断按钮。"""

    _attr_name = "门禁挂断"
    _attr_icon = "mdi:phone-hangup"
    _attr_unique_id: ClassVar[str] = "uppercoast_doorlock_button_hangup"

    def __init__(self, coordinator: UpperCoastDoorlockCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "doorlock")},
            name="虚拟门禁系统",
            manufacturer="UpperCoast",
            model="麦驰可视对讲",
        )

    async def async_press(self) -> None:
        data = self.coordinator.data or {}
        target_ip = data.get("target_ip", "")
        if target_ip:
            client = self.coordinator._client
            await client.async_hangup(target_ip)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: UpperCoastDoorlockCoordinator = entry_data["coordinator"]
    async_add_entities([
        UpperCoastDoorlockButtonUnlock(coordinator),
        UpperCoastDoorlockButtonAnswer(coordinator),
        UpperCoastDoorlockButtonHangup(coordinator),
    ])