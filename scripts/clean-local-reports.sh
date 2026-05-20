#!/usr/bin/env bash
# 删除本地报告 Markdown，不影响 GitHub 仓库内已提交的文件。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

rm -f daily_reports/*-文献每日速递*.md daily_reports/*-文献每日速递-*.md
rm -f weekly_reports/*.md 2>/dev/null || true

while IFS= read -r -d '' f; do
  case "$f" in
    */daily_reports/README.md) continue ;;
  esac
  git update-index --skip-worktree "$f" 2>/dev/null || true
done < <(git ls-files -z 'daily_reports/*.md' 'weekly_reports/*.md' 2>/dev/null || true)

echo "已清理本地报告 Markdown（GitHub 远端未改动）。"
