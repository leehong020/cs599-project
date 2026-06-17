# 架构决策

## ADR-001：使用 FastAPI + LangGraph + LangChain + Vue 3

状态：accepted

决策：MVP 使用 FastAPI 提供后端 API，使用 LangGraph 编排多步骤助理流程，使用 LangChain 集成模型与工具，使用 Vue 3 构建聊天界面。

原因：这套技术栈足够轻量，适合本地开发，同时支持图式恢复、类型化 API 契约和响应式前端体验。

影响：

- 助理行为通过图节点和服务层策略表达。
- FastAPI 负责认证、持久化、文件上传和执行边界。
- Vue 负责选中上下文、卡片和用户可见的聊天体验。

## ADR-002：聊天式确认不依赖 LangGraph interrupt

状态：accepted

决策：MVP 的确认机制使用普通聊天轮次，不依赖 `interrupt()`。

流程：

```text
展示 Proposal
→ 本轮图结束
→ 用户在下一条聊天消息或按钮中确认
→ 图重新开始
→ 加载 open work items 和 pending proposals
→ 解析目标
→ 校验授权
→ 执行
```

原因：这种方式更符合聊天体验，也能在页面刷新或服务重启后继续工作。

## ADR-003：支持多个 Open Work Item

状态：accepted

决策：同一个 Thread 中可以同时存在多个打开的 `Work Item`。

原因：用户会自然地暂停一封邮件、创建一个会议，再回到原邮件继续修改。

影响：所有确认、修改、取消动作都必须先解析目标 `Work Item` 或 `Proposal Item`，然后才能执行。

## ADR-004：所有关键字段必须有 Provenance

状态：accepted

决策：关键字段必须保存 `Field Evidence`，包括 source type、source reference、confidence、confirmation status 和 timestamp。

原因：助理不能伪造收件人、署名、时区、会议时间或参会人邮箱。

## ADR-005：字段不完整不得进入可执行 Proposal

状态：accepted

决策：`Work Item` 可以在缺字段时进入 reviewable 状态供用户查看，但必须等必填字段完整且有依据后，才能成为 `proposal_ready`。

原因：可见草稿可以帮助用户协作，但可执行动作必须经过更严格校验。

## ADR-006：外部写操作使用 Proposal + Authorization

状态：accepted

决策：每一个外部写操作都必须表示为 `Proposal Item`，并在用户授权后，才允许 `Execution Service` 调用 Google API。

外部写操作包括：

```text
send_email
create_calendar_event
update_calendar_event
create_gmail_draft
update_gmail_draft
```

MVP 中，`create_gmail_draft` 和 `update_gmail_draft` 只是 `send_email` 被批准后的内部执行步骤。

## ADR-007：草稿变化会让旧授权失效

状态：accepted

决策：任何有意义的 `Artifact` payload 变化都会递增 version、重新计算 fingerprint，并把旧 `Proposal Item` 标记为 `superseded`。

原因：用户确认只适用于当时展示的精确内容。

## ADR-008：SQLite 是事实来源

状态：accepted

决策：SQLite 保存 users、settings、threads、messages、work items、artifacts、field evidence、proposals、authorizations、action events、file metadata、file extractions、selected context refs 和 memories。

原因：MVP 需要可靠的本地持久化，但暂不引入 PostgreSQL 或 Redis。

## ADR-009：Markdown 是可读层，不是事实来源

状态：accepted

决策：Markdown 可以保存 Prompt、安全策略、模板、架构说明和可读导出。Markdown 不得保存密钥、授权事实、fingerprint、执行状态、checkpoint 或上传文件原文。

## ADR-010：MVP 不使用 Redis

状态：accepted

决策：只有在需要多实例 SSE 广播、分布式锁、缓存或后台队列时，才引入 Redis。

## ADR-011：草稿生成只写本地

状态：accepted

决策：生成或修改邮件/日程草稿只写本地 `Artifact`，不写 Gmail Draft 或 Calendar Event。

原因：写 Gmail Draft 仍然是外部副作用，必须要求用户确认。

补充：聊天 agent 中的 `create_calendar_event_draft` 和 `update_calendar_event_draft`
也必须遵守该规则。真实 Calendar 创建只能由 `execute_calendar_event_draft`
在用户确认后通过 Proposal + Authorization + Execution Service 完成。

## ADR-011A：多轮修改使用 active draft

状态：accepted

决策：每轮聊天必须把当前会话打开中的 `email_draft` 和 `calendar_event_draft`
作为 active draft 注入 agent 上下文。用户补充或修改字段时，默认更新 active
draft；只有用户明确要求“新建另一封邮件/另一个日程”时才创建新的 Work Item。

原因：自然对话中用户经常分多轮补齐收件人、署名、地点、参会人或时间。
如果没有 active draft，模型会重复创建草稿，导致确认对象不稳定。

## ADR-012：用户设置使用确定性数据表

状态：accepted

决策：时区、默认日历、默认署名、发件账号、会议时长、工作时间、午休时间等稳定偏好保存在 `user_settings`。

原因：这些字段会被完整性校验依赖，不能只依赖模糊的长期记忆。

补充：邮件生成必须优先读取默认署名；日程生成必须优先读取默认日历、
默认时区和默认会议时长。缺失时才追问用户。

## ADR-012A：联系人是收件人与参会人的共同事实来源

状态：accepted

决策：设置页维护的 `contacts` 同时用于邮件收件人和日程参会人解析。
唯一匹配可以自动使用邮箱；没有匹配或同名多人时必须追问。

原因：邮箱地址不能由模型猜测。联系人显式管理能把自然语言里的姓名
转换为确定性邮箱，同时保留同名消歧空间。

## ADR-013：上传文件是用户显式上下文

状态：accepted

决策：MVP 支持用户显式上传 PDF、DOCX、TXT 和 Markdown，不扫描整个邮箱或所有附件。

原因：显式上传能让用户保持控制，也能限制隐私、成本和实现复杂度。

## ADR-014：选中上下文是一等输入

状态：accepted

决策：前端选中的邮件、日程、文件、文件片段、草稿和 proposal 卡片，会作为 `selected_context_refs` 随每次聊天请求发送。

原因：自然对话往往依赖用户当前正在看什么或选中了什么。这个信息应该是显式数据，而不是模型猜测。

## ADR-015：内部复杂度必须对普通用户隐藏

状态：accepted

决策：UI 只暴露简单状态和动作，内部状态机留在后端服务和审计视图中。

用户可见状态：

```text
needs_info
draft_ready
awaiting_confirmation
completed
```

`proposal_ready`、`authorized`、`superseded`、`execution_unknown` 等内部状态名不作为普通 UI 文案。

## ADR-016：前端提供 Google 连接入口，但不持有 OAuth 密钥

状态：accepted

决策：前端必须提供类似普通应用登录的“连接 Google / 重新连接 / 断开连接”入口。前端只调用后端 OAuth API，不保存、不展示、不提交 `GOOGLE_CLIENT_SECRET`。

流程：

```text
用户点击连接 Google
→ 前端请求 GET /api/auth/google/login
→ 后端读取 .env 中的 GOOGLE_CLIENT_ID、GOOGLE_CLIENT_SECRET、GOOGLE_REDIRECT_URI
→ 后端生成 Google 授权 URL
→ 浏览器跳转到 Google
→ Google 回调 GET /gmail/auth/callback
→ 后端用 code 换 token
→ 后端加密保存 access token 和 refresh token
→ 前端通过 GET /api/auth/google/status 展示已连接状态
```

原因：OAuth Client ID 和 Client Secret 是应用级配置，不是用户输入项。即使系统只给一个人本地使用，也必须通过 Google OAuth 授权当前 Google 账号访问 Gmail 和 Calendar。

影响：

- `.env` 保存应用级 OAuth 配置；
- 前端只展示连接状态和操作按钮；
- `GOOGLE_CLIENT_SECRET` 只允许后端读取；
- 日志、接口响应和前端状态不得包含 OAuth secret 或 token；
- 用户撤销授权或切换账号后，前端必须提示重新连接。
