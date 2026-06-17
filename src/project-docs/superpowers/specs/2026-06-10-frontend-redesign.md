# 前端 UI 重新设计规格

> 编写日期：2026-06-10
> 状态：已确认
> 目标：将 2300+ 行单体 App.vue 重构为现代化、组件化的聊天助理界面

## 1. 设计目标

- 从单一 App.vue（2300+ 行）拆分为 ~16 个独立 Vue 组件
- 三栏布局，视觉层次清晰
- 专业蓝灰色调，接近 Linear / Stripe 风格
- Proposal 确认操作内嵌聊天流，不暴露内部状态机术语
- 保持与现有后端 API 完全兼容，仅修改前端

## 2. 整体布局：三栏结构

```
┌──────────┬──────────────────────────┬─────────────┐
│ 图标导航  │      主内容区              │ 上下文面板   │
│  52px    │       flex: 1            │   240px     │
│          │                          │             │
│   M      │  视图标题栏               │  待办摘要    │
│          │  ─────────────────       │             │
│   💬     │                          │  Google     │
│          │  视图内容                 │  状态       │
│   📧     │  （聊天 / Gmail /        │             │
│          │   Calendar / 设置）       │  快捷操作    │
│   📅     │                          │             │
│          │                          │             │
│   ⚙️     │                          │             │
│          │                          │             │
└──────────┴──────────────────────────┴─────────────┘
```

- **左侧**：52px 深色图标导航栏（#1e293b），4 个导航项 + 品牌标识
- **中间**：白色主内容区，根据当前视图切换内容
- **右侧**：240px 浅灰上下文面板（#f8fafc），待办列表 + Google 状态 + 快捷操作

## 3. 视觉设计系统

### 3.1 色彩体系

| 用途 | 颜色 | 色值 |
|---|---|---|
| 侧栏背景 | 深蓝灰 | #1e293b |
| 侧栏文字 | 灰蓝 | #64748b |
| 主强调色 | 蓝色 | #3b82f6 / #2563eb |
| 主背景 | 白色 | #ffffff |
| 面板背景 | 浅灰 | #f8fafc |
| 边框 | 灰 | #e2e8f0 |
| 标题文字 | 近黑 | #0f172a |
| 正文文字 | 深灰 | #334155 |
| 辅助文字 | 灰 | #475569 / #64748b |
| 弱文字 | 浅灰 | #94a3b8 |
| 成功绿 | 绿 | #059669 |
| 警告黄 | 琥珀 | #fef3c7 / #92400e |
| 错误红 | 红 | #fef2f2 / #991b1b |

### 3.2 邮件卡片色彩

| 用途 | 色值 |
|---|---|
| 卡片头部背景 | #eff6ff |
| 卡片边框 | #bfdbfe |
| 主按钮 | #2563eb |
| 正文左边框 | #3b82f6 |

### 3.3 日程卡片色彩

| 用途 | 色值 |
|---|---|
| 卡片头部背景 | #ecfdf5 |
| 卡片边框 | #a7f3d0 |
| 主按钮 | #059669 |
| 冲突警告框 | #fef2f2 背景 + #fecaca 边框 + #991b1b 文字 |

### 3.4 字体与圆角

- 字体：Inter, system-ui, sans-serif
- 圆角：按钮/输入框 6-7px，卡片 10px，气泡 8px
- 间距：8px 基准网格

## 4. 导航结构

4 个视图，左侧图标栏切换：

| 图标 | 视图 | 主内容 | 右侧面板 |
|---|---|---|---|
| 💬 | 聊天 | 对话历史 + Proposal 内嵌卡片 + 输入区 | 待办摘要 + Google 状态 + 快捷操作 |
| 📧 | Gmail | 搜索 + 结果列表 + 邮件详情 + 草稿表单 | 最近草稿 + 相关待办 |
| 📅 | Calendar | 日程列表 + Freebusy + 草稿表单 | 冲突提示 + 相关待办 |
| ⚙️ | 设置 | 子标签：个人设置 / 署名管理 / Google 连接 | — |

## 5. 组件树

```
App.vue
├── AppSidebar.vue           ← 左侧 52px 图标导航（4 项 + 品牌标识）
├── ChatView.vue             ← 聊天主视图
│   ├── ChatMessage.vue      ← 单条消息气泡（user / assistant / system）
│   ├── ProposalCard.vue     ← 内嵌确认卡片（邮件蓝色系 / 日程绿色系）
│   └── ChatInput.vue        ← 底部输入区（附件 + 输入 + 发送）
├── GmailView.vue            ← Gmail 工作台
│   ├── GmailSearch.vue      ← 搜索栏 + 结果列表
│   ├── GmailDetail.vue      ← 邮件详情展示
│   └── EmailDraftForm.vue   ← 新邮件 / 回复草稿表单
├── CalendarView.vue         ← Calendar 工作台
│   ├── EventList.vue        ← 日程列表
│   ├── FreebusyPanel.vue    ← 忙闲查询与冲突展示
│   └── CalendarDraftForm.vue ← 日程草稿表单
├── SettingsView.vue         ← 设置页
│   ├── ProfileSettings.vue  ← 个人设置表单
│   ├── SignatureManager.vue ← 署名列表 + 创建
│   └── GoogleConnection.vue ← Google 连接状态 + 按钮
└── ContextPanel.vue         ← 右侧上下文面板
    ├── TodoList.vue          ← 待办摘要列表
    ├── GoogleStatusBadge.vue ← Google 账号状态
    └── QuickActions.vue      ← 上传文件 / 导出 Markdown
```

## 6. 聊天视图设计

### 6.1 消息气泡类型

| 类型 | 样式 | 说明 |
|---|---|---|
| 用户消息 | 右对齐，蓝底（#3b82f6）白字，max-width 520px | 用户输入 |
| 助手消息 | 左对齐，带头像圆圈，浅灰底（#f8fafc）+ 边框 | AI 回复 |
| 系统提示 | 居中，轻量标签样式（灰底/黄底） | 进度、通知、错误 |
| Proposal 卡片 | 嵌入对话流，独立卡片样式 | 确认/修改/暂缓 |

### 6.2 Proposal 卡片

两种卡片嵌入聊天消息流中，共同结构：
- **头部**：图标 + 标题 + 状态标签（等待确认/已确认/草稿中）
- **字段区**：关键字段摘要展示
- **正文区**：正文预览（邮件）或冲突警告（日程）
- **操作栏**：主按钮 + 修改 + 暂缓 + 版本指纹

**邮件卡片** (蓝色系)：
- 头部图标 📧，背景 #eff6ff，边框 #bfdbfe
- 主操作按钮「确认发送」，颜色 #2563eb
- 正文区蓝色左边框引用样式

**日程卡片** (绿色系)：
- 头部图标 📅，背景 #ecfdf5，边框 #a7f3d0
- 主操作按钮，颜色 #059669
- 冲突时：红色冲突卡片（#fef2f2 / #fecaca），按钮文案变为「仍然创建」
- 无冲突时：按钮文案「创建日程」

## 7. 右侧面板设计

宽度 240px，固定显示，内容从上到下：
1. **待办摘要**：标题 + 计数 badge，每个待办项显示图标（📧/📅）、标题、摘要、状态标签
2. **Google 状态**：绿色连接卡片（已连接）/ 灰色未连接提示
3. **快捷操作**：上传文件、导出 Markdown 按钮

## 8. 设置页设计

顶部子标签切换：**个人设置** | **署名管理** | **Google 连接**

- **个人设置**：时区、发件账号、默认日历、会议时长、缓冲时间、邮件语气等表单
- **署名管理**：署名列表 + 新建署名表单
- **Google 连接**：连接状态 + 连接/断开按钮

## 9. 兼容性要求

- 不修改后端 API，仅重构前端
- 所有现有功能保持不变（聊天、Gmail 搜索/草稿、Calendar 查询/草稿、Proposal 确认、设置、署名、Markdown 导出）
- 保持 SSE 聊天流处理逻辑不变
- API 客户端（`frontend/src/api/*.ts`）无需修改

## 10. 不涉及的范围

- 不新增后端 API
- 不修改数据库结构
- 不新增功能（文件上传、选中上下文等仍为后续范围）
- 不引入 UI 组件库（使用纯 CSS 实现）
- 不引入 TypeScript 之外的构建工具

## 11. 文件变更清单

### 新增文件

```
frontend/src/components/AppSidebar.vue
frontend/src/components/ContextPanel.vue
frontend/src/components/TodoList.vue
frontend/src/components/GoogleStatusBadge.vue
frontend/src/components/QuickActions.vue
frontend/src/components/chat/ChatView.vue
frontend/src/components/chat/ChatMessage.vue
frontend/src/components/chat/ProposalCard.vue
frontend/src/components/chat/ChatInput.vue
frontend/src/components/gmail/GmailView.vue
frontend/src/components/gmail/GmailSearch.vue
frontend/src/components/gmail/GmailDetail.vue
frontend/src/components/gmail/EmailDraftForm.vue
frontend/src/components/calendar/CalendarView.vue
frontend/src/components/calendar/EventList.vue
frontend/src/components/calendar/FreebusyPanel.vue
frontend/src/components/calendar/CalendarDraftForm.vue
frontend/src/components/settings/SettingsView.vue
frontend/src/components/settings/ProfileSettings.vue
frontend/src/components/settings/SignatureManager.vue
frontend/src/components/settings/GoogleConnection.vue
```

### 修改文件

```
frontend/src/App.vue          — 重写为布局壳，移除所有业务逻辑
frontend/src/styles.css       — 替换为新的设计系统样式
frontend/index.html           — 更新标题和字体引用
```

### 不变文件

```
frontend/src/api/*.ts         — 所有 API 客户端保持不变
frontend/src/main.ts          — Vue 挂载入口不变
frontend/vite.config.ts       — Vite 配置不变
frontend/tsconfig.json        — TypeScript 配置不变
frontend/package.json         — 依赖不变
```
