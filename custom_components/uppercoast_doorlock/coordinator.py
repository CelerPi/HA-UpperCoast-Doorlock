from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import UpperCoastDoorlockClient

_LOGGER = logging.getLogger(__name__)


class UpperCoastDoorlockCoordinator(DataUpdateCoordinator):
    """协调 addon 状态与 HA 实体更新。"""

    def __init__(self, hass, client: UpperCoastDoorlockClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="uppercoast_doorlock",
            update_interval=1.0,
        )
        self._client = client
        self._previous: dict[str, Any] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        status = await self._client.async_get_status()
        new = status.get("runtime", {})
        self._detect_and_publish_events(new)
        return new

    @callback
    def _detect_and_publish_events(self, new: dict[str, Any]) -> None:
        prev = self._previous

        if new.get("in_call") and not prev.get("in_call"):
            self._hass.bus.async_fire("uppercoast_doorlock_call_started", {
                "device_name": new.get("device_name", ""),
                "display_name": new.get("display_name", ""),
                "target_ip": new.get("target_ip", ""),
                "floor_label": new.get("floor_label", ""),
                "position_detail": new.get("position_detail", ""),
            })

        if not new.get("in_call") and prev.get("in_call"):
            self._hass.bus.async_fire("uppercoast_doorlock_call_ended", {
                "device_name": prev.get("device_name", ""),
                "display_name": prev.get("display_name", ""),
                "target_ip": prev.get("target_ip", ""),
            })

        if new.get("frame_id") and new.get("frame_id") != prev.get("frame_id"):
            self._hass.bus.async_fire("uppercoast_doorlock_frame_received", {
                "frame_id": new.get("frame_id"),
            })

        self._previous = new.copy()