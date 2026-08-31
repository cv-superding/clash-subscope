# -*- coding: utf-8 -*-
"""Windows 系统代理（IE / Internet Settings）的临时关闭与恢复。

用途：把订阅导入 Clash 时，很多「梯子」会把系统代理指回自身或某个出口，
导致 Clash 拉取订阅请求被代理干扰（HTTP/2 中断 / 机房 IP 被订阅服务 403）。
临时关闭系统代理可让 Clash 直连拉取，导入成功后再恢复。

仅读写本机注册表 + 通过 wininet 广播设置变更，不联网、不上传。
所有操作都包在 try/except 中，绝不让异常冒泡到 GUI。
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger("clash_sub_tool.proxymgr")

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

# wininet 选项常量
_OPT_SETTINGS_CHANGED = 39   # INTERNET_OPTION_SETTINGS_CHANGED
_OPT_REFRESH = 37            # INTERNET_OPTION_REFRESH


def get_proxy_state() -> Dict[str, object]:
    """读取当前系统代理状态，返回可原样还原的字典。

    字段：enabled(int 0/1), ProxyServer(str), ProxyOverride(str)
    读取失败或不存在时给安全默认值（enabled=0 表示未开启）。
    """
    state: Dict[str, object] = {"enabled": 0, "ProxyServer": "", "ProxyOverride": ""}
    try:
        import winreg  # type: ignore

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH, 0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        try:
            val, _ = winreg.QueryValueEx(key, "ProxyEnable")
            # 兼容 REG_DWORD(int) 与 REG_SZ(str "1"/"0") 两种存储方式，
            # 避免把字符串型开启误判为"未开启"导致恢复时把代理关掉。
            try:
                state["enabled"] = int(str(val).strip())
            except (ValueError, TypeError):
                state["enabled"] = 0
        except OSError:
            state["enabled"] = 0
        for name in ("ProxyServer", "ProxyOverride"):
            try:
                val, _ = winreg.QueryValueEx(key, name)
                state[name] = val if isinstance(val, str) else ""
            except OSError:
                state[name] = ""
        winreg.CloseKey(key)
    except Exception as e:
        logger.warning("读取系统代理状态失败：%s", e)
    return state


def _set_reg(key_name: str, value, reg_type) -> None:
    import winreg  # type: ignore

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _REG_PATH, 0,
        winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
    )
    winreg.SetValueEx(key, key_name, 0, reg_type, value)
    winreg.CloseKey(key)


def _broadcast() -> None:
    """通知所有 WinInet 应用（含 Clash 的订阅拉取）设置已变更。"""
    try:
        import ctypes

        wininet = ctypes.windll.wininet  # type: ignore
        wininet.InternetSetOptionW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
        ]
        wininet.InternetSetOptionW(None, _OPT_SETTINGS_CHANGED, None, 0)
        wininet.InternetSetOptionW(None, _OPT_REFRESH, None, 0)
    except Exception as e:
        logger.warning("广播代理设置变更失败（可忽略）：%s", e)


def disable_system_proxy() -> Optional[Dict[str, object]]:
    """关闭系统代理，返回关闭前的状态（用于之后恢复）。

    失败时返回 None 并打日志，不抛异常。
    """
    try:
        import winreg  # type: ignore

        prev = get_proxy_state()
        if prev["enabled"]:
            _set_reg("ProxyEnable", 0, winreg.REG_DWORD)
        _broadcast()
        logger.info("已临时关闭系统代理（原状态 enabled=%s）", prev["enabled"])
        return prev
    except Exception as e:
        logger.error("关闭系统代理失败：%s", e)
        return None


def restore_system_proxy(state: Optional[Dict[str, object]]) -> bool:
    """按之前保存的状态恢复系统代理。

    仅当 state 有效时才恢复；恢复后广播变更。
    返回是否成功。
    """
    if not state:
        logger.info("无代理状态可恢复，跳过")
        return False
    try:
        import winreg  # type: ignore

        _set_reg("ProxyEnable", int(state.get("enabled") or 0), winreg.REG_DWORD)
        srv = state.get("ProxyServer") or ""
        ovr = state.get("ProxyOverride") or ""
        if srv:
            _set_reg("ProxyServer", srv, winreg.REG_SZ)
        if ovr:
            _set_reg("ProxyOverride", ovr, winreg.REG_SZ)
        _broadcast()
        logger.info("已恢复系统代理（enabled=%s）", state.get("enabled"))
        return True
    except Exception as e:
        logger.error("恢复系统代理失败：%s", e)
        return False
