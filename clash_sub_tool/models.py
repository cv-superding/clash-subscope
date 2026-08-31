# -*- coding: utf-8 -*-
"""数据模型。"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 来源类型常量
SRC_PROFILE = "本地配置文件"
SRC_RUNTIME = "运行时接口"
SRC_EMBEDDED = "配置文件内订阅"

# 问题级别
LV_INFO = "info"
LV_WARN = "warn"
LV_ERROR = "error"


@dataclass
class Issue:
    """一条诊断信息（提示 / 警告 / 错误）。"""

    level: str = LV_INFO
    title: str = ""
    detail: str = ""
    suggestion: str = ""

    def as_text(self) -> str:
        marks = {LV_INFO: "[提示]", LV_WARN: "[警告]", LV_ERROR: "[错误]"}
        parts = ["%s %s" % (marks.get(self.level, "[提示]"), self.title)]
        if self.detail:
            parts.append("    " + self.detail.replace("\n", "\n    "))
        if self.suggestion:
            parts.append("    建议：" + self.suggestion)
        return "\n".join(parts)


@dataclass
class SubscriptionItem:
    """一个订阅配置条目。"""

    uid: str = ""
    name: str = ""
    url: str = ""
    client_id: str = ""
    client_name: str = ""
    source: str = SRC_PROFILE
    source_detail: str = ""
    updated: Optional[int] = None          # 更新时间（Unix 秒）
    upload: Optional[int] = None           # 已上传字节
    download: Optional[int] = None         # 已下载字节
    total: Optional[int] = None            # 总流量字节
    expire: Optional[int] = None           # 到期时间（Unix 秒）
    is_current: bool = False               # 是否为当前正在使用的配置
    runtime_nodes: Optional[int] = None    # 运行时统计到的节点数
    shared_count: int = 1                  # 同一链接被多少个配置共用

    def key(self) -> str:
        """去重键。"""
        return "%s|%s|%s" % (self.client_id, self.uid, self.url)


@dataclass
class ClientInfo:
    """一个在本机发现的 Clash 客户端。"""

    client_id: str = ""
    name: str = ""
    data_dir: str = ""
    running: bool = False
    processes: List[str] = field(default_factory=list)
    installed: bool = True

    @property
    def status_text(self) -> str:
        if self.running:
            return "运行中"
        if self.installed:
            return "已安装，未运行"
        return "未发现"


@dataclass
class RuntimeInfo:
    """运行时接口的连接结果。"""

    connected: bool = False
    channel: str = ""            # 描述文字，如 "TCP 127.0.0.1:9090" / "命名管道 \\.\pipe\verge-mihomo"
    channel_type: str = ""       # tcp / pipe
    endpoint: str = ""
    core_name: str = ""          # mihomo / clash / clash-premium
    version: str = ""
    secret_used: bool = False
    node_count: int = 0
    provider_count: int = 0
    subscription_info: Optional[Dict[str, Any]] = None
    error: str = ""
    tried: List[str] = field(default_factory=list)


@dataclass
class ScanResult:
    """一次完整扫描的结果。"""

    clients: List[ClientInfo] = field(default_factory=list)
    items: List[SubscriptionItem] = field(default_factory=list)
    runtime: Optional[RuntimeInfo] = None
    issues: List[Issue] = field(default_factory=list)

    def active_clients(self) -> List[ClientInfo]:
        return [c for c in self.clients if c.installed]

    def any_running(self) -> bool:
        return any(c.running for c in self.clients)
