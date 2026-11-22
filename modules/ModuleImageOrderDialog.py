# -*- coding: utf-8 -*-
"""图片识别顺序设置对话框。"""
import os

from PyQt5 import QtCore, QtGui, QtWidgets

from modules.ModuleGetTargetInfo import (
    apply_image_order,
    list_target_image_files,
    load_image_order,
    save_image_order,
)


class ImageOrderDialog(QtWidgets.QDialog):
    def __init__(self, folder_path, parent=None):
        super(ImageOrderDialog, self).__init__(parent)
        self.folder_path = folder_path
        self.setWindowTitle("图片识别顺序")
        self.resize(560, 600)
        self.setMinimumSize(420, 360)
        if parent is not None and hasattr(parent, "centralwidget"):
            self.setStyleSheet(parent.centralwidget.styleSheet())

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        hint = QtWidgets.QLabel(
            "拖动列表或使用“上移/下移”调整识别顺序；\n"
            "保存后从下一次开始匹配时生效。新加入的图片默认排在末尾。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setObjectName("image_order_list")
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.currentItemChanged.connect(self._update_preview)
        layout.addWidget(self.list_widget, 1)

        preview_row = QtWidgets.QHBoxLayout()
        self.preview_image = QtWidgets.QLabel("选择图片以预览")
        self.preview_image.setObjectName("image_order_preview")
        self.preview_image.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_image.setFixedSize(200, 140)
        self.preview_image.setFrameShape(QtWidgets.QFrame.StyledPanel)
        preview_row.addWidget(self.preview_image)

        self.preview_name = QtWidgets.QLabel()
        self.preview_name.setWordWrap(True)
        preview_row.addWidget(self.preview_name, 1)
        layout.addLayout(preview_row)

        button_row = QtWidgets.QHBoxLayout()
        button_row.setSpacing(8)
        self.move_up_btn = QtWidgets.QPushButton("上移")
        self.move_down_btn = QtWidgets.QPushButton("下移")
        self.sort_btn = QtWidgets.QPushButton("按文件名排序")
        self.save_btn = QtWidgets.QPushButton("保存")
        self.cancel_btn = QtWidgets.QPushButton("取消")
        self.save_btn.setDefault(True)

        button_row.addWidget(self.move_up_btn)
        button_row.addWidget(self.move_down_btn)
        button_row.addWidget(self.sort_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.save_btn)
        button_row.addWidget(self.cancel_btn)
        layout.addLayout(button_row)

        self.move_up_btn.clicked.connect(lambda: self._move_item(-1))
        self.move_down_btn.clicked.connect(lambda: self._move_item(1))
        self.sort_btn.clicked.connect(self._sort_by_name)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

        self._load_images()

    def _load_images(self):
        if load_image_order(self.folder_path):
            files = apply_image_order(
                self.folder_path, list_target_image_files(self.folder_path)
            )
        else:
            files = list_target_image_files(self.folder_path, natural_sort=True)
        self._populate(files)

    def _populate(self, files):
        self.list_widget.clear()
        for image_path in files:
            relative = os.path.relpath(image_path, self.folder_path).replace("\\", "/")
            item = QtWidgets.QListWidgetItem(relative)
            item.setData(QtCore.Qt.UserRole, relative)
            item.setToolTip(image_path)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        else:
            self._update_preview()

    def _update_preview(self, current=None, _previous=None):
        if current is None:
            self.preview_image.setPixmap(QtGui.QPixmap())
            self.preview_image.setText("选择图片以预览")
            self.preview_name.clear()
            return

        relative = current.data(QtCore.Qt.UserRole)
        image_path = os.path.join(
            self.folder_path, *relative.replace("\\", "/").split("/")
        )
        reader = QtGui.QImageReader(image_path)
        reader.setAutoTransform(True)
        source_size = reader.size()
        if source_size.isValid():
            reader.setScaledSize(
                source_size.scaled(
                    QtCore.QSize(192, 132), QtCore.Qt.KeepAspectRatio
                )
            )
        image = reader.read()
        if image.isNull():
            self.preview_image.setPixmap(QtGui.QPixmap())
            self.preview_image.setText("图片无法预览")
        else:
            self.preview_image.setText("")
            self.preview_image.setPixmap(QtGui.QPixmap.fromImage(image))
        self.preview_name.setText(relative)
        self.preview_name.setToolTip(image_path)

    def _move_item(self, delta):
        row = self.list_widget.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self.list_widget.count():
            return
        item = self.list_widget.takeItem(row)
        self.list_widget.insertItem(target, item)
        self.list_widget.setCurrentRow(target)
        self._update_preview(self.list_widget.currentItem())

    def _sort_by_name(self):
        self._populate(list_target_image_files(self.folder_path, natural_sort=True))

    def _save(self):
        order = [
            self.list_widget.item(index).data(QtCore.Qt.UserRole)
            for index in range(self.list_widget.count())
        ]
        try:
            save_image_order(self.folder_path, order)
        except Exception as error:
            QtWidgets.QMessageBox.warning(
                self, "保存失败", "无法保存图片识别顺序：\n%s" % error
            )
            return
        self.accept()
