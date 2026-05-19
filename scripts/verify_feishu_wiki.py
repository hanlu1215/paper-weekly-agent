#!/usr/bin/env python3
"""验证飞书知识库配置（本地或 CI 可运行，不打印密钥）。"""

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "config" / "deepseek.env", override=True)

from feishu_client import FeishuAPIError, get_tenant_access_token  # noqa: E402
from feishu_wiki import (  # noqa: E402
    get_parent_node_token,
    get_wiki_space_id,
    validate_wiki_config,
)


def main() -> int:
    print("=== 飞书知识库配置验证 ===")

    try:
        validate_wiki_config()
        token = get_tenant_access_token()
        print(f"[OK] tenant_access_token 获取成功（长度 {len(token)}）")

        space_id = get_wiki_space_id()
        print(f"[OK] space_id = {space_id}")

        parent = get_parent_node_token()
        if parent:
            print(f"[OK] parent_node_token = {parent[:12]}...")

        print("验证通过，可创建知识库文档。")
        return 0
    except FeishuAPIError as err:
        print(f"[FAIL] {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
