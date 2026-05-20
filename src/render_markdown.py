import datetime
from pathlib import Path

from report_date import report_today

DAILY_REPORTS_DIR = Path("daily_reports")
DAILY_CUMULATIVE_DIR = Path("daily_cumulative")


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
    lines.append(summary)
    lines.append("\n---\n")
    return lines


def daily_report_title(today: datetime.date | None = None) -> str:
    today = today or report_today()
    return f"{today.isoformat()}-文献每日速递"


def daily_report_path(today: datetime.date | None = None) -> Path:
    """当日速递固定路径；同日多次运行覆盖同一文件，不在 GitHub 新增 -02 等副本。"""
    today = today or report_today()
    DAILY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return DAILY_REPORTS_DIR / f"{today.isoformat()}-文献每日速递.md"


def _remove_legacy_same_day_suffix_files(date_str: str) -> None:
    """删除旧版同日递增后缀文件（如 …-02.md），避免仓库残留多余条目。"""
    for path in DAILY_REPORTS_DIR.glob(f"{date_str}-文献每日速递-*.md"):
        path.unlink(missing_ok=True)


def _daily_cumulative_path(today: datetime.date | None = None) -> Path:
    today = today or report_today()
    DAILY_CUMULATIVE_DIR.mkdir(parents=True, exist_ok=True)
    return DAILY_CUMULATIVE_DIR / f"{today.year}-{today.month:02d}-文献日报-累计.md"


def render_daily_report(
    papers_with_summaries,
    *,
    output_path: Path | None = None,
) -> Path:
    """生成当日速递（仅包含本次新增文献），写入 daily_reports/。"""
    today = report_today()
    output_path = output_path or daily_report_path(today)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _remove_legacy_same_day_suffix_files(today.isoformat())

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
    return output_path


def append_to_daily_cumulative(papers_with_summaries) -> Path | None:
    """将新增文献追加到当月日报累计文件（daily_cumulative/，只追加不覆盖）。"""
    if not papers_with_summaries:
        return None

    today = report_today()
    output_path = _daily_cumulative_path(today)

    if output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        next_idx = existing.count("\n## ") + 1
        lines = [existing.rstrip(), "", f"\n> 追加日期：{today}\n"]
    else:
        next_idx = 1
        lines = [
            f"# {today.year}年{today.month}月文献日报累计\n",
            f"> 生成日期：{today}\n",
            "---\n",
            "本月日报累计文献（按日追加）：\n",
        ]

    added = 0
    for item in papers_with_summaries:
        paper = item["paper"]
        lines.extend(
            _render_paper_section(
                next_idx,
                paper,
                item["summary"],
                item.get("title_zh", ""),
            )
        )
        next_idx += 1
        added += 1

    if added == 0:
        return output_path if output_path.exists() else None

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def render_markdown_report(papers_with_summaries) -> Path:
    """生成每日速递存档，并追加到当月日报累计。"""
    daily_path = render_daily_report(papers_with_summaries)
    append_to_daily_cumulative(papers_with_summaries)
    return daily_path
