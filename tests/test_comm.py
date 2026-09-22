# -*- coding: utf-8 -*-
"""端到端通讯测试：TCP 服务端模式下的收包、自动应答、拆包与 SM4。"""

import os
import socket
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtCore import QCoreApplication, QTimer, QEventLoop

from core.packet import Packet, split_frames
from core.simulator import SimulatorEngine


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class _Harness:
    def __init__(self):
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.engine = SimulatorEngine()

    def wait(self, cond, timeout=6.0):
        end = time.time() + timeout
        while time.time() < end:
            self.app.processEvents()
            if cond():
                return True
            time.sleep(0.02)
        return False


class TestTcpServer(unittest.TestCase):
    def setUp(self):
        self.h = _Harness()
        self.port = _free_port()
        self.h.engine.cfg.version = "2017"
        self.h.engine.cfg.auto_answer = True
        self.h.engine.open_tcp_server("127.0.0.1", self.port)
        self.sent = []
        self.h.engine.packet_tx.connect(lambda p: self.sent.append(p))
        self.rx = []
        self.h.engine.packet_rx.connect(lambda p: self.rx.append(p))
        self.sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        self.sock.settimeout(3)
        self.buf = ""
        self.assertTrue(self.h.wait(lambda: self.h.engine.is_open, 3))

    def tearDown(self):
        try:
            self.sock.close()
        except Exception:
            pass
        self.h.engine.close()

    def _recv_frames(self, timeout=5.0):
        end = time.time() + timeout
        out = []
        while time.time() < end:
            self.h.app.processEvents()
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                continue
            if data:
                self.buf += data.decode("utf-8", errors="replace")
                frames, self.buf = split_frames(self.buf)
                out += frames
                if frames:
                    return out
            time.sleep(0.02)
        return out

    def test_upload_answer(self):
        p = Packet(version="2017", cn="2011", st="32")
        p.set_cp_text("DataTime=20250101120000;a21026-Rtd=1.1")
        self.sock.sendall(p.encode().encode())
        self.assertTrue(self.h.wait(lambda: len(self.rx) == 1, 5))
        self.assertEqual(self.rx[0].cn, "2011")
        self.assertTrue(self.rx[0].crc_ok)
        frames = self._recv_frames()
        self.assertEqual(len(frames), 1)
        ans = Packet.decode(frames[0])
        self.assertEqual(ans.cn, "9014")          # 数据应答
        self.assertTrue(ans.crc_ok)

    def test_extract_time(self):
        p = Packet(version="2017", cn="1011", st="32")
        self.sock.sendall(p.encode().encode())
        frames = self._recv_frames()
        ans = Packet.decode(frames[0])
        self.assertEqual(ans.cn, "1011")
        self.assertEqual(len(ans.cp_dict().get("SystemTime", "")), 14)

    def test_extract_interval(self):
        self.h.engine.cfg.rtd_interval = 45
        p = Packet(version="2017", cn="1061", st="32")
        self.sock.sendall(p.encode().encode())
        frames = self._recv_frames()
        ans = Packet.decode(frames[0])
        self.assertEqual(ans.cp_dict().get("RtdInterval"), "45")

    def test_control_command(self):
        p = Packet(version="2017", cn="3020", st="32")
        self.sock.sendall(p.encode().encode())
        frames = self._recv_frames()
        ans = Packet.decode(frames[0])
        self.assertEqual(ans.cn, "9013")

    def test_hj2025_version(self):
        self.h.engine.cfg.version = "2025"
        p = Packet(version="2025", cn="3011", st="32")
        self.sock.sendall(p.encode().encode())
        self.assertTrue(self.h.wait(lambda: len(self.rx) == 1, 5))
        self.assertEqual(self.rx[0].version, "2025")

    def test_sm4_roundtrip(self):
        self.h.engine.cfg.sm4_enable = True
        p = Packet(version="2017", cn="2011", st="32")
        p.set_cp_text("DataTime=20250101120000;a21026-Rtd=1.1")
        self.h.engine._apply_encrypt(p)   # 模拟现场机侧加密
        self.sock.sendall(p.encode().encode())
        self.assertTrue(self.h.wait(lambda: len(self.rx) == 1, 5))
        got = self.rx[0]
        self.assertEqual(got.cp_items[0][0], "[SM4解密]")
        self.assertIn("a21026-Rtd=1.1", got.cp_items[0][1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
