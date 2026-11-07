# -*- coding: utf-8 -*-
"""
SmartOnmyoji 主窗口 UI（重构版 + 控件尺寸放大）

基于 pyuic5 生成的 qt.ui 结果重构，主要改动：
  1. 抛弃 setGeometry 绝对定位，全部改用布局管理器；
  2. 修复底部 btn_start / btn_pause / btn_resume 相互重叠的问题；
  3. 窗口不再强制固定尺寸，支持缩放，日志区自适应；
  4. 控件初始可见性显式设置；
  5. 统一 QSS 放大按钮、输入框、单选框、标签等控件；
  6. 同步放大窗口与布局间距，避免放大后拥挤；
  7. objectName 与信号槽保持与原文件一致，外部逻辑无需改动。

注意：本文件若需继续用 Qt Designer 维护，请同步回 .ui，否则会被 pyuic5 覆盖。
"""

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    """主窗口 UI 类，仅负责界面搭建。"""

    # ================================================================== #
    #  对外入口
    # ================================================================== #
    def setupUi(self, MainWindow):
        self._setup_window(MainWindow)
        self._build_base_group()       # groupBox_2：基础设置
        self._build_temporary_group()
        self._build_advanced_group()   # groupBox：高级设置
        self._build_left_panel()       # 左侧面板
        self._build_right_panel()      # 右侧面板（进度 + 日志）
        self._build_bottom_bar()       # 底部按钮条
        self._assemble(MainWindow)     # 组装到 centralwidget

        self._apply_style()            # 统一控件样式（放大）

        self.retranslateUi(MainWindow)
        self._connect_signals()
        self._apply_initial_state()

        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    # ================================================================== #
    #  窗口与中央部件
    # ================================================================== #
    def _setup_window(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1040, 780)                                  # 放大窗口
        MainWindow.setMinimumSize(QtCore.QSize(960, 720))             # 放宽最小值
        MainWindow.setUnifiedTitleAndToolBarOnMac(False)

        # 全局字体（可选，与 QSS 叠加使用）
        font = QtGui.QFont("Microsoft YaHei", 10)
        MainWindow.setFont(font)

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.centralwidget.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))

        MainWindow.setCentralWidget(self.centralwidget)

    # ================================================================== #
    #  基础设置：groupBox_2
    # ================================================================== #
    def _build_base_group(self):
        self.groupBox_2 = QtWidgets.QGroupBox()
        self.groupBox_2.setObjectName("groupBox_2")
        self.groupBox_2.setCheckable(False)

        layout = QtWidgets.QVBoxLayout(self.groupBox_2)
        layout.setContentsMargins(8, 16, 8, 10)
        layout.setSpacing(8)

        # ---- 程序多开（外部程序） ----------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_multi_open_path = QtWidgets.QLabel()
        self.label_multi_open_path.setObjectName("label_multi_open_path")
        row.addWidget(self.label_multi_open_path)

        self.multi_open_path = QtWidgets.QLineEdit()
        self.multi_open_path.setObjectName("multi_open_path")
        self.multi_open_path.setPlaceholderText("选择要运行的 .exe 程序")
        row.addWidget(self.multi_open_path, 1)

        self.btn_select_multi_open_path = QtWidgets.QPushButton()
        self.btn_select_multi_open_path.setObjectName("btn_select_multi_open_path")
        self.btn_select_multi_open_path.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.btn_select_multi_open_path)
        layout.addLayout(row)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_multi_open_count = QtWidgets.QLabel()
        self.label_multi_open_count.setObjectName("label_multi_open_count")
        row.addWidget(self.label_multi_open_count)

        self.multi_open_count = QtWidgets.QSpinBox()
        self.multi_open_count.setObjectName("multi_open_count")
        self.multi_open_count.setMinimumSize(QtCore.QSize(70, 30))
        self.multi_open_count.setRange(1, 50)
        self.multi_open_count.setValue(2)
        row.addWidget(self.multi_open_count)

        self.label_multi_open_interval = QtWidgets.QLabel()
        self.label_multi_open_interval.setObjectName("label_multi_open_interval")
        row.addWidget(self.label_multi_open_interval)

        self.multi_open_interval = QtWidgets.QDoubleSpinBox()
        self.multi_open_interval.setObjectName("multi_open_interval")
        self.multi_open_interval.setMinimumSize(QtCore.QSize(90, 30))
        self.multi_open_interval.setRange(0.1, 600.0)
        self.multi_open_interval.setDecimals(1)
        self.multi_open_interval.setSingleStep(0.5)
        self.multi_open_interval.setValue(3.0)
        self.multi_open_interval.setSuffix("秒")
        row.addWidget(self.multi_open_interval)
        row.addStretch(1)
        layout.addLayout(row)

        self.btn_multi_open = QtWidgets.QPushButton()
        self.btn_multi_open.setObjectName("btn_multi_open")
        self.btn_multi_open.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_multi_open.setToolTip("按设定数量运行 .exe 程序，每个间隔按界面设置；目标程序需自身支持多实例")
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        row.addWidget(self.btn_multi_open)
        layout.addLayout(row)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.multi_open_isolate = QtWidgets.QCheckBox()
        self.multi_open_isolate.setObjectName("multi_open_isolate")
        self.multi_open_isolate.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.multi_open_isolate.setChecked(True)
        self.multi_open_isolate.setToolTip(
            "每个实例使用独立 AppData/Temp 和独立启动路径；不能绕过目标程序的全局单实例锁"
        )
        row.addWidget(self.multi_open_isolate)
        row.addStretch(1)
        layout.addLayout(row)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.multi_open_use_v5 = QtWidgets.QCheckBox()
        self.multi_open_use_v5.setObjectName("multi_open_use_v5")
        self.multi_open_use_v5.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.multi_open_use_v5.setToolTip(
            "调用 V5 程序多开器实现 Hook 级隔离；仅支持 32 位目标程序"
        )
        row.addWidget(self.multi_open_use_v5)

        self.btn_select_v5_path = QtWidgets.QPushButton()
        self.btn_select_v5_path.setObjectName("btn_select_v5_path")
        self.btn_select_v5_path.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_select_v5_path.setToolTip("选择 V5.exe")
        row.addWidget(self.btn_select_v5_path)
        row.addStretch(1)
        layout.addLayout(row)

        self.line_multi_open = QtWidgets.QFrame()
        self.line_multi_open.setObjectName("line_multi_open")
        self.line_multi_open.setFrameShape(QtWidgets.QFrame.HLine)
        self.line_multi_open.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(self.line_multi_open)

        # ---- 行 1：匹配目标 ----------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label = QtWidgets.QLabel()
        self.label.setObjectName("label")
        row.addWidget(self.label)

        self.rd_btn_windows_mod = QtWidgets.QRadioButton()
        self.rd_btn_windows_mod.setObjectName("rd_btn_windows_mod")
        self.rd_btn_windows_mod.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.rd_btn_windows_mod.setChecked(True)
        row.addWidget(self.rd_btn_windows_mod)

        self.rd_btn_android_adb = QtWidgets.QRadioButton()
        self.rd_btn_android_adb.setObjectName("rd_btn_android_adb")
        self.rd_btn_android_adb.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.rd_btn_android_adb)
        row.addStretch(1)
        layout.addLayout(row)

        # ---- 行 2：选择窗体 ----------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_2 = QtWidgets.QLabel()
        self.label_2.setObjectName("label_2")
        row.addWidget(self.label_2)

        self.process_num_one = QtWidgets.QRadioButton()
        self.process_num_one.setObjectName("process_num_one")
        self.process_num_one.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.process_num_one.setChecked(True)
        row.addWidget(self.process_num_one)

        self.process_num_more = QtWidgets.QRadioButton()
        self.process_num_more.setObjectName("process_num_more")
        self.process_num_more.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.process_num_more)
        row.addStretch(1)
        layout.addLayout(row)

        self.process_num_button_group = QtWidgets.QButtonGroup(self.groupBox_2)
        self.process_num_button_group.setObjectName("process_num_button_group")
        self.process_num_button_group.addButton(self.process_num_one)
        self.process_num_button_group.addButton(self.process_num_more)

        # ---- 行 3：窗体标题/数量 + 获取窗体 ------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)

        # 用 QGridLayout 让两个 QLineEdit 同格重叠，靠 show/hide 切换
        self._handle_stack = QtWidgets.QWidget()
        stack_layout = QtWidgets.QGridLayout(self._handle_stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)

        self.show_handle_title = QtWidgets.QLineEdit()
        self.show_handle_title.setObjectName("show_handle_title")
        self.show_handle_num = QtWidgets.QLineEdit()
        self.show_handle_num.setObjectName("show_handle_num")
        stack_layout.addWidget(self.show_handle_title, 0, 0)
        stack_layout.addWidget(self.show_handle_num, 0, 0)
        row.addWidget(self._handle_stack, 1)

        self.btn_select_handle = QtWidgets.QPushButton()
        self.btn_select_handle.setObjectName("btn_select_handle")
        self.btn_select_handle.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.btn_select_handle)
        layout.addLayout(row)

        # ---- 行 4：目标名称 + img 文件夹 ---------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_3 = QtWidgets.QLabel()
        self.label_3.setObjectName("label_3")
        row.addWidget(self.label_3)

        self.select_target_path_mode_combobox = QtWidgets.QComboBox()
        self.select_target_path_mode_combobox.setObjectName("select_target_path_mode_combobox")
        for _ in range(8):
            self.select_target_path_mode_combobox.addItem("")
        self.select_target_path_mode_combobox.setMinimumWidth(120)
        row.addWidget(self.select_target_path_mode_combobox, 1)

        self.targetpic_path_btn = QtWidgets.QPushButton()
        self.targetpic_path_btn.setObjectName("targetpic_path_btn")
        self.targetpic_path_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.targetpic_path_btn)
        layout.addLayout(row)

        # ---- 行 5：自定义路径 + 选择按钮 ---------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.show_target_path = QtWidgets.QLineEdit()
        self.show_target_path.setObjectName("show_target_path")
        self.show_target_path.setReadOnly(True)
        row.addWidget(self.show_target_path, 1)

        self.select_targetpic_path_btn = QtWidgets.QPushButton()
        self.select_targetpic_path_btn.setObjectName("select_targetpic_path_btn")
        self.select_targetpic_path_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.select_targetpic_path_btn)
        layout.addLayout(row)

        # ---- 行 6：自定义 mark 图片 ------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.custom_mark_image_label = QtWidgets.QLabel()
        self.custom_mark_image_label.setObjectName("custom_mark_image_label")
        row.addWidget(self.custom_mark_image_label)

        self.custom_mark_image = QtWidgets.QComboBox()
        self.custom_mark_image.setObjectName("custom_mark_image")
        self.custom_mark_image.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.custom_mark_image.setMinimumContentsLength(6)
        self.custom_mark_image.setMinimumWidth(120)
        self.custom_mark_image.setMaximumWidth(200)
        self.custom_mark_image.addItem("")
        row.addWidget(self.custom_mark_image, 1)
        layout.addLayout(row)

        # ---- 行 6：进度计算方式 ------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_21 = QtWidgets.QLabel()
        self.label_21.setObjectName("label_21")
        row.addWidget(self.label_21)

        self.run_by_min = QtWidgets.QRadioButton()
        self.run_by_min.setObjectName("run_by_min")
        self.run_by_min.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.run_by_min.setChecked(True)
        row.addWidget(self.run_by_min)

        self.run_by_rounds = QtWidgets.QRadioButton()
        self.run_by_rounds.setObjectName("run_by_rounds")
        self.run_by_rounds.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.run_by_rounds)
        row.addStretch(1)
        layout.addLayout(row)

        self.times_mode_button_group = QtWidgets.QButtonGroup(self.groupBox_2)
        self.times_mode_button_group.setObjectName("times_mode_button_group")
        self.times_mode_button_group.addButton(self.run_by_min)
        self.times_mode_button_group.addButton(self.run_by_rounds)

        # ---- 行 7：脚本持续运行 ------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_14 = QtWidgets.QLabel()
        self.label_14.setObjectName("label_14")
        row.addWidget(self.label_14)

        self.loop_min = QtWidgets.QDoubleSpinBox()
        self.loop_min.setObjectName("loop_min")
        self.loop_min.setMinimumSize(QtCore.QSize(90, 30))
        self.loop_min.setMinimum(1.0)
        self.loop_min.setMaximum(300.0)
        self.loop_min.setSingleStep(1.0)
        self.loop_min.setProperty("value", 90.0)
        row.addWidget(self.loop_min)

        self.label_16 = QtWidgets.QLabel()
        self.label_16.setObjectName("label_16")
        row.addWidget(self.label_16)
        row.addStretch(1)
        layout.addLayout(row)

        # ---- 行 8：每次匹配间隔 ------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_17 = QtWidgets.QLabel()
        self.label_17.setObjectName("label_17")
        row.addWidget(self.label_17)

        self.interval_seconds = QtWidgets.QDoubleSpinBox()
        self.interval_seconds.setObjectName("interval_seconds")
        self.interval_seconds.setMinimumSize(QtCore.QSize(80, 30))
        self.interval_seconds.setMinimum(0.1)
        self.interval_seconds.setMaximum(60.0)
        self.interval_seconds.setSingleStep(0.1)
        self.interval_seconds.setProperty("value", 5.0)
        row.addWidget(self.interval_seconds)

        self.label_20 = QtWidgets.QLabel()
        self.label_20.setObjectName("label_20")
        row.addWidget(self.label_20)

        self.interval_seconds_max = QtWidgets.QDoubleSpinBox()
        self.interval_seconds_max.setObjectName("interval_seconds_max")
        self.interval_seconds_max.setMinimumSize(QtCore.QSize(80, 30))
        self.interval_seconds_max.setMinimum(1.0)
        self.interval_seconds_max.setMaximum(120.0)
        self.interval_seconds_max.setSingleStep(0.1)
        self.interval_seconds_max.setProperty("value", 8.0)
        row.addWidget(self.interval_seconds_max)

        self.label_15 = QtWidgets.QLabel()
        self.label_15.setObjectName("label_15")
        row.addWidget(self.label_15)
        row.addStretch(1)
        layout.addLayout(row)

        # ---- 行 9：点击坐标偏移 ------------------------------------ #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_18 = QtWidgets.QLabel()
        self.label_18.setObjectName("label_18")
        row.addWidget(self.label_18)

        self.click_deviation = QtWidgets.QSpinBox()
        self.click_deviation.setObjectName("click_deviation")
        self.click_deviation.setMinimumSize(QtCore.QSize(80, 30))
        self.click_deviation.setMinimum(20)
        self.click_deviation.setMaximum(100)
        self.click_deviation.setProperty("value", 35)
        self.click_deviation.setDisplayIntegerBase(10)
        row.addWidget(self.click_deviation)

        self.label_19 = QtWidgets.QLabel()
        self.label_19.setObjectName("label_19")
        row.addWidget(self.label_19)
        row.addStretch(1)
        layout.addLayout(row)

        # ---- 单选互斥：匹配目标 ------------------------------------- #
        self.buttonGroup = QtWidgets.QButtonGroup(self.groupBox_2)
        self.buttonGroup.setObjectName("connection_mode_button_group")
        self.buttonGroup.addButton(self.rd_btn_windows_mod)
        self.buttonGroup.addButton(self.rd_btn_android_adb)

        layout.addStretch(1)

    def _build_temporary_group(self):
        self.temporary_task_group = QtWidgets.QGroupBox()
        self.temporary_task_group.setObjectName("temporary_task_group")
        layout = QtWidgets.QVBoxLayout(self.temporary_task_group)
        layout.setContentsMargins(14, 20, 14, 14)
        layout.setSpacing(8)

        trigger_row = QtWidgets.QHBoxLayout()
        trigger_row.setSpacing(10)
        self.temporary_trigger_image_label = QtWidgets.QLabel()
        self.temporary_trigger_image_label.setObjectName(
            "temporary_trigger_image_label"
        )
        trigger_row.addWidget(self.temporary_trigger_image_label)

        self.temporary_trigger_image = QtWidgets.QComboBox()
        self.temporary_trigger_image.setObjectName("temporary_trigger_image")
        self.temporary_trigger_image.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.temporary_trigger_image.setMinimumContentsLength(6)
        self.temporary_trigger_image.setMinimumWidth(120)
        self.temporary_trigger_image.setMaximumWidth(220)
        self.temporary_trigger_image.addItem("")
        trigger_row.addWidget(self.temporary_trigger_image, 1)
        layout.addLayout(trigger_row)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.temporary_task_target_label = QtWidgets.QLabel()
        self.temporary_task_target_label.setObjectName("temporary_task_target_label")
        row.addWidget(self.temporary_task_target_label)

        self.temporary_task_target = QtWidgets.QComboBox()
        self.temporary_task_target.setObjectName("temporary_task_target")
        self.temporary_task_target.addItem("")
        self.temporary_task_target.setMinimumWidth(120)
        row.addWidget(self.temporary_task_target, 1)

        self.temporary_task_rounds_label = QtWidgets.QLabel()
        self.temporary_task_rounds_label.setObjectName("temporary_task_rounds_label")
        row.addWidget(self.temporary_task_rounds_label)

        self.temporary_task_rounds = QtWidgets.QSpinBox()
        self.temporary_task_rounds.setObjectName("temporary_task_rounds")
        self.temporary_task_rounds.setMinimumSize(QtCore.QSize(70, 30))
        self.temporary_task_rounds.setRange(1, 20000)
        self.temporary_task_rounds.setValue(1)
        row.addWidget(self.temporary_task_rounds)
        layout.addLayout(row)

        mark_row = QtWidgets.QHBoxLayout()
        mark_row.setSpacing(10)
        self.temporary_custom_mark_image_label = QtWidgets.QLabel()
        self.temporary_custom_mark_image_label.setObjectName(
            "temporary_custom_mark_image_label"
        )
        mark_row.addWidget(self.temporary_custom_mark_image_label)

        self.temporary_custom_mark_image = QtWidgets.QComboBox()
        self.temporary_custom_mark_image.setObjectName(
            "temporary_custom_mark_image"
        )
        self.temporary_custom_mark_image.addItem("")
        mark_row.addWidget(self.temporary_custom_mark_image, 1)
        layout.addLayout(mark_row)

        path_row = QtWidgets.QHBoxLayout()
        path_row.setSpacing(10)
        self.temporary_task_path = QtWidgets.QLineEdit()
        self.temporary_task_path.setObjectName("temporary_task_path")
        self.temporary_task_path.setReadOnly(True)
        self.temporary_task_path.setPlaceholderText("选择临时任务模板文件夹…")
        path_row.addWidget(self.temporary_task_path, 1)

        self.temporary_task_path_btn = QtWidgets.QPushButton()
        self.temporary_task_path_btn.setObjectName("temporary_task_path_btn")
        self.temporary_task_path_btn.setCursor(
            QtGui.QCursor(QtCore.Qt.PointingHandCursor)
        )
        path_row.addWidget(self.temporary_task_path_btn)
        layout.addLayout(path_row)

        # 页面被 QScrollArea 拉伸到视口高度时，避免各行被平均拉开
        layout.addStretch(1)

    # ================================================================== #
    #  高级设置：groupBox
    # ================================================================== #
    def _build_advanced_group(self):
        self.groupBox = QtWidgets.QGroupBox()
        self.groupBox.setObjectName("groupBox")

        layout = QtWidgets.QVBoxLayout(self.groupBox)
        layout.setContentsMargins(14, 20, 14, 14)
        layout.setSpacing(10)

        # ---- 行 1：屏幕缩放 ----------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_23 = QtWidgets.QLabel()
        self.label_23.setObjectName("label_23")
        row.addWidget(self.label_23)

        self.screen_rate = QtWidgets.QDoubleSpinBox()
        self.screen_rate.setObjectName("screen_rate")
        self.screen_rate.setMinimumSize(QtCore.QSize(80, 30))
        self.screen_rate.setMinimum(1.0)
        self.screen_rate.setMaximum(10.0)
        self.screen_rate.setSingleStep(0.05)
        self.screen_rate.setProperty("value", 1.25)
        row.addWidget(self.screen_rate)

        self.label_24 = QtWidgets.QLabel()
        self.label_24.setObjectName("label_24")
        row.addWidget(self.label_24)
        row.addStretch(1)
        layout.addLayout(row)

        # ---- 行 2：运行模式 ----------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_7 = QtWidgets.QLabel()
        self.label_7.setObjectName("label_7")
        row.addWidget(self.label_7)

        self.runmod_nomal = QtWidgets.QRadioButton()
        self.runmod_nomal.setObjectName("runmod_nomal")
        self.runmod_nomal.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.runmod_nomal.setChecked(True)
        row.addWidget(self.runmod_nomal)

        self.runmod_compatibility = QtWidgets.QRadioButton()
        self.runmod_compatibility.setObjectName("runmod_compatibility")
        self.runmod_compatibility.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.runmod_compatibility)
        row.addStretch(1)
        layout.addLayout(row)

        # ---- 行 3：压缩截图 ----------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_8 = QtWidgets.QLabel()
        self.label_8.setObjectName("label_8")
        row.addWidget(self.label_8)

        self.image_compression = QtWidgets.QSlider()
        self.image_compression.setObjectName("image_compression")
        self.image_compression.setMinimum(40)
        self.image_compression.setMaximum(100)
        self.image_compression.setProperty("value", 80)
        self.image_compression.setSliderPosition(80)
        self.image_compression.setOrientation(QtCore.Qt.Horizontal)
        self.image_compression.setInvertedAppearance(False)
        self.image_compression.setInvertedControls(False)
        self.image_compression.setMinimumHeight(30)
        row.addWidget(self.image_compression, 1)
        layout.addLayout(row)

        # ---- 行 4：匹配方法 ----------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_9 = QtWidgets.QLabel()
        self.label_9.setObjectName("label_9")
        row.addWidget(self.label_9)

        self.template_matching = QtWidgets.QRadioButton()
        self.template_matching.setObjectName("template_matching")
        self.template_matching.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.template_matching.setChecked(True)
        row.addWidget(self.template_matching)

        self.sift_matching = QtWidgets.QRadioButton()
        self.sift_matching.setObjectName("sift_matching")
        self.sift_matching.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.sift_matching)
        row.addStretch(1)
        layout.addLayout(row)

        # 单选分组：运行模式与匹配方法是两个独立维度，必须各自加入 QButtonGroup。
        # 否则 Qt 会把同一父控件下所有未分组的 QRadioButton 视为一组，
        # 出现“选了运行模式就取消匹配方法”的互斥问题。
        self.run_mode_button_group = QtWidgets.QButtonGroup(self.groupBox)
        self.run_mode_button_group.setObjectName("run_mode_button_group")
        self.run_mode_button_group.setExclusive(True)
        self.run_mode_button_group.addButton(self.runmod_nomal)
        self.run_mode_button_group.addButton(self.runmod_compatibility)

        self.match_method_button_group = QtWidgets.QButtonGroup(self.groupBox)
        self.match_method_button_group.setObjectName("match_method_button_group")
        self.match_method_button_group.setExclusive(True)
        self.match_method_button_group.addButton(self.template_matching)
        self.match_method_button_group.addButton(self.sift_matching)

        # ---- 行 5：完成后动作 --------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_10 = QtWidgets.QLabel()
        self.label_10.setObjectName("label_10")
        row.addWidget(self.label_10)

        self.if_end_do = QtWidgets.QComboBox()
        self.if_end_do.setObjectName("if_end_do")
        self.if_end_do.setEditable(True)
        for _ in range(4):
            self.if_end_do.addItem("")
        row.addWidget(self.if_end_do, 1)
        layout.addLayout(row)

        # ---- 行 6：其他设置 ----------------------------------------- #
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.label_11 = QtWidgets.QLabel()
        self.label_11.setObjectName("label_11")
        row.addWidget(self.label_11)

        self.debug = QtWidgets.QCheckBox()
        self.debug.setObjectName("debug")
        self.debug.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.debug)

        self.set_priority = QtWidgets.QCheckBox()
        self.set_priority.setObjectName("set_priority")
        self.set_priority.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.set_priority)

        self.config_set_btn = QtWidgets.QPushButton()
        self.config_set_btn.setObjectName("config_set_btn")
        self.config_set_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        row.addWidget(self.config_set_btn)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addStretch(1)

    # ================================================================== #
    #  左侧面板
    # ================================================================== #
    def _build_left_panel(self):
        self.leftPanel = QtWidgets.QWidget()
        self.leftPanel.setObjectName("leftPanel")
        self.leftPanel.setMinimumWidth(500)
        self.leftPanel.setMaximumWidth(600)

        layout = QtWidgets.QVBoxLayout(self.leftPanel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.settings_tabs = QtWidgets.QTabWidget(self.leftPanel)
        self.settings_tabs.setObjectName("settings_tabs")

        for page_name, content_widget in (
            ("base_settings_page", self.groupBox_2),
            ("temporary_settings_page", self.temporary_task_group),
            ("advanced_settings_page", self.groupBox),
        ):
            page = QtWidgets.QWidget()
            page.setObjectName(page_name)
            page_layout = QtWidgets.QVBoxLayout(page)
            page_layout.setContentsMargins(0, 8, 0, 0)
            scroll = QtWidgets.QScrollArea()
            scroll.setObjectName(page_name + "_scroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            scroll.setStyleSheet(
                "QScrollArea { border: none; background: transparent; }"
            )
            scroll.setWidget(content_widget)
            page_layout.addWidget(scroll)
            self.settings_tabs.addTab(page, "")

        layout.addWidget(self.settings_tabs)

    # ================================================================== #
    #  右侧面板：进度 + 日志
    # ================================================================== #
    def _build_right_panel(self):
        self.rightPanel = QtWidgets.QWidget()
        self.rightPanel.setObjectName("rightPanel")

        layout = QtWidgets.QVBoxLayout(self.rightPanel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # ---- 进度区 ------------------------------------------------ #
        progress_box = QtWidgets.QGroupBox()
        progress_box.setObjectName("progress_box")
        progress_box.setTitle("")                                  # 占位，避免默认标题
        p_layout = QtWidgets.QVBoxLayout(progress_box)
        p_layout.setContentsMargins(12, 16, 12, 12)
        p_layout.setSpacing(8)

        self.label_12 = QtWidgets.QLabel()
        self.label_12.setObjectName("label_12")
        p_layout.addWidget(self.label_12)

        self.loop_progress = QtWidgets.QProgressBar()
        self.loop_progress.setObjectName("loop_progress")
        self.loop_progress.setProperty("value", 24)
        self.loop_progress.setMinimumHeight(28)
        p_layout.addWidget(self.loop_progress)

        layout.addWidget(progress_box)

        # ---- 日志区 ------------------------------------------------ #
        log_box = QtWidgets.QGroupBox()
        log_box.setObjectName("log_box")
        log_box.setTitle("")                                       # 占位
        l_layout = QtWidgets.QVBoxLayout(log_box)
        l_layout.setContentsMargins(12, 16, 12, 12)
        l_layout.setSpacing(8)

        self.label_13 = QtWidgets.QLabel()
        self.label_13.setObjectName("label_13")
        l_layout.addWidget(self.label_13)

        self.run_log = QtWidgets.QTextBrowser()
        self.run_log.setObjectName("run_log")
        self.run_log.viewport().setProperty(
            "cursor", QtGui.QCursor(QtCore.Qt.IBeamCursor))
        self.run_log.setReadOnly(True)
        self.run_log.setOpenExternalLinks(True)
        l_layout.addWidget(self.run_log, 1)

        layout.addWidget(log_box, 1)

    # ================================================================== #
    #  底部按钮条
    # ================================================================== #
    def _build_bottom_bar(self):
        self.bottomBar = QtWidgets.QWidget()
        self.bottomBar.setObjectName("bottomBar")

        layout = QtWidgets.QHBoxLayout(self.bottomBar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.btn_exit = QtWidgets.QPushButton()
        self.btn_exit.setObjectName("btn_exit")
        self.btn_exit.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        layout.addWidget(self.btn_exit)

        layout.addStretch(1)

        self.btn_start = QtWidgets.QPushButton()
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        layout.addWidget(self.btn_start)

        self.btn_pause = QtWidgets.QPushButton()
        self.btn_pause.setObjectName("btn_pause")
        self.btn_pause.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        layout.addWidget(self.btn_pause)

        self.btn_resume = QtWidgets.QPushButton()
        self.btn_resume.setObjectName("btn_resume")
        self.btn_resume.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        layout.addWidget(self.btn_resume)

        self.btn_stop = QtWidgets.QPushButton()
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        layout.addWidget(self.btn_stop)

    # ================================================================== #
    #  组装
    # ================================================================== #
    def _assemble(self, MainWindow):
        root = QtWidgets.QVBoxLayout(self.centralwidget)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # 主区：左 | 竖线 | 右
        main = QtWidgets.QHBoxLayout()
        main.setSpacing(10)
        main.addWidget(self.leftPanel, 0)

        self.line = QtWidgets.QFrame()
        self.line.setObjectName("line")
        self.line.setFrameShape(QtWidgets.QFrame.VLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        main.addWidget(self.line)

        main.addWidget(self.rightPanel, 1)
        root.addLayout(main, 1)

        # 横分割线
        self.line_2 = QtWidgets.QFrame()
        self.line_2.setObjectName("line_2")
        self.line_2.setFrameShape(QtWidgets.QFrame.HLine)
        self.line_2.setFrameShadow(QtWidgets.QFrame.Sunken)
        root.addWidget(self.line_2)

        root.addWidget(self.bottomBar)

    # ================================================================== #
    #  样式：统一放大控件尺寸与字体
    # ================================================================== #
    def _apply_style(self):
        self.centralwidget.setStyleSheet("""
            QWidget {
                font-size: 9pt;
            }

            /* ---- 输入类控件 ---- */
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                min-height: 26px;
                padding: 2px 5px;
                font-size: 9pt;
            }

            /* ---- 按钮 ---- */
            QPushButton {
                min-height: 28px;
                min-width: 72px;
                padding: 3px 8px;
                font-size: 9pt;
            }

            /* ---- 单选框 / 复选框 ---- */
            QRadioButton, QCheckBox {
                min-height: 22px;
                spacing: 5px;
                font-size: 9pt;
            }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }

            /* ---- 标签 ---- */
            QLabel {
                font-size: 9pt;
                min-height: 20px;
            }

            QTabBar::tab {
                min-height: 26px;
                padding: 3px 8px;
            }

            /* ---- 分组框 ---- */
            QGroupBox {
                font-size: 9pt;
                font-weight: bold;
                margin-top: 8px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }

            /* ---- 滑块 ---- */
            QSlider::groove:horizontal {
                height: 8px;
                background: #d0d0d0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
                background: #5a9bd5;
            }

            /* ---- 进度条 ---- */
            QProgressBar {
                min-height: 28px;
                text-align: center;
                font-size: 11pt;
            }

            /* ---- 日志区 ---- */
            QTextBrowser {
                font-size: 11pt;
            }
        """)

    # ================================================================== #
    #  信号槽连接
    # ================================================================== #
    def _connect_signals(self):
        # 匹配目标：Windows / Android
        self.rd_btn_android_adb.clicked['bool'].connect(self.show_handle_title.setDisabled)
        self.rd_btn_windows_mod.clicked['bool'].connect(self.show_handle_title.setEnabled)
        self.rd_btn_windows_mod.clicked['bool'].connect(self.btn_select_handle.setEnabled)
        self.rd_btn_android_adb.clicked['bool'].connect(self.btn_select_handle.setDisabled)

        # 单开 / 多开
        self.process_num_more.clicked['bool'].connect(self.show_handle_num.show)
        self.process_num_more.clicked['bool'].connect(self.show_handle_title.hide)
        self.process_num_one.clicked['bool'].connect(self.show_handle_num.hide)
        self.process_num_one.clicked['bool'].connect(self.show_handle_title.show)

        # Android 模式禁用多开/单开选择及数量框
        self.rd_btn_android_adb.clicked['bool'].connect(self.process_num_more.setDisabled)
        self.rd_btn_android_adb.clicked['bool'].connect(self.process_num_one.setDisabled)
        self.rd_btn_windows_mod.clicked['bool'].connect(self.process_num_more.setEnabled)
        self.rd_btn_windows_mod.clicked['bool'].connect(self.process_num_one.setEnabled)
        self.rd_btn_android_adb.clicked['bool'].connect(self.show_handle_num.setDisabled)

    # ================================================================== #
    #  初始状态
    # ================================================================== #
    def _apply_initial_state(self):
        self.show_handle_title.show()
        self.show_handle_num.hide()
        self.btn_select_handle.setEnabled(True)

    # ================================================================== #
    #  文字设置
    # ================================================================== #
    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate

        # ---- 窗口标题 ----
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))

        # ---- 高级设置分组 ----
        self.groupBox.setTitle(_translate("MainWindow", "高级设置"))
        self.label_10.setText(_translate("MainWindow", "完成后："))
        self.if_end_do.setCurrentText(_translate("MainWindow", "不执行任何操作"))
        self.if_end_do.setPlaceholderText(_translate("MainWindow", "请选择功能"))
        self.if_end_do.setItemText(0, _translate("MainWindow", "不执行任何操作"))
        self.if_end_do.setItemText(1, _translate("MainWindow", "电脑关机"))
        self.if_end_do.setItemText(2, _translate("MainWindow", "关闭匹配目标窗体"))
        self.if_end_do.setItemText(3, _translate("MainWindow", "关闭脚本"))
        self.label_9.setText(_translate("MainWindow", "匹配方法："))
        self.template_matching.setText(_translate("MainWindow", "模板匹配"))
        self.sift_matching.setText(_translate("MainWindow", "特征点匹配"))
        self.label_8.setText(_translate("MainWindow", "压缩截图："))
        self.label_7.setText(_translate("MainWindow", "运行模式："))
        self.runmod_nomal.setText(_translate("MainWindow", "正常-可后台"))
        self.runmod_compatibility.setText(_translate("MainWindow", "兼容-不可后台"))
        self.label_11.setText(_translate("MainWindow", "其他设置："))
        self.debug.setText(_translate("MainWindow", "开启调试"))
        self.set_priority.setText(_translate("MainWindow", "防闪退"))
        self.config_set_btn.setText(_translate("MainWindow", "配置文件"))
        self.label_23.setText(_translate("MainWindow", "屏幕缩放："))
        self.label_24.setText(_translate("MainWindow", "（设置/屏幕/缩放与布局）"))

        # ---- 基础设置分组 ----
        self.groupBox_2.setTitle(_translate("MainWindow", "基础设置"))
        self.label_multi_open_path.setText(_translate("MainWindow", "程序路径："))
        self.multi_open_path.setPlaceholderText(
            _translate("MainWindow", "选择要运行的 .exe 程序")
        )
        self.btn_select_multi_open_path.setText(_translate("MainWindow", "选择"))
        self.label_multi_open_count.setText(_translate("MainWindow", "数量："))
        self.label_multi_open_interval.setText(_translate("MainWindow", "间隔："))
        self.multi_open_interval.setSuffix(_translate("MainWindow", "秒"))
        self.btn_multi_open.setText(_translate("MainWindow", "运行多开"))
        self.multi_open_isolate.setText(_translate("MainWindow", "隔离运行"))
        self.multi_open_use_v5.setText(_translate("MainWindow", "使用 V5 多开器"))
        self.btn_select_v5_path.setText(_translate("MainWindow", "选择 V5"))
        self.rd_btn_windows_mod.setText(_translate("MainWindow", "Windows程序"))
        self.rd_btn_android_adb.setText(_translate("MainWindow", "Android ADB"))
        self.run_by_min.setText(_translate("MainWindow", "按分钟"))
        self.run_by_rounds.setText(_translate("MainWindow", "按轮次"))
        self.label_3.setText(_translate("MainWindow", "目标名称："))
        self.select_target_path_mode_combobox.setCurrentText(_translate("MainWindow", "御魂"))
        self.select_target_path_mode_combobox.setPlaceholderText(_translate("MainWindow", "请选择功能"))
        for idx, txt in enumerate(["御魂", "探索", "突破", "活动",
                                   "觉醒", "御灵", "百鬼夜行", "自定义"]):
            self.select_target_path_mode_combobox.setItemText(idx, _translate("MainWindow", txt))
        self.show_target_path.setPlaceholderText(_translate("MainWindow", "自定义文件夹路径…"))
        self.select_targetpic_path_btn.setText(_translate("MainWindow", "自定义文件夹"))
        self.custom_mark_image_label.setText(
            _translate("MainWindow", "自定义 mark 图片：")
        )
        self.custom_mark_image.setItemText(
            0, _translate("MainWindow", "不自定义")
        )
        self.show_handle_num.setText(_translate("MainWindow", "0"))
        self.show_handle_num.setPlaceholderText(
            _translate("MainWindow", "请输入窗体标题或选择窗体"))
        self.show_handle_title.setText(_translate("MainWindow", "阴阳师-网易游戏"))
        self.show_handle_title.setPlaceholderText(
            _translate("MainWindow", "请输入窗体标题或选择窗体"))
        self.btn_select_handle.setText(_translate("MainWindow", "获取窗体"))
        self.targetpic_path_btn.setText(_translate("MainWindow", "img文件夹"))
        self.label_18.setText(_translate("MainWindow", "坐标偏移："))
        self.label_19.setText(_translate("MainWindow", "个像素"))
        self.label_17.setText(_translate("MainWindow", "匹配间隔："))
        self.label_20.setText(_translate("MainWindow", "至"))
        self.label_15.setText(_translate("MainWindow", "秒"))
        self.label_14.setText(_translate("MainWindow", "脚本运行："))
        self.label_16.setText(_translate("MainWindow", "分钟/轮次"))
        self.label.setText(_translate("MainWindow", "匹配目标："))
        self.rd_btn_windows_mod.setText(_translate("MainWindow", "Windows程序"))
        self.rd_btn_android_adb.setText(_translate("MainWindow", "Android ADB"))
        self.label_2.setText(_translate("MainWindow", "选择窗体："))
        self.process_num_one.setText(_translate("MainWindow", "单开"))
        self.process_num_more.setText(_translate("MainWindow", "多开"))
        self.label_21.setText(_translate("MainWindow", "进度计算："))
        self.run_by_min.setText(_translate("MainWindow", "按分钟"))
        self.run_by_rounds.setText(_translate("MainWindow", "按轮次"))
        self.temporary_task_group.setTitle(
            _translate("MainWindow", "标记触发的临时任务")
        )
        self.settings_tabs.setTabText(
            0, _translate("MainWindow", "基础设置")
        )
        self.settings_tabs.setTabText(
            1, _translate("MainWindow", "临时任务")
        )
        self.settings_tabs.setTabText(
            2, _translate("MainWindow", "高级设置")
        )
        self.temporary_task_target_label.setText(_translate("MainWindow", "临时目标："))
        self.temporary_task_target.setItemText(0, _translate("MainWindow", "不启用"))
        self.temporary_task_target.addItem(_translate("MainWindow", "自定义"))
        self.temporary_task_rounds_label.setText(_translate("MainWindow", "轮数："))
        self.temporary_trigger_image_label.setText(
            _translate("MainWindow", "触发临时任务图片：")
        )
        self.temporary_trigger_image.setItemText(
            0, _translate("MainWindow", "默认标记图片")
        )
        self.temporary_custom_mark_image_label.setText(
            _translate("MainWindow", "临时任务 mark 图片：")
        )
        self.temporary_custom_mark_image.setItemText(
            0, _translate("MainWindow", "不自定义")
        )
        self.temporary_task_path_btn.setText(_translate("MainWindow", "选择文件夹"))

        # ---- 右侧日志与进度 ----
        self.label_13.setText(_translate("MainWindow", "运行日志："))
        self.btn_exit.setText(_translate("MainWindow", "退出"))
        self.btn_resume.setText(_translate("MainWindow", "恢复"))
        self.btn_stop.setText(_translate("MainWindow", "停止"))
        self.btn_pause.setText(_translate("MainWindow", "暂停"))
        self.btn_start.setText(_translate("MainWindow", "开始"))
        self.label_12.setText(_translate("MainWindow", "匹配进度："))