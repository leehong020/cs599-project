# 代码导览

本文档用于说明当前项目代码结构，方便评审和后续维护。它不是运行时依赖，程序不会读取本文件。

## 总体结构

```text
src/
├── backend/          # FastAPI 后端、LangGraph 多 Agent、Google API、SQLite 持久化
├── frontend/         # Vue 3 前端页面、聊天流、Gmail/Calendar 工作台、设置页
└── project-docs/     # 作业说明文档、架构决策、验收矩阵和手工测试脚本
```

运行时真正会读取的 Markdown 文件位于：

```text
src/backend/app/config/prompts/*.md
```

`src/project-docs/*.md`、`docs/*.md` 和 `README.md` 都是给人看的文档，不参与程序逻辑。

## 后端入口

| 路径 | 职责 |
|---|---|
| `src/backend/app/main.py` | 创建 FastAPI 应用，挂载健康检查、OAuth、Gmail、Calendar、Assistant、Workflow、Settings、Files、Memory 等路由 |
| `src/backend/app/core/config.py` | 读取 `.env` 和本地配置，定位仓库根目录、数据库、上传目录、OAuth 配置 |
| `src/backend/app/core/database.py` | SQLAlchemy 异步数据库连接和 Session 管理 |
| `src/backend/app/core/security.py` | Google token 加密、敏感数据处理辅助 |
| `src/backend/app/core/logging.py` | 日志脱敏、审计事件和错误追踪 |

## 后端 API

| 路径 | 职责 |
|---|---|
| `src/backend/app/api/health.py` | 健康检查 |
| `src/backend/app/api/auth.py` | Google OAuth 登录、回调、连接状态、断开连接 |
| `src/backend/app/api/gmail.py` | Gmail 搜索、读取、线程详情、准备新邮件/回复/转发、删除邮件 |
| `src/backend/app/api/calendar.py` | 日程列表、忙闲查询、日程草稿准备、日程页手动创建/修改/删除 |
| `src/backend/app/api/assistant_graph.py` | Assistant 对话、SSE 流式输出、会话管理、图结构调试 |
| `src/backend/app/api/workflow.py` | Work Item、Proposal、Authorization、Execution 的安全闭环 |
| `src/backend/app/api/files.py` | 文件上传、解析、读取、删除 |
| `src/backend/app/api/settings.py` | 用户资料、署名、联系人、偏好设置 |
| `src/backend/app/api/memory.py` | 短期记忆、长期记忆候选、联系人备注、Markdown 导出 |

## Agent 与工具

| 路径 | 职责 |
|---|---|
| `src/backend/app/graph/builder.py` | 构建 LangGraph 主图 |
| `src/backend/app/graph/multi_nodes.py` | 多 Agent 节点：state loader、supervisor、context、mail、calendar、review、confirmation、executor、response、memory extractor |
| `src/backend/app/graph/tools.py` | Assistant 可调用工具：邮件草稿、日程草稿、确认执行、联系人解析、上下文查询等 |
| `src/backend/app/graph/runner.py` | 运行 Assistant 图，维护线程状态和 checkpoint |
| `src/backend/app/graph/agents/runtime.py` | Agent 运行时和提示词加载 |
| `src/backend/app/config/prompts/*.md` | 多 Agent 提示词模板，属于程序运行时依赖 |

Assistant 的外部写操作边界：

- 邮件发送必须先形成本地草稿，再经过用户确认后执行。
- Assistant 创建、修改、删除 Google Calendar 事件必须先形成本地草稿或删除草稿，再经过用户确认后执行。
- 日程页的手动按钮属于用户显式操作，可以直接调用 Calendar API，不属于 Assistant 自动执行。

## 服务层

| 路径 | 职责 |
|---|---|
| `src/backend/app/services/oauth.py` | Google OAuth token 换取、刷新、保存和撤销 |
| `src/backend/app/services/gmail.py` | Gmail API 封装、邮件搜索/读取/发送相关逻辑 |
| `src/backend/app/services/calendar.py` | Calendar API 封装、事件转换、忙闲查询、创建/更新/删除 |
| `src/backend/app/services/workflow.py` | Work Item、Artifact、Proposal、Authorization、Action Event |
| `src/backend/app/services/completeness.py` | 邮件、日程、文件等必填字段完整性校验 |
| `src/backend/app/services/files.py` | 上传文件保存、类型检查、文本解析 |
| `src/backend/app/services/settings.py` | 用户设置、署名和联系人管理 |
| `src/backend/app/services/memory.py` | 记忆聚合、候选生成、导出 |
| `src/backend/app/services/llm_client.py` | LLM 调用和 Markdown prompt 加载 |

## 数据与迁移

| 路径 | 职责 |
|---|---|
| `src/backend/alembic.ini` | Alembic 配置 |
| `src/backend/alembic/env.py` | 迁移运行环境 |
| `src/backend/alembic/versions/0001_initial_schema.py` | 初始 SQLite 表结构 |
| `src/backend/app/models/base.py` | SQLAlchemy Base |

本地运行时会生成数据库、上传文件和导出文件，默认位于仓库根目录下的 `data/`。该目录是运行数据，不应提交到 GitHub。

## 前端结构

| 路径 | 职责 |
|---|---|
| `src/frontend/src/App.vue` | 应用主布局，组织侧边栏、聊天、Gmail、Calendar、设置等视图 |
| `src/frontend/src/main.ts` | Vue 应用入口 |
| `src/frontend/src/styles.css` | 全局样式 |
| `src/frontend/src/api/*.ts` | 前端请求后端 API 的客户端封装 |
| `src/frontend/src/composables/useAppState.ts` | 前端共享状态 |
| `src/frontend/src/components/chat/` | 聊天页、会话侧栏、消息、输入框、Proposal 卡片 |
| `src/frontend/src/components/gmail/` | Gmail 搜索、列表、详情、草稿表单 |
| `src/frontend/src/components/calendar/` | Calendar 日视图、网格、事件列表、手动编辑 |
| `src/frontend/src/components/settings/` | Google 连接、个人资料、署名、联系人 |

前端通过 Vite 代理访问 `http://127.0.0.1:8000/api`。

## 测试

| 路径 | 覆盖内容 |
|---|---|
| `src/backend/tests/unit/test_health.py` | 健康检查 |
| `src/backend/tests/unit/test_gmail.py` | Gmail MIME、搜索和发送构造 |
| `src/backend/tests/unit/test_calendar.py` | Calendar 事件、忙闲和冲突相关逻辑 |
| `src/backend/tests/unit/test_workflow.py` | Proposal、授权、幂等执行 |
| `src/backend/tests/unit/test_completeness.py` | 必填字段和安全校验 |
| `src/backend/tests/unit/test_assistant_graph.py` | Assistant 图、SSE、会话和工具流程 |
| `src/backend/tests/unit/test_files.py` | 文件上传和解析 |
| `src/backend/tests/unit/test_memory.py` | 记忆、联系人备注和 Markdown 导出 |
| `src/backend/tests/unit/test_logging_observability.py` | 日志脱敏和可观测性 |
| `src/backend/tests/test_agent_tools.py` | Agent 工具行为 |

## 不应提交的内容

以下内容由本地运行或开发工具生成，不属于作业源码：

- `.env`
- `google_oauth.json`
- `data/`
- `.venv/`
- `src/frontend/node_modules/`
- `src/frontend/dist/`
- `.agents/`
- `.superpowers/`
- `.claude/`
- Python 和前端缓存目录
