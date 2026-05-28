import os
import time
import xml.etree.ElementTree as ET

import requests


SCOPUS_API_URL = "https://api.elsevier.com/content/search/scopus"
SCOPUS_ABSTRACT_API_URL = "https://api.elsevier.com/content/abstract/eid/{eid}"
DEFAULT_TIMEOUT = 20
DEFAULT_DELAY = 1.0
DEFAULT_TOTAL_FETCH_SECONDS = 120
DEFAULT_REQUEST_COUNT = 25


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


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return int(value)


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "User-Agent": "paper-weekly-agent/0.1",
        "X-ELS-APIKey": api_key,
    }


def _normalize_date(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return "1970-01-01"
    if value.isdigit() and len(value) == 4:
        return f"{value}-01-01"
    if len(value) == 7 and value[4] == "-":
        return f"{value}-01"
    return value


def _authors(item: dict) -> list[str]:
    authors = item.get("author") or []
    if not isinstance(authors, list):
        authors = []

    names: list[str] = []
    for author in authors:
        if isinstance(author, dict):
            name = str(
                author.get("authname")
                or author.get("ce:indexed-name")
                or author.get("preferred-name")
                or author.get("surname")
                or author.get("given-name")
                or ""
            ).strip()
        else:
            name = str(author).strip()
        if name:
            names.append(name)

    if names:
        return names

    creator = str(item.get("dc:creator") or "").strip()
    return [creator] if creator else []


def _abstract_text_from_xml(payload: str) -> str:
    if not payload.strip():
        return ""

    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return ""

    candidates: list[str] = []
    for element in root.iter():
        tag = element.tag.split("}", 1)[-1].lower()
        if tag in {"description", "abstract", "dc:description"}:
            text = "".join(part.strip() for part in element.itertext()).strip()
            if text:
                candidates.append(text)

    if candidates:
        return max(candidates, key=len)

    return ""


def fetch_abstract(api_key: str, eid: str) -> str:
    if not eid:
        return "Scopus 未提供摘要。"

    response = requests.get(
        SCOPUS_ABSTRACT_API_URL.format(eid=eid),
        headers={
            "Accept": "application/xml",
            "X-ELS-APIKey": api_key,
            "User-Agent": "paper-weekly-agent/0.1",
        },
        params={"view": "META_ABS"},
        timeout=30,
    )

    if response.status_code in {401, 403, 404, 429}:
        return "Scopus 未提供摘要。"
    response.raise_for_status()

    abstract = _abstract_text_from_xml(response.text)
    return abstract or "Scopus 未提供摘要。"


def _paper_from_item(item: dict, api_key: str) -> dict | None:
    title = str(item.get("dc:title") or "").strip()
    if not title:
        return None

    doi = str(item.get("prism:doi") or item.get("doi") or "").strip()
    eid = str(item.get("eid") or "").strip()
    url = str(item.get("prism:url") or "").strip()
    if not url and eid:
        url = f"https://www.scopus.com/record/display.uri?eid={eid}"
    if not url and doi:
        url = f"https://doi.org/{doi}"

    publication_name = str(item.get("prism:publicationName") or "").strip()
    subtype = str(item.get("subtypeDescription") or "").strip()
    cited_by = str(item.get("citedby-count") or "").strip()
    categories = [value for value in [publication_name, subtype, f"Cited by: {cited_by}" if cited_by else ""] if value]

    cover_date = str(item.get("prism:coverDate") or item.get("coverDate") or "").strip()
    summary = str(item.get("dc:description") or item.get("description") or "").strip()
    if not summary:
        summary = fetch_abstract(api_key, eid)
    if not summary:
        summary = "Scopus 未提供摘要。"

    return {
        "title": title,
        "authors": _authors(item),
        "summary": summary,
        "published": _normalize_date(cover_date),
        "updated": _normalize_date(cover_date),
        "url": url,
        "arxiv_url": "",
        "pdf_url": "",
        "source": "Scopus",
        "external_id": eid or doi or title,
        "doi": doi,
        "categories": categories,
        "skip_recent_filter": True,
    }


def _build_query(keyword: str) -> str:
    escaped = keyword.replace('"', '\\"').strip()
    return f'TITLE-ABS-KEY("{escaped}")'


def _fetch_entries(api_key: str, keyword: str, timeout: float, per_keyword_limit: int) -> list[dict]:
    collected: list[dict] = []
    start = 0
    request_count = _env_int("SCOPUS_MAX_RECORDS_PER_REQUEST", DEFAULT_REQUEST_COUNT)
    page_size = max(1, min(request_count, per_keyword_limit))

    while len(collected) < per_keyword_limit:
        remaining = per_keyword_limit - len(collected)
        count = min(page_size, remaining)
        response = requests.get(
            SCOPUS_API_URL,
            params={
                "query": _build_query(keyword),
                "start": start,
                "count": count,
                "sort": "-coverDate",
                "view": "STANDARD",
                "suppressNavLinks": "true",
            },
            headers=_headers(api_key),
            timeout=timeout,
        )
        if response.status_code == 429:
            print("Scopus 返回 429，停止本轮 Scopus 查询。", flush=True)
            break
        response.raise_for_status()

        payload = response.json()
        entries = []
        search_results = payload.get("search-results") or {}
        if isinstance(search_results, dict):
            entries = search_results.get("entry") or []
        if not isinstance(entries, list):
            entries = []

        if not entries:
            break

        for item in entries:
            if not isinstance(item, dict):
                continue
            paper = _paper_from_item(item, api_key)
            if paper:
                collected.append(paper)
                if len(collected) >= per_keyword_limit:
                    break

        if len(entries) < count:
            break

        start += len(entries)

    return collected


def fetch_scopus_papers(keywords: list[str], max_results: int = 30) -> list[dict]:
    if not _env_bool("ENABLE_SCOPUS", True):
        print("Scopus 检索未启用，跳过。", flush=True)
        return []

    api_key = os.getenv("SCOPUS_API_KEY", "").strip()
    if not api_key:
        print("未配置 SCOPUS_API_KEY，跳过 Scopus 检索。", flush=True)
        return []
    if not keywords:
        return []

    timeout = _env_float("SCOPUS_TIMEOUT", DEFAULT_TIMEOUT)
    delay = _env_float("SCOPUS_KEYWORD_DELAY", DEFAULT_DELAY)
    total_budget = _env_float("SCOPUS_TOTAL_TIMEOUT_SECONDS", DEFAULT_TOTAL_FETCH_SECONDS)
    per_keyword_limit = max(1, max_results // max(1, len(keywords)))
    started_at = time.monotonic()
    papers: list[dict] = []

    print("正在抓取 Scopus 论文...", flush=True)
    for index, keyword in enumerate(keywords):
        elapsed = time.monotonic() - started_at
        if total_budget > 0 and elapsed >= total_budget:
            print(
                f"Scopus 查询已用 {elapsed:.1f}s，达到总耗时上限 {total_budget:g}s，停止继续查询。",
                flush=True,
            )
            break
        if index > 0:
            time.sleep(delay)

        print(f"开始查询 Scopus 关键词「{keyword}」({index + 1}/{len(keywords)})。", flush=True)
        try:
            papers.extend(_fetch_entries(api_key, keyword, timeout, per_keyword_limit))
        except requests.RequestException as exc:
            print(f"Scopus 关键词「{keyword}」查询失败，已跳过：{exc}", flush=True)
            continue
        except ValueError as exc:
            print(f"Scopus 关键词「{keyword}」返回内容解析失败，已跳过：{exc}", flush=True)
            continue

    print(f"Scopus 抓取论文数量：{len(papers)}", flush=True)
    return papers
