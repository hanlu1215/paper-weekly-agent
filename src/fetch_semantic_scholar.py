import os
import time

import requests

SEMANTIC_SCHOLAR_API_BASE = "https://api.semanticscholar.org/graph/v1"
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


def _headers() -> dict[str, str]:
    headers = {"User-Agent": "paper-weekly-agent/0.1"}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _authors(items: list[dict]) -> list[str]:
    return [str(item.get("name", "")).strip() for item in items if str(item.get("name", "")).strip()]


def _paper_from_item(item: dict) -> dict | None:
    title = str(item.get("title") or "").strip()
    if not title:
        return None

    external_ids = item.get("externalIds") or {}
    arxiv_id = str(external_ids.get("ArXiv") or "").strip()
    doi = str(external_ids.get("DOI") or "").strip()
    url = str(item.get("url") or "").strip()
    if arxiv_id and not url:
        url = f"https://arxiv.org/abs/{arxiv_id}"

    pdf_url = ""
    open_access_pdf = item.get("openAccessPdf") or {}
    if isinstance(open_access_pdf, dict):
        pdf_url = str(open_access_pdf.get("url") or "").strip()

    published = str(item.get("publicationDate") or "").strip()
    if not published and item.get("year"):
        published = f"{item['year']}-01-01"
    if not published:
        published = "1970-01-01"

    fields = item.get("fieldsOfStudy") or []
    venue = str(item.get("venue") or "").strip()
    categories = [str(field).strip() for field in fields if str(field).strip()]
    if venue:
        categories.insert(0, venue)

    return {
        "title": title,
        "authors": _authors(item.get("authors") or []),
        "summary": str(item.get("abstract") or "Semantic Scholar 未提供摘要。").strip(),
        "published": published,
        "updated": published,
        "url": url,
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
        "pdf_url": pdf_url,
        "source": "Semantic Scholar",
        "external_id": str(item.get("paperId") or arxiv_id or doi or title).strip(),
        "doi": doi,
        "categories": categories,
    }


def fetch_semantic_scholar_papers(keywords: list[str], max_results: int = 30) -> list[dict]:
    if not _env_bool("ENABLE_SEMANTIC_SCHOLAR", True):
        print("Semantic Scholar 检索未启用，跳过。", flush=True)
        return []
    if not keywords:
        return []

    timeout = _env_float("SEMANTIC_SCHOLAR_TIMEOUT", DEFAULT_TIMEOUT)
    delay = _env_float("SEMANTIC_SCHOLAR_KEYWORD_DELAY", DEFAULT_DELAY)
    total_budget = _env_float("SEMANTIC_SCHOLAR_TOTAL_TIMEOUT_SECONDS", DEFAULT_TOTAL_FETCH_SECONDS)
    per_keyword_limit = max(1, max_results // max(1, len(keywords)))
    started_at = time.monotonic()
    papers: list[dict] = []

    print("正在抓取 Semantic Scholar 论文...", flush=True)
    for index, keyword in enumerate(keywords):
        elapsed = time.monotonic() - started_at
        if total_budget > 0 and elapsed >= total_budget:
            print(
                f"Semantic Scholar 查询已用 {elapsed:.1f}s，达到总耗时上限 {total_budget:g}s，停止继续查询。",
                flush=True,
            )
            break
        if index > 0:
            time.sleep(delay)

        print(f"开始查询 Semantic Scholar 关键词「{keyword}」({index + 1}/{len(keywords)})。", flush=True)
        try:
            response = requests.get(
                f"{SEMANTIC_SCHOLAR_API_BASE}/paper/search",
                params={
                    "query": keyword,
                    "limit": per_keyword_limit,
                    "fields": "title,abstract,authors,year,publicationDate,url,externalIds,venue,fieldsOfStudy,openAccessPdf",
                },
                headers=_headers(),
                timeout=timeout,
            )
            if response.status_code == 429:
                print("Semantic Scholar 返回 429，停止本轮 Semantic Scholar 查询。", flush=True)
                break
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"Semantic Scholar 关键词「{keyword}」查询失败，已跳过：{exc}", flush=True)
            continue

        for item in response.json().get("data") or []:
            paper = _paper_from_item(item)
            if paper:
                papers.append(paper)

    print(f"Semantic Scholar 抓取论文数量：{len(papers)}", flush=True)
    return papers
