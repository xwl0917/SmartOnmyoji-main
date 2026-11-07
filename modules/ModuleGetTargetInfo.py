# -*- coding: utf-8 -*-
# @Link    : https://github.com/aicezam/SmartOnmyoji
# @Version : Python3.7.6
# @MIT License Copyright (c) 2022 ACE

from os import path, walk
from re import compile
import json

import numpy as np
from numpy import uint8, fromfile
# from cv2 import cv2
import cv2
from modules.ModuleImgProcess import ImgProcess
from modules.ModuleGetConfig import ReadConfigFile


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
IMAGE_ORDER_FILE = "img_order.json"


def _normalize_rel_path(rel_path):
    return str(rel_path or "").replace("\\", "/").strip()


def _natural_key(text):
    return [
        int(part) if part.isdigit() else part.lower()
        for part in compile(r"(\d+)").split(_normalize_rel_path(text))
    ]


def list_target_image_files(folder_path, natural_sort=False):
    """列出目标目录下的图片，返回绝对路径。

    默认保持 os.walk 原顺序（兼容旧行为）；对话框可用 natural_sort=True
    得到按文件名自然排序的列表。
    """
    img_file_path = []
    for cur_dir, _sub_dir, included_file in walk(folder_path):
        for file in included_file:
            if path.splitext(file)[1].lower() in IMAGE_EXTENSIONS:
                img_file_path.append(path.join(cur_dir, file))
    if natural_sort:
        img_file_path.sort(
            key=lambda item: _natural_key(path.relpath(item, folder_path))
        )
    return img_file_path


def load_image_order(folder_path):
    """读取 img_order.json，返回相对路径列表；不存在或损坏时返回空列表。"""
    order_path = path.join(folder_path, IMAGE_ORDER_FILE)
    try:
        with open(order_path, "r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("order", [])
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if str(item).strip()]


def apply_image_order(folder_path, image_paths):
    """按 img_order.json 排序；未列出的新图片按自然顺序追加到末尾。

    没有 img_order.json 时保持传入顺序，不改变旧版行为。
    """
    order = load_image_order(folder_path)
    if not order:
        return list(image_paths)

    by_relative = {}
    for image_path in image_paths:
        by_relative[_normalize_rel_path(path.relpath(image_path, folder_path))] = image_path

    ordered = []
    used = set()
    for relative in order:
        key = _normalize_rel_path(relative)
        if key in by_relative and key not in used:
            ordered.append(by_relative[key])
            used.add(key)

    unlisted = []
    for image_path in image_paths:
        key = _normalize_rel_path(path.relpath(image_path, folder_path))
        if key not in used:
            unlisted.append(image_path)
            used.add(key)
    unlisted.sort(
        key=lambda item: _natural_key(path.relpath(item, folder_path))
    )
    ordered.extend(unlisted)
    return ordered


def save_image_order(folder_path, relative_order):
    """保存图片识别顺序到目标目录的 img_order.json。"""
    order_path = path.join(folder_path, IMAGE_ORDER_FILE)
    data = {
        "order": [
            _normalize_rel_path(relative)
            for relative in relative_order
            if _normalize_rel_path(relative)
        ]
    }
    with open(order_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


class GetTargetPicInfo:
    def __init__(self, target_modname, custom_target_path, compress_val=1, compute_sift=True):
        super(GetTargetPicInfo, self).__init__()
        self.modname = target_modname
        self.custom_target_path = custom_target_path
        self.target_folder_path = None
        self.compress_val = compress_val
        self.compute_sift = compute_sift

    def get_target_folder_path(self):
        """
        不同的模式下，匹配对应文件夹的图片
        :returns: 需要匹配的目标图片地址，如果没有返回空值
        """
        rc = ReadConfigFile()
        file_name = rc.read_config_target_path_files_name()  # 读取配置文件中的待匹配目标的名字信息

        parent_path = path.abspath(path.dirname(path.dirname(__file__)))  # 父路径

        # 通过界面上的选择目标，定位待匹配的目标文件夹
        for i in range(7):
            if self.modname == file_name[i][0]:
                target_folder_path = parent_path + r"\img\\" + file_name[i][1]
                return target_folder_path

        if self.modname == "自定义":
            target_folder_path = self.custom_target_path
            return target_folder_path
        else:
            return None

    @property
    def get_target_info(self):
        """获取目标图片文件夹路径下的所有图片信息"""
        target_img_sift = {}
        img_hw = {}
        img_name = []
        folder_path = self.get_target_folder_path()
        img_file_path = []
        cv2_img = {}

        # 获取每张图片的路径地址
        if folder_path is None:
            print("<br>未找到目标文件夹或图片地址！即将退出！")
            return None  # 脚本结束
        else:
            img_file_path = list_target_image_files(folder_path)
            if len(img_file_path) == 0:
                print("<br>未找到目标文件夹或图片地址！")
                return None  # 脚本结束

            # 有 img_order.json 时按界面保存的顺序加载；否则保持原有目录顺序
            if load_image_order(folder_path):
                img_file_path = apply_image_order(folder_path, img_file_path)

            # 通过图片地址获取每张图片的信息
            for i in range(len(img_file_path)):
                # img = cv2.imread(img_file_path[i])  # 读取图片地址的图片到内存中
                # img = np.uint8(cv2.imdecode(fromfile(img_file_path[i], dtype=uint8), -1))  # 修复中文路径下opencv报错问题
                img = cv2.imdecode(
                    fromfile(img_file_path[i], dtype=uint8), cv2.IMREAD_COLOR
                )
                if img is None or img.size == 0:
                    print(f"<br>目标图片无法读取或文件已损坏：[ {img_file_path[i]} ]")
                    return None
                img_process = ImgProcess()
                img_hw[i] = img.shape[:2]  # 获取目标图片宽高
                img_name.append(self.trans_path_to_name(img_file_path[i]))  # 获取目标图片名称
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                # print(f"<br><img src='{img_file_path[i]}' />")
                # img_process.show_img(img)
                # 只在特征点匹配模式下计算 SIFT，模板匹配模式可省掉启动时的特征提取
                if self.compute_sift:
                    target_img_sift[i] = img_process.get_sift(img)
                cv2_img[i] = img  # 将图片信息读取到内存

            return target_img_sift, img_hw, img_name, img_file_path, cv2_img  # 返回图片特征点信息，图片宽高，图片名称，图片路径地址，图片

    @staticmethod
    def trans_path_to_name(path_string):
        """获取指定文件路径的文件名称"""
        pattern = compile(r'([^<>/\\|:"*?]+)\.\w+$')
        data = pattern.findall(path_string)
        if data:
            return data[0]
