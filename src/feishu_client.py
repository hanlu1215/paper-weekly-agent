"""飞书开放平台 API 客户端（tenant_access_token，不记录密钥）。"""

import os
import time
from typing import Any

import requests

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
_TOKEN_CACHE: dict[str, Any] = {"token": "", "expire_at": 0.0}


class FeishuAPIError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None, response: requests.Response | None = None):
        super().__init__(message)
        self.code = code
        self.response = response


def _env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


def get_tenant_access_token() -> str:
    app_id = _env_str("FEISHU_APP_ID")
    app_secret = _env_str("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise FeishuAPIError("未配置 FEISHU_APP_ID / FEISHU_APP_SECRET，无法调用知识库 API。")

    now = time.time()
    if _TOKEN_CACHE["token"] and _TOKEN_CACHE["expire_at"] > now + 60:
        return _TOKEN_CACHE["token"]

    response = requests.post(
        f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code >= 400 or payload.get("code") not in (None, 0):
        raise FeishuAPIError(
            "获取 tenant_access_token 失败："
            f"HTTP {response.status_code} code={payload.get('code')} msg={payload.get('msg', '')[:200]}"
        )

    token = payload["tenant_access_token"]
    expire = int(payload.get("expire", 7200))
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expire_at"] = now + expire
    return token


def feishu_request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    token = get_tenant_access_token()
    url = f"{FEISHU_API_BASE}{path}"
    response = requests.request(
        method,
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        json=json_body,
        timeout=90,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code >= 400:
        raise FeishuAPIError(
            f"飞书 HTTP {response.status_code} {method} {path}："
            f"code={payload.get('code')} msg={payload.get('msg', response.text[:200])}",
            code=payload.get("code"),
            response=response,
        )

    if payload.get("code") != 0:
        raise FeishuAPIError(
            f"飞书 API 失败 {method} {path}：code={payload.get('code')} msg={payload.get('msg', '')[:300]}",
            code=payload.get("code"),
            response=response,
        )
    return payload.get("data") or {}
