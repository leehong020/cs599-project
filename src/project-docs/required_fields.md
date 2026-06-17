# 必填字段

## Field Evidence 模型

每个关键字段必须包含：

```text
value
source_type
source_ref
confidence
confirmation_status
updated_at
```

允许的 `source_type`：

```text
user_message
user_profile
contact_store
gmail_message
gmail_thread
calendar_event
calendar_freebusy
uploaded_file
file_extraction
selected_context
system_default
llm_inference
unresolved
```

允许的 `confirmation_status`：

```text
verified
explicit_user_input
inferred_needs_review
missing
ambiguous
```

## 来源可信等级

| 优先级 | 来源 | 能否进入可执行 Proposal |
|---:|---|---|
| 1 | 用户本轮明确输入 | 可以 |
| 2 | 用户设置 | 可以 |
| 3 | 联系人唯一匹配 | 可以 |
| 4 | Gmail message 或 thread | 可以，但要谨慎 |
| 5 | 已存在 Calendar event | 可以 |
| 6 | 选中上下文 | 目标明确时可以 |
| 7 | 上传文件或文件解析结果 | 字段在文件中明确出现时可以 |
| 8 | 系统默认值 | 仅限低风险字段，且必须展示 |
| 9 | LLM 推断 | 不可以 |
| 10 | 缺失或歧义 | 不可以 |

## 新邮件必填字段

| 字段 | 必填 | 允许来源 |
|---|---:|---|
| 发件账号 | 是 | OAuth 用户账号、用户设置、用户显式选择 |
| To 收件人 | 是 | 用户输入、唯一联系人匹配、选中上下文 |
| 主题 | 是 | 用户输入、展示给用户的 AI 候选 |
| 正文 | 是 | 用户输入、AI 草稿、文件解析、选中上下文 |
| 署名策略 | 是 | 用户设置、用户输入、明确选择不加署名 |
| CC | 条件必填 | 用户提到 CC 时必须 |
| BCC | 条件必填 | 用户提到 BCC 时必须 |
| 附件 | 条件必填 | 用户要求附加文件时必须 |

以下情况禁止进入可执行 Proposal：

- 任一必填字段缺失。
- 任一收件人邮箱存在歧义。
- 署名策略不明确。
- 正文为空。
- payload fingerprint 无法计算。

## 回复邮件必填字段

| 字段 | 必填 | 允许来源 |
|---|---:|---|
| Gmail Thread ID | 是 | 选中邮件/thread、Gmail 搜索结果 |
| Reply-To Message ID | 是 | 选中 message、Gmail thread |
| 发件账号 | 是 | OAuth 用户账号、用户设置、用户显式选择 |
| To 收件人 | 是 | Gmail headers、用户输入 |
| 主题 | 是 | Gmail thread、用户输入 |
| 正文 | 是 | 用户输入、AI 草稿、文件解析 |
| 署名策略 | 是 | 用户设置、用户输入、明确选择不加署名 |

目标 thread/message 无法唯一确定时，禁止进入可执行 Proposal。

## 转发邮件必填字段

| 字段 | 必填 | 允许来源 |
|---|---:|---|
| Source Message ID | 是 | 选中 message、Gmail 搜索结果 |
| 转发收件人 | 是 | 用户输入、唯一联系人匹配 |
| 发件账号 | 是 | OAuth 用户账号、用户设置、用户显式选择 |
| 转发主题 | 是 | Gmail message、展示给用户的 AI 候选 |
| 附加说明 | 可选 | 用户输入、AI 草稿 |
| 署名策略 | 条件必填 | 存在附加说明时必须 |

## 日程必填字段

| 字段 | 必填 | 允许来源 |
|---|---:|---|
| 标题 | 是 | 用户输入、邮件上下文、文件解析、展示给用户的 AI 候选 |
| 开始时间 | 是 | 用户输入、明确的邮件/文件/日历上下文、已确认候选 |
| 结束时间或持续时长 | 是 | 用户输入、用户设置 |
| 时区 | 是 | 用户设置、用户输入 |
| 目标日历 | 是 | 用户设置、用户选择 |
| 组织者账号 | 是 | OAuth 用户账号 |
| 参会人邮箱 | 条件必填 | 需要邀请参会人时必须 |
| 地点 | 条件必填 | 用户提到地点时必须 |
| 视频会议策略 | 条件必填 | 用户要求线上会议时必须 |
| 重复规则 | 条件必填 | 周期会议必须 |
| 提醒设置 | 建议 | 用户设置或展示默认值 |
| 冲突检查 | 建议 | Calendar Freebusy |

以下情况禁止进入可执行 Proposal：

- 开始时间缺失或存在歧义。
- 结束时间或持续时长缺失。
- 时区缺失。
- 开始时间不早于结束时间。
- 参会人邮箱存在歧义。
- 重复规则无法解析。
- Proposal 不是最新版本。

## File Artifact 必填字段

| 字段 | 必填 | 说明 |
|---|---:|---|
| File ID | 是 | 本地 ID |
| User ID | 是 | 所有者 |
| Original filename | 是 | 仅用于展示 |
| Content type | 是 | 必须匹配支持类型 |
| File size | 是 | 必须通过大小限制 |
| SHA-256 | 是 | 完整性和去重 |
| Storage path | 是 | 本地存储引用 |
| Extraction status | 是 | uploaded、extracting、extracted、failed、deleted |

文件解析必填字段：

| 字段 | 必填 |
|---|---:|
| Extraction ID | 是 |
| Uploaded file ID | 是 |
| Extractor name | 是 |
| Status | 是 |
| Text content | 成功时必须 |
| Metadata | 建议 |
| Error message | 失败时必须 |

## Selected Context 必填字段

| 字段 | 必填 | 说明 |
|---|---:|---|
| `ref_type` | 是 | 被选中对象的类型 |
| `ref_id` | 是 | 稳定对象 ID |
| `selection` | 可选 | 页码、范围、卡片字段或文本片段 |

选中上下文只在当前用户和当前 thread 中有效。

## 追问规则

多个字段缺失时，尽量一次合并追问。

示例：

```text
这封邮件还缺少两项信息，补充后我才能准备可发送确认：
1. 李明的邮箱；
2. 署名。使用“张伟”，还是不加署名？
```

```text
我已记录会议开始时间为明天下午 3:00，还需要确认：
1. 会议持续多久；
2. 使用哪个时区。
```
