import datetime
import os
import time
import urllib.parse

import feedparser
import requests

DEFAULT_TIMEOUT = 60
DEFAULT_MAX_RETRIES = 4
DEFAULT_KEYWORD_DELAY = 3.5
DEFAULT_COOLDOWN_AFTER_FAIL = 12
# 关键词较多时，合并 OR 查询易超时且易触发 429，直接逐个查更稳
BULK_QUERY_MAX_KEYWORDS = 4


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return float(value)


def _user_agent() -> str:
    contact = os.getenv("ARXIV_CONTACT_EMAIL", "").strip()
    if contact:
        return f"paper-weekly-agent/0.1 (mailto:{contact})"
    return "paper-weekly-agent/0.1 (https://github.com/peinengzhong/paper-weekly-agent)"


def _build_arxiv_url(query: str, max_results: int) -> str:
    encoded_query = urllib.parse.quote(query)
    return (
        "https://export.arxiv.org/api/query?"
        f"search_query={encoded_query}"
        f"&start=0"
        f"&max_results={max_results}"
        f"&sortBy=submittedDate"
        f"&sortOrder=descending"
    )


def _paper_from_entry(entry) -> dict:
    return {
        "title": entry.title.replace("\n", " ").strip(),
        "authors": [author.name for author in entry.authors],
        "summary": entry.summary.replace("\n", " ").strip(),
        "published": entry.published,
        "updated": entry.updated,
        "arxiv_url": entry.link,
        "pdf_url": entry.link.replace("/abs/", "/pdf/") + ".pdf",
        "categories": [tag.term for tag in entry.tags] if hasattr(entry, "tags") else [],
    }


def _parse_arxiv_url(url: str, *, label: str = "") -> tuple[feedparser.FeedParserDict, int | None]:
    """请求 arXiv API，对 429 / 超时 / 5xx 自动退避重试。"""
    timeout = _env_int("ARXIV_REQUEST_TIMEOUT", DEFAULT_TIMEOUT)
    max_retries = _env_int("ARXIV_MAX_RETRIES", DEFAULT_MAX_RETRIES)
    session = requests.Session()
    session.trust_env = False

    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(
                url,
                headers={"User-Agent": _user_agent()},
                timeout=timeout,
            )
        except requests.RequestException as e:
            wait = min(60, 8 * attempt)
            if attempt < max_retries:
                print(
                    f"arXiv 网络异常（{label or 'query'}）：{e}；"
                    f"{wait}s 后重试 ({attempt}/{max_retries})…"
                )
                time.sleep(wait)
                continue
            raise

        if response.status_code == 429:
            wait = min(90, 15 * attempt)
            if attempt < max_retries:
                print(
                    f"arXiv 429 请求过频（{label or 'query'}）；"
                    f"{wait}s 后重试 ({attempt}/{max_retries})…"
                )
                time.sleep(wait)
                continue
            return feedparser.parse(""), 429

        if response.status_code >= 500:
            wait = min(60, 10 * attempt)
            if attempt < max_retries:
                print(
                    f"arXiv 服务端 {response.status_code}（{label or 'query'}）；"
                    f"{wait}s 后重试 ({attempt}/{max_retries})…"
                )
                time.sleep(wait)
                continue
            response.raise_for_status()

        response.raise_for_status()
        return feedparser.parse(response.text), response.status_code

    return feedparser.parse(""), 429


def _entries_from_feed(feed: feedparser.FeedParserDict, label: str) -> list[dict]:
    if getattr(feed, "bozo", False) and not feed.entries:
        print(
            f"arXiv 解析失败（{label}），已跳过："
            f"{getattr(feed, 'bozo_exception', '未知错误')}"
        )
        return []
    if getattr(feed, "bozo", False):
        print(
            f"arXiv 解析警告（{label}），继续处理已返回条目："
            f"{getattr(feed, 'bozo_exception', '未知错误')}"
        )
    return [_paper_from_entry(entry) for entry in feed.entries]


def _fetch_by_keywords(
    keywords: list[str],
    max_results: int,
    *,
    reason: str,
) -> list[dict]:
    papers: list[dict] = []
    per_keyword_limit = max(3, max_results // max(1, len(keywords)))
    delay = _env_float("ARXIV_KEYWORD_DELAY", DEFAULT_KEYWORD_DELAY)
    cooldown = _env_float("ARXIV_COOLDOWN_SECONDS", DEFAULT_COOLDOWN_AFTER_FAIL)

    print(f"按关键词逐个查询 arXiv（{reason}）…")
    if cooldown > 0:
        print(f"等待 {cooldown:.0f}s，避免触发频率限制…")
        time.sleep(cooldown)

    for index, keyword in enumerate(keywords):
        if index > 0:
            time.sleep(delay)

        query = f'all:"{keyword}"'
        label = f"关键词「{keyword}」"
        try:
            feed, status = _parse_arxiv_url(_build_arxiv_url(query, per_keyword_limit), label=label)
        except requests.RequestException as e:
            print(f"{label} 网络失败，已跳过：{e}")
            continue

        if status == 429:
            print(f"{label} 在多次重试后仍返回 429，已跳过。")
            continue

        papers.extend(_entries_from_feed(feed, label))

    return papers


def fetch_arxiv_papers(keywords, max_results=50):
    if not keywords:
        return []

    use_bulk = len(keywords) <= _env_int("ARXIV_BULK_QUERY_MAX_KEYWORDS", BULK_QUERY_MAX_KEYWORDS)

    if use_bulk:
        query = " OR ".join([f'all:"{kw}"' for kw in keywords])
        try:
            feed, status = _parse_arxiv_url(
                _build_arxiv_url(query, max_results),
                label="合并查询",
            )
            if status != 429 and feed.entries:
                return _entries_from_feed(feed, "合并查询")
            if status == 429:
                print("合并查询触发 429，改为按关键词逐个查询。")
        except requests.RequestException as e:
            print(f"arXiv 合并查询失败，改为按关键词逐个查询：{e}")

    return _fetch_by_keywords(keywords, max_results, reason=f"共 {len(keywords)} 个关键词")


def _parse_published_time(published: str):
    """解析 arXiv 发布时间（兼容 Z 后缀与 +00:00 等 ISO 格式）。"""
    text = published.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def filter_recent_papers(papers, days=7):
    now = datetime.datetime.now(datetime.timezone.utc)
    recent = []

    for paper in papers:
        try:
            published_time = _parse_published_time(paper["published"])
        except (ValueError, TypeError):
            continue

        if (now - published_time).days <= days:
            recent.append(paper)

    return recent


def deduplicate_papers(papers):
    seen = set()
    unique_papers = []

    for paper in papers:
        title_key = paper["title"].lower().strip()
        if title_key not in seen:
            seen.add(title_key)
            unique_papers.append(paper)

    return unique_papers
