# 前端 UI 重新设计 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 2300+ 行单体 App.vue 重构为 ~21 个独立 Vue 组件的现代化三栏布局界面，专业蓝灰风格，不修改后端 API。

**Architecture:** 采用三栏布局（图标侧栏 + 主内容 + 上下文面板），4 个视图通过左侧图标栏切换。共享状态（Google 连接、用户设置、署名、待办）通过 provide/inject 从 App.vue 注入。每个视图独立管理自己的 API 调用和表单状态。Proposal 确认操作内嵌聊天消息流中。

**Tech Stack:** Vue 3 (Composition API + `<script setup>`), TypeScript, Vite, 纯 CSS（无 UI 组件库）

---

## 文件结构总览

### 新增文件 (21 个组件)

```
frontend/src/composables/useAppState.ts        — 共享状态管理
frontend/src/components/AppSidebar.vue          — 左侧图标导航
frontend/src/components/ContextPanel.vue        — 右侧面板容器
frontend/src/components/TodoList.vue            — 待办列表
frontend/src/components/GoogleStatusBadge.vue   — Google 状态徽章
frontend/src/components/QuickActions.vue        — 快捷操作按钮
frontend/src/components/chat/ChatView.vue       — 聊天主视图
frontend/src/components/chat/ChatMessage.vue    — 消息气泡
frontend/src/components/chat/ProposalCard.vue   — 确认卡片
frontend/src/components/chat/ChatInput.vue      — 输入区
frontend/src/components/gmail/GmailView.vue     — Gmail 工作台
frontend/src/components/gmail/GmailSearch.vue   — 搜索 + 结果
frontend/src/components/gmail/GmailDetail.vue   — 邮件详情
frontend/src/components/gmail/EmailDraftForm.vue — 草稿表单
frontend/src/components/calendar/CalendarView.vue     — Calendar 工作台
frontend/src/components/calendar/EventList.vue         — 日程列表
frontend/src/components/calendar/FreebusyPanel.vue     — 忙闲面板
frontend/src/components/calendar/CalendarDraftForm.vue  — 日程草稿表单
frontend/src/components/settings/SettingsView.vue      — 设置页
frontend/src/components/settings/ProfileSettings.vue   — 个人设置
frontend/src/components/settings/SignatureManager.vue  — 署名管理
frontend/src/components/settings/GoogleConnection.vue  — Google 连接
```

### 修改文件 (3 个)

```
frontend/src/App.vue       — 重写为三栏布局壳
frontend/src/styles.css    — 完全替换为新设计系统
frontend/index.html        — 更新标题
```

### 不变文件

```
frontend/src/api/*.ts      — 所有 API 客户端不变
frontend/src/main.ts       — Vue 入口不变
frontend/vite.config.ts    — 构建配置不变
frontend/tsconfig.json     — TS 配置不变
frontend/package.json      — 依赖不变
```

---

## 任务列表

### Task 1: CSS 设计系统

**Files:**
- Overwrite: `frontend/src/styles.css`

- [ ] **Step 1: 写入新的 CSS 设计系统**

在 `frontend/src/styles.css` 中写入完整的新样式文件：

```css
/* ========================================
   Mailflow Agent — 设计系统
   专业蓝灰风格，基于 8px 网格
   ======================================== */

/* --- CSS 变量 --- */
:root {
  --color-sidebar: #1e293b;
  --color-sidebar-text: #64748b;
  --color-sidebar-active: rgba(255, 255, 255, 0.1);
  --color-primary: #3b82f6;
  --color-primary-hover: #2563eb;
  --color-bg: #ffffff;
  --color-panel: #f8fafc;
  --color-border: #e2e8f0;
  --color-heading: #0f172a;
  --color-body: #334155;
  --color-muted: #475569;
  --color-weak: #94a3b8;
  --color-success: #059669;
  --color-success-bg: #ecfdf5;
  --color-success-border: #a7f3d0;
  --color-warning: #92400e;
  --color-warning-bg: #fef3c7;
  --color-error: #991b1b;
  --color-error-bg: #fef2f2;
  --color-error-border: #fecaca;
  --color-email-bg: #eff6ff;
  --color-email-border: #bfdbfe;
  --color-email-accent: #3b82f6;
  --color-calendar-bg: #ecfdf5;
  --color-calendar-border: #a7f3d0;
  --color-calendar-btn: #059669;
  --radius-sm: 5px;
  --radius-md: 7px;
  --radius-lg: 10px;
  --radius-pill: 999px;
  --font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
}

/* --- Reset --- */
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: var(--font-family);
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-body);
  background: var(--color-bg);
  -webkit-font-smoothing: antialiased;
}

button {
  font: inherit;
  cursor: pointer;
}

button:disabled {
  cursor: default;
  opacity: 0.55;
}

input,
textarea {
  font: inherit;
  color: var(--color-body);
}

/* --- App Shell — 三栏布局 --- */
.app-shell {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) 240px;
  height: 100vh;
  overflow: hidden;
}

/* --- 左侧图标导航栏 --- */
.icon-sidebar {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  background: var(--color-sidebar);
  gap: 4px;
}

.icon-sidebar-brand {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 16px;
}

.icon-sidebar-item {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-sidebar-text);
  font-size: 16px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.icon-sidebar-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #cbd5e1;
}

.icon-sidebar-item.active {
  background: var(--color-sidebar-active);
  color: #fff;
}

.icon-sidebar-spacer {
  flex: 1;
}

/* --- 主内容区 --- */
.main-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--color-bg);
}

.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
  flex-shrink: 0;
}

.view-header h1 {
  font-size: 15px;
  font-weight: 650;
  color: var(--color-heading);
}

.view-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

/* --- 右侧上下文面板 --- */
.context-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  background: var(--color-panel);
  border-left: 1px solid var(--color-border);
  overflow-y: auto;
}

.panel-section {
  padding: 14px 14px;
}

.panel-section + .panel-section {
  border-top: 1px solid var(--color-border);
}

.panel-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--color-heading);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-badge {
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  background: var(--color-border);
  color: var(--color-sidebar-text);
  font-size: 9px;
  font-weight: 600;
}

/* --- 聊天视图 --- */
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 消息气泡 */
.chat-bubble {
  max-width: 520px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.chat-bubble.user {
  align-self: flex-end;
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: 3px;
}

.chat-bubble.assistant {
  align-self: flex-start;
  background: var(--color-panel);
  border: 1px solid var(--color-border);
  color: var(--color-body);
  border-bottom-left-radius: 3px;
}

.chat-bubble.system {
  align-self: center;
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  background: var(--color-panel);
  color: var(--color-weak);
  font-size: 11px;
  max-width: none;
}

.chat-bubble.system.warning {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.chat-bubble.system.error {
  background: var(--color-error-bg);
  color: var(--color-error);
}

.chat-bubble.system.success {
  background: var(--color-success-bg);
  color: var(--color-success);
}

/* 时间分隔 */
.time-divider {
  text-align: center;
  padding: 8px;
}

.time-divider span {
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  background: var(--color-panel);
  color: var(--color-weak);
  font-size: 10px;
}

/* --- Proposal 卡片 --- */
.proposal-card {
  border-radius: var(--radius-lg);
  overflow: hidden;
  font-size: 12px;
  align-self: stretch;
  max-width: 520px;
}

.proposal-card.email {
  border: 1px solid var(--color-email-border);
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.06);
}

.proposal-card.calendar {
  border: 1px solid var(--color-calendar-border);
  box-shadow: 0 1px 3px rgba(16, 185, 129, 0.06);
}

.proposal-header {
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.proposal-card.email .proposal-header {
  background: var(--color-email-bg);
  border-bottom: 1px solid var(--color-email-border);
}

.proposal-card.calendar .proposal-header {
  background: var(--color-calendar-bg);
  border-bottom: 1px solid var(--color-calendar-border);
}

.proposal-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  color: var(--color-heading);
}

.proposal-status {
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  font-size: 9px;
  font-weight: 600;
  white-space: nowrap;
}

.proposal-status.awaiting {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.proposal-status.approved {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.proposal-status.draft {
  background: #dbeafe;
  color: #1e40af;
}

.proposal-body {
  padding: 10px 12px;
  background: #fff;
  display: grid;
  gap: 4px;
}

.proposal-field {
  display: flex;
  gap: 8px;
}

.proposal-field-label {
  color: var(--color-weak);
  flex-shrink: 0;
}

.proposal-field-value {
  color: var(--color-body);
  overflow-wrap: anywhere;
}

.proposal-preview {
  margin-top: 4px;
  padding: 8px;
  border-radius: var(--radius-md);
  background: var(--color-panel);
  color: var(--color-muted);
  max-height: 60px;
  overflow: hidden;
  font-size: 11px;
}

.proposal-card.email .proposal-preview {
  border-left: 2px solid var(--color-email-accent);
}

.proposal-conflict {
  margin-top: 4px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: var(--color-error-bg);
  border: 1px solid var(--color-error-border);
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 11px;
}

.proposal-conflict-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.proposal-conflict-text {
  color: var(--color-error);
}

.proposal-conflict-text strong {
  font-weight: 650;
}

.proposal-actions {
  padding: 8px 12px;
  border-top: 1px solid var(--color-border);
  display: flex;
  gap: 6px;
  background: var(--color-panel);
  align-items: center;
}

.proposal-actions .btn-primary {
  padding: 5px 14px;
  border: 0;
  border-radius: var(--radius-sm);
  color: #fff;
  font-weight: 600;
  font-size: 10px;
}

.proposal-card.email .btn-primary {
  background: #2563eb;
}

.proposal-card.calendar .btn-primary {
  background: var(--color-calendar-btn);
}

.proposal-actions .btn-secondary {
  padding: 5px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: #fff;
  color: var(--color-muted);
  font-size: 10px;
}

.proposal-fingerprint {
  margin-left: auto;
  color: var(--color-weak);
  font-size: 9px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

/* --- 输入区 --- */
.chat-input-area {
  padding: 12px 20px 16px;
  border-top: 1px solid var(--color-border);
  flex-shrink: 0;
}

.chat-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-panel);
}

.chat-input-row input {
  flex: 1;
  border: 0;
  background: transparent;
  padding: 8px 4px;
  outline: none;
  font-size: 13px;
  color: var(--color-body);
}

.chat-input-row input::placeholder {
  color: var(--color-weak);
}

.chat-input-row .btn-send {
  padding: 8px 18px;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-weight: 600;
  font-size: 12px;
}

.chat-input-hint {
  text-align: center;
  margin-top: 6px;
  font-size: 10px;
  color: var(--color-weak);
}

/* --- 通用组件 --- */

/* 搜索框 */
.search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.search-bar input {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-panel);
  font-size: 12px;
}

/* 待办列表项 */
.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #fff;
  margin-bottom: 6px;
}

.todo-item-icon {
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 1px;
}

.todo-item-info {
  flex: 1;
  min-width: 0;
}

.todo-item-title {
  font-weight: 600;
  color: var(--color-heading);
  font-size: 11px;
  margin-bottom: 1px;
}

.todo-item-desc {
  color: var(--color-weak);
  font-size: 10px;
  margin-bottom: 3px;
}

.todo-item-status {
  display: inline-block;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  font-size: 8px;
  font-weight: 600;
}

.todo-item-status.awaiting {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.todo-item-status.draft {
  background: #dbeafe;
  color: #1e40af;
}

/* Google 状态徽章 */
.google-badge {
  padding: 8px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.google-badge.connected {
  background: var(--color-success-bg);
  border: 1px solid var(--color-success-border);
  color: #065f46;
}

.google-badge.disconnected {
  background: var(--color-panel);
  border: 1px solid var(--color-border);
  color: var(--color-weak);
}

.google-badge-check {
  font-size: 12px;
  flex-shrink: 0;
}

/* 快捷操作按钮 */
.quick-action-btn {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #fff;
  color: var(--color-muted);
  font-size: 11px;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.quick-action-btn:hover {
  background: var(--color-panel);
}

/* --- 表单通用样式 --- */
.form-group {
  display: grid;
  gap: 4px;
}

.form-label {
  color: var(--color-muted);
  font-size: 11px;
}

.form-input {
  width: 100%;
  padding: 7px 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 12px;
  background: #fff;
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.form-row {
  display: grid;
  gap: 8px;
}

.form-row.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.form-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-muted);
}

.form-checkbox input[type="checkbox"] {
  width: auto;
}

.btn {
  padding: 8px 16px;
  border: 0;
  border-radius: var(--radius-md);
  font-weight: 600;
  font-size: 12px;
  color: #fff;
  background: var(--color-primary);
}

.btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.btn-secondary {
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-muted);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-panel);
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* --- 结果列表 --- */
.result-list {
  display: grid;
  gap: 8px;
}

.result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #fff;
}

.result-item-meta {
  font-size: 11px;
  color: var(--color-weak);
}

/* --- Gmail / Calendar 视图布局 --- */
.workspace-view {
  padding: 20px;
}

/* --- 详情面板 --- */
.detail-panel {
  padding: 12px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #fff;
  margin-top: 12px;
}

.detail-panel h3 {
  font-size: 14px;
  margin-bottom: 6px;
  color: var(--color-heading);
}

.detail-panel pre {
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: inherit;
  font-size: 12px;
  margin-top: 8px;
}

/* --- 设置页子标签 --- */
.settings-tabs {
  display: flex;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-panel);
  flex-shrink: 0;
}

.settings-tab {
  padding: 10px 16px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--color-sidebar-text);
  font-size: 12px;
  cursor: pointer;
}

.settings-tab.active {
  color: var(--color-heading);
  font-weight: 600;
  border-bottom-color: var(--color-primary);
}

.settings-content {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

/* --- 内联错误/提示 --- */
.inline-error {
  color: var(--color-error);
  font-size: 11px;
  margin: 4px 0;
}

.inline-notice {
  padding: 6px 10px;
  border-radius: var(--radius-md);
  background: var(--color-success-bg);
  color: var(--color-success);
  font-size: 11px;
  margin: 4px 0;
}

/* --- 署名列表 --- */
.signature-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #fff;
  margin-bottom: 8px;
}

.signature-item-body {
  flex: 1;
}

.signature-item-label {
  font-weight: 600;
  color: var(--color-heading);
  font-size: 12px;
}

.signature-item-default {
  color: var(--color-success);
  font-size: 10px;
  margin-left: 6px;
}

.signature-item-content {
  color: var(--color-muted);
  font-size: 11px;
  margin-top: 2px;
  white-space: pre-wrap;
}

/* --- 响应式 --- */
@media (max-width: 900px) {
  .app-shell {
    grid-template-columns: 52px minmax(0, 1fr);
  }
  .context-panel {
    display: none;
  }
}

@media (max-width: 640px) {
  .app-shell {
    grid-template-columns: 1fr;
  }
  .icon-sidebar {
    display: none;
  }
}
```

- [ ] **Step 2: 验证构建**

```bash
Set-Location frontend
npm run build
```

预期：构建成功（虽然 App.vue 尚未适配新 CSS，但不影响 CSS 文件替换）

- [ ] **Step 3: 提交**

```bash
git add frontend/src/styles.css
git commit -m "feat: replace CSS with new design system"
```

---

### Task 2: 共享状态 composable

**Files:**
- Create: `frontend/src/composables/useAppState.ts`

- [ ] **Step 1: 创建 composable 文件**

```ts
// 共享应用状态。通过 provide/inject 在组件树中传递，
// 避免每个视图独立请求相同数据。
import { reactive, computed } from "vue";

export interface TodoItem {
  id: string;
  icon: string;
  title: string;
  desc: string;
  status: "awaiting" | "draft" | "approved" | "executed";
}

export function createAppState() {
  const state = reactive({
    // Google 连接
    googleConnected: false,
    googleEmail: "" as string | null,
    googleNeedsReconnect: false,
    googleMessage: "" as string | null,

    // 用户设置
    profile: null as Record<string, unknown> | null,
    signatures: [] as Array<Record<string, unknown>>,

    // 待办
    todos: [] as TodoItem[],
    todoCount: computed(() => state.todos.filter((t) => t.status === "awaiting").length),

    // 通知
    notice: "" as string | null,

    // 当前活跃视图
    activeView: "chat" as string,
  });

  function setNotice(msg: string | null) {
    state.notice = msg;
    if (msg) {
      setTimeout(() => {
        if (state.notice === msg) state.notice = null;
      }, 5000);
    }
  }

  return { state, setNotice };
}

export type AppState = ReturnType<typeof createAppState>;
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
Set-Location frontend
npx vue-tsc --noEmit src/composables/useAppState.ts
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/composables/useAppState.ts
git commit -m "feat: add shared app state composable"
```

---

### Task 3: AppSidebar（左侧图标导航）

**Files:**
- Create: `frontend/src/components/AppSidebar.vue`

- [ ] **Step 1: 创建组件**

```vue
<script setup lang="ts">
// 左侧 52px 图标导航栏。4 个导航项 + 品牌标识 M。
// 点击切换 activeView，通过 inject 获取共享状态。
import { inject } from "vue";
import type { AppState } from "../composables/useAppState";

const appState = inject<AppState>("appState")!;

const navItems = [
  { id: "chat", icon: "💬", label: "聊天" },
  { id: "gmail", icon: "📧", label: "Gmail" },
  { id: "calendar", icon: "📅", label: "Calendar" },
  { id: "settings", icon: "⚙️", label: "设置" },
];

function switchView(viewId: string) {
  appState.state.activeView = viewId;
}
</script>

<template>
  <nav class="icon-sidebar" aria-label="主导航">
    <div class="icon-sidebar-brand" title="Mailflow Agent">M</div>
    <button
      v-for="item in navItems"
      :key="item.id"
      class="icon-sidebar-item"
      :class="{ active: appState.state.activeView === item.id }"
      :title="item.label"
      :aria-label="item.label"
      @click="switchView(item.id)"
    >
      {{ item.icon }}
    </button>
    <div class="icon-sidebar-spacer"></div>
  </nav>
</template>
```

- [ ] **Step 2: 验证构建**

```bash
Set-Location frontend
npm run build
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/AppSidebar.vue
git commit -m "feat: add AppSidebar icon navigation component"
```

---

### Task 4: GoogleStatusBadge + QuickActions + TodoList

**Files:**
- Create: `frontend/src/components/GoogleStatusBadge.vue`
- Create: `frontend/src/components/QuickActions.vue`
- Create: `frontend/src/components/TodoList.vue`

- [ ] **Step 1: 创建 GoogleStatusBadge**

```vue
<script setup lang="ts">
// Google 账号连接状态徽章。已连接时展示绿色卡片 + 邮箱，
// 未连接时展示灰色提示。
import { inject } from "vue";
import type { AppState } from "../composables/useAppState";

const appState = inject<AppState>("appState")!;
</script>

<template>
  <div
    class="google-badge"
    :class="appState.state.googleConnected ? 'connected' : 'disconnected'"
  >
    <span v-if="appState.state.googleConnected" class="google-badge-check">✓</span>
    <span v-else class="google-badge-check">—</span>
    <div>
      <div v-if="appState.state.googleConnected" style="font-weight:600;font-size:11px">
        {{ appState.state.googleEmail }}
      </div>
      <div v-else style="color:var(--color-weak);font-size:11px">
        {{ appState.state.googleMessage || "未连接 Google" }}
      </div>
      <div
        v-if="appState.state.googleConnected"
        style="color:var(--color-success);font-size:9px"
      >
        Gmail · Calendar 已授权
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 创建 QuickActions**

```vue
<script setup lang="ts">
// 右侧面板快捷操作按钮：上传文件、导出 Markdown。
// 当前上传文件为后续范围，按钮暂时仅展示，点击导出触发 Emit。
defineEmits<{
  exportMarkdown: [];
}>();
</script>

<template>
  <button class="quick-action-btn">
    <span>📎</span> 上传文件
  </button>
  <button class="quick-action-btn" @click="$emit('exportMarkdown')">
    <span>📥</span> 导出 Markdown
  </button>
</template>
```

- [ ] **Step 3: 创建 TodoList**

```vue
<script setup lang="ts">
// 待办摘要列表。从 AppState 读取 todos，展示人类可读状态。
import { inject } from "vue";
import type { AppState } from "../composables/useAppState";

const appState = inject<AppState>("appState")!;
</script>

<template>
  <div class="panel-section">
    <div class="panel-title">
      待办事项
      <span v-if="appState.state.todoCount" class="panel-badge">
        {{ appState.state.todoCount }}
      </span>
    </div>
    <div
      v-for="todo in appState.state.todos"
      :key="todo.id"
      class="todo-item"
    >
      <span class="todo-item-icon">{{ todo.icon }}</span>
      <div class="todo-item-info">
        <div class="todo-item-title">{{ todo.title }}</div>
        <div class="todo-item-desc">{{ todo.desc }}</div>
        <span class="todo-item-status" :class="todo.status">
          {{ todo.status === "awaiting" ? "等待确认" : "草稿中" }}
        </span>
      </div>
    </div>
    <div
      v-if="!appState.state.todos.length"
      style="color:var(--color-weak);font-size:11px;padding:4px 0"
    >
      暂无待办事项
    </div>
  </div>
</template>
```

- [ ] **Step 4: 验证构建**

```bash
Set-Location frontend
npm run build
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/GoogleStatusBadge.vue frontend/src/components/QuickActions.vue frontend/src/components/TodoList.vue
git commit -m "feat: add panel sub-components (GoogleStatus, QuickActions, TodoList)"
```

---

### Task 5: ContextPanel（右侧面板容器）

**Files:**
- Create: `frontend/src/components/ContextPanel.vue`

- [ ] **Step 1: 创建组件**

```vue
<script setup lang="ts">
// 右侧 240px 上下文面板。始终可见，从上到下：待办列表 → Google 状态 → 快捷操作。
// 导出 Markdown 的 Emit 传递给父组件处理。
import TodoList from "./TodoList.vue";
import GoogleStatusBadge from "./GoogleStatusBadge.vue";
import QuickActions from "./QuickActions.vue";

defineEmits<{
  exportMarkdown: [];
}>();
</script>

<template>
  <aside class="context-panel" aria-label="上下文面板">
    <TodoList />
    <div class="panel-section">
      <div class="panel-title">Google 账号</div>
      <GoogleStatusBadge />
    </div>
    <div class="panel-section">
      <div class="panel-title">快捷操作</div>
      <QuickActions @export-markdown="$emit('exportMarkdown')" />
    </div>
  </aside>
</template>
```

- [ ] **Step 2: 验证构建**

```bash
Set-Location frontend
npm run build
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/ContextPanel.vue
git commit -m "feat: add ContextPanel right sidebar container"
```

---

### Task 6: ChatMessage + ChatInput + ProposalCard

**Files:**
- Create: `frontend/src/components/chat/ChatMessage.vue`
- Create: `frontend/src/components/chat/ChatInput.vue`
- Create: `frontend/src/components/chat/ProposalCard.vue`

- [ ] **Step 1: 创建 ChatMessage（消息气泡）**

```vue
<script setup lang="ts">
// 单条消息气泡。支持 user / assistant / system 三种角色。
// system 消息支持 warning / error / success 变体。
// 消息中的 Proposal 卡片由父组件 ChatView 在渲染时控制。
defineProps<{
  role: "user" | "assistant" | "system";
  content: string;
  systemType?: "warning" | "error" | "success";
}>();
</script>

<template>
  <div
    class="chat-bubble"
    :class="[role, systemType && `system ${systemType}`]"
  >
    {{ content }}
  </div>
</template>
```

- [ ] **Step 2: 创建 ProposalCard**

```vue
<script setup lang="ts">
// 内嵌在聊天流中的 Proposal 确认卡片。
// 邮件卡片蓝色系，日程卡片绿色系。
// 按钮点击向上 Emit，由 ChatView 处理具体逻辑。
import type { ProposalItem } from "../../api/workflow";

const props = defineProps<{
  proposal: ProposalItem;
}>();

defineEmits<{
  approve: [];
  reject: [];
  revise: [];
  defer: [];
}>();

function isEmail(): boolean {
  return props.proposal.action_type === "send_email";
}

function title(): string {
  const p = props.proposal.payload as Record<string, unknown>;
  return isEmail()
    ? (typeof p.subject === "string" ? p.subject : "未命名邮件")
    : (typeof p.title === "string" ? p.title : "未命名日程");
}

function statusLabel(): string {
  if (props.proposal.status === "awaiting_confirmation") return "等待确认";
  if (props.proposal.status === "approved") return "已确认";
  return "草稿中";
}

function statusClass(): string {
  if (props.proposal.status === "awaiting_confirmation") return "awaiting";
  if (props.proposal.status === "approved") return "approved";
  return "draft";
}

function primaryActionLabel(): string {
  if (isEmail()) return "确认发送";
  return "创建日程";
}

function fieldValue(key: string): string {
  const v = (props.proposal.payload as Record<string, unknown>)[key];
  if (typeof v === "string") return v;
  if (typeof v === "number") return String(v);
  if (typeof v === "boolean") return v ? "是" : "否";
  return "";
}

function fingerprintShort(): string {
  return props.proposal.fingerprint.slice(0, 12);
}

function hasConflict(): boolean {
  if (isEmail()) return false;
  return !!(props.proposal.payload as Record<string, unknown>).conflict_override;
}

function formatAddressList(key: string): string {
  const v = (props.proposal.payload as Record<string, unknown>)[key];
  if (!Array.isArray(v)) return "";
  return v
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        return (item as Record<string, unknown>).email || "";
      }
      return "";
    })
    .filter(Boolean)
    .join(", ");
}
</script>

<template>
  <div class="proposal-card" :class="isEmail() ? 'email' : 'calendar'">
    <div class="proposal-header">
      <div class="proposal-title">
        <span>{{ isEmail() ? "📧" : "📅" }}</span>
        {{ title() }}
      </div>
      <span class="proposal-status" :class="statusClass()">
        {{ statusLabel() }}
      </span>
    </div>

    <div class="proposal-body">
      <!-- 邮件字段 -->
      <template v-if="isEmail()">
        <div class="proposal-field">
          <span class="proposal-field-label">发件</span>
          <span class="proposal-field-value">{{ fieldValue("sender_email") }}</span>
        </div>
        <div class="proposal-field">
          <span class="proposal-field-label">收件</span>
          <span class="proposal-field-value">{{ formatAddressList("to") }}</span>
        </div>
        <div class="proposal-field">
          <span class="proposal-field-label">主题</span>
          <span class="proposal-field-value">{{ fieldValue("subject") }}</span>
        </div>
        <div class="proposal-preview">
          {{ fieldValue("body") }}
        </div>
      </template>

      <!-- 日程字段 -->
      <template v-else>
        <div class="proposal-field">
          <span class="proposal-field-label">时间</span>
          <span class="proposal-field-value">
            {{ fieldValue("start_time") }} - {{ fieldValue("end_time") || fieldValue("duration_minutes") + " 分钟" }}
          </span>
        </div>
        <div class="proposal-field">
          <span class="proposal-field-label">时区</span>
          <span class="proposal-field-value">{{ fieldValue("timezone") }}</span>
        </div>
        <div class="proposal-field">
          <span class="proposal-field-label">参会</span>
          <span class="proposal-field-value">{{ formatAddressList("attendees") }}</span>
        </div>
        <div v-if="fieldValue('location')" class="proposal-field">
          <span class="proposal-field-label">地点</span>
          <span class="proposal-field-value">{{ fieldValue("location") }}</span>
        </div>
        <div v-if="hasConflict()" class="proposal-conflict">
          <span class="proposal-conflict-icon">⚠️</span>
          <div class="proposal-conflict-text">
            该时段存在日程冲突
          </div>
        </div>
      </template>
    </div>

    <div class="proposal-actions">
      <button
        class="btn-primary"
        :disabled="proposal.status !== 'awaiting_confirmation'"
        @click="$emit('approve')"
      >
        {{ primaryActionLabel() }}
      </button>
      <button class="btn-secondary" @click="$emit('revise')">修改</button>
      <button class="btn-secondary" @click="$emit('defer')">暂缓</button>
      <span class="proposal-fingerprint">
        v{{ proposal.version }} · {{ fingerprintShort() }}
      </span>
    </div>
  </div>
</template>
```

- [ ] **Step 3: 创建 ChatInput**

```vue
<script setup lang="ts">
// 聊天输入区。管理输入文本，发送时 Emit 消息内容。
// 附件按钮当前仅占位，后续阶段接入文件上传。
import { ref } from "vue";

const input = ref("");

const emit = defineEmits<{
  send: [message: string];
}>();

function handleSubmit() {
  const msg = input.value.trim();
  if (!msg) return;
  emit("send", msg);
  input.value = "";
}
</script>

<template>
  <div class="chat-input-area">
    <form class="chat-input-row" @submit.prevent="handleSubmit">
      <button type="button" style="background:none;border:0;color:var(--color-weak);font-size:14px;padding:4px" title="上传文件">
        📎
      </button>
      <input
        v-model="input"
        type="text"
        placeholder="描述你要做什么，例如：帮李明写邮件..."
        autofocus
      />
      <button
        type="submit"
        class="btn-send"
        :disabled="!input.trim()"
      >
        发送
      </button>
    </form>
    <div class="chat-input-hint">Mailflow Agent · 你的邮件和日程助理</div>
  </div>
</template>
```

- [ ] **Step 4: 验证构建**

```bash
Set-Location frontend
npm run build
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/chat/ChatMessage.vue frontend/src/components/chat/ChatInput.vue frontend/src/components/chat/ProposalCard.vue
git commit -m "feat: add chat sub-components (Message, Input, ProposalCard)"
```

---

### Task 7: ChatView（聊天主视图）

**Files:**
- Create: `frontend/src/components/chat/ChatView.vue`

- [ ] **Step 1: 创建 ChatView**

```vue
<script setup lang="ts">
// 聊天主视图。管理消息列表、SSE 流式对话、Proposal 确认交互。
// 保持与现有 backend/app/api/assistant_graph.py 的 SSE 协议兼容。
import { ref, inject, nextTick } from "vue";
import type { AppState } from "../../composables/useAppState";
import {
  streamAssistantTurn,
  type AssistantTurnResponse,
  fetchAssistantState,
} from "../../api/assistant";
import { fetchOpenWorkItems, fetchPendingProposals, authorizeProposal, executeProposal, resolveSendConfirmation, type ProposalItem, type WorkItemSummary } from "../../api/workflow";
import ChatMessage from "./ChatMessage.vue";
import ProposalCard from "./ProposalCard.vue";
import ChatInput from "./ChatInput.vue";

const appState = inject<AppState>("appState")!;

interface ChatItem {
  id: string;
  type: "message" | "proposal";
  role?: "user" | "assistant" | "system";
  content?: string;
  systemType?: "warning" | "error" | "success";
  proposal?: ProposalItem;
}

const messages = ref<ChatItem[]>([
  {
    id: "welcome",
    type: "message",
    role: "assistant",
    content: "我可以帮你把邮件、日程和待确认事项串起来。你可以直接描述要做什么。",
  },
]);

const threadId = ref(loadThreadId());
const isStreaming = ref(false);
const pendingProposals = ref<ProposalItem[]>([]);

function loadThreadId(): string {
  const existing = localStorage.getItem("mailflow_assistant_thread_id");
  if (existing) return existing;
  const created = `thread_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
  localStorage.setItem("mailflow_assistant_thread_id", created);
  return created;
}

// 添加消息到列表
function addMessage(role: "user" | "assistant" | "system", content: string, systemType?: "warning" | "error" | "success") {
  messages.value.push({
    id: `msg_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
    type: "message",
    role,
    content,
    systemType,
  });
}

// 刷新待办列表
async function refreshTodos() {
  if (!appState.state.googleConnected) return;
  try {
    const [items, proposals] = await Promise.all([
      fetchOpenWorkItems(),
      fetchPendingProposals(),
    ]);
    pendingProposals.value = proposals;
    appState.state.todos = items.map((w: WorkItemSummary) => ({
      id: w.id,
      icon: w.work_item_type === "email_draft" ? "📧" : "📅",
      title: w.title,
      desc: w.work_item_type === "email_draft" ? "邮件草稿" : "日程草稿",
      status: w.status === "awaiting_confirmation" ? "awaiting" : "draft",
    }));
  } catch { /* 静默处理 */ }
}

// 发送消息
async function handleSend(message: string) {
  addMessage("user", message);
  isStreaming.value = true;

  try {
    const result = await streamAssistantTurn(
      { thread_id: threadId.value, message },
      () => {},
    );
    addMessage("assistant", result.response);

    // 刷新提案列表
    await refreshTodos();

    // 如果回复中包含可确认的 Proposal，以内嵌卡片展示
    if (pendingProposals.value.length) {
      for (const p of pendingProposals.value.slice(0, 3)) {
        messages.value.push({
          id: `proposal_${p.id}`,
          type: "proposal",
          proposal: p,
        });
      }
    }

    // 聊天式确认
    await handleChatSideEffects(message);
  } catch (e) {
    addMessage("system", e instanceof Error ? e.message : "聊天请求失败", "error");
  } finally {
    isStreaming.value = false;
    await nextTick();
    scrollToBottom();
  }
}

async function handleChatSideEffects(message: string) {
  if (!message.includes("确认发送")) return;
  try {
    const result = await resolveSendConfirmation();
    addMessage("system", result.message);
    if (result.status === "unique" && result.candidates[0]) {
      await authorizeProposal(result.candidates[0], "approved");
      addMessage("system", `已确认 Proposal，执行前保留幂等保护。`, "success");
      await refreshTodos();
    }
  } catch (e) {
    addMessage("system", e instanceof Error ? e.message : "确认失败", "error");
  }
}

// Proposal 卡片操作
async function handleApprove(proposal: ProposalItem) {
  try {
    await authorizeProposal(proposal, "approved");
    appState.setNotice?.("Proposal 已确认");
    await refreshTodos();
  } catch (e) {
    addMessage("system", e instanceof Error ? e.message : "确认失败", "error");
  }
}

function handleRevise(proposal: ProposalItem) {
  appState.setNotice?.("草稿已带回表单，请到对应工作台修改");
}

function handleDefer(proposal: ProposalItem) {
  appState.setNotice?.(`已暂缓 ${proposal.action_type}`);
}

// 从 checkpoint 恢复聊天历史
async function restoreChat() {
  try {
    const response = await fetchAssistantState(threadId.value);
    const msgs = Array.isArray(response.state.messages) ? response.state.messages : [];
    const restored = msgs
      .map((item: unknown, index: number) => {
        const record = item as Record<string, unknown>;
        const role = record.role === "user" ? "user" : "assistant";
        const content = typeof record.content === "string" ? record.content : "";
        return { id: `restore_${index}`, type: "message" as const, role, content };
      })
      .filter((item) => item.content);
    if (restored.length) {
      messages.value = restored;
    }
  } catch { /* 首次打开无 checkpoint 是正常情况 */ }
}

function scrollToBottom() {
  const el = document.querySelector(".chat-messages");
  if (el) el.scrollTop = el.scrollHeight;
}

// 初始化
restoreChat();
refreshTodos();
</script>

<template>
  <div class="chat-view">
    <div class="view-header">
      <h1>💬 聊天</h1>
      <span style="font-size:10px;color:var(--color-weak)">{{ threadId }}</span>
    </div>

    <div class="chat-messages" ref="messageList">
      <template v-for="item in messages" :key="item.id">
        <ChatMessage
          v-if="item.type === 'message'"
          :role="item.role!"
          :content="item.content!"
          :system-type="item.systemType"
        />
        <ProposalCard
          v-else-if="item.type === 'proposal' && item.proposal"
          :proposal="item.proposal"
          @approve="handleApprove(item.proposal!)"
          @revise="handleRevise(item.proposal!)"
          @defer="handleDefer(item.proposal!)"
        />
      </template>
    </div>

    <ChatInput @send="handleSend" :disabled="isStreaming" />
  </div>
</template>
```

- [ ] **Step 2: 验证构建**

```bash
Set-Location frontend
npm run build
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/chat/ChatView.vue
git commit -m "feat: add ChatView with SSE streaming and proposal cards"
```

---

### Task 8: Gmail 组件（GmailSearch + GmailDetail + EmailDraftForm + GmailView）

**Files:**
- Create: `frontend/src/components/gmail/GmailSearch.vue`
- Create: `frontend/src/components/gmail/GmailDetail.vue`
- Create: `frontend/src/components/gmail/EmailDraftForm.vue`
- Create: `frontend/src/components/gmail/GmailView.vue`

- [ ] **Step 1: 创建 GmailSearch**

```vue
<script setup lang="ts">
// Gmail 搜索栏 + 结果列表。用户输入查询后调用后端搜索 API，
// 搜索结果展示为列表，支持点击读取详情和线程。
import { ref } from "vue";
import { searchGmail, readGmailMessage, readGmailThread, type GmailMessageSummary, type GmailMessageDetail, type GmailThreadDetail } from "../../api/gmail";

const query = ref("newer_than:7d");
const maxResults = ref(10);
const isSearching = ref(false);
const results = ref<GmailMessageSummary[]>([]);
const error = ref<string | null>(null);

const emit = defineEmits<{
  select: [detail: GmailMessageDetail];
  selectThread: [thread: GmailThreadDetail];
}>();

async function handleSearch() {
  isSearching.value = true;
  error.value = null;
  try {
    const resp = await searchGmail({ query: query.value, max_results: maxResults.value });
    results.value = resp.messages;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "搜索失败";
  } finally {
    isSearching.value = false;
  }
}

async function handleReadMessage(id: string) {
  try {
    const detail = await readGmailMessage(id);
    emit("select", detail);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "读取失败";
  }
}

async function handleReadThread(id: string) {
  try {
    const thread = await readGmailThread(id);
    emit("selectThread", thread);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "读取线程失败";
  }
}
</script>

<template>
  <div>
    <div class="search-bar">
      <input v-model="query" placeholder="newer_than:7d from:someone@example.com" :disabled="isSearching" />
      <input v-model.number="maxResults" type="number" min="1" max="25" style="width:70px" :disabled="isSearching" />
      <button class="btn" :disabled="isSearching" @click="handleSearch">
        {{ isSearching ? "搜索中" : "搜索" }}
      </button>
    </div>
    <p v-if="error" class="inline-error">{{ error }}</p>
    <div v-if="results.length" class="result-list">
      <div v-for="item in results" :key="item.id" class="result-item">
        <div>
          <strong style="font-size:11px">{{ item.id }}</strong>
          <div class="result-item-meta">Thread {{ item.thread_id }}</div>
        </div>
        <div class="action-row">
          <button class="btn-secondary" style="font-size:10px;padding:4px 10px" @click="handleReadMessage(item.id)">读取</button>
          <button class="btn-secondary" style="font-size:10px;padding:4px 10px" @click="handleReadThread(item.thread_id)">线程</button>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 创建 GmailDetail**

```vue
<script setup lang="ts">
// 单封邮件详情展示。
import type { GmailMessageDetail } from "../../api/gmail";

defineProps<{
  detail: GmailMessageDetail | null;
}>();
</script>

<template>
  <div v-if="detail" class="detail-panel">
    <h3>{{ detail.subject || "无主题" }}</h3>
    <div style="color:var(--color-weak);font-size:11px">发件：{{ detail.from_email }}</div>
    <div style="color:var(--color-weak);font-size:11px">收件：{{ detail.to?.join(", ") }}</div>
    <pre>{{ detail.body?.text }}</pre>
  </div>
</template>
```

- [ ] **Step 3: 创建 EmailDraftForm**

```vue
<script setup lang="ts">
// 新邮件草稿表单 + 回复草稿表单。
// 收件人、主题、正文、署名策略。提交时调用后端 API 创建本地 Artifact。
import { ref, reactive, inject } from "vue";
import type { AppState } from "../../composables/useAppState";
import { prepareNewEmailDraft, type EmailArtifactResponse, type EmailAddress } from "../../api/gmail";

const appState = inject<AppState>("appState")!;

const form = reactive({
  to: "",
  subject: "",
  body: "",
  signature_policy: "no_signature",
});

const isSubmitting = ref(false);
const error = ref<string | null>(null);

const emit = defineEmits<{
  created: [artifact: EmailArtifactResponse];
}>();

function parseAddressList(value: string): EmailAddress[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((email) => ({ email, name: null }));
}

async function handleSubmit() {
  if (!form.to.trim() || !form.subject.trim()) return;
  isSubmitting.value = true;
  error.value = null;
  try {
    const senderEmail = (appState.state.profile?.default_sender_email as string)
      || appState.state.googleEmail
      || "";
    const artifact = await prepareNewEmailDraft({
      thread_id: null,
      sender_email: senderEmail,
      to: parseAddressList(form.to),
      cc: [],
      bcc: [],
      subject: form.subject.trim(),
      body: form.body.trim(),
      signature_policy: form.signature_policy,
    });
    emit("created", artifact);
    form.to = "";
    form.subject = "";
    form.body = "";
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建草稿失败";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <form @submit.prevent="handleSubmit" style="display:grid;gap:10px;margin-top:12px">
    <h3 style="font-size:13px;color:var(--color-heading)">新邮件草稿</h3>
    <div class="form-group">
      <label class="form-label">收件人</label>
      <input class="form-input" v-model="form.to" placeholder="name@example.com" />
    </div>
    <div class="form-group">
      <label class="form-label">主题</label>
      <input class="form-input" v-model="form.subject" />
    </div>
    <div class="form-group">
      <label class="form-label">正文</label>
      <textarea class="form-input form-textarea" v-model="form.body" rows="5" />
    </div>
    <button class="btn" type="submit" :disabled="isSubmitting">
      {{ isSubmitting ? "创建中" : "保存本地草稿" }}
    </button>
    <p v-if="error" class="inline-error">{{ error }}</p>
  </form>
</template>
```

- [ ] **Step 4: 创建 GmailView**

```vue
<script setup lang="ts">
// Gmail 工作台视图。组合搜索、详情、草稿表单三个子组件。
import { ref } from "vue";
import type { GmailMessageDetail, GmailThreadDetail, EmailArtifactResponse } from "../../api/gmail";
import GmailSearch from "./GmailSearch.vue";
import GmailDetail from "./GmailDetail.vue";
import EmailDraftForm from "./EmailDraftForm.vue";

const selectedDetail = ref<GmailMessageDetail | null>(null);
const latestArtifact = ref<EmailArtifactResponse | null>(null);

function handleArtifactCreated(artifact: EmailArtifactResponse) {
  latestArtifact.value = artifact;
}
</script>

<template>
  <div class="chat-view">
    <div class="view-header">
      <h1>📧 Gmail</h1>
    </div>
    <div class="view-body workspace-view">
      <GmailSearch @select="selectedDetail = $event" @select-thread="selectedDetail = $event.messages?.at(-1) ?? null" />
      <GmailDetail :detail="selectedDetail" />
      <EmailDraftForm @created="handleArtifactCreated" />
      <div v-if="latestArtifact" class="inline-notice" style="margin-top:10px">
        Artifact {{ latestArtifact.artifact_id }} 已创建 — {{ (latestArtifact.content as Record<string,unknown>)?.subject }}
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 5: 验证构建**

```bash
Set-Location frontend
npm run build
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/gmail/
git commit -m "feat: add Gmail workspace components"
```

---

### Task 9: Calendar 组件（EventList + FreebusyPanel + CalendarDraftForm + CalendarView）

**Files:**
- Create: `frontend/src/components/calendar/EventList.vue`
- Create: `frontend/src/components/calendar/FreebusyPanel.vue`
- Create: `frontend/src/components/calendar/CalendarDraftForm.vue`
- Create: `frontend/src/components/calendar/CalendarView.vue`

- [ ] **Step 1: 创建 EventList**

```vue
<script setup lang="ts">
import { ref } from "vue";
import { listCalendarEvents, type CalendarEventResponse } from "../../api/calendar";

const props = defineProps<{
  calendarId: string;
  googleConnected: boolean;
}>();

const events = ref<CalendarEventResponse[]>([]);
const isLoading = ref(false);
const error = ref<string | null>(null);

async function handleLoad() {
  isLoading.value = true;
  error.value = null;
  try {
    const resp = await listCalendarEvents({
      calendar_id: props.calendarId,
      time_min: new Date().toISOString(),
      time_max: null,
      max_results: 10,
    });
    events.value = resp.events;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "读取失败";
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
      <h3 style="font-size:13px;color:var(--color-heading)">日程列表</h3>
      <button class="btn-secondary" style="font-size:10px;padding:4px 10px" :disabled="isLoading || !googleConnected" @click="handleLoad">
        {{ isLoading ? "读取中" : "读取" }}
      </button>
    </div>
    <p v-if="error" class="inline-error">{{ error }}</p>
    <div v-if="events.length" class="result-list">
      <div v-for="event in events" :key="event.id" class="result-item">
        <div>
          <strong style="font-size:11px">{{ event.summary || "无标题" }}</strong>
          <div class="result-item-meta">{{ event.start?.date_time }} - {{ event.end?.date_time }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 创建 CalendarView**（含 FreebusyPanel 和 CalendarDraftForm）

```vue
<script setup lang="ts">
// Calendar 工作台视图。组合日程列表、忙闲查询、草稿表单。
import { ref, reactive, inject } from "vue";
import type { AppState } from "../../composables/useAppState";
import { queryCalendarFreebusy, prepareCalendarEventDraft, type CalendarArtifactResponse, type BusySlot } from "../../api/calendar";
import EventList from "./EventList.vue";

const appState = inject<AppState>("appState")!;

const form = reactive({
  calendar_id: "primary",
  title: "",
  start_time: "",
  end_time: "",
  duration_minutes: 60,
  timezone: "Asia/Shanghai",
  attendees: "",
  location: "",
  description: "",
  video_conference: false,
  conflict_override: false,
});

const isFreebusyLoading = ref(false);
const isSubmitting = ref(false);
const busySlots = ref<BusySlot[]>([]);
const conflicts = ref<BusySlot[]>([]);
const error = ref<string | null>(null);
const latestArtifact = ref<CalendarArtifactResponse | null>(null);

async function handleFreebusy() {
  if (!form.start_time || !form.end_time) return;
  isFreebusyLoading.value = true;
  error.value = null;
  try {
    const resp = await queryCalendarFreebusy({
      time_min: form.start_time,
      time_max: form.end_time,
      timezone: form.timezone,
      calendar_ids: [form.calendar_id],
    });
    busySlots.value = resp.busy;
    conflicts.value = resp.conflicts;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Freebusy 查询失败";
  } finally {
    isFreebusyLoading.value = false;
  }
}

function parseAttendees(value: string) {
  return value.split(",").map((s) => s.trim()).filter(Boolean).map((email) => ({ email, display_name: null }));
}

async function handleSubmit() {
  if (!form.title.trim() || !form.start_time.trim()) return;
  isSubmitting.value = true;
  error.value = null;
  try {
    const organizer = (appState.state.profile?.default_sender_email as string)
      || appState.state.googleEmail || "";
    const artifact = await prepareCalendarEventDraft({
      thread_id: null,
      title: form.title.trim(),
      start_time: form.start_time.trim(),
      end_time: form.end_time.trim() || null,
      duration_minutes: form.end_time.trim() ? null : form.duration_minutes,
      timezone: form.timezone.trim(),
      calendar_id: form.calendar_id.trim(),
      organizer_email: organizer,
      attendees: parseAttendees(form.attendees),
      location: form.location.trim() || null,
      description: form.description.trim() || null,
      video_conference: form.video_conference,
      recurrence_rule: null,
      conflict_override: form.conflict_override,
    });
    latestArtifact.value = artifact;
    conflicts.value = artifact.conflicts;
    form.title = "";
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建草稿失败";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div class="chat-view">
    <div class="view-header">
      <h1>📅 Calendar</h1>
    </div>
    <div class="view-body workspace-view">
      <EventList :calendar-id="form.calendar_id" :google-connected="appState.state.googleConnected" />

      <form @submit.prevent="handleSubmit" style="display:grid;gap:10px;margin-top:16px">
        <h3 style="font-size:13px;color:var(--color-heading)">新建日程草稿</h3>
        <div class="form-row two-col">
          <div class="form-group">
            <label class="form-label">日历</label>
            <input class="form-input" v-model="form.calendar_id" />
          </div>
          <div class="form-group">
            <label class="form-label">时区</label>
            <input class="form-input" v-model="form.timezone" />
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">标题</label>
          <input class="form-input" v-model="form.title" />
        </div>
        <div class="form-row two-col">
          <div class="form-group">
            <label class="form-label">开始时间</label>
            <input class="form-input" v-model="form.start_time" />
          </div>
          <div class="form-group">
            <label class="form-label">结束时间</label>
            <input class="form-input" v-model="form.end_time" />
          </div>
        </div>
        <div class="form-row two-col">
          <div class="form-group">
            <label class="form-label">持续分钟</label>
            <input class="form-input" v-model.number="form.duration_minutes" type="number" />
          </div>
          <div class="form-group">
            <label class="form-label">地点</label>
            <input class="form-input" v-model="form.location" />
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">参会人</label>
          <input class="form-input" v-model="form.attendees" placeholder="li@example.com, zhao@example.com" />
        </div>
        <div class="form-group">
          <label class="form-label">描述</label>
          <textarea class="form-input form-textarea" v-model="form.description" rows="3" />
        </div>
        <label class="form-checkbox">
          <input v-model="form.video_conference" type="checkbox" />
          创建视频会议
        </label>
        <label class="form-checkbox">
          <input v-model="form.conflict_override" type="checkbox" />
          已知冲突仍准备
        </label>
        <div class="action-row">
          <button type="submit" class="btn" :disabled="isSubmitting">
            {{ isSubmitting ? "创建中" : "保存日程草稿" }}
          </button>
          <button type="button" class="btn-secondary" :disabled="isFreebusyLoading || !form.start_time" @click="handleFreebusy">
            {{ isFreebusyLoading ? "查询中" : "Freebusy" }}
          </button>
        </div>
        <p v-if="error" class="inline-error">{{ error }}</p>

        <div v-if="conflicts.length" class="proposal-conflict">
          <span class="proposal-conflict-icon">⚠️</span>
          <div class="proposal-conflict-text">
            <div v-for="slot in conflicts" :key="slot.start">
              {{ slot.calendar_id }}: {{ slot.start }} - {{ slot.end }}
            </div>
          </div>
        </div>

        <div v-if="latestArtifact" class="inline-notice">
          Calendar Artifact {{ latestArtifact.artifact_id }} 已创建 — {{ (latestArtifact.content as Record<string,unknown>)?.title }}
        </div>
      </form>
    </div>
  </div>
</template>
```

- [ ] **Step 3: 验证构建**

```bash
Set-Location frontend
npm run build
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/calendar/
git commit -m "feat: add Calendar workspace components"
```

---

### Task 10: 设置组件（ProfileSettings + SignatureManager + GoogleConnection + SettingsView）

**Files:**
- Create: `frontend/src/components/settings/ProfileSettings.vue`
- Create: `frontend/src/components/settings/SignatureManager.vue`
- Create: `frontend/src/components/settings/GoogleConnection.vue`
- Create: `frontend/src/components/settings/SettingsView.vue`

- [ ] **Step 1: 创建 ProfileSettings**

```vue
<script setup lang="ts">
import { reactive, inject } from "vue";
import type { AppState } from "../../composables/useAppState";
import { saveProfile, type ProfileForm } from "../../api/settings";

const appState = inject<AppState>("appState")!;

const form = reactive<ProfileForm>({
  timezone: (appState.state.profile?.timezone as string) || null,
  default_calendar_id: (appState.state.profile?.default_calendar_id as string) || null,
  default_signature_id: (appState.state.profile?.default_signature_id as string) || null,
  default_sender_email: (appState.state.profile?.default_sender_email as string) || null,
  default_meeting_duration_minutes: (appState.state.profile?.default_meeting_duration_minutes as number) || null,
  meeting_buffer_minutes: (appState.state.profile?.meeting_buffer_minutes as number) || 0,
  working_hours: null,
  lunch_break: null,
  email_tone_internal: null,
  email_tone_external: null,
});

const isSaving = ref(false);
const error = ref<string | null>(null);

async function handleSave() {
  isSaving.value = true;
  error.value = null;
  try {
    const result = await saveProfile(form);
    appState.state.profile = result;
    appState.setNotice?.("设置已保存");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "保存失败";
  } finally {
    isSaving.value = false;
  }
}

function emptyToNull(v: string | number | null) {
  return v === "" ? null : v;
}
</script>

<template>
  <div class="settings-content">
    <h3 style="font-size:14px;margin-bottom:12px;color:var(--color-heading)">个人设置</h3>
    <form @submit.prevent="handleSave" style="display:grid;gap:10px;max-width:480px">
      <div class="form-group">
        <label class="form-label">时区</label>
        <input class="form-input" v-model="form.timezone" placeholder="Asia/Shanghai" />
      </div>
      <div class="form-group">
        <label class="form-label">发件账号</label>
        <input class="form-input" v-model="form.default_sender_email" />
      </div>
      <div class="form-group">
        <label class="form-label">默认日历</label>
        <input class="form-input" v-model="form.default_calendar_id" placeholder="primary" />
      </div>
      <div class="form-row two-col">
        <div class="form-group">
          <label class="form-label">默认会议时长（分钟）</label>
          <input class="form-input" v-model.number="form.default_meeting_duration_minutes" type="number" min="1" />
        </div>
        <div class="form-group">
          <label class="form-label">缓冲时间（分钟）</label>
          <input class="form-input" v-model.number="form.meeting_buffer_minutes" type="number" min="0" />
        </div>
      </div>
      <button class="btn" type="submit" :disabled="isSaving">
        {{ isSaving ? "保存中" : "保存设置" }}
      </button>
      <p v-if="error" class="inline-error">{{ error }}</p>
    </form>
  </div>
</template>
```

- [ ] **Step 2: 创建 SignatureManager**

```vue
<script setup lang="ts">
import { ref, reactive, inject } from "vue";
import type { AppState } from "../../composables/useAppState";
import { createSignature, fetchSignatures } from "../../api/settings";

const appState = inject<AppState>("appState")!;

const form = reactive({ label: "", content: "", is_default: false });
const isCreating = ref(false);
const error = ref<string | null>(null);

async function handleCreate() {
  if (!form.label.trim() || !form.content.trim()) return;
  isCreating.value = true;
  error.value = null;
  try {
    await createSignature({ label: form.label.trim(), content: form.content.trim(), is_default: form.is_default });
    const sigs = await fetchSignatures();
    appState.state.signatures = sigs;
    form.label = "";
    form.content = "";
    form.is_default = false;
    appState.setNotice?.("署名已创建");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建失败";
  } finally {
    isCreating.value = false;
  }
}
</script>

<template>
  <div class="settings-content">
    <h3 style="font-size:14px;margin-bottom:12px;color:var(--color-heading)">署名管理</h3>
    <div v-if="appState.state.signatures.length">
      <div v-for="sig in appState.state.signatures" :key="sig.id" class="signature-item">
        <div class="signature-item-body">
          <span class="signature-item-label">{{ sig.label }}</span>
          <span v-if="sig.is_default" class="signature-item-default">默认</span>
          <div class="signature-item-content">{{ sig.content }}</div>
        </div>
      </div>
    </div>
    <p v-else style="color:var(--color-weak);font-size:12px;margin-bottom:12px">暂无署名</p>

    <form @submit.prevent="handleCreate" style="display:grid;gap:8px;max-width:400px">
      <div class="form-group">
        <label class="form-label">名称</label>
        <input class="form-input" v-model="form.label" />
      </div>
      <div class="form-group">
        <label class="form-label">内容</label>
        <textarea class="form-input form-textarea" v-model="form.content" rows="4" />
      </div>
      <label class="form-checkbox">
        <input v-model="form.is_default" type="checkbox" />
        设为默认
      </label>
      <button class="btn" type="submit" :disabled="isCreating">
        {{ isCreating ? "创建中" : "创建署名" }}
      </button>
      <p v-if="error" class="inline-error">{{ error }}</p>
    </form>
  </div>
</template>
```

- [ ] **Step 3: 创建 GoogleConnection**

```vue
<script setup lang="ts">
import { inject } from "vue";
import type { AppState } from "../../composables/useAppState";
import { startGoogleLogin, disconnectGoogle } from "../../api/auth";

const appState = inject<AppState>("appState")!;

async function handleDisconnect() {
  try {
    await disconnectGoogle();
    appState.state.googleConnected = false;
    appState.state.googleEmail = null;
    appState.setNotice?.("Google 已断开");
  } catch (e) {
    appState.setNotice?.(e instanceof Error ? e.message : "断开失败");
  }
}
</script>

<template>
  <div class="settings-content">
    <h3 style="font-size:14px;margin-bottom:12px;color:var(--color-heading)">Google 连接</h3>
    <div class="google-badge" :class="appState.state.googleConnected ? 'connected' : 'disconnected'" style="margin-bottom:10px">
      <span class="google-badge-check">{{ appState.state.googleConnected ? "✓" : "—" }}</span>
      <div>
        <div style="font-weight:600;font-size:11px">
          {{ appState.state.googleConnected ? appState.state.googleEmail : "未连接" }}
        </div>
      </div>
    </div>
    <div class="action-row">
      <button class="btn" @click="startGoogleLogin">
        {{ appState.state.googleConnected ? "重新连接" : "连接 Google" }}
      </button>
      <button v-if="appState.state.googleConnected" class="btn-secondary" @click="handleDisconnect">
        断开连接
      </button>
    </div>
  </div>
</template>
```

- [ ] **Step 4: 创建 SettingsView**

```vue
<script setup lang="ts">
import { ref } from "vue";
import ProfileSettings from "./ProfileSettings.vue";
import SignatureManager from "./SignatureManager.vue";
import GoogleConnection from "./GoogleConnection.vue";

const activeTab = ref("profile");

const tabs = [
  { id: "profile", label: "个人设置" },
  { id: "signatures", label: "署名管理" },
  { id: "google", label: "Google 连接" },
];
</script>

<template>
  <div class="chat-view">
    <div class="view-header">
      <h1>⚙️ 设置</h1>
    </div>
    <div class="settings-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="settings-tab"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>
    <ProfileSettings v-if="activeTab === 'profile'" />
    <SignatureManager v-else-if="activeTab === 'signatures'" />
    <GoogleConnection v-else />
  </div>
</template>
```

- [ ] **Step 5: 验证构建**

```bash
Set-Location frontend
npm run build
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/settings/
git commit -m "feat: add Settings view with profile, signatures, Google connection"
```

---

### Task 11: 重写 App.vue（三栏布局壳）

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: 用新的布局壳替换 App.vue**

将当前 1400+ 行的 App.vue 替换为以下布局壳：

```vue
<script setup lang="ts">
// App.vue — 三栏布局壳。
// 负责：创建共享状态、provide 给子组件、加载初始化数据、
// 切换视图、处理全局通知、处理 Markdown 导出。
import { provide, onMounted, ref } from "vue";
import { createAppState, type AppState } from "./composables/useAppState";
import { fetchHealth } from "./api/health";
import { fetchGoogleStatus, type GoogleAuthStatus } from "./api/auth";
import { fetchProfile, fetchSignatures, type UserProfile } from "./api/settings";
import { exportMarkdownBundle } from "./api/memory";

import AppSidebar from "./components/AppSidebar.vue";
import ContextPanel from "./components/ContextPanel.vue";
import ChatView from "./components/chat/ChatView.vue";
import GmailView from "./components/gmail/GmailView.vue";
import CalendarView from "./components/calendar/CalendarView.vue";
import SettingsView from "./components/settings/SettingsView.vue";

// 共享状态
const { state, setNotice } = createAppState();
provide<AppState>("appState", { state, setNotice });

const isLoading = ref(true);
const globalError = ref<string | null>(null);
const globalNotice = ref<string | null>(null);

// 加载初始化数据
async function loadInitialData() {
  // 检查 URL 中的 Google 授权结果
  const query = new URLSearchParams(window.location.search);
  const authResult = query.get("google_auth");
  if (authResult === "connected") {
    state.notice = "Google 授权成功";
  } else if (authResult === "error" || authResult === "state_mismatch") {
    state.notice = "Google 授权失败";
  }

  try {
    const [health] = await Promise.all([
      fetchHealth(),
      loadGoogleArea(),
    ]);
    // health check passed silently
  } catch (e) {
    globalError.value = e instanceof Error ? e.message : "应用初始化失败";
  } finally {
    isLoading.value = false;
    window.history.replaceState({}, document.title, window.location.pathname);
  }
}

async function loadGoogleArea() {
  try {
    const gs = await fetchGoogleStatus();
    state.googleConnected = gs.connected;
    state.googleEmail = gs.email;
    state.googleNeedsReconnect = gs.needs_reconnect;
    state.googleMessage = gs.message;

    if (gs.connected) {
      const profile = await fetchProfile();
      state.profile = profile;
      const sigs = await fetchSignatures();
      state.signatures = sigs;
    }
  } catch {
    // Google 未连接不是致命错误
  }
}

// Markdown 导出
async function handleExportMarkdown() {
  try {
    await exportMarkdownBundle();
    setNotice("Markdown 已导出");
  } catch (e) {
    setNotice(e instanceof Error ? e.message : "导出失败");
  }
}

onMounted(loadInitialData);
</script>

<template>
  <!-- 加载中 -->
  <div v-if="isLoading" style="display:flex;align-items:center;justify-content:center;height:100vh;color:var(--color-weak);font-size:14px">
    正在启动 Mailflow Agent...
  </div>

  <!-- 三栏布局 -->
  <main v-else class="app-shell">
    <AppSidebar />

    <div class="main-content">
      <ChatView v-if="state.activeView === 'chat'" />
      <GmailView v-else-if="state.activeView === 'gmail'" />
      <CalendarView v-else-if="state.activeView === 'calendar'" />
      <SettingsView v-else-if="state.activeView === 'settings'" />
    </div>

    <ContextPanel @export-markdown="handleExportMarkdown" />

    <!-- 全局提示 -->
    <div
      v-if="state.notice"
      style="position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:8px 16px;border-radius:var(--radius-pill);background:var(--color-heading);color:#fff;font-size:12px;z-index:100;box-shadow:0 4px 12px rgba(0,0,0,0.15)"
    >
      {{ state.notice }}
    </div>
    <div
      v-if="globalError"
      style="position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:8px 16px;border-radius:var(--radius-pill);background:var(--color-error);color:#fff;font-size:12px;z-index:100"
    >
      {{ globalError }}
    </div>
  </main>
</template>
```

- [ ] **Step 2: 验证构建**

```bash
Set-Location frontend
npm run build
```

预期：构建成功。如有 TypeScript 错误，检查 import 路径和类型兼容性。

- [ ] **Step 3: 修正构建错误（如有）**

常见问题：
- `import { ref }` 缺失 → 在需要的文件中补充 import
- `fetchProfile` / `fetchSignatures` 返回类型不匹配 → 检查 `api/settings.ts` 的类型定义
- 组件 props 类型不匹配 → 对照 `api/*.ts` 中的 interface 调整

- [ ] **Step 4: 提交**

```bash
git add frontend/src/App.vue
git commit -m "refactor: replace App.vue with 3-column layout shell"
```

---

### Task 12: 更新 index.html

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: 更新标题**

把 `<title>` 从 `Mailflow Agent` 改为 `Mailflow — 邮件与日程助理`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Mailflow — 邮件与日程助理</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/index.html
git commit -m "chore: update index.html title and add Inter font"
```

---

### Task 13: 最终验证与修复

- [ ] **Step 1: 清理旧文件检查**

确认无需清理的旧组件文件（所有逻辑已迁移到新组件中，旧 App.vue 已被替换）。

- [ ] **Step 2: 生产构建**

```bash
Set-Location frontend
npm run build
```

预期：没有 TypeScript 错误，没有 CSS 引用错误，构建产物正确生成到 `dist/`。

- [ ] **Step 3: TypeScript 检查**

```bash
Set-Location frontend
npx vue-tsc --noEmit
```

- [ ] **Step 4: 逐项检查**

对照 spec 检查：
- [ ] 三栏布局：左侧 52px 图标导航 + 中间主内容 + 右侧 240px 面板
- [ ] 4 个视图通过图标栏切换
- [ ] 聊天视图：消息气泡 + Proposal 内嵌卡片 + 输入区
- [ ] Gmail 视图：搜索 + 结果 + 详情 + 草稿表单
- [ ] Calendar 视图：日程列表 + Freebusy + 草稿表单
- [ ] 设置视图：个人设置 / 署名管理 / Google 连接子标签
- [ ] 右侧面板：待办摘要 + Google 状态 + 快捷操作
- [ ] Proposal 卡片：邮件蓝色系 / 日程绿色系
- [ ] 响应式：900px 隐藏右侧面板，640px 隐藏侧栏
- [ ] API 客户端文件未修改

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "chore: final cleanup and verification pass"
```

---

## 实现顺序

```
Task 1  (CSS 设计系统)     ── 基础，必须先做
Task 2  (共享状态)         ── 基础，必须先做
Task 3  (AppSidebar)       ── 依赖 Task 2
Task 4  (面板子组件)        ── 依赖 Task 2，可与 Task 3 并行
Task 5  (ContextPanel)     ── 依赖 Task 4
Task 6  (聊天子组件)        ── 可与 Task 3-5 并行
Task 7  (ChatView)         ── 依赖 Task 2, 6
Task 8  (Gmail 组件)       ── 依赖 Task 2
Task 9  (Calendar 组件)    ── 依赖 Task 2
Task 10 (Settings 组件)    ── 依赖 Task 2
Task 11 (App.vue)          ── 依赖 Task 1-10 全部
Task 12 (index.html)       ── 可与 Task 11 并行
Task 13 (最终验证)         ── 依赖 Task 11, 12
```
