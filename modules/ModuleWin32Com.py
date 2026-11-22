# -*- coding: utf-8 -*-
"""重定向 win32com 的 gen_py 缓存目录。

部分电脑上杀毒软件的文件夹防护会拦截 python.exe 写入
%TEMP%\\gen_py 与 %LOCALAPPDATA%（表现为 WinError 5 拒绝访问），
导致 import win32com.client 时 gencache 重建缓存失败、程序无法启动。

本模块在导入 win32com.client 之前调用 configure_com_cache()：
按候选目录链找到第一个真正可写的位置，写探针文件验证后再重定向；
全部不可用时保留默认行为并打印提示，不抛异常中断启动。

必须在 import win32com.client 之前调用（modules/ModuleDoClick.py 与
modules/ModuleGetScreenCapture.py 已在各自 import 前调用）。
"""
import os
import sys
import tempfile

import win32com

_configured = False


def _is_writable(path):
    """创建目录并写入/删除探针文件，验证当前进程确实可写。"""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_probe")
        with open(probe, "w") as probe_file:
            probe_file.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _candidate_paths():
    version = "%d.%d" % (sys.version_info.major, sys.version_info.minor)
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    # 项目根目录（源码运行时为仓库根目录；打包后为 exe 同级的 _internal）
    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return [
        # 首选：用户目录，与“程序多开”的隔离目录同一根
        os.path.join(local_app_data, "SmartOnmyoji", "gen_py", version),
        # 备选：项目目录（config.ini/click_log 本就写在这里）
        os.path.join(app_root, "gen_py", version),
        # 最后手段：换一个名字避开可能被防护软件盯上的 %TEMP%\gen_py
        os.path.join(tempfile.gettempdir(), "SmartOnmyoji_gen_py", version),
    ]


def configure_com_cache():
    global _configured
    if _configured:
        return
    _configured = True

    for candidate in _candidate_paths():
        if _is_writable(candidate):
            break
    else:
        print(
            "<br>win32com 缓存目录均不可写，保留默认位置。"
            "若启动时仍报 gen_py 权限错误，请把 python 加入杀毒软件的信任名单，"
            "或删除 %TEMP%\\gen_py 后重试。"
        )
        return

    win32com.__gen_path__ = candidate
    # import win32com 时会合成一个 win32com.gen_py 模块（__path__ 指向默认目录），
    # 这里把它改指向我们的缓存目录，后续 gencache 生成/读取都会走新位置。
    gen_py = sys.modules["win32com.gen_py"]
    gen_py.__path__ = [candidate]
    win32com.gen_py = gen_py
