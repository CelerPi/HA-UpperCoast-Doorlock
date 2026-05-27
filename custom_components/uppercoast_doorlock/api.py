from __future__ import annotations

import aiohttp
from typing import Any


class UpperCoastDoorlockClient:
    """调用 addon HTTP API 的客户端。"""

    def __init__(self, host: str, port: int, token: str) -> None:
        self._base_url = f"http://{host}:{port}"
        self._token = token

    async def async_get_status(self) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            resp = await session.get(
                f"{self._base_url}/api/status",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=5),
            )
            resp.raise_for_status()
            return await resp.json()

    async def async_unlock(self, target_ip: str) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                f"{self._base_url}/api/unlock",
                json={"target_ip": target_ip},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=5),
            )
            return await resp.json()

    async def async_answer(self, target_ip: str) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                f"{self._base_url}/api/answer",
                json={"target_ip": target_ip},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=5),
            )
            return await resp.json()

    async def async_hangup(self, target_ip: str) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                f"{self._base_url}/api/hangup",
                json={"target_ip": target_ip},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=5),
            )
            return await resp.json()

    async def async_get_frame(self) -> bytes | None:
        async with aiohttp.ClientSession() as session:
            resp = await session.get(
                f"{self._base_url}/api/frame",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=5),
            )
            if resp.status == 404:
                return None
            resp.raise_for_status()
            return await resp.read()