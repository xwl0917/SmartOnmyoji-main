import os
import tempfile
import unittest

from PyQt5 import QtGui, QtWidgets

from modules.ModuleImageOrderDialog import ImageOrderDialog


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


if __name__ == "__main__":
    unittest.main()
