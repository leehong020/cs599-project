# 验收矩阵

本文档用于说明当前项目与作业提交要求、产品范围和安全边界的对应关系。

## 文档验收

| 项目 | 状态 | 说明 |
|---|---|---|
| README | 已完成 | 包含项目名称、简介、方向、技术栈、目录结构、环境搭建和项目状态 |
| 产品范围 | 已完成 | `src/project-docs/product_scope.md` 说明 MVP 支持能力和边界 |
| 架构决策 | 已完成 | `src/project-docs/architecture_decisions.md` 说明主要技术和安全决策 |
| 安全规则 | 已完成 | `src/project-docs/safety_rules.md` 说明外部写操作、确认、日志和隐私边界 |
| 必填字段 | 已完成 | `src/project-docs/required_fields.md` 说明邮件、日程、文件和上下文字段 |
| 边界行为 | 已完成 | `src/project-docs/behavior_decisions.md` 说明冲突、追问、OAuth、记忆等规则 |
| 代码导览 | 已完成 | `src/project-docs/code_guide.md` 说明当前代码结构 |
| 手工测试脚本 | 已完成 | `src/project-docs/assistant_manual_test_dialogues.md` 用于人工验证聊天能力 |

## 功能验收

| 能力 | 验收标准 | 对应实现 |
|---|---|---|
| Google OAuth | 可跳转授权、处理回调、保存加密 token、查询连接状态、断开连接 | `src/backend/app/api/auth.py`、`src/backend/app/services/oauth.py`、设置页 Google 连接组件 |
| Gmail 读取 | 可搜索邮件、读取邮件详情、读取 thread | `src/backend/app/api/gmail.py`、`src/backend/app/services/gmail.py`、Gmail 前端页面 |
| Gmail 发送 | Assistant 先生成本地邮件草稿，用户确认后发送 | `src/backend/app/graph/tools.py`、`src/backend/app/services/workflow.py`、`src/backend/app/services/gmail.py` |
| Calendar 读取 | 可列出日程、查询忙闲、展示日视图和事件列表 | `src/backend/app/api/calendar.py`、`src/backend/app/services/calendar.py`、Calendar 前端页面 |
| Calendar 写入 | Assistant 通过草稿和确认执行；Calendar 页面手动按钮可直接创建、修改、删除 | `src/backend/app/api/calendar.py`、`src/backend/app/graph/tools.py`、`src/backend/app/services/calendar.py` |
| 文件上传 | 支持上传并解析 txt、md、csv、json、log、xml、html、代码文件、docx、pdf | `src/backend/app/api/files.py`、`src/backend/app/services/files.py`、聊天输入附件 |
| 用户设置 | 可维护资料、默认署名、联系人、默认日历、默认时区等 | `src/backend/app/api/settings.py`、`src/backend/app/services/settings.py`、设置页 |
| Assistant 对话 | 支持多轮聊天、SSE 流式输出、会话列表、会话删除和标题 | `src/backend/app/api/assistant_graph.py`、`src/backend/app/graph/*`、聊天页 |
| 多 Agent 协作 | Supervisor、Context、Mail、Calendar、Review、Confirmation、Executor、Response 分工 | `src/backend/app/graph/multi_nodes.py`、`src/backend/app/config/prompts/*.md` |
| Workflow 安全闭环 | Work Item、Artifact、Proposal、Authorization、Action Event 可追踪 | `src/backend/app/services/workflow.py`、`src/backend/app/api/workflow.py` |
| 记忆与导出 | 支持短期记忆、长期记忆候选、联系人备注和 Markdown 导出 | `src/backend/app/api/memory.py`、`src/backend/app/services/memory.py` |

## 安全验收

| 规则 | 状态 |
|---|---|
| OAuth client secret、token、`.env`、`google_oauth.json` 不提交到 GitHub | 已配置 |
| Assistant 不在无确认情况下发送邮件、创建日程、修改日程或删除日程 | 已实现 |
| Calendar 页面手动写入属于用户显式点击，不作为 Assistant 自动执行路径 | 已说明 |
| Proposal 绑定 version 和 fingerprint，草稿变化会使旧确认失效 | 已实现 |
| 文件解析内容视为不可信上下文，不能绕过安全规则 | 已实现 |
| 日志不记录 token、OAuth secret、完整敏感邮件正文、完整上传文件正文 | 已实现 |
| `data/` 作为本地运行数据目录，不上传 GitHub | 已配置 |

## 测试验收

| 类型 | 命令 |
|---|---|
| 后端单元测试 | `cd src/backend && ..\..\.venv\Scripts\python -m pytest` |
| 后端静态检查 | `cd src/backend && ..\..\.venv\Scripts\python -m ruff check .` |
| 前端生产构建 | `cd src/frontend && npm run build` |

## 手工演示场景

| 场景 | 达标表现 |
|---|---|
| 连接 Google | 设置页显示授权状态，授权成功后可读取 Gmail 和 Calendar |
| 搜索 Gmail | Gmail 页可查询并展示邮件列表和详情 |
| 写邮件 | 聊天输入自然语言后生成本地邮件草稿，确认后才发送 |
| 回复邮件 | 选中邮件或 thread 后生成回复草稿，目标不明确时追问 |
| 创建日程 | 聊天生成本地日程草稿，确认后创建真实 Calendar 事件 |
| 修改日程 | 选中已有日程后生成修改草稿，确认后更新真实事件 |
| 删除日程 | Assistant 先生成删除确认，确认后删除；Calendar 页面按钮可手动删除 |
| 上传文件 | 文件内容可作为摘要或草稿依据，但不能包含指令绕过确认 |
| 联系人解析 | 设置页联系人唯一匹配时可用于收件人和参会人 |
| 普通聊天 | 不输出内部工具名、节点名、artifact id 或 Google Event ID |
