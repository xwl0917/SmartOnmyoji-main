# -*- coding: utf-8 -*-
"""HandleSet 空标题/空编号崩溃路径的回归测试。"""
import unittest

from modules.ModuleHandleSet import HandleSet


class GetHandleNumEmptyInputTests(unittest.TestCase):
    def test_empty_title_and_zero_handle_returns_falsy(self):
        # 单开模式未选择窗体时，全局鼠标点击监听会以 ("", 0) 构造 HandleSet；
        # 修复前此处对 None 做正则匹配抛 TypeError，导致 PyQt5 槽内异常崩溃。
        handle_set = HandleSet("", 0)
        self.assertFalse(handle_set.get_handle_num)

    def test_none_title_treated_as_empty(self):
        handle_set = HandleSet(None, 0)
        self.assertFalse(handle_set.get_handle_num)

    def test_zero_handle_valid_title_still_searches_by_title(self):
        # 标题存在但窗口不存在：不抛错，返回 None
        handle_set = HandleSet("不存在的窗口标题", 0)
        self.assertIsNone(handle_set.get_handle_num)


if __name__ == "__main__":
    unittest.main()
