# Paper Weekly Agent · 文献每日速递

> 写给第一次打开这个仓库的你：你不需要先成为 Python 专家，也**不必在本地跑 Python**。推荐全程只改 **GitHub 上的代码**，用 **Actions** 执行；密钥只放在 **Actions Secrets**。

---

## 推荐工作流：只改 GitHub，不用本地跑代码

| 做什么 | 在哪里做 |
|--------|----------|
| 改关键词、改代码、改 workflow | [GitHub 网页编辑器](https://github.com/peinengzhong/paper-weekly-agent) 或 Cursor 连仓库后 **只 commit/push，不跑 `python src/main.py`** |
| 每天抓论文、写总结、推飞书 | **Actions → Daily Paper Agent**（定时或 Run workflow） |
| 看往期日报 | 仓库 `daily_reports/` 目录（浏览器打开即可） |
| 密钥 | **Settings → Secrets and variables → Actions** |

**不建议：** 在本地安装 venv、配置 `.env`、手跑脚本（易遇到 arXiv 429，且与云端重复）。

若本机仍 clone 了仓库，仅作浏览时可以定期：

```bash
git pull origin main
./scripts/clean-local-reports.sh   # 删掉本地 .md，保留 GitHub 上的存档
```

---

## 这个仓库是做什么的？

一句话：**每天自动从 arXiv 找论文 → 用 AI 写成中文速递 → 存进你的 GitHub → 推送到飞书群和知识库。**

更具体一点，每天（默认北京时间 **09:00**）会发生这些事：

1. 按你设定的**关键词**在 arXiv 检索相关论文  
2. 筛掉太久远的、以及**往日已经推过**的（同一天可以重复推，隔天不重复）  
3. 用 **DeepSeek** 为每篇生成中文总结（含中文标题）  
4. 写成 Markdown，保存到仓库的 `daily_reports/`（同一天多次运行会**覆盖**当日那一个文件，不会堆出一堆 `-02.md`）  
5. 在飞书**知识库**新建一篇文档，并在群里发一条消息：标题、各篇中文题目、链接、往期 GitHub 存档地址  

你得到的是：

- **GitHub 上的永久存档**（按日期命名的 `.md`，方便回溯）  
- **飞书里的可读版本**（适合手机点开）  
- **群里的提醒**（不用自己每天刷 arXiv）  

默认关注方向包括：具身智能、机器人操作、VLA、扩散策略、世界模型、端到端自动驾驶等（见 `config/keywords.yaml`），你完全可以改成自己的研究方向。

---

## 上手：Fork → 在 GitHub 上改代码 → 填 Secrets → Run Actions

### 第一步：把仓库放到你自己的 GitHub

1. 打开本仓库在 GitHub 上的页面，点击右上角 **Fork**。  
2. （可选）设为 **Private**。  

之后所有自动化都在你 Fork 后的仓库里执行。

### 第二步：在 GitHub 上直接改文件（或 Cursor 只负责 push）

**方式 A — 网页（最简单）**

1. 打开仓库，进入要改的文件（如 `config/keywords.yaml`）。  
2. 点铅笔图标 **Edit**，改完后 **Commit changes** 到 `main`。  

**方式 B — Cursor 当编辑器，仍以 GitHub 为准**

1. Cursor 打开仓库或 `github.dev` 在线工作区。  
2. 用对话让 Agent 改代码，但**执行以 Actions 为准**；改完 push 到 `main`，不要在本地 `python src/main.py`。  

### 第三步：用对话（Cursor / Copilot）描述你想改什么

你不需要先读懂全部代码。在 Cursor 的 **Chat / Agent** 里，用自然语言描述目标即可，例如：

| 你想做的事 | 可以对 Cursor 说 |
|-----------|------------------|
| 换检索领域 | 「把 `config/keywords.yaml` 改成关注大模型推理、RAG、Agent 的英文关键词」 |
| 每天多推几篇 | 「把每天最多总结的篇数改成 8，并说明要改 workflow 还是环境变量」 |
| 改推送文案 | 「飞书群消息里把『本日文献周报』改成『今日 AI 文献精选』」 |
| 改总结结构 | 「DeepSeek 总结里增加『局限与未来工作』一小节」 |
| 改运行时间 | 「把 GitHub Actions 改成每天北京时间 8:00 运行」 |
| 只推链接、不建知识库 | 「说明如何设置 `FEISHU_NOTIFY_MODE=markdown`」 |

改完后让 Cursor 帮你 **commit**；你 **push 到 GitHub**，Actions 就会按新逻辑运行。

**适合改的文件（给 Cursor 指路径时有用）：**

- `config/keywords.yaml` — 搜哪些词  
- `src/summarize.py` — AI 总结的提示词与格式  
- `src/notify_feishu.py` — 飞书群消息文案  
- `src/render_markdown.py` — 日报 Markdown 版式  
- `src/published_history.py` — 跨日去重规则  
- `.github/workflows/weekly-paper-agent.yml` — 定时、依赖、CI 步骤  

### 第四步：配置 GitHub Actions Secrets（必做）

自动化跑在 GitHub 云端，**密钥只放在 Secrets 里**，不要写进代码或提交到 Git。

路径：**你的仓库 → Settings → Secrets and variables → Actions → New repository secret**

| Secret 名称 | 是否建议填 | 作用 |
|-------------|-----------|------|
| `DEEPSEEK_API_KEY` | 强烈建议 | 生成中文总结；不填则退回 arXiv 英文摘要 |
| `FEISHU_WEBHOOK_URL` | 强烈建议 | 群机器人 Webhook，用来发链接通知 |
| `FEISHU_APP_ID` | 知识库模式需要 | 飞书企业自建应用 |
| `FEISHU_APP_SECRET` | 知识库模式需要 | 同上 |
| `FEISHU_WIKI_SPACE_ID` | 知识库模式需要 | 目标知识库 space_id（纯数字） |
| `FEISHU_WIKI_BASE_URL` | 建议 | 租户域名，如 `https://my.feishu.cn` |
| `FEISHU_WIKI_PARENT_NODE_TOKEN` | 可选 | 文档建在哪个目录下 |

可选 Secret（不填则用默认值）：

| Secret | 默认行为 |
|--------|----------|
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | `deepseek-v4-pro` |

可选 **Variables**（非敏感，在 Actions → Variables 里设）：

| Variable | 含义 | 默认 |
|----------|------|------|
| `MAX_PAPERS_TO_SUMMARIZE` | 每天最多总结几篇 | `5` |
| `RECENT_DAYS` | 只考虑近 N 天内的论文 | `7` |

配好后：

1. 打开 **Actions** 页，确认 workflow **Daily Paper Agent** 已 **Enable**。  
2. 点 **Run workflow** 手动跑一次，看是否绿勾、飞书是否收到消息。  
3. 若定时没触发，检查 **Settings → Actions → General** 是否允许 Actions 与 scheduled workflows。  

### 第五步：配好飞书（一次即可）

需要两块能力，Secrets 里都要对应填好：

1. **群机器人 Webhook**（发链接到群）  
   - 飞书群 → 设置 → 群机器人 → 自定义机器人 → 复制 Webhook → 填入 `FEISHU_WEBHOOK_URL`  

2. **企业自建应用**（在知识库创建文档）  
   - [飞书开放平台](https://open.feishu.cn/app) 创建应用，开通 wiki / docx 相关权限并发布  
   - 把应用加为目标**知识库成员**  
   - 填写 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_WIKI_SPACE_ID` 等  

更细的权限与 space_id 获取方式，可在 Cursor 里问：「根据 README 帮我逐步配置飞书知识库」。

---

## 每天自动跑的时候，仓库里会发生什么？

```
定时 / 手动触发 (GitHub Actions)
        │
        ▼
  python src/main.py          ← 抓 arXiv、去重、DeepSeek 总结、写 daily_reports/
        │
        ▼
  git commit & push           ← 把日报、周报累计、published_papers.json 推回仓库
        │
        ▼
  python src/send_to_feishu.py ← 知识库建文档 + 群消息（标题、中文题目列表、链接）
```

**去重规则（新人常问）：**

- **同一天**跑多次：可以再次推送**相同**论文，当天的 `YYYY-MM-DD-文献每日速递.md` 会被**覆盖**  
- **隔天**：已在 `data/published_papers.json` 里记录过的 arXiv ID **不会再推**  

**群消息大致长这样：**

```
📚 本日文献周报已发布到知识库
标题：2026-05-20-文献每日速递
（各篇中文题目，一行一篇）
详情看链接：https://my.feishu.cn/wiki/...
查看往期推送：https://github.com/你的用户名/paper-weekly-agent/tree/main/daily_reports
```

---

## 仓库目录一览

```
paper-weekly-agent/
├── .github/workflows/
│   └── weekly-paper-agent.yml    # 定时任务：跑 main → 提交 → 飞书推送
├── config/
│   ├── keywords.yaml             # arXiv 检索关键词（最常改）
│   ├── deepseek.env.example      # DeepSeek 配置模板（本地用，勿提交密钥）
│   └── deepseek.env              # 本地真实配置（已在 .gitignore）
├── daily_reports/                # 每日速递 Markdown（Actions 会提交到 GitHub）
│   └── README.md
├── weekly_reports/               # 当周文献累计（按篇追加，跨日去重）
├── data/
│   └── published_papers.json     # 已推送 arXiv ID（跨日去重依据）
├── src/
│   ├── main.py                   # 主流程入口
│   ├── fetch_arxiv.py            # arXiv 抓取、筛选、去重
│   ├── summarize.py              # DeepSeek 中文总结 + 中文标题
│   ├── render_markdown.py        # 生成 / 覆盖当日日报、追加周报
│   ├── published_history.py      # 发布记录与跨日去重
│   ├── notify_feishu.py          # 飞书 Webhook 文本消息
│   ├── feishu_client.py          # 飞书 API 鉴权
│   ├── feishu_wiki.py            # 知识库创建文档、写入 Markdown
│   └── send_to_feishu.py         # 单独发布到飞书（CI 第二步调用）
├── scripts/
│   ├── verify_feishu_wiki.py     # CI 里校验飞书配置
│   ├── run-local.sh              # 可选：本地一键试跑
│   └── clean-local-reports.sh    # 可选：只删本地 md，不动 GitHub
├── .env.example                  # 环境变量说明（本地或对照 Secrets）
├── requirements.txt              # Python 依赖
└── README.md                     # 你正在看的文件
```

| 路径 | 谁在用 | 说明 |
|------|--------|------|
| `config/keywords.yaml` | 你 / Cursor | 决定「搜什么」 |
| `daily_reports/*.md` | Actions → GitHub | 每天一期速递正文 |
| `weekly_reports/*-累计.md` | Actions | 本周迄今所有篇目 |
| `data/published_papers.json` | 主流程 | 防止隔天重复推送 |
| `.github/workflows/weekly-paper-agent.yml` | GitHub | 定时与自动化编排 |
| `.env` / `config/deepseek.env` | 仅本地 | 本地试跑时用，**不要 push** |

---

## 我想看往期推送、或手动补跑一天

- **往期 Markdown：** 浏览器打开  
  `https://github.com/你的用户名/paper-weekly-agent/tree/main/daily_reports`  
- **手动触发一次：** GitHub → **Actions** → **Daily Paper Agent** → **Run workflow**  
- **只重发飞书、不重新抓论文：** 一般不需要；若 CI 里「提交」成功但飞书失败，可对 Cursor 说：「帮我只运行 send_to_feishu 的步骤」或查看 workflow 里最后一步的日志  

---

## 关于本地 clone（可选、仅浏览）

本仓库**不依赖**你在本机跑 Python。若磁盘上仍有 clone，只需与 GitHub 同步浏览；报告正文在 GitHub 的 `daily_reports/` 查看即可。`scripts/run-local.sh` 仅作调试备用，日常使用请 **Actions → Run workflow**。

---

## 安全提醒（请务必读）

- **永远不要**把 Webhook、API Key、App Secret 写进代码、README、Issue 或 commit。  
- 只使用 **GitHub Actions Secrets** 和本地 **`.env`**（已在 `.gitignore`）。  
- 若密钥曾经误提交，立即在对应平台**轮换密钥**，并清理 Git 历史。  

---

## 常见问题

**Q：定时任务没跑，只有手动 Run 才有记录？**  
A：到 **Settings → Actions** 确认已启用 Actions 与 scheduled workflows；workflow 未被 Disable；`main` 分支上存在 workflow 文件。

**Q：飞书 404 或 permission denied？**  
A：多半是 `FEISHU_WIKI_SPACE_ID` 填错，或应用未加入知识库成员。用 Actions 日志里 `verify_feishu_wiki` 步骤的报错对照修改。

**Q：今天没新文献，还会发飞书吗？**  
A：不会。日报里若是「今日无新增文献」，CI 会跳过飞书推送。

**Q：本地 / Actions 日志里 arXiv 超时或 429，抓取 0 篇？**  
A：这是 arXiv 官方 API 的**频率限制或网络慢**，不是关键词配错。12 个关键词合并查询很容易超时，紧接着连续请求又会触发 **429**。当前代码已对 429 自动退避重试，并在关键词较多时改为逐个查询。请隔 **5～10 分钟**再跑；仍失败可在 `.env` 里加大 `ARXIV_COOLDOWN_SECONDS=20`、`ARXIV_KEYWORD_DELAY=5`，或减少 `config/keywords.yaml` 里的关键词数量。GitHub Actions 机房网络有时比本地更稳，也可直接在 Actions 里 **Run workflow** 试一次。

**Q：能和 Cursor 说什么来大改？**  
A：例如换模型、改 cron 时区、增加邮件通知、改总结字数、增加微信公众号等——描述目标即可，由 Agent 改对应 `src/` 或 workflow。

---

## 许可证

本仓库未强制附带开源协议；Fork 后你可自行添加 `LICENSE` 文件。

---

**下一步建议：** Fork → 填 Secrets → Actions 手动 Run 一次 → 在 Cursor 里说一句：「帮我把关键词改成我关注的 XXX 领域」。祝你每天都有值得读的论文送到眼前。
