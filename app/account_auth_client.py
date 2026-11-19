# Reconstructed from the installed 2.3.0 PyArmor static disassembly.

import time

from service_urls import ACCOUNT_SERVICE_BASE_URL
from core.net.http_session import make_session


# The following class lines reproduce the Python 3.13 class metadata.


class AuthClientError(Exception):
    """Base error for account service requests."""


class AuthNetworkError(AuthClientError):
    """Raised when the account service cannot be reached."""


class AuthRequestError(AuthClientError):
    """Raised when the account service returns an unusable response."""

    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class AuthInvalidCredentials(AuthRequestError):
    """Raised when the user provides bad login credentials."""


class AuthSessionExpired(AuthRequestError):
    """Raised when a stored token is no longer valid."""


class AuthConflict(AuthRequestError):
    """配置推送与云端更新版本冲突(HTTP 409)。payload 含 server_version 等。"""


class FanToolAuthClient:
    def __init__(self, base_url=ACCOUNT_SERVICE_BASE_URL, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = None

    @property
    def session(self):
        """带重试/退避的 Session —— 首次真正发请求时才建。

UP-056：`__init__` 里直接 `make_session()` 会把 requests(约 200ms)
拽进构造路径。实测 `MainWindow.__init__` 第 158 行就 new 了一个本客户端，
于是**每次启动**都在窗口显示前付掉这 200ms，而绝大多数启动里用户
根本没碰账号功能。对象本身很轻，重的是它下面那条 HTTP 栈，延后即可。
"""
        if self._session is None:
            self._session = make_session()
            self._session.headers.update({
                "Accept": "application/json",
                "User-Agent": "FanToolDesktop/2.1",
            })
        return self._session

    @session.setter
    def session(self, value):
        """允许外部注入 Session（测试替身、或调用方自备的连接池）。

改成 property 之前这本来就是个普通属性，注入是既有用法，不能因为
加了惰性就把这条路堵死。
"""
        self._session = value

    def login(self, email, password, remember=False):
        data = self._request(
            "POST", "/api/login.php",
            payload={"email": email.strip(), "password": password, "remember": bool(remember)},
            invalid_credentials=True,
        )
        token = data.get("token")
        user = data.get("user") or {}
        expires_in = int(data.get("expires_in") or 0)
        if not token:
            raise AuthRequestError("账号服务没有返回有效 token。", payload=data)
        if expires_in <= 0:
            expires_in = 86400
        return {
            "token": token,
            "remember": bool(remember),
            "expires_in": expires_in,
            "expires_at": int(time.time()) + expires_in,
            "user": {
                "id": user.get("id"),
                "username": user.get("username") or "",
                "email": user.get("email") or email.strip(),
            },
        }

    def verify(self, token):
        return self._request("GET", "/api/verify.php", token=token, session_check=True)

    def refresh(self, token):
        """P3.1: 会话静默续期——用仍在有效期内的旧 token 换取新 token。

后端接口约定（/api/refresh.php，POST，Bearer token）：
  成功: {"status":"ok","token":"<新token>","expires_in":86400,"user":{...可选}}
  失败: 401 → AuthSessionExpired；其他错误 → AuthRequestError。
后端尚未部署该接口时（404），调用方应捕获 AuthRequestError 并静默放弃
——整体行为退回"到期重新登录"，与历史版本一致。
"""
        data = self._request("POST", "/api/refresh.php", token=token, session_check=True)
        new_token = data.get("token")
        if not new_token:
            raise AuthRequestError("续期接口没有返回新 token。", payload=data)
        expires_in = int(data.get("expires_in") or 0)
        if expires_in <= 0:
            expires_in = 86400
        return {
            "token": new_token,
            "expires_in": expires_in,
            "expires_at": int(time.time()) + expires_in,
            "user": data.get("user") or {},
        }

    def get_account_info(self, token):
        data = self._request("GET", "/api/get_account_info.php", token=token)
        return data.get("data") or {}

    def get_client_config(self, token):
        """取云端客户端配置。无记录返回 None;401→AuthSessionExpired;404/其它→AuthRequestError(调用方降级)。"""
        data = self._request("GET", "/api/get_client_config.php", token=token, session_check=True)
        return data.get("data")

    def put_client_config(self, token, *, config, schema_version, base_version, device_label, sha256):
        """上传云端配置(乐观并发)。409→AuthConflict(payload 带 server_version)。"""
        payload = {
            "config": config,
            "schema_version": int(schema_version),
            "base_version": base_version,
            "device_label": str(device_label or "")[:64],
            "sha256": str(sha256 or ""),
        }
        try:
            return self._request(
                "POST", "/api/update_client_config.php",
                token=token, payload=payload, session_check=True,
            )
        except AuthRequestError as exc:
            if getattr(exc, "status_code", None) == 409:
                conflict = AuthConflict(str(exc), exc.status_code, exc.payload)
                data = exc.payload.get("data") if isinstance(exc.payload, dict) else None
                conflict.server_version = (data or {}).get("server_version")
                raise conflict from exc
            raise

    def fetch_profile(self, token):
        verify_result = self.verify(token)
        profile = dict(verify_result.get("user") or {})
        try:
            account_info = self.get_account_info(token)
        except AuthRequestError:
            account_info = {}
        profile.update({key: value for key, value in account_info.items() if value not in (None, "")})
        return profile

    def _request(self, method, path, token=None, payload=None, invalid_credentials=False, session_check=False):
        import requests

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = self.session.request(
                method, f"{self.base_url}{path}", headers=headers, json=payload, timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AuthNetworkError(f"暂时无法连接 {ACCOUNT_SERVICE_BASE_URL}。") from exc

        data = self._decode_json(response)
        message = self._pick_message(data, response.status_code)
        if response.status_code == 401:
            raise AuthSessionExpired(message or "当前账号会话已失效。", response.status_code, data)
        if invalid_credentials and self._is_invalid_credentials(data):
            raise AuthInvalidCredentials(message or "邮箱或密码不正确。", response.status_code, data)
        if not response.ok:
            raise AuthRequestError(message or f"账号服务返回 HTTP {response.status_code}。", response.status_code, data)
        if session_check and isinstance(data, dict) and data.get("status") == "error":
            raise AuthSessionExpired(message or "当前账号会话已失效。", response.status_code, data)
        if isinstance(data, dict) and data.get("status") == "error":
            raise AuthRequestError(message or "账号服务请求失败。", response.status_code, data)
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _decode_json(response):
        try:
            return response.json()
        except ValueError as exc:
            raise AuthRequestError("账号服务返回了无效的 JSON 数据。", response.status_code, None) from exc

    @staticmethod
    def _pick_message(data, status_code):
        if isinstance(data, dict):
            message = data.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        if status_code == 401:
            return "当前账号会话已失效。"
        return ""

    @staticmethod
    def _is_invalid_credentials(data):
        if not isinstance(data, dict):
            return False
        message = str(data.get("message") or "").lower()
        return any(word in message for word in (
            "invalid email or password",
            "incorrect email or password",
            "邮箱或密码不正确",
            "邮箱或密码错误",
            "密码错误",
        ))
