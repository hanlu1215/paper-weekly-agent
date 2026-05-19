# Paper Weekly Agent

每周自动从 arXiv 抓取 AI / 机器人 / 具身智能相关论文，调用 DeepSeek 生成中文周报（Markdown），并可选推送到飞书群。

支持 **本地手动运行** 与 **GitHub Actions 每周一自动运行**（生成报告 → 提交到仓库 → 飞书通知）。

## 项目结构

```
paper-weekly-agent/
├── .github/workflows/weekly-paper-agent.yml  # 每周自动化
├── config/
│   ├── keywords.yaml           # arXiv 检索关键词
│   └── deepseek.env.example    # DeepSeek 配置模板（无真实密钥）
├── output/                     # 生成的周报 Markdown（会提交到 Git）
├── src/
│   ├── main.py                 # 主流程入口
│   ├── fetch_arxiv.py          # arXiv 抓取与筛选
│   ├── summarize.py            # DeepSeek 摘要
│   ├── render_markdown.py      # 生成 Markdown
│   ├── notify_feishu.py        # 飞书推送（库函数）
│   └── send_to_feishu.py       # 飞书推送 CLI（CI / 手动）
├── .env.example                # 环境变量模板
└── requirements.txt
```

## 本地运行

### 1. 安装依赖

```bash
cd paper-weekly-agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置环境变量

复制模板并填写（**不要提交真实密钥**）：

```bash
cp .env.example .env
cp config/deepseek.env.example config/deepseek.env
```

编辑 `.env` 与 `config/deepseek.env`，填入本地密钥。

### 3. 执行

```bash
python src/main.py
```

流程：读取 `config/keywords.yaml` → 抓取 arXiv → 去重 → 筛选近 N 天 → DeepSeek 总结（最多 M 篇）→ 写入 `output/` → 飞书预览推送。

单独推送已有周报（发送**完整** Markdown，过长会自动分段）：

```bash
python src/send_to_feishu.py
python src/send_to_feishu.py output/2026-W21-paper-weekly.md
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 推荐 | DeepSeek API Key；未配置则回退为 arXiv 原文摘要 |
| `FEISHU_WEBHOOK_URL` | 可选 | 飞书群机器人 Webhook；未配置则跳过推送 |
| `DEEPSEEK_BASE_URL` | 可选 | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 可选 | 默认 `deepseek-v4-pro` |
| `DEEPSEEK_MAX_TOKENS` | 可选 | 默认 `1400` |
| `DEEPSEEK_TEMPERATURE` | 可选 | 默认 `0.2` |
| `MAX_PAPERS_TO_SUMMARIZE` | 可选 | 默认 `10` |
| `RECENT_DAYS` | 可选 | 默认 `7` |
| `SKIP_FEISHU_NOTIFY` | 可选 | 设为 `1`/`true` 时主流程不推送（供 CI 在提交后调用 `send_to_feishu.py`） |

所有敏感项均通过 `os.getenv()` 读取，**不要**写入代码或 Markdown。

## 输出文件

- 目录：`output/`
- 命名：`{年}-W{ISO周数}-paper-weekly.md`（例如 `2026-W21-paper-weekly.md`）
- 标题含 ISO 周次与生成日期

该目录下的 `.md` 文件会纳入 Git 版本管理（`.env` 等仍被忽略）。

## GitHub Actions 自动化

### 启用

1. 将本仓库推送到 GitHub（见下方「首次上传」）。
2. 打开 **Settings → Secrets and variables → Actions**。
3. 添加 [Secrets](#github-secrets)（及可选 [Variables](#github-variables-可选)）。
4. 在 **Actions** 页确认 workflow **Weekly Paper Agent** 已启用。
5. 可点击 **Run workflow** 手动触发测试。

### 运行逻辑

1. 每周一 **UTC 00:00**（北京时间周一 **08:00**）定时触发，或手动 `workflow_dispatch`。
2. 安装依赖，从 Secrets 注入环境变量，执行 `python src/main.py`（`SKIP_FEISHU_NOTIFY=true`）。
3. 若 `output/*.md` 有变更，由 `github-actions[bot]` 提交并 push。
4. 执行 `python src/send_to_feishu.py`，将最新周报全文分段发到飞书。

### GitHub Secrets

在 **Settings → Secrets and variables → Actions → New repository secret** 添加：

| Secret | 必填 | 说明 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | 推荐 | DeepSeek API Key |
| `FEISHU_WEBHOOK_URL` | 推荐 | 飞书群机器人 Webhook 完整 URL |

可选（不配置则使用代码内默认值）：

| Secret | 说明 |
|--------|------|
| `DEEPSEEK_BASE_URL` | API 基地址 |
| `DEEPSEEK_MODEL` | 模型名称 |

### GitHub Variables（可选）

在 **Variables** 标签页可设置（非敏感）：

| Variable | 示例 | 说明 |
|----------|------|------|
| `MAX_PAPERS_TO_SUMMARIZE` | `10` | 每周最多总结篇数 |
| `RECENT_DAYS` | `7` | 仅保留近 N 天论文 |

## 飞书群机器人配置

1. 在飞书群聊 → **设置** → **群机器人** → **添加机器人** → **自定义机器人**。
2. 设置名称与安全校验（按需）。
3. 复制 **Webhook 地址**，填入本地 `.env` 的 `FEISHU_WEBHOOK_URL` 或 GitHub Secret `FEISHU_WEBHOOK_URL`。
4. Webhook 格式类似：`https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx`

**注意：** 勿在日志、Issue、README 或提交记录中粘贴 Webhook 或 API Key。

## 安全说明

- `.env`、`config/deepseek.env`、`*.env`（除 `*.env.example`）已在 `.gitignore` 中忽略。
- 若曾误将密钥提交到 Git，请立即**轮换密钥**，并使用 [git filter-repo](https://github.com/newren/git-filter-repo) 或 GitHub Secret scanning 清理历史。
- Actions 日志中不会 echo 密钥；请勿在 workflow 中打印 `secrets.*`。

## 首次上传到 GitHub

```bash
cd paper-weekly-agent

# 确认不会提交敏感文件
git status
git check-ignore -v .env config/deepseek.env

git add .
git commit -m "feat: weekly paper agent with GitHub Actions and Feishu notify"
git branch -M main
git remote add origin https://github.com/<你的用户名>/paper-weekly-agent.git
git push -u origin main
```

推送后在 GitHub 配置 Secrets，并在 Actions 中手动运行一次验证。

## 许可证

按需自行添加 LICENSE。
