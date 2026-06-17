# 产品范围

## 目的

本项目是一套本地优先的 Gmail 与 Google Calendar AI 助理。它帮助用户撰写邮件、准备回复、总结邮件上下文、创建或修改日程、解析用户上传的文档，并通过自然对话协调这些动作。

系统在用户体验上应该像“聊天助理 + 卡片 + 选中上下文”，而不是一个显眼的工作流引擎。内部可以使用 `Work Item`、`Artifact`、`Proposal`、`Authorization` 和 `Field Evidence` 来保证高风险动作安全、可追踪、可恢复。

## MVP 的白话解释

MVP 是 `Minimum Viable Product`，可以理解为“最小可用版本”或“最小可验证版本”。

它不是最终完整产品，也不是随便做一个演示页面。对本项目来说，MVP 的意思是：先做出一条能真实闭环、能被用户安全验证的核心路径。

本项目的 MVP 闭环是：

```text
Google 登录
→ 选择或上传邮件、日程、文件上下文
→ 对话生成本地邮件草稿或日程草稿
→ 缺字段时继续追问
→ 展示 Proposal 确认卡片
→ 用户明确确认
→ 执行 Gmail 或 Calendar 写操作
→ 保存执行记录，避免重复执行
```

因此，MVP 重点不是把所有功能都做完，而是把最关键、最危险、最能证明系统价值的链路做通。

## MVP 用户

- 本地运行应用的单个开发者。
- 一个主要 Google 账号。
- 少量用于演示、课程设计或毕业设计的测试用户。
- 希望用助理方式处理邮件和日程，同时要求外部写操作前明确确认的用户。

## MVP 必须支持

| 领域 | 范围 |
|---|---|
| Google OAuth | 登录、Token 加密存储、刷新、断开连接 |
| User settings | 发件账号、署名、时区、默认日历、会议时长、工作时间、午休时间 |
| Gmail read | 搜索邮件、读取邮件详情、读取线程、总结线程 |
| Gmail local drafts | 新邮件、回复邮件、转发邮件、本地邮件 `Artifact` 修改 |
| Gmail send | 通过 `Proposal + Authorization + Execution Service` 确认后发送 |
| Calendar read | 列出事件、查询 `Freebusy`、冲突检查 |
| Calendar local drafts | 创建日程草稿、修改日程草稿 |
| Calendar write | 通过 `Proposal + Authorization + Execution Service` 确认后创建或更新 |
| File upload | 解析用户主动上传的 PDF、DOCX、TXT、Markdown |
| Selected context | 显式选中的邮件、日程、文件、文件片段、草稿或 Proposal 卡片 |
| Conversation | 多轮聊天、追问、基于上下文修改 |
| Safety | `Provenance`、完整性校验、策略保护、幂等执行 |
| Persistence | SQLite 作为事实来源，Markdown 仅用于可读导出和 Prompt |
| Frontend | 聊天流、Google 连接入口、Open Work Item 面板、草稿卡片、确认卡片、文件卡片、选中上下文栏 |

## MVP 暂不支持

- Outlook 或 Exchange。
- 多租户组织管理。
- 企业多级审批。
- Gmail Watch、Google Pub/Sub、Calendar Push Notification。
- Redis、PostgreSQL、Celery、Kafka。
- 向量数据库。
- 自动扫描并解析邮箱中所有附件。
- 批量归档。
- 自动删除邮件。
- 无人值守自动发送邮件。
- 无人值守自动邀请外部参会人。

## 草稿边界

MVP 中邮件草稿和日程草稿都是本地 `Artifact`。

生成或修改草稿不得写入 Gmail 或 Google Calendar。创建或更新 Gmail Draft 属于外部写操作，必须经过 `Proposal + Authorization + Execution Service`。

默认发送流程：

```text
local email Artifact
→ Proposal Item: send_email
→ 用户确认当前 version 和 fingerprint
→ Execution Service 创建或更新 Gmail Draft
→ Execution Service 发送 Gmail Draft
→ Action Event 记录外部执行结果
```

如果后续版本增加“同步到 Gmail 草稿箱”，则 `create_gmail_draft` 和 `update_gmail_draft` 必须成为独立的 `Proposal Item` 动作类型。

## 文件上传边界

用户可以显式上传文件。系统不自动发现或解析所有 Gmail 附件。

MVP 支持格式：

```text
.pdf
.docx
.txt
.md
```

文件内容属于不可信上下文。它可以支持摘要、邮件、回复、日程准备，但文件里的指令不能覆盖系统安全规则。

## 选中上下文边界

前端必须显式发送选中上下文。后端不得把“最近展示”或“当前聚焦”的对象当作权威目标。

允许的选中上下文类型：

```text
gmail_thread
gmail_message
calendar_event
work_item
artifact
proposal_item
uploaded_file
file_extraction
file_span
```

如果选中上下文和用户文本冲突，助理必须追问。

## UX 原则

- 向用户隐藏内部工作流复杂度。
- 只展示人能理解的状态：需要补充、草稿已准备、等待确认、已完成。
- 允许用户选中卡片或文件后自然表达需求。
- 缺少多个字段时尽量一次合并追问。
- 不要求用户记住任何 ID。
- 确认卡片必须展示精确版本、可见内容和高风险字段。
- 每一轮回复都应该给用户一个明确的下一步。

## 成功标准

- 助理可以准备邮件，但不会写入 Gmail。
- 用户确认当前 `Proposal` 之前，助理不能发送邮件。
- 助理可以修改旧草稿，并让旧授权失效。
- 助理可以把用户上传的 PDF 或 DOCX 作为可引用上下文。
- 助理可以把选中的邮件或日程作为目标，不依赖猜测。
- 关键字段缺失或歧义时，助理会追问而不是猜测。
