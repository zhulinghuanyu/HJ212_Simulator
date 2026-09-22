# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（Windows / macOS / Linux 通用）。"""

import sys

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"]
try:
    hiddenimports += collect_submodules("serial")
except Exception:
    hiddenimports += ["serial", "serial.tools.list_ports"]

excludes = [
    "tkinter", "matplotlib", "numpy", "pandas", "pytest", "IPython",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtNfc",
    "PySide6.QtPositioning", "PySide6.QtSerialPort", "PySide6.QtRemoteObjects",
    "PySide6.QtSensors", "PySide6.QtSpatialAudio", "PySide6.QtStateMachine",
    "PySide6.QtTextToSpeech", "PySide6.QtWebSockets", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtHttpServer", "PySide6.QtUiTools",
]

icon = "assets/icon.ico" if sys.platform.startswith("win") else "assets/icon.png"

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=[],
    datas=[("assets/icon.png", "assets"), ("README.md", "."), ("LICENSE", ".")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HJ212Simulator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # GUI 程序，不弹控制台
    disable_windowed_traceback=False,
    icon=icon,
    version=None,
)
