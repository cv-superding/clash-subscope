# -*- coding: utf-8 -*-
"""检测与关闭本机 Clash 客户端进程。

导入订阅前必须让客户端退出，否则它会在后台异步改写 profiles.yaml，
与我们的写入产生竞争，导致写入被覆盖或导入「看起来失败」。

只终止 GUI / 核心进程（CLIENT_DEFS 的 processes 字段），
**不**碰 service_processes（Windows 服务，终止需要管理员且可能引发连锁重启）。
"""

import os
from typing import List, Optional, Tuple

from . import clients
from .models import ClientInfo


def _psutil_procs() -> List:
    try:
        import psutil  # type: ignore
    except Exception:
        return []
    try:
        return list(psutil.process_iter(["pid", "name"]))
    except Exception:
        return []


def is_running(client_info: ClientInfo) -> bool:
    """该客户端当前是否有进程在跑。"""
    defs = clients.get_def(client_info.client_id)
    if not defs:
        return False
    names = set(n.lower() for n in defs.get("processes", []))
    if not names:
        return False
    for p in _psutil_procs():
        try:
            name = (p.info.get("name") or "").lower()
        except Exception:
            continue
        if name in names:
            return True
    return False


def running_process_names(client_info: ClientInfo) -> List[str]:
    """返回当前命中的进程名列表（用于提示用户）。"""
    defs = clients.get_def(client_info.client_id)
    if not defs:
        return []
    names = set(n.lower() for n in defs.get("processes", []))
    hit = []
    for p in _psutil_procs():
        try:
            name = (p.info.get("name") or "").lower()
        except Exception:
            continue
        if name in names:
            hit.append(p.info.get("name") or name)
    return hit


def close(client_info: ClientInfo) -> Tuple[bool, str]:
    """尝试终止该客户端的 GUI / 核心进程。

    返回 (成功?, 可读消息)。成功指：目标进程已不存在（本来就没跑，或已被我们杀掉）。
    """
    defs = clients.get_def(client_info.client_id)
    if not defs:
        return False, "找不到该客户端定义，无法关闭"
    names = set(n.lower() for n in defs.get("processes", []))
    if not names:
        return False, "该客户端无已知进程名，无法自动关闭"

    killed = []
    failed = []
    for p in _psutil_procs():
        try:
            name = (p.info.get("name") or "").lower()
        except Exception:
            continue
        if name not in names:
            continue
        try:
            p.kill()
            killed.append(p.info.get("name") or name)
        except Exception as e:
            failed.append("%s(%s)" % (p.info.get("name") or name, e))

    if killed and not failed:
        return True, "已关闭：%s" % ", ".join(sorted(set(killed)))
    if killed and failed:
        return True, "已关闭 %s，但部分进程无法终止：%s（请手动结束）" % (
            ", ".join(sorted(set(killed))), ", ".join(failed))
    if failed:
        return False, "无法自动关闭：%s（请用任务管理器手动结束）" % ", ".join(failed)
    # 没命中任何进程（可能刚退出，或 psutil 读不到）
    return True, "未检测到运行中的进程（可能已退出）"
