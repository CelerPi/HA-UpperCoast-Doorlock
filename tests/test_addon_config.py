import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "addons" / "yunhai_intercom" / "app"
sys.path.insert(0, str(APP_DIR))

from yunhai_intercom.config import load_addon_options


class AddonConfigTest(unittest.TestCase):
    def test_missing_options_file_uses_1a_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            options_path = Path(temp_dir) / "options.json"

            config = load_addon_options(options_path)

        self.assertEqual("192.168.16.64", config.local_ip)
        self.assertEqual("00010116010", config.local_id)
        self.assertEqual("building_1_a", config.building_id)
        self.assertEqual("1栋A座", config.building_name)
        self.assertEqual("192.168.16.2", config.center_ip)
        self.assertEqual("192.168.23.255", config.property_center_ip)
        self.assertEqual(8, len(config.devices))

        devices_by_door = {device.door_no: device for device in config.devices}
        self.assertEqual("1号机", devices_by_door["01"].display_name)
        self.assertEqual("192.168.16.224", devices_by_door["01"].target_ip)
        self.assertEqual("1层", devices_by_door["01"].floor_label)
        self.assertEqual("车库", devices_by_door["01"].position_detail)
        self.assertEqual("192.168.16.225", devices_by_door["02"].target_ip)
        self.assertEqual("2层", devices_by_door["02"].floor_label)
        self.assertEqual("花园", devices_by_door["02"].position_detail)
        self.assertEqual("192.168.23.165", devices_by_door["08"].target_ip)
        self.assertEqual("电梯正对", devices_by_door["08"].position_detail)

    def test_blank_building_keeps_station_layout_but_no_active_devices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            options_path = Path(temp_dir) / "options.json"
            options_path.write_text(
                json.dumps(
                    {
                        "local_ip": "192.168.16.88",
                        "local_id": "00010122010",
                        "building_id": "building_2_c",
                    }
                ),
                encoding="utf-8",
            )

            config = load_addon_options(options_path)

        self.assertEqual("192.168.16.88", config.local_ip)
        self.assertEqual("00010122010", config.local_id)
        self.assertEqual("building_2_c", config.building_id)
        self.assertEqual("2栋C座", config.building_name)
        self.assertEqual(8, len(config.devices))
        self.assertEqual([], config.active_devices)
        self.assertEqual("", config.devices[0].target_ip)
        self.assertEqual("1层", config.devices[0].floor_label)
        self.assertEqual("-2层", config.devices[6].floor_label)

    def test_unknown_building_falls_back_to_default_preset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            options_path = Path(temp_dir) / "options.json"
            options_path.write_text(
                json.dumps({"building_id": "building_9_z"}),
                encoding="utf-8",
            )

            config = load_addon_options(options_path)

        self.assertEqual("building_1_a", config.building_id)
        self.assertEqual("1栋A座", config.building_name)
        self.assertEqual(8, len(config.active_devices))


if __name__ == "__main__":
    unittest.main()
