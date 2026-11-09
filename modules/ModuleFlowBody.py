# -*- coding: utf-8 -*-
"""流程体配置读写与编辑界面。"""
import json
import os
import tempfile

from PyQt5 import QtCore, QtGui, QtWidgets

from modules.ModuleGetTargetInfo import list_target_image_files


FLOW_BODY_FILE = "img_flow.json"
FLOW_ACTIONS = (
    ("click", "点击"),
    ("skip", "跳过点击"),
    ("stop", "停止脚本"),
)
FLOW_ACTION_LABELS = dict(FLOW_ACTIONS)
DEFAULT_NEXT = ""


def normalize_image_key(value):
    return str(value or "").replace("\\", "/").strip()


def image_key(image_path, folder_path):
    return normalize_image_key(os.path.relpath(image_path, folder_path))


def validate_flow_steps(steps):
    if not isinstance(steps, list):
        raise ValueError("流程体 steps 必须是列表")

    normalized_steps = []
    seen_images = set()
    valid_actions = {action for action, _label in FLOW_ACTIONS}
    for row_number, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise ValueError("第 %d 条流程规则格式无效" % row_number)
        raw_image = step.get("image")
        action = step.get("action")
        raw_next = step.get("next")
        if not isinstance(raw_image, str):
            raise ValueError("第 %d 条流程规则的识别图片无效" % row_number)
        if raw_next is not None and not isinstance(raw_next, str):
            raise ValueError("第 %d 条流程规则的下一步图片无效" % row_number)
        image = normalize_image_key(raw_image)
        next_image = normalize_image_key(raw_next)
        if not image:
            raise ValueError("第 %d 条流程规则未选择识别图片" % row_number)
        if image in seen_images:
            raise ValueError("识别图片重复：%s" % image)
        if not isinstance(action, str) or action not in valid_actions:
            raise ValueError("第 %d 条流程规则的操作无效" % row_number)
        seen_images.add(image)
        normalized_steps.append(
            {"image": image, "action": action, "next": next_image}
        )
    return normalized_steps


def load_flow_config(folder_path):
    """读取模板目录下的流程体配置；不存在配置时保持旧版顺序行为。"""
    config_path = os.path.join(folder_path, FLOW_BODY_FILE)
    if not os.path.isfile(config_path):
        return []

    try:
        with open(config_path, "r", encoding="utf-8-sig") as flow_file:
            data = json.load(flow_file)
    except (OSError, ValueError) as error:
        raise ValueError("读取流程体文件失败 [%s]：%s" % (config_path, error))

    if not isinstance(data, dict):
        raise ValueError("流程体文件格式无效：根节点必须是对象")
    if data.get("version", 1) != 1:
        raise ValueError("不支持的流程体文件版本：%s" % data.get("version"))
    return validate_flow_steps(data.get("steps", []))


def save_flow_config(folder_path, steps):
    """校验并原子保存流程体，避免写入中断留下损坏文件。"""
    if not folder_path or not os.path.isdir(folder_path):
        raise ValueError("请先选择有效的模板文件夹")

    normalized_steps = validate_flow_steps(steps)
    config_path = os.path.join(folder_path, FLOW_BODY_FILE)
    temporary_path = None
    try:
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=".img_flow_", suffix=".tmp", dir=folder_path
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as flow_file:
            json.dump(
                {"version": 1, "steps": normalized_steps},
                flow_file,
                ensure_ascii=False,
                indent=2,
            )
            flow_file.write("\n")
        os.replace(temporary_path, config_path)
        temporary_path = None
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


def resolve_next_index(target_index, image_keys, flow_steps):
    """确定匹配成功后下一轮优先检查的模板索引。"""
    if not image_keys:
        return 0

    current_key = image_keys[target_index]
    step = flow_steps.get(current_key, {})
    next_key = step.get("next", "")
    if next_key in image_keys:
        return image_keys.index(next_key)
    return (target_index + 1) % len(image_keys)


def has_configured_next_image(target_index, image_keys, flow_steps):
    if not image_keys:
        return False
    step = flow_steps.get(image_keys[target_index], {})
    next_key = step.get("next", "")
    return bool(next_key and next_key in image_keys)


class FlowBodyEditor(QtWidgets.QWidget):
    """在设置页内编辑并保存模板目录对应的流程规则。"""

    def __init__(self, parent=None):
        super(FlowBodyEditor, self).__init__(parent)
        self.folder_path = ""
        self.image_keys = []
        self.image_paths = {}
        self.image_icons = {}
        self.flow_steps = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.path_label = QtWidgets.QLabel("请先选择有效的模板文件夹")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        hint = QtWidgets.QLabel(
            "每张图片可设置匹配后的操作及下一步图片。"
            "可用上移/下移整理步骤；实际识别跳转由“下一步走哪”决定。"
            "默认下一步按原识别顺序扫描。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QtWidgets.QTableWidget(0, 3, self)
        self.table.setObjectName("flow_body_table")
        self.table.setHorizontalHeaderLabels(["识别图片", "执行操作", "下一步"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        button_row = QtWidgets.QHBoxLayout()
        self.move_up_button = QtWidgets.QPushButton("上移")
        self.move_down_button = QtWidgets.QPushButton("下移")
        self.add_button = QtWidgets.QPushButton("添加规则")
        self.delete_button = QtWidgets.QPushButton("删除选中")
        self.save_button = QtWidgets.QPushButton("保存流程")
        button_row.addWidget(self.move_up_button)
        button_row.addWidget(self.move_down_button)
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.delete_button)
        button_row.addStretch(1)
        button_row.addWidget(self.save_button)
        layout.addLayout(button_row)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.move_up_button.clicked.connect(lambda: self._move_rule(-1))
        self.move_down_button.clicked.connect(lambda: self._move_rule(1))
        self.add_button.clicked.connect(self._add_rule)
        self.delete_button.clicked.connect(self._delete_rule)
        self.save_button.clicked.connect(self._save)
        self.table.currentCellChanged.connect(
            lambda _row, _column, _previous_row, _previous_column:
            self._update_move_buttons()
        )
        self._update_enabled_state()

    def set_target_folder(self, folder_path):
        self.folder_path = folder_path or ""
        self.image_keys = []
        self.image_paths = {}
        self.image_icons = {}
        self.flow_steps = []
        self.table.setRowCount(0)
        self.status_label.clear()

        if not self.folder_path or not os.path.isdir(self.folder_path):
            self.path_label.setText("请先选择有效的模板文件夹")
            self._update_enabled_state()
            return

        self.path_label.setText(
            "当前模板目录：%s\n流程文件：%s"
            % (
                self.folder_path,
                os.path.join(self.folder_path, FLOW_BODY_FILE),
            )
        )
        image_paths = list_target_image_files(
            self.folder_path, natural_sort=True
        )
        self.image_keys = [
            image_key(image_path, self.folder_path) for image_path in image_paths
        ]
        self.image_paths = dict(zip(self.image_keys, image_paths))
        try:
            self.flow_steps = load_flow_config(self.folder_path)
        except ValueError as error:
            self.status_label.setText(str(error))
            self._update_enabled_state()
            return

        self._populate_table()
        if not self.image_keys:
            self.status_label.setText("当前模板目录中没有可用图片。")
        elif not self.flow_steps:
            self.status_label.setText("尚无流程规则；保存后写入 img_flow.json。")
        self._update_enabled_state()

    def _all_image_keys(self):
        keys = list(self.image_keys)
        for step in self.flow_steps:
            for key in (step["image"], step["next"]):
                if key and key not in keys:
                    keys.append(key)
        return keys

    @staticmethod
    def _image_label(key, available_keys):
        if key and key not in available_keys:
            return "缺失图片：%s" % key
        return key

    def _create_image_combo(self, selected_key="", allow_default=False):
        combo = QtWidgets.QComboBox()
        combo.setIconSize(QtCore.QSize(48, 36))
        available_keys = set(self.image_keys)
        if allow_default:
            combo.addItem("原识别顺序（下一张）", DEFAULT_NEXT)
        for key in self._all_image_keys():
            icon = self._image_icon(key)
            combo.addItem(icon, self._image_label(key, available_keys), key)
        selected_index = combo.findData(selected_key)
        if selected_index >= 0:
            combo.setCurrentIndex(selected_index)
        elif allow_default:
            combo.setCurrentIndex(0)
        return combo

    def _image_icon(self, key):
        if key not in self.image_icons:
            image_path = self.image_paths.get(key)
            icon = QtGui.QIcon()
            if image_path:
                reader = QtGui.QImageReader(image_path)
                source_size = reader.size()
                if source_size.isValid():
                    reader.setScaledSize(
                        source_size.scaled(
                            QtCore.QSize(96, 72), QtCore.Qt.KeepAspectRatio
                        )
                    )
                image = reader.read()
                if not image.isNull():
                    icon = QtGui.QIcon(QtGui.QPixmap.fromImage(image))
            self.image_icons[key] = icon
        return self.image_icons[key]

    def _populate_table(self):
        self.table.setRowCount(0)
        for step in self.flow_steps:
            self._insert_rule(self.table.rowCount(), step)

    def _add_rule(self):
        if not self.image_keys:
            return
        row = self.table.rowCount()
        self._insert_rule(
            row,
            {"image": self.image_keys[0], "action": "click", "next": ""},
        )
        self.table.selectRow(row)

    def _insert_rule(self, row, step):
        self.table.insertRow(row)
        self.table.setCellWidget(
            row, 0, self._create_image_combo(step["image"])
        )
        action_combo = QtWidgets.QComboBox()
        for action, label in FLOW_ACTIONS:
            action_combo.addItem(label, action)
        action_index = action_combo.findData(step["action"])
        if action_index >= 0:
            action_combo.setCurrentIndex(action_index)
        self.table.setCellWidget(row, 1, action_combo)
        self.table.setCellWidget(
            row, 2, self._create_image_combo(step["next"], allow_default=True)
        )
        next_combo = self.table.cellWidget(row, 2)
        next_combo.setProperty("previousData", next_combo.currentData())
        next_combo.currentIndexChanged.connect(
            lambda _index, combo=next_combo: self._on_next_image_changed(combo)
        )

    def _read_rule(self, row):
        return {
            "image": self.table.cellWidget(row, 0).currentData(),
            "action": self.table.cellWidget(row, 1).currentData(),
            "next": self.table.cellWidget(row, 2).currentData(),
        }

    def _on_next_image_changed(self, next_combo):
        row = next(
            (
                index
                for index in range(self.table.rowCount())
                if self.table.cellWidget(index, 2) is next_combo
            ),
            -1,
        )
        if row < 0:
            return

        selected_image = next_combo.currentData()
        previous_image = next_combo.property("previousData")
        next_row = row + 1
        if selected_image:
            expected_row = (
                next_row if next_row < self.table.rowCount() else -1
            )
            image_rows = [
                index
                for index in range(self.table.rowCount())
                if index != expected_row
                and self.table.cellWidget(index, 0).currentData() == selected_image
            ]
            if image_rows:
                next_combo.blockSignals(True)
                previous_index = next_combo.findData(previous_image)
                if previous_index >= 0:
                    next_combo.setCurrentIndex(previous_index)
                next_combo.blockSignals(False)
                QtWidgets.QMessageBox.warning(
                    self,
                    "图片重复",
                    "所选下一步图片已被其他流程行使用，不能重复识别。",
                )
                return

            if expected_row >= 0:
                next_image_combo = self.table.cellWidget(expected_row, 0)
                image_index = next_image_combo.findData(selected_image)
                if image_index >= 0:
                    next_image_combo.setCurrentIndex(image_index)

        next_combo.setProperty("previousData", selected_image)

    def _move_rule(self, delta):
        row = self.table.currentRow()
        target_row = row + delta
        if row < 0 or target_row < 0 or target_row >= self.table.rowCount():
            return

        steps = [
            self._read_rule(index) for index in range(self.table.rowCount())
        ]
        steps[row], steps[target_row] = steps[target_row], steps[row]
        self.table.setRowCount(0)
        for step in steps:
            self._insert_rule(self.table.rowCount(), step)
        self.table.selectRow(target_row)

    def _delete_rule(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            if self.table.rowCount():
                self.table.selectRow(min(row, self.table.rowCount() - 1))
            else:
                self._update_move_buttons()

    def _save(self):
        steps = []
        for row in range(self.table.rowCount()):
            steps.append(self._read_rule(row))
        try:
            save_flow_config(self.folder_path, steps)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "保存失败", str(error))
            return

        self.flow_steps = validate_flow_steps(steps)
        self.status_label.setText(
            "已保存 %d 条规则：%s"
            % (len(self.flow_steps), os.path.join(self.folder_path, FLOW_BODY_FILE))
        )
        self._populate_table()

    def _update_enabled_state(self):
        enabled = bool(self.folder_path and os.path.isdir(self.folder_path))
        self.table.setEnabled(enabled)
        self.move_up_button.setEnabled(enabled)
        self.move_down_button.setEnabled(enabled)
        self.add_button.setEnabled(enabled and bool(self.image_keys))
        self.delete_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self._update_move_buttons()

    def _update_move_buttons(self):
        row = self.table.currentRow()
        row_count = self.table.rowCount()
        self.move_up_button.setEnabled(row > 0)
        self.move_down_button.setEnabled(0 <= row < row_count - 1)
