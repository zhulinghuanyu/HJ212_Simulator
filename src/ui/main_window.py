# -*- coding: utf-8 -*-
"""HJ212 模拟器主窗口。"""

from __future__ import annotations

import json
import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFileDialog, QFrame,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QPushButton, QSizePolicy,
                               QSplitter, QStackedWidget, QStatusBar, QToolBar,
                               QVBoxLayout, QWidget)

from app.theme import ThemeManager
from core.simulator import SimulatorEngine, SimConfig
from core import commands
from ui.pages import (BuilderPage, CodePage, ConnectPage, LogPage, MonitorPage,
                    SimPage, SettingsPage)

APP_NAME = "HJ212 模拟器"
APP_VERSION = "1.0.0"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".hj212_simulator.json")


def _emoji_icon(text: str, color: str, size: int = 28) -> QIcon:
    """用字符绘制简易图标，避免依赖外部资源文件。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.TextAntialiasing)
    f = QFont("Segoe UI Emoji", size * 0.55)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(pm.rect(), Qt.AlignCenter, text)
    p.end()
    return QIcon(pm)


class MainWindow(QMainWindow):
    def __init__(self, theme: ThemeManager):
        super().__init__()
        self.theme = theme
        self.engine = SimulatorEngine(self)
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}  ·  HJ/T 212-2005 / HJ 212-2017 / HJ 212-2025")
        self.resize(1280, 820)
        self.setMinimumSize(1040, 680)

        self._build_toolbar()
        self._build_body()
        self._build_status()
        self._connect_signals()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(1000)

        self.load_config()
        self.theme.themeChanged.connect(self._on_theme_changed)

    # ---------------- 界面骨架 ----------------
    def _build_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        title = QLabel("HJ212 模拟器")
        title.setProperty("title", True)
        tb.addWidget(title)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.btn_theme = QPushButton("◐ 主题")
        self.btn_theme.clicked.connect(self._cycle_theme)
        tb.addWidget(self.btn_theme)

        self.lbl_theme_mode = QLabel("自动")
        self.lbl_theme_mode.setProperty("dim", True)
        tb.addWidget(self.lbl_theme_mode)

    def _build_body(self):
        self.nav = QListWidget()
        self.nav.setFixedWidth(168)
        self.nav.setSpacing(2)
        self.nav.setFrameShape(QFrame.NoFrame)
        self.stack = QStackedWidget()

        self.pages = {}
        for key, name, icon in [("connect", "连接管理", "🔌"),
                                ("builder", "报文构建", "📨"),
                                ("sim", "数据模拟", "📈"),
                                ("monitor", "报文监控", "🔍"),
                                ("log", "通信日志", "📜"),
                                ("code", "编码字典", "📚"),
                                ("settings", "系统设置", "⚙️")]:
            item = QListWidgetItem(f"  {icon}   {name}")
            item.setSizeHint(item.sizeHint())
            item.setData(Qt.UserRole, key)
            self.nav.addItem(item)

        self.pages["connect"] = ConnectPage(self.engine)
        self.pages["builder"] = BuilderPage(self.engine)
        self.pages["sim"] = SimPage(self.engine)
        self.pages["monitor"] = MonitorPage(self.engine)
        self.pages["log"] = LogPage(self.engine)
        self.pages["code"] = CodePage()
        self.pages["settings"] = SettingsPage(self.engine, self.theme)
        for p in self.pages.values():
            self.stack.addWidget(p)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.nav)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.addWidget(splitter)
        self.setCentralWidget(root)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

    def _build_status(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.lbl_state = QLabel("● 未连接")
        self.lbl_stats = QLabel("收 0 | 发 0 | 校验失败 0")
        self.lbl_stats.setProperty("dim", True)
        self.lbl_ver = QLabel("")
        self.lbl_ver.setProperty("dim", True)
        sb.addWidget(self.lbl_state, 1)
        sb.addPermanentWidget(self.lbl_stats)
        sb.addPermanentWidget(self.lbl_ver)

    def _connect_signals(self):
        e = self.engine
        e.state.connect(self._on_state)
        e.stats.connect(self._on_stats)
        e.log.connect(self.pages["log"].append)
        e.packet_rx.connect(lambda p: self.pages["monitor"].add_packet(p, "rx"))
        e.packet_tx.connect(lambda p: self.pages["monitor"].add_packet(p, "tx"))
        e.clients.connect(self.pages["connect"].set_clients)
        self.pages["settings"].configChanged.connect(self._on_config_changed)

    # ---------------- 回调 ----------------
    def _on_state(self, state, desc):
        color = {"opened": "#1a9c5b", "closed": "#6b7688", "error": "#d64545"}.get(state, "#6b7688")
        self.lbl_state.setText(f'<span style="color:{color}">●</span> {desc}')
        self.pages["connect"].set_state(state, desc)

    def _on_stats(self, rx, tx, bad):
        self.lbl_stats.setText(f"收 {rx} | 发 {tx} | 校验失败 {bad}")

    def _on_config_changed(self, cfg: dict):
        self.engine.cfg.update(cfg)
        self.lbl_ver.setText("HJ212-" + self.engine.cfg.version +
                             (" | SM4 加密" if self.engine.cfg.sm4_enable else ""))
        for key in ("builder", "sim"):
            self.pages[key].sync_from_config(self.engine.cfg)
        self.save_config()

    def _refresh_status(self):
        if self.engine.is_open:
            self.pages["connect"].tick()

    def _on_theme_changed(self, eff):
        self.lbl_theme_mode.setText({"light": "亮色", "dark": "暗色"}.get(eff, eff))

    def _cycle_theme(self):
        order = {"light": "dark", "dark": "auto", "auto": "light"}
        nxt = order.get(self.theme.effective() if self.theme.mode == "auto" else self.theme.mode, "light")
        self.theme.mode = nxt
        self.theme.apply()
        self._on_theme_changed(self.theme.effective())
        self.pages["settings"].sync_theme()

    # ---------------- 配置持久化 ----------------
    def collect_config(self) -> dict:
        cfg = self.engine.cfg.to_dict()
        cfg["theme_mode"] = self.theme.mode
        cfg["conn"] = self.pages["connect"].collect()
        return cfg

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.collect_config(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            self._on_config_changed({})
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        cfg = {k: v for k, v in data.items() if k not in ("theme_mode", "conn")}
        self.engine.cfg.update(cfg)
        self.theme.mode = data.get("theme_mode", "auto")
        self.theme.apply()
        self._on_theme_changed(self.theme.effective())
        self.pages["connect"].apply(data.get("conn", {}))
        self.pages["settings"].sync_from_config(self.engine.cfg)
        self._on_config_changed({})

    def closeEvent(self, event):
        self.save_config()
        self.engine.close()
        super().closeEvent(event)
