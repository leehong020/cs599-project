# 架构决策

## ADR-001：使用 FastAPI + LangGraph + LangChain + Vue 3

状态：accepted

决策：后端使用 FastAPI 提供 API，使用 LangGraph 编排多 Agent 流程，使用 LangChain 集成模型和工具，前端使用 Vue 3 构建页面。

原因：这套技术栈轻量，适合本地开发，也能支持图式编排、类型化 API、SSE 流式输出和现代前端体验。

## ADR-002：SQLite 是本地事实来源

状态：accepted

决策：MVP 使用 SQLite 保存用户设置、OAuth token、线程、消息、Work Item、Artifact、Proposal、Authorization、Action Event、文件元数据、记忆等数据。

原因：课程项目和本地个人使用场景不需要引入 PostgreSQL 或 Redis，SQLite 更容易运行和提交。

## ADR-003：Markdown 不是事实来源

状态：accepted

决策：Markdown 可以用于 README、架构说明、提示词模板、导出文件和课程文档，但不能保存密钥、授权事实、执行状态或唯一业务事实。

影响：

- `src/backend/app/config/prompts/*.md` 是运行时 prompt 模板。
- `src/project-docs/*.md` 和 `docs/*.md` 是作业/维护文档。
- `data/exports/*.md` 是从数据库导出的可读副本。

## ADR-004：Assistant 外部写操作必须经过 Proposal + Authorization

状态：accepted

决策：Assistant 触发的外部写操作必须表示为 `Proposal Item`，并在用户确认后由 `Execution Service` 调用 Google API。

外部写操作包括：

```text
send_email
create_calendar_event
update_calendar_event
delete_calendar_event
create_gmail_draft
update_gmail_draft
```

当前项目中，`create_gmail_draft` 和 `update_gmail_draft` 是邮件发送执行过程中的内部步骤，不作为普通前端功能暴露。

## ADR-005：Calendar 页面手动写入是明确用户操作

状态：accepted

决策：Calendar 页面提供新建、编辑和删除日程按钮。用户在该页面点击按钮时，视为明确的人为操作，可以直接调用 Calendar API。

边界：

- 该能力只属于 Calendar 页面手动操作。
- Assistant 不得绕过草稿、Proposal、用户确认和 Execution Service。
- Assistant 对日程的创建、修改、删除仍必须遵守 ADR-004。

## ADR-006：草稿变化会让旧确认失效

状态：accepted

决策：邮件或日程草稿 payload 发生有意义变化时，递增 version，重新计算 fingerprint，并让旧 Proposal 失效。

原因：用户确认只适用于当时看到的精确内容。

## ADR-007：关键字段必须有来源

状态：accepted

决策：收件人、参会人、时间、时区、日历、署名、邮件正文、日程标题等关键字段必须能追溯来源。

允许来源包括用户输入、用户设置、联系人唯一匹配、Gmail/Calendar 上下文、上传文件明确文本、选中上下文和系统默认值。单独依赖 LLM 推断不能授权外部写操作。

## ADR-008：文件内容是不可信上下文

状态：accepted

决策：上传文件可以被总结和引用，也可以在字段明确出现时作为 evidence，但文件中的指令不能覆盖系统规则，不能代替用户确认。

## ADR-009：用户设置是确定性偏好的事实来源

状态：accepted

决策：默认署名、默认时区、默认日历、默认会议时长、联系人等确定性信息保存在用户设置中。长期记忆不能静默覆盖用户设置。

## ADR-010：联系人同时服务邮件和日程

状态：accepted

决策：设置页维护的联系人同时用于邮件收件人和日程参会人解析。唯一匹配可以自动使用；无匹配或多重匹配时必须追问。

## ADR-011：前端只保存连接状态，不保存 OAuth secret

状态：accepted

决策：前端提供连接 Google、重新连接和断开连接入口，但不保存、不展示、不提交 `GOOGLE_CLIENT_SECRET`。OAuth client secret 只存在后端本地配置中。

OAuth 回调地址：

```text
http://localhost:8000/gmail/auth/callback
```

## ADR-012：内部复杂度对普通用户隐藏

状态：accepted

决策：用户界面展示聊天内容、确认卡片、日程和邮件结果，不展示内部节点名、工具调用、artifact id、work item id 或 Google Event ID。

内部状态和调试信息保留在后端、日志、测试和开发文档中。
