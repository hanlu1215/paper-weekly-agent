import os
import time

import requests

IEEE_XPLORE_API_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
DEFAULT_TIMEOUT = 20
DEFAULT_DELAY = 1.0
DEFAULT_TOTAL_FETCH_SECONDS = 120


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return float(value)


def _authors(item: dict) -> list[str]:
    authors = item.get("authors") or {}
    if isinstance(authors, dict):
        authors = authors.get("authors") or []
    if not isinstance(authors, list):
        return []
    names = []
    for author in authors:
        if isinstance(author, dict):
            name = str(author.get("full_name") or author.get("name") or "").strip()
        else:
            name = str(author).strip()
        if name:
            names.append(name)
    return names


def _paper_from_item(item: dict) -> dict | None:
    title = str(item.get("title") or "").strip()
    if not title:
        return None

    published = str(
        item.get("publication_date")
        or item.get("publication_year")
        or item.get("conference_dates")
        or "1970-01-01"
    ).strip()
    if published.isdigit() and len(published) == 4:
        published = f"{published}-01-01"

    doi = str(item.get("doi") or "").strip()
    pdf_url = str(item.get("pdf_url") or "").strip()
    url = str(item.get("html_url") or item.get("abstract_url") or "").strip()
    if not url and doi:
        url = f"https://doi.org/{doi}"

    categories = []
    publication_title = str(item.get("publication_title") or "").strip()
    content_type = str(item.get("content_type") or "").strip()
    if publication_title:
        categories.append(publication_title)
    if content_type:
        categories.append(content_type)

    return {
        "title": title,
        "authors": _authors(item),
        "summary": str(item.get("abstract") or "IEEE Xplore 未提供摘要。").strip(),
        "published": published,
        "updated": published,
        "url": url,
        "arxiv_url": "",
        "pdf_url": pdf_url,
        "source": "IEEE Xplore",
        "external_id": str(item.get("article_number") or doi or title).strip(),
        "doi": doi,
        "categories": categories,
    }


def fetch_ieee_xplore_papers(keywords: list[str], max_results: int = 30) -> list[dict]:
    api_key = os.getenv("IEEE_XPLORE_API_KEY", "").strip()
    if not _env_bool("ENABLE_IEEE_XPLORE", True):
        print("IEEE Xplore 检索未启用，跳过。", flush=True)
        return []
    if not api_key:
        print("未配置 IEEE_XPLORE_API_KEY，跳过 IEEE Xplore 检索。", flush=True)
        return []
    if not keywords:
        return []

    timeout = _env_float("IEEE_XPLORE_TIMEOUT", DEFAULT_TIMEOUT)
    delay = _env_float("IEEE_XPLORE_KEYWORD_DELAY", DEFAULT_DELAY)
    total_budget = _env_float("IEEE_XPLORE_TOTAL_TIMEOUT_SECONDS", DEFAULT_TOTAL_FETCH_SECONDS)
    per_keyword_limit = max(1, max_results // max(1, len(keywords)))
    started_at = time.monotonic()
    papers: list[dict] = []

    print("正在抓取 IEEE Xplore 论文...", flush=True)
    for index, keyword in enumerate(keywords):
        elapsed = time.monotonic() - started_at
        if total_budget > 0 and elapsed >= total_budget:
            print(
                f"IEEE Xplore 查询已用 {elapsed:.1f}s，达到总耗时上限 {total_budget:g}s，停止继续查询。",
                flush=True,
            )
            break
        if index > 0:
            time.sleep(delay)

        print(f"开始查询 IEEE Xplore 关键词「{keyword}」({index + 1}/{len(keywords)})。", flush=True)
        try:
            response = requests.get(
                IEEE_XPLORE_API_URL,
                params={
                    "apikey": api_key,
                    "format": "json",
                    "querytext": keyword,
                    "max_records": per_keyword_limit,
                    "sort_field": "publication_year",
                    "sort_order": "desc",
                },
                timeout=timeout,
            )
            if response.status_code == 429:
                print("IEEE Xplore 返回 429，停止本轮 IEEE Xplore 查询。", flush=True)
                break
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"IEEE Xplore 关键词「{keyword}」查询失败，已跳过：{exc}", flush=True)
            continue

        for item in response.json().get("articles") or []:
            paper = _paper_from_item(item)
            if paper:
                papers.append(paper)

    print(f"IEEE Xplore 抓取论文数量：{len(papers)}", flush=True)
    return papers
