"""将日报 Markdown 转为微信公众号图文 HTML。"""

import html
import re

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_LINK_RE = re.compile(r"(https?://[^\s<]+)")


def markdown_to_wechat_html(markdown: str) -> str:
    sections: list[str] = [
        '<section style="font-size:16px;line-height:1.75;color:#222;">'
    ]
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            sections.append("</ul>")
            in_list = False

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            close_list()
            sections.append('<p style="margin:0 0 12px;"><br /></p>')
            continue

        if line == "---":
            close_list()
            sections.append('<hr style="border:none;border-top:1px solid #e5e5e5;margin:24px 0;" />')
            continue

        if line.startswith("# "):
            close_list()
            sections.append(
                '<h1 style="font-size:22px;line-height:1.4;margin:0 0 18px;font-weight:700;">'
                f"{_inline(line[2:])}</h1>"
            )
            continue

        if line.startswith("## "):
            close_list()
            sections.append(
                '<h2 style="font-size:19px;line-height:1.45;margin:28px 0 12px;font-weight:700;">'
                f"{_inline(_strip_number_prefix(line[3:]))}</h2>"
            )
            continue

        if line.startswith("### "):
            close_list()
            sections.append(
                '<h3 style="font-size:17px;line-height:1.5;margin:20px 0 10px;font-weight:700;">'
                f"{_inline(line[4:])}</h3>"
            )
            continue

        if line.startswith(">"):
            close_list()
            sections.append(
                '<blockquote style="margin:12px 0;padding:8px 12px;border-left:4px solid #576b95;'
                'background:#f7f7f7;color:#666;">'
                f"{_inline(line.lstrip('>').strip())}</blockquote>"
            )
            continue

        if line.startswith("- "):
            if not in_list:
                sections.append('<ul style="padding-left:1.2em;margin:8px 0 12px;">')
                in_list = True
            sections.append(f'<li style="margin:4px 0;">{_inline(line[2:])}</li>')
            continue

        close_list()
        sections.append(f'<p style="margin:0 0 12px;">{_inline(line)}</p>')

    close_list()
    sections.append("</section>")
    return "\n".join(sections)


def extract_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return _plain(stripped[2:])[:32]
    return fallback[:32]


def extract_digest(markdown: str, fallback: str = "今日文献每日速递") -> str:
    titles = re.findall(r"^## \d+\.\s+(.+?)\s*$", markdown, re.MULTILINE)
    if titles:
        digest = "；".join(_plain(title) for title in titles[:2])
        return digest
    for line in markdown.splitlines():
        stripped = _plain(line.strip())
        if stripped and not stripped.startswith("#") and stripped != "---":
            return stripped[:120]
    return fallback[:120]


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = _LINK_RE.sub(r'<a href="\1">\1</a>', escaped)
    return escaped


def _plain(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_number_prefix(text: str) -> str:
    return re.sub(r"^\d+\.\s*", "", text).strip()
