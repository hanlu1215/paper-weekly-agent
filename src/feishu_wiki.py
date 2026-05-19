"""将周报 Markdown 发布到飞书知识库，并返回文档链接。"""

import copy
import os
from pathlib import Path
from typing import Any

from feishu_client import FeishuAPIError, feishu_request, _env_str


def _normalize_space_id(raw: str) -> str:
    """从知识库空间 URL 提取 space_id（纯数字）。"""
    text = raw.strip()
    if not text:
        return ""
    if "/wiki/space/" in text:
        tail = text.split("/wiki/space/", 1)[1]
        return tail.split("/")[0].split("?")[0].strip()
    return text


def _extract_node_token(raw: str) -> str:
    """从知识库页面 URL（/wiki/{node_token}）或 token 字符串提取 node_token。"""
    text = raw.strip()
    if not text:
        return ""
    if "/wiki/" in text and "/wiki/space/" not in text:
        tail = text.split("/wiki/", 1)[1]
        return tail.split("/")[0].split("?")[0].strip()
    return text


def _resolve_space_id_via_node(node_token: str) -> str:
    """通过节点 token 调用飞书 API 查询所属 space_id。"""
    data = feishu_request(
        "GET",
        "/wiki/v2/spaces/get_node",
        params={"token": node_token},
    )
    node = data.get("node") or {}
    space_id = str(node.get("space_id") or "").strip()
    if not space_id:
        raise FeishuAPIError(
            f"无法从节点 {node_token[:8]}... 解析 space_id，请确认应用已加入该知识库。"
        )
    return space_id


def get_wiki_space_id() -> str:
    raw = _env_str("FEISHU_WIKI_SPACE_ID")
    if not raw:
        return ""

    direct = _normalize_space_id(raw)
    if direct.isdigit():
        return direct

    # 用户粘贴了页面链接（如 /wiki/CtA5wUUV2i...）时，用 API 反查 space_id
    node_token = _extract_node_token(raw)
    if node_token and _env_str("FEISHU_APP_ID") and _env_str("FEISHU_APP_SECRET"):
        return _resolve_space_id_via_node(node_token)

    return direct


def wiki_configured() -> bool:
    return bool(
        _env_str("FEISHU_APP_ID")
        and _env_str("FEISHU_APP_SECRET")
        and get_wiki_space_id()
    )


def validate_wiki_config() -> None:
    """配置不全时抛出明确错误（不泄露密钥）。"""
    missing = []
    if not _env_str("FEISHU_APP_ID"):
        missing.append("FEISHU_APP_ID")
    if not _env_str("FEISHU_APP_SECRET"):
        missing.append("FEISHU_APP_SECRET")
    if not get_wiki_space_id():
        missing.append("FEISHU_WIKI_SPACE_ID")

    if missing:
        raise FeishuAPIError(
            "飞书知识库配置不完整，缺少环境变量："
            + ", ".join(missing)
            + "。\n"
            "请在 GitHub → Settings → Secrets → Actions 添加 FEISHU_WIKI_SPACE_ID。\n"
            "获取方式（任选其一）：\n"
            "  1) 空间 URL：.../wiki/space/6704147935988285963/... → 填数字 space_id\n"
            "  2) 目录 URL：.../wiki/CtA5wUUV2i... → 可粘贴整段链接（需已配置 APP_ID/SECRET）\n"
            "  3) 将目录 node_token 填到 FEISHU_WIKI_PARENT_NODE_TOKEN 指定创建位置。"
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
    validate_wiki_config()
    space_id = get_wiki_space_id()
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
