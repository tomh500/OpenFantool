# Reconstructed from the earlier recovery and installed 2.3.0 PyArmor disassembly.
"""Runtime update policy loader and evaluator."""
from __future__ import annotations




import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.utils.logger import get_logger
from service_urls import CHANGELOG_API_URL, CLIENT_UPDATE_API_URL, OFFICIAL_WEBSITE_URL

_VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,31}$")
_NUMBER_PATTERN = re.compile(r"\d+")
_SESSION = None


@dataclass
class UpdatePolicy:
    latest_version: str = ""
    min_supported_version: str = ""
    disabled_versions: List[str] = field(default_factory=list)
    mandatory: bool = False
    release_date: str = ""
    published_at: str = ""
    notes: str = ""
    announcement_lines: List[str] = field(default_factory=list)
    download_links: List[Dict[str, str]] = field(default_factory=list)
    download_url: str = ""
    source: str = ""


@dataclass
class UpdateCheckResult:
    blocked: bool = False
    update_available: bool = False
    update_text: str = ""
    block_message: str = ""
    download_url: str = ""
    source: str = ""
    download_sha256: str = ""


def _sha256_for_url(policy: "UpdatePolicy", url: str) -> str:
    """从 download_links 里找与 url 匹配的 sha256（无则空串）。"""
    target = _clean_text(url)
    if not target:
        return ""
    for link in policy.download_links or []:
        if _clean_text(link.get("url")) == target:
            return _clean_text(link.get("sha256"))
    return ""


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_version(value: Any) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    if _VERSION_PATTERN.match(cleaned):
        return cleaned

    lowered = cleaned.lower().lstrip("v")
    if _VERSION_PATTERN.match(lowered):
        return lowered
    return ""


def _version_numbers(version: str) -> Tuple[int, ...]:
    normalized = normalize_version(version)
    if not normalized:
        return (0,)

    numbers = [int(number) for number in _NUMBER_PATTERN.findall(normalized)]
    if not numbers:
        return (0,)

    while len(numbers) > 1 and numbers[-1] == 0:
        numbers.pop()
    return tuple(numbers)


def compare_versions(left: str, right: str) -> int:
    left_numbers = _version_numbers(left)
    right_numbers = _version_numbers(right)
    length = max(len(left_numbers), len(right_numbers))

    for i in range(length):
        x = left_numbers[i] if i < len(left_numbers) else 0
        y = right_numbers[i] if i < len(right_numbers) else 0
        if x > y:
            return 1
        if x < y:
            return -1
    return 0


def _normalize_lines(lines: Any) -> List[str]:
    if isinstance(lines, list):
        raw_lines = lines
    elif isinstance(lines, str):
        raw_lines = lines.splitlines()
    else:
        return []

    result = []
    for line in raw_lines:
        cleaned = _clean_text(line)
        if cleaned:
            result.append(cleaned)
    return result


def _normalize_download_links(links: Any) -> List[Dict[str, str]]:
    if not isinstance(links, list):
        return []

    result = []
    for item in links:
        if not isinstance(item, dict):
            continue
        label = _clean_text(item.get("label"))
        url = _clean_text(item.get("url"))
        if not (label and url):
            continue
        link = {"label": label, "url": url}
        sha256 = _clean_text(item.get("sha256")).lower()
        if len(sha256) == 64 and all(char in "0123456789abcdef" for char in sha256):
            link["sha256"] = sha256
        result.append(link)
    return result


def _pick_download_url(download_links: List[Dict[str, str]], fallback: str = "") -> str:
    if fallback:
        return fallback
    if download_links:
        return _clean_text(download_links[0].get("url"))
    return ""


def _build_policy(data: Dict[str, Any], source: str) -> UpdatePolicy:
    latest_version = normalize_version(data.get("latest_version"))
    min_supported_version = normalize_version(data.get("min_supported_version"))

    disabled_versions = []
    raw_disabled = data.get("disabled_versions")
    if isinstance(raw_disabled, list):
        for item in raw_disabled:
            normalized = normalize_version(item)
            if normalized:
                disabled_versions.append(normalized)

    mandatory = bool(data.get("mandatory"))
    release_date = _clean_text(data.get("release_date"))
    published_at = _clean_text(data.get("published_at"))
    notes = _clean_text(data.get("notes"))

    announcement_lines = _normalize_lines(data.get("announcement_lines"))
    if not announcement_lines:
        announcement_lines = _normalize_lines(data.get("changelog_lines"))

    download_links = _normalize_download_links(data.get("download_links"))
    download_url = _pick_download_url(download_links, _clean_text(data.get("download_url")))

    return UpdatePolicy(
        latest_version=latest_version,
        min_supported_version=min_supported_version,
        disabled_versions=disabled_versions,
        mandatory=mandatory,
        release_date=release_date,
        published_at=published_at,
        notes=notes,
        announcement_lines=announcement_lines,
        download_links=download_links,
        download_url=download_url,
        source=source,
    )


def parse_client_update_payload(payload: Dict[str, Any]) -> UpdatePolicy:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return UpdatePolicy(source="client_update")
    return _build_policy(data, source="client_update")


def parse_get_changelog_payload(payload: Dict[str, Any]) -> UpdatePolicy:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return UpdatePolicy(source="get_changelog")

    current = data.get("current_release") if isinstance(data.get("current_release"), dict) else {}

    merged = {
        "latest_version": data.get("latest_version") or current.get("version"),
        "min_supported_version": data.get("min_supported_version"),
        "disabled_versions": data.get("disabled_versions"),
        "mandatory": data.get("mandatory") if data.get("mandatory") is not None else current.get("mandatory"),
        "release_date": current.get("release_date"),
        "published_at": current.get("published_at"),
        "notes": current.get("notes"),

        "announcement_lines": data.get("announcement_lines") or current.get("changelog_lines") or data.get("changelog"),
        "download_links": data.get("download_links") or current.get("download_links"),
        "download_url": data.get("download_url"),
    }
    return _build_policy(merged, source="get_changelog")


def _policy_to_cache(policy: UpdatePolicy) -> Dict[str, Any]:
    return {
        "latest_version": policy.latest_version,
        "min_supported_version": policy.min_supported_version,
        "disabled_versions": list(policy.disabled_versions),
        "mandatory": bool(policy.mandatory),
        "release_date": policy.release_date,
        "published_at": policy.published_at,
        "notes": policy.notes,
        "announcement_lines": list(policy.announcement_lines),
        "download_links": list(policy.download_links),
        "download_url": policy.download_url,
        "source": policy.source,
    }


def _policy_from_cache(data: Dict[str, Any]) -> UpdatePolicy:
    source = _clean_text(data.get("source")) or "cache"
    return _build_policy(data, source=source)


def is_version_disabled(current_version: str, disabled_versions: List[str]) -> bool:
    version = normalize_version(current_version)
    if not version:
        return False

    for raw in disabled_versions:
        disabled = normalize_version(raw)
        if not disabled:
            continue
        if disabled == version:
            return True
        if compare_versions(disabled, version) == 0:
            return True
    return False


def build_update_text(current_version: str, policy: UpdatePolicy) -> str:
    if policy.announcement_lines:
        return "\n".join(policy.announcement_lines[:18]).strip()

    if policy.notes:
        return policy.notes

    lines = [
        "检测到新版本",
        f"当前版本: v{current_version}",
        f"最新版本: v{policy.latest_version}",
    ]

    if policy.mandatory:
        lines.append("此更新为强制更新，建议立即升级。")

    if policy.notes:
        lines.extend(["", "更新说明:", policy.notes])

    return "\n".join(lines).strip()


def build_startup_announcement_text(current_version: str, policy: UpdatePolicy) -> str:
    if policy.announcement_lines:
        return "\n".join(policy.announcement_lines[:18]).strip()
    return ""


def build_block_message(current_version: str, policy: UpdatePolicy, reason: str) -> str:
    lines = [
        f"当前版本 v{current_version} {reason}",
    ]

    if policy.latest_version:
        lines.append(f"请升级到 v{policy.latest_version} 或更高版本后继续使用。")

    lines.append(f"官网地址: {OFFICIAL_WEBSITE_URL}")

    download_url = _clean_text(policy.download_url)
    if download_url and download_url != OFFICIAL_WEBSITE_URL:
        lines.append(f"备用下载: {download_url}")

    return "\n".join(lines).strip()


class UpdateRuntimeChecker:
    """Load update policy from server and evaluate current client version."""

    def __init__(
        self,
        primary_url: str = CLIENT_UPDATE_API_URL,
        fallback_url: str = CHANGELOG_API_URL,
        timeout: int = 8,
        max_cache_age_seconds: int = 604800,
        cache_path: Optional[str] = None,
        logger=None,
    ):
        self.primary_url = primary_url
        self.fallback_url = fallback_url
        self.timeout = timeout
        self.max_cache_age_seconds = max(0, int(max_cache_age_seconds))
        self.cache_path = cache_path or self._default_cache_path()
        self.logger = logger or get_logger("UpdateRuntimeChecker")
    @staticmethod
    def _default_cache_path() -> str:

        appdata = os.getenv("APPDATA")
        if appdata:
            base_dir = os.path.join(appdata, "FanTool")
        else:
            base_dir = os.path.join(os.path.expanduser("~"), ".fantool")
        return os.path.join(base_dir, "update_cache.json")

    def _fetch_json(self, url: str) -> Dict[str, Any]:
        global _SESSION
        from core.net.http_session import make_session

        headers = {
            "User-Agent": "FanTool-UpdateChecker/2.x",
            "Accept": "application/json",
        }
        if _SESSION is None:
            _SESSION = make_session()
        resp = _SESSION.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        text = resp.content.decode("utf-8-sig", errors="replace")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("invalid json payload")
        return data

    def _save_cache(self, policy: UpdatePolicy) -> None:
        try:
            cache_dir = os.path.dirname(self.cache_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)

            payload = {
                "cached_at": int(time.time()),
                "policy": _policy_to_cache(policy),
            }
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to write update cache: {e}")
        return None

    def _load_cache(self) -> Optional[UpdatePolicy]:
        try:
            if not os.path.exists(self.cache_path):
                return None

            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None

            if self.max_cache_age_seconds > 0:
                cached_at_raw = data.get("cached_at")
                cached_at = 0
                if isinstance(cached_at_raw, (int, float)):
                    cached_at = int(cached_at_raw)
                elif isinstance(cached_at_raw, str) and cached_at_raw.strip().isdigit():
                    cached_at = int(cached_at_raw.strip())
                if cached_at <= 0:
                    return None
                age = int(time.time()) - cached_at
                if age > self.max_cache_age_seconds:
                    self.logger.info("Update cache expired, ignore stale cache data")
                    return None

            policy_data = data.get("policy")
            if not isinstance(policy_data, dict):
                return None

            policy = _policy_from_cache(policy_data)
            policy.source = "cache"
            return policy
        except Exception as e:
            self.logger.warning(f"Failed to read update cache: {e}")
            return None

    def load_policy(self) -> UpdatePolicy:
        errors = []

        try:
            data = self._fetch_json(self.primary_url)
            policy = parse_client_update_payload(data)
            policy.source = self.primary_url
            self._save_cache(policy)
            return policy
        except Exception as e:
            errors.append(f"primary failed: {e}")


        try:
            data = self._fetch_json(self.fallback_url)
            policy = parse_get_changelog_payload(data)
            policy.source = self.fallback_url
            self._save_cache(policy)
            return policy
        except Exception as e:
            errors.append(f"fallback failed: {e}")
        cache = self._load_cache()
        if cache:
            return cache
        raise RuntimeError("; ".join(errors) if errors else "no update source available")


    def check(self, current_version: str) -> UpdateCheckResult:
        policy = self.load_policy()

        version = normalize_version(current_version) or _clean_text(current_version) or "unknown"
        has_update = bool(policy.latest_version) and compare_versions(policy.latest_version, version) > 0

        if is_version_disabled(version, policy.disabled_versions):
            return UpdateCheckResult(
                blocked=True,
                block_message=build_block_message(version, policy, "已被服务器禁用。"),
                download_url=policy.download_url,
                source=policy.source,
            )

        if policy.min_supported_version and compare_versions(version, policy.min_supported_version) < 0:
            return UpdateCheckResult(
                blocked=True,
                block_message=build_block_message(
                    version,
                    policy,
                    f"低于最低支持版本 v{policy.min_supported_version}。",
                ),
                download_url=policy.download_url,
                source=policy.source,
            )

        if policy.mandatory and has_update:
            return UpdateCheckResult(
                blocked=True,
                block_message=build_block_message(version, policy, "不是当前可用的最新强制版本。"),
                download_url=policy.download_url,
                source=policy.source,
            )

        if has_update:
            return UpdateCheckResult(
                update_available=True,
                update_text=build_update_text(version, policy),
                download_url=policy.download_url,
                download_sha256=_sha256_for_url(policy, policy.download_url),
                source=policy.source,
            )

        return UpdateCheckResult(
            update_text=build_startup_announcement_text(version, policy),
            download_url=policy.download_url,
            source=policy.source,
        )
