import os
import requests


def notify_feishu(report_path, paper_count, report_text=None):
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")

    if not webhook_url:
        print("未配置 FEISHU_WEBHOOK_URL，跳过飞书推送。")
        return

    if report_text:
        preview = report_text[:3500]
        text = (
            f"本次文献周报已生成。\n"
            f"共筛选论文：{paper_count} 篇\n"
            f"GitHub Actions 输出文件路径：{report_path}\n\n"
            f"以下为内容预览：\n\n{preview}"
        )
    else:
        text = (
            f"本次文献周报已生成。\n"
            f"共筛选论文：{paper_count} 篇\n"
            f"GitHub Actions 输出文件路径：{report_path}"
        )

    payload = {
        "msg_type": "text",
        "content": {
            "text": text
        }
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=20)
        if response.status_code == 200:
            print("飞书通知发送成功。")
        else:
            print("飞书通知发送失败：", response.status_code, response.text)
    except Exception as e:
        print("飞书通知发送异常：", e)
