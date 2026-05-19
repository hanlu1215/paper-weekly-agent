import os

import requests

# 飞书 text 消息体建议控制在约 4k 字符以内
DEFAULT_PREVIEW_CHARS = 3500
DEFAULT_CHUNK_SIZE = 3500


def _post_text(webhook_url: str, text: str) -> requests.Response:
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    return requests.post(webhook_url, json=payload, timeout=30)


def send_feishu_text_chunks(
    webhook_url: str,
    header: str,
    body: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> None:
    """将长文本按 chunk_size 分段发送到飞书（不在日志中输出 webhook）。"""
    full_text = f"{header}{body}"
    if len(full_text) <= chunk_size:
        messages = [full_text]
    else:
        # 多段时预留 "[99/99]\n" 前缀空间，避免截断后丢字
        prefix_reserve = 16
        part_size = max(1, chunk_size - prefix_reserve)
        parts = []
        remaining = full_text
        while remaining:
            parts.append(remaining[:part_size])
            remaining = remaining[part_size:]
        total = len(parts)
        messages = [f"[{i}/{total}]\n{part}" for i, part in enumerate(parts, start=1)]

    for message in messages:
        response = _post_text(webhook_url, message)
        if response.status_code != 200:
            raise requests.HTTPError(
                f"飞书返回 HTTP {response.status_code}: {response.text[:200]}",
                response=response,
            )

        try:
            data = response.json()
        except ValueError:
            data = {}

        # 飞书成功时 code 为 0
        if isinstance(data, dict) and data.get("code") not in (None, 0):
            raise requests.HTTPError(
                f"飞书 API 错误 code={data.get('code')} msg={data.get('msg', '')[:200]}",
                response=response,
            )


def send_feishu_webhook_text(webhook_url: str, text: str) -> None:
    """向群机器人 Webhook 发送单条文本（不打印 webhook）。"""
    response = _post_text(webhook_url, text)
    if response.status_code != 200:
        raise requests.HTTPError(
            f"飞书返回 HTTP {response.status_code}: {response.text[:200]}",
            response=response,
        )
    try:
        data = response.json()
    except ValueError:
        data = {}
    if isinstance(data, dict) and data.get("code") not in (None, 0):
        raise requests.HTTPError(
            f"飞书 API 错误 code={data.get('code')} msg={data.get('msg', '')[:200]}",
            response=response,
        )


def send_feishu_document_link(
    webhook_url: str,
    *,
    title: str,
    doc_url: str,
    paper_count: int | None = None,
    report_name: str | None = None,
) -> None:
    """向群聊发送知识库文档链接（不发送全文）。"""
    lines = [
        "📚 本周文献周报已发布到知识库",
        f"标题：{title}",
        f"链接：{doc_url}",
    ]
    if paper_count is not None:
        lines.append(f"共 {paper_count} 篇论文")
    if report_name:
        lines.append(f"源文件：{report_name}")
    send_feishu_webhook_text(webhook_url, "\n".join(lines))


def notify_feishu(report_path, paper_count, report_text=None):
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")

    if not webhook_url or not str(webhook_url).strip():
        print("未配置 FEISHU_WEBHOOK_URL，跳过飞书推送。")
        return

    path_label = report_path if isinstance(report_path, str) else str(report_path)

    header = (
        f"本次文献周报已生成。\n"
        f"共筛选论文：{paper_count} 篇\n"
        f"文件：{path_label}\n\n"
    )

    if report_text:
        preview = report_text[:DEFAULT_PREVIEW_CHARS]
        body = f"以下为内容预览：\n\n{preview}"
        if len(report_text) > DEFAULT_PREVIEW_CHARS:
            body += "\n\n（内容已截断，完整版见仓库 Markdown 文件。）"
    else:
        body = ""

    try:
        send_feishu_text_chunks(webhook_url, header, body)
        print("飞书通知发送成功。")
    except requests.RequestException as e:
        print("飞书通知发送失败：", e)
