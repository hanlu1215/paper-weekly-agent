import datetime
import feedparser
import requests
import time
import urllib.parse


def _build_arxiv_url(query, max_results):
    encoded_query = urllib.parse.quote(query)
    return (
        "https://export.arxiv.org/api/query?"
        f"search_query={encoded_query}"
        f"&start=0"
        f"&max_results={max_results}"
        f"&sortBy=submittedDate"
        f"&sortOrder=descending"
    )


def _paper_from_entry(entry):
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


def _parse_arxiv_url(url):
    session = requests.Session()
    session.trust_env = False

    response = session.get(
        url,
        headers={"User-Agent": "paper-weekly-agent/0.1"},
        timeout=30,
    )

    if response.status_code == 429:
        return feedparser.parse(""), 429

    response.raise_for_status()
    return feedparser.parse(response.text), response.status_code


def fetch_arxiv_papers(keywords, max_results=50):
    query = " OR ".join([f'all:"{kw}"' for kw in keywords])
    try:
        feed, status = _parse_arxiv_url(_build_arxiv_url(query, max_results))
    except requests.RequestException as e:
        feed = feedparser.parse("")
        status = None
        print(f"arXiv 总查询网络失败，尝试按关键词逐个查询：{e}")

    if status == 429:
        print("arXiv API 当前返回 429：请求过于频繁，请稍等几分钟后重试。")
        return []

    if feed.entries:
        if getattr(feed, "bozo", False):
            print(f"arXiv API 解析警告，继续处理已返回条目：{getattr(feed, 'bozo_exception', '未知错误')}")
        return [_paper_from_entry(entry) for entry in feed.entries]

    if getattr(feed, "bozo", False):
        print(
            "arXiv 总查询失败，尝试按关键词逐个查询："
            f"{getattr(feed, 'bozo_exception', '未知错误')}"
        )

    papers = []
    per_keyword_limit = max(1, max_results // max(1, len(keywords)))

    for keyword in keywords:
        query = f'all:"{keyword}"'
        try:
            feed, status = _parse_arxiv_url(_build_arxiv_url(query, per_keyword_limit))
        except requests.RequestException as e:
            print(f"关键词“{keyword}”网络失败，已跳过：{e}")
            continue

        if status == 429:
            print("arXiv API 当前返回 429：请求过于频繁，请稍等几分钟后重试。")
            break

        if getattr(feed, "bozo", False) and not feed.entries:
            print(
                f"关键词“{keyword}”抓取失败，已跳过："
                f"{getattr(feed, 'bozo_exception', '未知错误')}"
            )
            continue

        if getattr(feed, "bozo", False):
            print(
                f"关键词“{keyword}”解析警告，继续处理已返回条目："
                f"{getattr(feed, 'bozo_exception', '未知错误')}"
            )

        for entry in feed.entries:
            papers.append(_paper_from_entry(entry))

        time.sleep(3.2)

    return papers


def filter_recent_papers(papers, days=7):
    now = datetime.datetime.now(datetime.timezone.utc)
    recent = []

    for paper in papers:
        try:
            published_time = datetime.datetime.strptime(
                paper["published"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=datetime.timezone.utc)
        except ValueError:
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
