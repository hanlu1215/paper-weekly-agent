import datetime
import re
from pathlib import Path

from published_history import extract_arxiv_id

# 每日速递单独目录，不覆盖 output/ 下历史文件
DAILY_REPORTS_DIR = Path("daily_reports")
WEEKLY_REPORTS_DIR = Path("weekly_reports")
_ARXIV_IN_MD_RE = re.compile(
    r"https://arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?",
    re.I,
)


def _render_paper_section(
    idx: int,
    paper: dict,
    summary: str,
    title_zh: str = "",
) -> list[str]:
    lines = []
    display_title = (title_zh or paper["title"]).strip()
    lines.append(f"\n## {idx}. {display_title}\n")
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


def daily_report_path(today: datetime.date | None = None) -> Path:
    """当日速递固定路径；同日多次运行覆盖同一文件，不在 GitHub 新增 -02 等副本。"""
    today = today or datetime.date.today()
    DAILY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return DAILY_REPORTS_DIR / f"{today.isoformat()}-文献每日速递.md"


def _remove_legacy_same_day_suffix_files(date_str: str) -> None:
    """删除旧版同日递增后缀文件（如 …-02.md），避免仓库残留多余条目。"""
    for path in DAILY_REPORTS_DIR.glob(f"{date_str}-文献每日速递-*.md"):
        path.unlink(missing_ok=True)


def _arxiv_ids_in_markdown(text: str) -> set[str]:
    return set(_ARXIV_IN_MD_RE.findall(text))


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
        lines.append("今日无新增文献（与往日已发布记录重复或暂无匹配论文）。\n")
        if skipped_duplicates:
            lines.append(f"\n> 已跳过 {skipped_duplicates} 篇往日已发布文献。\n")
    else:
        lines.append(f"今日新增 {len(papers_with_summaries)} 篇。\n")
        if skipped_duplicates:
            lines.append(f"> 已跳过 {skipped_duplicates} 篇往日已发布文献。\n")
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


def append_to_weekly_report(papers_with_summaries) -> Path | None:
    """将新增文献追加到当周累计文件（weekly_reports/，只追加不覆盖）。"""
    if not papers_with_summaries:
        return None

    today = datetime.date.today()
    _, week, _ = today.isocalendar()
    output_path = _weekly_report_path(today)

    existing_ids: set[str] = set()
    if output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        existing_ids = _arxiv_ids_in_markdown(existing)
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

    added = 0
    for item in papers_with_summaries:
        arxiv_id = extract_arxiv_id(item["paper"])
        if arxiv_id and arxiv_id in existing_ids:
            continue
        lines.extend(
            _render_paper_section(
                next_idx,
                item["paper"],
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


def render_markdown_report(papers_with_summaries, *, skipped_duplicates: int = 0) -> Path:
    """生成每日速递存档，并追加到当周累计。"""
    daily_path = render_daily_report(
        papers_with_summaries,
        skipped_duplicates=skipped_duplicates,
    )
    append_to_weekly_report(papers_with_summaries)
    return daily_path
