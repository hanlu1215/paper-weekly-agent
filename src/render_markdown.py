import datetime
from pathlib import Path


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


def _daily_report_path(today: datetime.date | None = None) -> Path:
    today = today or datetime.date.today()
    return Path("output") / f"{today.isoformat()}-paper-daily.md"


def _weekly_report_path(today: datetime.date | None = None) -> Path:
    today = today or datetime.date.today()
    year, week, _ = today.isocalendar()
    return Path("output") / f"{year}-W{week:02d}-paper-weekly.md"


def render_daily_report(papers_with_summaries, *, skipped_duplicates: int = 0) -> Path:
    """生成当日日报（仅包含本次新增文献）。"""
    today = datetime.date.today()
    output_path = _daily_report_path(today)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# {daily_report_title(today)}\n",
        f"> 生成时间：{today}\n",
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
    """将新增文献追加到当周周报（不覆盖既有内容）。"""
    if not papers_with_summaries:
        return None

    today = datetime.date.today()
    _, week, _ = today.isocalendar()
    output_path = _weekly_report_path(today)
    output_path.parent.mkdir(parents=True, exist_ok=True)

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
    """生成日报，并追加到当周周报。"""
    daily_path = render_daily_report(
        papers_with_summaries,
        skipped_duplicates=skipped_duplicates,
    )
    append_to_weekly_report(papers_with_summaries)
    return daily_path
