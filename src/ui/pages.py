# -*- coding: utf-8 -*-
"""主窗口各功能页面。"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
                               QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPlainTextEdit, QPushButton,
                               QRadioButton, QSpinBox, QSplitter, QTabWidget,
                               QTableWidget, QTableWidgetItem, QTextEdit,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget, QButtonGroup)

from core import commands
from core.packet import Packet, make_flag, now_qn, split_frames
from core.transport import HAS_SERIAL, list_serial_ports, local_ip

MONO = 'Consolas, "Courier New", "WenQuanYi Micro Hei", monospace'


def _mono(widget, size=12):
    f = QFont()
    f.setFamily("Consolas")
    f.setPointSize(size)
    widget.setFont(f)
    return widget


class _BasePage(QWidget):
    def sync_from_config(self, cfg):
        pass


# ==================================================================== 连接
class ConnectPage(_BasePage):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        t = QLabel("连接管理")
        t.setProperty("title", True)
        head.addWidget(t)
        head.addStretch(1)
        self.lbl_state = QLabel("● 未连接")
        self.lbl_state.setProperty("dim", True)
        head.addWidget(self.lbl_state)
        root.addLayout(head)

        # 模式
        mode_box = QGroupBox("通道类型")
        ml = QHBoxLayout(mode_box)
        self.rb_tcpc = QRadioButton("TCP 客户端（连接平台）")
        self.rb_tcps = QRadioButton("TCP 服务端（模拟平台）")
        self.rb_serial = QRadioButton("串口（RS232/RS485）")
        self.rb_tcpc.setChecked(True)
        self.bg_mode = QButtonGroup(self)
        for rb in (self.rb_tcpc, self.rb_tcps, self.rb_serial):
            ml.addWidget(rb)
            self.bg_mode.addButton(rb)
        ml.addStretch(1)
        root.addWidget(mode_box)

        # 参数
        param = QGroupBox("连接参数")
        pl = QGridLayout(param)
        pl.setVerticalSpacing(8)
        self.ed_host = QLineEdit(local_ip())
        self.ed_port = QSpinBox()
        self.ed_port.setRange(1, 65535)
        self.ed_port.setValue(9000)
        self.ed_lport = QSpinBox()
        self.ed_lport.setRange(1, 65535)
        self.ed_lport.setValue(10000)
        self.cb_serial = QComboBox()
        self.cb_serial.setEditable(True)
        self._refresh_ports()
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self._refresh_ports)
        self.cb_baud = QComboBox()
        self.cb_baud.addItems(["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"])
        self.cb_baud.setCurrentText("9600")
        self.cb_bytesize = QComboBox()
        self.cb_bytesize.addItems(["5", "6", "7", "8"])
        self.cb_bytesize.setCurrentText("8")
        self.cb_parity = QComboBox()
        self.cb_parity.addItems(["N", "E", "O", "M", "S"])
        self.cb_stop = QComboBox()
        self.cb_stop.addItems(["1", "1.5", "2"])
        self.cb_encoding = QComboBox()
        self.cb_encoding.addItems(["utf-8", "gbk", "gb2312", "latin1"])
        self.cb_version = QComboBox()
        self.cb_version.addItems(["HJ/T 212-2005", "HJ 212-2017", "HJ 212-2025"])
        self.cb_version.setCurrentIndex(1)

        pl.addWidget(QLabel("平台 IP / 域名"), 0, 0)
        pl.addWidget(self.ed_host, 0, 1)
        pl.addWidget(QLabel("平台端口"), 0, 2)
        pl.addWidget(self.ed_port, 0, 3)
        pl.addWidget(QLabel("本地监听端口"), 1, 0)
        pl.addWidget(self.ed_lport, 1, 1)
        pl.addWidget(QLabel("串口号"), 2, 0)
        pl.addWidget(self.cb_serial, 2, 1)
        pl.addWidget(btn_refresh, 2, 2)
        pl.addWidget(QLabel("波特率"), 3, 0)
        pl.addWidget(self.cb_baud, 3, 1)
        pl.addWidget(QLabel("数据位"), 3, 2)
        pl.addWidget(self.cb_bytesize, 3, 3)
        pl.addWidget(QLabel("校验位"), 4, 0)
        pl.addWidget(self.cb_parity, 4, 1)
        pl.addWidget(QLabel("停止位"), 4, 2)
        pl.addWidget(self.cb_stop, 4, 3)
        pl.addWidget(QLabel("字符编码"), 5, 0)
        pl.addWidget(self.cb_encoding, 5, 1)
        pl.addWidget(QLabel("协议版本"), 5, 2)
        pl.addWidget(self.cb_version, 5, 3)
        root.addWidget(param)

        # 操作
        ops = QHBoxLayout()
        self.btn_open = QPushButton("打开通道")
        self.btn_open.setProperty("accent", True)
        self.btn_open.clicked.connect(self.open_channel)
        self.btn_close = QPushButton("关闭通道")
        self.btn_close.setProperty("danger", True)
        self.btn_close.clicked.connect(self.engine.close)
        self.btn_close.setEnabled(False)
        ops.addWidget(self.btn_open)
        ops.addWidget(self.btn_close)
        ops.addStretch(1)
        self.lbl_hint = QLabel("")
        self.lbl_hint.setProperty("dim", True)
        ops.addWidget(self.lbl_hint)
        root.addLayout(ops)

        # 客户端
        cl = QGroupBox("已接入客户端（TCP 服务端模式）")
        cl_l = QVBoxLayout(cl)
        self.lst_clients = QListWidget()
        self.lst_clients.setMaximumHeight(140)
        cl_l.addWidget(self.lst_clients)
        root.addWidget(cl)
        root.addStretch(1)

        self._sync_mode()
        self.bg_mode.buttonClicked.connect(self._sync_mode)
        self.cb_version.currentIndexChanged.connect(self._on_version)
        self.cb_encoding.currentTextChanged.connect(
            lambda v: setattr(self.engine.cfg, "encoding", v))

    def _refresh_ports(self):
        self.cb_serial.clear()
        ports = list_serial_ports()
        self.cb_serial.addItems(ports or (["COM1", "/dev/ttyS0"] if not HAS_SERIAL else []))
        if not HAS_SERIAL:
            self.lbl_hint.setText("提示：未检测到 pyserial，串口功能不可用")

    def _sync_mode(self, *_):
        is_client = self.rb_tcpc.isChecked()
        is_server = self.rb_tcps.isChecked()
        self.ed_host.setEnabled(is_client)
        self.ed_port.setEnabled(is_client)
        self.ed_lport.setEnabled(is_server)
        for w in (self.cb_serial, self.cb_baud, self.cb_bytesize, self.cb_parity, self.cb_stop):
            w.setEnabled(self.rb_serial.isChecked())

    def _on_version(self, idx):
        self.engine.cfg.version = ["2005", "2017", "2025"][idx]

    def set_state(self, state, desc):
        color = {"opened": "#1a9c5b", "closed": "#6b7688", "error": "#d64545"}.get(state, "#6b7688")
        self.lbl_state.setText(f'<span style="color:{color}">●</span> {desc}')
        opened = state == "opened"
        self.btn_open.setEnabled(not opened)
        self.btn_close.setEnabled(opened)

    def tick(self):
        pass

    def set_clients(self, lst):
        self.lst_clients.clear()
        for c in lst:
            self.lst_clients.addItem(QListWidgetItem(c))

    def open_channel(self):
        try:
            if self.rb_tcpc.isChecked():
                self.engine.open_tcp_client(self.ed_host.text().strip(), self.ed_port.value())
                self.lbl_hint.setText("已作为现场机连接平台")
            elif self.rb_tcps.isChecked():
                self.engine.open_tcp_server("0.0.0.0", self.ed_lport.value())
                self.lbl_hint.setText("监听端口 %d，等待现场机接入" % self.ed_lport.value())
            else:
                self.engine.open_serial(
                    self.cb_serial.currentText().strip(), int(self.cb_baud.currentText()),
                    int(self.cb_bytesize.currentText()), self.cb_parity.currentText(),
                    float(self.cb_stop.currentText()))
                self.lbl_hint.setText("串口已打开")
        except Exception as exc:
            QMessageBox.warning(self, "打开失败", str(exc))

    def collect(self):
        return {"mode": ["tcp_client", "tcp_server", "serial"][
            [self.rb_tcpc.isChecked(), self.rb_tcps.isChecked(), self.rb_serial.isChecked()].index(True)],
            "host": self.ed_host.text(), "port": self.ed_port.value(),
            "lport": self.ed_lport.value(), "serial": self.cb_serial.currentText(),
            "baud": int(self.cb_baud.currentText()), "encoding": self.cb_encoding.currentText(),
            "version": self.engine.cfg.version}

    def apply(self, data: dict):
        if not data:
            return
        mode = data.get("mode", "tcp_client")
        {"tcp_client": self.rb_tcpc, "tcp_server": self.rb_tcps,
         "serial": self.rb_serial}[mode].setChecked(True)
        self.ed_host.setText(data.get("host", local_ip()))
        self.ed_port.setValue(data.get("port", 9000))
        self.ed_lport.setValue(data.get("lport", 10000))
        if data.get("serial"):
            self.cb_serial.setCurrentText(data["serial"])
        self.cb_baud.setCurrentText(str(data.get("baud", 9600)))
        self.cb_encoding.setCurrentText(data.get("encoding", "utf-8"))
        self.cb_version.setCurrentText({"2005": "HJ/T 212-2005", "2017": "HJ 212-2017",
                                        "2025": "HJ 212-2025"}.get(data.get("version", "2017")))
        self._sync_mode()


# ==================================================================== 报文构建
class BuilderPage(_BasePage):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        head = QHBoxLayout()
        t = QLabel("报文构建 / 解析")
        t.setProperty("title", True)
        head.addWidget(t)
        head.addStretch(1)
        root.addLayout(head)

        body = QSplitter(Qt.Horizontal)

        # --- 左：字段 ---
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        gb = QGroupBox("报文字段")
        form = QFormLayout(gb)
        form.setSpacing(8)
        self.cb_ver = QComboBox()
        self.cb_ver.addItems(["HJ/T 212-2005", "HJ 212-2017", "HJ 212-2025"])
        self.cb_ver.setCurrentIndex(1)
        self.ed_qn = QLineEdit()
        self.ed_qn.setPlaceholderText("留空自动生成（时间戳毫秒）")
        self.cb_st = QComboBox()
        self.cb_st.setEditable(True)
        self.cb_st.addItems([f"{k} - {v}" for k, v in commands.SYSTEM_CODES.items()])
        self.cb_st.setCurrentText("32 - " + commands.SYSTEM_CODES["32"])
        self.cb_cn = QComboBox()
        self.cb_cn.setEditable(True)
        self.cb_cn.addItems([f"{k} - {v}" for k, v in commands.COMMAND_CODES.items()])
        self.cb_cn.setCurrentText("2011 - " + commands.COMMAND_CODES["2011"])
        self.ed_pw = QLineEdit("123456")
        self.ed_mn = QLineEdit("010000A8900016F000169DC0")
        self.chk_answer = QCheckBox("需要应答 (Flag.A=1)")
        self.chk_answer.setChecked(True)
        self.chk_split = QCheckBox("允许拆分包 (Flag.D=1)")
        self.ed_rf = QLineEdit()
        self.ed_rf.setPlaceholderText("补传标志 RF，如 1（可留空）")
        form.addRow("协议版本", self.cb_ver)
        form.addRow("QN 请求编号", self.ed_qn)
        form.addRow("ST 系统编码", self.cb_st)
        form.addRow("CN 命令编码", self.cb_cn)
        form.addRow("PW 访问密码", self.ed_pw)
        form.addRow("MN 设备标识", self.ed_mn)
        form.addRow(self.chk_answer, self.chk_split)
        form.addRow("RF 补传", self.ed_rf)
        ll.addWidget(gb)

        gb2 = QGroupBox("数据区 CP")
        v2 = QVBoxLayout(gb2)
        self.tbl_cp = QTableWidget(0, 2)
        self.tbl_cp.setHorizontalHeaderLabels(["字段名", "值"])
        self.tbl_cp.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_cp.setColumnWidth(0, 180)
        self.tbl_cp.verticalHeader().setVisible(False)
        self.tbl_cp.setMinimumHeight(180)
        v2.addWidget(self.tbl_cp)
        btns = QHBoxLayout()
        for text, fn in [("+ 添加", self._add_row), ("- 删除", self._del_row),
                         ("插入 DataTime", self._ins_time), ("清空", self._clear_cp)]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            btns.addWidget(b)
        btns.addStretch(1)
        v2.addLayout(btns)
        ll.addWidget(gb2, 1)
        body.addWidget(left)

        # --- 右：预览 ---
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        gb3 = QGroupBox("生成报文")
        v3 = QVBoxLayout(gb3)
        self.txt_frame = _mono(QPlainTextEdit())
        self.txt_frame.setPlaceholderText("点击「生成报文」后显示完整通讯包")
        v3.addWidget(self.txt_frame, 1)
        self.lbl_info = QLabel("")
        self.lbl_info.setProperty("dim", True)
        v3.addWidget(self.lbl_info)
        hb = QHBoxLayout()
        b_gen = QPushButton("生成报文")
        b_gen.setProperty("accent", True)
        b_gen.clicked.connect(self.generate)
        b_send = QPushButton("发送")
        b_send.clicked.connect(self.send)
        b_copy = QPushButton("复制")
        b_copy.clicked.connect(self.copy)
        for b in (b_gen, b_send, b_copy):
            hb.addWidget(b)
        hb.addStretch(1)
        v3.addLayout(hb)
        rl.addWidget(gb3, 2)

        gb4 = QGroupBox("报文解析（粘贴报文后点解析）")
        v4 = QVBoxLayout(gb4)
        self.txt_in = _mono(QPlainTextEdit())
        self.txt_in.setPlaceholderText("粘贴 ##xxxxQN=...;CP=&&...&&xxxx\\r\\n")
        v4.addWidget(self.txt_in, 1)
        hb2 = QHBoxLayout()
        b_parse = QPushButton("解析")
        b_parse.clicked.connect(self.parse)
        b_clr = QPushButton("清空")
        b_clr.clicked.connect(self.txt_in.clear)
        hb2.addWidget(b_parse)
        hb2.addWidget(b_clr)
        hb2.addStretch(1)
        v4.addLayout(hb2)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["字段", "值"])
        self.tree.setColumnWidth(0, 160)
        self.tree.setAlternatingRowColors(True)
        v4.addWidget(self.tree, 1)
        rl.addWidget(gb4, 2)
        body.addWidget(right)

        body.setStretchFactor(0, 4)
        body.setStretchFactor(1, 5)
        root.addWidget(body, 1)

        self.cb_ver.currentIndexChanged.connect(self._ver_changed)
        self._ins_time()
        self._add_row("a21026-Rtd", "12.345")
        self._add_row("a21026-Flag", "N")

    # ---- 数据区表格 ----
    def _add_row(self, k="", v=""):
        r = self.tbl_cp.rowCount()
        self.tbl_cp.insertRow(r)
        self.tbl_cp.setItem(r, 0, QTableWidgetItem(k))
        self.tbl_cp.setItem(r, 1, QTableWidgetItem(v))

    def _del_row(self):
        r = self.tbl_cp.currentRow()
        if r >= 0:
            self.tbl_cp.removeRow(r)

    def _clear_cp(self):
        self.tbl_cp.setRowCount(0)

    def _ins_time(self):
        self._add_row("DataTime", time.strftime("%Y%m%d%H%M%S"))

    def _ver_changed(self, idx):
        ver = ["2005", "2017", "2025"][idx]
        self.engine.cfg.version = ver
        self.ed_mn.setPlaceholderText("14 位（2005）" if ver == "2005" else "24 位（2017/2025）")

    # ---- 组装 ----
    def build_packet(self) -> Packet:
        ver = ["2005", "2017", "2025"][self.cb_ver.currentIndex()]
        cn = self.cb_cn.currentText().split(" - ")[0].strip()
        st = self.cb_st.currentText().split(" - ")[0].strip()
        items = []
        for r in range(self.tbl_cp.rowCount()):
            k = (self.tbl_cp.item(r, 0) or QTableWidgetItem("")).text().strip()
            v = (self.tbl_cp.item(r, 1) or QTableWidgetItem("")).text().strip()
            if k:
                items.append((k, v))
        return Packet(qn=self.ed_qn.text().strip() or now_qn(), st=st, cn=cn,
                      pw=self.ed_pw.text().strip(), mn=self.ed_mn.text().strip(),
                      version=ver, need_answer=self.chk_answer.isChecked(),
                      split=self.chk_split.isChecked(), rf=self.ed_rf.text().strip() or None,
                      cp_items=items)

    def generate(self):
        pkt = self.build_packet()
        frames = pkt.encode_frames()
        self.txt_frame.setPlainText("".join(frames))
        self.engine.cfg.version = pkt.version
        self.lbl_info.setText("共 %d 包 | 数据段 %d 字节 | Flag=%d"
                              % (len(frames), len(pkt.data_segment()), make_flag(
                                  pkt.version, pkt.need_answer, pkt.split)))
        return pkt

    def send(self):
        if not self.txt_frame.toPlainText().strip():
            self.generate()
        if not self.engine.is_open:
            QMessageBox.information(self, "提示", "请先在「连接管理」中打开通道")
            return
        try:
            self.engine.send_raw(self.txt_frame.toPlainText().strip())
        except Exception as exc:
            QMessageBox.warning(self, "发送失败", str(exc))

    def copy(self):
        from PySide6.QtWidgets import QApplication as _App
        _App.clipboard().setText(self.txt_frame.toPlainText())
        self.lbl_info.setText("已复制到剪贴板")

    def parse(self):
        self.tree.clear()
        text = self.txt_in.toPlainText().strip()
        if not text:
            return
        frames, _ = split_frames(text.replace("\\r\\n", "\r\n"))
        if not frames:
            frames = [text]
        for f in frames:
            try:
                pkt = Packet.decode(f)
            except Exception as exc:
                item = QTreeWidgetItem(["解析失败", str(exc)])
                self.tree.addTopLevelItem(item)
                continue
            top = QTreeWidgetItem([f"报文 {pkt.cn}", commands.cn_name(pkt.cn)])
            for k, v in pkt.to_rows():
                top.addChild(QTreeWidgetItem([k, v]))
            self.tree.addTopLevelItem(top)
            top.setExpanded(True)
        self.tree.resizeColumnToContents(0)

    def sync_from_config(self, cfg):
        idx = {"2005": 0, "2017": 1, "2025": 2}.get(cfg.version, 1)
        self.cb_ver.setCurrentIndex(idx)
        self.ed_mn.setText(cfg.mn)
        self.ed_pw.setText(cfg.pw)


# ==================================================================== 数据模拟
class SimPage(_BasePage):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        head = QHBoxLayout()
        t = QLabel("数据模拟上报")
        t.setProperty("title", True)
        head.addWidget(t)
        head.addStretch(1)
        root.addLayout(head)

        body = QSplitter(Qt.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        gb = QGroupBox("监测因子（勾选参与上报）")
        v = QVBoxLayout(gb)
        self.lst_factors = QListWidget()
        for code, name, unit, lo, hi in commands.POLLUTANTS:
            it = QListWidgetItem(f"{code}  {name}  [{lo}~{hi} {unit}]")
            it.setData(Qt.UserRole, code)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if code in commands.DEFAULT_POLLUTANTS else Qt.Unchecked)
            self.lst_factors.addItem(it)
        v.addWidget(self.lst_factors)
        ll.addWidget(gb, 1)
        body.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        gb2 = QGroupBox("上报策略")
        f2 = QFormLayout(gb2)
        self.cb_cn = QComboBox()
        for cn, desc in commands.DATA_GRANULARITY:
            self.cb_cn.addItem(f"{cn} - {desc}", cn)
        self.sp_interval = QSpinBox()
        self.sp_interval.setRange(1, 3600)
        self.sp_interval.setValue(30)
        self.sp_interval.setSuffix(" 秒")
        self.ed_template = QLineEdit("DataTime={datetime};{items}")
        self.ed_template.setToolTip("可用占位符：{datetime} 数据时间、{items} 因子数据、{mn} 设备标识、{cn} 命令编码")
        self.chk_alarm = QCheckBox("数值超上限时自动上报报警（CN=2051）")
        self.chk_alarm.setChecked(True)
        self.chk_sm4 = QCheckBox("启用 SM4 加密（HJ 212-2025 要求，ECB/128bit/NoPadding）")
        self.ed_key = QLineEdit("0123456789ABCDEFFEDCBA9876543210")
        _mono(self.ed_key, 11)
        self.chk_auto_answer = QCheckBox("收到命令时自动应答")
        self.chk_auto_answer.setChecked(True)
        f2.addRow("数据粒度", self.cb_cn)
        f2.addRow("上报周期", self.sp_interval)
        f2.addRow("数据区模板", self.ed_template)
        f2.addRow(self.chk_alarm)
        f2.addRow(self.chk_sm4)
        f2.addRow("SM4 密钥(32 HEX)", self.ed_key)
        f2.addRow(self.chk_auto_answer)
        rl.addWidget(gb2)

        gb3 = QGroupBox("运行控制")
        h = QHBoxLayout(gb3)
        self.btn_start = QPushButton("启动自动上报")
        self.btn_start.setProperty("accent", True)
        self.btn_start.clicked.connect(self.start)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setProperty("danger", True)
        self.btn_stop.clicked.connect(self.engine.stop_upload)
        self.btn_stop.setEnabled(False)
        self.btn_once = QPushButton("立即上报一条")
        self.btn_once.clicked.connect(self.once)
        for b in (self.btn_start, self.btn_stop, self.btn_once):
            h.addWidget(b)
        h.addStretch(1)
        rl.addWidget(gb3)

        gb4 = QGroupBox("报文预览")
        v4 = QVBoxLayout(gb4)
        self.txt_preview = _mono(QPlainTextEdit())
        self.txt_preview.setReadOnly(True)
        v4.addWidget(self.txt_preview)
        rl.addWidget(gb4, 1)
        body.addWidget(right)

        body.setStretchFactor(0, 4)
        body.setStretchFactor(1, 6)
        root.addWidget(body, 1)

        self.lst_factors.itemChanged.connect(self._sync_cfg)
        self.cb_cn.currentIndexChanged.connect(self._sync_cfg)
        self.sp_interval.valueChanged.connect(self._sync_cfg)
        self.ed_template.textChanged.connect(self._sync_cfg)
        self.chk_alarm.stateChanged.connect(self._sync_cfg)
        self.chk_sm4.stateChanged.connect(self._sync_cfg)
        self.ed_key.textChanged.connect(self._sync_cfg)
        self.chk_auto_answer.stateChanged.connect(self._sync_cfg)
        self._sync_cfg()

    def _sync_cfg(self, *_):
        cfg = self.engine.cfg
        cfg.pollutants = [self.lst_factors.item(i).data(Qt.UserRole)
                          for i in range(self.lst_factors.count())
                          if self.lst_factors.item(i).checkState() == Qt.Checked]
        cfg.upload_cn = self.cb_cn.currentData() or "2011"
        cfg.upload_interval = self.sp_interval.value()
        cfg.template = self.ed_template.text() or "DataTime={datetime};{items}"
        cfg.exceed_alarm = self.chk_alarm.isChecked()
        cfg.sm4_enable = self.chk_sm4.isChecked()
        cfg.sm4_key = self.ed_key.text().strip()
        cfg.auto_answer = self.chk_auto_answer.isChecked()
        self.preview()

    def preview(self):
        try:
            pkt = self.engine.build_data_packet(self.engine.cfg.upload_cn)
            self.txt_preview.setPlainText(pkt.encode())
        except Exception as exc:
            self.txt_preview.setPlainText("预览失败：%s" % exc)

    def start(self):
        if not self.engine.is_open:
            QMessageBox.information(self, "提示", "请先在「连接管理」中打开通道")
            return
        try:
            self.engine.start_upload()
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
        except Exception as exc:
            QMessageBox.warning(self, "启动失败", str(exc))

    def stop_ui(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def once(self):
        if not self.engine.is_open:
            QMessageBox.information(self, "提示", "请先在「连接管理」中打开通道")
            return
        pkt = self.engine.build_data_packet(self.engine.cfg.upload_cn)
        self.engine._apply_encrypt(pkt)
        self.engine.send_packet(pkt)

    def sync_from_config(self, cfg):
        for i in range(self.lst_factors.count()):
            it = self.lst_factors.item(i)
            it.setCheckState(Qt.Checked if it.data(Qt.UserRole) in cfg.pollutants else Qt.Unchecked)
        idx = self.cb_cn.findData(cfg.upload_cn)
        if idx >= 0:
            self.cb_cn.setCurrentIndex(idx)
        self.sp_interval.setValue(cfg.upload_interval)
        self.ed_template.setText(cfg.template)
        self.chk_alarm.setChecked(cfg.exceed_alarm)
        self.chk_sm4.setChecked(cfg.sm4_enable)
        self.ed_key.setText(cfg.sm4_key)
        self.chk_auto_answer.setChecked(cfg.auto_answer)


# ==================================================================== 报文监控
class MonitorPage(_BasePage):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        head = QHBoxLayout()
        t = QLabel("报文监控")
        t.setProperty("title", True)
        head.addWidget(t)
        head.addStretch(1)
        self.chk_autoscroll = QCheckBox("自动滚动")
        self.chk_autoscroll.setChecked(True)
        b_clear = QPushButton("清空")
        b_clear.clicked.connect(self.clear)
        b_export = QPushButton("导出 CSV")
        b_export.clicked.connect(self.export_csv)
        head.addWidget(self.chk_autoscroll)
        head.addWidget(b_clear)
        head.addWidget(b_export)
        root.addLayout(head)

        sp = QSplitter(Qt.Vertical)
        self.tbl = QTableWidget(0, 7)
        self.tbl.setHorizontalHeaderLabels(["时间", "方向", "命令", "系统", "MN", "CRC", "摘要"])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        for i, w in enumerate([90, 50, 90, 60, 190, 60]):
            self.tbl.setColumnWidth(i, w)
        self.tbl.itemSelectionChanged.connect(self._show_detail)
        sp.addWidget(self.tbl)

        bottom = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["字段", "值"])
        self.tree.setColumnWidth(0, 160)
        self.tree.setAlternatingRowColors(True)
        bottom.addWidget(self.tree)
        self.txt_hex = _mono(QPlainTextEdit())
        self.txt_hex.setReadOnly(True)
        self.txt_hex.setPlaceholderText("原始报文 / 十六进制")
        bottom.addWidget(self.txt_hex)
        bottom.setStretchFactor(0, 5)
        bottom.setStretchFactor(1, 5)
        sp.addWidget(bottom)
        sp.setStretchFactor(0, 5)
        sp.setStretchFactor(1, 4)
        root.addWidget(sp, 1)
        self._packets = []

    def add_packet(self, pkt: Packet, direction: str):
        row = self.tbl.rowCount()
        self.tbl.insertRow(row)
        vals = [time.strftime("%H:%M:%S", time.localtime(pkt.timestamp)),
                "收 ←" if direction == "rx" else "发 →",
                f"{pkt.cn} {commands.cn_name(pkt.cn)}", pkt.st, pkt.mn,
                ("OK" if pkt.crc_ok else "ERR"), pkt.cp_text()[:120]]
        for c, v in enumerate(vals):
            it = QTableWidgetItem(v)
            if c == 1:
                it.setForeground(QColor("#1a6fb8" if direction == "rx" else "#1a9c5b"))
            if c == 5 and not pkt.crc_ok:
                it.setForeground(QColor("#d64545"))
            self.tbl.setItem(row, c, it)
        self._packets.append(pkt)
        if self.chk_autoscroll.isChecked():
            self.tbl.scrollToBottom()
        if self.tbl.rowCount() > 3000:
            self.tbl.removeRow(0)
            self._packets.pop(0)

    def _show_detail(self):
        row = self.tbl.currentRow()
        self.tree.clear()
        if row < 0 or row >= len(self._packets):
            return
        pkt = self._packets[row]
        for k, v in pkt.to_rows():
            self.tree.addTopLevelItem(QTreeWidgetItem([k, v]))
        self.tree.resizeColumnToContents(0)
        raw = pkt.raw or pkt.encode()
        hexs = " ".join("%02X" % b for b in raw.encode("utf-8", errors="replace"))
        self.txt_hex.setPlainText("【原文】\n%s\n\n【十六进制】\n%s" % (raw, hexs))

    def clear(self):
        self.tbl.setRowCount(0)
        self._packets.clear()
        self.tree.clear()
        self.txt_hex.clear()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出报文", "hj212_packets.csv", "CSV (*.csv)")
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["时间", "方向", "版本", "QN", "ST", "CN", "PW", "MN", "CRC", "数据区"])
            for p in self._packets:
                w.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.timestamp)),
                            p.direction, p.version, p.qn, p.st, p.cn, p.pw, p.mn,
                            p.crc_value, p.cp_text()])
        QMessageBox.information(self, "完成", "已导出 %d 条报文" % len(self._packets))


# ==================================================================== 日志
class LogPage(_BasePage):
    LEVEL_COLOR = {"info": None, "rx": "#1a6fb8", "tx": "#1a9c5b",
                   "warn": "#c98200", "error": "#d64545"}

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        head = QHBoxLayout()
        t = QLabel("通信日志")
        t.setProperty("title", True)
        head.addWidget(t)
        head.addStretch(1)
        self.cb_level = QComboBox()
        self.cb_level.addItems(["全部", "信息", "接收", "发送", "警告", "错误"])
        self.cb_level.currentTextChanged.connect(self._filter)
        b_clear = QPushButton("清空")
        b_clear.clicked.connect(self.clear)
        b_save = QPushButton("导出")
        b_save.clicked.connect(self.export)
        head.addWidget(QLabel("级别"))
        head.addWidget(self.cb_level)
        head.addWidget(b_clear)
        head.addWidget(b_save)
        root.addLayout(head)

        self.txt = _mono(QPlainTextEdit())
        self.txt.setReadOnly(True)
        self.txt.setLineWrapMode(QPlainTextEdit.NoWrap)
        root.addWidget(self.txt, 1)
        self._lines = []

    def append(self, level, text):
        ts = time.strftime("%H:%M:%S")
        row = "[%s] %s" % (ts, text)
        self._lines.append((level, row))
        color = self.LEVEL_COLOR.get(level)
        if self._match(level):
            if color:
                self.txt.appendHtml('<span style="color:%s">%s</span>' % (color, row))
            else:
                self.txt.appendPlainText(row)
        if len(self._lines) > 5000:
            self._lines = self._lines[-2000:]

    def _match(self, level) -> bool:
        m = {"全部": None, "信息": "info", "接收": "rx", "发送": "tx", "警告": "warn", "错误": "error"}
        need = m.get(self.cb_level.currentText())
        return need is None or need == level

    def _filter(self):
        self.txt.clear()
        for level, row in self._lines:
            if self._match(level):
                color = self.LEVEL_COLOR.get(level)
                if color:
                    self.txt.appendHtml('<span style="color:%s">%s</span>' % (color, row))
                else:
                    self.txt.appendPlainText(row)
        self.txt.verticalScrollBar().setValue(self.txt.verticalScrollBar().maximum())

    def clear(self):
        self.txt.clear()
        self._lines.clear()

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", "hj212_log.txt", "文本 (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            for _, row in self._lines:
                f.write(row + "\n")
        QMessageBox.information(self, "完成", "已导出日志")


# ==================================================================== 编码字典
class CodePage(_BasePage):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        head = QHBoxLayout()
        t = QLabel("编码字典")
        t.setProperty("title", True)
        head.addWidget(t)
        head.addStretch(1)
        self.ed_find = QLineEdit()
        self.ed_find.setPlaceholderText("按编码或名称过滤…")
        self.ed_find.textChanged.connect(self._filter)
        head.addWidget(self.ed_find)
        root.addLayout(head)

        self.tabs = QTabWidget()
        self.tables = {}
        for name, data in [("命令编码 CN", commands.COMMAND_CODES),
                           ("系统编码 ST", commands.SYSTEM_CODES),
                           ("结果编码", commands.RESULT_CODES)]:
            tb = self._mk_table([(k, v) for k, v in data.items()], ["编码", "含义"])
            self.tables[name] = tb
            self.tabs.addTab(tb, name)
        pt = self._mk_table([(c, f"{n}  单位:{u}  默认量程:{lo}~{hi}")
                             for c, n, u, lo, hi in commands.POLLUTANTS],
                            ["因子编码", "名称 / 单位 / 量程"])
        self.tables["监测因子"] = pt
        self.tabs.addTab(pt, "监测因子")
        root.addWidget(self.tabs, 1)
        tip = QLabel("提示：编码表依据 HJ/T 212-2005、HJ 212-2017 正文及附录整理，"
                     "HJ 212-2025 扩充了用电、用能、工况、视频、碳排放等编码；"
                     "如需适配地方平台，可直接修改 src/core/commands.py 后重新打包。")
        tip.setProperty("dim", True)
        tip.setWordWrap(True)
        root.addWidget(tip)

    def _mk_table(self, rows, headers):
        tb = QTableWidget(len(rows), 2)
        tb.setHorizontalHeaderLabels(headers)
        tb.verticalHeader().setVisible(False)
        tb.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tb.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tb.setColumnWidth(0, 120)
        for i, (a, b) in enumerate(rows):
            tb.setItem(i, 0, QTableWidgetItem(a))
            tb.setItem(i, 1, QTableWidgetItem(b))
        return tb

    def _filter(self, text):
        text = text.strip().lower()
        for tb in self.tables.values():
            for r in range(tb.rowCount()):
                a = tb.item(r, 0).text().lower()
                b = tb.item(r, 1).text().lower()
                tb.setRowHidden(r, bool(text) and text not in a and text not in b)


# ==================================================================== 设置
class SettingsPage(_BasePage):
    configChanged = Signal(dict)

    def __init__(self, engine, theme):
        super().__init__()
        self.engine = engine
        self.theme = theme
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        head = QHBoxLayout()
        t = QLabel("系统设置")
        t.setProperty("title", True)
        head.addWidget(t)
        head.addStretch(1)
        root.addLayout(head)

        gb = QGroupBox("外观")
        f = QFormLayout(gb)
        h = QHBoxLayout()
        self.bg_theme = QButtonGroup(self)
        self.rbs = {}
        for key, label in [("auto", "跟随系统"), ("light", "亮色"), ("dark", "暗色")]:
            rb = QRadioButton(label)
            self.rbs[key] = rb
            self.bg_theme.addButton(rb)
            h.addWidget(rb)
        self.bg_theme.buttonClicked.connect(self._theme_changed)
        f.addRow("主题模式", h)
        root.addWidget(gb)

        gb2 = QGroupBox("协议参数")
        f2 = QFormLayout(gb2)
        self.cb_ver = QComboBox()
        self.cb_ver.addItems(["HJ/T 212-2005", "HJ 212-2017", "HJ 212-2025"])
        self.ed_mn = QLineEdit()
        self.ed_pw = QLineEdit()
        self.ed_st = QLineEdit("32")
        self.cb_enc = QComboBox()
        self.cb_enc.addItems(["utf-8", "gbk", "gb2312", "latin1"])
        self.sp_rtd = QSpinBox()
        self.sp_rtd.setRange(1, 3600)
        self.sp_rtd.setValue(30)
        self.sp_rtd.setSuffix(" 秒（应答 CN=1061）")
        f2.addRow("默认协议版本", self.cb_ver)
        f2.addRow("MN 设备唯一标识", self.ed_mn)
        f2.addRow("PW 访问密码", self.ed_pw)
        f2.addRow("ST 系统编码", self.ed_st)
        f2.addRow("字符编码", self.cb_enc)
        f2.addRow("实时数据上报间隔", self.sp_rtd)
        root.addWidget(gb2)

        gb3 = QGroupBox("安全（HJ 212-2025）")
        f3 = QFormLayout(gb3)
        self.chk_sm4 = QCheckBox("启用 SM4 加密（ECB / 128bit / NoPadding）")
        self.ed_key = QLineEdit()
        _mono(self.ed_key, 11)
        f3.addRow(self.chk_sm4)
        f3.addRow("SM4 密钥（32 位 HEX）", self.ed_key)
        root.addWidget(gb3)

        ops = QHBoxLayout()
        b_save = QPushButton("保存配置")
        b_save.setProperty("accent", True)
        b_save.clicked.connect(self._save)
        b_reset = QPushButton("恢复默认")
        b_reset.clicked.connect(self._reset)
        ops.addWidget(b_save)
        ops.addWidget(b_reset)
        ops.addStretch(1)
        root.addLayout(ops)
        root.addStretch(1)

        self.cb_ver.currentIndexChanged.connect(self._save)
        self.ed_mn.textChanged.connect(self._save)
        self.ed_pw.textChanged.connect(self._save)
        self.ed_st.textChanged.connect(self._save)
        self.cb_enc.currentTextChanged.connect(self._save)
        self.sp_rtd.valueChanged.connect(self._save)
        self.chk_sm4.stateChanged.connect(self._save)
        self.ed_key.textChanged.connect(self._save)

    def sync_theme(self):
        self.rbs[self.theme.mode].setChecked(True)

    def _theme_changed(self, rb):
        for key, w in self.rbs.items():
            if w is rb:
                self.theme.apply(key)
        self.sync_theme()

    def _save(self, *_):
        cfg = {"version": ["2005", "2017", "2025"][self.cb_ver.currentIndex()],
               "mn": self.ed_mn.text().strip(), "pw": self.ed_pw.text().strip(),
               "st": self.ed_st.text().strip(), "encoding": self.cb_enc.currentText(),
               "rtd_interval": self.sp_rtd.value(),
               "sm4_enable": self.chk_sm4.isChecked(),
               "sm4_key": self.ed_key.text().strip()}
        self.configChanged.emit(cfg)

    def _reset(self):
        self.engine.cfg.update({"version": "2017", "mn": "010000A8900016F000169DC0",
                                "pw": "123456", "st": "32", "encoding": "utf-8",
                                "rtd_interval": 30, "sm4_enable": False,
                                "sm4_key": "0123456789ABCDEFFEDCBA9876543210"})
        self.sync_from_config(self.engine.cfg)
        self._save()

    def sync_from_config(self, cfg):
        self.cb_ver.setCurrentIndex({"2005": 0, "2017": 1, "2025": 2}.get(cfg.version, 1))
        self.ed_mn.setText(cfg.mn)
        self.ed_pw.setText(cfg.pw)
        self.ed_st.setText(cfg.st)
        self.cb_enc.setCurrentText(cfg.encoding)
        self.sp_rtd.setValue(cfg.rtd_interval)
        self.chk_sm4.setChecked(cfg.sm4_enable)
        self.ed_key.setText(cfg.sm4_key)
        self.sync_theme()
