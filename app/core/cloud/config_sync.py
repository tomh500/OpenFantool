"""云配置同步 · 纯逻辑核心（MVP，2026-06-16）。

设计见《帆派助手开放版_云配置同步_详细技术方案》。本模块**只放可单测的纯逻辑**
（载荷过滤 / 哈希 / 拉取决策 / 缺失资源分类 / 体积校验）；网络与磁盘读写由
调用方(控制器/UI)用现成的 account_auth_client + config 完成,保持本模块零副作用、
不依赖 Qt/网络,便于单测。
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional

from core.io_validation import replace_with_retry

CLOUD_EXCLUDE = frozenset({
    "csgo_dir", "window_width", "window_height", "debug_file_log",
    "player_steamid", "use_saved_size", "window_geometry",
    "usage_install_id", "usage_last_sent_ts",
})
MAX_CLOUD_BYTES = 262144
PULL_NOOP = "noop"
PULL_APPLY = "apply"
PULL_CONFLICT = "conflict"
PULL_NEED_UPGRADE = "need_upgrade"
PULL_CLOUD_EMPTY = "cloud_empty"
META_KEYS = frozenset({"__resource_manifest__"})
ACT_AUTO_RESTORE = "auto_restore"
ACT_DOWNLOAD = "download"
ACT_OPEN_LINK = "open_link"
ACT_MANUAL = "manual"
FIELD_DOMAIN = {
    "death_sound_style": "death",
    "grenade_sound_styles": "grenade_sounds",
    "c4_sound_style": "c4_sounds",
    "health_warning_style": "health_warning",
    "round_start_style": "round_sounds",
    "round_action_style": "round_sounds",
    "round_win_style": "round_sounds",
    "round_lose_style": "round_sounds",
    "round_mvp_style": "round_sounds",
    "weapon_switch_sounds": "switch_weapons",
    "weapon_reload_sounds": "reload_sounds",
    "kill_icon_style": "kill_icons",
    "flash_image_style": "flash_images",
    "flash_audio_style": "flash_audio",
    "crosshair_custom_data": "crosshair",
}


def domain_for_config_key(key) -> Optional[str]:
    """把(可能含点号的)配置字段名映射到资源域;未知返回 None。"""
    root = str(key or "").split(".", 1)[0]
    return FIELD_DOMAIN.get(root)


def filter_for_upload(config_dict: Dict) -> Dict:
    """上传前过滤:去掉设备本地/隐私字段。"""
    return {k: v for k, v in config_dict.items() if k not in CLOUD_EXCLUDE}


def merge_for_download(local_dict: Dict, cloud_dict: Dict) -> Dict:
    """套用云端:把云端字段覆盖到本地,但**绝不动**本地的设备/隐私字段。"""
    out = dict(local_dict)
    for k, v in cloud_dict.items():
        if k in CLOUD_EXCLUDE or k in META_KEYS:
            continue
        out[k] = v
    return out


def blob_sha256(blob: Dict) -> str:
    """对配置 dict 做稳定哈希(键排序),用于"有没有变"的判定。"""
    raw = json.dumps(blob, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def settings_sha(config_dict: Dict) -> str:
    """只对"用户设置"算哈希:排除设备/隐私字段(CLOUD_EXCLUDE)与元数据(META_KEYS)。
manifest 是机器相关的,绝不能进此哈希,否则跨机器永远误判"本地已改"。"""
    core = {k: v for k, v in config_dict.items() if k not in CLOUD_EXCLUDE and k not in META_KEYS}
    return blob_sha256(core)


def size_ok(blob: Dict) -> bool:
    return len(json.dumps(blob, ensure_ascii=False).encode("utf-8")) <= MAX_CLOUD_BYTES


def decide_pull_action(
    *, cloud_data: Optional[Dict], local_sha: str,
    last_synced_version: int, last_synced_sha: str,
    client_schema: int,
) -> str:
    """根据云端记录 + 本地上次同步标记 + 本地当前哈希,决定拉取动作。"""
    if not cloud_data:
        return PULL_CLOUD_EMPTY

    def _safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    if _safe_int(cloud_data.get("schema_version", 1), 1) > int(client_schema):
        return PULL_NEED_UPGRADE
    cloud_version = _safe_int(cloud_data.get("version", 0))
    cloud_changed = cloud_version != int(last_synced_version or 0)
    local_changed = (local_sha or "") != (last_synced_sha or "")
    if cloud_changed and local_changed:
        return PULL_CONFLICT
    if cloud_changed:
        return PULL_APPLY
    return PULL_NOOP


def classify_missing_resources(invalid_config_refs: List[Dict], manifest: Optional[Dict]) -> List[Dict]:
    """把 resource_health 的 invalid_config_refs 按资源清单 manifest 的来源归类。

manifest 以 "<domain>:<style>" 为键(domain 由 domain_for_config_key 从配置字段映射);
兼容旧的 "<config_key>:<style>" 与纯 style 键。缺来源 → source=unknown(手动)。
"""
    manifest = manifest or {}
    out = []
    for ref in invalid_config_refs or []:
        key = ref.get("key")
        val = ref.get("value")
        domain = domain_for_config_key(key)
        prov = None
        if domain is not None:
            prov = manifest.get(f"{domain}:{val}")
        if prov is None:
            prov = manifest.get(f"{key}:{val}") or manifest.get(str(val))
        prov = prov or {}
        out.append({
            "key": key,
            "value": val,
            "domain": domain,
            "reason": ref.get("reason"),
            "source": prov.get("source", "unknown"),
            "ref": prov.get("ref"),
        })
    return out


def plan_reconciliation(classified: List[Dict]) -> List[Dict]:
    """把"分类后的缺失项"映射为可执行动作。纯决策,执行(下载/重建)由调用方做。"""
    action_by_source = {
        "builtin": ACT_AUTO_RESTORE,
        "community": ACT_DOWNLOAD,
        "netdisk": ACT_OPEN_LINK,
    }
    out = []
    for it in classified or []:
        act = action_by_source.get(it.get("source"), ACT_MANUAL)
        out.append({**it, "action": act})
    return out


# 重建注记：此处保留行距，供 Python 3.13 类体的 __firstlineno__ 与安装字节码对齐。
# 这些行不参与执行；其他差异和核验方法见 CLOUD_MODULE_RECONSTRUCTION_NOTES.md。




























class CloudSyncState:
    """本地同步标记(独立小文件,避免改动庞大的 config.py)。"""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> Dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
            return {}
        except (OSError, ValueError):
            return {}

    def save(self, data: Dict) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        replace_with_retry(tmp, self.path)
class CloudConfigSyncController:
    """编排 push/pull/reconcile。所有副作用经注入的回调完成,便于单测。

注入项:
  auth_client     : 具 get_client_config / put_client_config
  token_provider(): -> token 或 None(None=未登录)
  read_config()   : -> dict(当前本地完整配置,通常 = 读 config.json)
  write_config(d) : 将 dict 落地为本地配置(通常 = 合并写 config.json)
  reload_config() : 让运行中的 config 重新加载(通常 = config.load_config())
  make_snapshot(reason): 套用云端前快照(通常 = config_snapshot_manager.create_snapshot)
  health_report() : -> dict(resource_health.collect_resource_system_health 结果)
  state           : CloudSyncState
  client_schema   : int(CONFIG_SCHEMA_VERSION)
  device_label    : str
"""

    def __init__(self, *, auth_client, token_provider, read_config, write_config,
                 reload_config, make_snapshot, health_report, state, client_schema,
                 device_label, manifest_provider=None):
        self.auth = auth_client
        self.token_provider = token_provider
        self.read_config = read_config
        self.write_config = write_config
        self.reload_config = reload_config
        self.make_snapshot = make_snapshot
        self.health_report = health_report
        self.state = state
        self.client_schema = int(client_schema)
        self.device_label = device_label
        self.manifest_provider = manifest_provider or (lambda: {})

    def _local_blob(self) -> Dict:
        return filter_for_upload(self.read_config())

    def push(self) -> Dict:
        token = self.token_provider()
        if not token:
            return {"status": "not_logged_in"}
        cfg = self.read_config()
        sha = settings_sha(cfg)
        st = self.state.load()
        if sha == st.get("last_synced_sha"):
            return {"status": "noop"}
        upload = filter_for_upload(cfg)
        upload["__resource_manifest__"] = self.manifest_provider() or {}
        if not size_ok(upload):
            return {"status": "too_large"}
        try:
            resp = self.auth.put_client_config(
                token, config=upload, schema_version=self.client_schema,
                base_version=st.get("last_synced_version"),
                device_label=self.device_label, sha256=sha,
            )
        except Exception as exc:
            sv = getattr(exc, "server_version", None)
            if sv is not None or exc.__class__.__name__ == "AuthConflict":
                return {"status": "conflict", "server_version": sv}
            return {"status": "error", "error": str(exc)}
        new_version = int((resp or {}).get("data", {}).get("version", 0))
        self.state.save({"last_synced_version": new_version, "last_synced_sha": sha})
        return {"status": "ok", "version": new_version}

    def pull(self) -> Dict:
        token = self.token_provider()
        if not token:
            return {"status": "not_logged_in"}
        try:
            cloud = self.auth.get_client_config(token)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        st = self.state.load()
        local_sha = blob_sha256(self._local_blob())
        action = decide_pull_action(
            cloud_data=cloud, local_sha=local_sha,
            last_synced_version=st.get("last_synced_version", 0),
            last_synced_sha=st.get("last_synced_sha", ""),
            client_schema=self.client_schema,
        )
        if action != PULL_APPLY:
            return {"status": action}
        try:
            from config import config as _cfg
            if hasattr(_cfg, "save_config_now"):
                _cfg.save_config_now()
        except Exception:
            pass
        self.make_snapshot("cloud-apply")
        merged = merge_for_download(self.read_config(), cloud.get("config") or {})
        self.write_config(merged)
        self.reload_config()
        try:
            applied_version = int(cloud.get("version", 0))
        except (TypeError, ValueError):
            applied_version = 0
        self.state.save({
            "last_synced_version": applied_version,
            "last_synced_sha": settings_sha(self.read_config()),
        })
        return {
            "status": "applied",
            "version": applied_version,
            "missing": self.reconcile(cloud),
        }

    def reconcile(self, cloud: Optional[Dict] = None) -> List[Dict]:
        report = self.health_report() or {}
        invalid = []
        for section in ("audio", "visual"):
            sub = report.get(section)
            if not isinstance(sub, dict):
                continue
            invalid += sub.get("invalid_config_refs", []) or []
        invalid += report.get("invalid_config_refs", []) or []
        manifest = {}
        if cloud and isinstance(cloud.get("config"), dict):
            manifest = cloud["config"].get("__resource_manifest__") or {}
        return plan_reconciliation(classify_missing_resources(invalid, manifest))


def execute_reconciliation(planned: List[Dict], handlers: Dict) -> List[Dict]:
    """按动作分发到处理器执行,逐项收集结果;处理器缺失=手动(skipped),异常=error。
handlers: {ACT_AUTO_RESTORE: fn(item), ACT_DOWNLOAD: fn, ACT_OPEN_LINK: fn}。纯编排,可测。"""
    results = []
    for item in planned or []:
        handler = (handlers or {}).get(item.get("action"))
        if handler is None:
            results.append({**item, "result": "skipped", "detail": "需手动处理"})
            continue
        try:
            detail = handler(item)
            results.append({**item, "result": "ok", "detail": detail})
        except Exception as exc:
            results.append({**item, "result": "error", "detail": str(exc)})
    return results


def make_default_reconcile_handlers():
    """生产用默认处理器(惰性导入,避免模块顶层依赖 Qt/资源)。"""
    def _auto_restore(item):
        from resource_manager import ResourceManager
        ResourceManager.copy_resources_to_appdata()
        return "已从内置资源重建"

    def _open_link(item):
        import webbrowser
        ref = item.get("ref")
        if ref:
            webbrowser.open(ref)
            return "已打开网盘链接"
        return "无可用链接,请手动获取"

    def _download(item):
        import webbrowser
        from service_urls import COMMUNITY_WEBSITE_URL
        ref = item.get("ref")
        url = f"{COMMUNITY_WEBSITE_URL}/resource.php?id={ref}" if ref else COMMUNITY_WEBSITE_URL
        webbrowser.open(url)
        return "已打开社区资源页"

    return {
        ACT_AUTO_RESTORE: _auto_restore,
        ACT_OPEN_LINK: _open_link,
        ACT_DOWNLOAD: _download,
    }


def build_default_controller(auth_client, session_store, *, provenance_path=None):
    """生产工厂:把真实 config / 会话 / 快照 / 体检 / 来源库 接进控制器(惰性导入)。"""
    import json
    import os
    from config import CONFIG_SCHEMA_VERSION, config, get_config_path
    from core.cloud.resource_provenance import ProvenanceStore
    from core.config_snapshot_manager import create_snapshot
    from core.resource_health import collect_resource_system_health

    cfg_dir = os.path.dirname(get_config_path())
    prov = ProvenanceStore(provenance_path or os.path.join(cfg_dir, "resource_provenance.json"))

    def read_cfg():
        config.save_config_now()
        with open(get_config_path(), "r", encoding="utf-8") as f:
            return json.load(f)

    def write_cfg(d):
        with open(get_config_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=4)

    def manifest_provider():
        return prov.all()

    return CloudConfigSyncController(
        auth_client=auth_client,
        token_provider=lambda: (session_store.load() or {}).get("token"),
        read_config=read_cfg, write_config=write_cfg,
        reload_config=config.load_config,
        make_snapshot=create_snapshot, health_report=collect_resource_system_health,
        state=CloudSyncState(os.path.join(cfg_dir, "cloud_sync_state.json")),
        client_schema=CONFIG_SCHEMA_VERSION,
        device_label=os.environ.get("COMPUTERNAME", "我的设备"),
        manifest_provider=manifest_provider,
    )
