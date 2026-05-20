#!/usr/bin/env python3
"""单独测试微信公众号发布（跳过文献检索与 DeepSeek 总结）。

默认发布 daily_reports/2026-05-20-文献每日速递.md，需配置：
  WECHAT_CLOUD_PUBLISH_URL、WECHAT_CLOUD_PUBLISH_TOKEN（与云托管环境变量一致）

用法:
  python3 scripts/test_wechat_publish.py
  python3 scripts/test_wechat_publish.py daily_reports/2026-05-20-文献每日速递.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "config" / "deepseek.env", override=True)

from send_to_wechat_cloud import publish_to_wechat_cloud  # noqa: E402

DEFAULT_REPORT = ROOT / "daily_reports" / "2026-05-20-文献每日速递.md"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="单独测试公众号云托管发布，不跑文献检索主流程",
    )
    parser.add_argument(
        "report",
        nargs="?",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"每日速递 .md 路径（默认 {DEFAULT_REPORT.relative_to(ROOT)}）",
    )
    args = parser.parse_args()

    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    if not report_path.is_file():
        print(f"日报文件不存在：{report_path}", file=sys.stderr)
        return 1

    print(f"=== 公众号发布测试（跳过检索）===\n文件：{report_path.relative_to(ROOT)}")
    try:
        publish_to_wechat_cloud(report_path)
        print("测试完成。")
        return 0
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"发布失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
