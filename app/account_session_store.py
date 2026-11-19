# Reconstructed from the installed 2.3.0 PyArmor static disassembly.

import base64
import ctypes
import json
import os
import tempfile
from ctypes import wintypes

from config import get_app_data_dir
from core.io_validation import replace_with_retry


CRYPTPROTECT_UI_FORBIDDEN = 1
_APP_ENTROPY = b"FanTool.AccountSession.v1"



class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


_crypt32 = ctypes.windll.crypt32
_kernel32 = ctypes.windll.kernel32

_crypt32.CryptProtectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    wintypes.LPCWSTR,
    ctypes.POINTER(DATA_BLOB),
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB),
]
_crypt32.CryptProtectData.restype = wintypes.BOOL

_crypt32.CryptUnprotectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    ctypes.POINTER(wintypes.LPWSTR),
    ctypes.POINTER(DATA_BLOB),
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB),
]
_crypt32.CryptUnprotectData.restype = wintypes.BOOL

_kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
_kernel32.LocalFree.restype = wintypes.HLOCAL


class SessionStoreError(Exception):
    """Raised when the local account session cannot be read or written."""


def _bytes_to_blob(raw_bytes):
    if raw_bytes is None:
        raw_bytes = b""
    if not isinstance(raw_bytes, (bytes, bytearray)):
        raise TypeError("raw_bytes must be bytes")

    size = len(raw_bytes)
    if size == 0:
        return DATA_BLOB(0, None), None

    buffer = ctypes.create_string_buffer(bytes(raw_bytes), size)
    blob = DATA_BLOB(size, ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def _protect_bytes(raw_bytes, entropy=_APP_ENTROPY):
    source, source_buffer = _bytes_to_blob(raw_bytes)
    extra, extra_buffer = _bytes_to_blob(entropy) if entropy else (None, None)
    output = DATA_BLOB()
    if not _crypt32.CryptProtectData(
        ctypes.byref(source),
        "FanTool account session",
        ctypes.byref(extra) if extra is not None else None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output),
    ):
        raise SessionStoreError("无法加密本地账号会话。")

    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        if output.pbData:
            _kernel32.LocalFree(output.pbData)
        del source_buffer
        del extra_buffer


def _unprotect_bytes(raw_bytes, entropy=_APP_ENTROPY):
    source, source_buffer = _bytes_to_blob(raw_bytes)
    extra, extra_buffer = _bytes_to_blob(entropy) if entropy else (None, None)
    output = DATA_BLOB()
    description = wintypes.LPWSTR()
    if not _crypt32.CryptUnprotectData(
        ctypes.byref(source),
        ctypes.byref(description),
        ctypes.byref(extra) if extra is not None else None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output),
    ):
        raise SessionStoreError("无法解密本地账号会话。")

    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        if description:
            _kernel32.LocalFree(description)
        if output.pbData:
            _kernel32.LocalFree(output.pbData)
        del source_buffer


class SessionStore:
    def __init__(self, filename="account_session.json"):
        self.root_dir = get_app_data_dir()
        self.session_path = os.path.join(self.root_dir, filename)

    def load(self):
        if os.environ.get("FANPAI_NO_ACCOUNT_SESSION") == "1":
            return None
        if not os.path.exists(self.session_path):
            return None

        try:
            with open(self.session_path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, ValueError) as exc:
            raise SessionStoreError("无法读取已保存的账号会话。") from exc

        if not isinstance(data, dict):
            raise SessionStoreError("无法读取已保存的账号会话。")
        encoded = data.get("token")
        if not encoded:
            return None

        try:
            encrypted = base64.b64decode(encoded)
            try:
                token = _unprotect_bytes(encrypted).decode("utf-8")
            except SessionStoreError:
                token = _unprotect_bytes(encrypted, entropy=None).decode("utf-8")
        except Exception as exc:
            raise SessionStoreError("无法解析已保存的账号会话。") from exc

        return {
            "token": token,
            "remember": bool(data.get("remember", False)),
            "expires_at": int(data.get("expires_at") or 0),
            "user": data.get("user") or {},
            "saved_at": data.get("saved_at") or "",
        }

    def save(self, session_data):
        token = session_data.get("token")
        if not token:
            raise SessionStoreError("不能保存空账号 token。")
        os.makedirs(self.root_dir, exist_ok=True)
        encoded = base64.b64encode(_protect_bytes(token.encode("utf-8"))).decode("ascii")
        data = {
            "token": encoded,
            "remember": bool(session_data.get("remember", False)),
            "expires_at": int(session_data.get("expires_at") or 0),
            "saved_at": session_data.get("saved_at") or "",
            "user": session_data.get("user") or {},
        }

        temporary_path = None
        try:
            fd, temporary_path = tempfile.mkstemp(
                prefix="account_session_", suffix=".tmp", dir=self.root_dir, text=True,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=True, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            replace_with_retry(temporary_path, self.session_path)
        except OSError as exc:
            if temporary_path and os.path.exists(temporary_path):
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass
            raise SessionStoreError("无法写入已保存的账号会话。") from exc

    def clear(self):
        try:
            if os.path.exists(self.session_path):
                os.remove(self.session_path)
        except OSError as exc:
            raise SessionStoreError("无法清除已保存的账号会话。") from exc
        return None
