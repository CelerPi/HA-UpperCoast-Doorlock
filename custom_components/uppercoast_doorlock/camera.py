from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.components.camera import Camera
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from typing import ClassVar

from .coordinator import UpperCoastDoorlockCoordinator
from .const import DOMAIN
from homeassistant.config_entries import ConfigEntry


class UpperCoastDoorlockCamera(Camera):
    """实时视频帧摄像头实体。"""

    _attr_name = "门禁视频"
    _attr_unique_id: ClassVar[str] = "uppercoast_doorlock_camera"

    def __init__(self, coordinator: UpperCoastDoorlockCoordinator) -> None:
        Camera.__init__(self)
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
        return bool(data.get("has_frame", False))

    async def async_camera_image(self) -> bytes | None:
        client = self.coordinator._client
        return await client.async_get_frame()

    async def stream_source(self) -> str | None:
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: UpperCoastDoorlockCoordinator = entry_data["coordinator"]
    async_add_entities([UpperCoastDoorlockCamera(coordinator)])