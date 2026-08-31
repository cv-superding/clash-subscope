# -*- coding: utf-8 -*-
"""运行时接口（Clash External Controller）。

只连接本机回环地址 127.0.0.1 或本机命名管道，不会访问任何外部网络，
也不会对订阅链接发起请求。
"""

import ctypes
import json
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from typing import Dict, List, Optional, Tuple

from .models import Issue, LV_INFO, RuntimeInfo

DEFAULT_TCP_PORTS = [9090, 9091, 9092, 9093, 9097, 33211, 7892]
DEFAULT_PIPES = [r"\\.\pipe\verge-mihomo", r"\\.\pipe\mihomo", r"\\.\pipe\clash"]
CONNECT_TIMEOUT = 0.35
READ_TIMEOUT = 5.0

RE_EXT_CTL = re.compile(r"(?m)^\s*external-controller\s*:\s*['\"]?([^'\"\r\n#]*)")
RE_PIPE = re.compile(r"(?m)^\s*external-controller-pipe\s*:\s*['\"]?([^'\"\r\n#]*)")
RE_SECRET = re.compile(r"(?m)^\s*(?:secret|verge_secret|verge-secret)\s*:\s*['\"]?([^'\"\r\n#]*)")


# --------------------------------------------------------------------------
# 候选端点收集
# --------------------------------------------------------------------------
def collect_candidates(config_paths: List[str]) -> Tuple[List[str], List[str], List[str]]:
    """从配置文件中收集：TCP 端点、命名管道、密钥。"""
    from .parsers import read_text  # 延迟导入，避免循环依赖

    tcp: List[str] = []
    pipes: List[str] = []
    secrets: List[str] = []

    def add(seq, val):
        val = (val or "").strip().strip("'\"").strip()
        if val and val not in seq:
            seq.append(val)

    for path in config_paths:
        text, err = read_text(path)
        if err:
            continue
        for m in RE_EXT_CTL.finditer(text):
            val = m.group(1).strip()
            if not val:
                continue
            host, _, port = val.rpartition(":")
            if not port.isdigit():
                continue
            host = host.strip() or "127.0.0.1"
            if host in ("0.0.0.0", "[::]", "*", "localhost"):
                host = "127.0.0.1"
            add(tcp, "%s:%s" % (host, port))
        for m in RE_PIPE.finditer(text):
            add(pipes, m.group(1))
        for m in RE_SECRET.finditer(text):
            # 注意：set-your-secret 是多数客户端出厂默认值，本身就是有效密钥，不能过滤
            val = m.group(1).strip()
            if val and val not in ("''", '""', "null", "none"):
                add(secrets, val)

    for port in DEFAULT_TCP_PORTS:
        add(tcp, "127.0.0.1:%d" % port)
    for p in DEFAULT_PIPES:
        add(pipes, p)
    return tcp, pipes, secrets


# --------------------------------------------------------------------------
# HTTP 响应解析
# --------------------------------------------------------------------------
def _split_response(raw: bytes) -> Tuple[str, bytes]:
    head, _, body = raw.partition(b"\r\n\r\n")
    return head.decode("utf-8", "replace"), body


def _decode_body(head: str, body: bytes) -> bytes:
    if re.search(r"(?i)transfer-encoding:\s*chunked", head):
        out = b""
        pos = 0
        while True:
            idx = body.find(b"\r\n", pos)
            if idx < 0:
                break
            line = body[pos:idx]
            try:
                size = int(line.split(b";")[0].strip() or b"0", 16)
            except ValueError:
                break
            pos = idx + 2
            if size == 0:
                break
            out += body[pos:pos + size]
            pos += size + 2
        return out
    m = re.search(r"(?i)content-length:\s*(\d+)", head)
    if m:
        return body[: int(m.group(1))]
    return body


def _parse(raw: bytes) -> Tuple[int, dict]:
    """返回 (HTTP 状态码, 解析后的 JSON 字典)。"""
    head, body = _split_response(raw)
    status = 0
    if head:
        m = re.match(r"HTTP/[\d.]+ (\d+)", head)
        if m:
            status = int(m.group(1))
    try:
        return status, json.loads(_decode_body(head, body).decode("utf-8", "replace"))
    except Exception:
        return status, {}


def _request_bytes(path: str, secret: Optional[str]) -> bytes:
    lines = [
        "GET %s HTTP/1.1" % path,
        "Host: 127.0.0.1",
        "User-Agent: clash-sub-extractor/1.0",
        "Accept: application/json",
        "Connection: close",
    ]
    if secret:
        lines.append("Authorization: Bearer %s" % secret)
    return ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")


# --------------------------------------------------------------------------
# TCP 通道
# --------------------------------------------------------------------------
def _tcp_get(endpoint: str, path: str, secret: Optional[str]) -> Tuple[int, dict]:
    host, _, port_s = endpoint.rpartition(":")
    with socket.create_connection((host or "127.0.0.1", int(port_s)), timeout=READ_TIMEOUT) as sock:
        sock.settimeout(READ_TIMEOUT)
        sock.sendall(_request_bytes(path, secret))
        chunks = []
        while True:
            try:
                data = sock.recv(65536)
            except socket.timeout:
                break
            if not data:
                break
            chunks.append(data)
            if b"\r\n\r\n" in b"".join(chunks) and len(b"".join(chunks)) > 4096:
                # 简单判断：非 chunked 且已收满 Content-Length 时提前退出
                head, body = _split_response(b"".join(chunks))
                if not re.search(r"(?i)transfer-encoding:\s*chunked", head):
                    m = re.search(r"(?i)content-length:\s*(\d+)", head)
                    if m and len(body) >= int(m.group(1)):
                        break
    return _parse(b"".join(chunks))


def _port_open(endpoint: str) -> bool:
    host, _, port_s = endpoint.rpartition(":")
    if not port_s.isdigit():
        return False
    try:
        with socket.create_connection((host or "127.0.0.1", int(port_s)), timeout=CONNECT_TIMEOUT):
            return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# 命名管道通道（Windows）
# --------------------------------------------------------------------------
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_KERNEL32 = ctypes.windll.kernel32
_CreateFileW = _KERNEL32.CreateFileW
_CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                         wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
_CreateFileW.restype = wintypes.HANDLE
_ReadFile = _KERNEL32.ReadFile
_ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                      ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
_WriteFile = _KERNEL32.WriteFile
_WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                       ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
_PeekNamedPipe = _KERNEL32.PeekNamedPipe


def _pipe_get(pipe: str, path: str, secret: Optional[str], timeout: float = READ_TIMEOUT) -> Tuple[int, dict]:
    handle = _CreateFileW(pipe, 0xC0000000, 0, None, 3, 0, None)
    if handle == _INVALID_HANDLE:
        raise OSError("CreateFileW 失败，错误码 %d" % _KERNEL32.GetLastError())
    try:
        payload = _request_bytes(path, secret)
        written = wintypes.DWORD(0)
        if not _WriteFile(handle, payload, len(payload), ctypes.byref(written), None):
            raise OSError("WriteFile 失败，错误码 %d" % _KERNEL32.GetLastError())

        buf = ctypes.create_string_buffer(262144)
        total = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            avail = wintypes.DWORD(0)
            _PeekNamedPipe(handle, None, 0, None, ctypes.byref(avail), None)
            if avail.value == 0:
                if total:
                    break
                time.sleep(0.02)
                continue
            n = wintypes.DWORD(0)
            if not _ReadFile(handle, buf, 262144, ctypes.byref(n), None) or n.value == 0:
                break
            total += buf.raw[: n.value]
            if len(total) > 8 * 1024 * 1024:
                break
        if not total:
            raise OSError("管道无响应（可能不是 Clash 控制器）")
        return _parse(total)
    finally:
        _KERNEL32.CloseHandle(handle)


def pipe_exists(pipe: str) -> bool:
    """判断命名管道是否存在（不发送任何数据）。

    os.listdir("\\\\.\\pipe\\") 返回的是裸名（如 verge-mihomo），
    因此这里只比较最后一段。
    """
    if not pipe:
        return False
    name = pipe.replace("/", "\\").rstrip("\\").split("\\")[-1].lower()
    if not name:
        return False
    try:
        return name in {p.lower() for p in _list_pipes()}
    except Exception:
        return False


def _list_pipes() -> List[str]:
    import os
    try:
        return os.listdir("\\\\.\\pipe\\")
    except Exception:
        return []


# --------------------------------------------------------------------------
# 对外主入口
# --------------------------------------------------------------------------
def probe_runtime(config_paths: List[str]) -> RuntimeInfo:
    """依次尝试 TCP 与命名管道，返回连接结果。"""
    tcp, pipes, secrets = collect_candidates(config_paths)
    info = RuntimeInfo()
    tried: List[str] = []

    # --- TCP：先并行做端口连通性检查，只对开放的端口发起 HTTP ---
    open_tcp: List[str] = []
    if tcp:
        try:
            with ThreadPoolExecutor(max_workers=min(16, len(tcp))) as pool:
                for endpoint, ok in zip(tcp, pool.map(_port_open, tcp)):
                    if ok:
                        open_tcp.append(endpoint)
        except Exception:
            open_tcp = []

    secret_pool: List[Optional[str]] = [None] + secrets
    for endpoint in open_tcp:
        for secret in secret_pool:
            tried.append("TCP %s%s" % (endpoint, " (带密钥)" if secret else ""))
            try:
                status, data = _tcp_get(endpoint, "/version", secret)
            except Exception as e:
                info.error = "TCP %s 请求失败：%s" % (endpoint, e)
                continue
            if status == 200 and data:
                info.connected = True
                info.channel_type = "tcp"
                info.channel = "TCP %s" % endpoint
                info.endpoint = endpoint
                info.secret_used = bool(secret)
                _fill_details(info, endpoint, "tcp", secret)
                info.tried = tried
                return info
            if status in (401, 403):
                info.error = "TCP %s 返回 %d：密钥不正确" % (endpoint, status)
                break

    # --- 命名管道 ---
    for pipe in pipes:
        if not pipe_exists(pipe):
            continue
        for secret in secret_pool:
            tried.append("管道 %s%s" % (pipe, " (带密钥)" if secret else ""))
            try:
                status, data = _pipe_get(pipe, "/version", secret)
            except Exception as e:
                info.error = "管道 %s 请求失败：%s" % (pipe, e)
                continue
            if status == 200 and data:
                info.connected = True
                info.channel_type = "pipe"
                info.channel = "命名管道 %s" % pipe
                info.endpoint = pipe
                info.secret_used = bool(secret)
                _fill_details(info, pipe, "pipe", secret)
                info.tried = tried
                return info
            if status in (401, 403):
                info.error = "管道 %s 返回 %d：密钥不正确" % (pipe, status)
                break

    info.tried = tried
    if not info.error:
        info.error = "未找到可用的控制器端点（已尝试 %d 个候选）" % len(tried)
    return info


def _get(endpoint: str, channel_type: str, secret: Optional[str], path: str) -> Tuple[int, dict]:
    if channel_type == "tcp":
        return _tcp_get(endpoint, path, secret)
    return _pipe_get(endpoint, path, secret)


def _fill_details(info: RuntimeInfo, endpoint: str, channel_type: str, secret: Optional[str]) -> None:
    """补齐核心版本、节点数、provider 订阅信息。"""
    try:
        status, data = _get(endpoint, channel_type, secret, "/version")
        if status == 200 and isinstance(data, dict):
            info.version = str(data.get("version") or "")
            info.core_name = "mihomo (Clash.Meta)" if data.get("meta") else "Clash"
            if info.version:
                info.core_name = "%s %s" % (info.core_name, info.version)
    except Exception:
        pass

    try:
        status, data = _get(endpoint, channel_type, secret, "/providers/proxies")
        if status == 200 and isinstance(data, dict):
            providers = data.get("providers") or {}
            if isinstance(providers, dict):
                info.provider_count = len(providers)
                total_nodes = 0
                subs: Dict[str, dict] = {}
                for name, pv in providers.items():
                    if not isinstance(pv, dict):
                        continue
                    nodes = pv.get("proxies") or []
                    if isinstance(nodes, list):
                        total_nodes += len(nodes)
                    si = pv.get("subscriptionInfo")
                    if isinstance(si, dict) and si:
                        subs[name] = si
                info.node_count = total_nodes
                if len(subs) == 1:
                    info.subscription_info = list(subs.values())[0]
                elif len(subs) > 1:
                    # 多个 provider 都带订阅信息时无法一一对应，只保留汇总提示
                    info.subscription_info = None
    except Exception:
        pass


def build_runtime_issue(info: RuntimeInfo) -> Issue:
    """把连接失败翻译成中文排查建议。"""
    if info.connected:
        return Issue(LV_INFO, "已连接运行时接口", "通道：%s" % info.channel, "")
    return Issue(
        LV_WARN,
        "未能连接运行时接口，已仅使用本地配置文件",
        info.error or "未知原因",
        "客户端未启动时属于正常现象。若客户端正在运行，可在其设置中开启「外部控制器 / "
        "External Controller」，或在配置里设置 external-controller: 127.0.0.1:9090 后重启客户端。",
    )
