# -*- coding: utf-8 -*-
"""本地配置文件解析。

支持 Clash Verge 系（Verge Rev / Nyanpasu / FlClash）、
Clash for Windows、以及独立 mihomo 核心的配置格式。
任何读取失败都会被记录为 Issue，不会抛出异常。
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from . import clients
from .models import Issue, LV_ERROR, LV_INFO, LV_WARN, SRC_EMBEDDED, SRC_PROFILE, SubscriptionItem

MAX_YAML_BYTES = 8 * 1024 * 1024      # 超过 8MB 的配置文件改用正则提取
MAX_SCAN_FILES = 300                   # 单次最多扫描的配置文件数量
URL_RE = re.compile(r"https?://[^\s\"'<>\]]{6,}")


# --------------------------------------------------------------------------
# 基础读写
# --------------------------------------------------------------------------
def read_text(path: str, issues: Optional[List[Issue]] = None) -> Tuple[str, Optional[str]]:
    """读取文本，依次尝试 utf-8 / utf-8-sig / gbk / latin-1。

    返回 (内容, 错误信息)。
    """
    if not path or not os.path.isfile(path):
        return "", "文件不存在"
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return "", "无法获取文件大小：%s" % e
    if size > 64 * 1024 * 1024:
        return "", "文件过大（%.1f MB），已跳过" % (size / 1024.0 / 1024.0)

    raw = None
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except PermissionError:
        return "", "权限不足，无法读取该文件"
    except OSError as e:
        return "", "读取失败：%s" % e

    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return raw.decode(enc), None
        except (UnicodeDecodeError, LookupError):
            continue
    return "", "文件编码无法识别"


def _looks_encrypted(raw: str) -> bool:
    """粗略判断配置是否疑似加密：大量不可打印字符，或超长无换行 base64 串。"""
    if not raw:
        return False
    sample = raw[:4096]
    printable = sum(1 for ch in sample if ch.isprintable() or ch in "\r\n\t")
    if sample and printable / len(sample) < 0.85:
        return True
    return bool(re.search(r"^[A-Za-z0-9+/=]{400,}$", sample.strip().splitlines()[0])) if sample.strip() else False


def load_yaml(path: str, issues: Optional[List[Issue]] = None):
    """安全加载 YAML。失败时返回 None 并记录诊断信息。"""
    issues = issues if issues is not None else []
    text, err = read_text(path, issues)
    if err:
        issues.append(Issue(LV_WARN, "无法读取配置文件", "%s：%s" % (path, err),
                            "请确认文件未被占用；若客户端正在写入，可稍后重试。"))
        return None
    if _looks_encrypted(text):
        issues.append(
            Issue(
                LV_ERROR,
                "配置文件疑似已加密或已损坏",
                "文件 %s 无法按文本解析（存在大量不可读内容）。" % path,
                "部分客户端会对配置做加密存储。请在客户端内关闭配置加密（或导出为明文配置）后重试；"
                "本工具不会尝试任何解密或绕过认证的操作。",
            )
        )
        return None
    try:
        import yaml  # type: ignore
    except ImportError:
        issues.append(Issue(LV_ERROR, "缺少 PyYAML 依赖", "无法解析 %s" % path,
                            "请在运行环境中执行 pip install pyyaml。"))
        return None
    try:
        return yaml.safe_load(text)
    except Exception as e:
        msg = str(e).splitlines()[0] if str(e) else ""
        issues.append(Issue(LV_ERROR, "配置文件解析失败", "%s：%s" % (path, msg),
                            "文件可能已损坏或由不兼容的客户端版本生成，可尝试在客户端中重新导入配置。"))
        return None


def _to_int(value: Any) -> Optional[int]:
    """把各种可能的写法转成整数秒/字节，失败返回 None。"""
    if value in (None, "", "null"):
        return None
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return int(value)
        s = str(value).strip()
        if not s:
            return None
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _first_url(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        for v in value:
            if isinstance(v, str) and v.strip().lower().startswith(("http://", "https://")):
                return v.strip()
    return ""


def _short_name(name: str, fallback: str = "") -> str:
    name = (name or "").strip()
    if name:
        return name
    return fallback or "未命名配置"


# --------------------------------------------------------------------------
# 各 flavor 的 profiles 解析
# --------------------------------------------------------------------------
def _iter_profile_entries(data: Any) -> List[Dict]:
    """从 profiles 数据中取出条目列表，兼容 items / profiles 两种键名。"""
    if not isinstance(data, dict):
        return []
    for key in ("items", "profiles", "list"):
        val = data.get(key)
        if isinstance(val, list):
            return [v for v in val if isinstance(v, dict)]
    return []


def _current_uid(data: Dict) -> str:
    for key in ("current", "current-profile", "current_profile", "currentUid"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict) and val.get("uid"):
            return str(val["uid"])
    # CFW 用 selected 记录当前选择
    sel = data.get("selected")
    if isinstance(sel, list):
        for s in sel:
            if isinstance(s, dict) and s.get("uid"):
                return str(s["uid"])
    return ""


def _parse_extra(entry: Dict, item: SubscriptionItem) -> None:
    """解析流量 / 到期信息，兼容 extra 嵌套与平铺两种写法。"""
    extra = entry.get("extra")
    if not isinstance(extra, dict):
        extra = entry
    for src_key, attr in (
        ("upload", "upload"),
        ("download", "download"),
        ("total", "total"),
        ("expire", "expire"),
        ("updated", "updated"),
    ):
        val = _to_int(extra.get(src_key))
        if val is None:
            val = _to_int(entry.get(src_key))
        if val is not None and val > 0:
            setattr(item, attr, val)
        elif val is not None and attr == "updated":
            setattr(item, attr, val)


def parse_profiles_file(
    path: str,
    client_id: str,
    client_name: str,
    flavor: str,
    issues: List[Issue],
) -> List[SubscriptionItem]:
    """解析一个 profiles 文件，返回其中的订阅条目。"""
    data = load_yaml(path, issues)
    if not isinstance(data, dict):
        return []

    cur_uid = _current_uid(data)
    entries = _iter_profile_entries(data)
    out: List[SubscriptionItem] = []

    for entry in entries:
        etype = str(entry.get("type") or "").lower()
        url = _first_url(entry.get("url"))
        if not url:
            continue
        # remote 类型一定带订阅；其他类型若显式写了 url 也一并收录
        if etype and etype not in ("remote", "remote-profile", "subscription", "http", ""):
            continue

        item = SubscriptionItem(
            uid=str(entry.get("uid") or entry.get("id") or ""),
            name=_short_name(entry.get("name"), os.path.splitext(os.path.basename(path))[0]),
            url=url,
            client_id=client_id,
            client_name=client_name,
            source=SRC_PROFILE,
            source_detail=os.path.basename(path),
        )
        _parse_extra(entry, item)
        item.is_current = bool(cur_uid and item.uid and cur_uid == item.uid)
        out.append(item)

    return out


def parse_generic_config(
    path: str,
    client_id: str,
    client_name: str,
    issues: List[Issue],
) -> List[SubscriptionItem]:
    """解析通用 clash 配置中的 proxy-providers（多订阅场景）。"""
    data = load_yaml(path, issues)
    if not isinstance(data, dict):
        return []
    providers = data.get("proxy-providers") or data.get("proxy_providers")
    if not isinstance(providers, dict):
        return []

    out: List[SubscriptionItem] = []
    base = os.path.basename(path)
    for name, conf in providers.items():
        if not isinstance(conf, dict):
            continue
        url = _first_url(conf.get("url"))
        if not url:
            continue
        out.append(
            SubscriptionItem(
                uid="provider:%s" % name,
                name=_short_name(str(name), base),
                url=url,
                client_id=client_id,
                client_name=client_name,
                source=SRC_EMBEDDED,
                source_detail="%s → proxy-providers.%s" % (base, name),
                updated=_to_int(conf.get("updated")),
            )
        )
    return out


def scan_profile_dir(
    dir_path: str,
    client_id: str,
    client_name: str,
    known_urls: set,
    issues: List[Issue],
) -> List[SubscriptionItem]:
    """扫描已下载配置片段目录，找出内嵌的 proxy-providers 订阅。"""
    if not dir_path or not os.path.isdir(dir_path):
        return []
    out: List[SubscriptionItem] = []
    count = 0
    try:
        filenames = sorted(os.listdir(dir_path))
    except PermissionError:
        issues.append(Issue(LV_WARN, "目录无访问权限", dir_path,
                            "请以当前登录用户身份运行本工具；若在受限账户下，改用有权限的账户。"))
        return []
    except OSError as e:
        issues.append(Issue(LV_WARN, "目录读取失败", "%s：%s" % (dir_path, e), ""))
        return []

    for fn in filenames:
        if count >= MAX_SCAN_FILES:
            break
        if not fn.lower().endswith((".yaml", ".yml")):
            continue
        full = os.path.join(dir_path, fn)
        try:
            if not os.path.isfile(full) or os.path.getsize(full) > MAX_YAML_BYTES:
                continue
        except OSError:
            continue
        text, err = read_text(full)
        if err or "proxy-providers" not in text:
            continue
        count += 1
        for item in parse_generic_config(full, client_id, client_name, issues):
            if item.url not in known_urls:
                out.append(item)
                known_urls.add(item.url)
    return out


def collect_config_paths(client_def: Dict, data_dir: str) -> List[str]:
    """收集与某客户端相关的配置文件路径（供运行时接口探测使用）。"""
    paths: List[str] = []
    if not data_dir:
        for cand in client_def.get("dirs", []):
            p = clients.expand(cand)
            if p and os.path.isdir(p):
                data_dir = p
                break
    for key in ("runtime_configs", "app_configs", "profiles_files"):
        for fn in client_def.get(key, []):
            p = os.path.join(data_dir, fn) if data_dir else fn
            if os.path.isfile(p) and p not in paths:
                paths.append(p)
    for cand in client_def.get("extra_config_dirs", []):
        d = clients.expand(cand)
        if d and os.path.isdir(d):
            for fn in ("profiles.yml", "profiles.yaml", "config.yaml"):
                p = os.path.join(d, fn)
                if os.path.isfile(p) and p not in paths:
                    paths.append(p)
    return paths


def parse_client(client_info, issues: List[Issue]) -> List[SubscriptionItem]:
    """解析单个客户端的全部订阅配置。"""
    client_def = clients.get_def(client_info.client_id)
    if not client_def:
        return []
    data_dir = client_info.data_dir
    items: List[SubscriptionItem] = []
    known_urls: set = set()

    # 1) profiles 主文件
    for fn in client_def.get("profiles_files", []):
        p = os.path.join(data_dir, fn) if data_dir else ""
        if not p or not os.path.isfile(p):
            continue
        flavor = client_def.get("flavor", "verge")
        if flavor == "generic":
            got = parse_generic_config(p, client_info.client_id, client_info.name, issues)
        else:
            got = parse_profiles_file(p, client_info.client_id, client_info.name, flavor, issues)
        # 同一客户端下不同 uid 的配置即使链接相同也逐条列出（用户可能重复导入过），
        # 去重只针对完全相同的 (客户端, uid, 链接) 三元组，交由 scanner._dedupe 处理。
        for it in got:
            known_urls.add(it.url)
            items.append(it)
        if got:
            break

    # 2) 顶层 config.yaml 里的 proxy-providers
    for fn in client_def.get("runtime_configs", []) + client_def.get("app_configs", []):
        p = os.path.join(data_dir, fn) if data_dir else ""
        if not p or not os.path.isfile(p):
            continue
        for it in parse_generic_config(p, client_info.client_id, client_info.name, issues):
            if it.url not in known_urls:
                known_urls.add(it.url)
                items.append(it)

    # 3) 已下载配置片段目录（多订阅嵌套场景）
    for sub in client_def.get("profile_dirs", []):
        d = os.path.join(data_dir, sub) if data_dir else ""
        for it in scan_profile_dir(d, client_info.client_id, client_info.name, known_urls, issues):
            items.append(it)

    if data_dir and not items:
        issues.append(
            Issue(
                LV_INFO,
                "%s 的配置目录中没有远程订阅" % client_info.name,
                "已检查目录：%s" % data_dir,
                "若你使用的是本地文件配置（非订阅链接），则不会出现在此列表中，这属于正常情况。",
            )
        )
    return items
