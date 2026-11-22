# -*- coding: utf-8 -*-
"""性能与资源管理优化项的回归测试：配置缓存、命令超时、SIFT 单例。"""
import os
import tempfile
import time
import unittest

import numpy as np

import modules.ModuleGetConfig as config_module
from modules.ModuleGetConfig import ReadConfigFile
from modules.ModuleHandleSet import HandleSet
from modules.ModuleImgProcess import ImgProcess

CONFIG_TEMPLATE = u"""[other_setting]
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
screen_scale_rate = {scale}
if_match_then_stop = True
stop_target_img_name = a,b
if_match_5times_stop = True
save_click_log = False
target_deviation = 32
success_match_then_wait = 300,600
"""


class OtherSettingCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "config.ini")
        with open(self.config_path, "w", encoding="utf-8-sig") as handle:
            handle.write(CONFIG_TEMPLATE.format(scale="1.0"))
        config_module._invalidate_other_setting_cache()

    def tearDown(self):
        config_module._invalidate_other_setting_cache()
        self.temp_dir.cleanup()

    def _reader(self):
        reader = ReadConfigFile()
        reader.file_path = self.config_path
        return reader

    def test_cached_read_returns_same_value_until_file_changes(self):
        first = self._reader().read_config_other_setting()
        self.assertEqual(first[11], "1.0")
        # 文件未改动时命中缓存，两次读取内容一致
        self.assertEqual(self._reader().read_config_other_setting()[11], "1.0")
        self.assertIsNot(self._reader().read_config_other_setting(), first)

    def test_refreshed_when_file_content_and_mtime_change(self):
        self._reader().read_config_other_setting()
        with open(self.config_path, "w", encoding="utf-8-sig") as handle:
            handle.write(CONFIG_TEMPLATE.format(scale="1.1"))
        stat = os.stat(self.config_path)
        os.utime(self.config_path, ns=(stat.st_mtime_ns + 1000000,) * 2)
        self.assertEqual(self._reader().read_config_other_setting()[11], "1.1")

    def test_multi_open_write_invalidates_cache(self):
        self._reader().read_config_other_setting()
        self.assertIsNotNone(config_module._OTHER_SETTING_CACHE)
        self._reader().writ_config_multi_open("", 2, 3.0, True, False, "")
        self.assertIsNone(config_module._OTHER_SETTING_CACHE)


class DealCmdTimeoutTests(unittest.TestCase):
    def test_timeout_returns_promptly(self):
        start = time.monotonic()
        result = HandleSet.deal_cmd("ping -n 30 127.0.0.1", timeout=2)
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 10)
        self.assertEqual(result, b"")


class SiftSingletonTests(unittest.TestCase):
    def test_detector_reused_across_calls(self):
        import modules.ModuleImgProcess as img_process_module

        image = np.zeros((8, 8), dtype=np.uint8)
        ImgProcess.get_sift(image)
        detector = img_process_module._SIFT_DETECTOR
        self.assertIsNotNone(detector)
        ImgProcess.get_sift(image)
        self.assertIs(img_process_module._SIFT_DETECTOR, detector)


if __name__ == "__main__":
    unittest.main()
