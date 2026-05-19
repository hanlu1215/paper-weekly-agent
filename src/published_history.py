"""记录已发布文献，避免每日重复推送同一篇 arXiv 论文。"""

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
    url = paper.get("arxiv_url") or ""
    match = ARXIV_ID_RE.search(url)
    return match.group(1) if match else None


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


def bootstrap_from_output_markdown(*search_dirs: Path) -> int:
    """从历史 Markdown 回填已发布记录（仅当 registry 为空时）。"""
    data = _load_raw()
    if data["papers"]:
        return 0

    dirs = search_dirs or (Path("daily_reports"), Path("weekly_reports"), Path("output"))
    added = 0
    seen_paths: set[Path] = set()
    for output_dir in dirs:
        if not output_dir.is_dir():
            continue
        for md_path in sorted(output_dir.glob("*.md")):
            if md_path in seen_paths:
                continue
            seen_paths.add(md_path)
            text = md_path.read_text(encoding="utf-8")
            for arxiv_id in ARXIV_URL_IN_MD_RE.findall(text):
                if arxiv_id not in data["papers"]:
                    data["papers"][arxiv_id] = {
                        "title": "",
                        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
                        "first_published_on": "imported",
                    }
                    added += 1

    if added:
        _save_raw(data)
    return added


def load_published_ids() -> set[str]:
    bootstrap_from_output_markdown()
    return set(_load_raw()["papers"].keys())


def filter_unpublished(papers: list[dict]) -> tuple[list[dict], int]:
    published = load_published_ids()
    fresh = []
    skipped = 0
    for paper in papers:
        arxiv_id = extract_arxiv_id(paper)
        if arxiv_id and arxiv_id in published:
            skipped += 1
            continue
        fresh.append(paper)
    return fresh, skipped


def mark_as_published(papers: list[dict], *, published_on: date | None = None) -> None:
    if not papers:
        return
    day = (published_on or date.today()).isoformat()
    data = _load_raw()
    for paper in papers:
        arxiv_id = extract_arxiv_id(paper)
        if not arxiv_id:
            continue
        data["papers"][arxiv_id] = {
            "title": paper.get("title", ""),
            "arxiv_url": paper.get("arxiv_url", ""),
            "first_published_on": day,
        }
    _save_raw(data)
