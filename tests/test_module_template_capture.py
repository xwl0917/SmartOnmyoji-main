# -*- coding: utf-8 -*-
"""模板采集工具纯函数的单元测试：命名、裁剪、保存回读、img_pos 合并。"""
import json
import os
import tempfile
import unittest

import numpy as np
from numpy import frombuffer, uint8
import cv2

from modules.ModuleTemplateCapture import (
    crop_screen_image,
    merge_flag_into_img_pos,
    next_available_name,
    sanitize_image_name,
    save_template_image,
)


def _read_image(path):
    return cv2.imdecode(frombuffer(np.fromfile(path, dtype=uint8), uint8), cv2.IMREAD_COLOR)


class SanitizeImageNameTests(unittest.TestCase):
    def test_strips_extension_and_illegal_chars(self):
        self.assertEqual(sanitize_image_name("  boss_1.JPG "), "boss_1")
        self.assertEqual(sanitize_image_name('a<b>c:d?.png'), "abcd")

    def test_empty_name_raises(self):
        with self.assertRaises(ValueError):
            sanitize_image_name("   ")
        with self.assertRaises(ValueError):
            sanitize_image_name("<>:*?")


class NextAvailableNameTests(unittest.TestCase):
    def test_returns_numbered_name_skipping_existing(self):
        with tempfile.TemporaryDirectory() as folder_path:
            self.assertEqual(next_available_name(folder_path), "capture_1")
            open(os.path.join(folder_path, "capture_1.jpg"), "wb").close()
            open(os.path.join(folder_path, "capture_2.jpg"), "wb").close()
            self.assertEqual(next_available_name(folder_path), "capture_3")


class CropScreenImageTests(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((100, 80), dtype=np.uint8)

    def test_in_bounds_crop_exact(self):
        crop = crop_screen_image(self.image, (10, 20, 40, 60))
        self.assertEqual(crop.shape, (40, 30))

    def test_swapped_and_out_of_bounds_clamped(self):
        # 坐标颠倒 + 越界：收敛到图片边界（y: 30→90 高60，x: 70→80 宽10）
        crop = crop_screen_image(self.image, (70, 90, 200, 30))
        self.assertEqual(crop.shape, (60, 10))

    def test_too_small_returns_none(self):
        self.assertIsNone(crop_screen_image(self.image, (10, 10, 14, 30)))


class SaveTemplateImageTests(unittest.TestCase):
    def test_roundtrip_reads_back_same_shape(self):
        with tempfile.TemporaryDirectory() as folder_path:
            image = np.full((48, 64), 128, dtype=np.uint8)
            path = save_template_image(folder_path, "中文名称", image)

            self.assertTrue(os.path.isfile(path))
            loaded = _read_image(path)
            self.assertEqual(loaded.shape, (48, 64, 3))


class MergeFlagIntoImgPosTests(unittest.TestCase):
    def test_creates_file_when_missing(self):
        with tempfile.TemporaryDirectory() as folder_path:
            path = merge_flag_into_img_pos(folder_path, "boss", "start")
            with open(path, "r", encoding="utf-8") as handle:
                entries = json.load(handle)
            self.assertEqual(
                entries,
                [{"name": "boss", "real_pos": [], "click_pos": [], "flag": "start"}],
            )

    def test_appends_new_entry_and_keeps_existing(self):
        with tempfile.TemporaryDirectory() as folder_path:
            json_path = os.path.join(folder_path, "img_pos.json")
            with open(json_path, "w", encoding="utf-8") as handle:
                json.dump(
                    [{"name": "fight", "real_pos": [1, 2],
                      "click_pos": [[3, 4]], "flag": "start"}],
                    handle,
                )
            merge_flag_into_img_pos(folder_path, "boss", "skip")

            with open(json_path, "r", encoding="utf-8") as handle:
                entries = json.load(handle)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["flag"], "start")
            self.assertEqual(entries[1]["flag"], "skip")

    def test_updates_existing_entry_flag_without_duplicating(self):
        with tempfile.TemporaryDirectory() as folder_path:
            json_path = os.path.join(folder_path, "img_pos.json")
            with open(json_path, "w", encoding="utf-8") as handle:
                json.dump(
                    [{"name": "boss", "real_pos": [1, 2],
                      "click_pos": [[3, 4]], "flag": ""}],
                    handle,
                )
            merge_flag_into_img_pos(folder_path, "boss", "mark")

            with open(json_path, "r", encoding="utf-8") as handle:
                entries = json.load(handle)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["flag"], "mark")
            self.assertEqual(entries[0]["real_pos"], [1, 2])

    def test_corrupted_json_raises_value_error(self):
        with tempfile.TemporaryDirectory() as folder_path:
            json_path = os.path.join(folder_path, "img_pos.json")
            with open(json_path, "w", encoding="utf-8") as handle:
                handle.write("{broken")
            with self.assertRaises(ValueError):
                merge_flag_into_img_pos(folder_path, "boss", "skip")


if __name__ == "__main__":
    unittest.main()
