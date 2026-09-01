# -*- coding: utf-8 -*-
"""检测与关闭本机 Clash 客户端进程。

导入订阅前必须让客户端退出，否则它会在后台异步改写 profiles.yaml，
与我们的写入产生竞争，导致写入被覆盖或导入「看起来失败」。

只终止 GUI / 核心进程（CLIENT_DEFS 的 processes 字段），
**不**碰 service_processes（Windows 服务，终止需要管理员且可能引发连锁重启）。
"""

import os
import time
from typing import List, Optional, Tuple

from . import clients
from .models import ClientInfo


def _pid_exists(pid: int) -> bool:
    """判断某个 pid 是否仍然存在（不枚举全量进程，开销极小）。"""
    if not pid:
        return False
    try:
        import psutil  # type: ignore

        return bool(psutil.pid_exists(pid))
    except Exception:
        return False


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


def close_and_wait(client_info: ClientInfo, timeout: float = 3.0,
                   kill_service: bool = False) -> Tuple[bool, str]:
    """关闭客户端并等待其进程真正退出（避免写入时文件句柄尚未释放）。

    与 close() 的区别：这里只对被 kill 的 pid 做 pid_exists 探测，
    不会反复枚举全量进程列表，轮询开销极小。

    参数 `kill_service`：
      - False（默认）：只杀 `processes` 字段里的主进程，不碰 `service_processes`。
        适用于「让用户自己关 Clash」之类非强制场景。
      - True：把 service_processes 也一并 kill。
        **仅在导入订阅这种「必须让 Clash 完全退出」的场景使用**——
        否则服务会立刻拉起主进程，导致写入被覆盖（M4 历史教训）。
        服务进程是 Windows 服务，没有管理员权限会失败；
        失败信息会原样返回，让调用方提示用户以管理员身份运行。
    """
    defs = clients.get_def(client_info.client_id)
    if not defs:
        return False, "找不到该客户端定义，无法关闭"
    main_names = set(n.lower() for n in defs.get("processes", []))
    svc_names = set(n.lower() for n in defs.get("service_processes", []))
    if not main_names:
        return False, "该客户端无已知进程名，无法自动关闭"

    # 导入场景必须把服务一起杀掉；否则服务会立刻拉起主进程，
    # 写 profiles.yaml 仍会被新进程覆盖——v1.1.1 历史 bug 的根因。
    if kill_service and svc_names:
        target_names = main_names | svc_names
    else:
        target_names = main_names

    killed: List[str] = []
    failed: List[str] = []
    pids: List[int] = []
    for p in _psutil_procs():
        try:
            name = (p.info.get("name") or "").lower()
        except Exception:
            continue
        if name not in target_names:
            continue
        try:
            pid = p.info.get("pid")
            p.kill()
            killed.append(p.info.get("name") or name)
            if pid:
                pids.append(pid)
        except Exception as e:
            failed.append("%s(%s)" % (p.info.get("name") or name, e))

    # 等待被 kill 的进程真正退出（只探测已知 pid）
    if pids:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not any(_pid_exists(pid) for pid in pids):
                break
            time.sleep(0.1)

    if failed and not killed:
        # 全部失败：可能是权限不足（无法 kill Windows 服务），
        # 返回详细原因让调用方提示用户
        names_hint = ""
        if kill_service and svc_names:
            names_hint = "（含服务进程 %s）" % "、 ".join(sorted(svc_names))
        return False, "无法自动关闭：%s%s。请用任务管理器手动结束，或尝试以管理员身份运行本工具。" % (
            "、 ".join(failed), names_hint)
    if killed:
        parts = "、".join(sorted(set(killed)))
        if failed:
            return True, "已关闭 %s，但部分进程无法终止：%s（请手动结束）" % (
                parts, "、 ".join(failed))
        return True, "已关闭：%s" % parts
    # 调用方明确传入要 kill 的目标，但什么都没 kill 到——
    # 若 is_running 之前返回 True，这里却找不到进程，说明扫描与关闭之间状态不一致，
    # 应当作为失败而不是静默成功（避免上一版的"silent no-op"问题）。
    if kill_service and svc_names:
        hint = "已尝试杀进程与服务，但当前未发现可终止的目标"
    else:
        hint = "已尝试杀主进程，但当前未发现可终止的目标"
    return False, hint + "（请手动在任务管理器结束 Clash 后重试导入）"
