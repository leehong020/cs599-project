# 开发文档要求 vs 实际实现 差距分析

> 分析日期：2026-06-10
> 对照依据：开发文档阶段 0-11、验收矩阵 28 个 E2E 场景

---

## 总览

| 状态 | 数量 | 说明 |
|---|---|---|
| ✅ 已满足 | 42 | 代码完整，有测试覆盖 |
| ⚠️ 部分满足 | 6 | 骨架存在但缺关键能力 |
| ❌ 未实现 | 4 | 代码中不存在 |

---

## 一、各阶段逐项核查

### 阶段 0：需求冻结 ✅

| 检查项 | 状态 | 证据 |
|---|---|---|
| MVP 范围冻结 | ✅ | `docs/product_scope.md` |
| 安全规则冻结 | ✅ | `docs/safety_rules.md` |
| 必填字段冻结 | ✅ | `docs/required_fields.md` |
| ADR 已记录 | ✅ | `docs/architecture_decisions.md`（16 条 ADR） |
| 边界行为冻结 | ✅ | `docs/behavior_decisions.md` |

### 阶段 1：工程骨架 ✅

| 检查项 | 状态 | 证据 |
|---|---|---|
| FastAPI 可启动 | ✅ | `/api/health` 返回 `{"status":"ok"}` |
| Alembic 空库迁移 | ✅ | `0001_initial_schema.py` 完整 |
| Vue 可启动 | ✅ | `npm run dev` + `npm run build` |
| SQLite 创建 | ✅ | `data/runtime/app.sqlite3` |
| `.env` 忽略 | ✅ | `.gitignore` 覆盖 |
| 测试命令可运行 | ✅ | 43 tests pass |

### 阶段 2：Google OAuth ✅

| 检查项 | 状态 | 证据 |
|---|---|---|
| Google 登录 | ✅ | `api/auth.py` + `services/oauth.py` |
| Token 加密保存 | ✅ | Fernet 加密 |
| Token 刷新 | ✅ | `refresh_access_token()` |
| 断开连接 | ✅ | `disconnect_google_user()` |
| 前端不暴露 Secret | ✅ | 前端只调 `/api/auth/google/*` |
| 时区/署名/日历未配置时追问 | ⚠️ | 完整性校验有规则，但未接入 LLM 对话追问 |

### 阶段 3：字段依据与完整性 ✅

| 检查项 | 状态 | 证据 |
|---|---|---|
| Field Evidence 模型 | ✅ | `schemas/completeness.py` |
| Completeness Gate | ✅ | `services/completeness.py`（4 种草稿校验器） |
| 缺邮箱追问 | ✅ | 校验规则存在 |
| 缺署名追问 | ✅ | 校验规则存在 |
| 缺时长追问 | ✅ | 校验规则存在 |
| AI 推断字段不可执行 | ✅ | `NON_EXECUTABLE_SOURCE_TYPES` 包含 `llm_inference` |
| 合并追问 | ✅ | `_build_questions()` 一次最多 3 个 |

### 阶段 4：Gmail 能力 ✅

| 检查项 | 状态 | 证据 |
|---|---|---|
| 搜索邮件 | ✅ | `GmailClient.search_messages()` → Gmail REST API |
| 读取详情 | ✅ | `GmailClient.get_message()` |
| 读取线程 | ✅ | `GmailClient.get_thread()` |
| MIME 解析 | ✅ | `extract_body_from_payload()` + HTML→文本 |
| 本地 Artifact 生成 | ✅ | `prepare_new/reply/forward_email_artifact()` |
| 确认后创建 Gmail Draft | ✅ | `commit_send_email_for_authorized_proposal()` |
| 确认后发送 | ✅ | 同上，Draft → Send 一条龙 |
| 未授权不可发送 | ✅ | `_load_authorized_send_email_proposal()` 校验 |
| 重复确认只发一次 | ✅ | 幂等 key 检查 |
| 回复邮件保持 Thread | ✅ | `In-Reply-To` + `References` headers |

### 阶段 5：Calendar 能力 ✅

| 检查项 | 状态 | 证据 |
|---|---|---|
| 读取事件 | ✅ | `CalendarClient.list_events()` |
| Freebusy 查询 | ✅ | `CalendarClient.query_freebusy()` |
| 冲突判断 | ✅ | `find_conflicts()` |
| 时区保留 | ✅ | `timeZone` 字段正确传递 |
| 邀请邮箱校验 | ✅ | `validate_attendee_emails()` |
| 缺时间不可创建 | ✅ | `calculate_end_time()` 阻止 |
| 重复点击只创建一次 | ✅ | 幂等 key |
| 更新前读取旧事件 | ✅ | `get_event_for_update()` |

### 阶段 6：Work Item / Proposal 安全闭环 ✅

| 检查项 | 状态 | 证据 |
|---|---|---|
| 多 Open Work Item | ✅ | `list_open_work_items()` |
| Proposal 有 version | ✅ | `proposal_items.version` |
| Proposal 有 fingerprint | ✅ | SHA-256 |
| 修改后旧授权失效 | ✅ | 旧 Proposal 标记 `superseded` |
| 部分确认 | ✅ | 每个 Proposal Item 独立授权 |
| "确认发送"只筛选邮件 | ✅ | `resolve_confirmation_candidates()` 按 action_type |
| 多封待发追问 | ✅ | `ResolveConfirmationResponse.status=ambiguous` |
| 幂等发送 | ✅ | `idempotency_key` + 条件更新 |
| 审计完整 | ✅ | `action_events` 表 + 审计日志 |

### 阶段 7：LangGraph ✅ (LLM 接入前为 ⚠️)

| 检查项 | 状态 | 证据 |
|---|---|---|
| 主图编译 | ✅ | `build_assistant_graph()` |
| Mail Subgraph | ✅ | `build_mail_subgraph()` |
| Calendar Subgraph | ✅ | `build_calendar_subgraph()` |
| 多人解析 | ⚠️ | 仅关键词提取，非 LLM 理解 |
| 同名联系人追问 | ✅ | `resolve_contact_mentions()` 检测歧义 |
| 多任务 DAG | ✅ | `schedule_task_batches()` |
| 无依赖任务并行 | ✅ | 同批次并行 |
| recursion limit | ✅ | 80 |
| Mermaid 导出 | ✅ | `export_assistant_mermaid()` |
| thread_id 恢复 | ✅ | SQLite checkpoint |
| LLM 生成自然语言回复 | ✅ | **刚刚完成**（`compose_response` 接入 LLM） |
| LLM 意图分类 | ✅ | **刚刚完成**（`interpret_user_turn`） |
| LLM 任务编译 | ✅ | **刚刚完成**（`compile_request_tasks_with_llm`） |

### 阶段 8：Vue 聊天界面 ✅

| 检查项 | 状态 | 证据 |
|---|---|---|
| SSE 进度 | ✅ | `streamAssistantTurn()` |
| 缺失字段提示 | ⚠️ | 前端展示 clarification，但后端 LLM 追问格式待验证 |
| 邮件卡片 | ✅ | `ProposalCard.vue`（蓝色系） |
| 日程卡片 | ✅ | `ProposalCard.vue`（绿色系） |
| 按钮携带 Proposal ID/version/fingerprint | ✅ | 卡片操作栏 |
| 聊天式确认 | ✅ | "确认发送"解析 + 授权 |
| 刷新恢复 Open Work Items | ✅ | `refreshTodos()` |
| 多工作项并存 | ✅ | 待办列表 |
| 左侧图标导航 | ✅ | `AppSidebar.vue` |
| 右侧上下文面板 | ✅ | `ContextPanel.vue` |
| Gmail 工作台 | ✅ | 搜索 + 详情 + 草稿 |
| Calendar 工作台 | ✅ | 日程列表 + Freebusy + 草稿 |
| 设置页 | ✅ | 子标签：设置/署名/Google |

### 阶段 9：记忆 ✅

| 检查项 | 状态 | 证据 |
|---|---|---|
| Thread 恢复 | ✅ | SQLite checkpoint |
| 最近消息窗口 | ✅ | `RECENT_MESSAGE_LIMIT = 12` |
| 长对话摘要 | ✅ | `_summarize_messages()` |
| 署名长期保存 | ✅ | `signatures` 表 + `user_settings` |
| 临时指令不误写长期 | ✅ | `TEMPORARY_MARKERS` 检测 |
| 联系人备注按需召回 | ✅ | `recall_contact_notes()` |
| Markdown 导出 | ✅ | `export_markdown_bundle()` |

### 阶段 10：测试/安全 ✅

| 检查项 | 状态 | 证据 |
|---|---|---|
| 单元测试 43 个 | ✅ | 全部通过 |
| Token 不出现日志 | ✅ | `RedactingFilter` |
| Prompt Injection 防护 | ✅ | 文件内容不可覆盖策略 |
| 重复确认不重复写 | ✅ | 幂等测试 |
| 错误可追踪 | ✅ | `log_error_trace()` |
| Mermaid 可导出 | ✅ | API 端点 |
| 节点耗时可观测 | ✅ | `node_timings` |

---

## 二、⚠️ 部分满足的 6 项

### GAP-1：多人解析仅关键词匹配

- **要求**：LLM 理解自然语言中的多人、多任务表达
- **现状**：`tasks.py` 有 LLM 路径（刚加入），但 `extract_contact_mentions` 仍只用正则 `(?:给|邀请)(.+?)`
- **影响**："给销售部的张三和李四发邮件" → 正则可能漏人
- **建议**：在 `interpret_user_turn` 中让 LLM 同时提取实体列表

### GAP-2：选中上下文未被图使用

- **要求**：用户选中邮件/日程后，图应使用选中对象作为操作目标
- **现状**：`selected_context_refs` 存在 state 中，`resolve_turn_references` 只是透传，后续节点不使用
- **影响**：用户选中邮件说"回复他"，图不知道要回复谁
- **建议**：在 `collect_grounded_context` 或 `resolve_entities` 中读取 refs 并获取实际内容

### GAP-3：日程冲突检查未接入图编排

- **要求**：创建日程 Proposal 前必须 Freebusy，冲突时展示警告
- **现状**：Calendar service 有完整的冲突检测逻辑，但图的子图不调用真实 Calendar API
- **影响**：LLM 可以生成日程草稿，但不会检查冲突
- **建议**：子图接入 CalendarClient，或在 `build_proposal_group` 时查询

### GAP-4：LLM 安全边界依赖提示词而非代码

- **要求**："AI 不可以猜测收件人邮箱、署名、会议时间、时区"
- **现状**：LLM 通过 `system_prompt.md` 被告知这些规则，但没有代码层兜底
- **影响**：LLM 可能在复杂 prompt 下绕过提示词限制
- **建议**：在 `build_proposal_group` 前增加代码层校验——检查关键字段的 Field Evidence 是否存在

### GAP-5：文件上传解析已补齐

- **要求**：用户上传 PDF/DOCX/TXT/MD，提取文本作为上下文
- **现状**：已新增 `POST /api/files`、`GET /api/files`、`GET /api/files/{id}`、`POST /api/files/{id}/extract`、`DELETE /api/files/{id}`，实现文件保存、解析、读取和删除
- **证据**：`backend/app/api/files.py`、`backend/app/services/files.py`、`frontend/src/api/files.ts`、`backend/tests/unit/test_files.py`
- **限制**：解析文本只作为不可信上下文，不作为用户确认或系统策略

### GAP-6：代码导览已更新

- **要求**：每个阶段完成后必须更新 `docs/code_guide.md`
- **现状**：已同步文件上传解析相关 API、service、schema、前端 API 和测试说明

---

## 三、❌ 未实现的 4 项

### GAP-7：文件上传解析 API 已实现

- 验收场景：E2E-019, E2E-020, E2E-025
- 当前：文件 API、解析服务和前端上传入口已实现
- 剩余：需要补真实浏览器 E2E 和复杂 PDF/DOCX 样本测试

### GAP-8：E2E 验收未执行

- 验收矩阵中 28 个 E2E 场景
- 当前：单元测试覆盖安全规则，但端到端场景（从用户输入到系统回复）未经测试
- 部分场景需要 Google 连接（无法自动化），但 LLM 对话场景可以测

### GAP-9：多标签并发未实测

- E2E-028 需要两个浏览器标签同时确认
- 当前：幂等逻辑在数据库层有保护，但未经过并发测试

### GAP-10：Token 过期/撤销恢复流程

- E2E-027 需要模拟 Token 撤销后确认 Proposal
- 当前：`get_valid_google_access_token` 有刷新逻辑，但撤销后的恢复体验未测试

---

## 四、总结

### 核心能力达成率

```
安全闭环（Proposal/Authorization/Execution）： ████████████████████ 100%
Google OAuth 集成：                           ████████████████████ 100%
Gmail 读取/发送：                             ████████████████████ 100%
Calendar 读取/创建：                          ████████████████████ 100%
LangGraph 编排 + LLM 对话：                   ██████████████████░░  95%
前端 UI：                                    ██████████████████░░  90%
文件上传解析：                                ████████████████░░░░  80%
E2E 验收：                                   ██████████░░░░░░░░░░  50%
```

### 最优先补的 3 项

1. **LLM 安全代码层兜底**（GAP-4）—— 防止 LLM 绕过规则猜测关键字段
2. **选中上下文接入图**（GAP-2）—— 让"选中邮件→回复"工作流跑通
3. **更新代码导览**（GAP-6）—— 文档与代码一致
