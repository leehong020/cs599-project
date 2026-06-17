# Mailflow Agent 架构说明

本文档是 CS599 课程提交目录下的架构说明入口。更完整的历史规格、ADR、安全规则和验收矩阵已归档到 `src/project-docs/`，这里保留面向评阅的简明架构视图。

## 系统分层

```mermaid
flowchart LR
    User["用户"] --> Frontend["Vue 3 前端"]
    Frontend --> API["FastAPI API 层"]
    API --> Graph["LangGraph 多 Agent 编排"]
    Graph --> Tools["工具层 / Execution Service"]
    Tools --> Gmail["Gmail API"]
    Tools --> Calendar["Google Calendar API"]
    API --> DB["SQLite 事实来源"]
    Graph --> DB
```

## Agent 编排

```mermaid
flowchart TD
    Start["用户输入"] --> StateLoader["state_loader"]
    StateLoader --> Supervisor["supervisor_agent"]
    Supervisor --> Context["context_agent"]
    Context --> Mail["mail_agent"]
    Mail --> Calendar["calendar_agent"]
    Calendar --> Review["review_gate"]
    Review --> Confirm["confirmation_gate"]
    Confirm --> Executor["executor"]
    Executor --> Response["response_agent"]
    Response --> Memory["memory_extractor"]
    Memory --> End["结束"]
```

## 安全执行闭环

```mermaid
flowchart LR
    Draft["本地 Artifact 草稿"] --> Proposal["Proposal Item"]
    Proposal --> Card["用户可见确认内容"]
    Card --> Auth["Authorization"]
    Auth --> Exec["Execution Service"]
    Exec --> External["Gmail / Calendar 写操作"]
    Exec --> Audit["Action Event 审计记录"]
```

## 关键设计原则

- AI 可以准备邮件和日程草稿，但不能绕过用户确认直接执行外部写操作。
- SQLite 是 Work Item、Artifact、Proposal、Authorization、Action Event、设置、联系人和记忆的事实来源。
- 上传文件、邮件正文和 LLM 输出都视为不可信上下文，不能覆盖系统安全规则。
- 前端只持有用户可见状态和交互上下文，不保存 OAuth Secret 或 access token。

## 详细文档位置

- Product Spec: `src/project-docs/product_scope.md`
- Architecture Decisions: `src/project-docs/architecture_decisions.md`
- Safety Rules: `src/project-docs/safety_rules.md`
- Acceptance Matrix: `src/project-docs/acceptance_matrix.md`
- Code Guide: `src/project-docs/code_guide.md`
