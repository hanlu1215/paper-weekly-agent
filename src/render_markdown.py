import datetime
import re
from pathlib import Path

from report_date import report_today
from summarize import _strip_ai_summary_heading

DAILY_REPORTS_DIR = Path("daily_reports")
MAX_RETAINED_DAILY_REPORTS = 30
_DAILY_REPORT_FILENAME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})-文献每日速递\.md$",
)


def _render_paper_section(
    idx: int,
    paper: dict,
    summary: str,
    title_zh: str = "",
) -> list[str]:
    lines = []
    display_title = (title_zh or paper["title"]).strip()
    source = paper.get("source") or "未知来源"
    paper_url = paper.get("url") or paper.get("arxiv_url") or ""
    pdf_url = paper.get("pdf_url") or ""
    lines.append(f"\n## {idx}. {display_title}\n")
    lines.append(f"- 作者：{', '.join(paper['authors'])}\n")
    lines.append(f"- 来源：{source}\n")
    lines.append(f"- 发布时间：{paper['published']}\n")
    if paper_url:
        lines.append(f"- 论文链接：{paper_url}\n")
    if pdf_url:
        lines.append(f"- PDF 链接：{pdf_url}\n")
    if paper.get("categories"):
        lines.append(f"- 分类：{', '.join(paper['categories'])}\n")
    lines.append("\n")
    lines.append(_strip_ai_summary_heading(summary))
    lines.append("\n---\n")
    return lines


def daily_report_title(today: datetime.date | None = None) -> str:
    today = today or report_today()
    return f"{today.isoformat()}-文献每日速递"


def daily_report_path(today: datetime.date | None = None) -> Path:
    """当日日报固定路径；目录不存在时自动创建。"""
    today = today or report_today()
    DAILY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return DAILY_REPORTS_DIR / f"{today.isoformat()}-文献每日速递.md"


def _list_dated_daily_reports() -> list[tuple[datetime.date, Path]]:
    """列出 daily_reports/ 下符合命名规范的日报 .md（不含 README）。"""
    if not DAILY_REPORTS_DIR.is_dir():
        return []

    reports: list[tuple[datetime.date, Path]] = []
    for path in DAILY_REPORTS_DIR.glob("*.md"):
        if path.name.upper() == "README.MD":
            continue
        match = _DAILY_REPORT_FILENAME_RE.match(path.name)
        if not match:
            continue
        try:
            report_date = datetime.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        reports.append((report_date, path))

    return sorted(reports, key=lambda item: item[0])


def _cleanup_same_day_extra_files(today: datetime.date) -> None:
    """删除同一天非标准命名的重复 .md（如 …-1.md、…-copy.md）。"""
    if not DAILY_REPORTS_DIR.is_dir():
        return

    date_str = today.isoformat()
    canonical = daily_report_path(today)
    for path in DAILY_REPORTS_DIR.glob(f"{date_str}*.md"):
        if path.resolve() == canonical.resolve():
            continue
        if path.is_file():
            path.unlink(missing_ok=True)
            print(f"已删除同日重复文件：{path.name}", flush=True)


def _prune_old_daily_reports(max_count: int = MAX_RETAINED_DAILY_REPORTS) -> None:
    """daily_reports/ 内仅保留最近 max_count 份标准日报，按日期删最旧的 .md。"""
    reports = _list_dated_daily_reports()
    if len(reports) <= max_count:
        return

    excess = len(reports) - max_count
    for report_date, path in reports[:excess]:
        path.unlink(missing_ok=True)
        print(
            f"已删除过期日报（{report_date.isoformat()}）：{path.name}",
            flush=True,
        )


def render_daily_report(
    papers_with_summaries,
    *,
    output_path: Path | None = None,
) -> Path:
    """生成当日日报并写入 daily_reports/（覆盖同日文件，并清理超量旧文件）。"""
    today = report_today()
    output_path = output_path or daily_report_path(today)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _cleanup_same_day_extra_files(today)

    lines = [
        f"# {daily_report_title(today)}\n",
        f"> 生成时间：{today}\n",
        f"> 存档文件：{output_path.name}\n",
        "---\n",
    ]

    if not papers_with_summaries:
        lines.append("今日无新增文献（暂无匹配论文）。\n")
    else:
        lines.append(f"今日新增 {len(papers_with_summaries)} 篇。\n")
        for idx, item in enumerate(papers_with_summaries, start=1):
            lines.extend(
                _render_paper_section(
                    idx,
                    item["paper"],
                    item["summary"],
                    item.get("title_zh", ""),
                )
            )

    output_path.write_text("\n".join(lines), encoding="utf-8")
    _prune_old_daily_reports()
    return output_path


def render_markdown_report(papers_with_summaries) -> Path:
    """生成每日日报 Markdown，统一保存到 daily_reports/。"""
    return render_daily_report(papers_with_summaries)
