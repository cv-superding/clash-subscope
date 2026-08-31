# -*- coding: utf-8 -*-
"""扫描编排：把发现、解析、运行时探测串成一次完整扫描。"""

from typing import Dict, List, Optional

from . import clients, parsers, runtime
from .models import (ClientInfo, Issue, LV_ERROR, LV_INFO, RuntimeInfo,
                     SRC_RUNTIME, ScanResult, SubscriptionItem)


def scan(progress=None) -> ScanResult:
    """执行一次完整扫描。任何内部异常都会被捕获并转成诊断信息。"""
    result = ScanResult()
    issues: List[Issue] = result.issues

    def tick(msg: str) -> None:
        if progress:
            try:
                progress(msg)
            except Exception:
                pass

    # 1. 发现客户端
    tick("正在查找本机 Clash 客户端…")
    try:
        found: List[ClientInfo] = clients.discover_clients(issues)
    except Exception as e:
        issues.append(Issue(LV_ERROR, "客户端查找失败", str(e),
                            "请确认当前用户对 %APPDATA% 有读取权限。"))
        found = []
    result.clients = found

    # 2. 解析本地配置
    config_paths: List[str] = []
    for client in found:
        tick("正在读取 %s 的配置…" % client.name)
        try:
            result.items.extend(parsers.parse_client(client, issues))
        except Exception as e:
            issues.append(
                Issue(LV_ERROR, "读取 %s 配置时出错" % client.name,
                      "%s：%s" % (type(e).__name__, e),
                      "该客户端已跳过，其余客户端不受影响。")
            )
        try:
            for p in parsers.collect_config_paths(clients.get_def(client.client_id), client.data_dir):
                if p not in config_paths:
                    config_paths.append(p)
        except Exception:
            pass

    # 3. 运行时接口
    tick("正在探测运行时接口…")
    try:
        rt: Optional[RuntimeInfo] = runtime.probe_runtime(config_paths)
    except Exception as e:
        rt = RuntimeInfo(error="探测过程异常：%s" % e)
    result.runtime = rt

    # 4. 合并运行时信息
    _merge_runtime(result)

    # 5. 去重 + 排序
    result.items = _dedupe(result.items)
    result.items.sort(key=lambda it: (
        0 if it.is_current else 1,
        it.client_name,
        it.name,
    ))

    # 6. 汇总诊断
    if not result.items:
        issues.insert(0, Issue(
            LV_INFO,
            "未找到任何订阅链接",
            "已扫描 %d 个客户端的配置目录。" % len(found),
            "若你使用的是本地文件配置（没有订阅地址），列表为空属于正常情况。",
        ))
    tick("完成")
    return result


def _merge_runtime(result: ScanResult) -> None:
    """把运行时拿到的流量/到期信息补到当前使用的配置上。"""
    rt = result.runtime
    if not rt or not rt.connected:
        return

    current = next((it for it in result.items if it.is_current), None)
    if current is None:
        return

    current.runtime_nodes = rt.node_count or None

    si = rt.subscription_info
    if not isinstance(si, dict) or not si:
        return

    def pick(*keys):
        for k in keys:
            v = si.get(k)
            if isinstance(v, (int, float)) and v > 0:
                return int(v)
        return None

    got_upload = pick("Upload", "upload")
    got_download = pick("Download", "download")
    got_total = pick("Total", "total")
    got_expire = pick("Expire", "expire")

    # 运行时数据优先，但仅在确有值时覆盖
    if got_upload is not None:
        current.upload = got_upload
    if got_download is not None:
        current.download = got_download
    if got_total is not None:
        current.total = got_total
    if got_expire is not None:
        current.expire = got_expire
    if any(v is not None for v in (got_upload, got_download, got_total, got_expire)):
        if current.source != SRC_RUNTIME:
            current.source_detail = "%s + 运行时接口" % current.source_detail
        current.source = SRC_RUNTIME


def _dedupe(items: List[SubscriptionItem]) -> List[SubscriptionItem]:
    """按 (客户端, uid, url) 去重；同名配置保留各自的 uid 以便区分。"""
    seen = {}
    out: List[SubscriptionItem] = []
    for it in items:
        key = it.key()
        if key in seen:
            old = seen[key]
            if it.is_current:
                old.is_current = True
            continue
        seen[key] = it
        out.append(it)

    # 统计同一客户端下被多个配置共用的链接
    counter: Dict[str, int] = {}
    for it in out:
        counter[it.url] = counter.get(it.url, 0) + 1
    for it in out:
        it.shared_count = counter.get(it.url, 1)
    return out
