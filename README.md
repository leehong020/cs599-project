# Mailflow Agent

## 项目简介

Mailflow Agent 是一个基于 FastAPI、LangGraph、LangChain、Vue 3 和 SQLite 的多 Agent 邮件与日程助理系统，用自然语言帮助用户处理 Gmail 邮件、Google Calendar 日程、文件上下文、联系人、署名和记忆，并在真实外部写操作前执行 Proposal + Authorization 安全确认闭环。

## 方向

方向一：Agentic AI 原生开发

## 技术栈

- AI IDE: Trae CN / Codex
- LLM: DeepSeek API
- 框架: LangGraph、LangChain、FastAPI、Vue 3
- 数据库: SQLite、SQLAlchemy、Alembic
- Google 集成: Google OAuth、Gmail API、Google Calendar API
- 协议: Function Calling / Tool Calling、SSE
- 测试: pytest、pytest-asyncio、ruff、vue-tsc、Vite build

## 目录结构

```text
cs599-project/
├── docs/                 # 课程提交文档与架构说明
├── src/
│   ├── backend/          # FastAPI 后端、LangGraph Agent 编排、数据库迁移和测试
│   ├── frontend/         # Vue 3 前端、聊天页、Gmail 页、Calendar 页和设置页
│   └── project-docs/     # 产品规格、架构决策、安全规则、验收矩阵和代码导览
├── data/                 # 本地运行数据
├── .env.example          # 环境变量模板
├── .gitignore
├── LICENSE
└── README.md
```

## 环境搭建

1. 依赖安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python -m pip install -e "src/backend[dev]"

Set-Location src/frontend
npm install
```

2. 环境变量配置

```powershell
Copy-Item .env.example .env
```

在 `.env` 中填写 LLM 和 Google OAuth 配置，不要硬编码 API Key。

3. Google OAuth 配置

项目需要 Google OAuth 才能访问 Gmail 和 Google Calendar。推荐自己创建 Google Cloud OAuth 应用：

```text
Google Cloud Console
→ APIs & Services
→ OAuth consent screen
→ 创建或配置应用
→ Test users 中加入要使用本系统的 Gmail 账号
→ Credentials
→ Create Credentials
→ OAuth client ID
→ Application type 选择 Web application
```

Authorized redirect URIs 填写：

```text
http://localhost:8000/gmail/auth/callback
```

创建完成后有两种配置方式。

方式一：在 `.env` 中填写：

```env
GOOGLE_CLIENT_ID=你的-client-id
GOOGLE_CLIENT_SECRET=你的-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/gmail/auth/callback
```

方式二：下载 Google Cloud Console 生成的 OAuth JSON 文件，放到项目根目录并命名为：

```text
google_oauth.json
```

JSON 文件格式通常如下：

```json
{
  "web": {
    "client_id": "你的-client-id",
    "client_secret": "你的-client-secret",
    "redirect_uris": [
      "http://localhost:8000/gmail/auth/callback"
    ]
  }
}
```

如果使用同一个 Google Cloud 应用给别人测试，需要把对方 Gmail 加入 OAuth consent screen 的 Test users。`google_oauth.json` 包含 `client_secret`，只适合私下给可信测试者使用，不要提交到 GitHub。

4. 启动步骤

```powershell
Set-Location src/backend
..\..\.venv\Scripts\python -m alembic upgrade head
..\..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
Set-Location src/frontend
npm run dev -- --port 5173
```

浏览器访问：

```text
http://127.0.0.1:5173
```

## 项目状态

- [x] Proposal：已完成选题、产品范围、架构设计、核心规格文档和项目初始化。
- [x] MVP：已完成多 Agent 邮件与日程助理核心闭环，支持聊天交互、Gmail、Calendar、文件上下文、联系人、署名和记忆。
- [x] Testing：已完成后端单元测试、Agent 工具测试、日志脱敏测试、前端类型检查和生产构建验证。
- [x] Docs：已整理 README、架构说明、规格文档、验收矩阵和课程报告。
- [x] Final：项目代码、文档和运行配置已整理为课程大作业最终提交版本。
