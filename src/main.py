import datetime
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml
from dotenv import load_dotenv

from fetch_arxiv import fetch_arxiv_papers
from fetch_openreview import fetch_openreview_papers
from fetch_scopus import fetch_scopus_papers
from fetch_semantic_scholar import fetch_semantic_scholar_papers
from notify_feishu import notify_feishu
from render_html import render_html_report
from summarize import summarize_paper


DEFAULT_MAX_RESULTS_PER_SOURCE = 10000
HISTORY_REPORT_DIR = Path("daily_reports")
_PAPER_LINK_RE = re.compile(r'<a href="([^"]+)"[^>]*>论文链接</a>')


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return int(value)


def load_keywords():
    with open("config/keywords.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data["keywords"]


def _normalize_key(value: str) -> str:
    return str(value or "").strip().lower().rstrip("/")


def _extract_key_from_url(url: str) -> str:
    normalized = _normalize_key(url)
    if not normalized:
        return ""

    parsed = urlparse(normalized)
    host = parsed.netloc
    path = parsed.path
    query = parse_qs(parsed.query)

    if "arxiv.org" in host:
        match = re.search(r"/(?:abs|pdf)/([^/?#]+)", path)
        if match:
            return f"arxiv:{match.group(1).replace('.pdf', '')}"

    if "openreview.net" in host:
        forum_id = (query.get("id") or [""])[0]
        if forum_id:
            return f"openreview:{forum_id}"

    if "scopus.com" in host:
        eid = (query.get("eid") or [""])[0]
        if eid:
            return f"scopus:{eid}"

    if "api.elsevier.com" in host and "scopus_id" in path:
        match = re.search(r"scopus_id/([^/?#]+)", path)
        if match:
            return f"scopus:{match.group(1)}"

    if "doi.org" in host and path.strip("/"):
        return f"doi:{path.strip('/')}"

    return normalized


def _paper_keys(paper: dict) -> set[str]:
    keys: set[str] = set()

    external_id = _normalize_key(paper.get("external_id", ""))
    if external_id:
        source = _normalize_key(paper.get("source", "unknown"))
        keys.add(f"{source}:{external_id}")

    doi = _normalize_key(paper.get("doi", ""))
    if doi:
        keys.add(f"doi:{doi}")

    for field in ("url", "arxiv_url"):
        extracted = _extract_key_from_url(paper.get(field, ""))
        if extracted:
            keys.add(extracted)

    return keys


def _collect_reported_keys() -> set[str]:
    keys: set[str] = set()
    if not HISTORY_REPORT_DIR.is_dir():
        return keys

    for report_path in HISTORY_REPORT_DIR.glob("*.html"):
        try:
            content = report_path.read_text(encoding="utf-8")
        except OSError:
            continue

        for url in _PAPER_LINK_RE.findall(content):
            extracted = _extract_key_from_url(url)
            if extracted:
                keys.add(extracted)

    return keys


def _filter_already_reported(papers: list[dict], reported_keys: set[str]) -> list[dict]:
    filtered: list[dict] = []
    skipped = 0
    for paper in papers:
        paper_keys = _paper_keys(paper)
        if paper_keys and paper_keys & reported_keys:
            skipped += 1
            continue
        filtered.append(paper)

    print(f"按历史报告去重后保留 {len(filtered)} 篇，过滤 {skipped} 篇。", flush=True)
    return filtered


def _parse_published_time(published: str) -> datetime.datetime:
    text = str(published or "").strip()
    if not text:
        return datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if len(text) == 4 and text.isdigit():
        text = f"{text}-01-01"
    elif len(text) == 7 and text[4] == "-":
        text = f"{text}-01"

    try:
        dt = datetime.datetime.fromisoformat(text)
    except ValueError:
        return datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _source_rank(paper: dict) -> int:
    return 0 if _normalize_key(paper.get("source", "")) == "scopus" else 1


def _sort_papers(papers: list[dict]) -> list[dict]:
    return sorted(
        papers,
        key=lambda item: (
            _source_rank(item),
            -_parse_published_time(item.get("published", "")).timestamp(),
        ),
    )


def _dedupe_papers(papers: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []

    for paper in papers:
        keys = _paper_keys(paper)
        primary = next(iter(keys), "")
        if keys and keys & seen:
            continue
        if primary:
            seen.update(keys)
        deduped.append(paper)

    return deduped


def main():
    load_dotenv()
    load_dotenv("config/deepseek.env", override=True)
    max_results_per_source = _env_int("MAX_RESULTS_PER_SOURCE", DEFAULT_MAX_RESULTS_PER_SOURCE)
    if max_results_per_source <= 0:
        max_results_per_source = DEFAULT_MAX_RESULTS_PER_SOURCE

    print("=" * 60, flush=True)
    print("文献日报 Agent 启动", flush=True)
    print("=" * 60, flush=True)

    print("正在读取关键词...", flush=True)
    keywords = load_keywords()

    for kw in keywords:
        print(f"  - {kw}", flush=True)

    papers = []
    source_fetchers = [
        ("Scopus", fetch_scopus_papers),
        ("arXiv", fetch_arxiv_papers),
        ("Semantic Scholar", fetch_semantic_scholar_papers),
        ("OpenReview", fetch_openreview_papers),
    ]
    for source_name, fetcher in source_fetchers:
        print(f"\n正在抓取 {source_name} 论文...", flush=True)
        source_papers = fetcher(keywords, max_results=max_results_per_source)
        print(f"{source_name} 原始抓取论文数量：{len(source_papers)}", flush=True)
        papers.extend(source_papers)

    print(f"\n多源原始抓取论文总数：{len(papers)}", flush=True)

    papers = _dedupe_papers(papers)
    print(f"去重后论文数量：{len(papers)}", flush=True)

    reported_keys = _collect_reported_keys()
    print(f"历史报告中识别到 {len(reported_keys)} 个去重键。", flush=True)
    papers = _filter_already_reported(papers, reported_keys)

    ordered_papers = _sort_papers(papers)
    print(f"排序后待总结论文数量：{len(ordered_papers)}", flush=True)

    papers_with_summaries = []

    for idx, paper in enumerate(ordered_papers, start=1):
        print("\n" + "-" * 60)
        print(f"正在处理第 {idx}/{len(ordered_papers)} 篇", flush=True)
        print(paper["title"], flush=True)
        summary, title_zh = summarize_paper(paper)
        print("摘要已生成。", flush=True)

        papers_with_summaries.append({
            "paper": paper,
            "summary": summary,
            "title_zh": title_zh,
        })

    print("\n正在生成 HTML 报告...", flush=True)
    report_path = render_html_report(
        papers_with_summaries,
    )
    print(f"HTML 日报已生成：{report_path}", flush=True)

    if os.getenv("SKIP_FEISHU_NOTIFY", "").lower() in ("1", "true", "yes"):
        print("\n已设置 SKIP_FEISHU_NOTIFY，跳过飞书推送（由 CI 在提交后单独发送）。", flush=True)
    elif not papers_with_summaries:
        print("\n今日无新增文献，跳过飞书推送。", flush=True)
    else:
        print("\n正在推送飞书通知...", flush=True)
        notify_feishu(report_path, len(papers_with_summaries))

    print("\n任务完成。", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
