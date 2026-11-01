# -*- coding: utf-8 -*-
"""通过 V5 程序多开器实现 32 位程序的隔离多开。

V5 是一个 MFC 对话框程序：
  * 路径输入框 ID = 1000
  * “隔离打开程序”按钮 ID = 1002
  * 每次点击按钮打开一个隔离实例；V5 必须保持运行，关闭 V5 会关闭所有实例。

本模块只负责写 V5 的 config.ini、启动/复用 V5、点击按钮，不做 DLL 注入。
"""
import os
import json
import struct
import subprocess
import time
from configparser import ConfigParser

import win32api
import win32con
import win32gui
import win32process


V5_PATH_EDIT_ID = 1000
V5_OPEN_BUTTON_ID = 1002
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

PE_MACHINE_X86 = 0x014C


def _norm(path):
    return os.path.normcase(os.path.abspath(str(path)))


def get_pe_machine(path):
    """返回 PE 文件的 Machine 字段；无法解析时返回 None。"""
    try:
        with open(path, "rb") as file:
            data = file.read(4096)
            if len(data) < 0x40 or data[:2] != b"MZ":
                return None
            pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
            if pe_offset + 6 > len(data):
                file.seek(pe_offset)
                data = file.read(6)
                if len(data) < 6:
                    return None
                return struct.unpack_from("<H", data, 4)[0]
            if data[pe_offset:pe_offset + 4] != b"PE\0\0":
                return None
            return struct.unpack_from("<H", data, pe_offset + 4)[0]
    except Exception:
        return None


def is_32bit_exe(path):
    return get_pe_machine(path) == PE_MACHINE_X86


def _process_exe(pid):
    handle = None
    try:
        handle = win32api.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, int(pid)
        )
        return win32process.GetModuleFileNameEx(handle, 0)
    except Exception:
        return ""
    finally:
        if handle:
            try:
                win32api.CloseHandle(handle)
            except Exception:
                pass


class V5MultiOpen:
    def __init__(self, v5_path, target_path, count, interval, logger=print):
        self.v5_path = os.path.abspath(v5_path)
        self.target_path = os.path.abspath(target_path)
        self.count = max(1, int(count))
        self.interval = max(0.1, float(interval))
        self.logger = logger or (lambda _msg: None)
        self.process = None
        self.hwnd = None
        self.started_by_us = False
        self.marker_path = os.path.join(
            os.path.dirname(self.v5_path), ".smart_onmyoji_v5.json"
        )

    # ------------------------------------------------------------------ #
    def run(self):
        self._validate()
        existing = self._find_v5_dialog()
        if existing:
            self.hwnd = existing
            _, pid = win32process.GetWindowThreadProcessId(existing)
            marker = self._read_marker()
            try:
                marker_pid = int(marker.get("pid", 0)) if marker else -1
            except (TypeError, ValueError):
                marker_pid = -1
            if (
                marker
                and marker_pid == int(pid)
                and _norm(marker.get("target", "")) == _norm(self.target_path)
            ):
                self.logger("复用本工具上一次启动的 V5 窗口")
            else:
                self._try_set_path(strict=True)
                self._write_marker(pid)
                self.logger("检测到 V5 已在运行，复用现有窗口")
        else:
            self._write_last_path()
            self._start_v5()
            self.hwnd = self._wait_dialog()
            self._try_set_path(strict=False)
            self._write_marker(self.process.pid)

        self._open_instances()
        if self.started_by_us:
            self.logger("V5 多开器保持运行中；关闭 V5 会关闭所有已隔离打开的程序")

    def _read_marker(self):
        try:
            with open(self.marker_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return None

    def _write_marker(self, pid):
        try:
            with open(self.marker_path, "w", encoding="utf-8") as file:
                json.dump(
                    {"pid": int(pid), "target": self.target_path},
                    file,
                    ensure_ascii=False,
                )
        except Exception as error:
            self.logger("写入 V5 复用标记失败：%s" % error)

    # ------------------------------------------------------------------ #
    def _validate(self):
        if not os.path.isfile(self.v5_path):
            raise RuntimeError("V5.exe 不存在：%s" % self.v5_path)
        if os.path.splitext(self.v5_path)[1].lower() != ".exe":
            raise RuntimeError("V5 路径不是 .exe 文件")
        if not os.path.isfile(self.target_path):
            raise RuntimeError("目标程序不存在：%s" % self.target_path)
        if os.path.splitext(self.target_path)[1].lower() != ".exe":
            raise RuntimeError("目标程序必须是 .exe")
        if not is_32bit_exe(self.target_path):
            raise RuntimeError(
                "V5 仅支持 32 位程序；当前目标不是 32 位 exe。"
                "请选择 Launch.exe 等 32 位启动器，不要选 64 位的 onmyoji.exe。"
            )

    # ------------------------------------------------------------------ #
    def _write_last_path(self):
        config_path = os.path.join(os.path.dirname(self.v5_path), "config.ini")
        try:
            config = ConfigParser(interpolation=None)
            config.optionxform = str
            if os.path.isfile(config_path):
                config.read(config_path, encoding="mbcs")
            if not config.has_section("V5"):
                config.add_section("V5")
            config.set("V5", "LastPath", self.target_path)
            with open(config_path, "w", encoding="mbcs", errors="replace") as file:
                config.write(file)
            check = ConfigParser(interpolation=None)
            check.optionxform = str
            check.read(config_path, encoding="mbcs")
            got = check.get("V5", "LastPath", fallback="")
        except Exception as error:
            raise RuntimeError("写入 V5 配置失败：%s" % error)
        if _norm(got) != _norm(self.target_path):
            raise RuntimeError(
                "V5 配置路径写入后校验失败：%r -> %r" % (self.target_path, got)
            )

    def _start_v5(self):
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            self.process = subprocess.Popen(
                [self.v5_path],
                cwd=os.path.dirname(self.v5_path),
                creationflags=creationflags,
            )
        except OSError as error:
            if getattr(error, "winerror", None) == 740:
                raise RuntimeError(
                    "V5 需要管理员权限。请以管理员身份运行本工具，"
                    "或右键 V5.exe 选择“以管理员身份运行”后再试。"
                )
            raise RuntimeError("启动 V5 失败：%s" % error)
        self.started_by_us = True

    def _wait_dialog(self):
        deadline = time.time() + 15.0
        while time.time() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise RuntimeError(
                    "V5 启动后立即退出，exit=%s" % self.process.returncode
                )
            hwnd = self._dialog_by_pid(self.process.pid)
            if hwnd:
                return hwnd
            time.sleep(0.2)
        raise RuntimeError("等待 V5 主窗口超时（15 秒）")

    # ------------------------------------------------------------------ #
    def _find_v5_dialog(self):
        found = []

        def enum(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if win32gui.GetClassName(hwnd) != "#32770":
                    return True
                title = win32gui.GetWindowText(hwnd)
                if "V5" not in title:
                    return True
                if not win32gui.GetDlgItem(hwnd, V5_OPEN_BUTTON_ID):
                    return True
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                exe = _process_exe(pid)
                if exe and _norm(exe) == _norm(self.v5_path):
                    found.append(hwnd)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(enum, None)
        return found[0] if found else None

    @staticmethod
    def _dialog_by_pid(pid):
        found = []

        def enum(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if win32gui.GetClassName(hwnd) != "#32770":
                    return True
                if "V5" not in win32gui.GetWindowText(hwnd):
                    return True
                if not win32gui.GetDlgItem(hwnd, V5_OPEN_BUTTON_ID):
                    return True
                _, wpid = win32process.GetWindowThreadProcessId(hwnd)
                if wpid == pid:
                    found.append(hwnd)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(enum, None)
        return found[0] if found else None

    def _try_set_path(self, strict):
        edit = win32gui.GetDlgItem(self.hwnd, V5_PATH_EDIT_ID)
        if not edit:
            if strict:
                raise RuntimeError("V5 主窗口没有找到路径输入框")
            return
        win32gui.SendMessage(edit, win32con.WM_SETTEXT, 0, self.target_path)
        time.sleep(0.15)
        got = win32gui.GetWindowText(edit)
        if _norm(got) != _norm(self.target_path):
            if strict:
                raise RuntimeError(
                    "检测到 V5 已在运行，但无法修改其目标路径。"
                    "请先关闭 V5，再在本工具中重新运行多开。"
                )
            self.logger(
                "V5 路径框未接受输入（通常为只读），"
                "已使用 config.ini 中的 LastPath"
            )

    # ------------------------------------------------------------------ #
    def _open_instances(self):
        for index in range(1, self.count + 1):
            if not win32gui.IsWindow(self.hwnd):
                raise RuntimeError("V5 主窗口已关闭")
            button = win32gui.GetDlgItem(self.hwnd, V5_OPEN_BUTTON_ID)
            if not button:
                raise RuntimeError("V5 主窗口没有找到“隔离打开程序”按钮")
            if not win32gui.IsWindowEnabled(button):
                deadline = time.time() + 3.0
                while time.time() < deadline and not win32gui.IsWindowEnabled(button):
                    time.sleep(0.1)
                if not win32gui.IsWindowEnabled(button):
                    raise RuntimeError("V5 的“隔离打开程序”按钮不可用")

            win32gui.SendMessage(button, win32con.BM_CLICK, 0, 0)
            self.logger(
                "V5 已发出第 [ %d / %d ] 个隔离打开：%s"
                % (index, self.count, os.path.basename(self.target_path))
            )
            time.sleep(0.4)
            if self.process is not None and self.process.poll() is not None:
                raise RuntimeError(
                    "V5 在打开实例后退出，exit=%s" % self.process.returncode
                )
            if index < self.count:
                time.sleep(self.interval)
