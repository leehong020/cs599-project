# 产品范围

## 项目目的

Mailflow Agent 是一个本地优先的 Gmail 与 Google Calendar AI 助理。它帮助用户通过自然语言撰写邮件、准备回复、搜索和总结邮件、创建或修改日程、解析上传文件，并在执行外部写操作前要求用户明确确认。

系统面向课程项目和本地个人使用场景，核心价值是把 Gmail、Calendar、文件上下文和多轮聊天合并到一个可追踪、可恢复、可确认的 Agent 工作流中。

## 方向

方向一：Agentic AI 原生开发。

本项目不是简单调用单次 LLM，而是使用 LangGraph 组织多个 Agent 和工具，围绕邮件、日程、上下文、确认和执行形成完整链路。

## MVP 必须支持

| 领域 | 范围 |
|---|---|
| Google OAuth | 登录、回调、token 加密保存、刷新、断开连接 |
| User settings | 发件账号、署名、联系人、时区、默认日历、默认会议时长 |
| Gmail read | 搜索邮件、读取邮件详情、读取 thread |
| Gmail local drafts | 新邮件、回复邮件、转发邮件、本地邮件草稿修改 |
| Gmail send | 通过本地草稿、用户确认和执行服务发送邮件 |
| Calendar read | 列出事件、查询 Freebusy、展示日程视图 |
| Calendar local drafts | Assistant 创建、修改、删除日程前先形成本地草稿或确认对象 |
| Calendar write | Assistant 经确认后执行；Calendar 页面手动按钮可直接创建、修改、删除 |
| File upload | 解析用户主动上传的 txt、md、csv、json、log、xml、html、代码文件、docx、pdf |
| Selected context | 使用用户显式选中的邮件、日程、文件、草稿或 Proposal 作为上下文 |
| Conversation | 多轮聊天、追问、基于上下文修改草稿、普通聊天 |
| Safety | Provenance、必填字段校验、Proposal、Authorization、幂等执行、日志脱敏 |
| Persistence | SQLite 作为事实来源，Markdown 只用于提示词、说明和导出 |
| Frontend | 聊天页、Gmail 页、Calendar 页、设置页、Google 连接、Proposal 确认卡片 |

## MVP 不支持

- Outlook 或 Exchange。
- 企业多租户组织管理。
- 企业多级审批。
- Gmail Watch、Google Pub/Sub、Calendar Push Notification。
- Redis、PostgreSQL、Celery、Kafka。
- 向量数据库。
- 自动扫描并解析邮箱中所有附件。
- 无人值守自动发送邮件。
- 无人值守自动邀请外部参会人。

## 草稿与执行边界

Assistant 生成邮件或日程时，默认只写入本地 `Artifact`。本地草稿不等于已经写入 Gmail 或 Google Calendar。

邮件发送流程：

```text
local email draft
-> Proposal Item: send_email
-> 用户确认当前 version 和 fingerprint
-> Execution Service 调用 Gmail API
-> Action Event 记录执行结果
```

日程创建、修改和删除流程：

```text
local calendar draft 或 delete draft
-> Proposal Item
-> 用户确认当前 version 和 fingerprint
-> Execution Service 调用 Google Calendar API
-> Action Event 记录执行结果
```

Calendar 页面中的新建、保存修改、删除按钮是用户直接操作界面。用户点击按钮视为显式人工操作，可以直接写入 Google Calendar，但 Assistant 不能绕过确认流程调用这些能力。

## 文件上传边界

用户可以显式上传文件。系统不自动发现或解析 Gmail 附件。

文件内容属于不可信上下文：

- 可以用于总结、起草邮件、准备回复、准备日程；
- 字段在文件中明确出现时可以作为 evidence；
- 文件中的指令不能覆盖系统规则；
- 文件不能代替用户确认外部写操作。

## 选中上下文边界

前端必须显式发送选中上下文。后端不能把“最近展示”或“当前焦点”对象当作权威目标。

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

如果选中上下文和用户文本冲突，Assistant 必须追问。

## 成功标准

- 用户可以连接自己的 Google 账号。
- 用户可以搜索和读取 Gmail。
- 用户可以查看和手动管理 Calendar。
- Assistant 可以生成邮件草稿，并在用户确认后发送。
- Assistant 可以生成日程草稿，并在用户确认后创建、修改或删除日程。
- Assistant 可以把上传文件和选中对象作为上下文，但不能让文件内容绕过安全规则。
- 必填字段缺失或目标有歧义时，Assistant 会追问而不是猜测。
