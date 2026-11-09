# -*- coding: utf-8 -*-
# @Link    : https://github.com/aicezam/SmartOnmyoji
# @Version : Python3.7.6
# @MIT License Copyright (c) 2022 ACE

import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import threading
from ctypes import windll
from os.path import abspath, dirname
from time import sleep
import urllib.request

import PyQt5.QtCore
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog
from pynput.mouse import Listener
from win32gui import GetClientRect, GetParent, IsWindow, ScreenToClient, WindowFromPoint

from modules.ModuleGetConfig import ReadConfigFile
from modules.ModuleHandleSet import HandleSet
from modules.ModuleGetTargetInfo import GetTargetPicInfo
from modules.ModuleImageOrderDialog import ImageOrderDialog
from modules.ModuleRunThread import MatchingThread, GetActiveWindowThread
from modules.ModuleV5MultiOpen import V5MultiOpen, is_32bit_exe
from modules.ui import Ui_MainWindow

now_tag = "v0.43"


class MainWindow(QMainWindow, Ui_MainWindow):
    mouse_click_signal = PyQt5.QtCore.pyqtSignal(int, int)
    update_status_signal = PyQt5.QtCore.pyqtSignal(str)
    multi_open_finished_signal = PyQt5.QtCore.pyqtSignal()

    def __init__(self, ui_info, target_file_name_list):
        QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        super(MainWindow).__init__()
        self.setupUi(self)  # 继承UI类，下面进行信号与槽的绑定和修改
        self.matching_thread = None

        # 使用配置文件参数
        self.connect_mod_value = ui_info[0]
        self.target_path_mode_value = ui_info[1]
        self.handle_title_value = ui_info[2]
        self.click_deviation_value = ui_info[3]
        self.interval_seconds_value = ui_info[4]
        self.loop_min_value = ui_info[5]
        self.img_compress_val_value = ui_info[6]
        self.match_method_value = ui_info[7]
        self.run_mode_value = ui_info[8]
        self.custom_target_path_value = ui_info[9]
        self.process_num_value = ui_info[10]
        self.handle_num_value = ui_info[11]
        self.if_end_value = ui_info[12]
        self.debug_status_value = ui_info[13]
        self.set_priority_status_value = ui_info[14]  
        self.interval_seconds_value_max = ui_info[15]
        self.screen_scale_rate_value = ui_info[16]
        self.times_mode = ui_info[17]
        self.temporary_target_mode_value = ui_info[18] if len(ui_info) > 18 else "不启用"
        self.temporary_rounds_value = ui_info[19] if len(ui_info) > 19 else 1
        self.temporary_custom_target_path_value = (
            ui_info[20] if len(ui_info) > 20 else ""
        )
        self.temporary_trigger_image_value = ui_info[21] if len(ui_info) > 21 else ""
        self.custom_mark_image_value = ui_info[22] if len(ui_info) > 22 else ""
        self.temporary_custom_mark_image_value = (
            ui_info[23] if len(ui_info) > 23 else ""
        )

        # 日志批处理：每 150ms 统一写入一次，避免每条 print 都触发富文本布局
        self._log_buffer = []
        self._log_pending_chars = 0
        self._log_timer = PyQt5.QtCore.QTimer(self)
        self._log_timer.setInterval(150)
        self._log_timer.timeout.connect(self._flush_log_buffer)

        # 控制台消息捕获并输出到运行日志
        sys.stdout = EmitStr(text_writ=self.output_write)  # 输出结果重定向
        sys.stderr = EmitStr(text_writ=self.output_write)  # 错误输出重定向

        # 继承重新设置GUI初始状态
        self.btn_pause.setEnabled(False)
        self.btn_pause.hide()
        self.btn_resume.setEnabled(False)
        self.btn_resume.hide()
        self.btn_stop.setEnabled(False)
        self.btn_stop.hide()
        self.btn_exit.show()
        self.loop_progress.setValue(0)
        self.select_targetpic_path_btn.hide()
        self.setWindowIcon(QIcon(os.path.join(abspath(dirname(__file__)), 'img', 'logo.ico')))
        manual_url = pathlib.PureWindowsPath(abspath(dirname(__file__)) + r'\modules\tools\manual.html')
        self.log_analysis_url = pathlib.PureWindowsPath(abspath(dirname(__file__)) + r'\modules\tools\log_analysis.html')
        self._clear_run_log("<br>"
                             "<p>本软件完全开源免费，不盈利不接受捐赠，作者不对使用该软件产生的一切后果负责！</p>"
                             "<p>本软件仅作学习用途，请勿用于其他非法途径！</p>"
                             "<p>本软件未对任何游戏或程序进行任何程度的修改，仅做辅助手段，帮助处理大量重复且乏味的操作！</p>"
                             "<br>"
                             "<p>你可以在以下地址下载：</p>"
                             "<p>脚本源码(git)："
                             "<a href='https://github.com/aicezam/SmartOnmyoji'>"
                             "https://github.com/aicezam/SmartOnmyoji</a></p>"
                             "<p>蓝奏云(密码yys)："
                             "<a href='https://isu.ink/yys'>"
                             "https://wwu.lanzouq.com/b03d5mdli</a></p>"
                             "<p>使用方法说明：<a href=" + manual_url.as_posix() + ">->点击查看</a></p> "
                             "<p>日志分析工具：<a href=" + self.log_analysis_url.as_posix() + ">->点击使用</a></p> "
                             "<br>"
                             "<p>🌟🌟🌟感谢你的使用，支持请 <a href='https://github.com/aicezam/SmartOnmyoji'>点star</a> 🌟🌟🌟</p>"
                             )

        # 加载config.ini文件中的默认参数
        self.click_deviation.setValue(self.click_deviation_value)  # 设置默认偏移量
        self.image_compression.setSliderPosition(int(self.img_compress_val_value * 100))  # 压缩截图默认值
        self.set_priority.setChecked(self.set_priority_status_value)
        self.debug.setChecked(self.debug_status_value)
        self.show_handle_title.setText(str(self.handle_title_value))
        self.show_handle_num.setText(str(self.handle_num_value))
        self.select_target_path_mode_combobox.setCurrentText(self.target_path_mode_value)
        if self.target_path_mode_value == '自定义':
            self.select_targetpic_path_btn.show()
        else:
            self.select_targetpic_path_btn.hide()
        self.interval_seconds.setValue(float(self.interval_seconds_value))
        self.interval_seconds_max.setValue(float(self.interval_seconds_value_max))
        self.loop_min.setValue(float(self.loop_min_value))
        self.show_target_path.setText(self.custom_target_path_value)
        self.temporary_task_path.setText(
            self.temporary_custom_target_path_value
        )
        self.screen_rate.setValue(float(self.screen_scale_rate_value))
        if self.run_mode_value == '正常-可后台':
            self.runmod_nomal.setChecked(True)
        else:
            self.runmod_compatibility.setChecked(True)
        if self.match_method_value == '模板匹配':
            self.template_matching.setChecked(True)
        else:
            self.sift_matching.setChecked(True)
        if self.process_num_value == '单开':
            self.process_num_one.setChecked(True)
            self.show_handle_title.show()
            self.show_handle_num.hide()
        else:
            self.process_num_more.setChecked(True)
            self.show_handle_num.show()
            self.show_handle_title.hide()
        if self.connect_mod_value == 'Windows程序':
            self.rd_btn_windows_mod.setChecked(True)
        else:
            self.rd_btn_android_adb.setChecked(True)
            self.btn_select_handle.setEnabled(False)
            self.show_handle_title.setEnabled(False)
            self.show_handle_num.setEnabled(False)
            self.process_num_one.setEnabled(False)
            self.process_num_more.setEnabled(False)

        if self.times_mode == "按分钟计算":
            self.run_by_min.setChecked(True)
        else:
            self.run_by_rounds.setChecked(True)

        # 程序多开（启动外部程序）参数
        (
            multi_open_path,
            multi_open_count,
            multi_open_interval,
            multi_open_isolate,
            multi_open_use_v5,
            multi_open_v5_path,
        ) = ReadConfigFile().read_multi_open_info()
        self.multi_open_path.setText(str(multi_open_path or ""))
        self.multi_open_count.setValue(int(multi_open_count))
        self.multi_open_interval.setValue(float(multi_open_interval))
        self.multi_open_isolate.setChecked(bool(multi_open_isolate))
        self.multi_open_use_v5.setChecked(bool(multi_open_use_v5))
        self._v5_path = self._resolve_v5_path(multi_open_v5_path)
        self._update_multi_open_mode()
        self._update_v5_tooltip()

        # 设置界面上显示的匹配目标文件夹的选项名称
        for i in range(len(target_file_name_list)):
            self.select_target_path_mode_combobox.setItemText(i, target_file_name_list[i][0])
            self.temporary_task_target.addItem(target_file_name_list[i][0])
        temporary_target_index = self.temporary_task_target.findText(
            self.temporary_target_mode_value
        )
        self.temporary_task_target.setCurrentIndex(
            temporary_target_index if temporary_target_index >= 0 else 0
        )
        self._refresh_main_target_images(
            self.temporary_trigger_image_value,
            self.custom_mark_image_value,
        )
        self._refresh_temporary_target_images(
            self.temporary_custom_mark_image_value
        )
        self.temporary_task_rounds.setValue(int(self.temporary_rounds_value))
        self.temporary_task_target.currentIndexChanged.connect(
            self._update_temporary_task_controls
        )
        self.temporary_task_target.currentIndexChanged.connect(
            lambda: self._refresh_temporary_target_images()
        )
        self._update_temporary_task_controls()
        self._update_temporary_path_visibility()

        # 绑定信号
        self.btn_start.clicked.connect(self.__on_clicked_btn_begin)
        self.btn_pause.clicked.connect(self.__on_clicked_btn_pause)
        self.btn_resume.clicked.connect(self.__on_clicked_btn_resume)
        self.btn_stop.clicked.connect(self.__on_clicked_btn_cancel)
        self.btn_exit.clicked.connect(self.__on_clicked_exit)
        self.select_target_path_mode_combobox.currentIndexChanged.connect(
            lambda: self.select_target_path_mode_btn_enable(self.select_target_path_mode_combobox.currentIndex()))
        self.btn_select_handle.clicked.connect(self.__on_click_btn_select_handle)
        self.select_targetpic_path_btn.clicked.connect(self.__on_click_btn_select_custom_path)
        self.temporary_task_target.currentIndexChanged.connect(
            self._update_temporary_path_visibility
        )
        self.temporary_task_path_btn.clicked.connect(
            self.__on_click_btn_select_temporary_path
        )
        self.config_set_btn.clicked.connect(self.__on_click_btn_config_set)
        self.targetpic_path_btn.clicked.connect(self.__on_click_btn_target_pic_folder_open)
        self.image_order_btn.clicked.connect(self.__on_click_btn_image_order)
        self.btn_select_multi_open_path.clicked.connect(
            self.__on_click_btn_select_multi_open_path
        )
        self.btn_multi_open.clicked.connect(self.__on_clicked_btn_multi_open)
        self.multi_open_path.editingFinished.connect(self._save_multi_open_config)
        self.multi_open_count.valueChanged.connect(
            lambda _value: self._save_multi_open_config()
        )
        self.multi_open_interval.valueChanged.connect(
            lambda _value: self._save_multi_open_config()
        )
        self.multi_open_isolate.stateChanged.connect(
            lambda _state: self._save_multi_open_config()
        )
        self.multi_open_use_v5.stateChanged.connect(self._on_multi_open_mode_changed)
        self.btn_select_v5_path.clicked.connect(self.__on_click_btn_select_v5_path)
        self.multi_open_finished_signal.connect(self._on_multi_open_finished)

        self.mouse_click_signal.connect(self._log_mouse_click)
        self.mouse_listener = Listener(on_click=self._on_global_mouse_click)
        self.mouse_listener.start()

        # 异步检查更新，避免联网超时阻塞窗口显示
        self.update_status_signal.connect(self._on_update_status)
        threading.Thread(target=self._check_update_async, daemon=True).start()

    # 控制台消息重定向槽函数：先缓存，定时批量写入运行日志
    def output_write(self, text):
        if not text:
            return
        self._log_buffer.append(text)
        self._log_pending_chars += len(text)
        if self._log_pending_chars >= 16384:
            self._flush_log_buffer()
        elif not self._log_timer.isActive():
            self._log_timer.start()

    def _flush_log_buffer(self):
        if not self._log_buffer:
            self._log_timer.stop()
            return
        text = "".join(self._log_buffer)
        self._log_buffer = []
        self._log_pending_chars = 0
        cursor = self.run_log.textCursor()
        try:
            cursor.insertHtml(text)
        except Exception:
            cursor.insertText(text)
        self.run_log.setTextCursor(cursor)
        self.run_log.ensureCursorVisible()
        if not self._log_buffer:
            self._log_timer.stop()

    def _clear_run_log(self, text=""):
        self._log_buffer = []
        self._log_pending_chars = 0
        self._log_timer.stop()
        self.run_log.setText(text)

    def _check_update_async(self):
        try:
            status = self.get_update_status(now_tag)
            if status:
                self.update_status_signal.emit(status[1] + status[2])
        except Exception:
            pass

    def _on_update_status(self, text):
        if text:
            self.output_write(
                "<br><p style='font-weight:bold;color:rgb(255, 136, 17);'>"
                + text
                + "</p>"
            )

    def _on_global_mouse_click(self, x, y, _, pressed):
        if pressed:
            self.mouse_click_signal.emit(int(x), int(y))

    def _log_mouse_click(self, x, y):
        if not self.rd_btn_windows_mod.isChecked():
            return

        target_handles = self._get_target_window_handles()
        if not target_handles:
            return

        clicked_handle = WindowFromPoint((x, y))
        visited_handles = set()
        while clicked_handle and clicked_handle not in visited_handles:
            if clicked_handle in target_handles and IsWindow(clicked_handle):
                local_x, local_y = ScreenToClient(clicked_handle, (x, y))
                _, _, client_width, client_height = GetClientRect(clicked_handle)
                if 0 <= local_x < client_width and 0 <= local_y < client_height:
                    self.output_write(
                        f"<br>鼠标点击坐标: [ {local_x} , {local_y} ]"
                    )
                return
            visited_handles.add(clicked_handle)
            clicked_handle = GetParent(clicked_handle)

    def _get_target_window_handles(self):
        if self.process_num_one.isChecked():
            handle = HandleSet(self.show_handle_title.text(), 0).get_handle_num
            return [int(handle)] if handle else []

        handles = []
        for handle_text in self.show_handle_num.text().split(","):
            try:
                handle = int(handle_text.strip())
            except ValueError:
                continue
            if handle:
                resolved_handle = HandleSet("", handle).get_handle_num
                if resolved_handle and resolved_handle not in handles:
                    handles.append(resolved_handle)
        return handles

    def _stop_mouse_listener(self):
        if self.mouse_listener.is_alive():
            self.mouse_listener.stop()

    def closeEvent(self, event):
        # 先协作停止匹配线程，避免窗口销毁后线程继续访问 UI
        thread = getattr(self, "matching_thread", None)
        if thread is not None and thread.isRunning():
            thread.cancel()
            if not thread.wait(5000):
                print("<br>警告：匹配线程未能在 5 秒内退出，尝试强制终止。")
                thread.terminate()
                thread.wait(1000)
        self._flush_log_buffer()
        self._stop_mouse_listener()
        super().closeEvent(event)

    # 根据下拉框内容，设置自定义文件夹按钮是否可点击
    def select_target_path_mode_btn_enable(self, tag):
        if tag == 7:
            self.select_targetpic_path_btn.show()
        else:
            self.select_targetpic_path_btn.hide()
            self.show_target_path.setText('')
        self._refresh_main_target_images()

    # 开始按钮被点击的槽函数
    def __on_clicked_btn_begin(self):
        # self.run_log.setTextInteractionFlags(PyQt5.QtCore.Qt.NoTextInteraction)  # 禁止选中
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_start.hide()
        self.btn_pause.show()
        self.btn_resume.hide()
        self.btn_stop.show()
        self.set_edit_enabled(False)
        self._clear_run_log('')
        self.matching_thread = MatchingThread(self)  # 创建线程
        self.matching_thread.quit_signal.connect(self._quit_application)  # “关闭脚本”结束时由主线程关窗
        self.matching_thread.finished_signal.connect(self.thread_finished)  # 线程信号和槽连接，任务正常结束重置按钮状态
        self.matching_thread.progress_val_signal.connect(self.loop_progress.setValue)  # 线程信号和槽连接，设置进度条
        self.matching_thread.clean_run_log_signal.connect(self._clear_run_log)  # 线程信号和槽连接，清空日志
        sleep(0.1)
        self.matching_thread.start()

    # 暂停按钮被点击的槽函数
    def __on_clicked_btn_pause(self):
        print("<br>---已暂停!---")
        print("<br>日志分析工具：<a href=" + self.log_analysis_url.as_posix() + ">->点击使用</a><br>")
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.btn_resume.show()
        self.btn_pause.hide()
        sleep(0.1)
        self.matching_thread.pause()

    # 恢复按钮被点击的槽函数
    def __on_clicked_btn_resume(self):
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_resume.hide()
        self.btn_pause.show()
        sleep(0.1)
        self.matching_thread.resume()

    # 停止按钮被点击的槽函数
    def __on_clicked_btn_cancel(self):
        print("<br>---已终止!---")
        print("<br>日志分析工具：<a href=" + self.log_analysis_url.as_posix() + ">->点击使用</a><br>")
        # 不立即恢复“开始”按钮：等线程真正退出后由 thread_finished 统一恢复，
        # 避免旧线程还在跑就启动新线程。
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_pause.hide()
        self.btn_resume.hide()
        self.btn_stop.hide()
        self.matching_thread.cancel()

    # 正常完成后的槽函数
    def thread_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.set_edit_enabled(True)
        self.btn_start.show()
        self.btn_pause.hide()
        self.btn_resume.hide()
        self.btn_stop.hide()

    def _quit_application(self):
        """“关闭脚本”结束动作：在工作线程发信号，由主线程关闭窗口"""
        self._flush_log_buffer()
        self.close()

    # 获取目标窗体的槽函数
    def __on_click_btn_select_handle(self):
        self._clear_run_log('')  # 清空运行日志
        self.thread_1 = GetActiveWindowThread(self)
        if self.process_num_one.isChecked():  # 如果单开
            self.thread_1.active_window_signal.connect(self.show_handle_title.setText)
        else:  # 如果多开
            self.thread_1.active_window_signal.connect(self.show_handle_num.setText)
        self.thread_1.start()

    # 点击选择自定义文件夹
    def __on_click_btn_select_custom_path(self):
        current_path = abspath(dirname(__file__))  # 当前路径
        custom_path = QFileDialog.getExistingDirectory(None, "选择文件夹", current_path + r'\img')  # 起始路径
        if custom_path:
            self.show_target_path.setText(custom_path)  # 显示路径
            self._refresh_main_target_images()

    def __on_click_btn_image_order(self):
        target_mode = self.select_target_path_mode_combobox.currentText()
        custom_path = self.show_target_path.text() if target_mode == "自定义" else ""
        folder_path = GetTargetPicInfo(
            target_mode, custom_path
        ).get_target_folder_path()
        if not folder_path or not os.path.isdir(folder_path):
            print("<br>图片识别顺序：请先选择有效的目标模板文件夹！")
            return
        dialog = ImageOrderDialog(folder_path, self)
        if dialog.exec_():
            print(
                f"<br>图片识别顺序已保存：[ {folder_path} ]，"
                "下次开始匹配时生效。"
            )

    # ---- 程序多开（启动外部程序） ---------------------------------- #
    def _save_multi_open_config(self):
        try:
            ReadConfigFile().writ_config_multi_open(
                self.multi_open_path.text().strip(),
                int(self.multi_open_count.value()),
                float(self.multi_open_interval.value()),
                bool(self.multi_open_isolate.isChecked()),
                bool(self.multi_open_use_v5.isChecked()),
                self._v5_path or "",
            )
        except Exception as error:
            print(f"<br>保存程序多开配置失败：{error}")

    @staticmethod
    def _resolve_v5_path(configured=""):
        configured = str(configured or "").strip()
        project_parent = dirname(dirname(__file__))
        candidates = []
        if configured:
            candidates.append(configured)
        candidates.extend(
            [
                os.path.join(project_parent, "v5多开器", "V5.exe"),
                os.path.join(dirname(__file__), "v5多开器", "V5.exe"),
                os.path.join(os.getcwd(), "v5多开器", "V5.exe"),
            ]
        )
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return abspath(candidate)
        if configured:
            return abspath(configured)
        return abspath(candidates[1])

    def _update_multi_open_mode(self):
        use_v5 = bool(self.multi_open_use_v5.isChecked())
        self.multi_open_isolate.setEnabled(not use_v5)

    def _update_v5_tooltip(self):
        path = self._v5_path or ""
        self.multi_open_use_v5.setToolTip(
            "调用 V5 程序多开器实现 Hook 级隔离；仅支持 32 位目标程序。\nV5: %s" % path
        )
        self.btn_select_v5_path.setToolTip("选择 V5.exe（当前：%s）" % path)

    def _on_multi_open_mode_changed(self, _state):
        self._update_multi_open_mode()
        self._save_multi_open_config()

    def __on_click_btn_select_v5_path(self):
        start_dir = dirname(dirname(__file__))
        if self._v5_path:
            current_dir = dirname(self._v5_path)
            if current_dir and os.path.isdir(current_dir):
                start_dir = current_dir
        v5_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 V5.exe",
            start_dir,
            "V5.exe (V5.exe);;程序 (*.exe)",
        )
        if v5_path:
            self._v5_path = abspath(v5_path)
            self.multi_open_use_v5.setChecked(True)
            self._update_multi_open_mode()
            self._update_v5_tooltip()
            self._save_multi_open_config()

    def __on_click_btn_select_multi_open_path(self):
        current_path = self.multi_open_path.text().strip()
        start_dir = abspath(dirname(__file__))
        if current_path:
            current_dir = dirname(current_path)
            if current_dir and os.path.isdir(current_dir):
                start_dir = current_dir
        program_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择要运行的 .exe 程序",
            start_dir,
            "程序 (*.exe)",
        )
        if program_path:
            self.multi_open_path.setText(program_path)
            self._save_multi_open_config()

    def __on_clicked_btn_multi_open(self):
        program_path = self.multi_open_path.text().strip()
        if not program_path or not os.path.isfile(program_path):
            print("<br>程序多开：请选择有效的程序文件路径！")
            return
        if os.path.splitext(program_path)[1].lower() != ".exe":
            print("<br>程序多开：目前只支持 .exe 程序！")
            return

        instance_count = int(self.multi_open_count.value())
        interval_seconds = float(self.multi_open_interval.value())
        isolate = bool(self.multi_open_isolate.isChecked())
        use_v5 = bool(self.multi_open_use_v5.isChecked())

        if use_v5:
            v5_path = self._resolve_v5_path(self._v5_path)
            self._v5_path = v5_path
            if not os.path.isfile(v5_path):
                print("<br>程序多开：未找到 V5.exe，请点“选择 V5”指定 V5 多开器。")
                return
            if not is_32bit_exe(program_path):
                print(
                    "<br>程序多开：V5 仅支持 32 位程序。"
                    "请选择 32 位的 Launch.exe，不要选择 64 位的 onmyoji.exe。"
                )
                return
            self._save_multi_open_config()
            self.btn_multi_open.setEnabled(False)
            self.btn_select_multi_open_path.setEnabled(False)
            self.multi_open_path.setEnabled(False)
            self.multi_open_count.setEnabled(False)
            self.multi_open_interval.setEnabled(False)
            self.multi_open_isolate.setEnabled(False)
            self.multi_open_use_v5.setEnabled(False)
            self.btn_select_v5_path.setEnabled(False)
            print(
                f"<br>程序多开：使用 V5 隔离多开 [ {os.path.basename(program_path)} ]，"
                f"数量 [ {instance_count} ]，间隔 [ {interval_seconds:g} ] 秒"
            )
            threading.Thread(
                target=self._launch_v5_programs,
                args=(program_path, instance_count, interval_seconds, v5_path),
                daemon=True,
            ).start()
            return

        self._save_multi_open_config()
        self.btn_multi_open.setEnabled(False)
        self.btn_select_multi_open_path.setEnabled(False)
        self.multi_open_path.setEnabled(False)
        self.multi_open_count.setEnabled(False)
        self.multi_open_interval.setEnabled(False)
        self.multi_open_isolate.setEnabled(False)
        self.multi_open_use_v5.setEnabled(False)
        self.btn_select_v5_path.setEnabled(False)
        print(
            f"<br>程序多开：开始运行 [ {os.path.basename(program_path)} ]，"
            f"数量 [ {instance_count} ]，间隔 [ {interval_seconds:g} ] 秒，"
            f"隔离 [ {'开' if isolate else '关'} ]"
        )
        threading.Thread(
            target=self._launch_programs,
            args=(program_path, instance_count, interval_seconds, isolate),
            daemon=True,
        ).start()

    def _launch_v5_programs(self, program_path, instance_count, interval_seconds, v5_path):
        try:
            V5MultiOpen(
                v5_path,
                program_path,
                instance_count,
                interval_seconds,
                logger=lambda message: print(f"<br>程序多开：{message}"),
            ).run()
        except Exception as error:
            print(f"<br>程序多开：V5 多开失败：{error}")
        finally:
            try:
                self.multi_open_finished_signal.emit()
            except RuntimeError:
                pass

    def _launch_programs(self, program_path, instance_count, interval_seconds, isolate):
        launched = []  # (index, process, sandbox_dir)
        reported_exits = set()
        try:
            for index in range(1, instance_count + 1):
                try:
                    process, sandbox = self._launch_program(
                        program_path, isolate, index
                    )
                    launched.append((index, process, sandbox))
                    sandbox_text = f"，隔离目录 [ {sandbox} ]" if sandbox else ""
                    print(
                        f"<br>程序多开：已运行第 [ {index} / {instance_count} ] 个："
                        f"{os.path.basename(program_path)}，PID [ {process.pid} ]"
                        f"{sandbox_text}"
                    )
                except Exception as error:
                    print(
                        f"<br>程序多开：第 [ {index} / {instance_count} ] 个运行失败：{error}"
                    )
                if index < instance_count:
                    sleep(interval_seconds)
                    # 检查前面已启动的进程是否还活着，便于确认目标程序是否只允许单实例
                    for launched_index, launched_process, _ in launched:
                        if (
                            launched_index not in reported_exits
                            and launched_process.poll() is not None
                        ):
                            reported_exits.add(launched_index)
                            print(
                                f"<br>程序多开：第 [ {launched_index} ] 个进程"
                                f"（PID {launched_process.pid}）已退出"
                            )
        finally:
            alive = [
                index
                for index, process, _ in launched
                if process.poll() is None
            ]
            print(
                f"<br>程序多开：完成，启动 [ {len(launched)} / {instance_count} ] 个，"
                f"仍在运行 [ {len(alive)} ] 个"
            )
            if len(alive) < len(launched):
                print(
                    "<br>程序多开：提示：有进程已退出。若目标程序是单实例启动器，"
                    "重复运行可能会关闭前一个实例，或启动后自动退出；"
                    "这类程序需要其自带的多开入口，或 V5 那种 Hook 级隔离，"
                    "普通启动参数/目录隔离无法绕过全局互斥锁。"
                )
            if isolate:
                print(
                    "<br>程序多开：隔离目录位于 "
                    "%LOCALAPPDATA%\\SmartOnmyoji\\MultiOpen\\<程序名>_<hash>\\instance_N，"
                    "可手动删除。"
                )
            try:
                self.multi_open_finished_signal.emit()
            except RuntimeError:
                pass

    @staticmethod
    def _prepare_isolated_launch(program_path, instance_index):
        """为单个实例准备独立 AppData/Temp 与独立启动路径（目录 junction）。"""
        program_dir = dirname(program_path) or "."
        exe_name = os.path.basename(program_path)
        program_key = hashlib.md5(
            os.path.normcase(os.path.abspath(program_path)).encode("utf-8")
        ).hexdigest()[:8]
        base_root = (
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("TEMP")
            or program_dir
        )
        sandbox = os.path.join(
            base_root,
            "SmartOnmyoji",
            "MultiOpen",
            "%s_%s" % (os.path.splitext(exe_name)[0], program_key),
            "instance_%d" % instance_index,
        )
        appdata = os.path.join(sandbox, "AppData", "Roaming")
        localappdata = os.path.join(sandbox, "AppData", "Local")
        temp_dir = os.path.join(sandbox, "Temp")
        for directory in (sandbox, appdata, localappdata, temp_dir):
            os.makedirs(directory, exist_ok=True)

        link_path = os.path.join(sandbox, "app")
        if not os.path.exists(link_path):
            result = None
            try:
                result = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", link_path, program_dir],
                    capture_output=True,
                    text=True,
                    encoding="mbcs",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception as error:
                print(f"<br>程序多开：创建隔离启动路径失败：{error}")
            if result is None or result.returncode != 0 or not os.path.exists(link_path):
                detail = ""
                if result is not None:
                    detail = (result.stderr or result.stdout or "").strip()
                if detail:
                    print(f"<br>程序多开：隔离启动路径创建失败，回退为仅 AppData/Temp 隔离：{detail}")
                link_path = program_dir

        launch_path = os.path.join(link_path, exe_name)
        env = os.environ.copy()
        env["APPDATA"] = appdata
        env["LOCALAPPDATA"] = localappdata
        env["TEMP"] = temp_dir
        env["TMP"] = temp_dir
        env["SMARTONMYOJI_INSTANCE"] = str(instance_index)
        return launch_path, link_path, env, sandbox

    @staticmethod
    def _launch_program(program_path, isolate=False, instance_index=1):
        if os.path.splitext(program_path)[1].lower() != ".exe":
            raise ValueError("只支持 .exe 程序")
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        if isolate:
            launch_path, cwd, env, sandbox = MainWindow._prepare_isolated_launch(
                program_path, instance_index
            )
            process = subprocess.Popen(
                [launch_path], cwd=cwd, env=env, creationflags=creationflags
            )
            return process, sandbox
        process = subprocess.Popen(
            [program_path],
            cwd=dirname(program_path) or None,
            creationflags=creationflags,
        )
        return process, ""

    def _on_multi_open_finished(self):
        self.btn_multi_open.setEnabled(True)
        self.btn_select_multi_open_path.setEnabled(True)
        self.multi_open_path.setEnabled(True)
        self.multi_open_count.setEnabled(True)
        self.multi_open_interval.setEnabled(True)
        self.multi_open_isolate.setEnabled(True)
        self.multi_open_use_v5.setEnabled(True)
        self.btn_select_v5_path.setEnabled(True)
        self._update_multi_open_mode()

    def _refresh_main_target_images(
        self, preferred_trigger_name=None, preferred_mark_name=None
    ):
        if preferred_trigger_name is None:
            preferred_trigger_name = self.temporary_trigger_image.currentData()
        if preferred_mark_name is None:
            preferred_mark_name = self.custom_mark_image.currentData()

        target_mode = self.select_target_path_mode_combobox.currentText()
        custom_path = (
            self.show_target_path.text() if target_mode == "自定义" else ""
        )
        target_folder = GetTargetPicInfo(
            target_mode, custom_path
        ).get_target_folder_path()

        image_names = set()
        if target_folder and os.path.isdir(target_folder):
            def report_walk_error(error):
                print(f"<br>读取主任务模板目录失败：{error}")

            for current_dir, _, filenames in os.walk(
                target_folder, onerror=report_walk_error
            ):
                for filename in filenames:
                    extension = os.path.splitext(filename)[1].lower()
                    if extension in (".jpg", ".png"):
                        image_names.add(os.path.splitext(filename)[0])

        for combo, default_text, preferred_name in (
            (self.temporary_trigger_image, "默认标记图片", preferred_trigger_name),
            (self.custom_mark_image, "不自定义", preferred_mark_name),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(default_text, "")
            for image_name in sorted(image_names):
                combo.addItem(image_name, image_name)

            selected_index = combo.findData(preferred_name or "")
            combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
            combo.blockSignals(False)

        self.flow_body_editor.set_target_folder(target_folder)

    def _update_temporary_task_controls(self):
        enabled = self.temporary_task_target.currentText() != "不启用"
        self.temporary_task_rounds.setEnabled(enabled)
        self.temporary_trigger_image.setEnabled(enabled)
        self.temporary_custom_mark_image.setEnabled(enabled)

    def _update_temporary_path_visibility(self):
        is_custom = self.temporary_task_target.currentText() == "自定义"
        self.temporary_task_path.setVisible(is_custom)
        self.temporary_task_path_btn.setVisible(is_custom)

    def __on_click_btn_select_temporary_path(self):
        current_path = self.temporary_task_path.text()
        if not current_path or not os.path.isdir(current_path):
            current_path = abspath(dirname(__file__)) + r'\img'
        custom_path = QFileDialog.getExistingDirectory(
            self, "选择临时任务模板文件夹", current_path
        )
        if custom_path:
            self.temporary_task_path.setText(custom_path)
            self._refresh_temporary_target_images()

    def _refresh_temporary_target_images(self, preferred_mark_name=None):
        if preferred_mark_name is None:
            preferred_mark_name = self.temporary_custom_mark_image.currentData()

        target_mode = self.temporary_task_target.currentText()
        custom_path = (
            self.temporary_task_path.text() if target_mode == "自定义" else ""
        )
        target_folder = GetTargetPicInfo(
            target_mode, custom_path
        ).get_target_folder_path()

        image_names = set()
        if target_folder and os.path.isdir(target_folder):
            def report_walk_error(error):
                print(f"<br>读取临时任务模板目录失败：{error}")

            for _, _, filenames in os.walk(target_folder, onerror=report_walk_error):
                for filename in filenames:
                    if os.path.splitext(filename)[1].lower() in (
                        ".jpg",
                        ".jpeg",
                        ".png",
                    ):
                        image_names.add(os.path.splitext(filename)[0])

        combo = self.temporary_custom_mark_image
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("不自定义", "")
        for image_name in sorted(image_names):
            combo.addItem(image_name, image_name)
        selected_index = combo.findData(preferred_mark_name or "")
        combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        combo.blockSignals(False)

    # 配置文件修改按钮
    @staticmethod
    def __on_click_btn_config_set():
        current_path = abspath(dirname(__file__))  # 当前路径
        cmd = 'notepad ' + current_path + r'\modules\config.ini'
        # os.system(cmd)  # 使用cmd命令打开配置文件,使用subprocess替换system后，打包成exe不会弹出cmd窗口
        subprocess.call(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 打开模板文件夹按钮
    @staticmethod
    def __on_click_btn_target_pic_folder_open():
        folder_path = abspath(dirname(__file__)) + r'\img'  # 当前路径
        os.startfile(folder_path)

    @staticmethod
    def get_update_status(now_tag1):
        """从 GitHub 获取更新状态（在后台线程调用）"""
        url = r"https://api.github.com/repos/aicezam/SmartOnmyoji/releases/latest"
        try:
            header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edg/107.0.1418.42"}
            request = urllib.request.Request(url, headers=header)
            response = urllib.request.urlopen(request, timeout=2).read().decode('utf8')
            tag_name = json.loads(response)["tag_name"]
            latest_version = tuple(int(x) for x in re.findall(r"\d+", tag_name))
            current_version = tuple(int(x) for x in re.findall(r"\d+", now_tag1))
            if latest_version and current_version and latest_version > current_version:
                return True, "检测到更新，当前最新版：", tag_name
            return False
        except Exception:
            return False

    # 退出程序的槽函数
    def __on_clicked_exit(self):
        thread = getattr(self, "matching_thread", None)
        if thread is not None and thread.isRunning():
            thread.cancel()
            if not thread.wait(5000):
                thread.terminate()
                thread.wait(1000)
        self._flush_log_buffer()
        self._stop_mouse_listener()
        sys.exit(0)

    # 开始运行后，禁用编辑
    def set_edit_enabled(self, bool_val=False):
        self.if_end_do.setEnabled(bool_val)
        self.template_matching.setEnabled(bool_val)
        self.sift_matching.setEnabled(bool_val)
        self.runmod_nomal.setEnabled(bool_val)
        self.runmod_compatibility.setEnabled(bool_val)
        self.debug.setEnabled(bool_val)
        self.flow_body_enabled.setEnabled(bool_val)
        self.select_target_path_mode_combobox.setEnabled(bool_val)
        if self.rd_btn_windows_mod.isChecked():
            self.show_handle_title.setEnabled(bool_val)
            self.show_handle_num.setEnabled(bool_val)
            self.btn_select_handle.setEnabled(bool_val)
            self.process_num_one.setEnabled(bool_val)
            self.process_num_more.setEnabled(bool_val)
        self.rd_btn_windows_mod.setEnabled(bool_val)
        self.rd_btn_android_adb.setEnabled(bool_val)
        self.show_target_path.setEnabled(bool_val)
        self.select_targetpic_path_btn.setEnabled(bool_val)
        self.custom_mark_image.setEnabled(bool_val)
        self.temporary_task_target.setEnabled(bool_val)
        self.temporary_task_rounds.setEnabled(
            bool_val and self.temporary_task_target.currentText() != "不启用"
        )
        self.temporary_trigger_image.setEnabled(
            bool_val and self.temporary_task_target.currentText() != "不启用"
        )
        self.temporary_task_path.setEnabled(bool_val)
        self.temporary_task_path_btn.setEnabled(bool_val)
        self.interval_seconds.setEnabled(bool_val)
        self.interval_seconds_max.setEnabled(bool_val)
        self.loop_min.setEnabled(bool_val)
        self.click_deviation.setEnabled(bool_val)
        self.image_compression.setEnabled(bool_val)
        self.set_priority.setEnabled(bool_val)
        self.config_set_btn.setEnabled(bool_val)
        self.targetpic_path_btn.setEnabled(bool_val)
        self.image_order_btn.setEnabled(bool_val)
        self.flow_body_editor.setEnabled(bool_val)
        self.screen_rate.setEnabled(bool_val)
        self.run_by_min.setEnabled(bool_val)
        self.run_by_rounds.setEnabled(bool_val)


class EmitStr(PyQt5.QtCore.QObject):
    """
    定义一个信号类，sys.stdout有个write方法，通过重定向，
    每当有新字符串输出时就会触发下面定义的write函数，进而发出信号
    """
    text_writ = PyQt5.QtCore.pyqtSignal(str)

    def write(self, text):
        self.text_writ.emit(str(text))

    def flush(self):
        # print(..., flush=True) 或第三方库调用 flush 时不应报错
        pass


def except_out_config(exc_type, value, tb):
    print('<br>Error Information:')
    print('<br>Type:', exc_type)
    print('<br>Value:', value)
    print('<br>Traceback:', tb)


def run_self_check():
    """打包后自检：不显示主窗口、不请求管理员权限，结果写入 selfcheck.log。"""
    import tempfile
    import traceback

    frozen = bool(getattr(sys, "frozen", False))
    base_dir = dirname(sys.executable) if frozen else abspath(dirname(__file__))
    log_path = os.path.join(base_dir, "selfcheck.log")
    try:
        log_file = open(log_path, "w", encoding="utf-8")
    except OSError:
        log_path = os.path.join(tempfile.gettempdir(), "smart_onmyoji_selfcheck.log")
        log_file = open(log_path, "w", encoding="utf-8")

    ok = True

    def record(message):
        # console=False 的 exe 里 sys.stdout 可能为 None，不能依赖 print
        log_file.write(str(message) + "\n")
        log_file.flush()

    try:
        record("SmartOnmyoji self-check")
        record("frozen=%s" % frozen)
        record("python=%s" % sys.version.split()[0])

        import cv2
        import numpy
        from PIL import __version__ as pillow_version
        record("cv2=%s" % cv2.__version__)
        record("numpy=%s" % numpy.__version__)
        record("Pillow=%s" % pillow_version)

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv[:1] or ["smart_onmyoji_start"])

        icon_path = os.path.join(abspath(dirname(__file__)), "img", "logo.ico")
        icon = QIcon(icon_path)
        icon_ok = not icon.isNull()
        record("QIcon=%s -> %s" % (icon_path, "OK" if icon_ok else "EMPTY"))
        if not icon_ok:
            ok = False

        config_info = ReadConfigFile().read_config_ui_info()
        record("config.ini -> OK (%d fields)" % len(config_info))

        target_info = GetTargetPicInfo("御魂", "", compute_sift=False).get_target_info
        if target_info is None:
            record("templates -> FAILED")
            ok = False
        else:
            record("templates -> OK (%d images)" % len(target_info[4]))
    except Exception:
        ok = False
        record("EXCEPTION:\n" + traceback.format_exc())
    finally:
        record("RESULT: " + ("OK" if ok else "FAILED"))
        log_file.close()
    return 0 if ok else 1


if __name__ == '__main__':

    if '--self-check' in sys.argv:
        sys.exit(run_self_check())

    if windll.shell32.IsUserAnAdmin():  # 是否以管理员身份运行
        sys.excepthook = except_out_config  # 错误信息输出

        app = QApplication(sys.argv)
        # 设置主题样式
        # 如需主题样式：pip install qt-material，恢复顶部 import 后取消下一行注释
        # apply_stylesheet(app,theme='light_amber.xml',invert_secondary=True)
        # 加载配置文件参数
        config_ini = ReadConfigFile()
        default_info = config_ini.read_config_ui_info()
        target_file_name = config_ini.read_config_target_path_files_name()
        myWindow = MainWindow(default_info, target_file_name)
        myWindow.setWindowTitle(now_tag)  # 设置窗口标题
        myWindow.show()
        sys.exit(app.exec_())
    else:
        windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)  # 调起UAC以管理员身份重新执行
        sys.exit(0)
