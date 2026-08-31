# -*- coding: utf-8 -*-
"""把一条订阅链接写入本机 Clash 客户端的配置文件（profiles）。

这是本工具唯一的「写」操作，且完全在用户点击按钮并确认后才执行：
- 写前自动备份原文件（profiles.yaml.bak_import_<时间戳>）
- 仅追加一条新订阅，不改动已有条目
- 链接已存在则跳过（去重）
- 任何解析/写入失败都回滚并给出可读错误，绝不破坏原文件

仅读写本机文件，不联网、不上传、不拉取订阅内容（节点拉取由 Clash 客户端完成）。
"""

import os
import shutil
import time
import uuid
from typing import List, Optional, Tuple

from . import clients
from .models import ClientInfo, Issue, LV_WARN


def _first_url(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        for v in value:
            if isinstance(v, str) and v.strip().lower().startswith(("http://", "https://")):
                return v.strip()
    return ""


def _find_profiles_file(client_info: ClientInfo) -> Optional[str]:
    """定位该客户端的 profiles 主文件（不存在则返回计划写入路径）。"""
    client_def = clients.get_def(client_info.client_id)
    if not client_def:
        return None
    data_dir = client_info.data_dir
    if not data_dir:
        # 退而用 dirs 展开后的第一个已存在目录
        for cand in client_def.get("dirs", []):
            p = clients.expand(cand)
            if p and os.path.isdir(p):
                data_dir = p
                break
    if not data_dir:
        return None
    files = client_def.get("profiles_files", ["profiles.yaml"])
    for fn in files:
        p = os.path.join(data_dir, fn)
        if os.path.isfile(p):
            return p
    # 文件不存在：计划新建第一个候选名
    return os.path.join(data_dir, files[0])


def add_subscription(
    client_info: ClientInfo,
    url: str,
    name: Optional[str] = None,
    issues: Optional[List[Issue]] = None,
) -> Tuple[bool, str]:
    """把 url 作为一条 remote 订阅追加进客户端的 profiles。

    返回 (成功?, 可读消息)。
    """
    url = (url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return False, "订阅链接必须以 http:// 或 https:// 开头"

    path = _find_profiles_file(client_info)
    if not path:
        return False, "找不到该客户端的配置目录，无法写入"

    existed = os.path.isfile(path)
    backup_path = None
    if existed:
        try:
            backup_path = "%s.bak_import_%d" % (path, int(time.time()))
            shutil.copy2(path, backup_path)
        except OSError as e:
            return False, "备份原文件失败，已取消写入：%s" % e
    else:
        # 新建文件：确保目录存在
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except OSError as e:
            return False, "创建配置目录失败：%s" % e

    # 复用 parsers 的 YAML 加载（含编码与加密检测）
    from . import parsers

    data = parsers.load_yaml(path, issues) if existed else None
    if existed and data is None:
        # 解析失败（加密/损坏）：不要动原文件
        return False, "原配置文件无法解析（可能已加密或损坏），已取消写入，原文件未改动"
    if not isinstance(data, dict):
        data = {}

    # 选取条目列表所在键
    list_key = None
    for k in ("items", "profiles", "list"):
        if isinstance(data.get(k), list):
            list_key = k
            break
    if list_key is None:
        list_key = "items"
        data.setdefault("items", [])

    entries = data[list_key]
    if not isinstance(entries, list):
        entries = []
        data[list_key] = entries

    # 去重
    for e in entries:
        if isinstance(e, dict) and _first_url(e.get("url")) == url:
            if backup_path and os.path.isfile(backup_path):
                try:
                    os.remove(backup_path)
                except OSError:
                    pass
            return False, "该订阅链接已存在于配置中，未重复添加"

    uid = uuid.uuid4().hex
    # 字段对齐 Clash Verge Rev 的 remote 条目真实结构：
    # - file：缓存拉取结果的相对文件名（解析为 profiles/<uid>.yaml），Verge 点「更新」时写入
    # - option：更新间隔/自动更新/引用其他 profile 的 uid；缺失非空引用对新建订阅无害
    entry = {
        "uid": uid,
        "type": "remote",
        "name": (name or "导入的订阅").strip() or "导入的订阅",
        "file": "%s.yaml" % uid,
        "url": url,
        "updated": 0,
        "extra": {"upload": 0, "download": 0, "total": 0, "expire": 0},
        "option": {
            "update_interval": 0,
            "allow_auto_update": True,
            "merge": "",
            "script": "",
            "rules": "",
            "proxies": "",
            "groups": "",
        },
    }
    entries.append(entry)

    # 落盘（保留原备份 backup_path）
    try:
        import yaml  # type: ignore

        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        tmp = path + ".tmp_%d" % int(time.time())
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        # 原子替换：先写临时文件再 rename，降低写到一半被中断的风险
        os.replace(tmp, path)
    except Exception as e:
        # 回滚：尽量还原备份
        if backup_path and os.path.isfile(backup_path):
            try:
                shutil.copy2(backup_path, path)
            except OSError:
                pass
        return False, "写入失败已回滚：%s" % e

    return True, "已添加订阅到 %s（配置：%s）" % (client_info.name, os.path.basename(path))
