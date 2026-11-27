# -*- coding: utf-8 -*-
"""程序多开配置读写（isolate 已移除）的单元测试。"""
import os
import tempfile
import unittest

from modules.ModuleGetConfig import ReadConfigFile

CONFIG_TEMPLATE = u"""[ui_info]
connect_mod = Windows程序

[other_setting]
save_ui_info_in_config = True
playtime_warming_status = True
success_times_warming_status = True
success_times_warming_times = 1
success_times_warming_waiting_seconds = 5,20
debug_status_show_pics = False
set_priority_num = 3
play_sound_status = True
adb_wifi_status = True
adb_wifi_ip = 127.0.0.1:7555
ex_click = 0.15
screen_scale_rate = 1.0
if_match_then_stop = True
stop_target_img_name = a,b
if_match_5times_stop = True
save_click_log = False
target_deviation = 32
success_match_then_wait = 300,600

[multi_open]
program_path = F:/yys/Launch.exe
instance_count = 2
interval_seconds = 3.0
isolate = True
use_v5 = False
v5_path =
"""


class MultiOpenConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "config.ini")
        with open(self.config_path, "w", encoding="utf-8-sig") as handle:
            handle.write(CONFIG_TEMPLATE)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _reader(self):
        reader = ReadConfigFile()
        reader.file_path = self.config_path
        return reader

    def test_read_returns_five_tuple_without_isolate(self):
        result = self._reader().read_multi_open_info()
        self.assertEqual(len(result), 5)
        program_path, instance_count, interval_seconds, use_v5, v5_path = result
        self.assertEqual(program_path, "F:/yys/Launch.exe")
        self.assertEqual(instance_count, 2)
        self.assertEqual(interval_seconds, 3.0)
        self.assertFalse(use_v5)
        self.assertEqual(v5_path, "")

    def test_write_roundtrip_and_removes_legacy_isolate_key(self):
        reader = self._reader()
        reader.writ_config_multi_open("C:/game.exe", 3, 5.0, True, "V5.exe")
        result = reader.read_multi_open_info()
        self.assertEqual(result[0], "C:/game.exe")
        self.assertEqual(result[1], 3)
        self.assertEqual(result[2], 5.0)
        self.assertTrue(result[3])
        self.assertEqual(result[4], "V5.exe")
        # 旧配置里的 isolate 键在写盘后被清理
        with open(self.config_path, "r", encoding="utf-8-sig") as handle:
            content = handle.read()
        self.assertNotIn("isolate", content)

    def test_missing_section_uses_defaults(self):
        with open(self.config_path, "w", encoding="utf-8-sig") as handle:
            handle.write(u"[ui_info]\nconnect_mod = Windows程序\n")
        program_path, instance_count, interval_seconds, use_v5, _v5 = (
            self._reader().read_multi_open_info()
        )
        self.assertEqual((program_path, instance_count, interval_seconds), ("", 2, 3.0))
        self.assertFalse(use_v5)


if __name__ == "__main__":
    unittest.main()
