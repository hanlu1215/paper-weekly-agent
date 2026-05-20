"""微信公众号接口客户端：获取 token、上传图文素材、群发图文。"""

import os
from pathlib import Path
from typing import Any

import requests

WECHAT_API_BASE = "https://api.weixin.qq.com"


class WeChatMPError(RuntimeError):
    def __init__(self, message: str, *, errcode: int | None = None):
        super().__init__(message)
        self.errcode = errcode

    @property
    def is_ip_whitelist_error(self) -> bool:
        return self.errcode == 40164 or "invalid ip" in str(self).lower()


def _env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


def wechat_configured() -> bool:
    return bool(
        _env_str("WECHAT_MP_APP_ID")
        and _env_str("WECHAT_MP_APP_SECRET")
    )


def get_access_token() -> str:
    app_id = _env_str("WECHAT_MP_APP_ID")
    app_secret = _env_str("WECHAT_MP_APP_SECRET")
    if not app_id or not app_secret:
        raise WeChatMPError("未配置 WECHAT_MP_APP_ID / WECHAT_MP_APP_SECRET。")

    response = requests.get(
        f"{WECHAT_API_BASE}/cgi-bin/token",
        params={
            "grant_type": "client_credential",
            "appid": app_id,
            "secret": app_secret,
        },
        timeout=30,
    )
    payload = _json_or_error(response)
    if payload.get("errcode"):
        raise WeChatMPError(
            f"获取微信 access_token 失败：errcode={payload.get('errcode')} errmsg={payload.get('errmsg', '')}",
            errcode=payload.get("errcode"),
        )
    token = payload.get("access_token")
    if not token:
        raise WeChatMPError("获取微信 access_token 失败：响应中缺少 access_token。")
    return token


def upload_news(access_token: str, article: dict[str, Any]) -> str:
    payload = {"articles": [article]}
    data = _wechat_post(
        "/cgi-bin/media/uploadnews",
        access_token=access_token,
        json_body=payload,
    )
    media_id = data.get("media_id")
    if not media_id:
        raise WeChatMPError("上传微信图文素材失败：响应中缺少 media_id。")
    return media_id


def upload_image_material(access_token: str, image_path: Path) -> str:
    if not image_path.is_file():
        raise WeChatMPError(f"微信公众号封面图不存在：{image_path}")

    with image_path.open("rb") as image_file:
        response = requests.post(
            f"{WECHAT_API_BASE}/cgi-bin/material/add_material",
            params={"access_token": access_token, "type": "image"},
            files={"media": (image_path.name, image_file, "image/png")},
            timeout=60,
        )
    payload = _json_or_error(response)
    errcode = payload.get("errcode", 0)
    if errcode not in (0, None):
        raise WeChatMPError(
            f"上传微信封面图失败：errcode={errcode} errmsg={payload.get('errmsg', '')}",
            errcode=errcode,
        )
    media_id = payload.get("media_id")
    if not media_id:
        raise WeChatMPError("上传微信封面图失败：响应中缺少 media_id。")
    return media_id


def mass_send_news_to_all(access_token: str, media_id: str) -> dict[str, Any]:
    return _wechat_post(
        "/cgi-bin/message/mass/sendall",
        access_token=access_token,
        json_body={
            "filter": {"is_to_all": True},
            "mpnews": {"media_id": media_id},
            "msgtype": "mpnews",
            "send_ignore_reprint": 0,
        },
    )


def _wechat_post(path: str, *, access_token: str, json_body: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{WECHAT_API_BASE}{path}",
        params={"access_token": access_token},
        json=json_body,
        timeout=60,
    )
    payload = _json_or_error(response)
    errcode = payload.get("errcode", 0)
    if errcode not in (0, None):
        raise WeChatMPError(
            f"微信接口失败 {path}：errcode={errcode} errmsg={payload.get('errmsg', '')}",
            errcode=errcode,
        )
    return payload


def _json_or_error(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise WeChatMPError(f"微信接口返回非 JSON：HTTP {response.status_code}") from exc

    if response.status_code >= 400:
        raise WeChatMPError(
            f"微信接口 HTTP {response.status_code}：errcode={payload.get('errcode')} "
            f"errmsg={payload.get('errmsg', response.text[:200])}",
            errcode=payload.get("errcode"),
        )
    return payload
