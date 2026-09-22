# -*- coding: utf-8 -*-
"""协议与算法自测（python -m unittest discover 或 pytest 均可）。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from core.crc import crc16_hex
from core.packet import Packet, make_flag, parse_flag, split_frames
from core.sm4 import SM4

# HJ212-2017 常见示例报文（数据段 141 字节）
SAMPLE = ("##0141QN=20160801085857223;ST=21;CN=2011;PW=123456;"
          "MN=010000A8900016F000169DC0;Flag=5;CP=&&DataTime=20160801085857;LA-Rtd=50.11&&")


class TestCRC(unittest.TestCase):
    def test_known(self):
        self.assertEqual(crc16_hex(b"123456789"), "4B37")  # CRC-16/MODBUS 标准检查值

    def test_empty(self):
        self.assertEqual(crc16_hex(b""), "FFFF")


class TestSM4(unittest.TestCase):
    def test_vector(self):
        key = bytes.fromhex("0123456789abcdeffedcba9876543210")
        plain = bytes.fromhex("0123456789abcdeffedcba9876543210")
        self.assertEqual(SM4(key).encrypt_ecb(plain).hex(), "681edf34d206965e86b3e94f536e4246")
        self.assertEqual(SM4(key).decrypt_ecb(bytes.fromhex("681edf34d206965e86b3e94f536e4246")), plain)

    def test_roundtrip(self):
        key = bytes.fromhex("00112233445566778899AABBCCDDEEFF")
        text = b"DataTime=20250101120000"
        padded = text + b"\x00" * (16 - len(text) % 16)
        c = SM4(key).encrypt_ecb(padded)
        self.assertEqual(SM4(key).decrypt_ecb(c).rstrip(b"\x00"), text)


class TestFlag(unittest.TestCase):
    def test_make(self):
        self.assertEqual(make_flag("2005", True, False), 1)
        self.assertEqual(make_flag("2017", True, True), 7)
        self.assertEqual(make_flag("2025", False, False), 8)

    def test_parse(self):
        self.assertEqual(parse_flag(7), ("2017", True, True))
        self.assertEqual(parse_flag(5), ("2017", False, True))
        self.assertEqual(parse_flag(1), ("2005", False, True))


class TestPacket(unittest.TestCase):
    def test_encode_structure(self):
        p = Packet(qn="20160801085857223", st="21", cn="2011", pw="123456",
                   mn="010000A8900016F000169DC0", version="2017", need_answer=True)
        p.set_cp_text("DataTime=20160801085857;LA-Rtd=50.11")
        frame = p.encode()
        self.assertTrue(frame.startswith("##"))
        self.assertTrue(frame.endswith("\r\n"))
        data = frame[6:6 + int(frame[2:6])]
        self.assertEqual(frame[2:6], "%04d" % len(data))
        self.assertEqual(frame[6 + len(data):10 + len(data)].upper(), crc16_hex(data.encode()))

    def test_decode_roundtrip(self):
        p = Packet(st="32", cn="2031", mn="010000A8900016F000169DC0", version="2017")
        p.set_cp_text("DataTime=20250101120000;a21026-Avg=1.1;a21026-Max=2.2;a21026-Flag=N")
        d = Packet.decode(p.encode())
        self.assertTrue(d.crc_ok)
        self.assertEqual(d.cn, "2031")
        self.assertEqual(d.st, "32")
        self.assertEqual(d.mn, "010000A8900016F000169DC0")
        self.assertEqual(d.version, "2017")
        self.assertEqual(d.cp_dict().get("a21026-Avg"), "1.1")
        self.assertEqual(d.cp_dict().get("DataTime"), "20250101120000")

    def test_2005_version(self):
        p = Packet(version="2005", pw="123456", mn="12345678901234", cn="2011", st="32")
        p.set_cp_text("DataTime=20250101120000;02-Rtd=1.1,02-Flag=N")
        d = Packet.decode(p.encode())
        self.assertEqual(d.version, "2005")
        self.assertTrue(d.crc_ok)

    def test_2025_version(self):
        p = Packet(version="2025", cn="2011", rf="1")
        p.set_cp_text("DataTime=20250101120000;a21026-Rtd=1.1")
        d = Packet.decode(p.encode())
        self.assertEqual(d.version, "2025")
        self.assertEqual(d.rf, "1")

    def test_split(self):
        p = Packet(version="2017", cn="2041")
        items = ";".join("w%05d-Rtd=%d.1" % (i, i) for i in range(200))
        p.set_cp_text("DataTime=20250101120000;" + items)
        frames = p.encode_frames()
        self.assertGreater(len(frames), 1)
        for f in frames:
            d = Packet.decode(f)
            self.assertTrue(d.crc_ok)
            self.assertTrue(d.split)

    def test_stream_split(self):
        p = Packet(version="2017", cn="2011")
        p.set_cp_text("DataTime=20250101120000;a21026-Rtd=1.1")
        stream = p.encode() + p.encode()[:20]
        frames, rest = split_frames(stream)
        self.assertEqual(len(frames), 1)
        self.assertEqual(rest, p.encode()[:20])

    def test_bad_crc(self):
        p = Packet(version="2017")
        p.set_cp_text("DataTime=20250101120000")
        f = p.encode()
        f = f[:-6] + "0000\r\n"
        self.assertFalse(Packet.decode(f).crc_ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
