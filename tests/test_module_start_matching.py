# -*- coding: utf-8 -*-
"""StartMatch.matching 匹配失败返回契约的回归测试。"""
import os
import tempfile
import unittest
from unittest import mock

import numpy as np

from modules.ModuleGetPos import GetPosByTemplateMatch
from modules.ModuleStartMatching import StartMatch


class FakeScreenMethod:
    def window_screen(self):
        return np.zeros((10, 10), dtype=np.uint8)


class MatchingFailureContractTests(unittest.TestCase):
    def _make_start_match(self):
        gui_info = (
            "Windows程序", "自定义", "测试标题", 32, 1.0, 90.0,
            1.0, "模板匹配", "正常-可后台", "", "单开", 0,
        )
        return StartMatch(gui_info)

    def test_failed_match_returns_none_target_name(self):
        # 修复前失败分支返回最后扫描索引对应的图片名，
        # 上层会把它当作命中结果读取 flag，污染 skip/mark 标记
        with tempfile.TemporaryDirectory() as folder_path:
            image_path = os.path.join(folder_path, "a.png")
            target_info = ([], {}, ["a.png"], [image_path], {})
            start_match = self._make_start_match()
            with mock.patch.object(
                GetPosByTemplateMatch,
                "get_pos_by_template",
                return_value=(None, 0),
            ):
                results = start_match.matching(
                    "Windows程序", 0, "正常-可后台", FakeScreenMethod(),
                    False, "模板匹配", 1.0, target_info,
                    None, None, True, False, False, 0,
                )

        self.assertEqual(results, (True, False, False, None, []))


if __name__ == "__main__":
    unittest.main()
