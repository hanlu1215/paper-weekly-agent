"""将每日速递自动群发到微信公众号。"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from markdown_to_wechat import extract_digest, extract_title, markdown_to_wechat_html
from wechat_mp_client import (
    WeChatMPError,
    get_access_token,
    mass_send_news_to_all,
    upload_image_material,
    upload_news,
    wechat_configured,
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
    explicit = os.getenv("WECHAT_MP_CONTENT_SOURCE_URL", "").strip()
    if explicit:
        return explicit

    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    branch = os.getenv("GITHUB_REPO_BRANCH", "main").strip() or "main"
    if repository and "/" in repository:
        return f"https://github.com/{repository}/blob/{branch}/{report_path.as_posix()}"
    return ""


def resolve_thumb_media_id(access_token: str) -> str:
    configured = os.getenv("WECHAT_MP_THUMB_MEDIA_ID", "").strip()
    if configured:
        return configured

    cover_path = Path(os.getenv("WECHAT_MP_COVER_IMAGE", "").strip() or DEFAULT_COVER_IMAGE)
    print(f"未配置 WECHAT_MP_THUMB_MEDIA_ID，自动上传封面图：{cover_path}", flush=True)
    return upload_image_material(access_token, cover_path)


def build_article(report_path: Path, thumb_media_id: str) -> dict:
    markdown = report_path.read_text(encoding="utf-8")
    title = os.getenv("WECHAT_MP_TITLE", "").strip() or extract_title(markdown, report_path.stem)
    digest = os.getenv("WECHAT_MP_DIGEST", "").strip() or extract_digest(markdown)
    author = os.getenv("WECHAT_MP_AUTHOR", "").strip() or "Paper Weekly Agent"

    return {
        "thumb_media_id": thumb_media_id,
        "author": author[:64],
        "title": title[:64],
        "content_source_url": github_report_url(report_path),
        "content": markdown_to_wechat_html(markdown),
        "digest": digest[:120],
        "show_cover_pic": 0,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }


def send_report_to_wechat(report_path: Path) -> None:
    if not report_path.is_file():
        raise FileNotFoundError(f"日报文件不存在：{report_path}")

    if not wechat_configured():
        print(
            "未完整配置 WECHAT_MP_APP_ID / WECHAT_MP_APP_SECRET，跳过公众号群发。",
            flush=True,
        )
        return

    token = get_access_token()
    thumb_media_id = resolve_thumb_media_id(token)
    article = build_article(report_path, thumb_media_id)
    print(f"正在上传微信公众号图文素材：{article['title']}", flush=True)
    media_id = upload_news(token, article)
    print("微信公众号图文素材上传成功，正在群发给全部用户...", flush=True)
    result = mass_send_news_to_all(token, media_id)
    msg_id = result.get("msg_id") or result.get("msg_data_id") or ""
    print(f"微信公众号群发已提交。msg_id={msg_id}", flush=True)


def main() -> int:
    load_dotenv()
    load_dotenv("config/deepseek.env", override=True)

    parser = argparse.ArgumentParser(description="将每日速递群发到微信公众号")
    parser.add_argument(
        "report",
        nargs="?",
        type=Path,
        help="每日速递 .md 路径；省略则自动选取 daily_reports/ 下最新文件",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help=f"自动查找目录（默认 {DEFAULT_REPORTS_DIR}）",
    )
    args = parser.parse_args()

    report_path = args.report or find_latest_report(args.reports_dir)
    if report_path is None:
        print(f"在 {args.reports_dir} 下未找到 .md 日报，跳过公众号群发。", file=sys.stderr)
        return 0

    try:
        send_report_to_wechat(report_path)
        return 0
    except (FileNotFoundError, WeChatMPError) as exc:
        print(f"微信公众号群发失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
