import datetime
import html
import re
from pathlib import Path

from report_date import report_today
from summarize import _strip_ai_summary_heading

DAILY_REPORTS_DIR = Path("daily_reports")
REPORT_INDEX_PATH = Path("index.html")
MAX_RETAINED_DAILY_REPORTS = 30
_DAILY_REPORT_FILENAME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})-文献每日速递\.html$",
)


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _render_text_block(text: str) -> str:
    stripped = _strip_ai_summary_heading(text).strip()
    if not stripped:
        return '<p class="empty">暂无摘要内容。</p>'

    paragraphs = []
    for chunk in re.split(r"\n\s*\n", stripped):
        chunk = chunk.strip()
        if not chunk:
            continue
        paragraphs.append(f"<p>{_escape(chunk).replace(chr(10), '<br>')}</p>")
    return "\n".join(paragraphs)


def _render_links(*, paper_url: str = "", pdf_url: str = "") -> str:
    items = []
    if paper_url:
        items.append(f'<li><a href="{_escape(paper_url)}" target="_blank" rel="noreferrer">论文链接</a></li>')
    if pdf_url:
        items.append(f'<li><a href="{_escape(pdf_url)}" target="_blank" rel="noreferrer">PDF 链接</a></li>')
    if not items:
        return ""
    return '<ul class="links">' + "".join(items) + "</ul>"


def _render_paper_section(
    idx: int,
    paper: dict,
    summary: str,
    title_zh: str = "",
) -> str:
    display_title = (title_zh or paper["title"]).strip()
    source = paper.get("source") or "未知来源"
    paper_url = paper.get("url") or paper.get("arxiv_url") or ""
    pdf_url = paper.get("pdf_url") or ""
    authors = ", ".join(paper["authors"])
    categories = ", ".join(paper.get("categories", []))

    meta_items = [
        f"<li><span>作者</span><span>{_escape(authors)}</span></li>",
        f"<li><span>来源</span><span>{_escape(source)}</span></li>",
        f"<li><span>发布时间</span><span>{_escape(paper['published'])}</span></li>",
    ]
    doi = str(paper.get("doi") or "").strip()
    if doi:
      meta_items.append(f"<li><span>DOI</span><span>{_escape(doi)}</span></li>")
    if categories:
        meta_items.append(f"<li><span>分类</span><span>{_escape(categories)}</span></li>")

    return f"""
    <section class="paper-card">
      <div class="paper-index">{idx}</div>
      <div class="paper-body">
        <h2>{_escape(display_title)}</h2>
        <ul class="meta-list">
          {''.join(meta_items)}
        </ul>
        {_render_links(paper_url=paper_url, pdf_url=pdf_url)}
        <div class="summary">
          {_render_text_block(summary)}
        </div>
      </div>
    </section>
    """


def daily_report_title(today: datetime.date | None = None) -> str:
    today = today or report_today()
    return f"{today.isoformat()}-文献每日速递"


def daily_report_path(today: datetime.date | None = None) -> Path:
    """当日日报固定路径；目录不存在时自动创建。"""
    today = today or report_today()
    DAILY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return DAILY_REPORTS_DIR / f"{today.isoformat()}-文献每日速递.html"


def _list_dated_daily_reports() -> list[tuple[datetime.date, Path]]:
    """列出 daily_reports/ 下符合命名规范的日报 .html（不含 README）。"""
    if not DAILY_REPORTS_DIR.is_dir():
        return []

    reports: list[tuple[datetime.date, Path]] = []
    for path in DAILY_REPORTS_DIR.glob("*.html"):
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
    """删除同一天非标准命名的重复 .html（如 …-1.html、…-copy.html）。"""
    if not DAILY_REPORTS_DIR.is_dir():
        return

    date_str = today.isoformat()
    canonical = daily_report_path(today)
    for path in DAILY_REPORTS_DIR.glob(f"{date_str}*.html"):
        if path.resolve() == canonical.resolve():
            continue
        if path.is_file():
            path.unlink(missing_ok=True)
            print(f"已删除同日重复文件：{path.name}", flush=True)


def _prune_old_daily_reports(max_count: int = MAX_RETAINED_DAILY_REPORTS) -> None:
    """daily_reports/ 内仅保留最近 max_count 份标准日报，按日期删最旧的 .html。"""
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


def _render_report_index_item(report_date: datetime.date, path: Path) -> str:
    title = f"{report_date.isoformat()}-文献每日速递"
    return f"""
    <a class="report-card" href="{_escape(path.as_posix())}" target="_blank" rel="noreferrer">
      <div class="report-date">{_escape(report_date.isoformat())}</div>
      <div class="report-title">{_escape(title)}</div>
    </a>
    """


def render_report_index() -> Path:
    """生成根目录 index.html，聚合链接到 daily_reports/ 下的所有日报。"""
    reports = list(reversed(_list_dated_daily_reports()))
    report_items = "\n".join(
        _render_report_index_item(report_date, path)
        for report_date, path in reports
    )
    empty_block = (
    '<p class="empty">当前还没有生成日报。</p>'
        if not reports
        else ""
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>文献报告目录</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: rgba(15, 23, 42, 0.7);
      --card: rgba(255, 255, 255, 0.08);
      --card-hover: rgba(255, 255, 255, 0.14);
      --text: #e5eefc;
      --muted: #a8b3c7;
      --accent: #38bdf8;
      --accent-2: #2dd4bf;
      --border: rgba(148, 163, 184, 0.25);
      --shadow: 0 24px 60px rgba(2, 6, 23, 0.35);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(56, 189, 248, 0.28), transparent 32%),
        radial-gradient(circle at top right, rgba(45, 212, 191, 0.18), transparent 30%),
        linear-gradient(180deg, #020617 0%, #0f172a 45%, #111827 100%);
    }}
    .page {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 44px 20px 72px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 30px;
      padding: 30px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
      margin-bottom: 24px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(32px, 5vw, 56px);
      line-height: 1.05;
    }}
    .section-title {{
      margin: 28px 0 14px;
      font-size: 18px;
      letter-spacing: 0.02em;
    }}
    .report-grid {{
      display: grid;
      gap: 14px;
    }}
    .report-card {{
      display: grid;
      gap: 8px;
      padding: 18px 20px;
      border-radius: 22px;
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--text);
      text-decoration: none;
      box-shadow: var(--shadow);
      transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
    }}
    .report-card:hover {{
      transform: translateY(-2px);
      background: var(--card-hover);
      border-color: rgba(56, 189, 248, 0.5);
    }}
    .report-date {{
      color: var(--accent-2);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .report-title {{
      font-size: 20px;
      font-weight: 700;
      line-height: 1.4;
    }}
    .empty {{
      margin: 0;
      padding: 18px 20px;
      border-radius: 20px;
      border: 1px dashed var(--border);
      color: var(--muted);
      background: rgba(255, 255, 255, 0.04);
    }}
    @media (max-width: 720px) {{
      .page {{ padding: 16px 12px 40px; }}
      .hero {{ padding: 20px; border-radius: 24px; }}
      .report-card {{ padding: 16px; }}
      .report-title {{ font-size: 18px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <h1>文献报告目录</h1>
    </header>

    <section>
      <div class="section-title">最新日报</div>
      <div class="report-grid">
        {report_items or empty_block}
      </div>
    </section>
  </main>
</body>
</html>
"""

    REPORT_INDEX_PATH.write_text(html_doc, encoding="utf-8")
    return REPORT_INDEX_PATH


def render_daily_report(
    papers_with_summaries,
    *,
    output_path: Path | None = None,
) -> Path:
    """生成当日日报 HTML 并写入 daily_reports/（覆盖同日文件，并清理超量旧文件）。"""
    today = report_today()
    output_path = output_path or daily_report_path(today)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _cleanup_same_day_extra_files(today)

    paper_sections = []
    for idx, item in enumerate(papers_with_summaries, start=1):
        paper_sections.append(
            _render_paper_section(
                idx,
                item["paper"],
                item["summary"],
                item.get("title_zh", ""),
            )
        )

    count = len(papers_with_summaries)
    summary_block = (
        '<p class="count">今日无新增文献（暂无匹配论文）。</p>'
        if count == 0
        else f'<p class="count">今日新增 {count} 篇。</p>'
    )
    content_html = "\n".join(paper_sections) if paper_sections else ""

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(daily_report_title(today))}</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --accent: #0f766e;
      --border: #dbe4ee;
      --shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: linear-gradient(180deg, #eef4ff 0%, #f5f7fb 30%, #f8fafc 100%);
      color: var(--text);
    }}
    .page {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 40px 20px 72px;
    }}
    .hero {{
      background: rgba(255, 255, 255, 0.72);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(219, 228, 238, 0.9);
      border-radius: 28px;
      padding: 28px 28px 24px;
      box-shadow: var(--shadow);
      margin-bottom: 28px;
    }}
    .eyebrow {{
      display: inline-block;
      color: var(--accent);
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 12px;
      margin-bottom: 10px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(30px, 4vw, 46px);
      line-height: 1.1;
    }}
    .hero-meta, .count {{
      color: var(--muted);
      margin: 12px 0 0;
      line-height: 1.7;
    }}
    .paper-grid {{
      display: grid;
      gap: 18px;
    }}
    .paper-card {{
      display: grid;
      grid-template-columns: 72px 1fr;
      gap: 18px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 22px;
      box-shadow: var(--shadow);
    }}
    .paper-index {{
      width: 64px;
      height: 64px;
      border-radius: 18px;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, #0f766e, #14b8a6);
      color: white;
      font-size: 24px;
      font-weight: 800;
    }}
    .paper-body h2 {{
      margin: 0 0 12px;
      font-size: 24px;
      line-height: 1.35;
    }}
    .meta-list, .links {{
      list-style: none;
      padding: 0;
      margin: 0 0 14px;
    }}
    .meta-list li {{
      display: flex;
      gap: 12px;
      margin: 6px 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    .meta-list span:first-child {{
      min-width: 84px;
      color: var(--text);
      font-weight: 600;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 8px;
      margin-bottom: 18px;
    }}
    .links a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }}
    .summary {{
      background: #f8fbff;
      border: 1px solid #d9e6f2;
      border-radius: 18px;
      padding: 16px 18px;
      line-height: 1.8;
    }}
    .summary p {{
      margin: 0 0 12px;
      white-space: pre-wrap;
    }}
    .summary p:last-child {{
      margin-bottom: 0;
    }}
    .empty {{
      color: var(--muted);
    }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 12px 44px; }}
      .hero, .paper-card {{ padding: 18px; border-radius: 20px; }}
      .paper-card {{ grid-template-columns: 1fr; }}
      .paper-index {{ width: 52px; height: 52px; font-size: 20px; }}
      .meta-list li {{ display: block; }}
      .meta-list span:first-child {{ display: block; min-width: 0; margin-bottom: 2px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <div class="eyebrow">Paper Weekly Agent</div>
      <h1>{_escape(daily_report_title(today))}</h1>
      <p class="hero-meta">生成时间：{_escape(today.isoformat())}<br>存档文件：{_escape(output_path.name)}</p>
      {summary_block}
    </header>
    <section class="paper-grid">
      {content_html}
    </section>
  </main>
</body>
</html>
"""

    output_path.write_text(html_doc, encoding="utf-8")
    _prune_old_daily_reports()
    return output_path


def render_html_report(papers_with_summaries) -> Path:
    report_path = render_daily_report(papers_with_summaries)
    render_report_index()
    return report_path