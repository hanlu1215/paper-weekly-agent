import os

import yaml
from dotenv import load_dotenv

from fetch_arxiv import fetch_arxiv_papers
from fetch_arxiv import filter_recent_papers
from fetch_ieee_xplore import fetch_ieee_xplore_papers
from fetch_openreview import fetch_openreview_papers
from fetch_semantic_scholar import fetch_semantic_scholar_papers
from summarize import summarize_paper
from render_markdown import render_markdown_report
from notify_feishu import notify_feishu


DEFAULT_MAX_PAPERS_TO_SUMMARIZE = 5
DEFAULT_RECENT_DAYS = 30
DEFAULT_MAX_RESULTS_PER_SOURCE = 30


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return int(value)


def load_keywords():
    with open("config/keywords.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data["keywords"]


def main():
    load_dotenv()
    load_dotenv("config/deepseek.env", override=True)
    max_papers_to_summarize = _env_int("MAX_PAPERS_TO_SUMMARIZE", DEFAULT_MAX_PAPERS_TO_SUMMARIZE)
    recent_days = _env_int("RECENT_DAYS", DEFAULT_RECENT_DAYS)
    max_results_per_source = _env_int("MAX_RESULTS_PER_SOURCE", DEFAULT_MAX_RESULTS_PER_SOURCE)

    print("=" * 60, flush=True)
    print("Paper Weekly Agent 启动", flush=True)
    print("=" * 60, flush=True)

    print("正在读取关键词...", flush=True)
    keywords = load_keywords()

    for kw in keywords:
        print(f"  - {kw}", flush=True)

    papers = []
    source_fetchers = [
        ("arXiv", fetch_arxiv_papers),
        ("Semantic Scholar", fetch_semantic_scholar_papers),
        ("OpenReview", fetch_openreview_papers),
        ("IEEE Xplore", fetch_ieee_xplore_papers),
    ]
    for source_name, fetcher in source_fetchers:
        print(f"\n正在抓取 {source_name} 论文...", flush=True)
        source_papers = fetcher(keywords, max_results=max_results_per_source)
        print(f"{source_name} 原始抓取论文数量：{len(source_papers)}", flush=True)
        papers.extend(source_papers)

    print(f"\n多源原始抓取论文总数：{len(papers)}", flush=True)

    print(f"\n正在筛选最近 {recent_days} 天论文...", flush=True)
    recent_papers = filter_recent_papers(papers, days=recent_days)
    print(f"最近 {recent_days} 天相关论文数量：{len(recent_papers)}", flush=True)

    recent_papers = recent_papers[:max_papers_to_summarize]
    print(f"本次最多总结论文数量：{len(recent_papers)}", flush=True)

    papers_with_summaries = []

    for idx, paper in enumerate(recent_papers, start=1):
        print("\n" + "-" * 60)
        print(f"正在处理第 {idx}/{len(recent_papers)} 篇", flush=True)
        print(paper["title"], flush=True)
        summary, title_zh = summarize_paper(paper)
        print("摘要已生成。", flush=True)

        papers_with_summaries.append({
            "paper": paper,
            "summary": summary,
            "title_zh": title_zh,
        })

    print("\n正在生成 Markdown 报告...", flush=True)
    report_path = render_markdown_report(
        papers_with_summaries,
    )
    print(f"Markdown 日报已生成：{report_path}", flush=True)

    report_text = report_path.read_text(encoding="utf-8")

    if os.getenv("SKIP_FEISHU_NOTIFY", "").lower() in ("1", "true", "yes"):
        print("\n已设置 SKIP_FEISHU_NOTIFY，跳过飞书推送（由 CI 在提交后单独发送）。", flush=True)
    elif not papers_with_summaries:
        print("\n今日无新增文献，跳过飞书推送。", flush=True)
    else:
        print("\n正在推送飞书通知...", flush=True)
        notify_feishu(report_path, len(papers_with_summaries), report_text=report_text)

    print("\n任务完成。", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
