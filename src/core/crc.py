# -*- coding: utf-8 -*-
"""HJ212 CRC16 校验（标准附录 A）。

算法：CRC-16/IBM（多项式 0xA001，初值 0xFFFF，低位在前），
结果以 4 位大写十六进制表示，随报文一起传输。
"""

POLY = 0xA001
INIT = 0xFFFF

_TABLE = []


def _build_table():
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ POLY
            else:
                crc >>= 1
        _TABLE.append(crc & 0xFFFF)


_build_table()


def crc16(data: bytes) -> int:
    """计算数据的 CRC16 校验值。"""
    crc = INIT
    for b in data:
        crc = ((crc >> 8) ^ _TABLE[(crc ^ b) & 0xFF]) & 0xFFFF
    return crc


def crc16_hex(data: bytes) -> str:
    """返回 4 位大写十六进制校验码。"""
    return "%04X" % crc16(data)
