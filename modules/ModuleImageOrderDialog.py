# -*- coding: utf-8 -*-
"""图片识别顺序设置与模板图片管理对话框。"""
import os

from PyQt5 import QtCore, QtGui, QtWidgets

from modules.ModuleFlowBody import find_flow_references, remove_flow_steps
from modules.ModuleGetTargetInfo import (
    apply_image_order,
    list_target_image_files,
    load_image_order,
    remove_image_order_entry,
    save_image_order,
)
from modules.ModuleTemplateCapture import remove_img_pos_entry


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

        self.hint = QtWidgets.QLabel(
            "拖动列表或使用“上移/下移”调整识别顺序；\n"
            "保存后从下一次开始匹配时生效。新加入的图片默认排在末尾。"
        )
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

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


def _image_stem(relative_key):
    """从相对路径取文件主名（与 custom_mark_image 下拉框的 name 一致）。"""
    return os.path.splitext(os.path.basename(relative_key))[0]


class TemplateManagerDialog(ImageOrderDialog):
    """模板图片管理：识别顺序、采集、删除、自定义 mark 一站式操作。

    在 ImageOrderDialog 基础上增加：
      - 采集模板：调用 capture_opener(folder_path) 回调（主窗口提供截图流程）
      - 删除选中：删图片文件并同步清理 img_order.json / img_pos.json /
        img_flow.json 中的引用（节点开始图片被引用时阻止删除）
      - 设为/取消 mark：通过 on_mark_set(name_or_empty) 回调写入主窗口的
        隐藏 custom_mark_image 下拉框（配置存储机制不变）
    识别顺序仍由基类在点击“保存”时写入 img_order.json。
    """

    def __init__(self, folder_path, current_mark_name="", on_mark_set=None,
                 capture_opener=None, parent=None):
        self.current_mark_name = current_mark_name or ""
        self.on_mark_set = on_mark_set
        self.capture_opener = capture_opener
        super(TemplateManagerDialog, self).__init__(folder_path, parent)
        self.setWindowTitle("模板图片管理")
        self.hint.setText(
            "拖动列表或使用“上移/下移”调整识别顺序（点“保存”生效）；\n"
            "采集/删除/mark 即时生效。★ 为当前自定义 mark 图片。"
        )

        # 在提示与列表之间插入管理工具栏
        toolbar_row = QtWidgets.QHBoxLayout()
        toolbar_row.setSpacing(8)
        self.capture_btn = QtWidgets.QPushButton("采集模板")
        self.delete_btn = QtWidgets.QPushButton("删除选中")
        self.mark_set_btn = QtWidgets.QPushButton("设为mark")
        self.mark_clear_btn = QtWidgets.QPushButton("取消mark")
        self.mark_status_label = QtWidgets.QLabel()
        toolbar_row.addWidget(self.capture_btn)
        toolbar_row.addWidget(self.delete_btn)
        toolbar_row.addWidget(self.mark_set_btn)
        toolbar_row.addWidget(self.mark_clear_btn)
        toolbar_row.addStretch(1)
        toolbar_row.addWidget(self.mark_status_label)
        self.layout().insertLayout(1, toolbar_row)

        self.capture_btn.clicked.connect(self._on_capture)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.mark_set_btn.clicked.connect(lambda: self._set_mark(False))
        self.mark_clear_btn.clicked.connect(lambda: self._set_mark(True))

        self._apply_mark_prefixes()
        self._refresh_mark_status()

    # ---- mark ------------------------------------------------------- #
    def _is_mark_image(self, relative_key):
        return bool(self.current_mark_name) and (
            _image_stem(relative_key) == self.current_mark_name
        )

    def _apply_mark_prefixes(self):
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            relative = item.data(QtCore.Qt.UserRole)
            prefix = "★ " if self._is_mark_image(relative) else ""
            item.setText(prefix + relative)

    def _refresh_mark_status(self):
        if self.current_mark_name:
            self.mark_status_label.setText(
                "当前自定义mark：%s" % self.current_mark_name
            )
        else:
            self.mark_status_label.setText("当前自定义mark：未设置")

    def _set_mark(self, clear):
        if clear:
            name = ""
        else:
            item = self.list_widget.currentItem()
            if item is None:
                QtWidgets.QMessageBox.information(
                    self, "未选择图片", "请先在列表中选择要设为 mark 的图片。"
                )
                return
            name = _image_stem(item.data(QtCore.Qt.UserRole))
        self.current_mark_name = name
        if self.on_mark_set is not None:
            self.on_mark_set(name)
        self._apply_mark_prefixes()
        self._refresh_mark_status()

    # ---- 采集 ------------------------------------------------------- #
    def _on_capture(self):
        if self.capture_opener is None:
            return
        saved = self.capture_opener(self.folder_path)
        if saved:
            self._load_images()
            QtWidgets.QMessageBox.information(
                self, "采集完成", "已保存模板：\n%s" % saved
            )

    # ---- 删除 ------------------------------------------------------- #
    def _delete_selected(self):
        item = self.list_widget.currentItem()
        if item is None:
            QtWidgets.QMessageBox.information(
                self, "未选择图片", "请先在列表中选择要删除的图片。"
            )
            return
        relative = item.data(QtCore.Qt.UserRole)
        image_path = os.path.join(
            self.folder_path, *relative.replace("\\", "/").split("/")
        )

        start_nodes, step_nodes, flow_error = find_flow_references(
            self.folder_path, relative
        )
        if flow_error:
            QtWidgets.QMessageBox.warning(
                self,
                "流程文件异常",
                "img_flow.json 无法解析：%s\n删除后流程中的相关引用将失效。"
                % flow_error,
            )
        elif start_nodes:
            QtWidgets.QMessageBox.warning(
                self,
                "无法删除",
                "图片 [ %s ] 是流程节点的开始图片（节点：%s）。\n"
                "请先在“流程体”页删除或修改这些节点，再删除图片。"
                % (relative, "、".join(start_nodes)),
            )
            return

        message = (
            "确定删除模板图片 [ %s ] 吗？\n"
            "将同时清理 img_pos.json / img_order.json 中的对应条目。"
            % relative
        )
        if step_nodes:
            message += (
                "\n该图片还被流程节点 [ %s ] 的步骤引用，"
                "删除时会自动移除这些步骤。"
                % "、".join(step_nodes)
            )
        answer = QtWidgets.QMessageBox.question(
            self, "删除确认", message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return

        try:
            os.remove(image_path)
        except OSError as error:
            QtWidgets.QMessageBox.warning(
                self, "删除失败", "无法删除图片文件：\n%s" % error
            )
            return
        try:
            remove_image_order_entry(self.folder_path, relative)
            remove_img_pos_entry(self.folder_path, _image_stem(relative))
            if step_nodes:
                remove_flow_steps(self.folder_path, relative)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.warning(
                self, "清理引用失败", "图片已删除，但清理配置时出错：\n%s" % error
            )

        row = self.list_widget.currentRow()
        self.list_widget.takeItem(row)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(min(row, self.list_widget.count() - 1))
        else:
            self._update_preview()
