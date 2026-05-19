import os

import requests


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
DEFAULT_DEEPSEEK_MAX_TOKENS = 1400
DEFAULT_DEEPSEEK_TEMPERATURE = 0.2


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
    user_content = f"""请阅读下面这篇 arXiv 论文信息，并用中文生成一份适合行业文献周报的 AI 总结。

标题：{paper["title"]}
作者：{authors}
分类：{categories}
发布时间：{paper["published"]}
arXiv 链接：{paper["arxiv_url"]}
原始摘要：
{paper["summary"]}

请严格按以下 Markdown 结构输出，整体控制在 350-550 个中文字符：
### AI 总结

**故事背景：**  
请从以下四个角度概括论文的研究背景，但不要机械分点罗列，而要组织成一段自然连贯的中文表述：  
1. 该研究面向什么应用背景或技术场景；  
2. 现有方法、系统或研究路线存在哪些不足；  
3. 作者为什么认为这个问题值得研究，即它的重要性或紧迫性；  
4. 这篇论文最终聚焦的核心研究问题。  
要求只能基于标题和摘要进行归纳，不要编造摘要中没有的信息。

**研究问题：**  
用一句话说明论文核心想解决的问题。

**论文脉络：**  
按照“问题动机 → 方法思路 → 验证方式 → 主要结论”的逻辑概括论文内容。只能基于摘要推断，不要虚构论文真实章节结构。

**创新点：**  
提炼 2-3 个最关键的新意。每一点要具体，避免使用“效果显著”“性能优越”等空泛表述。

**方法与结果：**  
简要说明论文采用了什么方法、如何验证、结果说明了什么。如果摘要没有提供具体实验结果，请明确说明“摘要中未明确说明具体数值结果”。

**值得关注：**  
说明这篇论文对 AI、机器人、具身智能、自动驾驶或后续研究可能带来的启发，包括可借鉴的方法、任务设定或研究趋势。
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

    payload = {
        "model": model,
        "messages": _build_deepseek_messages(paper),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()

    return data["choices"][0]["message"]["content"].strip()


def summarize_paper(paper):
    try:
        summary = _call_deepseek(paper)
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        print(f"DeepSeek 摘要生成失败，使用 arXiv 原文摘要：{e}")
        summary = None

    if summary:
        return summary

    return f"### 原文摘要\n\n{paper['summary']}"
