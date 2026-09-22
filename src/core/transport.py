# -*- coding: utf-8 -*-
"""通讯通道：TCP 客户端 / TCP 服务端 / 串口。

全部通道继承 BaseChannel，统一通过 Qt 信号向 UI 线程抛数据，
底层使用独立线程阻塞读取，避免界面卡顿。
"""

from __future__ import annotations

import socket
import threading
import time

from PySide6.QtCore import QObject, Signal

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except Exception:  # pragma: no cover
    serial = None
    HAS_SERIAL = False


class BaseChannel(QObject):
    """通道基类。"""

    received = Signal(bytes)          # 收到原始数据
    status = Signal(str, str)         # (状态, 描述)
    error = Signal(str)
    client_changed = Signal(list)     # TCP 服务端：客户端列表变化

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._thread: threading.Thread | None = None
        self.encoding = "utf-8"

    # ---- 子类实现 ----
    def _open(self):
        raise NotImplementedError

    def _close(self):
        raise NotImplementedError

    def _write(self, data: bytes):
        raise NotImplementedError

    # ---- 公共接口 ----
    @property
    def running(self) -> bool:
        return self._running

    def open(self):
        if self._running:
            return
        # 先置位，保证 _open() 内部启动的读线程不会立即退出
        self._running = True
        try:
            self._open()
            self.status.emit("opened", "通道已打开")
        except Exception as exc:
            self._running = False
            try:
                self._close()
            except Exception:
                pass
            self.error.emit("打开失败：%s" % exc)
            self.status.emit("error", "打开失败")
            raise

    def close(self):
        self._running = False
        try:
            self._close()
        except Exception:
            pass
        self.status.emit("closed", "通道已关闭")

    def send(self, data: bytes) -> int:
        if not self._running:
            raise RuntimeError("通道未打开")
        n = self._write(data)
        return n

    def _emit(self, data: bytes):
        if data:
            self.received.emit(data)


class TcpClientChannel(BaseChannel):
    """TCP 客户端：连接到监控平台（上位机）。"""

    def __init__(self, host: str, port: int, parent=None, encoding="utf-8"):
        super().__init__(parent)
        self.host, self.port = host, port
        self.encoding = encoding
        self._sock: socket.socket | None = None

    def _open(self):
        self._sock = socket.create_connection((self.host, self.port), timeout=5)
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running and self._sock:
            try:
                data = self._sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    self.error.emit("连接已断开")
                    self.status.emit("closed", "连接断开")
                self._running = False
                break
            if not data:
                if self._running:
                    self.error.emit("服务端关闭连接")
                    self.status.emit("closed", "服务端关闭连接")
                self._running = False
                break
            self._emit(data)

    def _write(self, data: bytes) -> int:
        return self._sock.sendall(data) or len(data)

    def _close(self):
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sock.close()
            self._sock = None


class TcpServerChannel(BaseChannel):
    """TCP 服务端：模拟平台侧，接受多个现场机连接。"""

    def __init__(self, host: str, port: int, parent=None, encoding="utf-8"):
        super().__init__(parent)
        self.host, self.port = host, port
        self.encoding = encoding
        self._srv: socket.socket | None = None
        self.clients: dict[tuple, socket.socket] = {}
        self._lock = threading.Lock()

    def _open(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.host, self.port))
        self._srv.listen(16)
        self._srv.settimeout(0.5)
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self._running and self._srv:
            try:
                conn, addr = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.settimeout(0.5)
            with self._lock:
                self.clients[addr] = conn
            self.client_changed.emit(self.client_list())
            self.status.emit("opened", "客户端接入：%s:%d" % addr)
            threading.Thread(target=self._client_loop, args=(conn, addr), daemon=True).start()

    def _client_loop(self, conn: socket.socket, addr):
        while self._running:
            try:
                data = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            self._emit(data)
        with self._lock:
            self.clients.pop(addr, None)
        try:
            conn.close()
        except OSError:
            pass
        self.client_changed.emit(self.client_list())
        self.status.emit("opened", "客户端断开：%s:%d" % addr)

    def client_list(self):
        with self._lock:
            return ["%s:%d" % a for a in self.clients]

    def _write(self, data: bytes) -> int:
        total = 0
        with self._lock:
            targets = list(self.clients.values())
        for c in targets:
            try:
                c.sendall(data)
                total += len(data)
            except OSError:
                pass
        return total

    def _close(self):
        with self._lock:
            for c in self.clients.values():
                try:
                    c.close()
                except OSError:
                    pass
            self.clients.clear()
        if self._srv:
            self._srv.close()
            self._srv = None
        self.client_changed.emit([])


class SerialChannel(BaseChannel):
    """串口通道（RS232/RS485），用于数采仪/仪表直连调试。"""

    def __init__(self, port: str, baudrate: int = 9600, bytesize=8, parity="N",
                 stopbits=1, parent=None, encoding="utf-8"):
        super().__init__(parent)
        self.port, self.baudrate = port, baudrate
        self.bytesize, self.parity, self.stopbits = bytesize, parity, stopbits
        self.encoding = encoding
        self._ser = None

    def _open(self):
        if not HAS_SERIAL:
            raise RuntimeError("未安装 pyserial，无法使用串口")
        self._ser = serial.Serial(
            port=self.port, baudrate=self.baudrate,
            bytesize=self.bytesize, parity=self.parity,
            stopbits=self.stopbits, timeout=0.5)
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running and self._ser and self._ser.is_open:
            try:
                n = self._ser.in_waiting
                data = self._ser.read(n or 1)
            except Exception as exc:
                if self._running:
                    self.error.emit("串口读取异常：%s" % exc)
                break
            if data:
                self._emit(data)

    def _write(self, data: bytes) -> int:
        return self._ser.write(data)

    def _close(self):
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None


def list_serial_ports():
    """枚举本机可用串口。"""
    if not HAS_SERIAL:
        return []
    try:
        return [p.device for p in serial.tools.list_ports.comports()]
    except Exception:
        return []


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
