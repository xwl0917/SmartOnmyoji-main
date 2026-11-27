import os
import tempfile
import unittest

from PyQt5 import QtGui, QtWidgets

from modules.ModuleImageOrderDialog import (
    ImageOrderDialog,
    TemplateManagerDialog,
)


class ImageOrderDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QtWidgets.QApplication.instance()
        if cls.application is None:
            cls.application = QtWidgets.QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder_path = self.temp_dir.name
        self._write_image("first.png", QtGui.QColor("red"))
        self._write_image("second.png", QtGui.QColor("blue"))
        self.dialog = ImageOrderDialog(self.folder_path)

    def tearDown(self):
        self.dialog.close()
        self.temp_dir.cleanup()

    def _write_image(self, name, color):
        image = QtGui.QImage(24, 16, QtGui.QImage.Format_RGB32)
        image.fill(color)
        image.save(os.path.join(self.folder_path, name))

    def test_selected_image_is_previewed(self):
        self.assertEqual(self.dialog.preview_name.text(), "first.png")
        self.assertFalse(self.dialog.preview_image.pixmap().isNull())
        self.assertLessEqual(
            self.dialog.preview_image.pixmap().width(),
            self.dialog.preview_image.width(),
        )
        self.assertLessEqual(
            self.dialog.preview_image.pixmap().height(),
            self.dialog.preview_image.height(),
        )

        self.dialog.list_widget.setCurrentRow(1)

        self.assertEqual(self.dialog.preview_name.text(), "second.png")
        self.assertFalse(self.dialog.preview_image.pixmap().isNull())

    def test_preview_follows_image_when_reordered(self):
        self.dialog.list_widget.setCurrentRow(0)

        self.dialog._move_item(1)

        self.assertEqual(self.dialog.preview_name.text(), "first.png")
        self.assertEqual(
            self.dialog.list_widget.item(1).text(),
            "first.png",
        )


class TemplateManagerDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QtWidgets.QApplication.instance()
        if cls.application is None:
            cls.application = QtWidgets.QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder_path = self.temp_dir.name
        image = QtGui.QImage(24, 16, QtGui.QImage.Format_RGB32)
        image.fill(QtGui.QColor("red"))
        image.save(os.path.join(self.folder_path, "first.png"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _build_dialog(self, **kwargs):
        return TemplateManagerDialog(self.folder_path, **kwargs)

    def test_construction_updates_hint_and_mark_state(self):
        # 回归：基类提示标签必须存为 self.hint，子类 __init__ 会改写其文本
        dialog = self._build_dialog(current_mark_name="")
        self.assertIn("★", dialog.hint.text())
        self.assertIn("未设置", dialog.mark_status_label.text())
        dialog.close()

    def test_mark_set_callback_receives_stem_and_prefixes_item(self):
        received = []
        dialog = self._build_dialog(
            current_mark_name="",
            on_mark_set=received.append,
        )
        dialog.list_widget.setCurrentRow(0)
        dialog._set_mark(False)

        self.assertEqual(received, ["first"])
        self.assertTrue(dialog.list_widget.item(0).text().startswith("★ "))
        self.assertIn("first", dialog.mark_status_label.text())

        dialog._set_mark(True)
        self.assertEqual(received, ["first", ""])
        self.assertFalse(dialog.list_widget.item(0).text().startswith("★"))
        dialog.close()

    def test_construction_without_mark_shows_star_on_current_mark(self):
        dialog = self._build_dialog(current_mark_name="first")
        self.assertTrue(dialog.list_widget.item(0).text().startswith("★ "))
        self.assertIn("first", dialog.mark_status_label.text())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
