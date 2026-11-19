"""资源来源登记(provenance,v2,2026-06-16)。

记录每个"配置引用的资源样式"是从哪来的(内置/社区/网盘/用户自导入),供换机后
按来源自动重获取。只存元数据(几 KB),不存资源本身。键 = "<config_key>:<style>"
与 resource_health 的 invalid_config_refs 同口径,便于对账匹配。
纯文件 I/O + dict,无 Qt/网络依赖,可单测。
"""
from __future__ import annotations

import json
import os
import time
from typing import Dict, Iterable, Optional

from core.io_validation import replace_with_retry

SOURCE_BUILTIN = "builtin"
SOURCE_COMMUNITY = "community"
SOURCE_NETDISK = "netdisk"
SOURCE_LOCAL = "local_import"
VALID_SOURCES = frozenset({SOURCE_BUILTIN, SOURCE_COMMUNITY, SOURCE_NETDISK, SOURCE_LOCAL})


def _key(config_key: str, style: str) -> str:
    return f"{config_key}:{style}"


class ProvenanceStore:
    def __init__(self, path: str):
        self.path = path

    def _load(self) -> Dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
            return {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: Dict) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        replace_with_retry(tmp, self.path)

    def record(self, domain: str, style: str, source: str,
        ref: Optional[str] = None, sha256: Optional[str] = None,
        size: Optional[int] = None) -> None:
        """资源进入本机时按"资源域+样式"登记来源(导入向导/装内置包/社区下载处调用)。
domain 取 resources 下的子目录名(如 weapon_kill_sounds / kill_icons),
与 config_sync.FIELD_DOMAIN 的取值一致,便于对账匹配。"""
        if source not in VALID_SOURCES:
            raise ValueError(f"unknown source: {source}")
        if not style or str(style) in ("", "0", "不启用", "未启用", "none", "off", "disabled"):
            return
        data = self._load()
        data[_key(domain, style)] = {
            "source": source, "ref": ref,
            "sha256": sha256,
            "size": size,
            "ts": int(time.time()),
        }
        self._save(data)

    def get(self, domain: str, style: str) -> Optional[Dict]:
        return self._load().get(_key(domain, style))

    def all(self) -> Dict:
        return self._load()

    def build_manifest(self, referenced_keys: Iterable[str]) -> Dict:
        """取"配置当前引用到的样式"的来源子集,作为随配置上云的精简清单。"""
        data = self._load()
        out = {}
        for k in referenced_keys or []:
            if k in data:
                out[k] = data[k]
        return out
