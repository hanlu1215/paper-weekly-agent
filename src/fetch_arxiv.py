import datetime
import os
import time
import urllib.parse

import feedparser
import requests

DEFAULT_TIMEOUT = 60
DEFAULT_CONNECT_TIMEOUT = 15
DEFAULT_MAX_RETRIES = 4
DEFAULT_KEYWORD_DELAY = 5.0
DEFAULT_COOLDOWN_AFTER_FAIL = 3
DEFAULT_TOTAL_FETCH_SECONDS = 600
# 合并 OR 查询易触发 429；默认禁用，始终按关键词逐个查询
BULK_QUERY_MAX_KEYWORDS = 0


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
    # 使用 quote_plus，与 arXiv API 文档一致（空格 → +）
    encoded_query = urllib.parse.quote_plus(query, safe="():\"")
    return (
        "https://export.arxiv.org/api/query?"
        f"search_query={encoded_query}"
        f"&start=0"
        f"&max_results={max_results}"
        f"&sortBy=submittedDate"
        f"&sortOrder=descending"
    )


def _request_timeouts() -> tuple[float, float]:
    read_timeout = _env_float("ARXIV_REQUEST_TIMEOUT", DEFAULT_TIMEOUT)
    connect_timeout = _env_float("ARXIV_CONNECT_TIMEOUT", DEFAULT_CONNECT_TIMEOUT)
    return (connect_timeout, read_timeout)


def _retry_after_seconds(response: requests.Response | None) -> int | None:
    if response is None:
        return None
    raw = response.headers.get("Retry-After", "").strip()
    if not raw:
        return None
    try:
        return max(1, int(raw))
    except ValueError:
        return None


def _dedupe_papers(papers: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for paper in papers:
        key = (
            paper.get("external_id")
            or paper.get("arxiv_url")
            or paper.get("url")
            or paper.get("title")
        )
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(paper)
    return unique


def _paper_from_entry(entry) -> dict:
    arxiv_url = entry.link
    arxiv_id = arxiv_url.rstrip("/").split("/")[-1]
    return {
        "title": entry.title.replace("\n", " ").strip(),
        "authors": [author.name for author in entry.authors],
        "summary": entry.summary.replace("\n", " ").strip(),
        "published": entry.published,
        "updated": entry.updated,
        "url": arxiv_url,
        "arxiv_url": arxiv_url,
        "pdf_url": arxiv_url.replace("/abs/", "/pdf/") + ".pdf",
        "source": "arXiv",
        "external_id": arxiv_id,
        "doi": "",
        "categories": [tag.term for tag in entry.tags] if hasattr(entry, "tags") else [],
    }


def _parse_arxiv_url(url: str, *, label: str = "") -> tuple[feedparser.FeedParserDict, int | None]:
    """请求 arXiv API，对 429 / 超时 / 5xx 自动退避重试。"""
    timeouts = _request_timeouts()
    max_retries = _env_int("ARXIV_MAX_RETRIES", DEFAULT_MAX_RETRIES)
    session = requests.Session()
    session.trust_env = False

    for attempt in range(1, max_retries + 1):
        print(
            f"arXiv 请求开始（{label or 'query'}，第 {attempt}/{max_retries} 次，"
            f"timeout={timeouts[1]}s）...",
            flush=True,
        )
        response: requests.Response | None = None
        try:
            response = session.get(
                url,
                headers={"User-Agent": _user_agent()},
                timeout=timeouts,
            )
        except requests.RequestException as e:
            wait = min(90, 10 * attempt)
            if attempt < max_retries:
                print(
                    f"arXiv 网络异常（{label or 'query'}）：{e}；"
                    f"{wait}s 后重试 ({attempt}/{max_retries})…",
                    flush=True,
                )
                time.sleep(wait)
                continue
            raise

        if response.status_code == 429:
            retry_after = _retry_after_seconds(response)
            wait = retry_after or min(120, 20 * attempt)
            if attempt < max_retries:
                print(
                    f"arXiv 429 请求过频（{label or 'query'}）；"
                    f"{wait}s 后重试 ({attempt}/{max_retries})…",
                    flush=True,
                )
                time.sleep(wait)
                continue
            return feedparser.parse(""), 429

        if response.status_code >= 500:
            wait = min(60, 10 * attempt)
            if attempt < max_retries:
                print(
                    f"arXiv 服务端 {response.status_code}（{label or 'query'}）；"
                    f"{wait}s 后重试 ({attempt}/{max_retries})…",
                    flush=True,
                )
                time.sleep(wait)
                continue
            response.raise_for_status()

        response.raise_for_status()
        print(
            f"arXiv 请求完成（{label or 'query'}，HTTP {response.status_code}）。",
            flush=True,
        )
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
    base_delay = _env_float("ARXIV_KEYWORD_DELAY", DEFAULT_KEYWORD_DELAY)
    inter_keyword_delay = base_delay
    cooldown = _env_float("ARXIV_COOLDOWN_SECONDS", DEFAULT_COOLDOWN_AFTER_FAIL)
    total_budget = _env_float("ARXIV_TOTAL_TIMEOUT_SECONDS", DEFAULT_TOTAL_FETCH_SECONDS)
    started_at = time.monotonic()
    failed_keywords: list[str] = []

    print(f"按关键词逐个查询 arXiv（{reason}）…", flush=True)
    if cooldown > 0:
        print(f"等待 {cooldown:.0f}s，避免触发频率限制…", flush=True)
        time.sleep(cooldown)

    for index, keyword in enumerate(keywords):
        elapsed = time.monotonic() - started_at
        if total_budget > 0 and elapsed >= total_budget:
            print(
                f"arXiv 查询已用 {elapsed:.1f}s，达到总耗时上限 {total_budget:g}s，"
                f"停止继续查询关键词（已收集 {len(papers)} 篇）。",
                flush=True,
            )
            break

        if index > 0 and inter_keyword_delay > 0:
            print(f"等待 {inter_keyword_delay:.1f}s 后查询下一个关键词…", flush=True)
            time.sleep(inter_keyword_delay)

        query = f'all:"{keyword}"'
        label = f"关键词「{keyword}」"
        print(f"开始查询 {label} ({index + 1}/{len(keywords)})。", flush=True)
        try:
            feed, status = _parse_arxiv_url(_build_arxiv_url(query, per_keyword_limit), label=label)
        except requests.RequestException as e:
            print(f"{label} 网络失败，已跳过：{e}", flush=True)
            failed_keywords.append(keyword)
            inter_keyword_delay = min(30.0, inter_keyword_delay + base_delay)
            continue

        if status == 429:
            print(f"{label} 在多次重试后仍返回 429，已跳过。", flush=True)
            failed_keywords.append(keyword)
            inter_keyword_delay = min(30.0, inter_keyword_delay + base_delay * 2)
            continue

        batch = _entries_from_feed(feed, label)
        papers.extend(batch)
        if batch:
            inter_keyword_delay = base_delay

    if failed_keywords:
        print(
            f"arXiv 有 {len(failed_keywords)} 个关键词未成功：{', '.join(failed_keywords[:5])}"
            f"{'…' if len(failed_keywords) > 5 else ''}",
            flush=True,
        )

    return _dedupe_papers(papers)


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
                return _dedupe_papers(_entries_from_feed(feed, "合并查询"))
            if status == 429:
                print("合并查询触发 429，改为按关键词逐个查询。", flush=True)
        except requests.RequestException as e:
            print(f"arXiv 合并查询失败，改为按关键词逐个查询：{e}", flush=True)

    return _fetch_by_keywords(keywords, max_results, reason=f"共 {len(keywords)} 个关键词")


def _parse_published_time(published: str):
    """解析 arXiv 发布时间（兼容 Z 后缀与 +00:00 等 ISO 格式）。"""
    text = published.strip()
    if len(text) == 4 and text.isdigit():
        text = f"{text}-01-01"
    elif len(text) == 7 and text[:4].isdigit() and text[4] == "-" and text[5:].isdigit():
        text = f"{text}-01"
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    dt = None
    try:
        dt = datetime.datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%d %B %Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                dt = datetime.datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        raise ValueError(f"无法解析发布时间：{published}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def filter_recent_papers(papers, days=7):
    now = datetime.datetime.now(datetime.timezone.utc)
    recent = []
    skipped_by_date = 0
    kept_without_date_filter = 0

    for paper in papers:
        if paper.get("skip_recent_filter"):
            recent.append(paper)
            kept_without_date_filter += 1
            continue

        try:
            published_time = _parse_published_time(paper["published"])
        except (ValueError, TypeError):
            skipped_by_date += 1
            continue

        if (now - published_time).days <= days:
            recent.append(paper)
        else:
            skipped_by_date += 1

    if kept_without_date_filter:
        print(f"其中 {kept_without_date_filter} 篇来源标记为跳过日期过滤，已保留。", flush=True)
    if skipped_by_date:
        print(f"因发布时间超过 {days} 天或无法解析，已过滤 {skipped_by_date} 篇。", flush=True)

    return recent

