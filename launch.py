"""Start the recovered FanTool source with its bundled Windows runtime."""

import multiprocessing
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
_dll_handles = []


def prepare_runtime() -> Path:
    """Prepare imports and isolate the recovered edition's saved data."""
    global _dll_handles
    if _dll_handles:
        return APP

    sys.path.insert(0, str(ROOT))
    from vendor_runtime import activate

    _dll_handles = activate(ROOT / "vendor")
    sys.path.insert(0, str(APP))
    os.chdir(APP)

    selected = os.environ.get("FANPAI_SOURCE_PROFILE")
    if selected:
        profile = Path(selected).expanduser().resolve()
    else:
        appdata = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        profile = appdata / "FanTool-Source-2.3.0"

    local = profile / "Local"
    roaming = profile / "Roaming"
    for folder in (local, roaming):
        folder.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        FANPAI_SOURCE_PROFILE=str(profile),
        LOCALAPPDATA=str(local),
        APPDATA=str(roaming),
        FANPAI_CONFIG_DIR=str(local / "FanTool"),
        FANPAI_LOG_DIR=str(local / "FanTool" / "logs"),
    )
    return APP


def main() -> int:
    prepare_runtime()
    from core.net.offline import activate_remote_policy
    from core.utils import autostart

    activate_remote_policy()
    # Give the source edition its own Windows startup entry.
    autostart._VALUE_NAME = "FanTool帆派助手开放版 源码版"
    from main_widget import main as app_main

    return app_main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
elif __name__ == "__mp_main__":
    prepare_runtime()
    from core.net.offline import activate_remote_policy

    activate_remote_policy()
