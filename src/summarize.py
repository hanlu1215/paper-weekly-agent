import os
import re
import time

import requests

_CHINESE_TITLE_RE = re.compile(
    r"^\*\*中文标题[：:]\*\*\s*(.+?)\s*$",
    re.MULTILINE,
)


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
DEFAULT_DEEPSEEK_MAX_TOKENS = 1400
DEFAULT_DEEPSEEK_TEMPERATURE = 0.2
DEFAULT_DEEPSEEK_TIMEOUT = 60


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return value.strip()


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


def _build_deepseek_messages(paper):
    authors = ", ".join(paper["authors"])
    categories = ", ".join(paper.get("categories", [])) or "N/A"
    source = paper.get("source") or "未知来源"
    paper_url = paper.get("url") or paper.get("arxiv_url") or ""
    user_content = f"""请阅读下面这篇论文信息，并用中文生成一份适合「文献每日速递」的 AI 总结。

标题：{paper["title"]}
作者：{authors}
来源：{source}
分类：{categories}
发布时间：{paper["published"]}
论文链接：{paper_url}
原始摘要：
{paper["summary"]}

输出最开头单独一行（必须在 ### AI 总结 之前）：
**中文标题：** （将英文标题翻译为简洁准确的中文题目，不超过 40 字）

请严格按以下 Markdown 结构输出，整体控制在 350-550 个中文字符：
### AI 总结

**研究背景：**  
请根据论文标题和摘要，组织成一段自然连贯的中文表述，说明该研究是由什么现象、应用需求或技术趋势引出的；现有方法、系统或研究路线存在哪些不足，尤其是同行方法为什么还不能充分解决该问题；进一步说明论文核心想解决的问题及其研究意义。要求只能基于标题和摘要进行归纳，不要机械分点，不要编造摘要中没有的信息。

**研究思路：**  
按照“问题动机 → 方法思路 → 解决问题 → 验证方式 → 主要结论”的逻辑概括论文内容。需要说明作者为什么提出该方法、方法大致如何工作、它试图解决哪些关键困难、论文如何验证有效性，以及摘要中体现出的主要结论。只能基于标题、摘要和已有总结进行合理归纳，不要虚构论文真实章节结构或摘要未出现的实验细节。

**局限性：**  
请基于摘要内容谨慎分析论文可能存在的局限、不确定性或后续仍需验证的问题，例如适用场景是否有限、实验验证是否充分、是否依赖特定数据/仿真环境/模型假设、是否缺少真实系统验证等。若摘要中没有足够信息判断局限性，请明确说明“摘要中未提供足够信息判断具体局限性”，不要凭空猜测。

**值得关注：**  
说明这篇论文对 AI、机器人、具身智能、自动驾驶或后续研究可能带来的启发，包括可借鉴的方法、任务设定、评价方式、系统设计思路或研究趋势。要求结合论文主题进行具体表述，不要写成泛泛的行业评论。
"""

    return [
        {
            "role": "system",
            "content": (
                "你是严谨的 AI/机器人/具身智能论文阅读助手。"
                "你擅长把论文讲成有背景、有脉络的行业分析。"
                "总结必须忠实于给定标题和摘要；缺少证据时要写“摘要未说明”，不要编造实验、数据或真实章节标题。"
            ),
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]


def _call_deepseek(paper):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if api_key is not None:
        api_key = api_key.strip()

    if not api_key:
        print("未配置 DEEPSEEK_API_KEY，使用 arXiv 原文摘要。")
        return None

    base_url = _env_str("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL).rstrip("/")
    model = _env_str("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
    max_tokens = _env_int("DEEPSEEK_MAX_TOKENS", DEFAULT_DEEPSEEK_MAX_TOKENS)
    temperature = _env_float("DEEPSEEK_TEMPERATURE", DEFAULT_DEEPSEEK_TEMPERATURE)
    timeout = _env_float("DEEPSEEK_TIMEOUT", DEFAULT_DEEPSEEK_TIMEOUT)

    payload = {
        "model": model,
        "messages": _build_deepseek_messages(paper),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    print(f"正在请求 DeepSeek（model={model}, timeout={timeout:g}s）...", flush=True)
    started_at = time.monotonic()
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    elapsed = time.monotonic() - started_at
    print(f"DeepSeek 响应完成，用时 {elapsed:.1f}s。", flush=True)

    return data["choices"][0]["message"]["content"].strip()


def _extract_chinese_title(text: str) -> tuple[str, str]:
    match = _CHINESE_TITLE_RE.search(text)
    if not match:
        return "", text
    title_zh = match.group(1).strip()
    cleaned = _CHINESE_TITLE_RE.sub("", text, count=1).lstrip("\n")
    return title_zh, cleaned


def summarize_paper(paper) -> tuple[str, str]:
    """返回 (总结正文, 中文标题)；无 AI 总结时中文标题为空。"""
    try:
        summary = _call_deepseek(paper)
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        print(f"DeepSeek 摘要生成失败，使用 arXiv 原文摘要：{e}")
        summary = None

    if summary:
        title_zh, summary = _extract_chinese_title(summary)
        return summary, title_zh

    return paper["summary"], ""
