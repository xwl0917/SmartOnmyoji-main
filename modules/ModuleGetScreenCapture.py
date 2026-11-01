# -*- coding: utf-8 -*-
# @Link    : https://github.com/aicezam/SmartOnmyoji
# @Version : Python3.7.6
# @MIT License Copyright (c) 2022 ACE

import time
from os.path import abspath, dirname
from subprocess import Popen, PIPE

import numpy as np
import win32com.client
from numpy import frombuffer, uint8, array
from win32con import SRCCOPY
from win32gui import DeleteObject, SetForegroundWindow, GetWindowRect, GetWindowDC, ReleaseDC
from win32ui import CreateDCFromHandle, CreateBitmap
# from cv2 import cv2
import cv2
from PIL import ImageGrab

from modules.ModuleGetConfig import ReadConfigFile


class GetScreenCapture:
    def __init__(self, handle_num=0, handle_width=0, handle_height=0):
        super(GetScreenCapture, self).__init__()
        self.hwd_num = handle_num
        self.screen_width = handle_width
        self.screen_height = handle_height
        self.screen_scale_rate = get_screen_scale_rate()  # 尝试获取屏幕分辨率缩放比例（暂未能找到自动获取的方法）
        self.dpi_scale = get_window_dpi_scale(handle_num) if handle_num else 1.0
        if handle_num and abs(self.dpi_scale - self.screen_scale_rate) > 0.01:
            warning_key = (round(self.dpi_scale, 2), round(self.screen_scale_rate, 2))
            if warning_key not in _DPI_WARNING_KEYS:
                _DPI_WARNING_KEYS.add(warning_key)
                print(
                    f"<br>提示：窗口 DPI 缩放约 {self.dpi_scale:.2f}，"
                    f"config 的 screen_scale_rate 为 {self.screen_scale_rate:.2f}；"
                    f"若截图或点击偏移，请把两者调成一致。"
                )

    def window_screen(self):
        """windows api 窗体截图方法，可后台截图，可被遮挡，不兼容部分窗口"""
        hwnd = self.hwd_num
        screen_width = self.screen_width
        screen_height = self.screen_height

        screen_width_source = int(screen_width / self.screen_scale_rate)
        screen_height_source = int(screen_height / self.screen_scale_rate)

        # 返回句柄窗口的设备环境，覆盖整个窗口，包括非客户区，标题栏，菜单，边框
        hwnd_dc = GetWindowDC(hwnd)
        mfc_dc = None
        save_dc = None
        save_bit_map = None
        try:
            # 创建设备描述表
            mfc_dc = CreateDCFromHandle(hwnd_dc)
            # 创建内存设备描述表
            save_dc = mfc_dc.CreateCompatibleDC()
            # 创建位图对象准备保存图片
            save_bit_map = CreateBitmap()
            # 为bitmap开辟存储空间
            save_bit_map.CreateCompatibleBitmap(mfc_dc, screen_width_source, screen_height_source)
            # 将截图保存到saveBitMap中
            save_dc.SelectObject(save_bit_map)
            # 保存bitmap到内存设备描述表
            save_dc.BitBlt((0, 0), (screen_width_source, screen_height_source), mfc_dc, (0, 0), SRCCOPY)

            # 保存图像
            signed_ints_array = save_bit_map.GetBitmapBits(True)
            im_opencv = frombuffer(signed_ints_array, dtype='uint8')
            im_opencv.shape = (screen_height_source, screen_width_source, 4)
            im_opencv = cv2.cvtColor(im_opencv, cv2.COLOR_BGRA2GRAY)
            # 缩放率为 1 时源尺寸与目标尺寸相同，跳过一次整帧 resize
            if (screen_width, screen_height) != (screen_width_source, screen_height_source):
                im_opencv = cv2.resize(im_opencv, (screen_width, screen_height))
            print("<br>截图成功！")
            return im_opencv
        finally:
            # 先删内存 DC（会取消位图选中），再删位图，最后释放窗口 DC
            if save_dc is not None:
                try:
                    save_dc.DeleteDC()
                except Exception:
                    pass
            if save_bit_map is not None:
                try:
                    DeleteObject(save_bit_map.GetHandle())
                except Exception:
                    pass
            # mfc_dc 只是 GetWindowDC 返回句柄的包装，不能对它调用 DeleteDC；
            # 窗口 DC 必须用 ReleaseDC 释放，否则会泄漏 GDI 句柄。
            try:
                ReleaseDC(hwnd, hwnd_dc)
            except Exception:
                pass

    def window_screen_bk(self):
        """PIL截图方法，不能被遮挡"""
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys('%')
        SetForegroundWindow(self.hwd_num)  # 窗口置顶
        time.sleep(0.2)  # 置顶后等0.2秒再截图
        x1, y1, x2, y2 = GetWindowRect(self.hwd_num)  # 获取窗口坐标
        grab_image = ImageGrab.grab((x1, y1, x2, y2))  # 用PIL方法截图
        im_cv2 = array(grab_image)  # 转换为cv2的矩阵格式
        # PIL 返回 RGB/RGBA；不能无条件用 BGRA 常量，否则 3 通道时会报通道数错误
        if im_cv2.ndim == 3 and im_cv2.shape[2] == 4:
            im_opencv = cv2.cvtColor(im_cv2, cv2.COLOR_RGBA2GRAY)
        else:
            im_opencv = cv2.cvtColor(im_cv2, cv2.COLOR_RGB2GRAY)

        # 统一到“窗口矩形”像素坐标，避免高 DPI 下截图物理像素与 GetWindowRect 逻辑像素不一致
        target_width = int(x2 - x1)
        target_height = int(y2 - y1)
        if (
            target_width > 0
            and target_height > 0
            and (im_opencv.shape[1], im_opencv.shape[0]) != (target_width, target_height)
        ):
            im_opencv = cv2.resize(im_opencv, (target_width, target_height))
        print("<br>截图成功！")

        return im_opencv

    @staticmethod
    def adb_screen(device_id):
        """安卓手机/模拟器 adb 截图。

        优先使用 `adb exec-out screencap -p`：部分 adb/Windows 组合下
        `adb shell screencap -p` 会把 PNG 的 LF 转成 CRLF，导致 cv2 解码失败。
        旧 adb 不支持 exec-out 时再回退到 shell，并做 CRLF 修正。
        """
        adb_path = abspath(dirname(__file__)) + r'\adb.exe'
        device_id = str(device_id)
        commands = (
            [adb_path, "-s", device_id, "exec-out", "screencap", "-p"],
            [adb_path, "-s", device_id, "shell", "screencap", "-p"],
        )

        img_bytes = b""
        last_error = ""
        for command in commands:
            process = Popen(command, stdout=PIPE, stderr=PIPE)
            try:
                data, error = process.communicate(timeout=20)
            except Exception as exc:
                try:
                    process.kill()
                    process.communicate(timeout=3)
                except Exception:
                    pass
                last_error = str(exc)
                continue

            if command[3] == "shell":
                # shell 通道在 Windows 下可能把 \n 变成 \r\n
                data = data.replace(b'\r\n', b'\n')
            if data.startswith(b'\x89PNG\r\n\x1a\n'):
                img_bytes = data
                break
            last_error = (error or data[:200]).decode("utf-8", "replace")

        if not img_bytes:
            print("<br>ADB截图数据为空或无法解码，请检查设备连接和ADB截图权限。")
            if last_error:
                print(f"<br>ADB截图错误：{last_error}")
            return None

        scr_img = cv2.imdecode(frombuffer(img_bytes, uint8), cv2.IMREAD_COLOR)
        if scr_img is None or scr_img.size == 0:
            print("<br>ADB截图数据为空或无法解码，请检查设备连接和ADB截图权限。")
            return None
        scr_img = cv2.cvtColor(scr_img, cv2.COLOR_BGR2GRAY)
        print("<br>截图成功！")
        return scr_img


_SCREEN_SCALE_RATE_CACHE = None
_DPI_WARNING_KEYS = set()


def get_window_dpi_scale(handle_num):
    """获取窗口所在显示器的 DPI 缩放比例（仅用于提示，不自动改坐标体系）"""
    try:
        import ctypes
        dpi = ctypes.windll.user32.GetDpiForWindow(handle_num)
        return dpi / 96.0 if dpi else 1.0
    except Exception:
        return 1.0


def reset_screen_scale_rate_cache():
    """每轮开始前清空缩放率缓存，使界面上的新设置能够生效"""
    global _SCREEN_SCALE_RATE_CACHE
    _SCREEN_SCALE_RATE_CACHE = None


def get_screen_scale_rate():
    """获取缩放比例（进程内缓存；每轮开始时会由 reset_... 刷新）"""
    global _SCREEN_SCALE_RATE_CACHE
    if _SCREEN_SCALE_RATE_CACHE is None:
        set_config = ReadConfigFile()  # 读取配置文件
        other_setting = set_config.read_config_other_setting()
        _SCREEN_SCALE_RATE_CACHE = float(other_setting[11])
    return _SCREEN_SCALE_RATE_CACHE
