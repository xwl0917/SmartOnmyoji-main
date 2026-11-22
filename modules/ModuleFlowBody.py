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
    ("esc", "按下ESC键"),
    ("stop", "停止脚本"),
)
FLOW_ACTION_LABELS = dict(FLOW_ACTIONS)
DEFAULT_NEXT = ""


def normalize_image_key(value):
    return str(value or "").replace("\\", "/").strip()


def image_key(image_path, folder_path):
    return normalize_image_key(os.path.relpath(image_path, folder_path))


def validate_flow_steps(steps, row_prefix="流程步骤"):
    if not isinstance(steps, list):
        raise ValueError("流程体 steps 必须是列表")

    normalized_steps = []
    seen_images = set()
    valid_actions = {action for action, _label in FLOW_ACTIONS}
    for row_number, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise ValueError("第 %d 条%s格式无效" % (row_number, row_prefix))
        raw_image = step.get("image")
        action = step.get("action")
        raw_next = step.get("next")
        if not isinstance(raw_image, str):
            raise ValueError("第 %d 条%s的识别图片无效" % (row_number, row_prefix))
        if raw_next is not None and not isinstance(raw_next, str):
            raise ValueError("第 %d 条%s的下一步图片无效" % (row_number, row_prefix))
        image = normalize_image_key(raw_image)
        next_image = normalize_image_key(raw_next)
        if not image:
            raise ValueError("第 %d 条%s未选择识别图片" % (row_number, row_prefix))
        if image in seen_images:
            raise ValueError("%s中识别图片重复：%s" % (row_prefix, image))
        if not isinstance(action, str) or action not in valid_actions:
            raise ValueError("第 %d 条%s的操作无效" % (row_number, row_prefix))
        seen_images.add(image)
        normalized_steps.append(
            {"image": image, "action": action, "next": next_image}
        )
    return normalized_steps


def validate_flow_nodes(nodes):
    if not isinstance(nodes, list):
        raise ValueError("流程体 nodes 必须是列表")

    normalized_nodes = []
    seen_names = set()
    seen_starts = set()
    valid_actions = {action for action, _label in FLOW_ACTIONS}
    for node_number, node in enumerate(nodes, 1):
        if not isinstance(node, dict):
            raise ValueError("第 %d 个流程节点格式无效" % node_number)
        name = str(node.get("name") or "").strip()
        next_node = node.get("next_node", "")
        if not name or name in seen_names:
            raise ValueError("流程节点名称不能为空或重复：%s" % name)
        if not isinstance(next_node, str):
            raise ValueError("流程节点 [%s] 的结束跳转无效" % name)
        steps = validate_flow_steps(
            node.get("steps", []), "流程节点 [%s] 规则" % name
        )
        if not steps:
            raise ValueError("流程节点 [%s] 至少需要一条规则" % name)
        start_image = steps[0]["image"]
        if start_image in seen_starts:
            raise ValueError("流程节点开始图片重复：%s" % start_image)
        for step in steps:
            if step["action"] not in valid_actions:
                raise ValueError("流程节点 [%s] 的操作无效" % name)
        seen_names.add(name)
        seen_starts.add(start_image)
        normalized_nodes.append(
            {"name": name, "steps": steps, "next_node": next_node.strip()}
        )

    node_names = {node["name"] for node in normalized_nodes}
    for node in normalized_nodes:
        if node["next_node"] and node["next_node"] not in node_names:
            raise ValueError(
                "流程节点 [%s] 的结束跳转节点不存在：%s"
                % (node["name"], node["next_node"])
            )
    return normalized_nodes


def _legacy_steps_to_nodes(steps):
    normalized_steps = validate_flow_steps(steps)
    if not normalized_steps:
        return []
    return [{"name": "流程1", "steps": normalized_steps, "next_node": ""}]


def load_flow_config(folder_path):
    """读取流程节点；自动兼容旧版单流程 steps 配置。"""
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
    version = data.get("version", 1)
    if version == 1:
        return _legacy_steps_to_nodes(data.get("steps", []))
    if version == 2:
        return validate_flow_nodes(data.get("nodes", []))
    raise ValueError("不支持的流程体文件版本：%s" % version)


def save_flow_config(folder_path, nodes):
    """校验并原子保存流程节点，避免写入中断留下损坏文件。"""
    if not folder_path or not os.path.isdir(folder_path):
        raise ValueError("请先选择有效的模板文件夹")

    normalized_nodes = validate_flow_nodes(nodes)
    config_path = os.path.join(folder_path, FLOW_BODY_FILE)
    temporary_path = None
    try:
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=".img_flow_", suffix=".tmp", dir=folder_path
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as flow_file:
            json.dump(
                {"version": 2, "nodes": normalized_nodes},
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


class FlowBodyRuntime:
    """Tracks node entry, step progression, interruption, and node transitions."""

    def __init__(self, image_keys, nodes):
        self.image_keys = list(image_keys)
        self.nodes = validate_flow_nodes(nodes) if nodes else []
        self.image_indices = {
            key: index for index, key in enumerate(self.image_keys)
        }
        self.nodes_by_name = {node["name"]: node for node in self.nodes}
        self.start_nodes = {}
        self.steps_by_node = {}
        for node in self.nodes:
            steps = node["steps"]
            self.steps_by_node[node["name"]] = {
                step["image"]: step for step in steps
            }
            start_image = steps[0]["image"]
            if start_image in self.image_indices:
                self.start_nodes[start_image] = node["name"]
        self.active_node = ""
        self.expected_image = ""
        self.last_matched_node = ""

    def reset(self):
        self.active_node = ""
        self.expected_image = ""
        self.last_matched_node = ""

    def candidate_indices(self, last_matched_index=-1):
        if not self.nodes:
            return None

        if self.active_node:
            # 节点内期望图优先：当前步骤的期望图排在最前，先被识别；
            # 其他节点的开始图只作为期望图不在屏幕上时的兜底，
            # 避免期望图与开始图同时在屏时节点被误打断。
            candidates = []
            expected_index = self.image_indices.get(self.expected_image)
            if expected_index is not None:
                candidates.append(expected_index)
            for start_image, node_name in self.start_nodes.items():
                if node_name == self.active_node:
                    continue
                start_index = self.image_indices.get(start_image)
                if start_index is not None and start_index not in candidates:
                    candidates.append(start_index)
            if not candidates:
                self.reset()
                return self.candidate_indices(last_matched_index)
            return candidates

        start_indices = [
            self.image_indices[key]
            for key in self.start_nodes
            if key in self.image_indices
        ]
        if not self.image_keys:
            return []
        scan_start = (
            (last_matched_index + 1) % len(self.image_keys)
            if last_matched_index >= 0
            else 0
        )
        remaining_indices = [
            (scan_start + offset) % len(self.image_keys)
            for offset in range(len(self.image_keys))
        ]
        return start_indices + [
            index for index in remaining_indices if index not in start_indices
        ]

    def on_match(self, image):
        self.last_matched_node = ""
        node_name = self.start_nodes.get(image)
        if node_name and node_name != self.active_node:
            self.active_node = node_name
            self.last_matched_node = node_name
            step = self.steps_by_node[node_name][image]
            self._advance(node_name, step)
            return step

        if not self.active_node or image != self.expected_image:
            return None

        node_name = self.active_node
        self.last_matched_node = node_name
        step = self.steps_by_node[node_name].get(image)
        if step is None:
            step = {"image": image, "action": "click", "next": ""}
            self._finish_node(node_name)
            return step
        self._advance(node_name, step)
        return step

    def _advance(self, node_name, step):
        node = self.nodes_by_name[node_name]
        if step["next"] and step["next"] in self.image_indices:
            self.expected_image = step["next"]
            return

        node_steps = node["steps"]
        step_index = next(
            index
            for index, candidate in enumerate(node_steps)
            if candidate["image"] == step["image"]
        )
        for candidate in node_steps[step_index + 1 :]:
            if candidate["image"] in self.image_indices:
                self.expected_image = candidate["image"]
                return

        self._finish_node(node_name)

    def _finish_node(self, node_name):
        node = self.nodes_by_name[node_name]
        next_node = node["next_node"]
        if next_node:
            next_start = self.nodes_by_name[next_node]["steps"][0]["image"]
            if next_start in self.image_indices:
                self.active_node = next_node
                self.expected_image = next_start
                return
        self.active_node = ""
        self.expected_image = ""


class FlowNodeImagesDialog(QtWidgets.QDialog):
    """多选模板图片，按列表勾选顺序一键生成流程节点。"""

    def __init__(self, editor, parent=None):
        super(FlowNodeImagesDialog, self).__init__(parent)
        self.editor = editor
        self.result_data = None
        self.setWindowTitle("多选生成节点")
        self.setMinimumWidth(460)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(QtWidgets.QLabel("节点名称"))
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setText(self._default_node_name())
        name_row.addWidget(self.name_edit, 1)
        layout.addLayout(name_row)

        layout.addWidget(QtWidgets.QLabel(
            "勾选需要的图片（可多选）；列表从上到下的勾选图片就是步骤顺序，"
            "选中一项后用上移/下移调整位置。"
        ))

        body_row = QtWidgets.QHBoxLayout()
        self.image_list = QtWidgets.QListWidget()
        self.image_list.setObjectName("flow_node_images_list")
        for key in editor.image_keys:
            item = QtWidgets.QListWidgetItem(editor._image_icon(key), key)
            item.setData(QtCore.Qt.UserRole, key)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.image_list.addItem(item)
        self.image_list.currentItemChanged.connect(self._update_preview)
        body_row.addWidget(self.image_list, 1)

        move_layout = QtWidgets.QVBoxLayout()
        self.move_up_button = QtWidgets.QPushButton("上移")
        self.move_down_button = QtWidgets.QPushButton("下移")
        move_layout.addWidget(self.move_up_button)
        move_layout.addWidget(self.move_down_button)
        move_layout.addStretch(1)
        body_row.addLayout(move_layout)
        layout.addLayout(body_row, 1)

        self.preview_image = QtWidgets.QLabel("选择图片以预览")
        self.preview_image.setObjectName("flow_node_images_preview")
        self.preview_image.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_image.setFixedSize(200, 140)
        self.preview_image.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.preview_name = QtWidgets.QLabel()
        self.preview_name.setWordWrap(True)
        preview_row = QtWidgets.QHBoxLayout()
        preview_row.addWidget(self.preview_image)
        preview_row.addWidget(self.preview_name, 1)
        layout.addLayout(preview_row)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch(1)
        self.ok_button = QtWidgets.QPushButton("生成节点")
        self.cancel_button = QtWidgets.QPushButton("取消")
        button_row.addWidget(self.ok_button)
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)

        self.ok_button.clicked.connect(self._on_accept)
        self.cancel_button.clicked.connect(self.reject)
        self.move_up_button.clicked.connect(lambda: self._move_item(-1))
        self.move_down_button.clicked.connect(lambda: self._move_item(1))

        if self.image_list.count():
            self.image_list.setCurrentRow(0)
        else:
            self._update_preview()

    def _default_node_name(self):
        existing = {node["name"] for node in self.editor.nodes}
        number = 1
        while "流程%d" % number in existing:
            number += 1
        return "流程%d" % number

    def _move_item(self, delta):
        row = self.image_list.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self.image_list.count():
            return
        item = self.image_list.takeItem(row)
        self.image_list.insertItem(target, item)
        self.image_list.setCurrentRow(target)

    def _update_preview(self, current=None, _previous=None):
        if current is None:
            self.preview_image.setPixmap(QtGui.QPixmap())
            self.preview_image.setText("选择图片以预览")
            self.preview_name.clear()
            return
        key = current.data(QtCore.Qt.UserRole)
        image_path = self.editor.image_paths.get(key, "")
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
        self.preview_name.setText(key)
        self.preview_name.setToolTip(image_path)

    def _checked_keys(self):
        return [
            self.image_list.item(row).data(QtCore.Qt.UserRole)
            for row in range(self.image_list.count())
            if self.image_list.item(row).checkState() == QtCore.Qt.Checked
        ]

    def _on_accept(self):
        name = self.name_edit.text().strip()
        if not name or any(node["name"] == name for node in self.editor.nodes):
            QtWidgets.QMessageBox.warning(
                self, "节点名称无效", "节点名称不能为空且不能重复。"
            )
            return
        keys = self._checked_keys()
        if not keys:
            QtWidgets.QMessageBox.warning(
                self, "未选择图片", "请至少勾选一张图片。"
            )
            return
        used_starts = {
            node["steps"][0]["image"] for node in self.editor.nodes
            if node["steps"]
        }
        if keys[0] in used_starts:
            QtWidgets.QMessageBox.warning(
                self,
                "开始图片冲突",
                "首张勾选图片 [ %s ] 已是其他节点的开始图片，"
                "请调整勾选顺序或换一张开始图。" % keys[0],
            )
            return
        self.result_data = (name, keys)
        self.accept()

    def get_result(self):
        return self.result_data


class FlowBodyEditor(QtWidgets.QWidget):
    """在设置页内编辑并保存模板目录对应的流程规则。"""

    def __init__(self, parent=None):
        super(FlowBodyEditor, self).__init__(parent)
        self.folder_path = ""
        self.image_keys = []
        self.image_paths = {}
        self.image_icons = {}
        self.nodes = []
        self.current_node_name = ""

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.path_label = QtWidgets.QLabel("请先选择有效的模板文件夹")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        hint = QtWidgets.QLabel(
            "主循环持续识别每个节点的首条图片。进入节点后按节点步骤识别；"
            "其他节点的开始图片可打断并切换。末尾可跳转到其他节点或返回主循环。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        node_row = QtWidgets.QHBoxLayout()
        node_row.addWidget(QtWidgets.QLabel("流程节点"))
        self.node_combo = QtWidgets.QComboBox()
        self.node_combo.setObjectName("flow_body_node_combo")
        node_row.addWidget(self.node_combo, 1)
        self.add_node_button = QtWidgets.QPushButton("添加节点")
        self.quick_create_button = QtWidgets.QPushButton("多选生成节点")
        self.quick_create_button.setObjectName("flow_body_quick_create_button")
        self.quick_create_button.setToolTip(
            "从模板图片中按顺序勾选多张图，一键生成完整节点"
        )
        self.delete_node_button = QtWidgets.QPushButton("删除节点")
        node_row.addWidget(self.add_node_button)
        node_row.addWidget(self.quick_create_button)
        node_row.addWidget(self.delete_node_button)
        layout.addLayout(node_row)

        end_row = QtWidgets.QHBoxLayout()
        end_row.addWidget(QtWidgets.QLabel("节点结束后"))
        self.end_node_combo = QtWidgets.QComboBox()
        self.end_node_combo.setObjectName("flow_body_end_node_combo")
        self.end_node_combo.addItem("返回主循环", "")
        end_row.addWidget(self.end_node_combo, 1)
        layout.addLayout(end_row)

        self.table = QtWidgets.QTableWidget(0, 3, self)
        self.table.setObjectName("flow_body_table")
        self.table.setHorizontalHeaderLabels(
            ["识别图片（首条为节点开始）", "执行操作", "节点内下一步"]
        )
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
        self.add_button = QtWidgets.QPushButton("添加步骤")
        self.delete_button = QtWidgets.QPushButton("删除选中")
        self.save_button = QtWidgets.QPushButton("保存流程体")
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
        self.add_node_button.clicked.connect(self._add_node)
        self.quick_create_button.clicked.connect(self._on_quick_create_node)
        self.delete_node_button.clicked.connect(self._delete_node)
        self.save_button.clicked.connect(self._save)
        self.node_combo.currentIndexChanged.connect(self._on_node_changed)
        self.end_node_combo.currentIndexChanged.connect(self._save_current_node)
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
        self.nodes = []
        self.current_node_name = ""
        self.table.setRowCount(0)
        self.node_combo.clear()
        self.end_node_combo.clear()
        self.end_node_combo.addItem("返回主循环", "")
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
            self.nodes = load_flow_config(self.folder_path)
        except ValueError as error:
            self.status_label.setText(str(error))
            self._update_enabled_state()
            return

        self._populate_node_combo()
        if self.nodes:
            self.node_combo.setCurrentIndex(0)
            self._show_node(self.nodes[0]["name"])
        if not self.image_keys:
            self.status_label.setText("当前模板目录中没有可用图片。")
        elif not self.nodes:
            self.status_label.setText("尚无流程节点；添加节点后保存流程体。")
        self._update_enabled_state()

    def _all_image_keys(self):
        keys = list(self.image_keys)
        for node in self.nodes:
            for step in node["steps"]:
                if step["image"] not in keys:
                    keys.append(step["image"])
        return keys

    @staticmethod
    def _image_label(key, available_keys):
        if key and key not in available_keys:
            return "缺失图片：%s" % key
        return key

    def _create_image_combo(self, selected_key=""):
        combo = QtWidgets.QComboBox()
        combo.setIconSize(QtCore.QSize(48, 36))
        available_keys = set(self.image_keys)
        for key in self._all_image_keys():
            icon = self._image_icon(key)
            combo.addItem(icon, self._image_label(key, available_keys), key)
        selected_index = combo.findData(selected_key)
        if selected_index >= 0:
            combo.setCurrentIndex(selected_index)
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

    def _populate_node_combo(self):
        self.node_combo.blockSignals(True)
        self.node_combo.clear()
        for node in self.nodes:
            self.node_combo.addItem(node["name"], node["name"])
        self.node_combo.blockSignals(False)

    def _populate_end_node_combo(self, selected_node=""):
        self.end_node_combo.blockSignals(True)
        self.end_node_combo.clear()
        self.end_node_combo.addItem("返回主循环", "")
        for node in self.nodes:
            self.end_node_combo.addItem(node["name"], node["name"])
        index = self.end_node_combo.findData(selected_node)
        self.end_node_combo.setCurrentIndex(max(0, index))
        self.end_node_combo.blockSignals(False)

    def _show_node(self, node_name):
        node = next(
            (item for item in self.nodes if item["name"] == node_name), None
        )
        self.current_node_name = node_name if node else ""
        self.table.setRowCount(0)
        if node is None:
            self._populate_end_node_combo()
            return
        self._populate_end_node_combo(node["next_node"])
        for step in node["steps"]:
            self._insert_rule(self.table.rowCount(), step)

    def _save_current_node(self, _index=None):
        if not self.current_node_name:
            return
        node = next(
            (
                item
                for item in self.nodes
                if item["name"] == self.current_node_name
            ),
            None,
        )
        if node is None:
            return
        node["steps"] = [
            self._read_rule(row) for row in range(self.table.rowCount())
        ]
        node["next_node"] = self.end_node_combo.currentData() or ""

    def _on_node_changed(self, index):
        if index < 0:
            self.current_node_name = ""
            self.table.setRowCount(0)
            self._populate_end_node_combo()
            self._update_enabled_state()
            return
        new_node_name = self.node_combo.itemData(index)
        if new_node_name == self.current_node_name:
            return
        self._save_current_node()
        self._show_node(new_node_name)
        self._update_enabled_state()

    def _used_images(self):
        return {
            self.table.cellWidget(row, 0).currentData()
            for row in range(self.table.rowCount())
        }

    def _add_rule(self):
        if not self.image_keys or not self.current_node_name:
            return
        row = self.table.rowCount()
        used_images = self._used_images()
        image = next(
            (key for key in self.image_keys if key not in used_images),
            self.image_keys[0],
        )
        if row:
            next_image = self.table.cellWidget(row - 1, 2).currentData()
            if next_image in self.image_keys and next_image not in used_images:
                image = next_image
        if image in used_images:
            self.status_label.setText("该节点中的每张识别图片只能添加一次。")
            return
        self._insert_rule(
            row,
            {"image": image, "action": "click", "next": ""},
        )
        self.table.selectRow(row)

    def _on_next_image_changed(self, next_combo):
        """节点末尾规则的“下一步图片”选了尚未使用的新图片时，自动追加该步骤。"""
        row = next(
            (
                index
                for index in range(self.table.rowCount())
                if self.table.cellWidget(index, 2) is next_combo
            ),
            -1,
        )
        if row < 0 or not self.current_node_name:
            return
        selected_image = next_combo.currentData()
        if (
            not selected_image
            or selected_image == DEFAULT_NEXT
            or selected_image not in self.image_keys
            or selected_image in self._used_images()
        ):
            return
        if row != self.table.rowCount() - 1:
            return
        new_row = self.table.rowCount()
        self._insert_rule(
            new_row,
            {"image": selected_image, "action": "click", "next": ""},
        )
        self.status_label.setText("已自动添加下一步骤：%s" % selected_image)
        self.table.selectRow(new_row)

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
        next_combo = QtWidgets.QComboBox()
        next_combo.blockSignals(True)
        next_combo.addItem("按节点顺序（末尾结束）", DEFAULT_NEXT)
        node_images = [
            self.table.cellWidget(index, 0).currentData()
            for index in range(row)
        ]
        if step["image"] not in node_images:
            node_images.append(step["image"])
        next_images = list(self.image_keys)
        next_images.extend(key for key in node_images if key not in next_images)
        node = next(
            (item for item in self.nodes if item["name"] == self.current_node_name),
            None,
        )
        if node:
            next_images.extend(
                step["image"]
                for step in node["steps"]
                if step["image"] not in next_images
            )
        for key in next_images:
            icon = self._image_icon(key)
            next_combo.addItem(
                icon, self._image_label(key, set(self.image_keys)), key
            )
        selected_index = next_combo.findData(step["next"])
        if selected_index >= 0:
            next_combo.setCurrentIndex(selected_index)
        next_combo.blockSignals(False)
        next_combo.currentIndexChanged.connect(
            lambda _index, combo=next_combo: self._on_next_image_changed(combo)
        )
        self.table.setCellWidget(row, 2, next_combo)

    def _add_node(self):
        if not self.image_keys:
            return
        name, accepted = QtWidgets.QInputDialog.getText(
            self, "添加流程节点", "节点名称："
        )
        if not accepted:
            return
        name = name.strip()
        if not name or any(node["name"] == name for node in self.nodes):
            QtWidgets.QMessageBox.warning(
                self, "节点名称无效", "节点名称不能为空且不能重复。"
            )
            return
        self._save_current_node()
        used_starts = {
            node["steps"][0]["image"] for node in self.nodes if node["steps"]
        }
        available_starts = [
            key for key in self.image_keys if key not in used_starts
        ]
        if not available_starts:
            QtWidgets.QMessageBox.information(
                self, "没有可用开始图片", "每个节点必须使用不同的开始图片。"
            )
            return
        start_image, accepted = QtWidgets.QInputDialog.getItem(
            self,
            "选择开始图片",
            "节点开始图片：",
            available_starts,
            0,
            False,
        )
        if not accepted:
            return
        node = {
            "name": name,
            "steps": [{"image": start_image, "action": "click", "next": ""}],
            "next_node": "",
        }
        self.nodes.append(node)
        self._populate_node_combo()
        index = self.node_combo.findData(name)
        self.node_combo.setCurrentIndex(index)
        self._show_node(name)
        self._update_enabled_state()

    def _on_quick_create_node(self):
        if not self.image_keys:
            return
        used_starts = {
            node["steps"][0]["image"] for node in self.nodes if node["steps"]
        }
        if not [key for key in self.image_keys if key not in used_starts]:
            QtWidgets.QMessageBox.information(
                self,
                "没有可用开始图片",
                "每个节点的开始图片不能重复，当前已没有可用的开始图片。",
            )
            return
        dialog = FlowNodeImagesDialog(self, self)
        if dialog.exec_():
            name, keys = dialog.get_result()
            self._create_node_from_images(name, keys)

    def _create_node_from_images(self, name, image_keys_list):
        """按给定图片顺序一键生成节点；失败时状态栏提示并返回 False。"""
        name = str(name or "").strip()
        if not name or any(node["name"] == name for node in self.nodes):
            self.status_label.setText("节点名称不能为空且不能重复。")
            return False
        keys = [key for key in image_keys_list if key in self.image_keys]
        if not keys:
            self.status_label.setText("请至少选择一张模板图片。")
            return False
        used_starts = {
            node["steps"][0]["image"] for node in self.nodes if node["steps"]
        }
        if keys[0] in used_starts:
            self.status_label.setText(
                "开始图片冲突：%s 已是其他节点的开始图片。" % keys[0]
            )
            return False
        self._save_current_node()
        node = {
            "name": name,
            "steps": [
                {"image": key, "action": "click", "next": ""} for key in keys
            ],
            "next_node": "",
        }
        self.nodes.append(node)
        self._populate_node_combo()
        index = self.node_combo.findData(name)
        self.node_combo.setCurrentIndex(index)
        self._show_node(name)
        self._update_enabled_state()
        self.status_label.setText(
            "已生成节点 [%s]，共 %d 步；保存流程体后生效。" % (name, len(keys))
        )
        return True

    def _delete_node(self):
        if not self.current_node_name:
            return
        self._save_current_node()
        self.nodes = [
            node for node in self.nodes if node["name"] != self.current_node_name
        ]
        for node in self.nodes:
            if node["next_node"] == self.current_node_name:
                node["next_node"] = ""
        self.current_node_name = ""
        self._populate_node_combo()
        if self.nodes:
            self.node_combo.setCurrentIndex(0)
            self._show_node(self.nodes[0]["name"])
        else:
            self._show_node("")
        self._update_enabled_state()

    def _read_rule(self, row):
        return {
            "image": self.table.cellWidget(row, 0).currentData(),
            "action": self.table.cellWidget(row, 1).currentData(),
            "next": self.table.cellWidget(row, 2).currentData(),
        }

    def _move_rule(self, delta):
        row = self.table.currentRow()
        target_row = row + delta
        if row < 0 or target_row < 0 or target_row >= self.table.rowCount():
            return

        if target_row == 0 and row != 0:
            QtWidgets.QMessageBox.information(
                self, "开始图片", "节点的首条规则是开始图片，不能移到后面。"
            )
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
            if row == 0:
                QtWidgets.QMessageBox.information(
                    self, "开始图片", "节点的首条规则是开始图片，不能删除。"
                )
                return
            self.table.removeRow(row)
            if self.table.rowCount():
                self.table.selectRow(min(row, self.table.rowCount() - 1))
            else:
                self._update_move_buttons()

    def _save(self):
        self._save_current_node()
        try:
            self.nodes = validate_flow_nodes(self.nodes)
            save_flow_config(self.folder_path, self.nodes)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "保存失败", str(error))
            return

        self.status_label.setText(
            "已保存 %d 个流程节点：%s"
            % (len(self.nodes), os.path.join(self.folder_path, FLOW_BODY_FILE))
        )
        self._populate_node_combo()
        index = self.node_combo.findData(self.current_node_name)
        if index >= 0:
            self.node_combo.setCurrentIndex(index)
            self._show_node(self.current_node_name)

    def _update_enabled_state(self):
        enabled = bool(self.folder_path and os.path.isdir(self.folder_path))
        has_node = enabled and bool(self.current_node_name)
        self.node_combo.setEnabled(enabled and bool(self.nodes))
        self.add_node_button.setEnabled(enabled and bool(self.image_keys))
        self.quick_create_button.setEnabled(enabled and bool(self.image_keys))
        self.delete_node_button.setEnabled(has_node)
        self.end_node_combo.setEnabled(has_node)
        self.table.setEnabled(has_node)
        self.add_button.setEnabled(has_node and bool(self.image_keys))
        self.delete_button.setEnabled(has_node)
        self.move_up_button.setEnabled(has_node)
        self.move_down_button.setEnabled(has_node)
        self.save_button.setEnabled(enabled)
        self._update_move_buttons()

    def _update_move_buttons(self):
        row = self.table.currentRow()
        row_count = self.table.rowCount()
        has_node = bool(self.folder_path and self.current_node_name)
        self.move_up_button.setEnabled(has_node and row > 1)
        self.move_down_button.setEnabled(has_node and 0 <= row < row_count - 1)
