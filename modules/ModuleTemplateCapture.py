# -*- coding: utf-8 -*-
"""模板采集工具：抓取目标窗口/设备整屏截图，框选区域保存为模板图。

流程：主界面点「采集模板」→ 后台抓取当前目标窗口（Windows）或设备（ADB）
的整屏截图 → 对话框内拖拽框选 → 命名（可选 flag 标记）→ 保存到当前目标
模板目录；flag 非空时同步写入该目录 img_pos.json。

写盘遵循项目中文路径约定：cv2.imencode + ndarray.tofile，不使用 cv2.imwrite。
"""
import json
import os
import re

import cv2
import numpy as np

from PyQt5 import QtCore, QtGui, QtWidgets

from modules.ModuleGetScreenCapture import GetScreenCapture
from modules.ModuleHandleSet import HandleSet

IMAGE_EXT = ".jpg"
JPEG_QUALITY = 95
MIN_REGION_SIZE = 8      # 小于该尺寸的选区拒绝保存
SUGGEST_MIN_SIZE = 30    # 建议尺寸下限（仅提示，不强制）
SUGGEST_MAX_SIZE = 200   # 建议尺寸上限（仅提示，不强制）


# ----------------------------- 纯函数（可单测） --------------------------- #
def sanitize_image_name(name):
    """清理模板名称：去扩展名、去非法字符；结果为空时抛 ValueError。"""
    name = str(name or "").strip()
    name = re.sub(r"\.(jpg|jpeg|png)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r'[\\/:*?"<>|]+', "", name).strip()
    if not name:
        raise ValueError("模板名称不能为空")
    return name


def next_available_name(folder_path, base="capture"):
    """返回 folder 下未占用的 base_N 名称（N 从 1 起）。"""
    number = 1
    while os.path.exists(
        os.path.join(folder_path, "%s_%d%s" % (base, number, IMAGE_EXT))
    ):
        number += 1
    return "%s_%d" % (base, number)


def crop_screen_image(image, rect):
    """按 (x1, y1, x2, y2) 裁剪，自动收敛到图片边界；选区过小返回 None。"""
    height, width = image.shape[:2]
    x1, x2 = sorted((int(rect[0]), int(rect[2])))
    y1, y2 = sorted((int(rect[1]), int(rect[3])))
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    if x2 - x1 < MIN_REGION_SIZE or y2 - y1 < MIN_REGION_SIZE:
        return None
    return image[y1:y2, x1:x2]


def save_template_image(folder_path, name, image):
    """保存模板 jpg（中文路径安全），返回完整路径。"""
    path = os.path.join(folder_path, name + IMAGE_EXT)
    ok, buffer = cv2.imencode(
        IMAGE_EXT, image, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    )
    if not ok:
        raise OSError("图片编码失败")
    buffer.tofile(path)
    return path


def merge_flag_into_img_pos(folder_path, image_name, flag):
    """在目录 img_pos.json 中为 image_name 设置 flag；文件不存在则创建。

    已有同名条目只更新 flag、保留其他字段；无同名条目则按
    real_pos/click_pos 为空的形式追加（与现有标记条目结构一致）。
    """
    json_path = os.path.join(folder_path, "img_pos.json")
    entries = []
    if os.path.isfile(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                entries = [item for item in data if isinstance(item, dict)]
        except (OSError, ValueError) as error:
            raise ValueError("读取 img_pos.json 失败：%s" % error)

    updated = False
    for entry in entries:
        if entry.get("name") == image_name:
            entry["flag"] = flag
            updated = True
            break
    if not updated:
        entries.append(
            {"name": image_name, "real_pos": [], "click_pos": [], "flag": flag}
        )

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=4)
    return json_path


def capture_screen_image(connect_mod, hwnd):
    """抓取整屏截图，返回 (灰度图, 来源描述)；失败抛 ValueError。

    :param hwnd: Windows 模式的目标窗口句柄（ADB 模式忽略，自动取首个设备）
    """
    if connect_mod == "Windows程序":
        if not hwnd:
            raise ValueError("请先选择待匹配目标窗口！")
        handle_set = HandleSet("", hwnd)
        pos = handle_set.get_handle_pos
        if not pos:
            raise ValueError("目标窗口已关闭或无法获取窗口位置")
        width = int(pos[2] - pos[0])
        height = int(pos[3] - pos[1])
        if width <= 0 or height <= 0:
            raise ValueError("目标窗口尺寸异常")
        capture = GetScreenCapture(hwnd, width, height)
        image = capture.window_screen()
        source = "窗口 [ %s ]（句柄 %d）" % (
            HandleSet.get_handle_title(hwnd) or "未知窗口", hwnd
        )
    else:
        status, devices = HandleSet.adb_device_status()
        if not status:
            raise ValueError("未检测到安卓设备：%s" % devices)
        image = GetScreenCapture().adb_screen(devices[0])
        source = "设备 [ %s ]" % devices[0]
    if image is None or image.size == 0:
        raise ValueError("截图失败，请检查目标窗口/设备状态")
    return image, source


# --------------------------------- 界面 ----------------------------------- #
FLAG_OPTIONS = (
    ("", "（无标记）"),
    ("start", "start（回合开始）"),
    ("skip", "skip（跳过点击）"),
    ("mark", "mark（每轮标记一次）"),
    ("stop", "stop（停止脚本）"),
)


def _gray_ndarray_to_qimage(image):
    """单通道 ndarray 转 QImage（返回 QImage 同时返回原数组引用保活）。"""
    image = np.ascontiguousarray(image)
    height, width = image.shape[:2]
    qimage = QtGui.QImage(
        image.data, width, height, width, QtGui.QImage.Format_Grayscale8
    )
    return qimage, image


class _RegionSelectLabel(QtWidgets.QLabel):
    """展示截图并支持拖拽框选；松开鼠标时发出原图坐标 (x1, y1, x2, y2)。"""

    selection_changed = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super(_RegionSelectLabel, self).__init__(parent)
        self.setObjectName("capture_region_label")
        self.setCursor(QtCore.Qt.CrossCursor)
        self._scale = 1.0
        self._origin = None
        self._rubber_band = None
        self._keep_image = None  # QImage 底层数组引用，防止被回收

    def set_capture_image(self, cv_image, max_size=(960, 560)):
        height, width = cv_image.shape[:2]
        scale = min(1.0, float(max_size[0]) / width, float(max_size[1]) / height)
        self._scale = scale
        display = cv_image
        if scale < 1.0:
            display = cv2.resize(
                cv_image,
                (max(1, int(width * scale)), max(1, int(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        qimage, keep = _gray_ndarray_to_qimage(display)
        self._keep_image = qimage
        self.setPixmap(QtGui.QPixmap.fromImage(qimage))
        self.setFixedSize(display.shape[1], display.shape[0])
        self._clear_selection()

    def _clear_selection(self):
        self._origin = None
        if self._rubber_band is None:
            self._rubber_band = QtWidgets.QRubberBand(
                QtWidgets.QRubberBand.Rectangle, self
            )
        self._rubber_band.hide()
        self.selection_changed.emit(None)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.pixmap():
            self._origin = event.pos()
            self._rubber_band.setGeometry(
                QtCore.QRect(self._origin, QtCore.QSize())
            )
            self._rubber_band.show()

    def mouseMoveEvent(self, event):
        if self._origin is not None:
            self._rubber_band.setGeometry(
                QtCore.QRect(self._origin, event.pos()).normalized()
            )

    def mouseReleaseEvent(self, event):
        if self._origin is None:
            return
        rect = self._rubber_band.geometry().normalized()
        self._origin = None
        self._rubber_band.hide()
        scale = self._scale or 1.0
        self.selection_changed.emit(
            (
                int(rect.left() / scale),
                int(rect.top() / scale),
                int(rect.right() / scale),
                int(rect.bottom() / scale),
            )
        )


class TemplateCaptureDialog(QtWidgets.QDialog):
    """框选截图区域并保存为当前目标目录的模板图。"""

    def __init__(self, folder_path, image, source_label, parent=None):
        super(TemplateCaptureDialog, self).__init__(parent)
        self.folder_path = folder_path
        self.image = image
        self.saved_path = None
        self.saved_flag = ""
        self._selection = None
        self._preview_keep = None

        self.setWindowTitle("采集模板")
        self.setMinimumWidth(1000)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        header = QtWidgets.QLabel(
            "来源：%s。按住左键在截图上拖拽框选模板区域，选完在下方命名保存；"
            "建议尺寸 %d×%d ~ %d×%d（现有模板常见范围）。"
            % (source_label, SUGGEST_MIN_SIZE, SUGGEST_MIN_SIZE,
               SUGGEST_MAX_SIZE, SUGGEST_MAX_SIZE)
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self.region_label = _RegionSelectLabel()
        self.region_label.selection_changed.connect(self._on_selection_changed)
        self.region_label.set_capture_image(image)
        layout.addWidget(self.region_label)

        self.selection_info = QtWidgets.QLabel("未选择区域")
        layout.addWidget(self.selection_info)

        preview_row = QtWidgets.QHBoxLayout()
        self.preview_image = QtWidgets.QLabel("框选后显示预览")
        self.preview_image.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_image.setFixedSize(220, 150)
        self.preview_image.setFrameShape(QtWidgets.QFrame.StyledPanel)
        preview_row.addWidget(self.preview_image)

        form_layout = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setText(next_available_name(self.folder_path))
        form_layout.addRow("模板名称", self.name_edit)
        self.flag_combo = QtWidgets.QComboBox()
        for flag, label in FLAG_OPTIONS:
            self.flag_combo.addItem(label, flag)
        form_layout.addRow("flag 标记", self.flag_combo)
        self.size_hint_label = QtWidgets.QLabel("")
        form_layout.addRow("尺寸提示", self.size_hint_label)
        preview_row.addLayout(form_layout, 1)
        layout.addLayout(preview_row)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch(1)
        self.save_button = QtWidgets.QPushButton("保存模板")
        self.cancel_button = QtWidgets.QPushButton("取消")
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)

        self.save_button.clicked.connect(self._on_save)
        self.cancel_button.clicked.connect(self.reject)

    def _on_selection_changed(self, rect):
        if rect is None:
            self._selection = None
            self.selection_info.setText("未选择区域")
            self.preview_image.setPixmap(QtGui.QPixmap())
            self.preview_image.setText("框选后显示预览")
            self.size_hint_label.clear()
            return
        self._selection = rect
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        self.selection_info.setText(
            "选区：%d × %d 像素（原图坐标）" % (width, height)
        )

        crop = crop_screen_image(self.image, rect)
        if crop is None:
            self.size_hint_label.setText(
                "选区过小，请重新框选（至少 %d×%d）"
                % (MIN_REGION_SIZE, MIN_REGION_SIZE)
            )
            self.preview_image.setPixmap(QtGui.QPixmap())
            self.preview_image.setText("框选后显示预览")
            return

        hint = ""
        if not (
            SUGGEST_MIN_SIZE <= width <= SUGGEST_MAX_SIZE
            and SUGGEST_MIN_SIZE <= height <= SUGGEST_MAX_SIZE
        ):
            hint = "（建议 %d×%d ~ %d×%d）" % (
                SUGGEST_MIN_SIZE, SUGGEST_MIN_SIZE,
                SUGGEST_MAX_SIZE, SUGGEST_MAX_SIZE,
            )
        self.size_hint_label.setText("尺寸 %d × %d %s" % (width, height, hint))

        preview_height, preview_width = crop.shape[:2]
        preview_scale = min(1.0, 208.0 / preview_width, 138.0 / preview_height)
        if preview_scale < 1.0:
            crop = cv2.resize(
                crop,
                (
                    max(1, int(preview_width * preview_scale)),
                    max(1, int(preview_height * preview_scale)),
                ),
                interpolation=cv2.INTER_AREA,
            )
        qimage, keep = _gray_ndarray_to_qimage(crop)
        self._preview_keep = keep
        self.preview_image.setText("")
        self.preview_image.setPixmap(QtGui.QPixmap.fromImage(qimage))

    def _on_save(self):
        if self._selection is None:
            QtWidgets.QMessageBox.warning(
                self, "未选择区域", "请先在截图上框选模板区域。"
            )
            return
        crop = crop_screen_image(self.image, self._selection)
        if crop is None:
            QtWidgets.QMessageBox.warning(
                self, "选区无效", "选区过小或无效，请重新框选。"
            )
            return
        try:
            name = sanitize_image_name(self.name_edit.text())
        except ValueError as error:
            QtWidgets.QMessageBox.warning(self, "名称无效", str(error))
            return
        path = os.path.join(self.folder_path, name + IMAGE_EXT)
        if os.path.exists(path):
            answer = QtWidgets.QMessageBox.question(
                self,
                "覆盖确认",
                "模板 [ %s ] 已存在，要覆盖吗？" % name,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return
        try:
            saved = save_template_image(self.folder_path, name, crop)
            flag = self.flag_combo.currentData() or ""
            if flag:
                merge_flag_into_img_pos(self.folder_path, name, flag)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "保存失败", str(error))
            return
        self.saved_path = saved
        self.saved_flag = flag
        self.accept()
