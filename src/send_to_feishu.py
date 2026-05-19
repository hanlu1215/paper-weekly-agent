"""通过飞书群机器人 Webhook 发送周报 Markdown（支持分段，不打印密钥）。"""

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from notify_feishu import send_feishu_text_chunks

DEFAULT_OUTPUT_DIR = Path("output")
# 飞书 text 消息建议单条不超过约 4k 字符，留余量
DEFAULT_CHUNK_SIZE = 3500


def find_latest_report(output_dir: Path) -> Path | None:
    reports = sorted(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def send_report_file(report_path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        print("未配置 FEISHU_WEBHOOK_URL，跳过飞书推送。", file=sys.stderr)
        return

    if not report_path.is_file():
        raise FileNotFoundError(f"周报文件不存在：{report_path}")

    report_text = report_path.read_text(encoding="utf-8")
    header = (
        f"📚 文献周报已更新\n"
        f"文件：{report_path.name}\n"
        f"{'=' * 40}\n\n"
    )
    send_feishu_text_chunks(webhook_url, header, report_text, chunk_size=chunk_size)
    print("飞书通知已发送。")


def main():
    load_dotenv()
    load_dotenv("config/deepseek.env", override=True)

    parser = argparse.ArgumentParser(description="将周报 Markdown 推送到飞书群")
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
        help="单条消息最大字符数（默认 3500）",
    )
    args = parser.parse_args()

    report_path = args.report
    if report_path is None:
        report_path = find_latest_report(args.output_dir)
        if report_path is None:
            print(f"在 {args.output_dir} 下未找到 .md 周报，跳过飞书推送。", file=sys.stderr)
            sys.exit(0)

    try:
        send_report_file(report_path, chunk_size=args.chunk_size)
    except requests.RequestException as e:
        print(f"飞书推送失败：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
