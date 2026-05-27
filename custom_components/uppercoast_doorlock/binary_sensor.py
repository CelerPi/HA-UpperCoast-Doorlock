from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import UpperCoastDoorlockCoordinator
from .const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from typing import ClassVar


class UpperCoastDoorlockBinarySensor(BinarySensorEntity):
    """表示当前是否有活跃呼叫。attributes 中附带当前门口机详情。"""

    _attr_name = "门禁呼叫状态"
    _attr_icon = "mdi:doorbell-video"
    _attr_unique_id: ClassVar[str] = "uppercoast_doorlock_call_active"

    def __init__(self, coordinator: UpperCoastDoorlockCoordinator) -> None:
        self.coordinator = coordinator
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: UpperCoastDoorlockCoordinator = entry_data["coordinator"]
    async_add_entities([UpperCoastDoorlockBinarySensor(coordinator)])