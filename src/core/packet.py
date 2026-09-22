# -*- coding: utf-8 -*-
"""HJ212 报文模型与编解码。

支持版本：
  * HJ/T 212-2005（版本位 0）
  * HJ 212-2017（版本位 1）
  * HJ 212-2025（版本位 2）

通讯包结构：## + 数据段长度(4) + 数据段(ASCII) + CRC16(4HEX) + <CR><LF>
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .crc import crc16_hex

HEADER = "##"
TAIL = "\r\n"

#: 版本位（Flag 的 V5~V0）
VERSION_BITS = {"2005": 0, "2017": 1, "2025": 2}

#: 各版本字段约束
VERSION_SPEC = {
    "2005": {"pw_len": 6, "mn_len": 14, "qn_len": 20, "pnum": True, "pno_len": 4, "rf": False},
    "2017": {"pw_len": 9, "mn_len": 24, "qn_len": 20, "pnum": True, "pno_len": 8, "rf": True},
    "2025": {"pw_len": 9, "mn_len": 24, "qn_len": 20, "pnum": True, "pno_len": 5, "rf": True},
}

#: 单包数据区最大长度（字节），超过则拆包
MAX_CP_LEN = 950

_CP_RE = re.compile(r"CP=&&(.*?)&&", re.S)


def now_qn() -> str:
    """生成请求编号 QN=YYYYMMDDHHMMSSZZZ（精确到毫秒）。"""
    t = time.time()
    ms = int((t % 1) * 1000)
    return time.strftime("%Y%m%d%H%M%S", time.localtime(t)) + "%03d" % ms


def now_datatime() -> str:
    return time.strftime("%Y%m%d%H%M%S")


def make_flag(version: str, need_answer: bool = True, split: bool = False) -> int:
    """按 (V5..V0 << 2) | (D << 1) | A 生成标志位。"""
    return (VERSION_BITS.get(version, 1) << 2) | ((1 if split else 0) << 1) | (1 if need_answer else 0)


def parse_flag(flag: int) -> Tuple[str, bool, bool]:
    """解析标志位，返回 (版本号, 是否分包, 是否需要应答)。"""
    ver = {0: "2005", 1: "2017", 2: "2025"}.get(flag >> 2, "未知(%d)" % (flag >> 2))
    return ver, bool((flag >> 1) & 1), bool(flag & 1)


@dataclass
class Packet:
    """一条 HJ212 通讯包。"""

    qn: str = ""
    st: str = "32"
    cn: str = "2011"
    pw: str = "123456"
    mn: str = "010000A8900016F000169DC0"
    version: str = "2017"
    need_answer: bool = True
    split: bool = False
    pnum: int = 1
    pno: int = 1
    rf: Optional[str] = None
    cp_items: List[Tuple[str, str]] = field(default_factory=list)
    raw: str = ""
    crc_ok: bool = True
    crc_value: str = ""
    direction: str = ""
    timestamp: float = field(default_factory=time.time)

    # ---------- 数据区 ----------
    def set_cp_text(self, text: str) -> None:
        """以 `k=v;k=v` 文本设置数据区（支持 `&&` 包裹）。"""
        text = text.strip()
        if text.startswith("&&"):
            text = text[2:]
        if text.endswith("&&"):
            text = text[:-2]
        items = []
        for seg in text.split(";"):
            seg = seg.strip()
            if not seg:
                continue
            if "=" in seg:
                k, v = seg.split("=", 1)
                items.append((k.strip(), v.strip()))
            else:
                items.append((seg, ""))
        self.cp_items = items

    def cp_text(self) -> str:
        return ";".join(f"{k}={v}" if v != "" else k for k, v in self.cp_items)

    def cp_wrapped(self) -> str:
        return "&&%s&&" % self.cp_text()

    def cp_dict(self) -> Dict[str, str]:
        return {k: v for k, v in self.cp_items}

    # ---------- 编码 ----------
    def data_segment(self) -> str:
        spec = VERSION_SPEC.get(self.version, VERSION_SPEC["2017"])
        parts = [
            "QN=" + (self.qn or now_qn()),
            "ST=" + self.st,
            "CN=" + self.cn,
            "PW=" + str(self.pw)[: spec["pw_len"]],
            "MN=" + self.mn,
            "Flag=" + str(make_flag(self.version, self.need_answer, self.split)),
        ]
        if self.split and spec["pnum"]:
            parts.append("PNUM=%0*d" % (spec["pno_len"], self.pnum))
            parts.append("PNO=%0*d" % (spec["pno_len"], self.pno))
        if self.rf:
            parts.append("RF=" + self.rf)
        parts.append("CP=" + self.cp_wrapped())
        return ";".join(parts)

    def encode(self) -> str:
        data = self.data_segment()
        return HEADER + "%04d" % len(data) + data + crc16_hex(data.encode("utf-8")) + TAIL

    def encode_frames(self) -> List[str]:
        """数据区超长时自动拆包，返回若干报文。"""
        full = self.cp_text()
        if len(full.encode("utf-8")) <= MAX_CP_LEN:
            self.split = self.split and self.pnum > 1
            return [self.encode()]
        chunks = []
        buf = ""
        for seg in full.split(";"):
            add = (seg + ";")
            if len((buf + add).encode("utf-8")) > MAX_CP_LEN and buf:
                chunks.append(buf.rstrip(";"))
                buf = ""
            buf += add
        if buf:
            chunks.append(buf.rstrip(";"))
        frames, orig = [], self.cp_items
        self.split = True
        self.pnum = len(chunks)
        for i, c in enumerate(chunks, 1):
            self.pno = i
            self.cp_items = _split_items(c)
            frames.append(self.encode())
        self.cp_items = orig
        return frames

    # ---------- 解码 ----------
    @staticmethod
    def decode(frame: str) -> "Packet":
        p = Packet()
        p.raw = frame
        body = frame
        if body.startswith(HEADER):
            body = body[2:]
        if body.endswith(TAIL):
            body = body[:-2]
        if len(body) < 8:
            raise ValueError("报文长度不足")
        length = int(body[:4])
        data, crc = body[4:4 + length], body[4 + length:8 + length]
        p.crc_value = crc.upper()
        p.crc_ok = crc16_hex(data.encode("utf-8")) == crc.upper()
        p._parse_data(data)
        return p

    def _parse_data(self, data: str) -> None:
        m = _CP_RE.search(data)
        cp_text = ""
        head = data
        if m:
            cp_text = m.group(1)
            head = data[:m.start()] + data[m.end():]
        for seg in head.split(";"):
            seg = seg.strip().rstrip(";").strip()
            if not seg or "=" not in seg:
                continue
            k, v = seg.split("=", 1)
            k, v = k.strip().upper(), v.strip()
            if k == "QN":
                self.qn = v
            elif k == "ST":
                self.st = v
            elif k == "CN":
                self.cn = v
            elif k == "PW":
                self.pw = v
            elif k == "MN":
                self.mn = v
            elif k == "FLAG":
                try:
                    ver, sp, ans = parse_flag(int(v))
                    self.version = ver if not ver.startswith("未知") else self.version
                    self.split, self.need_answer = sp, ans
                except ValueError:
                    pass
            elif k == "PNUM":
                self.pnum = int(v) if v.isdigit() else 1
            elif k == "PNO":
                self.pno = int(v) if v.isdigit() else 1
            elif k == "RF":
                self.rf = v
        if cp_text:
            self.set_cp_text(cp_text)

    # ---------- 展示 ----------
    def describe(self) -> str:
        from .commands import cn_name
        return f"CN={self.cn} ({cn_name(self.cn)}) ST={self.st} MN={self.mn} QN={self.qn}"

    def to_rows(self) -> List[Tuple[str, str]]:
        rows = [("报文方向", self.direction or "-"),
                ("协议版本", "HJ212-" + self.version),
                ("QN 请求编号", self.qn),
                ("ST 系统编码", self.st),
                ("CN 命令编码", self.cn),
                ("PW 访问密码", self.pw),
                ("MN 设备标识", self.mn),
                ("Flag 标志位", str(make_flag(self.version, self.need_answer, self.split))),
                ("拆分包", "是 (%d/%d)" % (self.pno, self.pnum) if self.split else "否")]
        if self.rf:
            rows.append(("RF 补传标志", self.rf))
        rows.append(("CRC 校验", "%s %s" % (self.crc_value, "通过" if self.crc_ok else "失败")))
        rows.append(("数据段长度", str(len(self.raw))))
        for k, v in self.cp_items:
            rows.append(("CP." + k, v))
        return rows


def _split_items(text: str) -> List[Tuple[str, str]]:
    items = []
    for seg in text.split(";"):
        if "=" in seg:
            k, v = seg.split("=", 1)
            items.append((k, v))
    return items


def split_frames(stream: str) -> Tuple[List[str], str]:
    """从字节流中切出完整报文，返回 (完整报文列表, 残留缓冲)。"""
    frames, buf = [], stream
    while True:
        start = buf.find(HEADER)
        if start < 0:
            buf = ""
            break
        buf = buf[start:]
        if len(buf) < 10:
            break
        try:
            length = int(buf[2:6])
        except ValueError:
            buf = buf[2:]
            continue
        end = 6 + length + 4
        if len(buf) < end:
            break
        frames.append(buf[:end])
        buf = buf[end:]
        if buf.startswith(TAIL):
            buf = buf[2:]
    return frames, buf
