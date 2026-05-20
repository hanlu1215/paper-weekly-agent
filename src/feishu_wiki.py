"""将日报 Markdown 发布到飞书知识库，并返回文档链接。"""

import copy
import os
import re
from pathlib import Path
from typing import Any

from feishu_client import FeishuAPIError, feishu_request, _env_str

_SPACE_ID_RE = re.compile(r"^\d{10,25}$")


def _normalize_space_id(raw: str) -> str:
    """从知识库 URL 提取 space_id（纯数字）。"""
    text = raw.strip()
    if not text:
        return ""

    for marker in ("/wiki/space/", "/wiki/settings/"):
        if marker in text:
            tail = text.split(marker, 1)[1]
            candidate = tail.split("/")[0].split("?")[0].strip()
            if _SPACE_ID_RE.match(candidate):
                return candidate

    if _SPACE_ID_RE.match(text):
        return text

    return ""


def _extract_node_token(raw: str) -> str:
    """从 /wiki/{node_token} 链接或 token 字符串提取 node_token。"""
    text = raw.strip()
    if not text:
        return ""
    if "/wiki/" in text and "/wiki/space/" not in text and "/wiki/settings/" not in text:
        tail = text.split("/wiki/", 1)[1]
        return tail.split("/")[0].split("?")[0].strip()
    if _SPACE_ID_RE.match(text):
        return ""
    return text


def _resolve_space_id_via_node(node_token: str) -> str:
    data = feishu_request(
        "GET",
        "/wiki/v2/spaces/get_node",
        params={"token": node_token},
    )
    node = data.get("node") or {}
    space_id = str(node.get("space_id") or "").strip()
    if not _SPACE_ID_RE.match(space_id):
        raise FeishuAPIError(
            f"节点 {node_token[:12]}... 返回的 space_id 无效，请确认应用已加入该知识库。"
        )
    return space_id


def _verify_space_exists(space_id: str) -> None:
    feishu_request("GET", f"/wiki/v2/spaces/{space_id}")


def get_parent_node_token() -> str:
    raw = _env_str("FEISHU_WIKI_PARENT_NODE_TOKEN")
    if not raw:
        return ""
    return _extract_node_token(raw) or raw


def get_wiki_space_id() -> str:
    """解析并校验 space_id（必须是纯数字，不能误用 node_token）。"""
    candidates: list[str] = []

    for key in ("FEISHU_WIKI_SPACE_ID",):
        raw = _env_str(key)
        if not raw:
            continue
        numeric = _normalize_space_id(raw)
        if numeric:
            candidates.append(numeric)
            continue
        node_token = _extract_node_token(raw)
        if node_token:
            candidates.append(f"node:{node_token}")

    parent = get_parent_node_token()
    if parent:
        candidates.append(f"node:{parent}")

    if not candidates:
        return ""

    last_error = FeishuAPIError("未找到可用的 space_id 配置")

    for item in candidates:
        if item.startswith("node:"):
            if not (_env_str("FEISHU_APP_ID") and _env_str("FEISHU_APP_SECRET")):
                continue
            space_id = _resolve_space_id_via_node(item[5:])
        else:
            space_id = item

        try:
            _verify_space_exists(space_id)
            return space_id
        except FeishuAPIError as err:
            last_error = err
            continue

    raise FeishuAPIError(
        "无法解析有效的 FEISHU_WIKI_SPACE_ID。\n"
        f"最后一次错误：{last_error}\n"
        "请任选一种配置方式：\n"
        "  1) 知识库设置页 URL：.../wiki/settings/数字/ → Secret 只填数字\n"
        "  2) 目录页 URL：.../wiki/CtA5wUUV2i... → 粘贴整段链接（需 APP_ID/SECRET）\n"
        "  3) FEISHU_WIKI_PARENT_NODE_TOKEN 填目录 node_token，SPACE_ID 可留空由程序反查\n"
        "注意：不要把 node_token 当成 space_id 直接填数字以外的字符串。"
    )


def wiki_configured() -> bool:
    try:
        return bool(
            _env_str("FEISHU_APP_ID")
            and _env_str("FEISHU_APP_SECRET")
            and get_wiki_space_id()
        )
    except FeishuAPIError:
        return False


def validate_wiki_config() -> None:
    missing = []
    if not _env_str("FEISHU_APP_ID"):
        missing.append("FEISHU_APP_ID")
    if not _env_str("FEISHU_APP_SECRET"):
        missing.append("FEISHU_APP_SECRET")
    if not (_env_str("FEISHU_WIKI_SPACE_ID") or get_parent_node_token()):
        missing.append("FEISHU_WIKI_SPACE_ID 或 FEISHU_WIKI_PARENT_NODE_TOKEN")

    if missing:
        raise FeishuAPIError(
            "飞书知识库配置不完整，缺少："
            + ", ".join(missing)
        )

    get_wiki_space_id()


def _title_from_markdown(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _wiki_base_url() -> str:
    return _env_str("FEISHU_WIKI_BASE_URL", "https://feishu.cn").rstrip("/")


def _wiki_document_url(node_token: str) -> str:
    return f"{_wiki_base_url()}/wiki/{node_token}"


def _create_wiki_docx_node(title: str) -> dict[str, Any]:
    validate_wiki_config()
    space_id = get_wiki_space_id()
    body: dict[str, Any] = {
        "obj_type": "docx",
        "node_type": "origin",
        "title": title,
    }
    parent = get_parent_node_token()
    if parent:
        body["parent_node_token"] = parent

    data = feishu_request("POST", f"/wiki/v2/spaces/{space_id}/nodes", json_body=body)
    node = data.get("node") or {}
    if not node.get("obj_token") or not node.get("node_token"):
        raise FeishuAPIError("创建知识库节点成功但未返回 obj_token / node_token。")
    return node


def _sanitize_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = copy.deepcopy(blocks)

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            obj.pop("merge_info", None)
            for value in obj.values():
                _walk(value)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(cleaned)
    return cleaned


def _convert_markdown_to_blocks(markdown: str) -> dict[str, Any]:
    return feishu_request(
        "POST",
        "/docx/v1/documents/blocks/convert",
        json_body={"content_type": "markdown", "content": markdown},
    )


def _insert_blocks(document_id: str, convert_data: dict[str, Any]) -> None:
    first_level_ids = convert_data.get("first_level_block_ids") or []
    blocks = convert_data.get("blocks") or []
    if not first_level_ids or not blocks:
        raise FeishuAPIError("Markdown 转换结果为空，无法写入知识库文档。")

    descendants = _sanitize_blocks(blocks)
    if len(descendants) > 1000:
        raise FeishuAPIError(
            f"转换块数量 {len(descendants)} 超过单次插入上限 1000，请缩短日报内容。"
        )

    feishu_request(
        "POST",
        f"/docx/v1/documents/{document_id}/blocks/{document_id}/descendant",
        params={"document_revision_id": -1},
        json_body={
            "index": 0,
            "children_id": first_level_ids,
            "descendants": descendants,
        },
    )


def publish_markdown_to_wiki(markdown: str, *, title: str | None = None) -> str:
    doc_title = title or "文献每日速递"
    node = _create_wiki_docx_node(doc_title)
    document_id = node["obj_token"]
    node_token = node["node_token"]

    convert_data = _convert_markdown_to_blocks(markdown)
    _insert_blocks(document_id, convert_data)

    return _wiki_document_url(node_token)


def publish_report_file_to_wiki(report_path: Path) -> tuple[str, str]:
    content = report_path.read_text(encoding="utf-8")
    title = _title_from_markdown(content, report_path.stem)
    url = publish_markdown_to_wiki(content, title=title)
    return title, url
