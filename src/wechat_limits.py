"""微信公众号草稿/图文接口字段长度限制。"""

WECHAT_TITLE_MAX_CHARS = 32
WECHAT_AUTHOR_MAX_CHARS = 16
# 开放接口 draft/add 的 digest 实际更严，按字节计约 54（文档默认抓正文前 54 字）
WECHAT_DIGEST_MAX_CHARS = 54
WECHAT_DIGEST_MAX_BYTES = 54
WECHAT_CONTENT_SOURCE_URL_MAX_BYTES = 1024


def truncate_chars(text: str, max_chars: int) -> str:
    return text[:max_chars]


def truncate_digest(text: str) -> str:
    """摘要同时按字符与 UTF-8 字节截断，避免 errcode 45004。"""
    trimmed = truncate_chars(text.strip(), WECHAT_DIGEST_MAX_CHARS)
    return truncate_utf8_bytes(trimmed, WECHAT_DIGEST_MAX_BYTES)


def truncate_utf8_bytes(text: str, max_bytes: int) -> str:
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text
    cut = data[:max_bytes]
    while cut:
        try:
            return cut.decode("utf-8")
        except UnicodeDecodeError:
            cut = cut[:-1]
    return ""
