import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

WECHAT_OPENAPI_BASE = "http://api.weixin.qq.com"


def health(_request):
    return JsonResponse({"ok": True, "service": "wechat-cloud-publisher"})


@csrf_exempt
def publish(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method_not_allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
        _verify_token(request, payload)
        article = _article_from_payload(payload)
        media_id = _publish_article(article, payload)
    except PublishError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception as exc:  # pragma: no cover - defensive for cloud logs
        return JsonResponse({"ok": False, "error": f"internal_error: {exc}"}, status=500)

    return JsonResponse({"ok": True, **media_id})


def _verify_token(request, payload: dict[str, Any]) -> None:
    expected = os.getenv("WECHAT_CLOUD_PUBLISH_TOKEN", "").strip()
    if not expected:
        raise PublishError("server_missing_publish_token")

    auth = request.headers.get("Authorization", "")
    bearer = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
    provided = bearer or str(payload.get("token") or "").strip()
    if provided != expected:
        provided_hint = "empty" if not provided else f"len={len(provided)}"
        expected_hint = f"len={len(expected)}"
        raise PublishError(f"invalid_publish_token provided={provided_hint} expected={expected_hint}")


def _article_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    required = ("title", "content")
    missing = [key for key in required if not str(payload.get(key) or "").strip()]
    if missing:
        raise PublishError(f"missing_fields: {', '.join(missing)}")

    thumb_media_id = str(payload.get("thumb_media_id") or "").strip()
    if not thumb_media_id:
        if not str(payload.get("cover_image_base64") or "").strip():
            raise PublishError("missing_fields: thumb_media_id or cover_image_base64")
        thumb_media_id = _upload_cover(payload)
    return {
        "thumb_media_id": thumb_media_id,
        "author": str(payload.get("author") or "Paper Weekly")[:16],
        "title": str(payload["title"])[:32],
        "content_source_url": str(payload.get("content_source_url") or "")[:1024],
        "content": str(payload["content"]),
        "digest": str(payload.get("digest") or ""),
        "show_cover_pic": 0,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }


def _publish_article(article: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    draft = _wechat_post_json("/cgi-bin/draft/add", {"articles": [article]})
    media_id = draft.get("media_id")
    if not media_id:
        raise PublishError("draft_add_missing_media_id")

    result = _wechat_post_json(
        "/cgi-bin/freepublish/submit",
        {"media_id": media_id},
    )
    publish_id = str(result.get("publish_id") or "")
    msg_data_id = str(result.get("msg_data_id") or "")
    return {"media_id": str(media_id), "publish_id": publish_id, "msg_id": msg_data_id}


def _upload_cover(payload: dict[str, Any]) -> str:
    try:
        image_bytes = base64.b64decode(str(payload["cover_image_base64"]), validate=True)
    except (ValueError, TypeError) as exc:
        raise PublishError("invalid_cover_image_base64") from exc

    filename = str(payload.get("cover_filename") or "cover.png")
    content_type = str(payload.get("cover_content_type") or "image/png")
    with tempfile.NamedTemporaryFile(prefix="wechat-cover-", suffix=Path(filename).suffix or ".png") as tmp:
        tmp.write(image_bytes)
        tmp.flush()
        data = _wechat_post_file(
            "/cgi-bin/material/add_material",
            params={"type": "image"},
            file_field="media",
            file_path=Path(tmp.name),
            filename=filename,
            content_type=content_type,
        )

    media_id = data.get("media_id")
    if not media_id:
        raise PublishError("add_material_missing_media_id")
    return str(media_id)


def _wechat_post_json(path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(_url(path), json=body, timeout=25)
    return _wechat_payload(response, path)


def _wechat_post_file(
    path: str,
    *,
    params: dict[str, str],
    file_field: str,
    file_path: Path,
    filename: str,
    content_type: str,
) -> dict[str, Any]:
    with file_path.open("rb") as handle:
        response = requests.post(
            _url(path, params),
            files={file_field: (filename, handle, content_type)},
            timeout=25,
        )
    return _wechat_payload(response, path)


def _url(path: str, params: dict[str, str] | None = None) -> str:
    query = dict(params or {})
    from_appid = os.getenv("WECHAT_CLOUD_FROM_APPID", "").strip()
    if from_appid:
        query["from_appid"] = from_appid
    query_string = ""
    if query:
        from urllib.parse import urlencode

        query_string = "?" + urlencode(query)
    return f"{WECHAT_OPENAPI_BASE}{path}{query_string}"


def _wechat_payload(response: requests.Response, path: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise PublishError(f"{path} returned non-json http={response.status_code}") from exc

    errcode = data.get("errcode", 0)
    if response.status_code >= 400 or errcode not in (0, None):
        seqid = response.headers.get("x-openapi-seqid", "")
        raise PublishError(
            f"{path} failed: http={response.status_code} errcode={errcode} "
            f"errmsg={data.get('errmsg', '')} x-openapi-seqid={seqid}"
        )
    return data


class PublishError(RuntimeError):
    pass
