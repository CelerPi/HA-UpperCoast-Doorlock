from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_LOCAL_IP = "192.168.16.64"
DEFAULT_LOCAL_ID = "00010116010"
DEFAULT_BUILDING_ID = "building_1_a"
DEFAULT_CENTER_IP = "192.168.16.2"
DEFAULT_PROPERTY_CENTER_IP = "192.168.23.255"

STATION_LAYOUT = [
    {"name": "1F-1", "door_no": "01", "floor_label": "1层", "position_detail": "车库"},
    {"name": "2F-2", "door_no": "02", "floor_label": "2层", "position_detail": "花园"},
    {"name": "B1-3", "door_no": "03", "floor_label": "-1层", "position_detail": "车库"},
    {"name": "B2-4", "door_no": "04", "floor_label": "-2层", "position_detail": "车库"},
    {
        "name": "1F-5",
        "door_no": "05",
        "floor_label": "-1层",
        "position_detail": "电梯左侧小门左边",
    },
    {
        "name": "1F-6",
        "door_no": "06",
        "floor_label": "-1层",
        "position_detail": "电梯左侧小门右边",
    },
    {
        "name": "1F-7",
        "door_no": "07",
        "floor_label": "-2层",
        "position_detail": "电梯左侧小门左边",
    },
    {"name": "1F-8", "door_no": "08", "floor_label": "1层", "position_detail": "电梯正对"},
]

BUILDING_NAMES = [
    ("building_1_a", "1栋A座"),
    ("building_1_b", "1栋B座"),
    ("building_1_c", "1栋C座"),
    ("building_1_d", "1栋D座"),
    ("building_1_e", "1栋E座"),
    ("building_2_a", "2栋A座"),
    ("building_2_b", "2栋B座"),
    ("building_2_c", "2栋C座"),
]

BUILDING_NAME_BY_ID = dict(BUILDING_NAMES)

BUILDING_IPS_BY_ID = {
    "building_1_a": {
        "01": "192.168.16.224",
        "02": "192.168.16.225",
        "03": "192.168.16.226",
        "04": "192.168.16.227",
        "05": "192.168.16.228",
        "06": "192.168.16.229",
        "07": "192.168.23.164",
        "08": "192.168.23.165",
    },
}


@dataclass(frozen=True)
class DoorStation:
    name: str
    door_no: str
    floor_label: str
    position_detail: str
    target_ip: str = ""

    @property
    def display_name(self) -> str:
        return f"{int(self.door_no)}号机"

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "door_no": self.door_no,
            "floor_label": self.floor_label,
            "position_detail": self.position_detail,
            "target_ip": self.target_ip,
        }


@dataclass(frozen=True)
class IntercomConfig:
    local_ip: str
    local_id: str
    building_id: str
    building_name: str
    center_ip: str
    property_center_ip: str
    devices: tuple[DoorStation, ...]

    @property
    def active_devices(self) -> list[DoorStation]:
        return [device for device in self.devices if device.target_ip]

    def as_dict(self) -> dict[str, Any]:
        return {
            "local_ip": self.local_ip,
            "local_id": self.local_id,
            "building_id": self.building_id,
            "building_name": self.building_name,
            "center_ip": self.center_ip,
            "property_center_ip": self.property_center_ip,
            "devices": [device.as_dict() for device in self.devices],
            "active_device_count": len(self.active_devices),
        }


def load_addon_options(options_path: str | Path = "/data/options.json") -> IntercomConfig:
    path = Path(options_path)
    if path.exists():
        raw_options = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw_options = {}
    return normalize_options(raw_options)


def normalize_options(raw_options: Any) -> IntercomConfig:
    options = raw_options if isinstance(raw_options, dict) else {}

    building_id = str(options.get("building_id") or DEFAULT_BUILDING_ID)
    if building_id not in BUILDING_NAME_BY_ID:
        building_id = DEFAULT_BUILDING_ID

    devices = tuple(_build_devices(building_id, options.get("devices")))

    return IntercomConfig(
        local_ip=str(options.get("local_ip") or DEFAULT_LOCAL_IP),
        local_id=str(options.get("local_id") or DEFAULT_LOCAL_ID),
        building_id=building_id,
        building_name=BUILDING_NAME_BY_ID[building_id],
        center_ip=str(options.get("center_ip") or DEFAULT_CENTER_IP),
        property_center_ip=str(options.get("property_center_ip") or DEFAULT_PROPERTY_CENTER_IP),
        devices=devices,
    )


def _build_devices(building_id: str, saved_devices: Any = None) -> list[DoorStation]:
    known_ips = BUILDING_IPS_BY_ID.get(building_id, {})
    saved_by_door = _saved_devices_by_door(saved_devices)
    devices = []

    for station in STATION_LAYOUT:
        door_no = station["door_no"]
        saved = saved_by_door.get(door_no, {})
        saved_target_ip = saved.get("target_ip")
        target_ip = saved_target_ip if saved_target_ip is not None else known_ips.get(door_no, "")
        devices.append(
            DoorStation(
                name=str(saved.get("name") or station["name"]),
                door_no=door_no,
                floor_label=str(saved.get("floor_label") or station["floor_label"]),
                position_detail=str(saved.get("position_detail") or station["position_detail"]),
                target_ip=str(target_ip),
            )
        )

    return devices


def _saved_devices_by_door(saved_devices: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(saved_devices, list):
        return {}

    devices: dict[str, dict[str, Any]] = {}
    for device in saved_devices:
        if not isinstance(device, dict):
            continue
        door_no = str(device.get("door_no") or "").strip()
        if door_no:
            devices[door_no] = device
    return devices
