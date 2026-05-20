# 不用本机文件夹：Cursor + GitHub 直接改代码

本仓库设计为**以 GitHub 为唯一源码**，日常不需要在本机保留 clone。

## 在 Cursor 里打开（不占用本地项目目录）

1. **Command Palette**（`Ctrl+Shift+P` / `Cmd+Shift+P`）→ 输入 **Git: Clone** 或 **Clone Repository**。  
2. 填入：`https://github.com/peinengzhong/paper-weekly-agent.git`（或你的 Fork 地址）。  
3. 若 Cursor 询问存放位置，可选一个**临时目录**，或改用下面「完全不 clone」的方式。

**更省事：浏览器 + Cursor 远程**

- 在 GitHub 仓库页按 `.` 打开 **github.dev** 在线编辑器；或  
- 使用 Cursor 的 **Remote / SSH / Codespaces**（若已配置）连接 GitHub。

## 改代码以后

1. **Commit & Push** 到 `main`（网页编辑器或 Cursor 内置 Git 均可）。  
2. 打开 **Actions → Daily Paper Agent → Run workflow** 验证。  
3. 密钥只在 **Settings → Secrets and variables → Actions**，不要写在代码里。

## 看往期日报

https://github.com/peinengzhong/paper-weekly-agent/tree/main/daily_reports
