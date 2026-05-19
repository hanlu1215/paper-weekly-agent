# Paper Weekly Agent

每周自动从 arXiv 抓取 AI / 机器人 / 具身智能相关论文，调用 DeepSeek 生成中文周报（Markdown），并可选推送到飞书群。

支持 **本地手动运行** 与 **GitHub Actions 每天自动运行**（生成报告 → 提交到仓库 → 飞书通知）。

## 项目结构

```
paper-weekly-agent/
├── .github/workflows/weekly-paper-agent.yml  # 定时自动化（每天 09:00 北京时间）
├── config/
│   ├── keywords.yaml           # arXiv 检索关键词
│   └── deepseek.env.example    # DeepSeek 配置模板（无真实密钥）
├── output/                     # 生成的周报 Markdown（会提交到 Git）
├── src/
│   ├── main.py                 # 主流程入口
│   ├── fetch_arxiv.py          # arXiv 抓取与筛选
│   ├── summarize.py            # DeepSeek 摘要
│   ├── render_markdown.py      # 生成 Markdown
│   ├── notify_feishu.py        # 飞书 Webhook 消息
│   ├── feishu_client.py        # 飞书 API 鉴权
│   ├── feishu_wiki.py          # 知识库建文档 + 写入 Markdown
│   └── send_to_feishu.py       # 发布 CLI（CI / 手动）
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

发布周报到飞书（**默认**：在知识库新建文档并往群里发链接）：

```bash
python src/send_to_feishu.py
python src/send_to_feishu.py output/2026-W21-paper-weekly.md
```

回退为向群里发送 Markdown 全文：

```bash
FEISHU_NOTIFY_MODE=markdown python src/send_to_feishu.py
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 推荐 | DeepSeek API Key；未配置则回退为 arXiv 原文摘要 |
| `FEISHU_WEBHOOK_URL` | wiki 模式推荐 | 群机器人 Webhook，用于发送文档链接 |
| `FEISHU_NOTIFY_MODE` | 可选 | `auto`（默认）/ `wiki_link` / `markdown` |
| `FEISHU_APP_ID` | wiki 模式必填 | 飞书企业自建应用 App ID |
| `FEISHU_APP_SECRET` | wiki 模式必填 | 飞书企业自建应用 App Secret |
| `FEISHU_WIKI_SPACE_ID` | wiki 模式必填 | 知识库 space_id |
| `FEISHU_WIKI_PARENT_NODE_TOKEN` | 可选 | 父节点 token，不填则建在空间根目录 |
| `FEISHU_WIKI_BASE_URL` | 推荐 | 租户域名，如 `https://your.feishu.cn` |
| `DEEPSEEK_BASE_URL` | 可选 | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 可选 | 默认 `deepseek-v4-pro` |
| `DEEPSEEK_MAX_TOKENS` | 可选 | 默认 `1400` |
| `DEEPSEEK_TEMPERATURE` | 可选 | 默认 `0.2` |
| `MAX_PAPERS_TO_SUMMARIZE` | 可选 | 默认 `5` |
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

1. 每天 **UTC 01:00**（北京时间 **09:00**）定时触发，或手动 `workflow_dispatch`。
2. 安装依赖，从 Secrets 注入环境变量，执行 `python src/main.py`（`SKIP_FEISHU_NOTIFY=true`）。
3. 若 `output/*.md` 有变更，由 `github-actions[bot]` 提交并 push。
4. 执行 `python src/send_to_feishu.py`：在知识库新建文档、写入 Markdown，并向群里发送文档链接。

### GitHub Secrets

在 **Settings → Secrets and variables → Actions → New repository secret** 添加：

| Secret | 必填 | 说明 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | 推荐 | DeepSeek API Key |
| `FEISHU_WEBHOOK_URL` | 推荐 | 群机器人 Webhook（发送文档链接） |
| `FEISHU_APP_ID` | 推荐 | 飞书自建应用 App ID |
| `FEISHU_APP_SECRET` | 推荐 | 飞书自建应用 App Secret |
| `FEISHU_WIKI_SPACE_ID` | 推荐 | 目标知识库 space_id |
| `FEISHU_WIKI_BASE_URL` | 推荐 | 租户域名，如 `https://your.feishu.cn` |

可选：

| Secret | 说明 |
|--------|------|
| `FEISHU_WIKI_PARENT_NODE_TOKEN` | 知识库父目录节点 token |

可选（不配置则使用代码内默认值）：

| Secret | 说明 |
|--------|------|
| `DEEPSEEK_BASE_URL` | API 基地址 |
| `DEEPSEEK_MODEL` | 模型名称 |

### GitHub Variables（可选）

在 **Variables** 标签页可设置（非敏感）：

| Variable | 示例 | 说明 |
|----------|------|------|
| `MAX_PAPERS_TO_SUMMARIZE` | `5` | 每天最多总结篇数 |
| `RECENT_DAYS` | `7` | 仅保留近 N 天论文 |

## 飞书配置（知识库 + 群链接）

### 1. 群机器人 Webhook（发链接到群）

1. 飞书群 → **设置** → **群机器人** → **自定义机器人**。
2. 复制 **Webhook**，填入 `FEISHU_WEBHOOK_URL`。
3. **不要**开启「签名校验」（当前代码未实现）。

### 2. 企业自建应用（创建知识库文档）

1. 打开 [飞书开放平台](https://open.feishu.cn/app) → **创建企业自建应用**。
2. 在 **权限管理** 中开通（至少）：
   - `wiki:wiki` 或 `wiki:node:create`（知识库）
   - `docx:document` 相关写权限
   - `docx:document.block:convert`（Markdown 转文档块）
3. **版本管理与发布** → 创建并发布版本，让管理员审批。
4. 把应用 **添加为目标知识库成员/管理员**（否则 `131006 permission denied`）。
5. 记录 **App ID**、**App Secret** → `FEISHU_APP_ID` / `FEISHU_APP_SECRET`。
6. 打开目标知识库，从浏览器地址栏获取 `space_id`（`/wiki/space/{space_id}/...`）→ `FEISHU_WIKI_SPACE_ID`。
7. 配置 `FEISHU_WIKI_BASE_URL` 为你的租户域名（浏览器打开知识库时的域名，如 `https://xxx.feishu.cn`）。
8. （可选）在某个目录下新建文档时，复制该目录节点 URL 中的 `node_token` → `FEISHU_WIKI_PARENT_NODE_TOKEN`。

### 3. 推送效果

- 每次运行在知识库 **新建一篇文档**，内容为周报 Markdown。
- 群里收到一条消息，含 **标题 + 知识库链接**（不再发送全文）。

**注意：** 勿在日志、Issue、README 或 Git 中粘贴 Webhook、App Secret。

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
