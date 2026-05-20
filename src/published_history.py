"""记录已发布文献：同日多次运行可重复推送，跨日不重复推送同一篇论文。"""

import hashlib
import json
import re
from datetime import date
from pathlib import Path

HISTORY_PATH = Path("data/published_papers.json")
ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
ARXIV_URL_IN_MD_RE = re.compile(
    r"https://arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?",
    re.I,
)


def extract_arxiv_id(paper: dict) -> str | None:
    url = paper.get("arxiv_url") or paper.get("url") or ""
    match = ARXIV_ID_RE.search(url)
    return match.group(1) if match else None


def _normalize_arxiv_id(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id.strip(), flags=re.I)


def _title_fingerprint(title: str) -> str:
    normalized = re.sub(r"\s+", " ", title).strip().lower()
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"title:{digest}"


def extract_paper_key(paper: dict) -> str:
    arxiv_id = extract_arxiv_id(paper)
    if arxiv_id:
        return f"arxiv:{_normalize_arxiv_id(arxiv_id)}"

    doi = str(paper.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"

    source = re.sub(r"\s+", "-", str(paper.get("source") or "unknown").strip().lower())
    external_id = str(paper.get("external_id") or "").strip()
    if external_id:
        return f"{source}:{external_id}"

    return _title_fingerprint(str(paper.get("title") or ""))


def _load_raw() -> dict:
    if not HISTORY_PATH.exists():
        return {"version": 1, "papers": {}}
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "papers": {}}
    if "papers" not in data or not isinstance(data["papers"], dict):
        data["papers"] = {}
    return data


def _save_raw(data: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def bootstrap_from_report_markdown(*search_dirs: Path) -> int:
    """从历史 Markdown 回填已发布记录（仅当 registry 为空时）。"""
    data = _load_raw()
    if data["papers"]:
        return 0

    dirs = search_dirs or (Path("daily_reports"), Path("weekly_reports"))
    added = 0
    seen_paths: set[Path] = set()
    for report_dir in dirs:
        if not report_dir.is_dir():
            continue
        for md_path in sorted(report_dir.glob("*.md")):
            if md_path in seen_paths:
                continue
            seen_paths.add(md_path)
            text = md_path.read_text(encoding="utf-8")
            for arxiv_id in ARXIV_URL_IN_MD_RE.findall(text):
                key = f"arxiv:{_normalize_arxiv_id(arxiv_id)}"
                legacy_key = _normalize_arxiv_id(arxiv_id)
                if key not in data["papers"] and legacy_key not in data["papers"]:
                    data["papers"][key] = {
                        "title": "",
                        "url": f"https://arxiv.org/abs/{arxiv_id}",
                        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
                        "source": "arXiv",
                        "first_published_on": "imported",
                    }
                    added += 1

    if added:
        _save_raw(data)
    return added


def _is_blocked_on_day(record: dict, today: date) -> bool:
    """非今日已发布（含历史导入）的文献在筛选时跳过；今日已发布的可再次推送。"""
    pub_day = str(record.get("first_published_on", "")).strip()
    if not pub_day or pub_day == "imported":
        return True
    return pub_day != today.isoformat()


def load_published_records() -> dict[str, dict]:
    bootstrap_from_report_markdown()
    return _load_raw()["papers"]


def filter_unpublished(
    papers: list[dict],
    *,
    today: date | None = None,
) -> tuple[list[dict], int]:
    today = today or date.today()
    published = load_published_records()
    fresh = []
    skipped = 0
    for paper in papers:
        paper_key = extract_paper_key(paper)
        legacy_arxiv_id = extract_arxiv_id(paper)
        legacy_arxiv_id = _normalize_arxiv_id(legacy_arxiv_id) if legacy_arxiv_id else None
        published_key = None
        if paper_key in published:
            published_key = paper_key
        elif legacy_arxiv_id and legacy_arxiv_id in published:
            published_key = legacy_arxiv_id

        if published_key and _is_blocked_on_day(published[published_key], today):
            skipped += 1
            continue
        fresh.append(paper)
    return fresh, skipped


def mark_as_published(
    papers: list[dict],
    *,
    published_on: date | None = None,
) -> None:
    if not papers:
        return
    today = published_on or date.today()
    day = today.isoformat()
    data = _load_raw()
    for paper in papers:
        paper_key = extract_paper_key(paper)
        legacy_arxiv_id = extract_arxiv_id(paper)
        legacy_arxiv_id = _normalize_arxiv_id(legacy_arxiv_id) if legacy_arxiv_id else None
        existing_key = paper_key
        if legacy_arxiv_id and legacy_arxiv_id in data["papers"]:
            existing_key = legacy_arxiv_id

        existing = data["papers"].get(existing_key)
        if existing and existing.get("first_published_on") == day:
            existing["title"] = paper.get("title", "")
            existing["url"] = paper.get("url") or paper.get("arxiv_url", "")
            existing["arxiv_url"] = paper.get("arxiv_url", "")
            existing["source"] = paper.get("source", "")
            continue
        if existing and _is_blocked_on_day(existing, today):
            continue
        data["papers"][paper_key] = {
            "title": paper.get("title", ""),
            "url": paper.get("url") or paper.get("arxiv_url", ""),
            "arxiv_url": paper.get("arxiv_url", ""),
            "source": paper.get("source", ""),
            "doi": paper.get("doi", ""),
            "first_published_on": day,
        }
    _save_raw(data)
