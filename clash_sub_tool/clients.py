# -*- coding: utf-8 -*-
"""客户端定义与本机发现。

仅使用本机进程列表与本地文件系统，不做任何网络请求。
"""

import os
from typing import Dict, List, Optional

from .models import ClientInfo, Issue, LV_INFO, LV_WARN

# 各客户端的识别规则。
# dirs 里支持 %APPDATA% / %LOCALAPPDATA% / %USERPROFILE% 等环境变量占位符，
# 以兼容不同 Windows 版本与用户目录。
CLIENT_DEFS: List[Dict] = [
    {
        "id": "clash-verge-rev",
        "name": "Clash Verge Rev",
        "flavor": "verge",
        "processes": ["clash-verge.exe", "verge-mihomo.exe", "clash-verge"],
        "service_processes": ["clash-verge-service.exe"],
        "dirs": [
            r"%APPDATA%\io.github.clash-verge-rev.clash-verge-rev",
            r"%APPDATA%\com.clash-verge-rev.app",
            r"%APPDATA%\clash-verge-rev",
        ],
        "profiles_files": ["profiles.yaml", "profiles.yml"],
        "app_configs": ["verge.yaml", "config.yaml"],
        "runtime_configs": ["clash-verge.yaml", "clash-verge-check.yaml", "config.yaml"],
        "profile_dirs": ["profiles"],
    },
    {
        "id": "clash-verge",
        "name": "Clash Verge（旧版）",
        "flavor": "verge",
        "processes": ["Clash Verge.exe", "clash.exe", "clash-meta.exe"],
        "dirs": [
            r"%APPDATA%\io.github.clash-verge.clash-verge",
            r"%APPDATA%\Clash Verge",
        ],
        "profiles_files": ["profiles.yaml", "profiles.yml"],
        "app_configs": ["verge.yaml", "config.yaml"],
        "runtime_configs": ["clash.yaml", "config.yaml"],
        "profile_dirs": ["profiles"],
    },
    {
        "id": "clash-nyanpasu",
        "name": "Clash Nyanpasu",
        "flavor": "verge",
        "processes": ["clash-nyanpasu.exe", "Clash Nyanpasu.exe", "nyanpasu-mihomo.exe", "mihomo.exe"],
        "dirs": [
            r"%APPDATA%\top.gydong.clash.nyanpasu",
            r"%APPDATA%\Clash Nyanpasu",
            r"%APPDATA%\clash-nyanpasu",
        ],
        "profiles_files": ["profiles.yaml", "profiles.yml"],
        "app_configs": ["verge.yaml", "nyanpasu.yaml", "config.yaml"],
        "runtime_configs": ["clash.yaml", "config.yaml"],
        "profile_dirs": ["profiles"],
    },
    {
        "id": "flclash",
        "name": "FlClash",
        "flavor": "flclash",
        "processes": ["FlClash.exe", "flclash.exe"],
        "service_processes": ["FlClashHelperService.exe"],
        "dirs": [
            r"%APPDATA%\com.follow.clash",
            r"%LOCALAPPDATA%\com.follow.clash",
            r"%APPDATA%\FlClash",
        ],
        "profiles_files": ["profiles.yaml", "profiles.yml"],
        "app_configs": ["config.yaml", "flclash.yaml"],
        "runtime_configs": ["config.yaml"],
        "profile_dirs": ["profiles"],
    },
    {
        "id": "clash-for-windows",
        "name": "Clash for Windows",
        "flavor": "cfw",
        "processes": ["Clash for Windows.exe", "clash-win64.exe"],
        "service_processes": ["Clash for Windows Helper.exe"],
        "dirs": [
            r"%APPDATA%\Clash for Windows",
        ],
        "profiles_files": ["profiles.yml", "profiles.yaml"],
        "app_configs": ["config.yaml", "config.yml"],
        "runtime_configs": ["config.yaml"],
        "profile_dirs": ["profiles"],
        "extra_config_dirs": [r"%USERPROFILE%\.config\clash"],
    },
    {
        "id": "clash-meta",
        "name": "Mihomo / Clash.Meta（独立核心）",
        "flavor": "generic",
        "processes": ["mihomo.exe", "clash-meta.exe", "clash.exe", "clash-premium.exe"],
        "dirs": [
            r"%USERPROFILE%\.config\clash",
            r"%USERPROFILE%\.config\mihomo",
            r"%USERPROFILE%\.config\clash-meta",
        ],
        "profiles_files": ["config.yaml", "config.yml"],
        "app_configs": [],
        "runtime_configs": ["config.yaml", "config.yml"],
        "profile_dirs": [],
    },
]


def expand(path: str) -> str:
    """展开环境变量与用户目录占位符。"""
    if not path:
        return ""
    return os.path.normpath(os.path.expandvars(os.path.expanduser(path)))


def _lower_names() -> List[str]:
    """收集所有需要匹配的进程名（小写）。"""
    names = []
    for d in CLIENT_DEFS:
        names.extend(d["processes"])
    return [n.lower() for n in names]


def snapshot_processes() -> Dict[str, List[int]]:
    """返回 {进程名小写: [pid, ...]}。

    优先使用 psutil（可拿到完整命令行）；没有 psutil 时退回 tasklist。
    """
    result: Dict[str, List[int]] = {}
    try:
        import psutil  # type: ignore

        for proc in psutil.process_iter(["pid", "name"]):
            name = (proc.info.get("name") or "").lower()
            if name:
                result.setdefault(name, []).append(proc.info["pid"])
        return result
    except Exception:
        pass

    # 退回方案：tasklist
    try:
        import subprocess

        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="gbk",
            errors="replace",
        ).stdout
        for line in out.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 2:
                result.setdefault(parts[0].lower(), []).append(int(parts[1]) if parts[1].isdigit() else 0)
    except Exception:
        pass
    return result


def discover_clients(issues: Optional[List[Issue]] = None) -> List[ClientInfo]:
    """扫描本机已安装的 Clash 客户端及其运行状态。"""
    issues = issues if issues is not None else []
    running = snapshot_processes()
    found: List[ClientInfo] = []

    for d in CLIENT_DEFS:
        data_dir = ""
        for cand in d["dirs"]:
            p = expand(cand)
            if p and os.path.isdir(p):
                data_dir = p
                break

        procs_hit = [n for n in d.get("processes", []) if n.lower() in running]
        # 后台服务常驻（如 FlClash 的 Helper、Verge 的 service）不代表客户端主程序已启动
        svc_hit = [n for n in d.get("service_processes", []) if n.lower() in running]
        if svc_hit and not procs_hit and data_dir:
            procs_hit = []  # 仅服务在跑：视为未运行，但仍列出客户端

        # 目录不存在且主进程也没跑 -> 认为未安装
        if not data_dir and not procs_hit:
            continue

        info = ClientInfo(
            client_id=d["id"],
            name=d["name"],
            data_dir=data_dir,
            running=bool(procs_hit),
            processes=procs_hit,
            installed=bool(data_dir),
        )
        found.append(info)

        if procs_hit and not data_dir:
            issues.append(
                Issue(
                    LV_WARN,
                    "检测到 %s 正在运行，但找不到其数据目录" % d["name"],
                    "匹配到的进程：%s" % "、".join(procs_hit),
                    "该客户端可能使用了自定义数据目录或绿色版配置，请手动确认配置存放位置。",
                )
            )

    if not found:
        issues.append(
            Issue(
                LV_WARN,
                "未在本机发现已知的 Clash 客户端",
                "已检查的目录：%APPDATA%\\…、%USERPROFILE%\\.config\\clash 等常见位置。",
                "请确认客户端是否已安装；若是绿色版，可将配置目录放到上述常见路径后重试。",
            )
        )
    elif not any(c.running for c in found):
        issues.append(
            Issue(
                LV_INFO,
                "未检测到正在运行的 Clash 客户端",
                "已发现配置目录，但对应进程不在运行列表内。",
                "工具已仅从本地配置文件读取订阅链接；启动客户端后可获取实时流量与到期信息。",
            )
        )
    return found


def get_def(client_id: str) -> Dict:
    for d in CLIENT_DEFS:
        if d["id"] == client_id:
            return d
    return {}
