import os
import time

import requests

OPENREVIEW_API_BASE = "https://api2.openreview.net"
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


def _content_value(content: dict, key: str, default=""):
    value = content.get(key, default)
    if isinstance(value, dict) and "value" in value:
        return value.get("value", default)
    return value


def _authors(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _format_timestamp(ts) -> str:
    try:
        seconds = int(ts) / 1000
    except (TypeError, ValueError):
        return "1970-01-01"
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


def _paper_from_note(note: dict) -> dict | None:
    content = note.get("content") or {}
    title = str(_content_value(content, "title", "") or "").strip()
    if not title:
        return None

    abstract = str(_content_value(content, "abstract", "") or "").strip()
    keywords = _content_value(content, "keywords", []) or []
    venue = str(_content_value(content, "venue", "") or "").strip()
    forum = str(note.get("forum") or note.get("id") or "").strip()
    url = f"https://openreview.net/forum?id={forum}" if forum else "https://openreview.net"
    published = _format_timestamp(note.get("pdate") or note.get("cdate"))

    categories = [str(item).strip() for item in keywords if str(item).strip()] if isinstance(keywords, list) else []
    if venue:
        categories.insert(0, venue)

    return {
        "title": title,
        "authors": _authors(_content_value(content, "authors", [])),
        "summary": abstract or "OpenReview 未提供摘要。",
        "published": published,
        "updated": _format_timestamp(note.get("mdate") or note.get("pdate") or note.get("cdate")),
        "url": url,
        "arxiv_url": "",
        "pdf_url": f"https://openreview.net/pdf?id={forum}" if forum else "",
        "source": "OpenReview",
        "external_id": forum or title,
        "doi": "",
        "categories": categories,
        "skip_recent_filter": True,
    }


def fetch_openreview_papers(keywords: list[str], max_results: int = 30) -> list[dict]:
    if not _env_bool("ENABLE_OPENREVIEW", True):
        print("OpenReview 检索未启用，跳过。", flush=True)
        return []
    if not keywords:
        return []

    timeout = _env_float("OPENREVIEW_TIMEOUT", DEFAULT_TIMEOUT)
    delay = _env_float("OPENREVIEW_KEYWORD_DELAY", DEFAULT_DELAY)
    total_budget = _env_float("OPENREVIEW_TOTAL_TIMEOUT_SECONDS", DEFAULT_TOTAL_FETCH_SECONDS)
    per_keyword_limit = max(1, max_results // max(1, len(keywords)))
    started_at = time.monotonic()
    papers: list[dict] = []

    print("正在抓取 OpenReview 论文...", flush=True)
    for index, keyword in enumerate(keywords):
        elapsed = time.monotonic() - started_at
        if total_budget > 0 and elapsed >= total_budget:
            print(
                f"OpenReview 查询已用 {elapsed:.1f}s，达到总耗时上限 {total_budget:g}s，停止继续查询。",
                flush=True,
            )
            break
        if index > 0:
            time.sleep(delay)

        print(f"开始查询 OpenReview 关键词「{keyword}」({index + 1}/{len(keywords)})。", flush=True)
        try:
            response = requests.get(
                f"{OPENREVIEW_API_BASE}/notes/search",
                params={"term": keyword, "limit": per_keyword_limit, "content": "all"},
                timeout=timeout,
            )
            if response.status_code == 429:
                print("OpenReview 返回 429，停止本轮 OpenReview 查询。", flush=True)
                break
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"OpenReview 关键词「{keyword}」查询失败，已跳过：{exc}", flush=True)
            continue

        for note in response.json().get("notes") or []:
            paper = _paper_from_note(note)
            if paper:
                papers.append(paper)

    print(f"OpenReview 抓取论文数量：{len(papers)}", flush=True)
    return papers
