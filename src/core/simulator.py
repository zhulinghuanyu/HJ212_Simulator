# -*- coding: utf-8 -*-
"""HJ212 会话引擎：收发、自动应答、自动上报、SM4 加解密。"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from . import commands
from .packet import Packet, now_datatime, now_qn, split_frames
from .sm4 import SM4
from .transport import (BaseChannel, SerialChannel, TcpClientChannel,
                        TcpServerChannel)

HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")

#: 需要上位机应答的命令（收到后回 9011/9014）
REQUEST_CN = {"1000", "1011", "1061", "1071", "1021", "1031", "3011", "3013", "3014", "3015", "3020"}
UPLOAD_CN = {"2011", "2021", "2031", "2041", "2051", "2061", "2071", "2081", "2091", "2101", "2111"}


@dataclass
class SimConfig:
    """模拟器运行参数。"""

    version: str = "2017"
    st: str = "32"
    mn: str = "010000A8900016F000169DC0"
    pw: str = "123456"
    encoding: str = "utf-8"
    auto_answer: bool = True
    auto_upload: bool = False
    upload_interval: int = 30          # 秒
    upload_cn: str = "2011"
    pollutants: List[str] = field(default_factory=lambda: list(commands.DEFAULT_POLLUTANTS))
    exceed_alarm: bool = True          # 超标自动报警
    sm4_enable: bool = False
    sm4_key: str = "0123456789ABCDEFFEDCBA9876543210"
    template: str = "DataTime={datetime};{items}"
    rtd_interval: int = 30             # 实时数据间隔（应答 1061）

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    def update(self, data: dict):
        for k, v in data.items():
            if hasattr(self, k):
                setattr(self, k, v)


class SimulatorEngine(QObject):
    """核心引擎：绑定通道并完成协议交互。"""

    packet_rx = Signal(object)      # Packet（收）
    packet_tx = Signal(object)      # Packet（发）
    raw_rx = Signal(bytes)
    raw_tx = Signal(bytes)
    log = Signal(str, str)          # (级别, 文本)
    state = Signal(str, str)        # (状态, 描述)
    stats = Signal(int, int, int)   # (收包数, 发包数, 校验失败数)
    clients = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = SimConfig()
        self.channel: Optional[BaseChannel] = None
        self._buffer = ""
        self._rx_count = self._tx_count = self._crc_bad = 0
        self._values: Dict[str, float] = {}
        self._upload_timer = QTimer(self)
        self._upload_timer.timeout.connect(self._tick_upload)

    # ---------------- 通道管理 ----------------
    def open_tcp_client(self, host: str, port: int):
        ch = TcpClientChannel(host, port, self, self.cfg.encoding)
        self._bind(ch)
        ch.open()

    def open_tcp_server(self, host: str, port: int):
        ch = TcpServerChannel(host, port, self, self.cfg.encoding)
        self._bind(ch)
        ch.open()

    def open_serial(self, port: str, baud: int, bytesize=8, parity="N", stopbits=1):
        ch = SerialChannel(port, baud, bytesize, parity, stopbits, self, self.cfg.encoding)
        self._bind(ch)
        ch.open()

    def _bind(self, ch: BaseChannel):
        self.close()
        self.channel = ch
        ch.received.connect(self._on_data)
        ch.status.connect(self.state)
        ch.error.connect(lambda m: self.log.emit("error", m))
        ch.client_changed.connect(self.clients)
        self._buffer = ""

    def close(self):
        self.stop_upload()
        if self.channel:
            try:
                self.channel.close()
            except Exception:
                pass
            self.channel = None
        self.state.emit("closed", "通道已关闭")

    @property
    def is_open(self) -> bool:
        return bool(self.channel and self.channel.running)

    # ---------------- 接收 ----------------
    def _on_data(self, data: bytes):
        self.raw_rx.emit(data)
        try:
            text = data.decode(self.cfg.encoding, errors="replace")
        except Exception:
            text = data.decode("latin1", errors="replace")
        self._buffer += text
        frames, self._buffer = split_frames(self._buffer)
        for f in frames:
            try:
                pkt = Packet.decode(f)
            except Exception as exc:
                self.log.emit("error", "报文解析失败：%s | %s" % (exc, f[:80]))
                continue
            pkt.direction = "收"
            self._rx_count += 1
            if not pkt.crc_ok:
                self._crc_bad += 1
                self.log.emit("warn", "CRC 校验失败：%s" % f[:60])
            self._try_decrypt(pkt)
            self.packet_rx.emit(pkt)
            self.log.emit("rx", "%s %s" % (pkt.direction, pkt.describe()))
            self._emit_stats()
            if self.cfg.auto_answer:
                self._auto_answer(pkt)

    def _emit_stats(self):
        self.stats.emit(self._rx_count, self._tx_count, self._crc_bad)

    # ---------------- 发送 ----------------
    def send_packet(self, pkt: Packet) -> List[Packet]:
        if not self.is_open:
            raise RuntimeError("通道未连接")
        sent = []
        for frame in pkt.encode_frames():
            data = frame.encode(self.cfg.encoding, errors="replace")
            self.channel.send(data)
            sp = Packet.decode(frame)
            sp.direction = "发"
            sp.raw = frame
            self._tx_count += 1
            self.raw_tx.emit(data)
            self.packet_tx.emit(sp)
            self.log.emit("tx", "%s %s" % (sp.direction, sp.describe()))
            sent.append(sp)
        self._emit_stats()
        return sent

    def send_raw(self, text: str):
        if not self.is_open:
            raise RuntimeError("通道未连接")
        if not text.endswith("\r\n"):
            text += "\r\n"
        data = text.encode(self.cfg.encoding, errors="replace")
        self.channel.send(data)
        self.raw_tx.emit(data)
        self._tx_count += 1
        self.log.emit("tx", "原始报文 %d 字节" % len(data))
        self._emit_stats()

    # ---------------- 自动应答 ----------------
    def _auto_answer(self, pkt: Packet):
        cn = pkt.cn
        qn = now_qn()
        cp = pkt.cp_dict()
        if cn in ("9011", "9012", "9013", "9014", "9015"):
            return  # 不应答应答包

        if cn == "1011":  # 提取现场机时间
            self._reply("1011", [("SystemTime", now_datatime())], qn)
        elif cn == "1061":  # 提取实时数据间隔
            self._reply("1061", [("RtdInterval", "%02d" % self.cfg.rtd_interval)], qn)
        elif cn == "3011":  # 心跳
            self._reply("9011", [("QnRtn", "1")], qn)
        elif cn == "1000":  # 初始化/注册
            self._reply("9011", [("QnRtn", "1")], qn)
        elif cn == "3020" or cn.startswith("302"):  # 反控
            self._reply("9013", [("ExcRtn", "1"), ("ExcDesc", "执行成功")], qn)
        elif cn in UPLOAD_CN:
            self._reply("9014", [("QnRtn", "1")], qn)
        elif pkt.need_answer:
            self._reply("9011", [("QnRtn", "1")], qn)
        else:
            self.log.emit("info", "收到 %s，按要求不应答" % cn)
        if cp and self.cfg.auto_answer:
            pass

    def _reply(self, cn: str, items, qn: str):
        pkt = Packet(qn=qn, st=self.cfg.st, cn=cn, pw=self.cfg.pw, mn=self.cfg.mn,
                     version=self.cfg.version, need_answer=False, cp_items=list(items))
        self._apply_encrypt(pkt)
        self.send_packet(pkt)

    # ---------------- SM4 ----------------
    def _pad(self, text: str) -> bytes:
        raw = text.encode("utf-8")
        rem = len(raw) % 16
        return raw + b"\x00" * (16 - rem if rem else 0)

    def _apply_encrypt(self, pkt: Packet):
        if not self.cfg.sm4_enable or not pkt.cp_items:
            return
        try:
            cipher = SM4(bytes.fromhex(self.cfg.sm4_key)).encrypt_ecb(self._pad(pkt.cp_text()))
            pkt.cp_items = [("EncryptedData", cipher.hex().upper())]
        except Exception as exc:
            self.log.emit("error", "SM4 加密失败：%s" % exc)

    def _try_decrypt(self, pkt: Packet):
        if not self.cfg.sm4_enable:
            return
        for k, v in pkt.cp_items:
            if len(v) >= 32 and len(v) % 32 == 0 and HEX_RE.match(v):
                try:
                    plain = SM4(bytes.fromhex(self.cfg.sm4_key)).decrypt_ecb(bytes.fromhex(v))
                    plain = plain.rstrip(b"\x00").decode("utf-8", errors="replace")
                    pkt.cp_items = [("[SM4解密]", plain)]
                    self.log.emit("info", "SM4 解密成功，明文：%s" % plain[:60])
                except Exception:
                    pass
                break

    # ---------------- 自动上报 ----------------
    def start_upload(self):
        if not self.is_open:
            raise RuntimeError("通道未连接")
        if self.cfg.upload_interval < 1:
            self.cfg.upload_interval = 1
        self._upload_timer.start(self.cfg.upload_interval * 1000)
        self.log.emit("info", "自动上报已启动，周期 %d 秒，命令 %s"
                      % (self.cfg.upload_interval, self.cfg.upload_cn))

    def stop_upload(self):
        if self._upload_timer.isActive():
            self._upload_timer.stop()
            self.log.emit("info", "自动上报已停止")

    @property
    def uploading(self) -> bool:
        return self._upload_timer.isActive()

    def _tick_upload(self):
        if not self.is_open:
            self.stop_upload()
            return
        pkt = self.build_data_packet(self.cfg.upload_cn)
        self._apply_encrypt(pkt)
        try:
            self.send_packet(pkt)
        except Exception as exc:
            self.log.emit("error", "自动上报失败：%s" % exc)
            self.stop_upload()
        if self.cfg.exceed_alarm and self._has_exceed():
            alarm = self.build_alarm_packet()
            self._apply_encrypt(alarm)
            try:
                self.send_packet(alarm)
            except Exception:
                pass

    def _next_value(self, code: str) -> float:
        item = commands.pollutant(code)
        lo, hi = item[3], item[4]
        span = max(hi - lo, 0.001)
        base = self._values.get(code)
        if base is None:
            base = lo + span * random.uniform(0.15, 0.45)
        drift = random.gauss(0, span * 0.03)
        wave = span * 0.05 * (1 + 0.5 * abs(hash(code + str(int(time.time() // 60))) % 7))
        base = min(max(base + drift + span * 0.002, lo), hi * 1.15)
        self._values[code] = base
        return round(base + (wave * 0), 3)

    def _has_exceed(self) -> bool:
        for c in self.cfg.pollutants:
            item = commands.pollutant(c)
            v = self._values.get(c, 0)
            if v > item[4]:
                return True
        return False

    def build_data_items(self, cn: str) -> List[tuple]:
        items = []
        dt = now_datatime()
        for code in self.cfg.pollutants:
            v = self._next_value(code)
            if cn == "2011":
                items.append(("%s-Rtd" % code, "%.3f" % v))
                items.append(("%s-Flag" % code, "N"))
            elif cn in ("2021", "2031", "2041"):
                items.append(("%s-Avg" % code, "%.3f" % v))
                items.append(("%s-Max" % code, "%.3f" % (v * 1.08)))
                items.append(("%s-Min" % code, "%.3f" % (v * 0.92)))
                items.append(("%s-Cou" % code, "%.3f" % (v * 1.5)))
                items.append(("%s-Flag" % code, "N"))
            else:
                items.append(("%s-Rtd" % code, "%.3f" % v))
        return dt, items

    def build_data_packet(self, cn: str = "2011") -> Packet:
        dt, items = self.build_data_items(cn)
        text = self.cfg.template.replace("{datetime}", dt) \
            .replace("{items}", ";".join("%s=%s" % kv for kv in items)) \
            .replace("{mn}", self.cfg.mn).replace("{cn}", cn)
        pkt = Packet(qn=now_qn(), st=self.cfg.st, cn=cn, pw=self.cfg.pw,
                     mn=self.cfg.mn, version=self.cfg.version,
                     need_answer=True)
        pkt.set_cp_text(text)
        return pkt

    def build_alarm_packet(self) -> Packet:
        over = []
        for c in self.cfg.pollutants:
            item = commands.pollutant(c)
            v = self._values.get(c, 0)
            if v > item[4]:
                over.append("%s 超标 %.3f > %.3f" % (item[1], v, item[4]))
        pkt = Packet(qn=now_qn(), st=self.cfg.st, cn="2051", pw=self.cfg.pw,
                     mn=self.cfg.mn, version=self.cfg.version, need_answer=True)
        pkt.set_cp_text("DataTime=%s;AlarmType=1;AlarmDesc=%s;PolId=%s"
                        % (now_datatime(), "；".join(over) or "超标",
                           ",".join(self.cfg.pollutants)))
        return pkt
