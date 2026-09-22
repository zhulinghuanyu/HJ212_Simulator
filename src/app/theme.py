# -*- coding: utf-8 -*-
"""主题管理：自动（跟随系统）/ 亮色 / 暗色。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication, QPalette, QColor
from PySide6.QtWidgets import QApplication

LIGHT = {
    "bg": "#f4f6fa",
    "panel": "#ffffff",
    "panel_alt": "#eef2f9",
    "text": "#1d2430",
    "text_dim": "#6b7688",
    "border": "#dde3ee",
    "accent": "#2f6fd0",
    "accent_text": "#ffffff",
    "accent_soft": "#e5efff",
    "ok": "#1a9c5b",
    "warn": "#c98200",
    "err": "#d64545",
    "sel": "#dbe8ff",
    "rx": "#1a6fb8",
    "tx": "#1a9c5b",
}

DARK = {
    "bg": "#151922",
    "panel": "#1c2230",
    "panel_alt": "#232b3b",
    "text": "#e6ebf5",
    "text_dim": "#8b97ad",
    "border": "#2c3547",
    "accent": "#4d90ff",
    "accent_text": "#ffffff",
    "accent_soft": "#223350",
    "ok": "#4ec98a",
    "warn": "#e0a33a",
    "err": "#ef6b6b",
    "sel": "#294066",
    "rx": "#68b7f0",
    "tx": "#5fd39b",
}

QSS_TEMPLATE = """
QWidget {{
    background: {bg};
    color: {text};
    font-family: "Microsoft YaHei UI", "PingFang SC", "WenQuanYi Micro Hei", "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{ background: {bg}; }}
QMenuBar {{ background: {panel}; border-bottom: 1px solid {border}; padding: 2px; }}
QMenuBar::item:selected {{ background: {accent_soft}; border-radius: 6px; }}
QMenu {{ background: {panel}; border: 1px solid {border}; padding: 4px; }}
QMenu::item:selected {{ background: {accent}; color: {accent_text}; border-radius: 4px; }}

QToolBar {{ background: {panel}; border: none; padding: 6px; spacing: 6px; }}
QToolButton {{ color: {text}; padding: 4px 8px; border-radius: 6px; }}
QToolButton:hover {{ background: {panel_alt}; }}

QPushButton {{
    background: {panel}; color: {text};
    border: 1px solid {border}; border-radius: 8px;
    padding: 7px 16px; min-height: 16px;
}}
QPushButton:hover {{ border-color: {accent}; background: {accent_soft}; }}
QPushButton:pressed {{ background: {sel}; }}
QPushButton:disabled {{ color: {text_dim}; background: {panel_alt}; border-color: {border}; }}
QPushButton[accent="true"] {{
    background: {accent}; color: {accent_text}; border: 1px solid {accent}; font-weight: 600;
}}
QPushButton[accent="true"]:hover {{ background: {accent}; border-color: {accent}; }}
QPushButton[danger="true"] {{ color: {err}; border-color: {err}; }}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {panel}; color: {text};
    border: 1px solid {border}; border-radius: 8px; padding: 6px 8px;
    selection-background-color: {accent}; selection-color: {accent_text};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border-color: {accent};
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {panel}; color: {text}; border: 1px solid {border};
    selection-background-color: {accent}; selection-color: {accent_text};
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; }}

QGroupBox {{
    border: 1px solid {border}; border-radius: 10px;
    margin-top: 14px; padding: 12px 10px 10px 10px; background: {panel};
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: {accent}; font-weight: 600;
}}

QTabWidget::pane {{ border: 1px solid {border}; border-radius: 10px; background: {panel}; top: -1px; }}
QTabBar::tab {{
    background: transparent; color: {text_dim};
    padding: 8px 18px; margin-right: 2px; border-radius: 8px;
}}
QTabBar::tab:selected {{ background: {accent_soft}; color: {accent}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {text}; }}

QTableWidget, QTreeWidget, QListWidget {{
    background: {panel}; alternate-background-color: {panel_alt};
    border: 1px solid {border}; border-radius: 10px;
    gridline-color: {border}; outline: none;
}}
QHeaderView::section {{
    background: {panel_alt}; color: {text}; font-weight: 600;
    border: none; border-right: 1px solid {border}; border-bottom: 1px solid {border};
    padding: 7px 8px;
}}
QTableWidget::item, QTreeWidget::item {{ padding: 4px 6px; }}
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {sel}; color: {text};
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {text_dim}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QSplitter::handle {{ background: {border}; }}
QStatusBar {{ background: {panel}; color: {text_dim}; border-top: 1px solid {border}; }}
QLabel[dim="true"] {{ color: {text_dim}; }}
QLabel[title="true"] {{ font-size: 16px; font-weight: 700; color: {text}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {border}; background: {panel}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 8px; border: 1px solid {border}; background: {panel}; }}
QRadioButton::indicator:checked {{ background: {accent}; border-color: {accent}; }}
QProgressBar {{ border: 1px solid {border}; border-radius: 6px; background: {panel}; text-align: center; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 6px; }}
QToolTip {{ background: {panel}; color: {text}; border: 1px solid {border}; }}
"""


class ThemeManager(QObject):
    """统一管理应用配色，支持 auto / light / dark。"""

    themeChanged = Signal(str)   # 实际生效的模式：light / dark

    def __init__(self, app: QApplication, parent=None):
        super().__init__(parent)
        self.app = app
        self.mode = "auto"      # auto / light / dark
        self._effective = "light"
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_scheme)

    # ---------- 查询 ----------
    def system_is_dark(self) -> bool:
        hints = QGuiApplication.styleHints()
        try:
            from PySide6.QtCore import Qt
            return hints.colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            pal = self.app.palette()
            return pal.color(QPalette.Window).lightness() < 128

    def effective(self) -> str:
        if self.mode == "auto":
            return "dark" if self.system_is_dark() else "light"
        return self.mode

    def tokens(self) -> dict:
        return DARK if self.effective() == "dark" else LIGHT

    # ---------- 应用 ----------
    def apply(self, mode: str | None = None):
        if mode:
            self.mode = mode
        eff = self.effective()
        t = self.tokens()
        self.app.setStyleSheet(QSS_TEMPLATE.format(**t))
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(t["bg"]))
        pal.setColor(QPalette.WindowText, QColor(t["text"]))
        pal.setColor(QPalette.Base, QColor(t["panel"]))
        pal.setColor(QPalette.AlternateBase, QColor(t["panel_alt"]))
        pal.setColor(QPalette.Text, QColor(t["text"]))
        pal.setColor(QPalette.Button, QColor(t["panel"]))
        pal.setColor(QPalette.ButtonText, QColor(t["text"]))
        pal.setColor(QPalette.Highlight, QColor(t["accent"]))
        pal.setColor(QPalette.HighlightedText, QColor(t["accent_text"]))
        pal.setColor(QPalette.Link, QColor(t["accent"]))
        pal.setColor(QPalette.Disabled, QPalette.Text, QColor(t["text_dim"]))
        self.app.setPalette(pal)
        if eff != self._effective or True:
            self._effective = eff
            self.themeChanged.emit(eff)

    def _on_system_scheme(self, *_):
        if self.mode == "auto":
            self.apply()

    def toggle(self):
        self.apply("dark" if self.effective() == "light" else "light")
