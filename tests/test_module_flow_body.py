import os
import tempfile
import unittest
from unittest import mock

import numpy as np
from modules.ModuleGetPos import GetPosBySiftMatch, GetPosByTemplateMatch
from modules.ModuleFlowBody import (
    has_configured_next_image,
    load_flow_config,
    resolve_next_index,
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
        steps = [
            {"image": "a.png", "action": "skip", "next": "c.png"},
            {"image": "b.png", "action": "click", "next": ""},
        ]

        save_flow_config(self.folder_path, steps)

        self.assertEqual(load_flow_config(self.folder_path), steps)
        self.assertTrue(
            os.path.isfile(os.path.join(self.folder_path, "img_flow.json"))
        )

    def test_duplicate_source_image_is_rejected(self):
        steps = [
            {"image": "a.png", "action": "click", "next": ""},
            {"image": "a.png", "action": "skip", "next": ""},
        ]

        with self.assertRaisesRegex(ValueError, "识别图片重复"):
            save_flow_config(self.folder_path, steps)

    def test_next_index_uses_route_or_default_order(self):
        image_keys = ["a.png", "b.png", "c.png"]
        flow_steps = {
            "a.png": {"image": "a.png", "action": "click", "next": "c.png"},
            "b.png": {"image": "b.png", "action": "skip", "next": ""},
        }

        self.assertEqual(resolve_next_index(0, image_keys, flow_steps), 2)
        self.assertEqual(resolve_next_index(1, image_keys, flow_steps), 2)
        self.assertEqual(resolve_next_index(2, image_keys, flow_steps), 0)
        self.assertTrue(has_configured_next_image(0, image_keys, flow_steps))
        self.assertFalse(has_configured_next_image(1, image_keys, flow_steps))

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


if __name__ == "__main__":
    unittest.main()
