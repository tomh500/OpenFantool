"""Root-level launch settings for the recovered source edition."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml


CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.yml"
OFFLINE_MESSAGE = "远端联网已阻断。修改 config.yml 后重启可恢复。"


@dataclass(frozen=True)
class SourceOptions:
    block_remote_network: bool
    replace_announcement: bool
    announcement_title: str
    announcement_text: str


@cache
def get_source_options() -> SourceOptions:
    try:
        values = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise RuntimeError(f"无法读取 {CONFIG_PATH}，请检查公告和联网设置。") from exc
    if not isinstance(values, dict):
        raise ValueError("config.yml 必须是由设置名和对应值组成的配置。")

    blocked = values.get("block_remote_network", True)
    replacement = values.get("replace_announcement", True)
    if type(blocked) is not bool or type(replacement) is not bool:
        raise ValueError("block_remote_network 和 replace_announcement 必须使用 true 或 false。")

    title = values.get("announcement_title", "帆派助手开放版")
    body = values.get("announcement_text", "")
    if not isinstance(title, str) or not isinstance(body, str):
        raise ValueError("公告标题和正文必须是文本。")
    if replacement and (not title.strip() or not body.strip()):
        raise ValueError("替换公告已启用，请在 config.yml 中填写公告标题和正文。")
    return SourceOptions(blocked, replacement, title.strip(), body)


def remote_network_blocked() -> bool:
    return get_source_options().block_remote_network
