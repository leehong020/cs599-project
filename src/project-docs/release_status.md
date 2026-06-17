# 阶段 11 发布状态

本文档记录阶段 11 的本地 MVP 发布验收结果。它不是密钥或用户数据来源，只记录检查项、证据和限制。

## 本地发布结论

当前项目已经满足“本地 MVP 可启动、可迁移、可构建、核心安全规则可测试”的发布状态。

可以本地验证的能力已经通过自动化检查：

- 后端 ruff 检查通过；
- 后端 pytest 通过；
- Alembic 可以从空 SQLite 数据库升级；
- FastAPI 可以启动并通过 `/api/health`；
- 前端可以生产构建；
- 前端包含 Google 连接、用户设置、时区、默认日历和署名配置界面；
- `.env`、数据库、运行日志、Markdown 导出目录和前端构建产物已被 `.gitignore` 排除；
- 自动化测试不使用真实 Google 测试账号，外部写操作通过本地状态机、mock 客户端和幂等记录验证。

## 需要真实账号手动联调

以下能力依赖真实 Google OAuth Client、真实测试账号和人工授权，不能仅靠本地单元测试证明：

- Google OAuth 登录、callback 和刷新 token 的完整浏览器流程；
- Gmail 搜索、读取线程、创建 Draft 和发送；
- Calendar events、Freebusy、insert 和 update；
- Token 被 Google 撤销后的真实恢复体验；
- 多浏览器标签同时点击确认时的端到端并发体验。

## 当前未作为本地发布阻塞项的后续范围

以下内容已经在产品文档和验收矩阵中作为目标能力记录，但当前代码阶段尚未完整实现为真实端到端功能：

- 选中 Gmail 邮件后自动生成回复目标的完整前端工作流；
- 选中 Calendar 日程后自动生成修改目标的完整前端工作流；
- 批量确认“全部发送”的二次范围确认 UI；
- 冲突日程的替代时间推荐；
- Markdown 导出内容的前端下载体验。

这些能力不影响当前本地 MVP 的启动和安全闭环验收，但如果要进入真实自用生产状态，应优先补齐。

## 已补齐的文件上传解析

当前已支持聊天页上传并解析：

- TXT、MD、CSV、JSON、LOG、XML、HTML、代码文本；
- DOCX；
- PDF。

后端会保存上传元数据到 `uploaded_files`，解析结果写入 `file_extractions`，原始文件保存到 `data/uploads/`。文件文本只作为不可信上下文使用，不会直接授权发送邮件或创建日程。

## 启动命令摘要

后端：

```powershell
Set-Location C:\Users\Lee\Desktop\mailflow-agent\backend
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```powershell
Set-Location C:\Users\Lee\Desktop\mailflow-agent\frontend
npm install
npm run dev -- --port 5173
```

浏览器打开：

```text
http://127.0.0.1:5173
```
