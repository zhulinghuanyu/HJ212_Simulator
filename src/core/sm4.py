# -*- coding: utf-8 -*-
"""国密 SM4 分组密码算法（GB/T 32907-2016）纯 Python 实现。

HJ212-2025 要求互联网传输的报文采用 SM4 算法加密：
16 字节（128 位）密钥、ECB 工作模式、NoPadding 填充。
本模块零第三方依赖，便于打包发布。
"""

SBOX = [
    0xD6, 0x90, 0xE9, 0xFE, 0xCC, 0xE1, 0x3D, 0xB7, 0x16, 0xB6, 0x14, 0xC2, 0x28, 0xFB, 0x2C, 0x05,
    0x2B, 0x67, 0x9A, 0x76, 0x2A, 0xBE, 0x04, 0xC3, 0xAA, 0x44, 0x13, 0x26, 0x49, 0x86, 0x06, 0x99,
    0x9C, 0x42, 0x50, 0xF4, 0x91, 0xEF, 0x98, 0x7A, 0x33, 0x54, 0x0B, 0x43, 0xED, 0xCF, 0xAC, 0x62,
    0xE4, 0xB3, 0x1C, 0xA9, 0xC9, 0x08, 0xE8, 0x95, 0x80, 0xDF, 0x94, 0xFA, 0x75, 0x8F, 0x3F, 0xA6,
    0x47, 0x07, 0xA7, 0xFC, 0xF3, 0x73, 0x17, 0xBA, 0x83, 0x59, 0x3C, 0x19, 0xE6, 0x85, 0x4F, 0xA8,
    0x68, 0x6B, 0x81, 0xB2, 0x71, 0x64, 0xDA, 0x8B, 0xF8, 0xEB, 0x0F, 0x4B, 0x70, 0x56, 0x9D, 0x35,
    0x1E, 0x24, 0x0E, 0x5E, 0x63, 0x58, 0xD1, 0xA2, 0x25, 0x22, 0x7C, 0x3B, 0x01, 0x21, 0x78, 0x87,
    0xD4, 0x00, 0x46, 0x57, 0x9F, 0xD3, 0x27, 0x52, 0x4C, 0x36, 0x02, 0xE7, 0xA0, 0xC4, 0xC8, 0x9E,
    0xEA, 0xBF, 0x8A, 0xD2, 0x40, 0xC7, 0x38, 0xB5, 0xA3, 0xF7, 0xF2, 0xCE, 0xF9, 0x61, 0x15, 0xA1,
    0xE0, 0xAE, 0x5D, 0xA4, 0x9B, 0x34, 0x1A, 0x55, 0xAD, 0x93, 0x32, 0x30, 0xF5, 0x8C, 0xB1, 0xE3,
    0x1D, 0xF6, 0xE2, 0x2E, 0x82, 0x66, 0xCA, 0x60, 0xC0, 0x29, 0x23, 0xAB, 0x0D, 0x53, 0x4E, 0x6F,
    0xD5, 0xDB, 0x37, 0x45, 0xDE, 0xFD, 0x8E, 0x2F, 0x03, 0xFF, 0x6A, 0x72, 0x6D, 0x6C, 0x5B, 0x51,
    0x8D, 0x1B, 0xAF, 0x92, 0xBB, 0xDD, 0xBC, 0x7F, 0x11, 0xD9, 0x5C, 0x41, 0x1F, 0x10, 0x5A, 0xD8,
    0x0A, 0xC1, 0x31, 0x88, 0xA5, 0xCD, 0x7B, 0xBD, 0x2D, 0x74, 0xD0, 0x12, 0xB8, 0xE5, 0xB4, 0xB0,
    0x89, 0x69, 0x97, 0x4A, 0x0C, 0x96, 0x77, 0x7E, 0x65, 0xB9, 0xF1, 0x09, 0xC5, 0x6E, 0xC6, 0x84,
    0x18, 0xF0, 0x7D, 0xEC, 0x3A, 0xDC, 0x4D, 0x20, 0x79, 0xEE, 0x5F, 0x3E, 0xD7, 0xCB, 0x39, 0x48,
]

CK = [
    0x00070E15, 0x1C232A31, 0x383F464D, 0x545B6269,
    0x70777E85, 0x8C939AA1, 0xA8AFB6BD, 0xC4CBD2D9,
    0xE0E7EEF5, 0xFC030A11, 0x181F262D, 0x343B4249,
    0x50575E65, 0x6C737A81, 0x888F969D, 0xA4ABB2B9,
    0xC0C7CED5, 0xDCE3EAF1, 0xF8FF060D, 0x141B2229,
    0x30373E45, 0x4C535A61, 0x686F767D, 0x848B9299,
    0xA0A7AEB5, 0xBCC3CAD1, 0xD8DFE6ED, 0xF4FB0209,
    0x10171E25, 0x2C333A41, 0x484F565D, 0x646B7279,
]

FK = [0xA3B1BAC6, 0x56AA3350, 0x677D9197, 0xB27022DC]

_MASK = 0xFFFFFFFF


def _rotl(x: int, n: int) -> int:
    return ((x << n) | (x >> (32 - n))) & _MASK


def _tau(a: int) -> int:
    return ((SBOX[(a >> 24) & 0xFF] << 24) | (SBOX[(a >> 16) & 0xFF] << 16) |
            (SBOX[(a >> 8) & 0xFF] << 8) | SBOX[a & 0xFF])


def _l(b: int) -> int:
    return b ^ _rotl(b, 2) ^ _rotl(b, 10) ^ _rotl(b, 18) ^ _rotl(b, 24)


def _lp(b: int) -> int:
    return b ^ _rotl(b, 13) ^ _rotl(b, 23)


def _t(x: int) -> int:
    return _l(_tau(x))


def _tp(x: int) -> int:
    return _lp(_tau(x))


class SM4:
    """SM4 分组密码，支持 ECB / CBC 模式。"""

    BLOCK = 16

    def __init__(self, key: bytes):
        if len(key) != 16:
            raise ValueError("SM4 密钥长度必须为 16 字节（128 位）")
        mk = [int.from_bytes(key[i * 4:i * 4 + 4], "big") for i in range(4)]
        k = [mk[i] ^ FK[i] for i in range(4)]
        self._rk = []
        for i in range(32):
            v = k[i + 1] ^ k[i + 2] ^ k[i + 3] ^ CK[i]
            k.append(k[i] ^ _tp(v))
            self._rk.append(k[i + 4])

    def _crypt_block(self, block: bytes, decrypt: bool) -> bytes:
        x = [int.from_bytes(block[i * 4:i * 4 + 4], "big") for i in range(4)]
        rk = self._rk[::-1] if decrypt else self._rk
        for i in range(32):
            v = x[1] ^ x[2] ^ x[3] ^ rk[i]
            x = x[1:] + [x[0] ^ _t(v)]
        return b"".join(v.to_bytes(4, "big") for v in (x[3], x[2], x[1], x[0]))

    def encrypt_ecb(self, data: bytes) -> bytes:
        return self._ecb(data, False)

    def decrypt_ecb(self, data: bytes) -> bytes:
        return self._ecb(data, True)

    def _ecb(self, data: bytes, decrypt: bool) -> bytes:
        if len(data) % self.BLOCK:
            raise ValueError("SM4 NoPadding 模式要求数据长度为 16 字节整数倍")
        return b"".join(self._crypt_block(data[i:i + self.BLOCK], decrypt)
                        for i in range(0, len(data), self.BLOCK))

    def encrypt_cbc(self, data: bytes, iv: bytes) -> bytes:
        return self._cbc(data, iv, False)

    def decrypt_cbc(self, data: bytes, iv: bytes) -> bytes:
        return self._cbc(data, iv, True)

    def _cbc(self, data: bytes, iv: bytes, decrypt: bool) -> bytes:
        if len(iv) != 16:
            raise ValueError("IV 长度必须为 16 字节")
        out = bytearray()
        prev = iv
        for i in range(0, len(data), self.BLOCK):
            chunk = data[i:i + self.BLOCK]
            if decrypt:
                tmp = self._crypt_block(chunk, True)
                out += bytes(a ^ b for a, b in zip(tmp, prev))
                prev = chunk
            else:
                xored = bytes(a ^ b for a, b in zip(chunk, prev))
                blk = self._crypt_block(xored, False)
                out += blk
                prev = blk
        return bytes(out)


def sm4_ecb_encrypt_hex(key_hex: str, text: str, encoding: str = "utf-8") -> str:
    """对文本做 SM4-ECB 加密，返回大写十六进制串。"""
    return SM4(bytes.fromhex(key_hex)).encrypt_ecb(text.encode(encoding)).hex().upper()


def sm4_ecb_decrypt_hex(key_hex: str, cipher_hex: str, encoding: str = "utf-8") -> str:
    """解密 SM4-ECB 十六进制密文，返回原文字符串。"""
    return SM4(bytes.fromhex(key_hex)).decrypt_ecb(bytes.fromhex(cipher_hex)).decode(encoding)


if __name__ == "__main__":
    # GB/T 32907-2016 附录 A 标准测试向量
    key = bytes.fromhex("0123456789abcdeffedcba9876543210")
    plain = bytes.fromhex("0123456789abcdeffedcba9876543210")
    expect = "681edf34d206965e86b3e94f536e4246"
    got = SM4(key).encrypt_ecb(plain).hex()
    print("encrypt:", got, "PASS" if got == expect else "FAIL")
    print("decrypt:", SM4(key).decrypt_ecb(bytes.fromhex(expect)).hex(),
          "PASS" if SM4(key).decrypt_ecb(bytes.fromhex(expect)) == plain else "FAIL")
