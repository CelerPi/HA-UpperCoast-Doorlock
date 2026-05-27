from __future__ import annotations

import logging
from typing import ClassVar

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import UpperCoastDoorlockCoordinator
from .const import DOMAIN
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class UpperCoastDoorlockBinarySensor(CoordinatorEntity[UpperCoastDoorlockCoordinator], BinarySensorEntity):
    """表示当前是否有活跃呼叫。attributes 中附带当前门口机详情。"""

    _attr_name = "门禁呼叫状态"
    _attr_icon = "mdi:doorbell-video"
    _attr_unique_id: ClassVar[str] = "uppercoast_doorlock_call_active"

    def __init__(self, coordinator: UpperCoastDoorlockCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "doorlock")},
            name="虚拟门禁系统",
            manufacturer="UpperCoast",
            model="麦驰可视对讲",
        )

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        return bool(data.get("in_call", False))

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        data = self.coordinator.data or {}
        if not data.get("in_call"):
            return {}
        return {
            "device_name": data.get("device_name", ""),
            "display_name": data.get("display_name", ""),
            "target_ip": data.get("target_ip", ""),
            "floor_label": data.get("floor_label", ""),
            "position_detail": data.get("position_detail", ""),
        }


class UpperCoastDoorlockCamera(CoordinatorEntity[UpperCoastDoorlockCoordinator], Camera):
    """实时视频帧摄像头实体。"""

    _attr_name = "门禁视频"
    _attr_unique_id: ClassVar[str] = "uppercoast_doorlock_camera"

    def __init__(self, coordinator: UpperCoastDoorlockCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "doorlock")},
            name="虚拟门禁系统",
            manufacturer="UpperCoast",
            model="麦驰可视对讲",
        )

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        return bool(data.get("has_frame", False))

    async def async_camera_image(self) -> bytes | None:
        client = self.coordinator._client
        return await client.async_get_frame()

    async def stream_source(self) -> str | None:
        return None

    def pre_SHUTDOWN(self) -> None:
        pass


class UpperCoastDoorlockButtonUnlock(CoordinatorEntity[UpperCoastDoorlockCoordinator], ButtonEntity):
    """解锁按钮。"""

    _attr_name = "门禁解锁"
    _attr_icon = "mdi:door-open"
    _attr_unique_id: ClassVar[str] = "uppercoast_doorlock_button_unlock"

    def __init__(self, coordinator: UpperCoastDoorlockCoordinator) -> None:
        super().__init__(coordinator)
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


class UpperCoastDoorlockButtonAnswer(CoordinatorEntity[UpperCoastDoorlockCoordinator], ButtonEntity):
    """接听按钮。"""

    _attr_name = "门禁接听"
    _attr_icon = "mdi:phone"
    _attr_unique_id: ClassVar[str] = "uppercoast_doorlock_button_answer"

    def __init__(self, coordinator: UpperCoastDoorlockCoordinator) -> None:
        super().__init__(coordinator)
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


class UpperCoastDoorlockButtonHangup(CoordinatorEntity[UpperCoastDoorlockCoordinator], ButtonEntity):
    """挂断按钮。"""

    _attr_name = "门禁挂断"
    _attr_icon = "mdi:phone-hangup"
    _attr_unique_id: ClassVar[str] = "uppercoast_doorlock_button_hangup"

    def __init__(self, coordinator: UpperCoastDoorlockCoordinator) -> None:
        super().__init__(coordinator)
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
    coordinator = entry_data["coordinator"]

    async_add_entities([
        UpperCoastDoorlockBinarySensor(coordinator),
        UpperCoastDoorlockCamera(coordinator),
        UpperCoastDoorlockButtonUnlock(coordinator),
        UpperCoastDoorlockButtonAnswer(coordinator),
        UpperCoastDoorlockButtonHangup(coordinator),
    ])