# -*- coding: utf-8 -*-
"""资源路径解析，兼容源码运行与 PyInstaller 打包运行。"""

import os
import sys


def app_root() -> str:
    """返回工程根目录（源码运行）或临时解包目录（打包运行）。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource(rel: str) -> str:
    return os.path.join(app_root(), rel.replace("/", os.sep))
