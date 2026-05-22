"""发布日报到飞书：默认写入知识库并推送文档链接；可回退为全文推送。"""

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

from feishu_client import FeishuAPIError
from feishu_wiki import publish_report_file_to_wiki, validate_wiki_config, wiki_configured
from notify_feishu import (
    extract_paper_titles_from_report,
    get_github_daily_reports_url,
    send_feishu_document_link,
    send_feishu_text_chunks,
)
from render_markdown import daily_report_path
from report_date import report_today

DEFAULT_REPORTS_DIR = Path("daily_reports")
DEFAULT_CHUNK_SIZE = 3500


def _date_from_report_filename(path: Path) -> date | None:
    match = re.match(r"(\d{4}-\d{2}-\d{2})-文献每日速递(?:-\d+)?\.md$", path.name)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def find_latest_report(reports_dir: Path = DEFAULT_REPORTS_DIR) -> Path | None:
    """优先当日（配置时区）速递，否则取文件名日期最新的一期。"""
    if not reports_dir.is_dir():
        return None

    today_path = daily_report_path(report_today())
    if today_path.is_file():
        return today_path

    reports = list(reports_dir.glob("*-文献每日速递*.md"))
    if not reports:
        return None

    dated: list[tuple[date, Path]] = []
    undated: list[Path] = []
    for path in reports:
        report_date = _date_from_report_filename(path)
        if report_date:
            dated.append((report_date, path))
        else:
            undated.append(path)

    if dated:
        return max(dated, key=lambda item: item[0])[1]

    return max(undated, key=lambda p: p.stat().st_mtime)


def _get_webhook_url() -> str | None:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")
    if not webhook_url or not str(webhook_url).strip():
        return None
    return str(webhook_url).strip()


def _resolve_notify_mode() -> str:
    mode = os.getenv("FEISHU_NOTIFY_MODE", "auto").strip().lower()
    if mode == "auto":
        return "wiki_link" if wiki_configured() else "markdown"
    if mode == "wiki_link" and not wiki_configured():
        validate_wiki_config()  # 抛出明确说明，避免 spaces//nodes 的 404
    return mode


def send_report_as_markdown(report_path: Path, chunk_size: int) -> None:
    webhook_url = _get_webhook_url()
    if not webhook_url:
        print("未配置 FEISHU_WEBHOOK_URL，跳过飞书推送。", file=sys.stderr)
        return

    report_text = report_path.read_text(encoding="utf-8")
    header = (
        f"📚 文献每日速递已更新\n"
        f"文件：{report_path.name}\n"
        f"{'=' * 40}\n\n"
    )
    send_feishu_text_chunks(webhook_url, header, report_text, chunk_size=chunk_size)
    print("飞书通知已发送（Markdown 全文模式）。")


def send_report_as_github_link(report_path: Path) -> None:
    """知识库不可用时，推送 GitHub daily_reports 链接与文献列表。"""
    webhook_url = _get_webhook_url()
    if not webhook_url:
        print("未配置 FEISHU_WEBHOOK_URL，跳过飞书推送。", file=sys.stderr)
        return

    archive_url = get_github_daily_reports_url()
    if not archive_url:
        raise FeishuAPIError("无法生成 GitHub daily_reports 链接（请配置 GITHUB_REPOSITORY）。")

    content = report_path.read_text(encoding="utf-8")
    paper_titles = extract_paper_titles_from_report(content)
    title = report_path.stem

    send_feishu_document_link(
        webhook_url,
        title=title,
        doc_url=archive_url,
        paper_titles=paper_titles,
        archive_url=archive_url,
    )
    print(f"飞书已推送 GitHub 日报链接：{archive_url}")


def send_report_as_wiki_link(report_path: Path) -> None:
    webhook_url = _get_webhook_url()
    if not webhook_url:
        print("未配置 FEISHU_WEBHOOK_URL，跳过群聊通知。", file=sys.stderr)
        return

    content = report_path.read_text(encoding="utf-8")
    paper_titles = extract_paper_titles_from_report(content)

    try:
        title, doc_url = publish_report_file_to_wiki(report_path)
    except FeishuAPIError as err:
        print(f"知识库写入失败，回退 GitHub 链接推送：{err}", file=sys.stderr)
        send_report_as_github_link(report_path)
        return

    send_feishu_document_link(
        webhook_url,
        title=title,
        doc_url=doc_url,
        paper_titles=paper_titles,
    )
    print(f"知识库文档已创建：{doc_url}")
    print("飞书群聊已发送文档链接。")


def send_report_file(report_path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
    if not report_path.is_file():
        raise FileNotFoundError(f"日报文件不存在：{report_path}")

    mode = _resolve_notify_mode()
    try:
        if mode == "wiki_link":
            send_report_as_wiki_link(report_path)
        elif mode == "markdown":
            send_report_as_markdown(report_path, chunk_size)
        else:
            raise ValueError(f"未知的 FEISHU_NOTIFY_MODE：{mode}")
    except FeishuAPIError as err:
        print(f"飞书推送失败，尝试 GitHub 链接回退：{err}", file=sys.stderr)
        send_report_as_github_link(report_path)


def main():
    load_dotenv()
    load_dotenv("config/deepseek.env", override=True)

    parser = argparse.ArgumentParser(description="发布日报到飞书（知识库链接或 Markdown 全文）")
    parser.add_argument(
        "report",
        nargs="?",
        type=Path,
        help="每日速递 .md 路径；省略则自动选取 daily_reports/ 下最新文件",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        dest="reports_dir",
        default=DEFAULT_REPORTS_DIR,
        help=f"自动查找目录（默认 {DEFAULT_REPORTS_DIR}）",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="Markdown 全文模式下的单条消息字符上限",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "wiki_link", "markdown"),
        help="推送模式，覆盖环境变量 FEISHU_NOTIFY_MODE",
    )
    args = parser.parse_args()

    if args.mode:
        os.environ["FEISHU_NOTIFY_MODE"] = args.mode

    report_path = args.report
    if report_path is None:
        report_path = find_latest_report(args.reports_dir)
        if report_path is None:
            print(f"在 {args.reports_dir} 下未找到 .md 日报，跳过飞书推送。", file=sys.stderr)
            sys.exit(0)

    try:
        send_report_file(report_path, chunk_size=args.chunk_size)
    except (requests.RequestException, ValueError, RuntimeError) as e:
        print(f"飞书推送失败：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
