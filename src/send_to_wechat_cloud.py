"""将每日速递发送到微信云托管中转服务。"""

import argparse
import base64
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from markdown_to_wechat import extract_digest, extract_title, markdown_to_wechat_html
from wechat_cover import compress_cover_image
from wechat_limits import (
    WECHAT_AUTHOR_MAX_CHARS,
    WECHAT_CONTENT_SOURCE_URL_MAX_BYTES,
    WECHAT_TITLE_MAX_CHARS,
    truncate_chars,
    truncate_digest,
    truncate_utf8_bytes,
)

DEFAULT_REPORTS_DIR = Path("daily_reports")
DEFAULT_COVER_IMAGE = Path("02.png")


def find_latest_report(reports_dir: Path = DEFAULT_REPORTS_DIR) -> Path | None:
    if not reports_dir.is_dir():
        return None
    reports = sorted(
        reports_dir.glob("*-文献每日速递*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return reports[0] if reports else None


def github_report_url(report_path: Path) -> str:
    explicit = os.getenv("WECHAT_CLOUD_CONTENT_SOURCE_URL", "").strip()
    if explicit:
        return explicit

    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    branch = os.getenv("GITHUB_REPO_BRANCH", "main").strip() or "main"
    if repository and "/" in repository:
        return f"https://github.com/{repository}/blob/{branch}/{report_path.as_posix()}"
    return ""


def build_payload(report_path: Path) -> dict:
    markdown = report_path.read_text(encoding="utf-8")
    title = os.getenv("WECHAT_CLOUD_TITLE", "").strip() or extract_title(markdown, report_path.stem)
    digest = os.getenv("WECHAT_CLOUD_DIGEST", "").strip() or extract_digest(markdown)
    author = os.getenv("WECHAT_CLOUD_AUTHOR", "").strip() or "Paper Weekly"

    source_url = truncate_utf8_bytes(
        github_report_url(report_path),
        WECHAT_CONTENT_SOURCE_URL_MAX_BYTES,
    )
    payload: dict = {
        "title": truncate_chars(title, WECHAT_TITLE_MAX_CHARS),
        "digest": truncate_digest(digest),
        "author": truncate_chars(author, WECHAT_AUTHOR_MAX_CHARS),
        "content": markdown_to_wechat_html(markdown),
        "content_source_url": source_url,
    }

    thumb_media_id = os.getenv("WECHAT_CLOUD_THUMB_MEDIA_ID", "").strip()
    if thumb_media_id:
        payload["thumb_media_id"] = thumb_media_id
        return payload

    cover_path = Path(os.getenv("WECHAT_CLOUD_COVER_IMAGE", "").strip() or DEFAULT_COVER_IMAGE)
    if not cover_path.is_file():
        raise FileNotFoundError(f"公众号封面图不存在：{cover_path}")

    cover_bytes, cover_name, cover_type = compress_cover_image(cover_path)
    payload.update(
        {
            "cover_filename": cover_name,
            "cover_content_type": cover_type,
            "cover_image_base64": base64.b64encode(cover_bytes).decode("ascii"),
        }
    )
    return payload


def publish_to_wechat_cloud(report_path: Path) -> None:
    url = os.getenv("WECHAT_CLOUD_PUBLISH_URL", "").strip()
    token = os.getenv("WECHAT_CLOUD_PUBLISH_TOKEN", "").strip()
    if not url or not token:
        print("未配置 WECHAT_CLOUD_PUBLISH_URL / WECHAT_CLOUD_PUBLISH_TOKEN，跳过公众号云托管群发。")
        return

    payload = build_payload(report_path)
    payload["token"] = token
    cover_kb = len(payload.get("cover_image_base64", "")) // 1024
    content_kb = len(payload.get("content", "")) // 1024
    print(
        f"正在发送公众号文章到微信云托管：{payload['title']}"
        f"（正文约 {content_kb}KB，封面约 {cover_kb}KB）",
        flush=True,
    )
    timeout = float(os.getenv("WECHAT_CLOUD_HTTP_TIMEOUT", "180"))
    response = requests.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=(30, timeout),
    )
    try:
        data = response.json()
    except ValueError:
        data = {"text": response.text[:500]}

    if response.status_code >= 400 or not data.get("ok", False):
        raise RuntimeError(f"微信云托管发布失败：HTTP {response.status_code} {data}")

    print(
        "微信公众号图文推文已提交发布（草稿→发表）。"
        f" media_id={data.get('media_id', '')}"
        f" publish_id={data.get('publish_id', '')}"
        f" msg_id={data.get('msg_id', '')}",
        flush=True,
    )
    print(
        "请在微信公众平台 → 内容与互动 → 发表记录 查看进度；"
        "成功后会在公众号主页以图文推文形式展示，关注者可在订阅号消息里看到。",
        flush=True,
    )


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"


def main() -> int:
    load_dotenv()
    load_dotenv("config/deepseek.env", override=True)

    parser = argparse.ArgumentParser(description="将每日速递发送到微信云托管公众号中转服务")
    parser.add_argument("report", nargs="?", type=Path, help="每日速递 .md 路径")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    args = parser.parse_args()

    report_path = args.report or find_latest_report(args.reports_dir)
    if report_path is None:
        print(f"在 {args.reports_dir} 下未找到 .md 日报，跳过公众号云托管群发。", file=sys.stderr)
        return 0

    try:
        publish_to_wechat_cloud(report_path)
        return 0
    except (FileNotFoundError, RuntimeError, requests.RequestException) as exc:
        print(f"公众号云托管群发失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
