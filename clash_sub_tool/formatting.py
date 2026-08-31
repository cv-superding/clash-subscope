# -*- coding: utf-8 -*-
"""显示格式化：脱敏、流量、时间、导出文本。"""

import datetime
import os
from typing import List, Optional

from .models import ScanResult, SubscriptionItem

MASK = "••••••••"


def mask_url(url: str, keep_head: int = 30, keep_tail: int = 4) -> str:
    """脱敏显示：保留前若干字符 + 省略号 + 末尾少量字符。

    订阅链接里的令牌通常位于中段，因此中段统一打码。
    """
    if not url:
        return ""
    n = len(url)
    if n <= keep_head + keep_tail + len(MASK):
        # URL 太短，无法同时保留头尾+掩码：尽量保留头尾，掩码缩短
        head = max(4, n // 3)
        tail = max(2, n // 5)
        if head + tail >= n:
            return MASK  # 极短：整体打码
        return url[:head] + MASK + url[-tail:]
    masked = url[:keep_head] + MASK
    if keep_tail:
        masked += url[-keep_tail:]
    return masked


def fmt_bytes(num: Optional[int]) -> str:
    if num is None or num < 0:
        return "未知"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    val = float(num)
    idx = 0
    while val >= 1024 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    if idx == 0:
        return "%d B" % int(val)
    return "%.2f %s" % (val, units[idx])


def fmt_traffic(item: SubscriptionItem) -> str:
    """已用 / 总量。"""
    if item.upload is None and item.download is None and item.total is None:
        return "未知"
    used = (item.upload or 0) + (item.download or 0)
    if not item.total:
        return (fmt_bytes(used) if used else "0 B") + " / 未知"
    if used <= 0:
        return "0 B / %s" % fmt_bytes(item.total)
    pct = used * 100.0 / item.total
    return "%s / %s（%.1f%%）" % (fmt_bytes(used), fmt_bytes(item.total), min(pct, 999.9))


def fmt_time(ts: Optional[int]) -> str:
    if not ts or ts <= 0:
        return "未知"
    try:
        if ts > 10 ** 12:  # 毫秒
            ts = ts // 1000
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return "未知"


def fmt_expire(ts: Optional[int]) -> str:
    if not ts or ts <= 0:
        return "未知"
    try:
        dt = datetime.datetime.fromtimestamp(ts)
    except (OSError, OverflowError, ValueError):
        return "未知"
    delta = dt - datetime.datetime.now()
    days = delta.days
    if days < 0:
        return "%s（已过期）" % dt.strftime("%Y-%m-%d")
    if days == 0:
        hours = max(0, delta.seconds // 3600)
        return "%s（仅剩 %d 小时）" % (dt.strftime("%Y-%m-%d"), hours)
    return "%s（剩 %d 天）" % (dt.strftime("%Y-%m-%d"), days)


def build_export_text(result: ScanResult, reveal: bool = False) -> str:
    """生成导出用的纯文本。"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = []
    lines.append("Clash 订阅链接导出")
    lines.append("导出时间：%s" % now)
    lines.append("脱敏：%s" % ("否（完整链接）" if reveal else "是"))
    lines.append("")

    if result.clients:
        lines.append("【客户端】")
        for c in result.clients:
            lines.append("  %s：%s%s" % (
                c.name, c.status_text,
                "（%s）" % c.data_dir if c.data_dir else "",
            ))
    if result.runtime and result.runtime.connected:
        lines.append("【运行时接口】%s，核心：%s，节点数：%d" % (
            result.runtime.channel, result.runtime.core_name or "未知", result.runtime.node_count))
    lines.append("")

    lines.append("【订阅配置】共 %d 项" % len(result.items))
    lines.append("")
    for idx, item in enumerate(result.items, 1):
        url = item.url if reveal else mask_url(item.url)
        lines.append("%d. %s%s" % (idx, item.name, "  ← 当前使用" if item.is_current else ""))
        lines.append("   客户端：%s" % item.client_name)
        lines.append("   订阅链接：%s" % url)
        lines.append("   来源：%s（%s）" % (item.source, item.source_detail))
        lines.append("   更新时间：%s" % fmt_time(item.updated))
        lines.append("   流量：%s" % fmt_traffic(item))
        lines.append("   到期：%s" % fmt_expire(item.expire))
        lines.append("")

    if result.issues:
        lines.append("【诊断信息】")
        for issue in result.issues:
            lines.append("  " + issue.as_text().replace("\n", "\n  "))
        lines.append("")

    lines.append("说明：本文件由本机工具生成，内容仅来自本机已有配置，未发起任何网络请求。")
    return "\n".join(lines)


def default_export_path() -> str:
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        desktop = os.path.expanduser("~")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(desktop, "Clash订阅链接_%s.txt" % stamp)
