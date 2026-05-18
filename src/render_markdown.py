import datetime
from pathlib import Path


def render_markdown_report(papers_with_summaries):
    today = datetime.date.today()
    year, week, _ = today.isocalendar()

    title = f"{year}年第{week}周 AI/机器人/具身智能文献周报"
    filename = f"{year}-W{week:02d}-paper-weekly.md"
    output_path = Path("output") / filename

    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# {title}\n")
    lines.append(f"> 生成日期：{today}\n")
    lines.append("---\n")

    if not papers_with_summaries:
        lines.append("本次未检索到符合关键词的论文。\n")
    else:
        lines.append(f"本次共筛选出 {len(papers_with_summaries)} 篇相关论文。\n")

    for idx, item in enumerate(papers_with_summaries, start=1):
        paper = item["paper"]
        summary = item["summary"]

        lines.append(f"\n## {idx}. {paper['title']}\n")
        lines.append(f"- 作者：{', '.join(paper['authors'])}\n")
        lines.append(f"- 发布时间：{paper['published']}\n")
        lines.append(f"- arXiv 链接：{paper['arxiv_url']}\n")
        lines.append(f"- PDF 链接：{paper['pdf_url']}\n")

        if paper["categories"]:
            lines.append(f"- 分类：{', '.join(paper['categories'])}\n")

        lines.append("\n### 摘要\n")
        lines.append(summary)
        lines.append("\n---\n")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
