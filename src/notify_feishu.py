"""发布日报到飞书群机器人 Webhook。"""

import argparse
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


def _post_text(webhook_url: str, text: str) -> requests.Response:
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    return requests.post(webhook_url, json=payload, timeout=30)


def send_feishu_webhook_text(webhook_url: str, text: str) -> None:
    """向群机器人 Webhook 发送单条文本（不打印 webhook）。"""
    response = _post_text(webhook_url, text)
    if response.status_code != 200:
        raise requests.HTTPError(
            f"飞书返回 HTTP {response.status_code}: {response.text[:200]}",
            response=response,
        )
    try:
        data = response.json()
    except ValueError:
        data = {}
    if isinstance(data, dict) and data.get("code") not in (None, 0):
        raise requests.HTTPError(
            f"飞书 API 错误 code={data.get('code')} msg={data.get('msg', '')[:200]}",
            response=response,
        )


def get_github_daily_reports_url() -> str | None:
    """GitHub 仓库 daily_reports/ 目录链接（Actions 自动识别 GITHUB_REPOSITORY）。"""
    branch = os.getenv("GITHUB_REPO_BRANCH", "main").strip() or "main"
    explicit = os.getenv("GITHUB_REPO_URL", "").strip().rstrip("/")
    if explicit:
        return f"{explicit}/tree/{branch}/daily_reports"

    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    if repository and "/" in repository:
        return f"https://github.com/{repository}/tree/{branch}/daily_reports"

    return None


def get_github_report_file_url(report_path: Path) -> str | None:
    """GitHub 仓库内单个日报文件链接。"""
    branch = os.getenv("GITHUB_REPO_BRANCH", "main").strip() or "main"
    explicit = os.getenv("GITHUB_REPO_URL", "").strip().rstrip("/")
    report_name = report_path.name
    if explicit:
        return f"{explicit}/blob/{branch}/daily_reports/{report_name}"

    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    if repository and "/" in repository:
        return f"https://github.com/{repository}/blob/{branch}/daily_reports/{report_name}"

    return None


def send_report_notice(report_path: Path, paper_count: int) -> None:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")

    if not webhook_url or not str(webhook_url).strip():
        print("未配置 FEISHU_WEBHOOK_URL，跳过飞书推送。")
        return

    lines = [
        "本次文献每日速递已生成。",
        f"共筛选论文：{paper_count} 篇",
        f"文件：{report_path}",
    ]

    file_url = get_github_report_file_url(report_path)
    if file_url:
        lines.append(f"HTML 文件：{file_url}")

    archive_url = get_github_daily_reports_url()
    if archive_url:
        lines.append(f"历史归档：{archive_url}")

    send_feishu_webhook_text(webhook_url, "\n".join(lines))
    print("飞书通知发送成功。")


def notify_feishu(report_path, paper_count):
    send_report_notice(Path(report_path), paper_count)


def send_report_file(report_path: Path, paper_count: int = 0) -> None:
    if not report_path.is_file():
        raise FileNotFoundError(f"日报文件不存在：{report_path}")

    notify_feishu(report_path, paper_count)


def _parse_args():
    parser = argparse.ArgumentParser(description="发送文献日报飞书 webhook 通知")
    parser.add_argument("report", type=Path, help="日报 HTML 文件路径")
    parser.add_argument(
        "--paper-count",
        type=int,
        default=0,
        help="日报论文数量",
    )
    return parser.parse_args()


def main() -> int:
    import sys

    load_dotenv()
    load_dotenv("config/deepseek.env", override=True)

    args = _parse_args()
    if not args.report.is_file():
        print(f"日报文件不存在：{args.report}", file=sys.stderr)
        return 1

    try:
        send_report_file(args.report, paper_count=args.paper_count)
    except requests.RequestException as e:
        print(f"飞书推送失败：{e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
