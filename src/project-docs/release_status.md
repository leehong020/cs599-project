# 本地发布状态

本文档记录当前项目作为 CS599 作业提交时的本地可运行状态。它不是密钥、数据库或用户数据来源。

## 结论

Mailflow Agent 当前可以作为本地 MVP 提交和演示：

- 后端 FastAPI 可以启动并提供健康检查、OAuth、Gmail、Calendar、Assistant、Workflow、Settings、Files、Memory 等接口。
- 前端 Vue 3 可以启动并访问聊天页、Gmail 页、Calendar 页和设置页。
- Gmail 与 Calendar 的真实能力依赖用户本地 Google OAuth 配置。
- 外部写操作遵守确认边界：Assistant 写邮件和写日程需要本地草稿、Proposal、用户确认和执行记录；Calendar 页面手动按钮属于用户直接操作。
- 本地运行数据写入 `data/`，该目录不提交到 GitHub。

## 已验证命令

```powershell
Set-Location C:\Users\Lee\Desktop\cs599-project\src\backend
..\..\.venv\Scripts\python -m pytest
..\..\.venv\Scripts\python -m ruff check .
```

```powershell
Set-Location C:\Users\Lee\Desktop\cs599-project\src\frontend
npm run build
```

## 启动命令

后端：

```powershell
Set-Location C:\Users\Lee\Desktop\cs599-project\src\backend
..\..\.venv\Scripts\python -m alembic upgrade head
..\..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```powershell
Set-Location C:\Users\Lee\Desktop\cs599-project\src\frontend
npm install
npm run dev -- --port 5173
```

浏览器访问：

```text
http://127.0.0.1:5173
```

## Google OAuth 配置要求

运行真实 Gmail 和 Calendar 功能前，需要在本地配置 Google OAuth：

```env
GOOGLE_CLIENT_ID=你的 Client ID
GOOGLE_CLIENT_SECRET=你的 Client Secret
GOOGLE_REDIRECT_URI=http://localhost:8000/gmail/auth/callback
```

也可以使用仓库根目录下的 `google_oauth.json` 作为本地配置文件，但该文件包含 `client_secret`，不得提交到 GitHub。

如果 Google Cloud OAuth 应用处于 Testing 状态，使用者的 Gmail 账号必须加入 Test users。否则授权时会被 Google 拒绝。

## 运行数据

程序运行时可能自动创建：

- `data/app.db`
- `data/uploads/`
- `data/exports/`
- `data/logs/`

这些文件是本地运行数据，不是源码，不需要移动到 `src/`，也不应上传到 GitHub。
