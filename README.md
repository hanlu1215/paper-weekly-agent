# Paper Weekly Agent

## 用途

每天按关键词从 arXiv、Semantic Scholar、OpenReview、IEEE Xplore 检索近期论文，用 DeepSeek 生成中文速递，写入 GitHub 的 `daily_reports/`，并推送到飞书知识库与群消息。

## 怎么使用

### 1. Fork 到你的仓库

在 GitHub 打开本仓库，点 **Fork**，在你自己的仓库里运行（可选设为 Private）。

### 2. 配置 Secrets

路径：**你的仓库 → Settings → Secrets and variables → Actions → New repository secret**

| 名称 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | 生成中文总结 |
| `FEISHU_WEBHOOK_URL` | 群机器人 Webhook |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书自建应用 |
| `FEISHU_WIKI_SPACE_ID` | 知识库 ID |
| `FEISHU_WIKI_BASE_URL` | 租户地址，如 `https://xxx.feishu.cn` |

可选：`SEMANTIC_SCHOLAR_API_KEY`、`IEEE_XPLORE_API_KEY`（启用对应来源时填写）。

### 3. 运行

1. **Actions** → 左侧 **Daily Paper Agent** → **Run workflow** → 分支选 **main** → Run。  
2. 默认每天北京时间约 9:00 也会自动跑一次。  
3. 日报在仓库 **daily_reports/**；飞书会收到知识库链接。  

若 **Commit and push** 失败并提示 `rejected (fetch first)`，重新 **Run workflow** 即可（已自动先拉取远程再推送）。

### 4. 改检索方向（Cursor / Codex）

不用改代码结构，主要改 **`config/keywords.yaml`** 里的英文关键词。在 Cursor 或 Codex 里直接说，例如：

> 把关键词改成：dexterous manipulation, VLA, world model

改完 **commit 到 main**，下次 Actions 会按新关键词检索。

---

本地调试（可选）：复制 `.env.example` 为 `.env`，填好密钥后执行 `./scripts/run-local.sh`。日常推荐只用 GitHub Actions，密钥不要提交到仓库。
