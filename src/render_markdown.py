import datetime
from pathlib import Path

# 每日速递单独目录，不覆盖 output/ 下历史文件
DAILY_REPORTS_DIR = Path("daily_reports")
WEEKLY_REPORTS_DIR = Path("weekly_reports")


def _render_paper_section(idx: int, paper: dict, summary: str) -> list[str]:
    lines = []
    lines.append(f"\n## {idx}. {paper['title']}\n")
    lines.append(f"- 作者：{', '.join(paper['authors'])}\n")
    lines.append(f"- 发布时间：{paper['published']}\n")
    lines.append(f"- arXiv 链接：{paper['arxiv_url']}\n")
    lines.append(f"- PDF 链接：{paper['pdf_url']}\n")
    if paper.get("categories"):
        lines.append(f"- 分类：{', '.join(paper['categories'])}\n")
    lines.append("\n")
    lines.append(summary)
    lines.append("\n---\n")
    return lines


def daily_report_title(today: datetime.date | None = None) -> str:
    today = today or datetime.date.today()
    return f"{today.isoformat()}-文献每日速递"


def allocate_daily_report_path(today: datetime.date | None = None) -> Path:
    """
    在 daily_reports/ 下分配当日文件路径；若已存在则递增序号，避免覆盖。
    例如：2026-05-19-文献每日速递.md → 2026-05-19-文献每日速递-02.md
    """
    today = today or datetime.date.today()
    DAILY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = today.isoformat()
    first = DAILY_REPORTS_DIR / f"{date_str}-文献每日速递.md"
    if not first.exists():
        return first
    index = 2
    while True:
        candidate = DAILY_REPORTS_DIR / f"{date_str}-文献每日速递-{index:02d}.md"
        if not candidate.exists():
            return candidate
        index += 1


def _weekly_report_path(today: datetime.date | None = None) -> Path:
    today = today or datetime.date.today()
    year, week, _ = today.isocalendar()
    WEEKLY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return WEEKLY_REPORTS_DIR / f"{year}-W{week:02d}-文献每日速递-累计.md"


def render_daily_report(
    papers_with_summaries,
    *,
    skipped_duplicates: int = 0,
    output_path: Path | None = None,
) -> Path:
    """生成当日速递（仅包含本次新增文献），写入 daily_reports/。"""
    today = datetime.date.today()
    output_path = output_path or allocate_daily_report_path(today)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# {daily_report_title(today)}\n",
        f"> 生成时间：{today}\n",
        f"> 存档文件：{output_path.name}\n",
        "---\n",
    ]

    if not papers_with_summaries:
        lines.append("今日无新增文献（与历史已发布记录重复或暂无匹配论文）。\n")
        if skipped_duplicates:
            lines.append(f"\n> 已跳过 {skipped_duplicates} 篇此前已发布文献。\n")
    else:
        lines.append(f"今日新增 {len(papers_with_summaries)} 篇。\n")
        if skipped_duplicates:
            lines.append(f"> 已跳过 {skipped_duplicates} 篇此前已发布文献。\n")
        for idx, item in enumerate(papers_with_summaries, start=1):
            lines.extend(_render_paper_section(idx, item["paper"], item["summary"]))

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def append_to_weekly_report(papers_with_summaries) -> Path | None:
    """将新增文献追加到当周累计文件（weekly_reports/，只追加不覆盖）。"""
    if not papers_with_summaries:
        return None

    today = datetime.date.today()
    _, week, _ = today.isocalendar()
    output_path = _weekly_report_path(today)

    if output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        next_idx = existing.count("\n## ") + 1
        lines = [existing.rstrip(), "", f"\n> 追加日期：{today}\n"]
    else:
        next_idx = 1
        lines = [
            f"# {daily_report_title(today)}\n",
            f"> 第 {week} 周累计 · 生成日期：{today}\n",
            "---\n",
            "本周累计文献（按日追加）：\n",
        ]

    for item in papers_with_summaries:
        lines.extend(_render_paper_section(next_idx, item["paper"], item["summary"]))
        next_idx += 1

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def render_markdown_report(papers_with_summaries, *, skipped_duplicates: int = 0) -> Path:
    """生成每日速递存档，并追加到当周累计。"""
    daily_path = render_daily_report(
        papers_with_summaries,
        skipped_duplicates=skipped_duplicates,
    )
    append_to_weekly_report(papers_with_summaries)
    return daily_path
