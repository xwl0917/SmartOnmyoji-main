# -*- coding: utf-8 -*-
"""模板图片管理（删除引用清理）纯函数的单元测试。"""
import json
import os
import tempfile
import unittest

from modules.ModuleFlowBody import (
    find_flow_references,
    load_flow_config,
    remove_flow_steps,
)
from modules.ModuleGetTargetInfo import (
    load_image_order,
    remove_image_order_entry,
    save_image_order,
)
from modules.ModuleTemplateCapture import remove_img_pos_entry


class RemoveImageOrderEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder_path = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_removes_existing_entry(self):
        save_image_order(self.folder_path, ["a.jpg", "sub/b.png", "c.jpg"])
        remove_image_order_entry(self.folder_path, "sub/b.png")
        self.assertEqual(load_image_order(self.folder_path), ["a.jpg", "c.jpg"])

    def test_missing_entry_keeps_file(self):
        save_image_order(self.folder_path, ["a.jpg"])
        remove_image_order_entry(self.folder_path, "not_listed.png")
        self.assertEqual(load_image_order(self.folder_path), ["a.jpg"])

    def test_missing_file_is_noop(self):
        remove_image_order_entry(self.folder_path, "a.jpg")
        self.assertFalse(
            os.path.exists(os.path.join(self.folder_path, "img_order.json"))
        )


class RemoveImgPosEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder_path = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, entries):
        with open(
            os.path.join(self.folder_path, "img_pos.json"), "w", encoding="utf-8"
        ) as handle:
            json.dump(entries, handle)

    def _read(self):
        with open(
            os.path.join(self.folder_path, "img_pos.json"), "r", encoding="utf-8"
        ) as handle:
            return json.load(handle)

    def test_removes_named_entry_keeps_others(self):
        self._write(
            [
                {"name": "a", "real_pos": [1, 2], "click_pos": [], "flag": ""},
                {"name": "b", "real_pos": [], "click_pos": [], "flag": "skip"},
            ]
        )
        remove_img_pos_entry(self.folder_path, "a")
        entries = self._read()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], "b")

    def test_missing_file_is_noop(self):
        remove_img_pos_entry(self.folder_path, "a")
        self.assertFalse(
            os.path.exists(os.path.join(self.folder_path, "img_pos.json"))
        )


class FlowReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder_path = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def _save_nodes(self):
        from modules.ModuleFlowBody import save_flow_config

        save_flow_config(
            self.folder_path,
            [
                {
                    "name": "A",
                    "steps": [
                        {"image": "a.png", "action": "click", "next": ""},
                        {"image": "b.png", "action": "click", "next": ""},
                    ],
                    "next_node": "",
                },
                {
                    "name": "B",
                    "steps": [
                        {"image": "b.png", "action": "click", "next": ""}
                    ],
                    "next_node": "",
                },
            ],
        )

    def test_start_reference_found(self):
        self._save_nodes()
        start_nodes, step_nodes, error = find_flow_references(
            self.folder_path, "b.png"
        )
        self.assertEqual(error, None)
        self.assertEqual(start_nodes, ["B"])
        self.assertEqual(step_nodes, ["A"])

    def test_no_reference(self):
        self._save_nodes()
        start_nodes, step_nodes, error = find_flow_references(
            self.folder_path, "zzz.png"
        )
        self.assertEqual((start_nodes, step_nodes, error), ([], [], None))

    def test_missing_file_reports_no_reference(self):
        start_nodes, step_nodes, error = find_flow_references(
            self.folder_path, "a.png"
        )
        self.assertEqual((start_nodes, step_nodes), ([], []))
        self.assertIsNone(error)

    def test_remove_flow_steps_keeps_start_images(self):
        self._save_nodes()
        removed = remove_flow_steps(self.folder_path, "b.png")
        self.assertEqual(removed, 1)
        nodes = load_flow_config(self.folder_path)
        # 节点 A 的 b.png 步骤被移除，开始图 a.png 保留；节点 B 的开始图不动
        self.assertEqual(
            [step["image"] for step in nodes[0]["steps"]], ["a.png"]
        )
        self.assertEqual(
            [step["image"] for step in nodes[1]["steps"]], ["b.png"]
        )


if __name__ == "__main__":
    unittest.main()
