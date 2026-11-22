import os
import tempfile
import unittest
from unittest import mock

import numpy as np
from PyQt5 import QtWidgets
from modules.ModuleGetPos import GetPosBySiftMatch, GetPosByTemplateMatch
from modules.ModuleFlowBody import (
    DEFAULT_NEXT,
    FLOW_ACTION_LABELS,
    FlowBodyRuntime,
    FlowBodyEditor,
    load_flow_config,
    save_flow_config,
)


class FlowBodyConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder_path = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_file_keeps_default_flow(self):
        self.assertEqual(load_flow_config(self.folder_path), [])

    def test_save_and_load_flow_steps(self):
        nodes = [
            {
                "name": "流程A",
                "steps": [
                    {"image": "a.png", "action": "skip", "next": "b.png"},
                    {"image": "b.png", "action": "click", "next": ""},
                ],
                "next_node": "",
            },
        ]

        save_flow_config(self.folder_path, nodes)

        self.assertEqual(load_flow_config(self.folder_path), nodes)
        self.assertTrue(
            os.path.isfile(os.path.join(self.folder_path, "img_flow.json"))
        )

    def test_legacy_config_loads_as_single_node(self):
        config_path = os.path.join(self.folder_path, "img_flow.json")
        with open(config_path, "w", encoding="utf-8") as flow_file:
            flow_file.write(
                '{"version": 1, "steps": ['
                '{"image": "a.png", "action": "click", "next": ""}]}'
            )

        self.assertEqual(
            load_flow_config(self.folder_path),
            [
                {
                    "name": "流程1",
                    "steps": [
                        {"image": "a.png", "action": "click", "next": ""}
                    ],
                    "next_node": "",
                }
            ],
        )

    def test_duplicate_node_start_image_is_rejected(self):
        nodes = [
            {
                "name": "流程A",
                "steps": [{"image": "a.png", "action": "click", "next": ""}],
                "next_node": "",
            },
            {
                "name": "流程B",
                "steps": [{"image": "a.png", "action": "skip", "next": ""}],
                "next_node": "",
            },
        ]

        with self.assertRaisesRegex(ValueError, "开始图片重复"):
            save_flow_config(self.folder_path, nodes)

    def test_esc_action_is_valid_and_persisted(self):
        nodes = [
            {
                "name": "流程A",
                "steps": [
                    {"image": "a.png", "action": "esc", "next": ""}
                ],
                "next_node": "",
            }
        ]
        save_flow_config(self.folder_path, nodes)
        loaded = load_flow_config(self.folder_path)

        self.assertEqual(loaded[0]["steps"][0]["action"], "esc")
        self.assertIn("esc", FLOW_ACTION_LABELS)
        self.assertEqual(FLOW_ACTION_LABELS["esc"], "按下ESC键")

    def test_runtime_prioritizes_expected_image_over_other_starts_and_transitions(self):
        image_keys = ["a_start.png", "a_end.png", "b_start.png", "b_end.png"]
        nodes = [
            {
                "name": "A",
                "steps": [
                    {"image": "a_start.png", "action": "click", "next": ""},
                    {"image": "a_end.png", "action": "skip", "next": ""},
                ],
                "next_node": "B",
            },
            {
                "name": "B",
                "steps": [
                    {"image": "b_start.png", "action": "click", "next": ""},
                    {"image": "b_end.png", "action": "stop", "next": ""},
                ],
                "next_node": "",
            },
        ]
        runtime = FlowBodyRuntime(image_keys, nodes)

        self.assertEqual(runtime.candidate_indices(), [0, 2, 1, 3])
        self.assertEqual(runtime.on_match("a_start.png")["action"], "click")
        self.assertEqual(runtime.active_node, "A")
        # 节点内：期望图 a_end 优先，其他节点开始图 b_start 只作兜底
        self.assertEqual(runtime.candidate_indices(), [1, 2])

        runtime.on_match("b_start.png")
        self.assertEqual(runtime.active_node, "B")
        self.assertEqual(runtime.expected_image, "b_end.png")

        runtime.on_match("b_end.png")
        self.assertEqual(runtime.active_node, "")

    def test_runtime_jumps_to_configured_node_at_node_end(self):
        nodes = [
            {
                "name": "A",
                "steps": [{"image": "a.png", "action": "click", "next": ""}],
                "next_node": "B",
            },
            {
                "name": "B",
                "steps": [{"image": "b.png", "action": "skip", "next": ""}],
                "next_node": "",
            },
        ]
        runtime = FlowBodyRuntime(["a.png", "b.png"], nodes)

        runtime.on_match("a.png")

        self.assertEqual(runtime.active_node, "B")
        self.assertEqual(runtime.expected_image, "b.png")
        self.assertEqual(runtime.on_match("b.png")["action"], "skip")
        self.assertEqual(runtime.active_node, "")

    def test_template_matching_can_restrict_to_next_image(self):
        screen = np.zeros((4, 4), dtype=np.uint8)
        templates = [screen, screen, screen]
        with mock.patch.object(
            GetPosByTemplateMatch, "template_matching", return_value=None
        ) as template_match:
            position, image_index = GetPosByTemplateMatch.get_pos_by_template(
                screen, templates, False, start_index=0, candidate_indices=[2]
            )

        self.assertIsNone(position)
        self.assertEqual(image_index, 2)
        self.assertEqual(
            [call[0][-1] for call in template_match.call_args_list], [2]
        )

    def test_sift_matching_can_restrict_to_next_image(self):
        target_sift = [None, None, None]
        target_hw = [(1, 1), (1, 1), (1, 1)]
        target_images = [None, None, None]
        with mock.patch.object(
            GetPosBySiftMatch, "sift_matching", return_value=None
        ) as sift_match:
            position, image_index = GetPosBySiftMatch.get_pos_by_sift(
                target_sift,
                None,
                target_hw,
                target_images,
                None,
                False,
                start_index=0,
                candidate_indices=[1],
            )

        self.assertIsNone(position)
        self.assertEqual(image_index, 1)
        self.assertEqual([call[0][-1] for call in sift_match.call_args_list], [1])


class FlowBodyEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QtWidgets.QApplication.instance()
        if cls.application is None:
            cls.application = QtWidgets.QApplication([])

    def test_added_rule_uses_previous_rule_next_image(self):
        with tempfile.TemporaryDirectory() as folder_path:
            image_paths = [
                os.path.join(folder_path, "a.png"),
                os.path.join(folder_path, "b.png"),
            ]
            save_flow_config(
                folder_path,
                [
                    {
                        "name": "流程A",
                        "steps": [
                            {
                                "image": "b.png",
                                "action": "click",
                                "next": "a.png",
                            }
                        ],
                        "next_node": "",
                    }
                ],
            )
            editor = FlowBodyEditor()
            with mock.patch(
                "modules.ModuleFlowBody.list_target_image_files",
                return_value=image_paths,
            ):
                editor.set_target_folder(folder_path)

            editor.node_combo.setCurrentIndex(0)
            editor._add_rule()

            self.assertEqual(editor.table.rowCount(), 2)
            self.assertEqual(
                editor.table.cellWidget(1, 0).currentData(), "a.png"
            )
            editor.close()

    def test_last_row_next_image_appends_step(self):
        with tempfile.TemporaryDirectory() as folder_path:
            image_paths = [
                os.path.join(folder_path, "a.png"),
                os.path.join(folder_path, "b.png"),
            ]
            save_flow_config(
                folder_path,
                [
                    {
                        "name": "流程A",
                        "steps": [
                            {"image": "a.png", "action": "click", "next": ""}
                        ],
                        "next_node": "",
                    }
                ],
            )
            editor = FlowBodyEditor()
            with mock.patch(
                "modules.ModuleFlowBody.list_target_image_files",
                return_value=image_paths,
            ):
                editor.set_target_folder(folder_path)

            self.assertEqual(editor.table.rowCount(), 1)
            next_combo = editor.table.cellWidget(0, 2)
            next_combo.setCurrentIndex(next_combo.findData("b.png"))

            self.assertEqual(editor.table.rowCount(), 2)
            self.assertEqual(
                editor.table.cellWidget(1, 0).currentData(), "b.png"
            )
            self.assertEqual(
                editor.table.cellWidget(1, 1).currentData(), "click"
            )
            self.assertEqual(
                editor.table.cellWidget(1, 2).currentData(), DEFAULT_NEXT
            )
            self.assertIn("b.png", editor.status_label.text())
            editor.close()

    def test_next_image_change_guards(self):
        with tempfile.TemporaryDirectory() as folder_path:
            image_paths = [
                os.path.join(folder_path, "a.png"),
                os.path.join(folder_path, "b.png"),
                os.path.join(folder_path, "c.png"),
            ]
            save_flow_config(
                folder_path,
                [
                    {
                        "name": "流程A",
                        "steps": [
                            {
                                "image": "a.png",
                                "action": "click",
                                "next": "b.png",
                            },
                            {"image": "b.png", "action": "click", "next": ""},
                        ],
                        "next_node": "",
                    }
                ],
            )
            editor = FlowBodyEditor()
            with mock.patch(
                "modules.ModuleFlowBody.list_target_image_files",
                return_value=image_paths,
            ):
                editor.set_target_folder(folder_path)

            # 加载已配置 next 的节点时，不会触发自动追加
            self.assertEqual(editor.table.rowCount(), 2)

            # 非末行选择新图：仅作为跳转目标，不追加步骤
            first_next = editor.table.cellWidget(0, 2)
            first_next.setCurrentIndex(first_next.findData("c.png"))
            self.assertEqual(editor.table.rowCount(), 2)

            # 末行选择节点内已使用的图片：不追加
            last_next = editor.table.cellWidget(1, 2)
            last_next.setCurrentIndex(last_next.findData("a.png"))
            self.assertEqual(editor.table.rowCount(), 2)

            # 末行选择新图：自动追加该图片的步骤
            last_next.setCurrentIndex(last_next.findData("c.png"))
            self.assertEqual(editor.table.rowCount(), 3)
            self.assertEqual(
                editor.table.cellWidget(2, 0).currentData(), "c.png"
            )
            editor.close()


if __name__ == "__main__":
    unittest.main()
