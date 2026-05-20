#!/usr/bin/env bash
# 本地运行主流程（需已配置 .env 与 config/deepseek.env）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "请先复制并填写配置：cp .env.example .env" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -q -r requirements.txt

python src/main.py "$@"
