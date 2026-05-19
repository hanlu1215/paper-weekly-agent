"""发布周报到飞书：默认写入知识库并推送文档链接；可回退为全文推送。"""

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from feishu_wiki import publish_report_file_to_wiki, validate_wiki_config, wiki_configured
from notify_feishu import send_feishu_document_link, send_feishu_text_chunks

DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_CHUNK_SIZE = 3500


def find_latest_report(output_dir: Path) -> Path | None:
    today_name = f"{datetime.date.today().isoformat()}-paper-daily.md"
    today_path = output_dir / today_name
    if today_path.is_file():
        return today_path
    reports = sorted(output_dir.glob("*-paper-daily.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if reports:
        return reports[0]
    reports = sorted(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


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


def _count_papers_in_report(content: str) -> int | None:
    match = re.search(r"本次共筛选出\s*(\d+)\s*篇", content)
    if match:
        return int(match.group(1))
    if "本次未检索到符合关键词的论文" in content:
        return 0
    return None


def send_report_as_markdown(report_path: Path, chunk_size: int) -> None:
    webhook_url = _get_webhook_url()
    if not webhook_url:
        print("未配置 FEISHU_WEBHOOK_URL，跳过飞书推送。", file=sys.stderr)
        return

    report_text = report_path.read_text(encoding="utf-8")
    header = (
        f"📚 文献周报已更新\n"
        f"文件：{report_path.name}\n"
        f"{'=' * 40}\n\n"
    )
    send_feishu_text_chunks(webhook_url, header, report_text, chunk_size=chunk_size)
    print("飞书通知已发送（Markdown 全文模式）。")


def send_report_as_wiki_link(report_path: Path) -> None:
    webhook_url = _get_webhook_url()
    if not webhook_url:
        print("未配置 FEISHU_WEBHOOK_URL，跳过群聊通知。", file=sys.stderr)
        return

    title, doc_url = publish_report_file_to_wiki(report_path)
    content = report_path.read_text(encoding="utf-8")
    paper_count = _count_papers_in_report(content)

    send_feishu_document_link(
        webhook_url,
        title=title,
        doc_url=doc_url,
        paper_count=paper_count,
        report_name=report_path.name,
    )
    print(f"知识库文档已创建：{doc_url}")
    print("飞书群聊已发送文档链接。")


def send_report_file(report_path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
    if not report_path.is_file():
        raise FileNotFoundError(f"周报文件不存在：{report_path}")

    mode = _resolve_notify_mode()
    if mode == "wiki_link":
        send_report_as_wiki_link(report_path)
    elif mode == "markdown":
        send_report_as_markdown(report_path, chunk_size)
    else:
        raise ValueError(f"未知的 FEISHU_NOTIFY_MODE：{mode}")


def main():
    load_dotenv()
    load_dotenv("config/deepseek.env", override=True)

    parser = argparse.ArgumentParser(description="发布周报到飞书（知识库链接或 Markdown 全文）")
    parser.add_argument(
        "report",
        nargs="?",
        type=Path,
        help="周报 .md 路径；省略则自动选取 output/ 下最新文件",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"自动查找目录（默认 {DEFAULT_OUTPUT_DIR}）",
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
        report_path = find_latest_report(args.output_dir)
        if report_path is None:
            print(f"在 {args.output_dir} 下未找到 .md 周报，跳过飞书推送。", file=sys.stderr)
            sys.exit(0)

    try:
        send_report_file(report_path, chunk_size=args.chunk_size)
    except (requests.RequestException, ValueError, RuntimeError) as e:
        print(f"飞书推送失败：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
