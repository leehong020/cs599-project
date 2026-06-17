# 代码导览

本文档是给 vibe coding 使用的代码地图。每个阶段新增或修改代码后，都必须同步更新这里。

阅读原则：

- 按目录结构理解项目，不需要一次读完所有文件；
- 先看“当前阶段入口”，再按功能追到具体文件；
- `node_modules/`、`dist/`、`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`、`data/runtime/` 都是生成物或运行时文件，不需要人工阅读；
- 代码中的注释和 docstring 必须使用中文；英文只保留在代码标识符、API 名、表名、状态枚举中。

## 当前阶段入口

阶段 25 为日程页增加人工增删改查：

```text
明确产品边界：日程页人工点击新增、编辑、删除会直接写 Google Calendar
Assistant 聊天代办仍然必须先生成本地日程草稿，等用户确认后才作用于 Google Calendar
后端 /api/calendar/events 重新作为日程页人工写入接口，支持 create/update/delete
前端日程页新增“新建日程”按钮、编辑弹窗、删除按钮和列表项选择
用户在日程页或 Assistant 创建出的真实 Google 日程都会出现在同一个日程列表里，双方都能继续查看、修改、删除
```

阶段 24 优化聊天页附件展示：

```text
聊天输入上传文件后，用户气泡只展示用户输入的需求和附件 chip，不再把解析出的文件全文拼到用户消息下面
文件解析文本仍会作为 hidden selected_context_refs 传给 Assistant，保证模型能读取附件内容
附件解析失败时，用户气泡显示“解析失败”状态，但不会把失败详情刷屏展示
```

阶段 23 新增 Assistant 手工对话测试脚本：

```text
新增 docs/assistant_manual_test_dialogues.md
测试脚本以聊天页 Assistant 为核心，按真实用户输入组织手工回归用例
覆盖普通对话、联系人、默认署名、单封邮件、多封邮件、本地草稿、Gmail 搜索、选中邮件回复、日程查询、创建、修改、删除、冲突处理、组合任务、文件上传、记忆、会话隔离、安全确认和幂等
每个用例都写明前置条件、用户输入和达标标准，方便复制到聊天页逐项验证
```

阶段 22 优化前端字号、图标和侧边栏可读性：

```text
全局基础字号从 15px 提升到 16px，并提升正文行高，降低聊天气泡和列表文字的紧绷感
左侧主图标栏从 64px 调整为 72px，品牌按钮和导航图标同步放大
聊天会话侧边栏从 260px 调整为 300px，历史会话条目高度和字号同步增加
聊天消息区增加横向留白，assistant 气泡、Proposal 卡片、输入框和按钮尺寸整体放大
文件附件预览、发送按钮、加载提示和 Markdown 列表间距同步调整，避免看起来像浏览器缩放过小
```

阶段 21 修复普通对话体验和 SSE 二次模型调用：

```text
Supervisor Agent 改为输出结构化 JSON 路由计划
普通聊天由 Supervisor 的 direct_response 承接，不再让 Response Agent 二次调用模型
Response Agent 提示词强化自然对话，不把普通问候强行变成邮件/日程说明
Response Agent 上下文改为当前轮任务优先，不再把旧 active draft 详情直接喂给最终回复模型
Mail/Calendar Agent 提示词明确旧草稿只是背景，新建任务不默认修改或提醒旧草稿
Calendar Agent 使用默认署名作为组织者/本人显示名，但不把署名写入外部参会人 attendees
聊天回复不再显示 Google Event ID、external_event_id 等内部日程标识
SSE 接口不再读取旧 streaming_context 进行二次流式生成，避免内部 response_agent 标签泄漏
SSE 会先推送准备/理解进度，再运行主图，避免 DeepSeek 慢响应时前端空白等待
LLM 客户端新增请求超时和一次重试，避免外部模型无响应导致聊天页一直卡住
```

阶段 20 恢复多 LLM Agent 工作流主图：

```text
主图从单 agent_node 切换为多 LLM Agent + 非 LLM 工作流节点
LLM Agent 包含 supervisor_agent、context_agent、mail_agent、calendar_agent、response_agent
非 LLM 节点包含 state_loader、review_gate、confirmation_gate、executor、memory_extractor
新增通用 run_llm_agent runtime，复用 tool_calls、DSML 解析、工具观察和 fallback 回复能力
新增 create_tools_for_agent，按 Agent 职责隔离工具集
发送邮件、执行日程创建/删除仍由 confirmation_gate + executor 确定性执行
新增专用 prompt：supervisor_agent、context_agent、mail_agent_tools、calendar_agent_tools、response_agent
```

阶段 19 修复多封邮件确认发送和本地草稿详情：

```text
新增 send_all_local_email_drafts 工具，批量发送当前线程打开中的本地邮件草稿
上一轮 assistant 明确提示“两封/多封邮件”后，用户回复“确认发送”会走批量发送
批量发送仍逐封走 Proposal -> Authorization -> Execution，不绕过安全链路
同一线程残留合并草稿和单人草稿时，批量发送优先发送单人分别草稿
邮箱页点击本地草稿不再调用 Gmail message API，而是读取 Work Item 详情
邮箱页本地草稿详情支持展示收件人、主题和正文，也支持删除本地草稿
```

阶段 18 让聊天 AI 管理本地邮件草稿：

```text
不实现 Gmail 草稿同步，继续保留本地 SQLite 草稿作为 AI 多轮修改层
新增本地邮件草稿工具：列出、读取、删除单封、清空所有
用户问“草稿箱”时，AI 应区分 Gmail 远端草稿和本地邮件草稿
删除本地草稿采用确认式流程，首次列出候选，用户确认后才真正删除
删除本地草稿只清理 SQLite Work Item / Artifact / Proposal 关联记录，不调用 Gmail
```

阶段 17 修复聊天联系人事实源优先级：

```text
新增 resolve_contact 工具，聊天 agent 可显式查询设置页联系人
联系人不再只依赖 prompt 中的 available_contacts 文本，避免模型漏看后说“找不到”
联系人策略调整为事实源优先级：直接邮箱 > 设置页联系人 > 邮件/历史线索 > 追问用户
设置页联系人唯一匹配时直接使用邮箱；多个候选或事实冲突时再请用户确认
邮件和日程共用联系人解析兜底，参会人也可以写“赵涛”这类联系人姓名
```

阶段 16 修复联系人解析、日程删除和署名设置：

```text
邮件工具会把“赵涛”这类联系人姓名解析为设置页联系人邮箱
创建/修改邮件草稿时会读取当前默认署名；历史无默认标记时退回第一条署名
署名设置页改为单行输入，只保存一个默认署名
删除日程不再直接拒绝，而是先创建本地删除草稿
用户确认删除后走 delete_calendar_event Proposal、Authorization、Execution
Calendar 删除执行写入 action_events，重复确认按幂等 key 返回已有结果
```

阶段 15 修复日程确认创建和日程列表加载问题：

```text
用户回复“确认创建”等确认式短语时，agent_node 会先走确定性工具执行分支
确认创建日程会直接调用 execute_calendar_event_draft，工具成功才回复“已创建”
确认发送邮件会直接调用 send_email_draft，工具成功才回复“已发送”
如果工具失败，assistant 回复失败原因，不再让模型自行编造成功结果
Calendar 列表视图挂载后会自动读取事件，不再必须手动点“刷新”
```

阶段 14 在阶段 13 基础上简化聊天展示、强化联系人读取，并把署名设置收敛成单一署名：

```text
聊天页不再展示邮件/日程 DraftCard
SSE final 仍保留 artifacts 字段兼容旧客户端，但固定返回空列表
assistant 回复需要在文本中直接列出邮件内容或日程内容
后端仍保留数据库 Artifact，用于确认发送、日程创建、版本和幂等控制
历史 assistant 消息不再携带或恢复 artifacts
设置页署名只有一个 textarea，不再暴露标签、默认开关或多署名列表
后端保存署名时会清理同一用户的旧署名，确保只有一个默认署名
联系人每轮从数据库注入 available_contacts
用户提到联系人姓名时，agent 优先读取 available_contacts 或调用 resolve_contact；唯一匹配时直接使用邮箱
```

阶段 13 在阶段 12 基础上补齐邮件和日程的 active draft、安全确认执行、默认设置和联系人管理：

```text
每轮聊天都会加载当前会话打开中的 email_draft 和 calendar_event_draft
用户补充信息时默认更新当前 active draft，不再重复创建草稿
前端选中的日程会作为 selected_context_refs 随聊天请求发送
邮件草稿允许字段暂时不完整，assistant 回复会说明缺失字段
邮件正文会做确定性格式化：称呼独立、正文段落缩进、署名独立
默认署名来自 settings/signatures，存在时自动使用且避免重复追加
“确认发送”调用 send_email_draft，内部走 Proposal -> Authorization -> Execution
日程创建工具只创建本地 calendar_event_draft，不直接写 Google Calendar
日程确认创建调用 execute_calendar_event_draft，执行前仍由 Calendar 服务二次 Freebusy
选中已有日程后修改会生成 calendar update draft，确认后执行 update_calendar_event Proposal
日程冲突会显示在 assistant 回复里，用户明确“仍然创建”才会写入 conflict_override
聊天工具不直接删除 Google Calendar 日程
Calendar 普通 API 的直接 create/update/delete 已限制，避免绕过确认执行链路
设置页新增联系人管理，联系人同时用于邮件收件人和日程参会人解析
```

阶段 12 在阶段 11 基础上把聊天主流程收敛为 LangChain `@tool` agent 逻辑：

```text
聊天页只发送自然语言和可选上下文
LangGraph 主图进入单 agent 节点
agent 可多轮调用 LangChain @tool
DeepSeek 返回的 DSML 文本工具调用会被解析执行，不会泄漏给用户
工具调用只写后端日志，前端不展示工具过程
工具统一返回 JSON 字符串，包含 ok、code、message、data
创建/修改邮件草稿时，工具曾返回 email_draft 卡片数据（阶段 14 已废弃聊天卡片）
创建/修改日程草稿时，工具曾返回 calendar_event_draft 卡片数据（阶段 14 已废弃聊天卡片）
agent_node 曾从工具结果中收集 artifacts（阶段 14 已改为空列表）
普通聊天不显示卡片
创建/修改邮件或日程时，当前只在 assistant 文本里展示内容
SSE final 保留 response 和 artifacts 字段，但 artifacts 固定为空列表
前端不再把 artifacts 挂到 assistant 消息上
记忆工具必须真实写入 SQLite 后才返回成功
```

阶段 11 的目标是在阶段 10 基础上完成本地 MVP 发布验收：

```text
FastAPI 后端可启动
SQLite 可迁移
Vue 前端可启动
前端可通过 Vite 代理请求后端
前端可发起 Google 授权
后端可加密保存 OAuth Token
用户可维护发件账号、时区、默认日历和署名
邮件和日程草稿可校验关键字段完整性
每个关键字段可记录和查询 Field Evidence
仅 AI 推断的字段不得进入 proposal_ready
Gmail 可搜索、读取详情和读取线程
Gmail MIME 正文可解析，HTML 可转纯文本
邮件草稿只创建本地 Artifact，不写 Gmail Draft
已授权 Proposal 可由执行服务创建 Gmail Draft 并发送
Calendar 可读取未来事件、查询 Freebusy 并判断冲突
日程草稿只创建本地 Artifact，不写 Google Calendar
已授权 Proposal 可由执行服务创建或更新 Calendar Event
后端可列出多个 Open Work Item
本地邮件和日程 Artifact 可生成带 version 和 fingerprint 的 Proposal
用户确认会写入 Authorization，修改后的旧 Proposal 会失效
“确认发送”只匹配邮件 Proposal，多候选时返回追问状态
已授权 Proposal 可经统一 Execution Service 分发到 Gmail 或 Calendar 执行
重复执行会读取已有 Action Event，避免重复发送或重复创建日程
前端可查看 Work Item、Proposal、授权、拒绝和执行结果
LangGraph 主图可编译并运行
Mail Subgraph 和 Calendar Subgraph 可单独运行
用户请求可编译成多任务 DAG，并区分并行批次和顺序依赖批次
同名联系人会触发追问，不会静默选择邮箱
主图和子图可导出 Mermaid
主图使用 `thread_id` 和 SQLite checkpoint 恢复状态
后端提供 SSE 聊天进度流
前端可恢复聊天历史并通过底部输入发送消息
右侧可展示完整邮件 Proposal 卡片和日程 Proposal 卡片
Proposal 按钮携带 ID、version 和 fingerprint
聊天式“确认发送”会走阶段 6 的确认候选和授权逻辑
旧草稿可带回表单修改，重新保存后生成新 Proposal
短期记忆可聚合最近消息、摘要、Open Work Items、Pending Proposals、任务 DAG、Artifact 摘要和执行结果
长期记忆只在用户明确长期意图时写入候选，临时指令不会污染长期记忆
联系人备注按需召回，不注入无关 Prompt
偏好、署名、联系人和审计可导出为 Markdown
SQLite 仍是偏好、署名、联系人、记忆和审计的事实来源
日志会统一脱敏 token、client secret、完整 Prompt 和完整邮件正文
审计日志只记录白名单字段，避免敏感正文进入日志
Workflow 会记录 Proposal 创建、确认、拒绝、执行开始、执行成功和执行失败审计事件
上传文件或文件解析得到的字段不能直接进入 proposal_ready
LangGraph 主图节点会返回 node_timings，用于观察每个节点耗时
Mermaid 图、SSE、SQLite checkpoint、Prompt Injection 防护和重复确认都有测试覆盖
根目录提供 `.env.example`，用于创建本地 `.env`
`.gitignore` 覆盖运行时数据库、日志、Markdown 导出、依赖和构建产物
README 给出迁移、后端启动、前端启动和验证命令
阶段 11 发布状态、限制和后续真实联调范围已记录
测试命令可运行
```

最常看的文件：

- `backend/app/main.py`：后端应用入口。
- `backend/app/api/auth.py`：Google OAuth 接口。
- `backend/app/api/calendar.py`：Calendar 读取、Freebusy 和本地日程草稿接口。
- `backend/app/api/completeness.py`：字段完整性校验和 Field Evidence 接口。
- `backend/app/api/files.py`：文件上传、解析、读取和删除接口。
- `backend/app/api/gmail.py`：Gmail 搜索、读取和准备本地邮件草稿接口。
- `backend/app/api/settings.py`：用户设置、署名和联系人接口。
- `backend/app/api/workflow.py`：Work Item、Proposal、授权和执行接口。
- `backend/app/api/assistant_graph.py`：阶段 8 主图运行、SSE 聊天流、状态读取、Mermaid 和子图调试接口。
- `backend/app/api/memory.py`：阶段 9 短期记忆、长期记忆候选、联系人备注和 Markdown 导出接口。
- `backend/app/core/logging.py`：阶段 10 日志脱敏、审计事件和错误追踪基础设施。
- `backend/app/graph/builder.py`：LangGraph 主图和子图编译入口。
- `backend/app/graph/nodes.py`：主图节点实现；阶段 12 起负责多轮 `@tool` 循环和 DeepSeek DSML 工具调用解析；阶段 14 起不再收集聊天卡片 artifacts。
- `backend/app/graph/observability.py`：阶段 10 主图节点耗时统计包装器。
- `backend/app/graph/runner.py`：带 SQLite checkpoint 的主图运行入口；阶段 13 起会把 active draft、默认设置和联系人上下文注入图状态。
- `backend/app/graph/tasks.py`：任务 DAG 编译、联系人解析和执行批次计算。
- `backend/app/services/calendar.py`：Calendar REST 客户端、Freebusy 冲突判断、本地日程 Artifact 和执行逻辑。
- `backend/app/services/completeness.py`：关键字段规则、追问合并、Field Evidence 读写逻辑。
- `backend/app/services/files.py`：TXT/MD/DOCX/PDF 上传保存、文本解析和解析状态记录逻辑。
- `backend/app/services/gmail.py`：Gmail REST 客户端、MIME 解析、本地邮件 Artifact 和发送执行逻辑。
- `backend/app/services/oauth.py`：OAuth URL、token 交换、加密保存和刷新逻辑。
- `backend/app/services/draft_context.py`：阶段 13 新增的 active draft 查询、Artifact 更新和 Work Item 关闭服务。
- `backend/app/services/settings.py`：用户设置、署名和联系人读写逻辑。
- `backend/app/services/workflow.py`：Proposal 生成、确认目标解析、授权校验和统一执行分发逻辑。
- `backend/app/services/memory.py`：阶段 9 短期记忆聚合、长期记忆候选和 Markdown 导出逻辑。
- `backend/app/schemas/completeness.py`：字段来源和完整性结果结构。
- `backend/app/schemas/files.py`：上传文件和文件解析结果 API 结构。
- `backend/app/schemas/calendar.py`：Calendar 和日程草稿 API 结构。
- `backend/app/schemas/gmail.py`：Gmail 和邮件草稿 API 结构。
- `backend/app/schemas/workflow.py`：Work Item、Proposal、授权和执行响应结构。
- `backend/app/schemas/assistant_graph.py`：阶段 10 主图、SSE 和节点耗时 API 结构。
- `backend/app/schemas/memory.py`：阶段 9 短期记忆、长期记忆和 Markdown 导出 API 结构。
- `backend/tests/unit/test_assistant_graph.py`：阶段 7 主图、子图、DAG、Mermaid 和恢复测试。
- `backend/tests/unit/test_completeness.py`：阶段 3 安全规则测试。
- `backend/tests/unit/test_files.py`：文件上传、DOCX 解析和删除测试。
- `backend/tests/unit/test_calendar.py`：阶段 5 Freebusy、冲突和事件转换测试。
- `backend/tests/unit/test_gmail.py`：阶段 4 MIME 解析和 RFC 822 构造测试。
- `backend/tests/unit/test_workflow.py`：阶段 6 Proposal fingerprint、旧授权失效和确认目标筛选测试。
- `backend/tests/unit/test_memory.py`：阶段 9 短期记忆、长期记忆、联系人备注、Markdown 导出和子图隔离测试。
- `backend/tests/unit/test_logging_observability.py`：阶段 10 日志脱敏、审计字段白名单和可观测性测试。
- `docs/release_status.md`：阶段 11 本地发布状态、限制和启动命令摘要。
- `backend/app/api/health.py`：健康检查接口。
- `backend/alembic/versions/0001_initial_schema.py`：初始数据库迁移。
- `frontend/src/App.vue`：阶段 8 前端页面，包含聊天、Gmail、Calendar 和 Workflow 工作台。
- `frontend/src/api/auth.ts`：前端 Google 授权 API 客户端。
- `frontend/src/api/calendar.ts`：前端 Calendar API 客户端。
- `frontend/src/api/gmail.ts`：前端 Gmail API 客户端。
- `frontend/src/api/workflow.ts`：前端 Workflow API 客户端。
- `frontend/src/api/assistant.ts`：前端阶段 10 主图、SSE 和节点耗时 API 客户端；阶段 14 起聊天页不再使用 `AssistantTurnResponse.artifacts`。
- `frontend/src/api/files.ts`：前端文件上传和解析结果 API 客户端。
- `frontend/src/api/memory.ts`：前端阶段 9 记忆和 Markdown 导出 API 客户端。
- `frontend/src/api/settings.ts`：前端用户设置、署名和联系人 API 客户端。
- `frontend/src/api/health.ts`：前端健康检查请求。

## 阶段 12 改动文件

## 阶段 25 改动文件

### `backend/app/api/calendar.py`

阶段 25 调整：
- `/api/calendar/events` 支持日程页人工创建 Google Calendar 日程。
- `/api/calendar/events/{event_id}` 的 `PUT` 支持日程页人工更新 Google Calendar 日程。
- `/api/calendar/events/{event_id}` 的 `DELETE` 支持日程页人工删除 Google Calendar 日程。
- 文件注释明确：这些直接写接口只服务日程页人工操作，Assistant 仍然走确认链路。

### `frontend/src/api/calendar.ts`

阶段 25 调整：
- 新增 `CalendarEventPayload` 类型。
- 新增 `createCalendarEvent()`、`updateCalendarEvent()`、`deleteCalendarEvent()` 前端 API 客户端。

### `frontend/src/components/calendar/CalendarView.vue`

阶段 25 调整：
- 页面头部新增“新建日程”按钮。
- 新增日程表单弹窗，支持标题、开始时间、结束时间、地点、参会人邮箱和描述。
- 选中日程详情弹窗新增“编辑”和“删除”按钮。
- 编辑保存和删除会直接调用 Google Calendar 写接口，成功后刷新当前日程视图。
- 选中日程仍会写入 `selectedContextRefs`，Assistant 可以继续基于选中日程处理聊天请求。

### `frontend/src/components/calendar/EventList.vue`

阶段 25 调整：
- 列表视图中的日程条目支持点击选中，并复用 CalendarView 的详情、编辑和删除弹窗。

### `docs/behavior_decisions.md`

阶段 25 调整：
- 记录日程页人工 CRUD 和 Assistant 代办确认链路的边界差异。

## 阶段 24 改动文件

### `frontend/src/components/chat/ChatInput.vue`

阶段 24 调整：
- 发送附件时拆分 `displayMessage` 和 `modelMessage`。
- `displayMessage` 只用于聊天页展示用户输入，不包含文件全文。
- `modelMessage` 保留附件提示，供后端理解本轮任务。
- 文件解析文本放入 `fileRefs[].extracted_text`，作为隐藏上下文传给 Assistant。

### `frontend/src/components/chat/ChatView.vue`

阶段 24 调整：
- `handleSend()` 接收结构化发送 payload。
- 用户消息气泡显示 `displayMessage` 和附件 chip。
- 后端请求仍发送 `modelMessage` 与 `selected_context_refs`，避免 Assistant 失去附件内容。

### `frontend/src/components/chat/ChatMessage.vue`

阶段 24 调整：
- 新增附件 chip 展示能力。
- 用户上传文件后，消息气泡旁显示文件名和解析状态，不展示文件正文全文。

## 阶段 23 改动文件

### `docs/assistant_manual_test_dialogues.md`

阶段 23 新增：
- 这是一份面向人工测试的 Assistant 对话脚本。
- 文档按功能域组织测试用例，每个用例包含前置条件、用户输入和达标标准。
- 覆盖普通聊天、邮件草稿、批量邮件、本地草稿、Gmail 上下文、日程操作、文件解析、长期记忆、会话隔离、安全确认和幂等恢复。
- 用于补充 `docs/acceptance_matrix.md`，后者偏验收矩阵，本文件偏真实对话回归测试。

## 阶段 22 改动文件

### `frontend/src/styles.css`

阶段 22 调整：
- 放大全局基础字号、行高、页面头部、聊天消息、Proposal 卡片、表单、按钮和设置页常用控件。
- 将主图标侧边栏宽度调整为 72px，并放大品牌按钮和导航按钮，避免左侧导航显得过窄。
- 放大聊天输入区、附件预览和发送按钮，让底部操作区与消息正文视觉比例一致。

### `frontend/src/components/AppSidebar.vue`

阶段 22 调整：
- 更新中文注释，把主图标导航栏说明从旧的 52px 修正为当前 72px。

### `frontend/src/components/chat/SessionSidebar.vue`

阶段 22 调整：
- 将会话历史侧边栏宽度调整为 300px，并增加“新会话”按钮、会话条目、图标和删除按钮尺寸。
- 让会话标题更容易阅读，减少侧栏和主内容之间比例失衡的问题。

### `frontend/src/components/chat/ChatView.vue`

阶段 22 调整：
- 增加聊天消息区左右内边距和消息间距。
- 放大“正在生成回复”提示字号，使流式等待状态不再显得突兀偏小。

### `frontend/src/components/chat/ChatMessage.vue`

阶段 22 调整：
- 放宽消息堆叠宽度，并调整 Markdown 列表、加粗文字和列表项间距。
- 让 assistant 的长回复更像正常阅读文本，而不是密集的小字号说明块。

### `frontend/src/components/chat/ChatInput.vue`

阶段 22 调整：
- 放大附件按钮、附件预览文字和移除按钮。
- 保持输入框区域高度稳定，同时让用户输入文字和发送按钮更清楚。

## 阶段 21 改动文件

### `backend/app/config/prompts/supervisor_agent.md`

阶段 21 调整：

- Supervisor Agent 输出结构化 JSON，包含 `intent`、`summary`、`route_agents`、`direct_response` 和 `reason`。
- 普通聊天、问候、体验反馈和概念解释会被提示词引导为 `response_agent` 轻量路径。
- `direct_response` 由模型生成自然回复草案，避免把“你好”写成硬编码规则。

### `backend/app/config/prompts/response_agent.md`

阶段 21 调整：

- Response Agent 会优先承接 Supervisor Plan 中的 `direct_response`。
- 普通聊天不再强行输出邮件/日程功能说明。
- 明确禁止输出 `response_agent`、`supervisor_agent`、`route_agents` 等内部节点名。
- 明确禁止输出 Google Event ID、external_event_id、artifact_id、work_item_id 等内部 ID。

### `backend/app/config/prompts/calendar_agent_tools.md`

阶段 21 调整：

- 明确默认署名只能用于组织者/本人显示名，不应写入 attendees。
- attendees 只表示需要邀请的外部参会人；未指定外部参会人时应说“未邀请其他参会人”。
- 明确禁止输出 Google Event ID、external_event_id、artifact_id、work_item_id 等内部 ID。

### `backend/app/graph/multi_nodes.py`

阶段 21 调整：

- 新增 `_parse_supervisor_json()`，解析 Supervisor Agent 的结构化 JSON 输出。
- 新增 `_normalize_route_agents()`，清洗模型输出的 Agent 路由列表。
- `_json_context()` 新增 `audience` 参数；给 Response Agent 的上下文只保留旧草稿存在性摘要，不暴露旧草稿详细内容。
- `supervisor_agent()` 会优先使用模型结构化路由，解析失败时再走兼容兜底。
- `response_agent()` 在普通聊天且没有工具结果时，直接使用 `direct_response`，避免同一轮重复调用 DeepSeek。

### `backend/app/graph/tools.py`

阶段 21 调整：

- `_calendar_card_data()` 增加 `organizer_email` 和 `organizer_display_name`，供 Calendar Agent 区分组织者和外部参会人。
- `create_calendar_event_draft()` 优先用默认署名作为 `organizer_display_name`，其次使用用户显示名或 Google 邮箱。
- 日程更新/删除相关失败文案不再暴露 Google Event ID 这种内部字段名。

### `backend/app/graph/nodes.py`

阶段 21 调整：

- `_deterministic_tool_reply()` 的日程创建/删除成功回复不再显示 Google Event ID。

### `backend/app/api/assistant_graph.py`

阶段 21 调整：

- `/api/assistant/turn/stream` 改为异步事件生成器，先返回进度事件，再运行主图。
- 删除旧的 `streaming_context -> stream_response()` 二次模型调用链路。
- 最终回复只使用主图 `state["response"]`，避免内部提示词或节点名泄漏到聊天页。

### `backend/app/services/llm_client.py`

阶段 21 调整：

- `ChatOpenAI` 增加 `timeout=settings.llm_timeout_seconds`。
- `ChatOpenAI` 增加 `max_retries=1`，外部模型偶发失败时只做一次轻量重试。

### `backend/app/core/config.py`

阶段 21 调整：

- 新增 `llm_timeout_seconds` 配置项，默认 45 秒。

### `.env.example`

阶段 21 调整：

- 新增 `LLM_TIMEOUT_SECONDS=45` 示例和中文说明。

### `backend/tests/unit/test_assistant_graph.py`

阶段 21 新增回归测试：

| 名称 | 类型 | 作用 |
|---|---|---|
| `test_general_chat_reuses_supervisor_direct_response()` | 测试函数 | 验证普通聊天只调用一次模型，并使用 Supervisor 的自然回复。 |
| `test_response_agent_context_does_not_expose_stale_active_draft_details()` | 测试函数 | 验证最终回复模型不会看到无关旧 active draft 详情，避免主动汇总旧任务。 |

## 阶段 20 改动文件

### `backend/app/graph/builder.py`

阶段 20 调整：

- 主图节点改为 `state_loader -> supervisor_agent -> context_agent -> mail_agent -> calendar_agent -> review_gate -> confirmation_gate -> executor -> response_agent -> save_turn -> memory_extractor`。
- Mermaid 导出会真实展示多 Agent 和 Gate/Executor 节点。

### `backend/app/graph/agents/runtime.py`

阶段 20 新增：

- 通用 LLM Agent 运行时，集中处理模型调用、工具调用、DeepSeek DSML 解析、工具结果观察和 fallback 回复。
- `run_llm_agent()` 供 Supervisor、Context、Mail、Calendar 和 Response Agent 复用。

### `backend/app/graph/multi_nodes.py`

阶段 20 新增：

- `state_loader()`：复用原上下文加载逻辑，作为多 Agent 主图入口。
- `supervisor_agent()`：调用模型识别任务并生成 Agent 路由计划。
- `context_agent()`：调用模型整理选中上下文、文件和历史信息。
- `mail_agent()`：调用模型处理邮件和本地邮件草稿，只能看到邮件相关工具。
- `calendar_agent()`：调用模型处理日程查询、草稿和冲突说明，只能看到日程相关工具。
- `review_gate()`：确定性检查风险和草稿状态，不调用模型。
- `confirmation_gate()`：确定性识别确认发送、确认创建和确认删除，不调用模型。
- `executor()`：只执行已确认动作，复用现有确定性执行兜底。
- `response_agent()`：调用模型整合结果；如果 Executor 已真实执行，则直接采用执行结果避免模型伪造成功。
- `memory_extractor()`：复用原记忆候选提取逻辑。

### `backend/app/graph/tools.py`

阶段 20 调整：

- 新增 `AGENT_TOOL_NAMES`，定义每个 Agent 可见的工具白名单。
- 新增 `create_tools_for_agent()`，按 Agent 名称返回工具子集。
- Mail/Calendar Agent 不直接拿发送或执行类工具；外部写操作仍交给 Executor。

### `backend/app/config/prompts/*.md`

阶段 20 新增：

- `supervisor_agent.md`：负责意图理解和 Agent 路由。
- `context_agent.md`：负责上下文整理。
- `mail_agent_tools.md`：负责邮件、本地草稿、联系人和多封邮件规则。
- `calendar_agent_tools.md`：负责日程查询、草稿、修改、删除和冲突规则。
- `response_agent.md`：负责最终自然语言回复。

### `backend/app/api/assistant_graph.py`

阶段 20 调整：

- SSE progress 文案改为多 Agent 节点名称。

### `backend/app/graph/observability.py`

阶段 20 调整：

- 将 `state_loader` 识别为每轮首节点，重置本轮节点耗时。

### `backend/tests`

阶段 20 调整：

- 主图测试改为断言多 Agent/Gate/Executor 节点。
- 工具测试新增 Agent 工具白名单隔离断言。
- 图测试统一 mock LLM，避免单元测试依赖真实 DeepSeek 调用。

## 阶段 19 改动文件

### `backend/app/graph/tools.py`

阶段 19 调整：

- 新增 `send_all_local_email_drafts()`，用于多封本地邮件草稿的确认发送。
- 批量发送内部逐封调用现有 `send_email_draft()`，每封仍经过 Proposal、Authorization 和 Execution。
- 当同一线程同时存在合并收件人草稿和单人分别草稿时，优先发送单人分别草稿，降低误发旧合并草稿的风险。

新增关键函数和工具：

| 名称 | 类型 | 作用 |
|---|---|---|
| `_format_email_items_for_text()` | 函数 | 把工具返回的邮箱列表转成回复文本。 |
| `send_all_local_email_drafts()` | `@tool` | 用户确认后批量发送当前线程打开中的本地邮件草稿。 |

### `backend/app/graph/nodes.py`

阶段 19 调整：

- 新增 `_previous_assistant_requested_batch_send()`，识别上一轮 assistant 是否提示确认发送多封邮件。
- 新增 `_should_batch_email_send()`，判断本轮确认是否应走批量发送。
- `_try_deterministic_confirmation()` 在批量确认时调用 `send_all_local_email_drafts`，不再只发 active 单封。
- `_deterministic_tool_reply()` 增加批量发送结果展示。

### `frontend/src/components/gmail/GmailView.vue`

阶段 19 调整：

- 草稿箱中的本地草稿点击后调用 `fetchWorkItem()`，不再调用 Gmail message API。
- 将本地 `artifact_content` 转成 `GmailMessageDetail`，复用邮件详情展示组件。
- 删除本地草稿时调用 `deleteWorkItem()`；删除 Gmail 邮件时仍调用 `deleteGmailMessage()`。

### `frontend/src/components/gmail/GmailMessageList.vue`

阶段 19 调整：

- 本地草稿没有 Gmail thread，不再显示“线程”按钮，避免误触发 Gmail thread 查询。

### `backend/tests/test_agent_tools.py`

阶段 19 调整：

- 工具集合测试加入 `send_all_local_email_drafts`。
- 新增批量确认发送回归测试，确保上一轮提示两封邮件后，“确认发送”走批量工具。

## 阶段 18 改动文件

### `backend/app/graph/tools.py`

阶段 18 调整：

- 新增本地邮件草稿管理工具，聊天 AI 可以查看、读取、删除 SQLite 中的本地邮件草稿。
- 本地草稿删除只清理本地数据库，不调用 Gmail API。
- 删除单封或全部本地草稿都带 `confirm` 参数，prompt 要求用户明确确认后才执行。
- 删除时会清理关联的 `field_evidence`、`proposal_items`、`action_authorizations`、`action_events`、`artifacts` 和 `work_items`。

新增关键函数和工具：

| 名称 | 类型 | 作用 |
|---|---|---|
| `_local_email_draft_from_row()` | 函数 | 把本地邮件草稿 SQL 查询结果转成稳定字典。 |
| `_format_local_email_draft_line()` | 函数 | 生成本地草稿列表的文本摘要。 |
| `_delete_local_work_items()` | 函数 | 删除本地 Work Item 及其关联数据，不调用 Gmail。 |
| `list_local_email_drafts()` | `@tool` | 列出打开中的本地邮件草稿，可选包含关闭历史。 |
| `read_local_email_draft()` | `@tool` | 读取单封本地邮件草稿详情。 |
| `delete_local_email_draft()` | `@tool` | 用户确认后删除单封本地邮件草稿。 |
| `delete_all_local_email_drafts()` | `@tool` | 用户确认后清空打开中的本地邮件草稿。 |

### `backend/app/config/prompts/system_prompt.md`

阶段 18 调整：

- 明确“草稿箱”包含两个来源：Gmail 远端草稿和本地邮件草稿。
- 要求查看草稿箱时同时查询 Gmail `is:draft` 和 `list_local_email_drafts`。
- 要求删除本地邮件草稿前先列出候选并等待确认。

### `backend/tests/test_agent_tools.py`

阶段 18 调整：

- 工具集合测试加入四个本地邮件草稿管理工具。
- 新增本地草稿摘要解析回归测试。

## 阶段 17 改动文件

### `backend/app/graph/tools.py`

阶段 17 调整：

- 新增 `resolve_contact()` 工具，让 agent 在写邮件、创建日程或回答“某人的邮箱是什么”前，可以显式读取设置页联系人。
- 新增联系人匹配辅助函数，先精确匹配姓名，再做包含匹配；不唯一时返回候选，不静默猜测。
- 日程参会人解析复用邮件联系人解析逻辑，用户可以输入联系人姓名而不只限邮箱。

新增关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `_contact_to_json()` | 函数 | 把联系人对象转成稳定 JSON 字典。 |
| `_resolve_contact_matches()` | 函数 | 按姓名从设置页联系人中查找候选。 |
| `_resolve_calendar_attendees()` | 函数 | 把日程参会人文本解析为 `CalendarAttendee` 列表。 |
| `resolve_contact()` | `@tool` | 查询设置页联系人，唯一匹配时返回邮箱，歧义或缺失时返回结构化原因。 |

### `backend/app/config/prompts/system_prompt.md`

阶段 17 调整：

- 联系人策略改为“事实源优先级”，不再写成单一硬规则。
- 明确直接邮箱、设置页联系人、邮件/历史线索和追问用户的优先顺序。
- 明确多个候选或事实源冲突时需要让用户确认。

### `backend/tests/test_agent_tools.py`

阶段 17 调整：

- 工具集合测试加入 `resolve_contact`。
- 新增联系人解析回归测试，验证设置页中的“赵涛”可以被工具解析成邮箱。

## 阶段 16 改动文件

### `backend/app/graph/tools.py`

阶段 16 调整：

- `create_email_draft()` 和 `update_email_draft()` 会解析联系人姓名，不再只接受邮箱字符串。
- 邮件草稿创建和正文更新会读取当前默认署名。
- `delete_calendar_event()` 改为创建日程删除草稿，不直接删除 Google Calendar。
- 新增 `execute_calendar_event_delete_draft()`，确认后通过 Workflow 执行删除。

新增关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `_split_recipient_tokens()` | 函数 | 将收件人文本拆成邮箱或联系人姓名。 |
| `_get_default_signature_content()` | 函数 | 读取当前用户默认署名，历史无默认时退回第一条。 |
| `_resolve_contact_emails()` | 函数 | 根据设置页联系人把姓名解析成邮箱。 |
| `_contact_to_json()` | 函数 | 阶段 17 新增，把联系人对象转成稳定 JSON 字典。 |
| `_resolve_contact_matches()` | 函数 | 阶段 17 新增，按姓名从设置页联系人中查找候选。 |
| `_resolve_calendar_attendees()` | 函数 | 阶段 17 新增，让日程参会人复用联系人解析。 |
| `resolve_contact()` | `@tool` | 阶段 17 新增，供 agent 显式查询设置页联系人。 |

### `backend/app/services/calendar.py`

阶段 16 调整：

- `CalendarWriteClient` 增加 `delete_event()` 协议方法。
- 新增 `commit_delete_calendar_event_for_authorized_proposal()`。
- 新增 `_execute_calendar_delete()`，记录删除类 `action_events` 并保持幂等。

### `backend/app/services/workflow.py`

阶段 16 调整：

- `PROPOSAL_READY_ACTIONS` 增加 `delete_calendar_event`。
- `execute_authorized_proposal()` 增加删除日程分发。

### `backend/app/schemas/calendar.py`

阶段 16 调整：

- `CalendarEventPayload` 增加 `external_event_id` 和 `calendar_action`，用于表达“删除哪个外部日程”。

### `backend/app/schemas/workflow.py`

阶段 16 调整：

- `ActionType` 增加 `delete_calendar_event`。

### `frontend/src/components/settings/SignatureManager.vue`

阶段 16 调整：

- 署名输入从多行 textarea 改为单行 input。
- 仍然保存为唯一默认署名。

### `frontend/src/api/workflow.ts`

阶段 16 调整：

- 前端 Workflow 类型允许 `delete_calendar_event`。

### `backend/app/config/prompts/system_prompt.md`

阶段 16 调整：

- 明确联系人存在时工具参数应填写邮箱。
- 明确删除日程应先创建删除草稿，再等用户确认删除。

## 阶段 15 改动文件

### `backend/app/graph/nodes.py`

阶段 15 调整：

- 在 `agent_node()` 调用 LLM 前增加确定性确认分支。
- 用户确认发送邮件时，直接调用 `send_email_draft`。
- 用户确认创建日程时，直接调用 `execute_calendar_event_draft`。
- 只有工具真实成功时才生成成功回复；工具失败时返回失败原因。

新增关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `_has_negative_intent()` | 函数 | 识别“不要、先不、取消”等否定词，避免误执行。 |
| `_is_email_send_confirmation()` | 函数 | 判断用户是否在确认发送当前邮件草稿。 |
| `_is_calendar_create_confirmation()` | 函数 | 判断用户是否在确认创建当前日程草稿。 |
| `_wants_conflict_override()` | 函数 | 判断用户是否明确要求忽略冲突仍然创建。 |
| `_format_addresses()` | 函数 | 把工具返回的邮箱列表格式化成回复文本。 |
| `_deterministic_tool_reply()` | 函数 | 把确认执行工具的 JSON 结果转换成自然语言回复。 |
| `_try_deterministic_confirmation()` | 函数 | 在 LLM 前拦截高风险确认操作并调用真实工具。 |

### `frontend/src/components/calendar/EventList.vue`

阶段 15 调整：

- 列表视图挂载后，如果 Google 已连接，会自动调用 `handleLoad()`。
- `calendarId` 或 Google 连接状态变化时会重新读取事件。

### `backend/tests/test_agent_tools.py`

阶段 15 新增回归测试：

| 名称 | 类型 | 作用 |
|---|---|---|
| `test_calendar_confirmation_executes_tool_before_llm()` | 测试函数 | 确认创建日程时必须先执行工具，且不调用 LLM 编造成功话术。 |

## 阶段 14 改动文件

### `backend/app/graph/nodes.py`

阶段 14 调整：

- `agent_node()` 仍负责多轮 LLM -> tool -> observe -> final 循环。
- 工具结果只作为模型观察输入和日志依据，不再转换成聊天卡片。
- assistant 历史消息只恢复文本内容，不再把旧 `artifacts` 回填给模型。
- 返回给 API 的 `artifacts` 固定为空列表，避免前端重复展示邮件/日程草稿。

关键函数变化：

| 名称 | 类型 | 作用 |
|---|---|---|
| `agent_node()` | LangGraph 节点 | 执行工具调用并生成自然语言最终回复；阶段 14 起不再附加聊天卡片。 |
| `_tool_result_message()` | 函数 | 把工具 JSON 压缩成模型可读观察文本。 |
| `_fallback_tool_summary()` | 函数 | 当模型没有产出自然语言回复时，用工具 message 生成保底回复。 |

### `backend/app/api/assistant_graph.py`

阶段 14 调整：

- `_turn_response()` 保留 `artifacts` 字段用于 API 兼容，但固定返回 `[]`。
- 聊天页需要展示的邮件内容、日程内容和执行结果，全部由 `response` 文本承载。

### `backend/app/services/settings.py`

阶段 14 调整署名逻辑：

| 名称 | 类型 | 作用 |
|---|---|---|
| `create_signature()` | 异步函数 | 保存单一署名；创建前删除当前用户旧署名，并把新署名设为默认。 |
| `update_signature()` | 异步函数 | 更新单一署名；更新后删除当前用户其它历史署名，并同步默认署名引用。 |

### `backend/app/config/prompts/system_prompt.md`

阶段 14 新增联系人规则：

- 用户提到姓名时，agent 优先查看 `available_contacts`，不确定时调用 `resolve_contact`。
- 唯一匹配联系人时直接使用邮箱，不再追问。
- 设置页无匹配时可以继续查邮件/历史线索；仍无结果或多匹配时才追问用户。

### `frontend/src/components/chat/ChatView.vue`

阶段 14 调整：

- 删除消息下方 artifacts 合并和附加逻辑。
- 恢复聊天历史时只恢复 `role` 和 `content`。
- 发送消息后只展示 `result.response`，不再读取 `result.artifacts`。

关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `addMessage()` | 函数 | 只追加文本消息，不再接收 artifacts。 |
| `handleSend()` | 异步函数 | 发送 SSE 聊天请求，并只用 assistant 文本更新 UI。 |
| `restoreChat()` | 异步函数 | 从 checkpoint 恢复文本聊天历史。 |

### `frontend/src/components/chat/ChatMessage.vue`

阶段 14 调整：

- 移除 `DraftCard` 引用。
- 移除 `artifacts` prop 和删除卡片事件。
- 组件只负责渲染 Markdown 文本气泡。

### `frontend/src/components/chat/DraftCard.vue`

阶段 14 删除：

- 聊天页不再使用邮件/日程卡片。
- 邮件和日程内容应由 assistant 回复文本直接展示。

### `frontend/src/api/settings.ts`

阶段 14 调整：

| 名称 | 类型 | 作用 |
|---|---|---|
| `SignatureCreateForm` | 接口 | 兼容单署名创建；`label` 和 `is_default` 对前端调用可选。 |
| `SignatureUpdateForm` | 接口 | 更新单一署名的请求结构。 |
| `updateSignature()` | 异步函数 | 调用 `PUT /api/settings/signatures/{signature_id}` 保存当前署名。 |

### `frontend/src/components/settings/SignatureManager.vue`

阶段 14 重写：

- 设置页只显示一个署名输入框。
- 不再展示多署名列表、标签字段和默认开关。
- 保存时优先更新当前默认署名；没有署名时创建一条默认署名。

关键变量和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `content` | `ref` | 当前署名文本。 |
| `currentSignature` | `computed` | 从共享状态中选出默认署名或第一条历史署名。 |
| `refreshSignatures()` | 异步函数 | 重新读取署名并写回共享状态。 |
| `handleSave()` | 异步函数 | 创建或更新单一默认署名。 |

## 阶段 13 改动文件

### `backend/app/services/draft_context.py`

作用：

- 提供 active draft 的确定性查询和更新服务。
- 只读写 SQLite 的 Work Item / Artifact，不调用 Gmail 或 Google Calendar。
- 让聊天 agent 在多轮补充信息时能更新原草稿，而不是重复创建新草稿。

关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `load_active_artifact()` | 异步函数 | 按 `thread_id + user_id + artifact_type` 读取最近一个打开中的草稿。 |
| `load_artifact_for_update()` | 异步函数 | 按 artifact id 读取当前用户可修改的草稿。 |
| `update_artifact_content()` | 异步函数 | 更新 Artifact 内容、递增 version，并同步 Work Item 摘要和成熟度。 |
| `close_work_item()` | 异步函数 | 外部执行成功后关闭 Work Item，例如 `sent` 或 `created`。 |
| `_row_to_artifact()` | 函数 | 把数据库行转换成普通字典，方便 prompt 和工具使用。 |

### `backend/app/services/settings.py`

阶段 13 新增联系人管理：

| 名称 | 类型 | 作用 |
|---|---|---|
| `list_contacts()` | 异步函数 | 读取当前用户联系人列表。 |
| `create_contact()` | 异步函数 | 创建联系人，写入 `contacts` 表。 |
| `update_contact()` | 异步函数 | 修改联系人姓名或邮箱。 |
| `delete_contact()` | 异步函数 | 删除联系人。 |
| `_get_contact()` | 异步函数 | 读取单个联系人，不存在时返回 404。 |
| `_validate_contact_email()` | 函数 | 校验联系人邮箱格式。 |

### `backend/app/api/settings.py`

阶段 13 新增联系人路由：

| 路由 | 函数 | 作用 |
|---|---|---|
| `GET /api/settings/contacts` | `read_contacts()` | 列出联系人。 |
| `POST /api/settings/contacts` | `add_contact()` | 创建联系人。 |
| `PUT /api/settings/contacts/{contact_id}` | `edit_contact()` | 更新联系人。 |
| `DELETE /api/settings/contacts/{contact_id}` | `remove_contact()` | 删除联系人。 |

### `frontend/src/components/settings/ContactManager.vue`

作用：

- 设置页联系人管理组件。
- 支持创建、编辑和删除联系人。
- 联系人包含姓名和邮箱两个核心字段。

关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `startEdit()` | 函数 | 把联系人填入表单进入编辑状态。 |
| `resetForm()` | 函数 | 清空表单并退出编辑状态。 |
| `reloadContacts()` | 异步函数 | 重新读取联系人列表并更新共享状态。 |
| `handleSubmit()` | 异步函数 | 根据当前状态创建或更新联系人。 |
| `handleDelete()` | 异步函数 | 删除联系人并刷新列表。 |

### `frontend/src/components/chat/DraftCard.vue`（阶段 14 已删除）

阶段 13 曾新增：

- 根据 `missing_fields` 显示缺失字段，而不是误导用户直接确认。
- 根据 `status` 显示已发送或已创建。
- 根据 `conflict_summary` 显示日程冲突提示。
- 只有字段完整且无阻塞冲突时，才提示“确认发送”或“创建日程”。

阶段 14 删除原因：

- 聊天页只保留 assistant 文本回复。
- 邮件和日程内容直接打印在回复中，避免卡片和文本重复造成“二次创建草稿”的误解。

### `frontend/src/components/calendar/CalendarView.vue`

阶段 13 调整：

- 日程页保留浏览、刷新和事件详情。
- 移除直接创建和直接删除 UI，避免绕过 Proposal + Authorization + Execution。
- 新日程创建应通过聊天助手生成本地草稿并确认执行。

### `backend/app/api/calendar.py`

阶段 13 调整：

- `POST /api/calendar/events` 不再直接写 Google Calendar，返回 405。
- `PUT /api/calendar/events/{event_id}` 不再直接更新 Google Calendar，返回 405。
- `DELETE /api/calendar/events/{event_id}` 不再直接删除 Google Calendar，返回 405。
- 保留事件读取、Freebusy 和本地草稿准备接口。

### `backend/app/graph/tools.py`

作用：

- 定义聊天 agent 可调用的 LangChain `@tool`。
- 阶段 12 起所有工具返回统一 JSON 字符串：`ok`、`code`、`message`、`data`。
- 工具调用过程只进入后端日志，不直接展示给前端。
- `create_email_draft` 会创建可不完整的本地邮件 Artifact，并把草稿内容作为工具观察数据返回给模型。
- `update_email_draft` 会优先更新当前 active email draft，并把更新后的内容作为工具观察数据返回给模型。
- `send_email_draft` 会在用户确认后走 Proposal、Authorization 和 Execution 发送邮件。
- `create_calendar_event_draft` 只创建本地日程 Artifact，不写 Google Calendar。
- `update_calendar_event_draft` 会优先更新当前 active calendar draft，并重新计算缺失字段和冲突。
- `create_calendar_update_draft` 会为选中的已有 Google Calendar 事件创建本地更新草稿。
- `execute_calendar_event_draft` 会在用户确认后走 Proposal、Authorization 和 Execution 创建日程。
- `execute_calendar_event_update_draft` 会在用户确认后走 Proposal、Authorization 和 Execution 更新已有日程。
- `delete_calendar_event` 在聊天工具中拒绝直接删除 Google Calendar 日程。
- `remember_user_fact` 只有真实写入 SQLite 成功后才返回成功。

关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `set_tool_context()` | 函数 | 注入当前 `thread_id`、Gmail 客户端、Calendar 客户端、数据库 session 和用户。 |
| `_json_result()` | 函数 | 统一编码工具 JSON 返回。 |
| `_ok()` | 函数 | 生成成功工具结果。 |
| `_fail()` | 函数 | 生成失败工具结果。 |
| `_email_addresses_to_json()` | 函数 | 把 Pydantic 邮箱对象转成前端可渲染字典。 |
| `_format_email_body()` | 函数 | 规整邮件正文格式，并追加默认署名。 |
| `_contact_to_json()` | 函数 | 把联系人对象转成稳定 JSON 字典。 |
| `_resolve_contact_matches()` | 函数 | 按姓名从设置页联系人中查找候选。 |
| `_resolve_calendar_attendees()` | 函数 | 把日程参会人文本解析为 Calendar 参会人列表。 |
| `_local_email_draft_from_row()` | 函数 | 把本地邮件草稿查询结果转成稳定字典。 |
| `_format_local_email_draft_line()` | 函数 | 生成本地草稿列表的文本摘要。 |
| `_format_email_items_for_text()` | 函数 | 把邮箱列表转成适合回复的短文本。 |
| `_delete_local_work_items()` | 函数 | 删除本地 Work Item 及其关联记录，不调用 Gmail。 |
| `_calendar_card_data()` | 函数 | 构造日程草稿工具返回数据；阶段 14 起不再用于聊天卡片渲染。 |
| `create_tools()` | 函数 | 创建所有 LangChain `@tool`，包括邮件、日程、设置和记忆工具。 |
| `search_emails()` | `@tool` | 搜索 Gmail，并返回结构化邮件摘要。 |
| `read_email()` | `@tool` | 读取 Gmail 邮件详情。 |
| `create_email_draft()` | `@tool` | 创建本地邮件草稿 Artifact，并返回模型可读的草稿数据。 |
| `update_email_draft()` | `@tool` | 修改本地邮件草稿 Artifact，并返回模型可读的更新后数据。 |
| `send_email_draft()` | `@tool` | 用户确认后发送当前邮件草稿。 |
| `send_all_local_email_drafts()` | `@tool` | 用户确认后批量发送当前线程打开中的本地邮件草稿。 |
| `list_local_email_drafts()` | `@tool` | 列出打开中的本地邮件草稿。 |
| `read_local_email_draft()` | `@tool` | 读取单封本地邮件草稿详情。 |
| `delete_local_email_draft()` | `@tool` | 用户确认后删除单封本地邮件草稿。 |
| `delete_all_local_email_drafts()` | `@tool` | 用户确认后清空打开中的本地邮件草稿。 |
| `delete_email()` | `@tool` | 将 Gmail 邮件移入垃圾箱。 |
| `list_calendar_events()` | `@tool` | 读取 Calendar 事件列表。 |
| `create_calendar_event_draft()` | `@tool` | 创建本地日程草稿，并返回模型可读的日程草稿数据。 |
| `update_calendar_event_draft()` | `@tool` | 修改本地日程草稿，并返回模型可读的更新后数据。 |
| `create_calendar_update_draft()` | `@tool` | 为已有 Google Calendar 事件创建本地更新草稿。 |
| `execute_calendar_event_draft()` | `@tool` | 用户确认后创建 Google Calendar 日程。 |
| `execute_calendar_event_update_draft()` | `@tool` | 用户确认后更新已有 Google Calendar 日程。 |
| `delete_calendar_event()` | `@tool` | 拒绝聊天路径直接删除日程。 |
| `execute_calendar_event_delete_draft()` | `@tool` | 用户确认后删除已有 Google Calendar 日程。 |
| `resolve_contact()` | `@tool` | 查询设置页联系人，唯一匹配时返回邮箱，歧义或缺失时返回结构化原因。 |
| `get_user_signatures()` | `@tool` | 读取用户署名列表。 |
| `get_user_profile()` | `@tool` | 读取用户设置。 |
| `remember_user_fact()` | `@tool` | 写入长期记忆。 |
| `recall_memories()` | `@tool` | 召回长期记忆。 |

### `backend/app/graph/nodes.py`

作用：

- 阶段 12 起 `agent_node` 是聊天主流程核心。
- 支持多轮 `LLM -> tool -> observe -> final`。
- 兼容 DeepSeek DSML 文本工具调用，避免内部工具协议泄漏给用户。
- 阶段 13 起系统 prompt 会包含联系人、默认设置、active email draft 和 active calendar draft。
- 阶段 13 起系统 prompt 会包含前端显式选中的 selected context refs，例如选中的 Calendar 事件。
- 阶段 14 起工具 JSON 只作为模型观察输入，不再提取聊天卡片。
- 阶段 14 起历史 assistant 消息只恢复文本，不再恢复 artifacts。

关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `_parse_dsml_tool_calls()` | 函数 | 把 DeepSeek DSML 文本工具调用解析成标准工具调用结构。 |
| `_contains_tool_protocol()` | 函数 | 判断最终回复是否仍包含工具协议。 |
| `_load_tool_json()` | 函数 | 解析工具统一 JSON 返回。 |
| `_tool_result_message()` | 函数 | 把工具 JSON 压缩成模型可读观察文本。 |
| `_fallback_tool_summary()` | 函数 | 模型仍返回工具协议时，用工具结果生成保底自然语言回复。 |
| `_compact_active_artifact()` | 函数 | 压缩 active draft，避免长正文反复进入 prompt。 |
| `load_context()` | LangGraph 节点 | 组装系统 prompt 所需的当前日期、记忆、联系人、设置和 active draft。 |
| `agent_node()` | LangGraph 节点 | 执行多轮工具调用、日志记录和最终回复生成。 |

### `backend/app/api/assistant_graph.py`

作用：

- 提供 `/api/assistant/turn` 和 `/api/assistant/turn/stream`。
- 阶段 14 起 `_turn_response()` 固定返回空 `artifacts`，聊天页只使用 `response` 文本。
- 阶段 13 起 `_prepare_turn_context()` 会读取联系人、默认设置、默认署名和当前 active draft。

关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `_turn_response()` | 函数 | 把 LangGraph state 转换成前端响应；`artifacts` 为兼容字段，固定为空。 |
| `_prepare_turn_context()` | 异步函数 | 每轮聊天前读取长期记忆、联系人、签名、用户设置、active draft 和 Google 客户端。 |

### `backend/app/graph/runner.py`

作用：

- 运行带 SQLite checkpoint 的 LangGraph 主图。
- 阶段 12 起会把当前 `thread_id` 传入工具上下文，让聊天中创建的本地邮件草稿归属当前线程。
- 阶段 13 起会把 `user_profile`、`active_email_draft` 和 `active_calendar_draft` 注入 LangGraph state。

关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `run_assistant_turn()` | 函数 | 注入工具上下文并执行一轮 agent 图。 |

### `backend/app/graph/builder.py`

作用：

- 编译主图和导出 Mermaid。
- 阶段 12 起 Mail/Calendar 子图 Mermaid 使用真实子图导出，而不是手写占位文本。

关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `export_mail_subgraph_mermaid()` | 函数 | 导出真实 Mail Subgraph Mermaid。 |
| `export_calendar_subgraph_mermaid()` | 函数 | 导出真实 Calendar Subgraph Mermaid。 |

### `frontend/src/components/chat/ChatMessage.vue`

作用：

- 渲染单条聊天消息。
- 阶段 14 起只渲染文本气泡，不再渲染邮件/日程卡片。

关键逻辑：

| 名称 | 类型 | 作用 |
|---|---|---|
| `renderMarkdown()` | 函数 | 对 assistant 文本进行基础 Markdown 渲染。 |
| `renderedContent` | `computed` | 根据角色生成安全转义后的 HTML。 |

### `frontend/src/components/chat/ChatView.vue`

作用：

- 管理聊天消息列表、会话切换和 SSE 发送。
- 阶段 14 起聊天消息只保存文本，不再保存或展示 artifacts。

关键函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `addMessage()` | 函数 | 追加用户、assistant 或系统文本消息。 |
| `handleSend()` | 异步函数 | 发送聊天请求，接收 SSE final，并只展示 assistant 文本回复。 |
| `restoreChat()` | 异步函数 | 从 checkpoint 恢复文本聊天历史。 |

## 根目录

### `.gitignore`

作用：

- 忽略 `.env`、`.venv/`、数据库、运行日志、Markdown 导出、前端依赖、构建产物和缓存。
- 保护密钥和运行时数据不被提交。

当前没有函数。

### `.env.example`

作用：

- 根目录环境变量模板。
- 推荐复制为 `.env` 后填写真实 DeepSeek、Google OAuth 和 Token 加密配置。
- 文件内只保留 `replace-me` 占位，不保存真实密钥。

当前没有函数。

### `.env`

作用：

- 本机私有配置文件。
- 保存 DeepSeek API Key、Google OAuth 配置、Token 加密 key 等敏感值。
- 已被 `.gitignore` 忽略，不会提交。

注意：

- `LLM_API_KEY` 需要填入真实 DeepSeek API Key。
- `GOOGLE_CLIENT_ID` 和 `GOOGLE_CLIENT_SECRET` 阶段 2 接入 Google OAuth 时必须填写。
- `DATABASE_URL` 和 `LANGGRAPH_DB_PATH` 默认保持注释，由后端按项目根目录自动计算，避免相对路径随启动目录变化。
- `GOOGLE_OAUTH_SCOPES` 定义 Google 授权范围，包含 `openid email profile`、Gmail 和 Calendar 权限。
- 不要把真实密钥复制到 README、开发文档或聊天记录里。

当前没有函数。

### `README.md`

作用：

- 说明如何安装依赖、运行迁移、启动后端、启动前端、运行测试。
- 记录代码注释约定：新增和修改代码必须使用中文注释和中文 docstring。

当前没有函数。

### `基于LangGraph与FastAPI的多Agent邮件与日程助理系统_开发文档.md`

作用：

- 主开发文档，记录产品范围、架构、阶段计划、API 契约、数据库设计、验收项。
- 阶段 0 和阶段 1 的完成状态已在这里勾选。

当前没有函数。

## `docs/`

### `docs/product_scope.md`

作用：

- 冻结 MVP 产品范围。
- 说明哪些能力必须做、哪些暂不做。
- 明确本地草稿、文件上传、选中上下文和 UX 原则。

当前没有函数。

### `docs/architecture_decisions.md`

作用：

- 记录 ADR-001 到 ADR-015。
- 解释为什么选择 FastAPI、LangGraph、SQLite、本地草稿、选中上下文等设计。

当前没有函数。

### `docs/safety_rules.md`

作用：

- 冻结安全规则。
- 明确哪些事情 AI 可以做，哪些绝对不能做。
- 定义确认、fingerprint、Prompt Injection、文件安全、幂等和日志规则。

当前没有函数。

### `docs/required_fields.md`

作用：

- 定义邮件、日程、文件、选中上下文的必填字段。
- 定义 `Field Evidence` 模型和来源可信等级。

当前没有函数。

### `docs/behavior_decisions.md`

作用：

- 冻结复杂边界行为。
- 覆盖日程冲突、模糊时间、邮件回复、文件解析失败、选中上下文冲突、执行恢复、OAuth、长期记忆、追问和隐私。

当前没有函数。

### `docs/acceptance_matrix.md`

作用：

- 定义阶段 0 验收、E2E 场景、单元验收、集成验收和发布门禁。
- 阶段 11 记录本地发布状态、已验证证据、真实 Google E2E 和文件上传解析的后续范围。

当前没有函数。

### `docs/release_status.md`

作用：

- 记录阶段 11 本地 MVP 发布验收结果。
- 区分已自动验证项目、需要真实 Google 账号手动联调项目、以及后续功能范围。
- 提供后端和前端启动命令摘要。

当前没有函数。

### `docs/code_guide.md`

作用：

- 当前文件。
- 按目录解释代码文件、类、函数和阶段用途。
- 后续每个阶段都要更新。

当前没有函数。

## `backend/`

### `backend/pyproject.toml`

作用：

- 定义 Python 包、依赖、开发依赖、pytest 配置和 ruff 配置。
- 后端依赖包括 FastAPI、SQLAlchemy、Alembic、LangGraph、Google API 客户端等。
- `python-multipart` 用于接收浏览器 multipart 文件上传。
- `pypdf` 用于 PDF 文本提取。

当前没有函数。

### `backend/.env.example`

作用：

- 提供后端局部调试环境变量模板。
- 阶段 11 起推荐优先使用根目录 `.env.example` 创建 `.env`，这个文件用于只调试后端目录时参考。
- 当前默认 LLM provider 是 `deepseek`，模型是 `deepseek-v4-flash`。
- Google OAuth 回调地址统一为 `http://localhost:8000/gmail/auth/callback`。
- 文件内有中文注释，说明每个环境变量何时需要填写。

当前没有函数。

### `backend/alembic.ini`

作用：

- Alembic 配置文件。
- 告诉 Alembic 迁移脚本位置、默认数据库 URL 和日志格式。

当前没有函数。

## `backend/app/`

### `backend/app/__init__.py`

作用：

- 标记 `app` 是 Python package。
- 当前只包含中文模块说明。

当前没有函数。

### `backend/app/main.py`

作用：

- FastAPI 应用入口。
- 挂载健康检查、阶段 8 Assistant Graph/SSE、Google OAuth、字段完整性校验、Gmail、Calendar、用户设置、Workflow 和 Google callback 路由。
- 创建 app 时会先配置阶段 10 日志脱敏，确保后端运行日志默认不泄露 token、完整 Prompt 或完整邮件正文。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `create_app()` | 函数 | 创建并配置 FastAPI app，设置 CORS，挂载 `/api/health`、`/api/assistant/*`、`/api/auth/google/*`、`/api/calendar/*`、`/api/completeness/*`、`/api/gmail/*`、`/api/memory/*`、`/api/settings/*`、`/api/work-items/*`、`/api/proposals/*` 和 `/gmail/auth/callback`。测试也通过它创建干净 app。 |
| `app` | 模块对象 | Uvicorn 启动 `app.main:app` 时使用的全局 FastAPI 实例。 |

## `backend/app/api/`

### `backend/app/api/__init__.py`

作用：

- 标记 API 路由目录。
- 当前只包含中文模块说明。

当前没有函数。

### `backend/app/api/health.py`

作用：

- 提供阶段 1 健康检查接口。
- 该接口不只是返回内存里的 `ok`，还会执行一次 SQLite 查询，验证数据库路径和连接都可用。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `router` | `APIRouter` | 健康检查路由容器，在 `main.py` 中挂载到 `/api`。 |
| `health_check()` | 异步函数 | 处理 `GET /api/health`，执行 `SELECT 1`，返回 `HealthResponse`。 |

### `backend/app/api/memory.py`

作用：

- 提供阶段 9 短期记忆、长期记忆候选、联系人备注召回和 Markdown 导出接口。
- 所有接口要求已连接 Google 账号，因为记忆、偏好和导出都归属于当前用户。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `router` | `APIRouter` | `/api/memory/*` 路由容器。 |
| `read_short_term_memory()` | 异步函数 | 处理 `GET /api/memory/threads/{thread_id}/short-term`，返回短期记忆聚合。 |
| `add_memory_candidate()` | 异步函数 | 处理 `POST /api/memory/candidates`，在明确长期意图时创建记忆候选。 |
| `read_contact_notes()` | 异步函数 | 处理 `GET /api/memory/contacts/{contact_email}/notes`，按需召回联系人备注。 |
| `export_markdown()` | 异步函数 | 处理 `POST /api/memory/exports/markdown`，导出偏好、署名、联系人和审计 Markdown。 |

### `backend/app/api/assistant_graph.py`

作用：

- 提供阶段 8 LangGraph 主图、SSE 聊天流和子图的调试/验收接口。
- 运行主图和聊天流时不要求 Google OAuth，因为当前阶段不会直接执行外部写操作。
- 导出 Mermaid 方便确认图结构，也给后续调试 UI 或文档使用。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `router` | `APIRouter` | `/api/assistant/*` 路由容器。 |
| `run_turn()` | 异步函数 | 处理 `POST /api/assistant/turn`，运行一轮主图并返回任务、批次和轨迹。 |
| `stream_turn()` | 异步函数 | 处理 `POST /api/assistant/turn/stream`，以 SSE 形式推送进度和最终回复。 |
| `read_thread_state()` | 异步函数 | 处理 `GET /api/assistant/threads/{thread_id}/state`，读取 checkpoint 状态。 |
| `read_assistant_mermaid()` | 异步函数 | 处理 `GET /api/assistant/graph/mermaid`，导出主图 Mermaid。 |
| `read_subgraph_mermaid()` | 异步函数 | 处理 `GET /api/assistant/subgraphs/{subgraph}/mermaid`，导出 Mail 或 Calendar 子图 Mermaid。 |
| `run_subgraph()` | 异步函数 | 处理 `POST /api/assistant/subgraphs/run`，单独运行 Mail 或 Calendar Subgraph。 |
| `_turn_response_from_state()` | 函数 | 把主图状态转换成 API 响应结构。 |
| `_progress_steps()` | 函数 | 返回聊天流的确定性进度步骤。 |
| `_format_sse()` | 函数 | 把 `AssistantStreamEvent` 格式化为 SSE 文本。 |

### `backend/app/api/auth.py`

作用：

- 提供 Google OAuth 前后端接口。
- 前端只调用这些接口，不接触 `GOOGLE_CLIENT_SECRET`。
- Google callback 使用根路径 `/gmail/auth/callback`，和 Google Cloud Console 配置保持一致。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `router` | `APIRouter` | `/api/auth/google/*` 路由容器。 |
| `start_google_login()` | 异步函数 | 创建 OAuth state cookie，生成 Google 授权 URL，并重定向浏览器。 |
| `get_google_status()` | 异步函数 | 返回前端连接状态，包括是否已连接、是否需要重新连接、当前邮箱和 scope。 |
| `disconnect_google()` | 异步函数 | 删除本地保存的 Google OAuth token。 |
| `callback_router` | `APIRouter` | 根路径 callback 路由容器。 |
| `handle_google_callback()` | 异步函数 | 校验 OAuth state，用 code 换 token，读取 Google 用户信息，加密保存 token，再跳回前端。 |

### `backend/app/api/settings.py`

作用：

- 提供用户设置和署名 API。
- 这些设置是后续字段完整性校验的确定性事实来源。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `router` | `APIRouter` | `/api/settings/*` 路由容器。 |
| `read_profile()` | 异步函数 | 读取当前已连接 Google 用户的设置。 |
| `write_profile()` | 异步函数 | 更新时区、默认日历、默认发件账号、会议时长等设置。 |
| `read_signatures()` | 异步函数 | 列出当前用户的邮件署名。 |
| `add_signature()` | 异步函数 | 创建邮件署名。 |
| `edit_signature()` | 异步函数 | 更新邮件署名。 |
| `remove_signature()` | 异步函数 | 删除邮件署名。 |

### `backend/app/api/completeness.py`

作用：

- 提供字段完整性校验和 Field Evidence 读写接口。
- 该接口只判断草稿是否具备进入 Proposal 的字段条件，不执行 Gmail 或 Calendar 外部写操作。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `router` | `APIRouter` | `/api/completeness/*` 和 `/api/artifacts/*/field-evidence` 路由容器。 |
| `validate_draft()` | 异步函数 | 处理 `POST /api/completeness/validate`，按草稿类型返回完整性结果。 |
| `read_artifact_field_evidence()` | 异步函数 | 查询某个 Artifact 的字段来源列表。 |
| `write_artifact_field_evidence()` | 异步函数 | 记录用户补充或系统解析得到的字段来源。 |

### `backend/app/api/files.py`

作用：

- 提供文件上传、解析、读取、重新解析和删除接口。
- 上传文件会保存到 `data/uploads/`，解析结果写入 `file_extractions`。
- 文件解析文本只作为不可信上下文，不能直接授权发送邮件或创建日程。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `router` | `APIRouter` | `/api/files/*` 路由容器。 |
| `upload_file()` | 异步函数 | 处理 `POST /api/files`，接收 multipart 文件并立即解析。 |
| `read_files()` | 异步函数 | 处理 `GET /api/files`，可按 `thread_id` 列出文件。 |
| `read_file()` | 异步函数 | 处理 `GET /api/files/{uploaded_file_id}`，读取文件和最近解析结果。 |
| `extract_file()` | 异步函数 | 处理 `POST /api/files/{uploaded_file_id}/extract`，重新解析文件。 |
| `remove_file()` | 异步函数 | 处理 `DELETE /api/files/{uploaded_file_id}`，软删除并移除本地原始文件。 |

### `backend/app/api/calendar.py`

作用：

- 提供 Calendar 未来事件读取、Freebusy 查询和本地日程草稿准备接口。
- 创建或更新真实 Calendar Event 不暴露为普通 API，只能由后续 Execution Service 调用。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `router` | `APIRouter` | `/api/calendar/*` 路由容器。 |
| `list_events()` | 异步函数 | 处理 `POST /api/calendar/events/list`，读取未来日程。 |
| `query_freebusy()` | 异步函数 | 处理 `POST /api/calendar/freebusy`，查询 busy slot 和冲突。 |
| `prepare_calendar_event()` | 异步函数 | 处理 `POST /api/calendar/prepare/event`，创建本地日程 Artifact。 |

### `backend/app/api/gmail.py`

作用：

- 提供 Gmail 搜索、邮件详情、线程读取和本地邮件草稿准备接口。
- 搜索和读取会调用 Gmail API；准备草稿只写本地 Artifact，不写 Gmail Draft。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `router` | `APIRouter` | `/api/gmail/*` 路由容器。 |
| `search_emails()` | 异步函数 | 处理 `POST /api/gmail/search`，搜索 Gmail 邮件。 |
| `read_email()` | 异步函数 | 处理 `GET /api/gmail/messages/{message_id}`，读取并解析单封邮件。 |
| `read_email_thread()` | 异步函数 | 处理 `GET /api/gmail/threads/{thread_id}`，读取 Gmail Thread。 |
| `prepare_new_email()` | 异步函数 | 创建新邮件本地 Artifact。 |
| `prepare_reply_email()` | 异步函数 | 创建回复邮件本地 Artifact，并保留 Gmail thread 关系。 |
| `prepare_forward_email()` | 异步函数 | 创建转发邮件本地 Artifact。 |

### `backend/app/api/workflow.py`

作用：

- 提供阶段 6 Work Item、Proposal、Authorization 和 Execution 的 HTTP 接口。
- 这些接口要求当前已经连接 Google 账号，因为 Proposal 和执行结果都归属于当前用户。
- 业务安全错误统一转换为 HTTP 409，前端可以把它展示为“需要重新确认、不能执行、候选不唯一”等用户可理解状态。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `router` | `APIRouter` | Workflow 路由容器，挂载到 `/api` 后提供 `/api/work-items/open` 和 `/api/proposals/*`。 |
| `_workflow_error()` | 函数 | 把 `WorkflowSafetyError` 转换为 HTTP 409，避免把安全规则阻断当成服务器崩溃。 |
| `read_open_work_items()` | 异步函数 | 处理 `GET /api/work-items/open`，列出当前用户打开中的 Work Item。 |
| `read_pending_proposals()` | 异步函数 | 处理 `GET /api/proposals/pending`，列出待确认或已授权未执行的 Proposal，可按动作类型筛选。 |
| `create_proposal()` | 异步函数 | 处理 `POST /api/proposals`，从本地 Artifact 创建待确认 Proposal。 |
| `resolve_confirmation()` | 异步函数 | 处理 `POST /api/proposals/resolve-confirmation`，根据用户意图筛选唯一或多个候选 Proposal。 |
| `authorize()` | 异步函数 | 处理 `POST /api/proposals/{proposal_item_id}/authorize`，写入用户确认或拒绝。 |
| `execute()` | 异步函数 | 处理 `POST /api/proposals/{proposal_item_id}/execute`，执行已授权 Proposal。 |

## `backend/app/core/`

### `backend/app/core/__init__.py`

作用：

- 标记核心基础设施目录。
- 当前只包含中文模块说明。

当前没有函数。

### `backend/app/core/config.py`

作用：

- 管理运行时配置。
- 从环境变量和 `.env` 读取配置。
- 统一把 SQLite、LangGraph checkpoint、运行日志路径解析到仓库根目录，避免不同启动目录产生多份数据库。

常量、类和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `REPO_ROOT` | 常量 | 仓库根目录。用于生成稳定的运行时路径。 |
| `DEFAULT_DATABASE_URL` | 常量 | 默认 SQLite 数据库 URL，指向 `data/runtime/app.sqlite3`。 |
| `DEFAULT_LANGGRAPH_DB_PATH` | 常量 | 默认 LangGraph checkpoint 数据库路径。 |
| `Settings` | 类 | 所有后端运行配置的集中定义，包括 APP、数据库、Google OAuth、DeepSeek LLM 配置。 |
| `Settings.runtime_dir` | 属性 | 返回 `data/runtime` 目录，用于 SQLite 和日志文件。 |
| `Settings.exports_dir` | 属性 | 返回 `data/exports` 目录，用于阶段 9 Markdown 导出文件。 |
| `Settings.uploads_dir` | 属性 | 返回 `data/uploads` 目录，用于保存上传原始文件。 |
| `get_settings()` | 函数 | 返回缓存后的 `Settings`，避免每次请求都重新解析环境变量。 |

### `backend/app/core/database.py`

作用：

- 创建 SQLAlchemy 异步 engine 和 session factory。
- 提供后续 FastAPI 路由和 service 层访问数据库的统一入口。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `get_engine()` | 函数 | 创建异步 SQLAlchemy engine，并确保 runtime 目录存在。 |
| `engine` | 模块对象 | 阶段 1 单进程 MVP 使用的全局数据库 engine。 |
| `AsyncSessionLocal` | 模块对象 | SQLAlchemy async session factory。 |
| `get_session_factory()` | 函数 | 返回 `AsyncSessionLocal`，给需要自行控制 session 生命周期的代码使用。 |
| `get_db_session()` | 异步生成器 | FastAPI 依赖，每个请求提供一个独立数据库 session。 |

### `backend/app/core/exceptions.py`

作用：

- 定义业务异常基类。
- 后续 service 层可以继承它区分用户可见业务错误和系统内部错误。

类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `MailflowError` | 异常类 | 项目业务异常基类。 |

### `backend/app/core/logging.py`

作用：

- 配置阶段 10 日志格式、脱敏过滤器、审计事件和错误追踪辅助函数。
- 日志输出前会隐藏 access token、refresh token、client secret、api key、Bearer token、完整 Prompt 和完整邮件正文。
- 审计日志只允许白名单字段，避免业务正文或密钥被误传进日志。

常量、类和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `SENSITIVE_PATTERNS` | 常量 | token、secret、Bearer 等字符串级脱敏正则集合。 |
| `SENSITIVE_TEXT_KEYS` | 常量 | 结构化日志中需要整体隐藏的字段名集合。 |
| `AUDIT_EVENT_NAMES` | 常量 | 允许写入的审计事件名称集合。 |
| `AUDIT_ALLOWED_FIELDS` | 常量 | 审计日志允许记录的字段白名单。 |
| `REDACTION` | 常量 | 脱敏占位文本。 |
| `redact_text()` | 函数 | 把字符串或结构化对象转换成脱敏后的日志文本。 |
| `_redact_structured_value()` | 函数 | 递归隐藏 dict/list 中的敏感字段。 |
| `RedactingFilter` | 类 | logging filter，在 handler 输出前统一脱敏。 |
| `RedactingFilter.filter()` | 方法 | 把 LogRecord 的最终文本替换为脱敏文本，并清空 args。 |
| `configure_logging()` | 函数 | 设置本地开发日志格式、LogRecordFactory 和 handler 脱敏过滤器。 |
| `audit_log_event()` | 函数 | 写入脱敏审计日志，只保留白名单字段。 |
| `log_error_trace()` | 函数 | 写入可追踪错误日志，只记录错误分类和安全 ID 字段。 |
| `_ensure_redacting_filter()` | 函数 | 确保 logger 或 handler 只挂一个脱敏过滤器。 |
| `_configure_log_record_factory()` | 函数 | 在 LogRecord 创建阶段脱敏，覆盖测试和动态 handler 场景。 |

### `backend/app/core/security.py`

作用：

- 放安全相关基础工具。
- 提供 OAuth Token 加密相关工具。
- 阶段 2 使用 Fernet 加密 Google access token 和 refresh token 后再写入 SQLite。

类和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `TokenEncryptionError` | 异常类 | Token 加密或解密失败时抛出，通常意味着密钥未配置或已更换。 |
| `generate_token_encryption_key()` | 函数 | 生成 Fernet key；阶段 2 用于加密 OAuth access token 和 refresh token。 |
| `get_token_cipher()` | 函数 | 根据 `.env` 中的 `TOKEN_ENCRYPTION_KEY` 创建 Fernet 加密器。 |
| `encrypt_secret()` | 函数 | 加密敏感字符串。 |
| `decrypt_secret()` | 函数 | 解密敏感字符串，失败时提示重新连接 Google。 |

## `backend/app/models/`

### `backend/app/models/__init__.py`

作用：

- 暴露 SQLAlchemy `Base`。
- 后续 ORM model 都会从这里统一导入基础类。

对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `Base` | 导出对象 | ORM model 的共同基类。 |

### `backend/app/models/base.py`

作用：

- 定义 SQLAlchemy ORM model 的共同基类。
- 阶段 1 表结构先由手写迁移创建，后续补 ORM model 时会继承它。

类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `Base` | 类 | SQLAlchemy `DeclarativeBase` 子类，供后续 ORM model 继承。 |

## `backend/app/graph/`

### `backend/app/graph/__init__.py`

作用：

- 标记 LangGraph 编排层目录。
- 说明阶段 7 主图和子图只做编排，不直接执行 Gmail / Calendar 外部写操作。

当前没有函数。

### `backend/app/graph/state.py`

作用：

- 定义主图和任务状态结构。
- 所有状态都保持可序列化，避免把数据库 session、Google token 或客户端对象写进 checkpoint。

类型和类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `TaskDomain` | Literal 类型 | 任务所属业务域：`mail`、`calendar` 或 `general`。 |
| `TaskStatus` | Literal 类型 | 任务状态：`planned`、`blocked` 或 `completed`。 |
| `AssistantTask` | TypedDict | 主图内部任务结构，包含任务 ID、业务域、依赖和状态。 |
| `AssistantState` | TypedDict | 主图 checkpoint 状态，包含用户输入、任务 DAG、子图结果、回复、轨迹、节点耗时和轮次计数。 |

### `backend/app/graph/tasks.py`

作用：

- 提供确定性的任务 DAG 编译和联系人解析。
- 区分无依赖并行任务和有依赖顺序任务。
- 同名联系人只返回歧义候选，不直接选择邮箱。

常量和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `MAIL_KEYWORDS` | 常量 | 识别邮件任务的关键词集合。 |
| `CALENDAR_KEYWORDS` | 常量 | 识别日程任务的关键词集合。 |
| `DEPENDENCY_KEYWORDS` | 常量 | 识别邮件依赖日程产物的关键词集合，例如“会议链接”。 |
| `detect_requested_domains()` | 函数 | 根据用户输入识别涉及的业务域。 |
| `extract_contact_mentions()` | 函数 | 从“给 A、B 发邮件”等表达中提取多个联系人候选名。 |
| `resolve_contact_mentions()` | 函数 | 根据联系人候选列表解析人名，发现同名联系人时返回歧义。 |
| `compile_request_tasks()` | 函数 | 把用户请求编译成任务列表。 |
| `schedule_task_batches()` | 函数 | 根据依赖关系生成可并行或顺序执行的任务批次。 |
| `_mail_depends_on_calendar()` | 函数 | 判断邮件任务是否必须等待日程任务完成。 |
| `_clean_contact_name()` | 函数 | 清理联系人候选名里的动作词残留。 |

### `backend/app/graph/subgraphs.py`

作用：

- 定义 Mail Subgraph 和 Calendar Subgraph。
- 阶段 7 子图只生成可追踪计划结果，不直接调用 Gmail 或 Google Calendar。

类和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `SubgraphState` | TypedDict | Mail / Calendar 子图共享状态。 |
| `build_mail_subgraph()` | 函数 | 编译 Mail Subgraph。 |
| `build_calendar_subgraph()` | 函数 | 编译 Calendar Subgraph。 |
| `plan_mail_task()` | 函数 | 为邮件任务生成子图结果。 |
| `plan_calendar_task()` | 函数 | 为日程任务生成子图结果。 |
| `run_mail_subgraph_once()` | 函数 | 单独运行 Mail Subgraph，供测试和调试接口使用。 |
| `run_calendar_subgraph_once()` | 函数 | 单独运行 Calendar Subgraph，供测试和调试接口使用。 |

### `backend/app/graph/routes.py`

作用：

- 集中定义主图 conditional edge 的路由判断。
- 让 builder 只负责搭图，节点路径选择逻辑放在独立文件里。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `route_after_apply_turn_actions()` | 函数 | 决定本轮是处理确认，还是编译新请求。 |
| `route_after_validate_task_plan()` | 函数 | 决定任务计划通过后继续分发，还是先追问用户。 |

### `backend/app/graph/observability.py`

作用：

- 提供阶段 10 主图节点耗时统计。
- 不改变 LangGraph 节点的业务输入输出，只在返回值中追加 `node_timings`。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `timed_node()` | 函数 | 包装单个主图节点，记录执行耗时并追加 `{node, duration_ms}`。 |
| `wrapped()` | 内部函数 | 实际被 LangGraph 调用的节点函数，先执行原节点，再合并原状态、节点结果和本次耗时；在 `load_context` 处重置上一轮耗时。 |

### `backend/app/graph/nodes.py`

作用：

- 实现阶段 7 主图节点。
- 每个节点只做本地编排或状态转换，不直接执行外部写操作。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `_trace()` | 函数 | 追加节点轨迹，方便调试和测试。 |
| `load_context()` | 函数 | 加载 checkpoint 中已有消息、选中上下文和联系人候选。 |
| `interpret_user_turn()` | 函数 | 解释用户输入，识别确认意图和联系人候选。 |
| `resolve_turn_references()` | 函数 | 解析本轮显式选中的上下文引用。 |
| `apply_turn_actions()` | 函数 | 应用不产生外部副作用的本地动作。 |
| `compile_new_requests()` | 函数 | 把自然语言请求编译成任务列表。 |
| `resolve_entities()` | 函数 | 解析联系人实体，同名联系人时设置追问。 |
| `collect_grounded_context()` | 函数 | 汇总可溯源上下文计数。 |
| `validate_task_plan()` | 函数 | 校验任务 DAG 并生成执行批次。 |
| `dispatch_read_tasks()` | 函数 | 把邮件和日程任务分发给对应子图。 |
| `run_mail_subgraph()` | 函数 | 在主图中运行 Mail Subgraph 并合并结果。 |
| `run_calendar_subgraph()` | 函数 | 在主图中运行 Calendar Subgraph 并合并结果。 |
| `collect_artifacts()` | 函数 | 收集子图产物，进入 Artifact 构建阶段。 |
| `build_or_revise_artifacts()` | 函数 | 根据任务结果构建本地 Artifact 草稿预览。 |
| `validate_artifact_completeness()` | 函数 | 标记 Artifact 审阅状态，不替代阶段 3 完整性校验。 |
| `build_proposal_group()` | 函数 | 构建聊天层 Proposal 预览和 fingerprint。 |
| `emit_chat_confirmation()` | 函数 | 生成聊天确认提示。 |
| `resolve_action_reference()` | 函数 | 解析用户确认的是哪些预览动作。 |
| `record_authorizations()` | 函数 | 记录聊天层授权预览轨迹。 |
| `validate_authorizations()` | 函数 | 校验授权预览是否完整。 |
| `execute_authorized_actions()` | 函数 | 阶段 7 执行占位，不调用外部 API。 |
| `record_action_results()` | 函数 | 记录执行占位结果。 |
| `ask_for_clarification()` | 函数 | 生成追问回复。 |
| `compose_response()` | 函数 | 合成最终回复。 |
| `save_turn_state()` | 函数 | 把本轮用户和助手消息写入 checkpoint 状态。 |
| `extract_memory_candidates()` | 函数 | 提取长期记忆候选，但不自动写入长期记忆表。 |
| `_artifact_type_for_domain()` | 函数 | 把任务域映射为 Artifact 类型。 |
| `_action_for_artifact()` | 函数 | 把 Artifact 类型映射为动作类型。 |

### `backend/app/graph/builder.py`

作用：

- 编译阶段 7 主图。
- 编译 Mail / Calendar 子图并导出 Mermaid。
- 把 conditional edge 连接到 `routes.py` 中的路由函数。
- 阶段 10 起所有主图节点都通过 `timed_node()` 注册，运行结果可观察每个节点耗时。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `build_assistant_graph()` | 函数 | 编译主图，可注入 checkpoint saver。 |
| `add_timed_node()` | 内部函数 | 在 `build_assistant_graph()` 内部注册带耗时统计的主图节点。 |
| `export_assistant_mermaid()` | 函数 | 导出主图 Mermaid 文本。 |
| `export_mail_subgraph_mermaid()` | 函数 | 导出 Mail Subgraph Mermaid 文本。 |
| `export_calendar_subgraph_mermaid()` | 函数 | 导出 Calendar Subgraph Mermaid 文本。 |

### `backend/app/graph/runner.py`

作用：

- 提供带 SQLite checkpoint 的主图运行入口。
- 使用 `settings.langgraph_db_path` 保存 LangGraph checkpoint，支持服务重启后恢复。

常量和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `DEFAULT_RECURSION_LIMIT` | 常量 | 主图默认 recursion limit。 |
| `build_thread_config()` | 函数 | 生成包含 `thread_id` 和 recursion limit 的 LangGraph 调用配置。 |
| `run_assistant_turn()` | 函数 | 运行一轮阶段 7 主图。 |
| `get_assistant_thread_state()` | 函数 | 读取某个 `thread_id` 的 checkpoint 状态。 |
| `get_persistent_assistant_graph()` | 函数 | 返回带 SQLite checkpoint 的主图单例。 |
| `clear_graph_cache_for_tests()` | 函数 | 清理图缓存，供测试切换配置时使用。 |

## `backend/app/schemas/`

### `backend/app/schemas/__init__.py`

作用：

- 标记 Pydantic schema 目录。
- 当前只包含中文模块说明。

当前没有函数。

### `backend/app/schemas/health.py`

作用：

- 定义健康检查接口响应结构。

类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `HealthResponse` | Pydantic model | `GET /api/health` 的响应结构，包含 `status` 和 `environment`。 |

### `backend/app/schemas/auth.py`

作用：

- 定义 OAuth 连接状态响应。

类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `GoogleAuthStatusResponse` | Pydantic model | 前端显示 Google 连接状态时使用。 |
| `GoogleCallbackErrorResponse` | Pydantic model | callback 失败时的结构化错误，后续如改为 JSON 响应可复用。 |

### `backend/app/schemas/settings.py`

作用：

- 定义用户设置和邮件署名 API 的请求、响应结构。

类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `WorkingHours` | Pydantic model | 工作时间或午休时间结构。 |
| `UserProfileResponse` | Pydantic model | 用户设置页完整响应。 |
| `UserProfileUpdateRequest` | Pydantic model | 更新用户确定性偏好的请求。 |
| `SignatureResponse` | Pydantic model | 邮件署名响应。 |
| `SignatureCreateRequest` | Pydantic model | 创建邮件署名请求。 |
| `SignatureUpdateRequest` | Pydantic model | 更新邮件署名请求。 |

### `backend/app/schemas/completeness.py`

作用：

- 定义 Field Evidence、完整性校验结果和开发期校验接口结构。

类型和类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `SourceType` | Literal 类型 | 字段来源类型，例如 `user_message`、`user_profile`、`llm_inference`。 |
| `ConfirmationStatus` | Literal 类型 | 字段确认状态，例如 `verified`、`missing`、`ambiguous`。 |
| `Maturity` | Literal 类型 | 完整性成熟度：`incomplete`、`reviewable`、`proposal_ready`。 |
| `FieldEvidenceInput` | Pydantic model | 关键字段来源输入结构。 |
| `FieldEvidenceRecord` | Pydantic model | 数据库中的字段来源记录。 |
| `CompletenessResult` | Pydantic model | 完整性校验结果，包含缺失、歧义、推断字段和追问。 |
| `DraftValidationRequest` | Pydantic model | `POST /api/completeness/validate` 请求结构。 |
| `FieldEvidenceUpsertRequest` | Pydantic model | 写入字段来源记录的请求结构。 |
| `FieldEvidenceListResponse` | Pydantic model | 查询字段来源列表的响应结构。 |

### `backend/app/schemas/calendar.py`

作用：

- 定义 Calendar 事件、Freebusy、忙碌时间段、本地日程草稿和 Artifact 响应结构。

类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `CalendarAttendee` | Pydantic model | 日程参会人。 |
| `CalendarEventTime` | Pydantic model | Calendar 事件开始或结束时间。 |
| `CalendarEventPayload` | Pydantic model | 本地日程 Artifact 和 Proposal payload。 |
| `CalendarEventResponse` | Pydantic model | Calendar 事件详情响应。 |
| `ListEventsRequest` | Pydantic model | 读取未来日程请求。 |
| `ListEventsResponse` | Pydantic model | 读取未来日程响应。 |
| `FreebusyRequest` | Pydantic model | Freebusy 查询请求。 |
| `BusySlot` | Pydantic model | 忙碌或冲突时间段。 |
| `FreebusyResponse` | Pydantic model | Freebusy 查询响应，包含 busy、conflicts 和 warnings。 |
| `PrepareCalendarEventRequest` | Pydantic model | 准备日程本地草稿的请求。 |
| `CalendarArtifactResponse` | Pydantic model | 本地日程 Artifact 响应。 |

### `backend/app/schemas/gmail.py`

作用：

- 定义 Gmail 搜索、邮件详情、线程详情、本地邮件草稿和 Artifact 响应结构。

类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `GmailSearchRequest` | Pydantic model | Gmail 搜索请求，包含查询语句和最大结果数。 |
| `GmailMessageSummary` | Pydantic model | Gmail 搜索结果摘要。 |
| `GmailSearchResponse` | Pydantic model | Gmail 搜索响应。 |
| `GmailParsedBody` | Pydantic model | MIME 解析后的正文，包含纯文本和可选 HTML。 |
| `GmailMessageDetail` | Pydantic model | 单封 Gmail 邮件详情。 |
| `GmailThreadDetail` | Pydantic model | Gmail Thread 详情。 |
| `EmailAddress` | Pydantic model | 结构化邮件地址。 |
| `EmailDraftPayload` | Pydantic model | 本地邮件 Artifact 的内容结构。 |
| `PrepareNewEmailRequest` | Pydantic model | 准备新邮件本地草稿的请求。 |
| `PrepareReplyEmailRequest` | Pydantic model | 准备回复邮件本地草稿的请求。 |
| `PrepareForwardEmailRequest` | Pydantic model | 准备转发邮件本地草稿的请求。 |
| `EmailArtifactResponse` | Pydantic model | 本地邮件 Artifact 响应。 |

### `backend/app/schemas/workflow.py`

作用：

- 定义阶段 6 Workflow API 的请求和响应结构。
- 统一约束可执行动作类型、用户确认决策、Proposal 展示结构和执行结果结构。

类型和类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `ActionType` | Literal 类型 | 可进入执行闭环的动作类型：`send_email`、`create_calendar_event`、`update_calendar_event`。 |
| `Decision` | Literal 类型 | 用户对 Proposal 的决策：`approved` 或 `rejected`。 |
| `WorkItemSummary` | Pydantic model | 打开中的 Work Item 摘要，用于前端恢复多个未完成事项。 |
| `ArtifactSummary` | Pydantic model | Artifact 摘要，用于 Proposal Service 读取本地草稿内容。 |
| `ProposalItemResponse` | Pydantic model | Proposal Item 响应，包含 payload、version、fingerprint、状态和过期时间。 |
| `CreateProposalRequest` | Pydantic model | 从本地 Artifact 创建 Proposal 的请求。 |
| `AuthorizeProposalRequest` | Pydantic model | 用户确认或拒绝 Proposal 的请求，必须带上 version 和 fingerprint。 |
| `ExecuteProposalRequest` | Pydantic model | 执行 Proposal 的请求，目前 `external_resource_id` 用于更新指定 Calendar Event。 |
| `ResolveConfirmationRequest` | Pydantic model | 根据动作类型筛选确认候选的请求。 |
| `ResolveConfirmationResponse` | Pydantic model | 确认目标解析结果，状态为 `none`、`unique` 或 `ambiguous`。 |
| `ExecutionResultResponse` | Pydantic model | 执行结果响应，包含幂等 key、外部资源 ID 和外部 API 返回摘要。 |

### `backend/app/schemas/assistant_graph.py`

作用：

- 定义阶段 10 主图调试、SSE 聊天和节点耗时 API 的请求/响应结构。
- 这些结构用于运行一轮主图、读取 checkpoint 状态、导出 Mermaid、单独运行子图和推送 SSE 事件。

类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `AssistantTurnRequest` | Pydantic model | 主图单轮运行请求，包含 `thread_id`、消息、用户 ID、选中上下文和联系人候选。 |
| `AssistantTurnResponse` | Pydantic model | 主图单轮运行响应，包含回复、任务、批次、轨迹、节点耗时和 Proposal 预览。 |
| `AssistantStreamEvent` | Pydantic model | SSE 事件结构，事件类型为 `progress`、`final` 或 `error`。 |
| `AssistantStateResponse` | Pydantic model | checkpoint 状态读取响应。 |
| `MermaidResponse` | Pydantic model | Mermaid 图响应。 |
| `SubgraphRunRequest` | Pydantic model | 单独运行 Mail 或 Calendar Subgraph 的请求。 |
| `SubgraphRunResponse` | Pydantic model | 单独运行子图的响应。 |

### `backend/app/schemas/memory.py`

作用：

- 定义阶段 9 记忆和 Markdown 导出 API 结构。
- 让短期记忆、长期记忆候选、联系人备注和导出结果都有稳定契约。

类：

| 名称 | 类型 | 作用 |
|---|---|---|
| `RecentMessage` | Pydantic model | 短期记忆中的最近消息。 |
| `ShortTermMemoryResponse` | Pydantic model | 短期记忆响应，包含最近消息、摘要、工作项、Proposal、任务 DAG、Artifact 摘要和执行结果。 |
| `MemoryCandidateCreateRequest` | Pydantic model | 创建长期记忆候选的请求。 |
| `MemoryRecordResponse` | Pydantic model | 长期记忆记录响应。 |
| `ContactNoteResponse` | Pydantic model | 联系人备注召回响应。 |
| `MarkdownExportRequest` | Pydantic model | Markdown 导出请求。 |
| `MarkdownExportResponse` | Pydantic model | Markdown 导出文件列表响应。 |

## `backend/app/services/`

### `backend/app/services/completeness.py`

作用：

- 负责阶段 3 字段完整性校验。
- 合并追问缺失、歧义和仅 AI 推断字段。
- 提供 Field Evidence 查询和写入能力。
- 阶段 10 起把上传文件和文件解析结果视为不可直接执行来源，必须经用户确认后才能进入 `proposal_ready`。

类、常量和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `EXECUTABLE_CONFIRMATION_STATUSES` | 常量 | 允许进入 `proposal_ready` 的确认状态集合。 |
| `NON_EXECUTABLE_SOURCE_TYPES` | 常量 | 不允许直接进入可执行 Proposal 的来源类型集合，包含 LLM 推断、系统默认、上传文件和文件解析结果。 |
| `RequiredField` | dataclass | 单个关键字段规则，包含字段路径、展示名和追问文案。 |
| `_evidence_by_field()` | 函数 | 把 evidence 列表转换成按字段索引的字典。 |
| `_has_value()` | 函数 | 判断字段值是否真正存在。 |
| `_get_nested_value()` | 函数 | 按点号路径读取嵌套字段。 |
| `_is_inferred_only()` | 函数 | 判断字段是否只能进入 reviewable。 |
| `_field_question_intro()` | 函数 | 生成合并追问开头。 |
| `_build_questions()` | 函数 | 把多个缺失或待确认字段合并成一次追问。 |
| `_validate_required_fields()` | 函数 | 通用完整性校验核心。 |
| `validate_new_email_draft()` | 函数 | 校验新邮件草稿。 |
| `validate_reply_email_draft()` | 函数 | 校验回复邮件草稿。 |
| `validate_forward_email_draft()` | 函数 | 校验转发邮件草稿。 |
| `validate_calendar_event_draft()` | 函数 | 校验日程草稿。 |
| `validate_draft_by_type()` | 函数 | 按草稿类型分发到具体校验器。 |
| `list_field_evidence()` | 异步函数 | 查询某个 Artifact 的字段来源列表。 |
| `upsert_field_evidence()` | 异步函数 | 写入用户补充或系统解析得到的字段来源。 |
| `get_field_evidence_by_id()` | 异步函数 | 按 ID 读取单条字段来源记录。 |
| `_ensure_artifact_exists()` | 异步函数 | 写入 Field Evidence 前确认 Artifact 存在。 |

### `backend/app/services/calendar.py`

作用：

- 负责 Google Calendar REST 调用、Freebusy 冲突判断、本地日程 Artifact 生成和受授权创建/更新执行。
- 创建和更新 Calendar Event 的函数只供后续 Execution Service 调用，不作为普通前端 API 暴露。

类、常量和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `CALENDAR_API_BASE_URL` | 常量 | Google Calendar REST API 基础地址。 |
| `EMAIL_PATTERN` | 常量 | MVP 级参会人邮箱格式校验正则。 |
| `CalendarApiError` | 异常类 | Calendar API 调用失败时抛出。 |
| `CalendarExecutionBlocked` | 异常类 | 缺少授权、存在冲突或字段不完整时阻止执行。 |
| `CalendarWriteClient` | Protocol | 创建或更新日程执行所需的最小客户端协议。 |
| `parse_iso_datetime()` | 函数 | 解析 ISO 时间，兼容 `Z` 结尾。 |
| `calculate_end_time()` | 函数 | 根据结束时间或持续时长得到最终结束时间。 |
| `validate_attendee_emails()` | 函数 | 校验参会人邮箱格式。 |
| `to_google_event_payload()` | 函数 | 把内部日程 payload 转成 Google Calendar 请求体。 |
| `parse_calendar_event()` | 函数 | 把 Google 原始事件转成内部响应结构。 |
| `collect_busy_slots()` | 函数 | 从 Freebusy 原始响应提取 busy slot 和 warning。 |
| `find_conflicts()` | 函数 | 判断目标时间和 busy slot 是否重叠。 |
| `CalendarClient` | 类 | Google Calendar REST 客户端。 |
| `CalendarClient.list_events()` | 异步方法 | 读取未来日程。 |
| `CalendarClient.get_event_for_update()` | 异步方法 | 更新前读取旧事件。 |
| `CalendarClient.query_freebusy()` | 异步方法 | 查询 Freebusy 并返回冲突。 |
| `CalendarClient.insert_event()` | 异步方法 | 创建 Calendar Event，只能由执行路径调用。 |
| `CalendarClient.update_event()` | 异步方法 | 更新 Calendar Event，只能由执行路径调用。 |
| `build_calendar_client_for_user()` | 异步函数 | 根据当前用户创建 CalendarClient。 |
| `_ensure_thread()` | 异步函数 | 确保本地 Thread 存在。 |
| `prepare_calendar_event_artifact()` | 异步函数 | 准备本地日程 Artifact，并先执行 Freebusy。 |
| `_create_calendar_artifact()` | 异步函数 | 创建本地日程 Work Item 和 Artifact。 |
| `_record_calendar_evidence()` | 异步函数 | 为本地日程草稿写入基础 Field Evidence。 |
| `commit_create_calendar_event_for_authorized_proposal()` | 异步函数 | 执行已授权的 `create_calendar_event` Proposal。 |
| `commit_update_calendar_event_for_authorized_proposal()` | 异步函数 | 执行已授权的 `update_calendar_event` Proposal。 |
| `_assert_freebusy_allows_execution()` | 异步函数 | 执行前二次 Freebusy 校验。 |
| `_load_authorized_calendar_proposal()` | 异步函数 | 校验 Proposal、Authorization、version 和 fingerprint。 |
| `_execute_calendar_write()` | 异步函数 | 执行 Calendar 写操作并记录 Action Event。 |
| `_load_action_event_by_idempotency()` | 异步函数 | 根据幂等 key 返回已有执行事件。 |
| `_mark_action_event_failed()` | 异步函数 | 标记 Calendar 执行失败并保留错误信息。 |

### `backend/app/services/oauth.py`

作用：

- 负责 Google OAuth 业务逻辑。
- 生成授权 URL、交换 token、读取用户信息、保存本地用户、刷新 token 和断开连接。
- 所有 token 写库前都必须加密。

类、常量和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `GOOGLE_AUTH_URL` | 常量 | Google OAuth 授权地址。 |
| `GOOGLE_TOKEN_URL` | 常量 | Google token 交换和刷新地址。 |
| `GOOGLE_USERINFO_URL` | 常量 | Google 用户信息地址。 |
| `OAuthConfigurationError` | 异常类 | OAuth 配置缺失时抛出。 |
| `OAuthProviderError` | 异常类 | Google 返回失败响应时抛出。 |
| `ConnectedUser` | dataclass | 当前本地已连接用户的最小身份信息。 |
| `now_iso()` | 函数 | 生成 UTC ISO 时间字符串。 |
| `build_google_user_id()` | 函数 | 根据 Google 邮箱生成稳定本地用户 ID。 |
| `configured_google_scopes()` | 函数 | 从配置读取 scope 列表。 |
| `ensure_oauth_configured()` | 函数 | 检查 `GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`、`GOOGLE_REDIRECT_URI` 是否已配置。 |
| `create_oauth_state()` | 函数 | 生成 OAuth state，防止 callback 被伪造。 |
| `build_authorization_url()` | 函数 | 生成 Google 授权 URL。 |
| `exchange_code_for_token()` | 异步函数 | 用 callback code 换取 token。 |
| `fetch_google_userinfo()` | 异步函数 | 用 access token 读取 Google 邮箱和展示名。 |
| `refresh_access_token()` | 异步函数 | 使用 refresh token 刷新 access token。 |
| `upsert_connected_google_user()` | 异步函数 | 写入或更新用户、默认设置和加密 token。 |
| `get_connected_google_user()` | 异步函数 | 读取当前本地已连接 Google 用户。 |
| `get_google_connection_status()` | 异步函数 | 返回连接状态，必要时尝试刷新 token。 |
| `get_valid_google_access_token()` | 异步函数 | 读取可用 access token，过期时自动刷新，失败时要求重新连接。 |
| `disconnect_google_user()` | 异步函数 | 删除本地保存的 Google token。 |

### `backend/app/services/gmail.py`

作用：

- 负责 Gmail REST 调用、MIME 解析、HTML 转文本、本地邮件 Artifact 生成和发送执行适配。
- 创建/更新/发送 Gmail Draft 的方法只供受授权保护的执行路径调用，不作为普通前端 API 暴露。

类、常量和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `GMAIL_API_BASE_URL` | 常量 | Gmail REST API 基础地址。 |
| `GmailApiError` | 异常类 | Gmail API 调用失败时抛出。 |
| `GmailExecutionBlocked` | 异常类 | 缺少授权或 Proposal 状态不允许发送时抛出。 |
| `GmailSendClient` | Protocol | 发送执行所需的最小 Gmail 客户端接口，方便测试替换。 |
| `_HtmlTextExtractor` | 类 | 使用标准库解析 HTML 邮件正文。 |
| `html_to_text()` | 函数 | 把 HTML 正文转换成纯文本。 |
| `decode_base64url()` | 函数 | 解码 Gmail MIME part body。 |
| `encode_base64url()` | 函数 | 编码 RFC 822 邮件 raw 内容。 |
| `headers_to_dict()` | 函数 | 把 Gmail header 列表转换成字典。 |
| `split_address_header()` | 函数 | 拆分邮件地址头用于展示。 |
| `extract_body_from_payload()` | 函数 | 从 Gmail MIME payload 中提取正文，优先 `text/plain`。 |
| `parse_gmail_message()` | 函数 | 把 Gmail 原始 message 转成内部详情结构。 |
| `format_email_address()` | 函数 | 把结构化邮箱转换为 RFC 822 地址。 |
| `build_rfc822_message()` | 函数 | 根据本地邮件 Artifact 构造 Gmail Draft 所需邮件内容。 |
| `GmailClient` | 类 | Gmail REST 客户端，提供搜索、读取、Draft 创建和发送方法。 |
| `GmailClient.search_messages()` | 异步方法 | 搜索 Gmail 邮件。 |
| `GmailClient.get_message()` | 异步方法 | 读取单封 Gmail 邮件详情。 |
| `GmailClient.get_thread()` | 异步方法 | 读取 Gmail Thread。 |
| `GmailClient.create_draft_for_execution()` | 异步方法 | 创建 Gmail Draft，只能由执行路径调用。 |
| `GmailClient.update_draft_for_execution()` | 异步方法 | 更新 Gmail Draft，只能由执行路径调用。 |
| `GmailClient.send_draft_for_execution()` | 异步方法 | 发送 Gmail Draft，只能由执行路径调用。 |
| `build_gmail_client_for_user()` | 异步函数 | 根据当前用户创建 GmailClient。 |
| `_json_payload()` | 函数 | 把邮件草稿 payload 序列化为稳定 JSON。 |
| `_ensure_thread()` | 异步函数 | 确保本地 Thread 存在。 |
| `_create_email_artifact()` | 异步函数 | 创建本地邮件 Work Item 和 Artifact。 |
| `_record_email_evidence()` | 异步函数 | 为本地邮件草稿写入基础 Field Evidence。 |
| `prepare_new_email_artifact()` | 异步函数 | 准备新邮件本地 Artifact。 |
| `prepare_reply_email_artifact()` | 异步函数 | 准备回复邮件本地 Artifact，并保留 Gmail thread 关系。 |
| `prepare_forward_email_artifact()` | 异步函数 | 准备转发邮件本地 Artifact。 |
| `commit_send_email_for_authorized_proposal()` | 异步函数 | 执行已授权的 `send_email` Proposal，创建 Draft、发送、记录 Action Event。 |
| `_load_authorized_send_email_proposal()` | 异步函数 | 校验 Proposal、Authorization、version 和 fingerprint。 |
| `_load_action_event_by_idempotency()` | 异步函数 | 根据幂等 key 返回已有执行事件。 |
| `_mark_action_event_failed()` | 异步函数 | 标记 Gmail 发送执行失败并保留错误信息。 |

### `backend/app/services/workflow.py`

作用：

- 负责阶段 6 的 Work Item 与 Proposal 安全闭环。
- 从本地 Artifact 创建带 version 和 fingerprint 的 Proposal。
- 解析“确认发送”这类用户意图时按动作类型筛选，避免把邮件确认误用到日程创建。
- 写入用户 Authorization，并校验旧 version 或旧 fingerprint 不能继续执行。
- 作为统一 Execution Service，把已授权 Proposal 分发给 Gmail 或 Calendar 的受保护执行函数。
- 阶段 10 起写入脱敏审计日志，用于追踪 Proposal 创建、确认、拒绝、执行开始、执行成功和执行失败。

类、常量和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `PROPOSAL_READY_ACTIONS` | 常量 | 映射动作类型和允许进入 Proposal 的 Artifact 类型，防止拿日程草稿发送邮件。 |
| `WorkflowSafetyError` | 异常类 | 工作流安全规则阻止当前操作时抛出。 |
| `stable_json_dumps()` | 函数 | 生成稳定 JSON 文本，保证 fingerprint 不受字段顺序和空格影响。 |
| `compute_payload_fingerprint()` | 函数 | 对 Proposal payload 计算 SHA-256 fingerprint。 |
| `_loads_payload()` | 函数 | 从 SQLite 文本字段恢复 JSON payload。 |
| `_proposal_from_row()` | 函数 | 把数据库行转换成 `ProposalItemResponse`。 |
| `list_open_work_items()` | 异步函数 | 列出当前用户打开中的 Work Item，支持多个未完成事项并存。 |
| `get_artifact_for_user()` | 异步函数 | 读取属于当前用户的 Artifact，并阻止跨用户访问。 |
| `create_proposal_from_artifact()` | 异步函数 | 从本地 Artifact 创建待确认 Proposal，并把同一 Work Item + action_type 的旧 Proposal 标记为 `superseded`，随后记录 `proposal.created` 审计事件。 |
| `get_proposal_item()` | 异步函数 | 读取当前用户的单个 Proposal Item。 |
| `list_pending_proposals()` | 异步函数 | 列出待确认或已授权未执行的 Proposal，可按动作类型筛选。 |
| `resolve_confirmation_candidates()` | 异步函数 | 根据动作类型解析确认候选，返回无候选、唯一候选或多个候选。 |
| `authorize_proposal()` | 异步函数 | 校验 Proposal 状态、version、fingerprint 和过期时间后写入确认或拒绝，并记录 `proposal.approved` 或 `proposal.rejected`。 |
| `execute_authorized_proposal()` | 异步函数 | 统一执行入口，按动作类型分发到 Gmail 发送或 Calendar 创建/更新，并记录执行开始、成功或失败审计事件。 |
| `_load_latest_action_event()` | 异步函数 | 读取最近 Action Event，重复执行时返回已有结果。 |

### `backend/app/services/memory.py`

作用：

- 负责阶段 9 短期记忆聚合、长期记忆候选、联系人备注召回和 Markdown 导出。
- 短期记忆只取必要摘要，不把完整长对话或完整邮件正文塞回 Prompt。
- 长期记忆只在用户明确长期意图时写入候选，临时指令不会写入。
- Markdown 导出严格从 SQLite 事实来源读取。

常量和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `RECENT_MESSAGE_LIMIT` | 常量 | 短期记忆最近消息窗口大小。 |
| `LONG_CONVERSATION_THRESHOLD` | 常量 | 触发长对话摘要的消息数量阈值。 |
| `LONG_TERM_MARKERS` | 常量 | 识别长期记忆意图的关键词集合。 |
| `TEMPORARY_MARKERS` | 常量 | 阻止写入长期记忆的临时指令关键词集合。 |
| `build_short_term_memory()` | 异步函数 | 聚合最近消息、摘要、Open Work Items、Pending Proposals、任务 DAG、Artifact 摘要和执行结果。 |
| `create_memory_candidate()` | 异步函数 | 在明确长期意图时写入 `memories` 候选记录。 |
| `should_store_long_term_memory()` | 函数 | 判断消息是否允许写入长期记忆候选。 |
| `get_memory_record()` | 异步函数 | 按 ID 读取长期记忆记录。 |
| `recall_contact_notes()` | 异步函数 | 按联系人邮箱按需召回备注。 |
| `export_markdown_bundle()` | 异步函数 | 导出偏好、署名、联系人和审计 Markdown。 |
| `_normalize_messages()` | 函数 | 把 checkpoint 消息转换成短期记忆消息。 |
| `_recent_messages()` | 函数 | 截取最近消息窗口。 |
| `_summarize_messages()` | 函数 | 为长对话生成摘要。 |
| `_summarize_artifacts()` | 函数 | 为 Artifact 生成摘要，避免注入完整正文。 |
| `_memory_key_from_message()` | 函数 | 根据用户消息生成长期记忆 key。 |
| `_memory_from_row()` | 函数 | 把数据库行转换成 `MemoryRecordResponse`。 |
| `_export_preferences()` | 异步函数 | 从 `user_settings` 导出 `preferences.md`。 |
| `_export_signatures()` | 异步函数 | 从 `signatures` 导出 `signatures.md`。 |
| `_export_contacts()` | 异步函数 | 从 `contacts` 和联系人备注导出联系人 Markdown。 |
| `_export_audit()` | 异步函数 | 从 `action_events` 导出当天审计 Markdown。 |
| `_markdown_value()` | 函数 | 把 SQLite 值转换成 Markdown 文本。 |
| `_safe_filename()` | 函数 | 为联系人 Markdown 生成安全文件名。 |

### `backend/app/services/files.py`

作用：

- 负责上传文件保存、文本提取、解析状态写库和软删除。
- 支持文本类文件、DOCX 和 PDF。
- 未连接 Google 时会创建本地文件用户，只用于文件归属；外部写操作仍要求 Google 授权。

常量和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `MAX_UPLOAD_BYTES` | 常量 | 单文件最大 20MB。 |
| `SUPPORTED_EXTENSIONS` | 常量 | 允许上传的扩展名集合。 |
| `TEXT_EXTENSIONS` | 常量 | 普通文本解析器支持的扩展名集合。 |
| `upload_and_extract_file()` | 异步函数 | 保存上传文件、写入 `uploaded_files`，并立即解析。 |
| `list_uploaded_files()` | 异步函数 | 列出当前用户或本地文件用户的上传文件。 |
| `get_uploaded_file()` | 异步函数 | 读取文件元数据和最近一次解析结果。 |
| `extract_uploaded_file()` | 异步函数 | 重新解析文件并写入 `file_extractions`。 |
| `delete_uploaded_file()` | 异步函数 | 软删除上传文件并移除本地原始文件。 |
| `_extract_text()` | 函数 | 根据扩展名分发到文本、DOCX 或 PDF 解析器。 |
| `_extract_text_file()` | 函数 | 解析普通文本文件，按多种编码尝试。 |
| `_extract_docx()` | 函数 | 使用标准库 ZIP/XML 解析 DOCX 主文档段落。 |
| `_extract_pdf()` | 函数 | 使用 `pypdf` 提取 PDF 文本。 |
| `_normalize_text()` | 函数 | 清理空白和不可见字符。 |
| `_extractor_name()` | 函数 | 记录解析器名称。 |
| `_content_type_for_extension()` | 函数 | 为扩展名生成保守 content type。 |
| `_latest_extraction()` | 异步函数 | 读取最近解析结果。 |
| `_get_or_create_file_user()` | 异步函数 | 获取 Google 用户；未连接时创建本地文件用户。 |
| `_ensure_thread()` | 异步函数 | 确保文件关联的会话存在。 |

### `backend/app/services/settings.py`

作用：

- 负责用户设置和署名的数据库读写。
- 阶段 2 按本地单用户处理，要求先连接 Google 账号。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `require_connected_user()` | 异步函数 | 确认当前已有 Google 连接，否则返回 401。 |
| `_loads_hours()` | 函数 | 从 JSON 文本恢复时间段结构。 |
| `_dumps_hours()` | 函数 | 把时间段结构序列化为 JSON 文本。 |
| `get_user_profile()` | 异步函数 | 读取用户设置。 |
| `update_user_profile()` | 异步函数 | 更新用户设置。 |
| `list_signatures()` | 异步函数 | 列出邮件署名。 |
| `create_signature()` | 异步函数 | 创建邮件署名，可设为默认。 |
| `update_signature()` | 异步函数 | 更新邮件署名，可切换默认署名。 |
| `delete_signature()` | 异步函数 | 删除邮件署名并清理默认引用。 |
| `_get_signature()` | 异步函数 | 读取单个署名，不存在时返回 404。 |
| `_clear_default_signature()` | 异步函数 | 清除当前用户所有默认署名标记。 |
| `_set_profile_default_signature()` | 异步函数 | 同步 `user_settings.default_signature_id`。 |

## `backend/alembic/`

### `backend/alembic/env.py`

作用：

- Alembic 运行入口。
- 负责让 Alembic 使用和应用运行时相同的数据库 URL。
- 由于应用使用 `sqlite+aiosqlite`，这里需要把 Alembic 同步迁移逻辑桥接到异步 engine。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `target_metadata` | 模块对象 | Alembic autogenerate 的模型元数据入口。阶段 1 还为空。 |
| `get_url()` | 函数 | 返回应用运行时使用的同一个数据库 URL。 |
| `run_migrations_offline()` | 函数 | 离线生成 SQL，不连接数据库。 |
| `do_run_migrations(connection)` | 函数 | 在 Alembic 提供的同步 connection 上执行迁移。 |
| `run_async_migrations()` | 异步函数 | 创建 async engine，并通过 `connection.run_sync` 运行迁移。 |
| `run_migrations_online()` | 函数 | 普通 `alembic upgrade head` 的入口。 |

### `backend/alembic/script.py.mako`

作用：

- Alembic 新迁移文件模板。
- 已写入中文提示，要求后续新迁移补充中文业务说明。

模板函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `upgrade()` | 迁移函数模板 | 后续新迁移的升级逻辑。 |
| `downgrade()` | 迁移函数模板 | 后续新迁移的回滚逻辑。 |

## `backend/alembic/versions/`

### `backend/alembic/versions/0001_initial_schema.py`

作用：

- 初始数据库迁移。
- 对应阶段 1 的“空库可迁移”验收。
- 提前创建阶段 0 已冻结的核心事实表。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `upgrade()` | 迁移函数 | 创建所有初始表和索引，包括 `users`、`user_settings`、`oauth_credentials`、`work_items`、`artifacts`、`proposal_items`、`uploaded_files`、`selected_context_refs` 等。 |
| `downgrade()` | 迁移函数 | 按外键依赖反向删除表和索引。 |

主要表用途：

| 表名 | 用途 |
|---|---|
| `users` | 用户基础身份。 |
| `user_settings` | 确定性用户设置，例如时区、默认日历、默认署名。 |
| `oauth_credentials` | 加密保存 Google OAuth Token。 |
| `signatures` | 用户署名。 |
| `contacts` | 联系人索引。 |
| `threads` | 聊天会话。 |
| `messages` | 对话消息时间线。 |
| `work_items` | 多轮未完成事项。 |
| `artifacts` | 本地草稿和只读结果。 |
| `field_evidence` | 关键字段来源。 |
| `proposal_groups` | 一组待确认操作。 |
| `proposal_items` | 单个可确认外部写操作。 |
| `action_authorizations` | 用户授权事实。 |
| `action_events` | 外部 API 执行与恢复记录。 |
| `uploaded_files` | 用户上传文件元数据。 |
| `file_extractions` | 文件解析结果。 |
| `selected_context_refs` | 用户显式选中的上下文。 |
| `memories` | 长期记忆候选和已激活记忆。 |

## `backend/tests/`

### `backend/tests/unit/test_health.py`

作用：

- 阶段 1 后端冒烟测试。
- 通过真实 FastAPI app factory 请求 `/api/health`，验证路由、配置和 SQLite 连接。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `test_health_check_returns_ok()` | 测试函数 | 断言 `GET /api/health` 返回 HTTP 200，并且 JSON 中 `status` 为 `ok`。 |

### `backend/tests/unit/test_assistant_graph.py`

作用：

- 覆盖阶段 7 LangGraph 主图、子图、任务 DAG、联系人追问、Mermaid 和 checkpoint 恢复。
- 覆盖阶段 8 SSE 聊天流是否推送进度和最终事件。
- 覆盖阶段 10 Mermaid API、节点耗时返回和主图可观测性。
- 不依赖真实 Google 账号，也不调用外部 Gmail / Calendar API。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `test_assistant_graph_compiles_and_exports_mermaid()` | 测试函数 | 验证主图可编译、可运行，并能导出包含关键节点的 Mermaid，同时返回节点耗时。 |
| `test_mail_and_calendar_subgraphs_run_independently()` | 测试函数 | 验证 Mail 和 Calendar 子图可单独运行。 |
| `test_multiple_people_are_parsed_from_user_turn()` | 测试函数 | 验证用户输入中的多人可被解析出来。 |
| `test_same_name_contact_requires_clarification()` | 测试函数 | 验证同名联系人会触发追问。 |
| `test_task_dag_parallel_and_sequential_batches()` | 测试函数 | 验证无依赖任务同批并行，有依赖任务顺序执行。 |
| `test_thread_id_checkpoint_recovers_after_graph_rebuild()` | 测试函数 | 验证同一 `thread_id` 在 SQLite checkpoint 中可跨图重建恢复。 |
| `test_recursion_limit_is_part_of_thread_config()` | 测试函数 | 验证主图调用配置包含默认 recursion limit。 |
| `test_cycle_in_task_dag_is_rejected()` | 测试函数 | 验证循环依赖会被拒绝，避免图无限递归。 |
| `test_assistant_turn_stream_emits_progress_and_final()` | 测试函数 | 验证 SSE 聊天流返回 progress 和 final 事件。 |
| `test_assistant_graph_mermaid_api_exports_main_and_subgraphs()` | 测试函数 | 验证主图、Mail 子图和 Calendar 子图的 Mermaid API 可导出。 |
| `test_assistant_turn_api_returns_node_timings()` | 测试函数 | 验证 `/api/assistant/turn` 返回 `node_timings`。 |

### `backend/tests/unit/test_completeness.py`

作用：

- 覆盖阶段 3 字段完整性校验的核心安全规则。
- 验证缺失字段会合并追问，AI 推断字段不会直接进入 `proposal_ready`。
- 覆盖阶段 10 文件解析 Prompt Injection 防护，上传文件内容不能伪造用户确认。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `evidence()` | 测试辅助函数 | 快速创建 `FieldEvidenceInput`，减少测试重复。 |
| `test_new_email_missing_recipient_and_signature_are_asked_together()` | 测试函数 | 缺收件人和署名时返回一次合并追问。 |
| `test_llm_inferred_subject_keeps_email_reviewable_not_proposal_ready()` | 测试函数 | 仅由 LLM 推断的主题只能进入 `reviewable`。 |
| `test_uploaded_file_evidence_cannot_bypass_user_confirmation()` | 测试函数 | 验证上传文件和文件解析字段只能进入 `reviewable`，不能直接进入 `proposal_ready`。 |
| `test_verified_new_email_can_become_proposal_ready()` | 测试函数 | 所有关键字段可信时新邮件可进入 `proposal_ready`。 |
| `test_calendar_missing_duration_timezone_and_attendees_are_asked_together()` | 测试函数 | 日程缺时长、时区和参会人邮箱时返回一次合并追问。 |

### `backend/tests/unit/test_files.py`

作用：

- 覆盖文件上传解析服务。
- 使用内存 SQLite 和临时上传目录，不依赖真实 Google 账号。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `file_session()` | pytest fixture | 创建文件测试用内存 SQLite 和隔离配置。 |
| `FILE_TEST_SCHEMA` | 常量 | 文件服务测试所需最小表结构。 |
| `test_upload_text_file_extracts_content()` | 测试函数 | 验证 Markdown/TXT 文本能保存并解析。 |
| `test_upload_docx_file_extracts_paragraphs()` | 测试函数 | 验证 DOCX 段落能解析为文本。 |
| `test_delete_uploaded_file_marks_deleted()` | 测试函数 | 验证删除接口会把文件状态标记为 `deleted`。 |
| `_minimal_docx_bytes()` | 测试辅助函数 | 构造最小 DOCX 测试文件。 |

### `backend/tests/unit/test_calendar.py`

作用：

- 覆盖阶段 5 中不依赖真实 Google 账号的 Calendar 基础能力。
- 验证结束时间计算、冲突判断、Freebusy warning、参会人邮箱校验、时区保留和事件解析。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `test_calculate_end_time_uses_duration_when_end_missing()` | 测试函数 | 缺结束时间但有持续时长时能算出结束时间。 |
| `test_calculate_end_time_blocks_missing_duration_and_end()` | 测试函数 | 缺结束时间和持续时长时阻止创建。 |
| `test_find_conflicts_detects_overlapping_busy_slots()` | 测试函数 | Freebusy busy slot 与目标时间重叠时识别冲突。 |
| `test_collect_busy_slots_reports_unreadable_calendar()` | 测试函数 | Calendar busy 信息不可读时返回 warning。 |
| `test_validate_attendee_emails_rejects_invalid_email()` | 测试函数 | 参会人邮箱格式非法时阻止。 |
| `test_to_google_event_payload_preserves_timezone_and_attendees()` | 测试函数 | Google 请求体保留时区和参会人。 |
| `test_parse_calendar_event_reads_start_end_and_attendees()` | 测试函数 | Calendar 原始事件能解析时间和参会人。 |

### `backend/tests/unit/test_gmail.py`

作用：

- 覆盖阶段 4 中不依赖真实 Google 账号的 Gmail 基础能力。
- 验证 HTML 转文本、MIME 正文优先级、header 解析和回复邮件 RFC 822 头。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `encode_body()` | 测试辅助函数 | 生成 Gmail MIME body 使用的 base64url 文本。 |
| `test_html_to_text_keeps_readable_content()` | 测试函数 | 验证 HTML 邮件正文能转成可读文本。 |
| `test_extract_body_prefers_plain_text_over_html()` | 测试函数 | 验证 MIME 解析优先使用 `text/plain`。 |
| `test_parse_gmail_message_extracts_headers_and_body()` | 测试函数 | 验证 Gmail 原始 message 能提取 subject、to 和正文。 |
| `test_build_rfc822_reply_keeps_thread_headers()` | 测试函数 | 验证回复邮件保留 `In-Reply-To` 和 `References`。 |

### `backend/tests/unit/test_workflow.py`

作用：

- 覆盖阶段 6 中不依赖真实 Google 账号的 Workflow 安全规则。
- 使用内存 SQLite 创建最小表结构，验证 Proposal fingerprint、旧 Proposal 失效、确认目标筛选、旧 fingerprint 拒绝、过期拒绝和重复确认不重复写。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `workflow_session()` | pytest fixture | 创建阶段 6 测试专用内存 SQLite 数据库和 session。 |
| `WORKFLOW_TEST_SCHEMA` | 常量 | 测试所需的最小表结构 SQL。 |
| `seed_artifact()` | 测试辅助函数 | 写入测试用 Thread、Work Item 和 Artifact。 |
| `test_stable_json_and_fingerprint_ignore_key_order()` | 测试函数 | 验证 JSON 字段顺序不影响 fingerprint。 |
| `test_create_proposal_supersedes_old_proposal()` | 测试函数 | 验证同一 Work Item 重新生成 Proposal 会让旧 Proposal 失效。 |
| `test_resolve_confirmation_filters_send_email_only()` | 测试函数 | 验证“确认发送”只匹配邮件 Proposal，不会匹配日程 Proposal。 |
| `test_authorize_rejects_stale_fingerprint()` | 测试函数 | 验证旧 fingerprint 无法授权，正确 fingerprint 才能进入 `approved`。 |
| `test_authorize_rejects_expired_proposal()` | 测试函数 | 验证过期 Proposal 必须重新生成，不能继续授权。 |
| `test_repeated_authorization_does_not_write_duplicate_rows()` | 测试函数 | 验证重复确认会被状态机拒绝，`action_authorizations` 不重复写入。 |

### `backend/tests/unit/test_logging_observability.py`

作用：

- 覆盖阶段 10 日志脱敏、审计字段白名单和运行时日志可观测性。
- 不读取 `.env`，也不使用真实 token。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `test_redact_text_masks_tokens_and_sensitive_body()` | 测试函数 | 验证结构化日志中的 token、client secret 和完整正文会被脱敏。 |
| `test_configured_logging_redacts_runtime_messages()` | 测试函数 | 验证配置后的普通 logger 输出不会包含 token 或 Bearer secret。 |
| `test_audit_log_event_keeps_only_allowlisted_fields()` | 测试函数 | 验证审计日志只保留允许字段，丢弃正文和 token。 |

### `backend/tests/unit/test_memory.py`

作用：

- 覆盖阶段 9 短期记忆、长期记忆候选、联系人备注、Markdown 导出和子图隔离。
- 使用内存 SQLite，避免依赖真实 Google 账号或真实用户数据。

函数和对象：

| 名称 | 类型 | 作用 |
|---|---|---|
| `memory_session()` | pytest fixture | 创建阶段 9 测试专用内存 SQLite 数据库。 |
| `MEMORY_TEST_SCHEMA` | 常量 | 测试所需的最小表结构 SQL。 |
| `seed_memory_user()` | 测试辅助函数 | 写入测试用户、设置、署名和联系人。 |
| `test_long_term_memory_requires_explicit_non_temporary_signal()` | 测试函数 | 验证长期记忆必须有明确长期信号，临时指令不写入。 |
| `test_create_memory_candidate_blocks_temporary_instruction()` | 测试函数 | 验证临时指令返回 `None`，明确长期偏好写入候选。 |
| `test_short_term_memory_uses_recent_window_and_summary()` | 测试函数 | 验证最近消息窗口、长对话摘要、工作项、任务 DAG 和 Artifact 摘要。 |
| `test_contact_notes_are_recalled_on_demand()` | 测试函数 | 验证联系人备注只在按邮箱请求时召回。 |
| `test_markdown_export_uses_sqlite_facts()` | 测试函数 | 验证 Markdown 导出使用 SQLite 中的偏好和署名事实。 |
| `test_mail_and_calendar_subgraphs_do_not_inject_unrelated_context()` | 测试函数 | 验证 Mail 子图不注入日程结果，Calendar 子图不注入邮件结果。 |

## `frontend/`

### `frontend/package.json`

作用：

- 前端项目配置。
- 定义 `dev`、`build`、`preview` 命令。
- 依赖 Vue 3、Vite、TypeScript、vue-tsc。

当前没有函数。

### `frontend/package-lock.json`

作用：

- npm 锁文件。
- 固定前端依赖版本，保证不同机器安装结果一致。

当前没有函数。通常不需要人工阅读。

### `frontend/index.html`

作用：

- Vite 前端 HTML 入口。
- 提供 `<div id="app"></div>` 给 Vue 挂载。

当前没有函数。

### `frontend/vite.config.ts`

作用：

- Vite 配置。
- 阶段 1 使用 `/api` 代理到 `http://127.0.0.1:8000`，让前端能请求后端健康检查。

配置项：

| 名称 | 类型 | 作用 |
|---|---|---|
| `defineConfig(...)` | 配置导出 | 配置 Vue 插件、开发服务器端口和 API 代理。 |

### `frontend/tsconfig.json`

作用：

- TypeScript 配置。
- 开启严格模式，支持 `.vue` 文件类型检查。

当前没有函数。

## `frontend/src/`

### `frontend/src/main.ts`

作用：

- Vue 应用启动入口。
- 挂载 `App.vue` 到 `#app`。

当前没有自定义函数。

### `frontend/src/App.vue`

作用：

- 阶段 9 的主界面。
- 展示 API 状态、Google 连接状态、SSE 聊天区、Gmail 工作台、Calendar 工作台、Workflow 面板、Memory 导出面板、用户设置表单和署名管理。
- 页面加载时同时调用健康检查和 Google 连接状态接口。
- 前端只跳转到后端 OAuth 入口，不保存或展示 `GOOGLE_CLIENT_SECRET`。
- Gmail 工作台支持搜索、读取邮件、读取线程、准备新邮件本地草稿和回复本地草稿。
- Calendar 工作台支持读取未来事件、查询 Freebusy、准备本地日程草稿。
- Workflow 面板支持查看打开中的 Work Item、完整邮件/日程 Proposal 卡片、生成 Proposal、确认发送匹配、确认、拒绝、修改、暂缓和执行。
- 聊天区支持恢复 LangGraph checkpoint 消息、SSE 进度、底部输入和聊天式“确认发送”。
- Memory 面板支持导出 Markdown，并在聊天后尝试创建长期记忆候选。

响应式状态和逻辑：

| 名称 | 类型 | 作用 |
|---|---|---|
| `health` | `ref` | 保存后端健康检查结果。 |
| `googleStatus` | `ref` | 保存 Google 连接状态。 |
| `profile` | `ref` | 保存用户设置响应。 |
| `signatures` | `ref` | 保存邮件署名列表。 |
| `error` | `ref` | 保存页面级错误信息。 |
| `notice` | `ref` | 保存连接成功、断开、保存成功等提示。 |
| `gmailError` | `ref` | 保存 Gmail 工作台错误信息。 |
| `isLoading` | `ref` | 标记应用初始化是否进行中。 |
| `isSavingProfile` | `ref` | 标记用户设置保存是否进行中。 |
| `isCreatingSignature` | `ref` | 标记署名创建是否进行中。 |
| `isSearchingGmail` | `ref` | 标记 Gmail 搜索是否进行中。 |
| `isReadingGmail` | `ref` | 标记 Gmail 读取是否进行中。 |
| `isPreparingDraft` | `ref` | 标记本地邮件草稿创建是否进行中。 |
| `gmailResults` | `ref` | 保存 Gmail 搜索结果。 |
| `selectedMessage` | `ref` | 保存当前读取的 Gmail 邮件详情。 |
| `selectedThread` | `ref` | 保存当前读取的 Gmail Thread。 |
| `latestEmailArtifact` | `ref` | 保存最近创建的本地邮件 Artifact。 |
| `calendarError` | `ref` | 保存 Calendar 工作台错误信息。 |
| `isLoadingCalendar` | `ref` | 标记未来日程读取是否进行中。 |
| `isQueryingFreebusy` | `ref` | 标记 Freebusy 查询是否进行中。 |
| `isPreparingCalendarDraft` | `ref` | 标记本地日程草稿创建是否进行中。 |
| `calendarEvents` | `ref` | 保存未来日程列表。 |
| `busySlots` | `ref` | 保存 Freebusy busy slot。 |
| `calendarConflicts` | `ref` | 保存目标时间冲突。 |
| `latestCalendarArtifact` | `ref` | 保存最近创建的本地日程 Artifact。 |
| `workflowError` | `ref` | 保存 Workflow 面板错误信息。 |
| `isLoadingWorkflow` | `ref` | 标记 Work Item 和 Proposal 刷新是否进行中。 |
| `isCreatingProposal` | `ref` | 标记 Proposal 创建是否进行中。 |
| `isAuthorizingProposal` | `ref` | 标记 Proposal 确认或拒绝是否进行中。 |
| `isExecutingProposal` | `ref` | 标记 Proposal 执行是否进行中。 |
| `openWorkItems` | `ref` | 保存当前打开中的 Work Item 列表。 |
| `pendingProposals` | `ref` | 保存待确认或已授权未执行的 Proposal 列表。 |
| `latestExecutionResult` | `ref` | 保存最近一次 Proposal 执行结果。 |
| `assistantThreadId` | `ref` | 保存当前浏览器使用的 LangGraph thread_id。 |
| `chatInput` | `ref` | 保存底部聊天输入框文本。 |
| `chatMessages` | `ref` | 保存当前页面展示的聊天历史。 |
| `streamEvents` | `ref` | 保存本轮 SSE 进度事件。 |
| `isStreamingChat` | `ref` | 标记聊天 SSE 是否进行中。 |
| `latestAssistantTurn` | `ref` | 保存最近一次主图响应。 |
| `isExportingMarkdown` | `ref` | 标记 Markdown 导出是否进行中。 |
| `memoryError` | `ref` | 保存记忆或 Markdown 导出错误。 |
| `latestMarkdownExport` | `ref` | 保存最近一次 Markdown 导出的文件列表。 |
| `gmailSearchForm` | `reactive` | Gmail 搜索表单状态。 |
| `newEmailForm` | `reactive` | 新邮件本地草稿表单状态。 |
| `replyEmailForm` | `reactive` | 回复邮件本地草稿表单状态。 |
| `calendarForm` | `reactive` | Calendar 工作台表单状态。 |
| `profileForm` | `reactive` | 用户设置表单状态。 |
| `signatureForm` | `reactive` | 新建署名表单状态。 |
| `googleLabel` | `computed` | 根据连接状态生成状态标签。 |
| `googleStatusClass` | `computed` | 根据连接状态生成样式 class。 |
| `defaultSenderEmail` | `computed` | 从用户设置或 Google 邮箱推导默认发件账号。 |
| `missingSettingLabels` | `computed` | 根据用户设置和署名列表生成需要补充的字段提示。 |
| `parseAddressList()` | 函数 | 把逗号分隔的用户输入转换为结构化邮箱列表。 |
| `parseCalendarAttendees()` | 函数 | 把逗号分隔的参会人邮箱转换为结构化参会人列表。 |
| `firstAddress()` | 函数 | 把单个邮件头转换为结构化邮箱列表。 |
| `emptyToNull()` | 函数 | 保存前把空字符串转成 `null`。 |
| `loadAssistantThreadId()` | 函数 | 从 localStorage 读取或创建当前浏览器的 `thread_id`。 |
| `appendChatMessage()` | 函数 | 向聊天历史追加一条用户、助手或系统消息。 |
| `restoreAssistantThread()` | 异步函数 | 从后端 checkpoint 恢复聊天消息。 |
| `applyProfileForm()` | 函数 | 把后端返回的用户设置同步到表单。 |
| `loadGoogleArea()` | 异步函数 | 加载 Google 状态、用户设置和署名。 |
| `loadWorkflowArea()` | 异步函数 | 刷新打开中的 Work Item 和待处理 Proposal。 |
| `loadInitialData()` | 异步函数 | 页面挂载后加载健康检查和 Google 区域。 |
| `handleSendChat()` | 异步函数 | 发送聊天消息，读取 SSE 进度，并追加最终助手回复。 |
| `maybeCreateMemoryCandidate()` | 异步函数 | 聊天后尝试创建长期记忆候选，失败不打断聊天。 |
| `handleChatSideEffects()` | 异步函数 | 处理聊天式“确认发送”，调用阶段 6 的确认候选和授权逻辑。 |
| `handleDisconnectGoogle()` | 异步函数 | 调用后端断开 Google 连接。 |
| `handleSaveProfile()` | 异步函数 | 保存用户设置。 |
| `handleCreateSignature()` | 异步函数 | 创建邮件署名并刷新列表。 |
| `handleSearchGmail()` | 异步函数 | 调用 Gmail 搜索接口并更新结果列表。 |
| `handleReadMessage()` | 异步函数 | 读取单封 Gmail 邮件详情。 |
| `handleReadThread()` | 异步函数 | 读取 Gmail Thread，并选中最后一封邮件。 |
| `handlePrepareNewDraft()` | 异步函数 | 根据表单创建新邮件本地 Artifact。 |
| `handlePrepareReplyDraft()` | 异步函数 | 根据选中 Gmail 邮件创建回复本地 Artifact。 |
| `handleListCalendarEvents()` | 异步函数 | 读取未来 Calendar 事件。 |
| `handleQueryFreebusy()` | 异步函数 | 查询目标时间段 Freebusy 并显示冲突。 |
| `handlePrepareCalendarDraft()` | 异步函数 | 根据表单创建本地日程 Artifact。 |
| `handleCreateEmailProposal()` | 异步函数 | 根据最近的邮件 Artifact 生成 `send_email` Proposal。 |
| `handleCreateCalendarProposal()` | 异步函数 | 根据最近的日程 Artifact 生成 `create_calendar_event` Proposal。 |
| `handleResolveSendConfirmation()` | 异步函数 | 请求后端按 `send_email` 筛选确认候选，多候选时提示需要明确目标。 |
| `handleAuthorizeProposal()` | 异步函数 | 使用 Proposal 当前 version 和 fingerprint 进行确认或拒绝。 |
| `handleExecuteProposal()` | 异步函数 | 执行已确认 Proposal，并展示执行结果。 |
| `handleReviseProposal()` | 函数 | 把旧 Proposal payload 带回邮件或日程表单，供用户修改后重新保存。 |
| `handleDeferProposal()` | 函数 | 暂缓某个 Proposal，不改变外部系统。 |
| `handleExportMarkdown()` | 异步函数 | 调用后端导出 Markdown，并展示生成文件列表。 |
| `proposalTitle()` | 函数 | 根据 Proposal payload 生成卡片标题。 |
| `stringField()` | 函数 | 从 payload 读取字符串字段。 |
| `displayField()` | 函数 | 把空值、数字、布尔值转换成适合卡片展示的文本。 |
| `formatAddressList()` | 函数 | 把结构化邮箱列表转成逗号分隔文本。 |
| `fingerprintShort()` | 函数 | 截短 Proposal fingerprint 供卡片展示。 |
| `onMounted(...)` | 生命周期逻辑 | 页面挂载后调用 `loadInitialData()`。 |

### `frontend/src/api/auth.ts`

作用：

- 前端 Google OAuth API 客户端。
- 只跳转到后端授权入口，不拼接 Google URL，不接触 Client Secret。

接口和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `GoogleAuthStatus` | TypeScript interface | 描述 Google 连接状态响应。 |
| `startGoogleLogin()` | 函数 | 跳转到 `/api/auth/google/login`。 |
| `fetchGoogleStatus()` | 异步函数 | 请求 `/api/auth/google/status`。 |
| `disconnectGoogle()` | 异步函数 | 请求 `/api/auth/google/disconnect`。 |

### `frontend/src/api/settings.ts`

作用：

- 前端用户设置和署名 API 客户端。
- 保持请求和响应类型化，避免设置页和后端契约漂移。

接口和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `WorkingHours` | TypeScript interface | 工作时间或午休时间结构。 |
| `UserProfile` | TypeScript interface | 用户设置响应。 |
| `Signature` | TypeScript interface | 邮件署名响应。 |
| `ProfileForm` | TypeScript interface | 用户设置保存请求。 |
| `SignatureCreateForm` | TypeScript interface | 创建署名请求。 |
| `fetchProfile()` | 异步函数 | 请求 `/api/settings/profile`。 |
| `saveProfile()` | 异步函数 | 保存 `/api/settings/profile`。 |
| `fetchSignatures()` | 异步函数 | 请求 `/api/settings/signatures`。 |
| `createSignature()` | 异步函数 | 创建邮件署名。 |

### `frontend/src/api/gmail.ts`

作用：

- 前端 Gmail API 客户端。
- 只调用后端 `/api/gmail/*`，不接触 Gmail access token。

接口和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `GmailSearchRequest` | TypeScript interface | Gmail 搜索请求。 |
| `GmailMessageSummary` | TypeScript interface | Gmail 搜索结果摘要。 |
| `GmailSearchResponse` | TypeScript interface | Gmail 搜索响应。 |
| `GmailParsedBody` | TypeScript interface | MIME 解析后的正文。 |
| `GmailMessageDetail` | TypeScript interface | 单封 Gmail 邮件详情。 |
| `GmailThreadDetail` | TypeScript interface | Gmail Thread 详情。 |
| `EmailAddress` | TypeScript interface | 结构化邮件地址。 |
| `PrepareNewEmailRequest` | TypeScript interface | 准备新邮件本地草稿请求。 |
| `PrepareReplyEmailRequest` | TypeScript interface | 准备回复邮件本地草稿请求。 |
| `EmailArtifactResponse` | TypeScript interface | 本地邮件 Artifact 响应。 |
| `searchGmail()` | 异步函数 | 请求 `/api/gmail/search`。 |
| `readGmailMessage()` | 异步函数 | 请求 `/api/gmail/messages/{message_id}`。 |
| `readGmailThread()` | 异步函数 | 请求 `/api/gmail/threads/{thread_id}`。 |
| `prepareNewEmailDraft()` | 异步函数 | 请求 `/api/gmail/prepare/new`。 |
| `prepareReplyEmailDraft()` | 异步函数 | 请求 `/api/gmail/prepare/reply`。 |

### `frontend/src/api/calendar.ts`

作用：

- 前端 Calendar API 客户端。
- 只调用后端 `/api/calendar/*`，不接触 Google access token。

接口和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `CalendarAttendee` | TypeScript interface | 日程参会人。 |
| `CalendarEventTime` | TypeScript interface | Calendar 事件时间。 |
| `CalendarEventResponse` | TypeScript interface | Calendar 事件详情。 |
| `ListEventsRequest` | TypeScript interface | 读取未来日程请求。 |
| `ListEventsResponse` | TypeScript interface | 读取未来日程响应。 |
| `BusySlot` | TypeScript interface | 忙碌或冲突时间段。 |
| `FreebusyRequest` | TypeScript interface | Freebusy 查询请求。 |
| `FreebusyResponse` | TypeScript interface | Freebusy 查询响应。 |
| `PrepareCalendarEventRequest` | TypeScript interface | 准备本地日程草稿请求。 |
| `CalendarArtifactResponse` | TypeScript interface | 本地日程 Artifact 响应。 |
| `listCalendarEvents()` | 异步函数 | 请求 `/api/calendar/events/list`。 |
| `queryCalendarFreebusy()` | 异步函数 | 请求 `/api/calendar/freebusy`。 |
| `prepareCalendarEventDraft()` | 异步函数 | 请求 `/api/calendar/prepare/event`。 |

### `frontend/src/api/assistant.ts`

作用：

- 前端阶段 10 主图、SSE 和节点耗时 API 客户端。
- 支持普通主图请求、SSE 聊天流、checkpoint 状态读取、Mermaid 读取和子图调试。
- 不接触 Gmail 或 Calendar token，也不会绕过 Proposal / Authorization。

接口和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `AssistantTurnRequest` | TypeScript interface | 主图单轮运行请求。 |
| `AssistantTurnResponse` | TypeScript interface | 主图单轮运行响应，包含 `node_timings` 供后续前端显示节点耗时。 |
| `AssistantStreamEvent` | TypeScript interface | SSE 事件结构，包含进度、最终结果和错误事件。 |
| `AssistantStateResponse` | TypeScript interface | checkpoint 状态读取响应。 |
| `MermaidResponse` | TypeScript interface | Mermaid 图响应。 |
| `SubgraphRunResponse` | TypeScript interface | 单独运行子图的响应。 |
| `runAssistantTurn()` | 异步函数 | 请求 `/api/assistant/turn`。 |
| `streamAssistantTurn()` | 异步函数 | 请求 `/api/assistant/turn/stream`，逐块解析 SSE 并回调进度事件。 |
| `fetchAssistantState()` | 异步函数 | 请求 `/api/assistant/threads/{thread_id}/state`。 |
| `fetchAssistantMermaid()` | 异步函数 | 请求 `/api/assistant/graph/mermaid`。 |
| `runAssistantSubgraph()` | 异步函数 | 请求 `/api/assistant/subgraphs/run`。 |
| `parseSsePart()` | 函数 | 从 SSE 文本块中解析 JSON 事件。 |

### `frontend/src/api/files.ts`

作用：

- 前端文件上传 API 客户端。
- 使用 `FormData` 上传文件，由后端解析 TXT/MD/DOCX/PDF。

接口和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `FileExtraction` | TypeScript interface | 文件解析结果结构。 |
| `UploadedFile` | TypeScript interface | 上传文件元数据和解析结果结构。 |
| `UploadedFileList` | TypeScript interface | 文件列表响应结构。 |
| `uploadChatFile()` | 异步函数 | 上传聊天附件并返回解析结果。 |
| `fetchThreadFiles()` | 异步函数 | 按 `thread_id` 读取文件列表。 |

### `frontend/src/api/memory.ts`

作用：

- 前端阶段 9 记忆和 Markdown 导出 API 客户端。
- 不在前端自行判断长期记忆是否生效，所有写入决策交给后端安全规则。

接口和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `ShortTermMemoryResponse` | TypeScript interface | 短期记忆响应结构。 |
| `MemoryRecordResponse` | TypeScript interface | 长期记忆记录响应结构。 |
| `MarkdownExportResponse` | TypeScript interface | Markdown 导出文件列表响应。 |
| `fetchShortTermMemory()` | 异步函数 | 请求 `/api/memory/threads/{thread_id}/short-term`。 |
| `createMemoryCandidate()` | 异步函数 | 请求 `/api/memory/candidates`，尝试创建长期记忆候选。 |
| `exportMarkdownBundle()` | 异步函数 | 请求 `/api/memory/exports/markdown`，导出 Markdown 文件。 |

### `frontend/src/api/workflow.ts`

作用：

- 前端 Workflow API 客户端。
- 只处理本地 Work Item、Proposal、Authorization 和 Execution 状态，不直接接触 Gmail 或 Calendar token。
- 发起确认时必须把 Proposal 当前 version 和 fingerprint 一起传给后端。

接口和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `WorkItemSummary` | TypeScript interface | 打开中的 Work Item 摘要。 |
| `ProposalItem` | TypeScript interface | Proposal 响应结构，包含 payload、version、fingerprint 和状态。 |
| `CreateProposalRequest` | TypeScript interface | 创建 Proposal 请求。 |
| `AuthorizeProposalRequest` | TypeScript interface | 确认或拒绝 Proposal 请求。 |
| `ExecutionResult` | TypeScript interface | 执行结果响应。 |
| `ResolveConfirmationResponse` | TypeScript interface | 确认目标解析响应。 |
| `fetchOpenWorkItems()` | 异步函数 | 请求 `/api/work-items/open`。 |
| `fetchPendingProposals()` | 异步函数 | 请求 `/api/proposals/pending`，可传动作类型筛选。 |
| `createProposal()` | 异步函数 | 请求 `/api/proposals`，从本地 Artifact 生成 Proposal。 |
| `resolveSendConfirmation()` | 异步函数 | 请求 `/api/proposals/resolve-confirmation`，并固定传入 `send_email`。 |
| `authorizeProposal()` | 异步函数 | 请求 `/api/proposals/{id}/authorize`，提交 version、fingerprint 和确认决策。 |
| `executeProposal()` | 异步函数 | 请求 `/api/proposals/{id}/execute`，触发后端 Execution Service。 |

### `frontend/src/api/health.ts`

作用：

- 前端健康检查 API 客户端。
- 把 `/api/health` 的响应类型化，供 `App.vue` 使用。

接口和函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `HealthResponse` | TypeScript interface | 描述后端健康检查响应字段。 |
| `fetchHealth()` | 异步函数 | 请求 `/api/health`；非 2xx 时抛出错误；成功时返回 `HealthResponse`。 |

### `frontend/src/styles.css`

作用：

- 阶段 9 页面样式。
- 定义主布局、状态标签、聊天历史、SSE 进度、Google 连接区、Gmail 工作台、Calendar 工作台、Workflow 面板、Memory 面板、完整 Proposal 卡片、设置表单和署名列表。

当前没有函数。

## 生成物和运行时目录

这些目录和文件通常不需要读，也不需要手动编辑：

| 路径 | 说明 |
|---|---|
| `.venv/` | Python 虚拟环境。 |
| `frontend/node_modules/` | 前端依赖。 |
| `frontend/dist/` | 前端构建产物。 |
| `backend/.pytest_cache/` | pytest 缓存。 |
| `backend/.ruff_cache/` | ruff 缓存。 |
| `backend/**/__pycache__/` | Python 字节码缓存。 |
| `data/runtime/app.sqlite3` | 本地 SQLite 数据库。 |
| `data/runtime/*.log` | 本地运行日志。 |
| `data/exports/` | 阶段 9 Markdown 导出目录，内容由后端从 SQLite 事实来源生成。 |

## 阶段 B+ (LLM 集成阶段，2026-06-10)

以下为 LLM 集成和差距修复阶段新增/修改的文件。

### 新增文件

#### `backend/app/services/llm_client.py`

作用：LLM 客户端，封装 DeepSeek API 调用。DeepSeek 兼容 OpenAI chat API，使用 langchain-openai 的 ChatOpenAI。提供同步（`llm_invoke`、`llm_invoke_structured`）和异步（`generate_response`、`generate_structured_output`）两套接口。同步接口用于 LangGraph 节点，异步接口用于 FastAPI 端点。

函数：

| 名称 | 类型 | 作用 |
|---|---|---|
| `get_chat_model()` | 函数 | 返回缓存的 ChatOpenAI 单例，配置从 .env 读取 |
| `load_prompt(name)` | 函数 | 从 `config/prompts/{name}.md` 加载提示词模板 |
| `build_system_prompt(context)` | 函数 | 构建完整系统提示词，注入上下文 JSON |
| `llm_invoke(messages)` | 函数 | 同步调用 LLM，返回文本。用于 LangGraph 同步节点 |
| `llm_invoke_structured(messages, schema)` | 函数 | 同步调用 LLM，返回 Pydantic 结构化输出 |
| `generate_response(system_prompt, user_message)` | 异步函数 | 异步调用 LLM 生成回复。用于 FastAPI 端点 |
| `generate_structured_output(system_prompt, user_message, schema)` | 异步函数 | 异步调用 LLM 生成结构化输出 |
| `reset_chat_model_for_tests()` | 函数 | 清理 LLM 缓存，供测试使用 |

#### `backend/app/config/prompts/system_prompt.md`

作用：Assistant 系统人设提示词。定义角色、能力边界、安全规则（不猜测邮箱/署名/时间/时区）、回复风格。`{context}` 占位符在运行时被替换为当前图状态 JSON。

#### `backend/app/config/prompts/task_compiler.md`

作用：任务编译提示词。定义 LLM 如何从用户输入判断意图（general_chat / create_task / confirm_action / revise_task）并输出结构化 Task DAG。包含明确的边界规则——不能猜测邮箱、时间、时区。

#### `backend/app/config/prompts/mail_agent.md`

作用：邮件草稿生成提示词。定义 LLM 如何生成邮件主题、正文、署名策略。强调只生成本地草稿，不发送。

#### `backend/app/config/prompts/calendar_agent.md`

作用：日程草稿生成提示词。定义 LLM 如何生成日程标题、时间、描述、参会人等字段。强调不直接创建 Google Calendar 事件。

#### `backend/app/config/prompts/compose_response.md`

作用：回复合成提示词。定义 LLM 如何根据图状态（任务、草稿、Proposal、追问）生成用户可见的自然语言回复。包含占位符 `{user_message}`、`{tasks_summary}` 等。

### 修改文件

#### `backend/app/graph/nodes.py` (LLM 接入 + 安全加固)

核心改动：
- `interpret_user_turn`：增加 LLM 意图分类（`_TurnIntent`），合并 LLM 实体提取和正则实体
- `compile_new_requests`：LLM 优先编译，关键词降级
- `collect_grounded_context`：生成选中对象的可读标签列表，供 LLM 理解操作目标
- `validate_artifact_completeness`：增加代码层安全校验——检测 LLM 是否猜测了邮箱、时间、时区
- `compose_response`：`_llm_compose_response()` LLM 生成回复 + `_fallback_response()` 降级
- `build_or_revise_artifacts`：将子图 LLM 草稿摘要包装为 Artifact

#### `backend/app/graph/routes.py` (新增 general_chat 路由)

`route_after_apply_turn_actions`：新增 `general_chat → compose_response` 直通分支，闲聊不走任务编译链。

#### `backend/app/graph/tasks.py` (LLM 任务编译)

新增：
- `_CompiledTask` / `_TaskCompilation`：LLM 结构化输出 schema
- `compile_request_tasks_with_llm()`：LLM 编译任务 DAG（主路径），降级时回退到 `compile_request_tasks()`

#### `backend/app/graph/subgraphs.py` (LLM 草稿生成)

`plan_mail_task` / `plan_calendar_task`：改为调用 LLM 生成草稿内容（通过 `_generate_draft()`），降级时返回简单摘要。子图状态新增 `user_message` 字段。

#### `backend/app/graph/builder.py` (路由表更新)

`route_after_apply_turn_actions` 条件边新增 `compose_response` 目标。

#### `backend/app/api/assistant_graph.py` (无变更，LLM 回复通过节点生成)

#### `backend/pyproject.toml` (新增依赖)

添加 `langchain-openai` 到项目依赖。

#### 前端增强

- `GmailSearch.vue`：添加快捷搜索按钮（最近一周/未读/收件箱），邮件列表卡片
- `EventList.vue`：按日期分组、今天/本周筛选
- `ProfileSettings.vue`：Google 连接后自动填充发件账号

## 后续阶段维护规则

每个阶段完成后，必须更新本文档：

- 新增文件：补上文件职责。
- 新增函数或类：补上名称、类型、作用。
- 修改核心行为：更新对应文件说明。
- 删除文件：从本文档移除。
- 引入生成物：标明是否需要人工阅读。
