# -*- coding: utf-8 -*-
"""HJ212 模拟器启动入口。"""

import os
import sys

# 保证以脚本方式直接运行时也能导入同级包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.paths import resource
from app.theme import ThemeManager
from ui.main_window import APP_NAME, MainWindow


def main():
    if hasattr(Qt, "AA_ShareOpenGLContexts"):
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("HJ212Simulator")
    app.setStyle("Fusion")
    try:
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(resource("assets/icon.png")))
    except Exception:
        pass

    theme = ThemeManager(app)
    theme.apply("auto")

    win = MainWindow(theme)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
