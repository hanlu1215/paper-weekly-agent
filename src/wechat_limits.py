"""微信公众号草稿/图文接口字段长度限制。"""

WECHAT_TITLE_MAX_CHARS = 32
WECHAT_AUTHOR_MAX_CHARS = 16
WECHAT_DIGEST_MAX_BYTES = 120
WECHAT_CONTENT_SOURCE_URL_MAX_BYTES = 1024


def truncate_chars(text: str, max_chars: int) -> str:
    return text[:max_chars]


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
