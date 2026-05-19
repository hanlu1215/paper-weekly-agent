"""将周报 Markdown 发布到飞书知识库，并返回文档链接。"""

import copy
import os
from pathlib import Path
from typing import Any

from feishu_client import FeishuAPIError, feishu_request, _env_str


def wiki_configured() -> bool:
    return bool(
        _env_str("FEISHU_APP_ID")
        and _env_str("FEISHU_APP_SECRET")
        and _env_str("FEISHU_WIKI_SPACE_ID")
    )


def _title_from_markdown(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _wiki_base_url() -> str:
    base = _env_str("FEISHU_WIKI_BASE_URL", "https://feishu.cn").rstrip("/")
    return base


def _wiki_document_url(node_token: str) -> str:
    return f"{_wiki_base_url()}/wiki/{node_token}"


def _create_wiki_docx_node(title: str) -> dict[str, Any]:
    space_id = _env_str("FEISHU_WIKI_SPACE_ID")
    body: dict[str, Any] = {
        "obj_type": "docx",
        "node_type": "origin",
        "title": title,
    }
    parent = _env_str("FEISHU_WIKI_PARENT_NODE_TOKEN")
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
            f"转换块数量 {len(descendants)} 超过单次插入上限 1000，请缩短周报内容。"
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
    """
    在知识库新建 docx 文档并写入 Markdown，返回 wiki 链接。
    """
    doc_title = title or "文献周报"
    node = _create_wiki_docx_node(doc_title)
    document_id = node["obj_token"]
    node_token = node["node_token"]

    convert_data = _convert_markdown_to_blocks(markdown)
    _insert_blocks(document_id, convert_data)

    return _wiki_document_url(node_token)


def publish_report_file_to_wiki(report_path: Path) -> tuple[str, str]:
    """发布本地周报文件，返回 (标题, wiki_url)。"""
    content = report_path.read_text(encoding="utf-8")
    title = _title_from_markdown(content, report_path.stem)
    url = publish_markdown_to_wiki(content, title=title)
    return title, url
