"""Activate locally staged Windows x64 CPython 3.13 dependencies."""

import os
from pathlib import Path
import struct
import sys


DLL_DIRECTORIES = ("", "PySide6", "shiboken6", "pygame", "numpy.libs", "pywin32_system32", "win32")


def check_python() -> None:
    if sys.platform != "win32" or sys.version_info[:2] != (3, 13) or struct.calcsize("P") != 8:
        raise RuntimeError("The bundled third-party dependencies require Windows x64 CPython 3.13.")


def activate(vendor: Path) -> list:
    """Activate the staged vendor directory, retaining the returned DLL handles."""
    check_python()
    vendor = vendor.resolve()
    plugin_path = vendor / "PySide6" / "plugins"
    if not (plugin_path / "platforms" / "qwindows.dll").is_file():
        raise FileNotFoundError(f"Qt platform plugins are missing at {plugin_path}")
    sys.path[:0] = [str(vendor), str(vendor / "win32")]
    os.environ["QT_PLUGIN_PATH"] = str(plugin_path)
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugin_path / "platforms")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    return [os.add_dll_directory(str(vendor / name)) for name in DLL_DIRECTORIES]
