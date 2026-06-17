<script setup lang="ts">
// 聊天主视图 —— agent + tools 架构。
// 左侧 SessionSidebar + 右侧消息区。
import { ref, inject, nextTick, watch } from "vue";
import type { AppState } from "../../composables/useAppState";
import { streamAssistantTurn, fetchAssistantState, updateThreadTitle } from "../../api/assistant";
import {
  fetchOpenWorkItems,
  fetchPendingProposals,
  authorizeProposal,
  executeProposal,
  type ProposalItem,
  type WorkItemSummary,
} from "../../api/workflow";
import ChatMessage from "./ChatMessage.vue";
import ProposalCard from "./ProposalCard.vue";
import ChatInput from "./ChatInput.vue";
import SessionSidebar from "./SessionSidebar.vue";

const appState = inject<AppState>("appState")!;

interface ChatItem {
  id: string;
  type: "message" | "proposal";
  role?: "user" | "assistant" | "system";
  content?: string;
  systemType?: "warning" | "error" | "success";
  attachments?: ChatAttachment[];
  proposal?: ProposalItem;
}

interface ChatAttachment {
  filename: string;
  status: "succeeded" | "failed";
}

interface ChatSendPayload {
  displayMessage: string;
  modelMessage: string;
  fileRefs?: Record<string, unknown>[];
  attachments?: ChatAttachment[];
}

interface SessionInfo {
  id: string;
  title: string;
}

type MessageCache = Map<string, ChatItem[]>;

const messagesCache: MessageCache = new Map();
const messages = ref<ChatItem[]>([
  {
    id: "welcome",
    type: "message",
    role: "assistant",
    content: "我可以帮你写邮件、管理日程、搜索 Gmail。直接告诉我要做什么。",
  },
]);

const threadId = ref(loadActiveThreadId());
const sessions = ref<SessionInfo[]>(loadSessions());
const isStreaming = ref(false);
const pendingProposals = ref<ProposalItem[]>([]);
const messagesContainer = ref<HTMLElement | null>(null);
const isFirstMessage = ref<Set<string>>(loadFirstMessageFlags());

function loadAllThreadIds(): string[] {
  const stored = localStorage.getItem("mailflow_thread_ids");
  if (stored) {
    try { return JSON.parse(stored); } catch { /* ignore */ }
  }
  return [loadActiveThreadId()];
}

function saveAllThreadIds(ids: string[]) {
  localStorage.setItem("mailflow_thread_ids", JSON.stringify(ids));
}

function loadActiveThreadId(): string {
  const existing = localStorage.getItem("mailflow_assistant_thread_id");
  if (existing) return existing;
  const created = `thread_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
  localStorage.setItem("mailflow_assistant_thread_id", created);
  return created;
}

function loadSessions(): SessionInfo[] {
  const titles = localStorage.getItem("mailflow_thread_titles");
  const titleMap: Record<string, string> = titles ? JSON.parse(titles) : {};
  return loadAllThreadIds().map(id => ({
    id,
    title: titleMap[id] || "",
  }));
}

function saveSessions() {
  const titleMap: Record<string, string> = {};
  for (const s of sessions.value) {
    if (s.title) titleMap[s.id] = s.title;
  }
  localStorage.setItem("mailflow_thread_titles", JSON.stringify(titleMap));
}

function loadFirstMessageFlags(): Set<string> {
  const stored = localStorage.getItem("mailflow_first_msg_flags");
  if (stored) {
    try { return new Set(JSON.parse(stored)); } catch { /* ignore */ }
  }
  return new Set<string>();
}

function saveFirstMessageFlags() {
  localStorage.setItem("mailflow_first_msg_flags", JSON.stringify([...isFirstMessage.value]));
}

function cacheCurrentMessages() {
  messagesCache.set(threadId.value, [...messages.value]);
}

async function switchThread(newThreadId: string) {
  if (newThreadId === threadId.value) return;
  cacheCurrentMessages();
  threadId.value = newThreadId;
  localStorage.setItem("mailflow_assistant_thread_id", newThreadId);

  const cached = messagesCache.get(newThreadId);
  if (cached) {
    messages.value = cached;
  } else {
    messages.value = [{
      id: "welcome",
      type: "message",
      role: "assistant",
      content: "我可以帮你写邮件、管理日程、搜索 Gmail。直接告诉我要做什么。",
    }];
    restoreChat();
  }
  scrollToBottom();
  refreshTodos();
}

function createNewThread() {
  cacheCurrentMessages();
  const newId = `thread_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
  const allIds = [...loadAllThreadIds(), newId];
  saveAllThreadIds(allIds);
  sessions.value.push({ id: newId, title: "" });
  isFirstMessage.value.add(newId);
  saveFirstMessageFlags();
  switchThread(newId);
}

function deleteThread(threadIdToDelete: string) {
  const ids = loadAllThreadIds();
  if (ids.length <= 1) return;
  const newIds = ids.filter(id => id !== threadIdToDelete);
  saveAllThreadIds(newIds);
  sessions.value = sessions.value.filter(s => s.id !== threadIdToDelete);
  saveSessions();
  messagesCache.delete(threadIdToDelete);
  isFirstMessage.value.delete(threadIdToDelete);
  saveFirstMessageFlags();

  if (threadId.value === threadIdToDelete) {
    switchThread(newIds[0]);
  }
}

function addMessage(
  role: "user" | "assistant" | "system",
  content: string,
  systemType?: "warning" | "error" | "success",
  attachments?: ChatAttachment[],
) {
  messages.value.push({
    id: `msg_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
    type: "message",
    role,
    content,
    systemType,
    attachments,
  });
  scrollToBottom();
}

watch(
  () => messages.value.length,
  () => { nextTick(() => scrollToBottom()); },
);

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
  } catch {
    // 静默
  }
}

async function generateSessionTitle() {
  // 用 LLM 根据第一条用户消息生成标题
  const firstUserMsg = messages.value.find(m => m.type === "message" && m.role === "user");
  if (!firstUserMsg?.content) return;

  try {
    const resp = await fetch("/api/assistant/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: `title_gen_${threadId.value}`,
        message: `根据以下消息生成一个简短的会话标题（2-8个汉字，不要引号，只返回标题）：\n"${firstUserMsg.content.slice(0, 200)}"`,
      }),
    });
    if (resp.ok) {
      const data = await resp.json();
      let title = (data.response || "").replace(/["""'']/g, "").trim().slice(0, 30);
      if (title) {
        const session = sessions.value.find(s => s.id === threadId.value);
        if (session) {
          session.title = title;
          saveSessions();
          // 异步持久化到后端
          updateThreadTitle(threadId.value, title).catch(() => {});
        }
      }
    }
  } catch {
    // 标题生成失败不影响
  }
}

async function handleSend(payload: ChatSendPayload) {
  addMessage("user", payload.displayMessage, undefined, payload.attachments);
  isStreaming.value = true;

  try {
    let streamedContent = "";
    const selectedRefs = [
      ...appState.state.selectedContextRefs,
      ...(payload.fileRefs ?? []),
    ];
    const result = await streamAssistantTurn(
      { thread_id: threadId.value, message: payload.modelMessage, selected_context_refs: selectedRefs },
      (event) => {
        if (event.event === "token" && event.message) {
          streamedContent += event.message;
          const last = messages.value[messages.value.length - 1];
          if (last && last.type === "message" && last.role === "assistant") {
            last.content = streamedContent;
          } else {
            messages.value.push({
              id: `msg_stream_${Date.now()}`,
              type: "message",
              role: "assistant",
              content: streamedContent,
            });
          }
          scrollToBottom();
        }
      },
    );

    if (!streamedContent && result.response) {
      const last = messages.value[messages.value.length - 1];
      if (last && last.type === "message" && last.role === "assistant" && !last.content) {
        last.content = result.response;
      } else {
        addMessage("assistant", result.response);
      }
    }

    if (streamedContent) {
      const last = messages.value[messages.value.length - 1];
      if (last && last.type === "message" && last.role === "assistant") {
        last.content = streamedContent;
      }
    }

    await refreshTodos();
    appState.triggerRefresh?.();

    // 第一条消息：生成标题
    if (isFirstMessage.value.has(threadId.value)) {
      isFirstMessage.value.delete(threadId.value);
      saveFirstMessageFlags();
      setTimeout(() => generateSessionTitle(), 500);
    }
  } catch (e) {
    addMessage("system", e instanceof Error ? e.message : "聊天请求失败", "error");
  } finally {
    isStreaming.value = false;
    cacheCurrentMessages();
    scrollToBottom();
  }
}

async function handleApprove(proposal: ProposalItem) {
  try {
    await authorizeProposal(proposal, "approved");
    const execResult = await executeProposal(proposal);
    const execMsg = execResult.status === "executed" ? "已执行完成" : `执行结果: ${execResult.status}`;
    addMessage("system", `✅ ${execMsg}`, "success");
    appState.setNotice?.(execMsg);
    await refreshTodos();
    appState.triggerRefresh?.();
  } catch (e) {
    addMessage("system", e instanceof Error ? e.message : "执行失败", "error");
  }
}

function handleRevise(_proposal: ProposalItem) {
  appState.setNotice?.("草稿已带回表单，请到对应工作台修改");
}

function handleDefer(_proposal: ProposalItem) {
  appState.setNotice?.("已暂缓 Proposal");
}

async function restoreChat() {
  try {
    const response = await fetchAssistantState(threadId.value);
    const msgs = Array.isArray(response.state.messages) ? response.state.messages : [];
    const restored = msgs
      .map((item: unknown, index: number) => {
        const record = item as Record<string, unknown>;
        const role = record.role === "user" ? "user" : "assistant";
        const content = typeof record.content === "string" ? record.content : "";
        return {
          id: `restore_${index}`,
          type: "message" as const,
          role,
          content,
        } satisfies ChatItem;
      })
      .filter((item) => item.content);
    if (restored.length) {
      messages.value = restored;
    }
    scrollToBottom();
  } catch {
    // 首次无 checkpoint 正常
  }
}

function scrollToBottom() {
  nextTick(() => {
    const el = messagesContainer.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

restoreChat();
refreshTodos();
</script>

<template>
  <div class="chat-view">
    <SessionSidebar
      :sessions="sessions"
      :active-id="threadId"
      @switch="switchThread"
      @delete="deleteThread"
      @new="createNewThread"
    />

    <div class="chat-main">
      <div class="view-header">
        <h1>💬 聊天</h1>
      </div>

      <div ref="messagesContainer" class="chat-messages">
        <template v-for="item in messages" :key="item.id">
          <ChatMessage
            v-if="item.type === 'message'"
            :role="item.role!"
            :content="item.content!"
            :system-type="item.systemType"
            :attachments="item.attachments"
          />
          <ProposalCard
            v-else-if="item.type === 'proposal' && item.proposal"
            :proposal="item.proposal"
            @approve="handleApprove(item.proposal!)"
            @revise="handleRevise(item.proposal!)"
            @defer="handleDefer(item.proposal!)"
          />
        </template>

        <div v-if="isStreaming" style="padding:12px 0;color:var(--color-weak);font-size:15px">
          正在生成回复…
        </div>
      </div>

      <ChatInput @send="handleSend" :disabled="isStreaming" :thread-id="threadId" />
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex !important;
  flex-direction: row !important;
  height: 100%;
  overflow: hidden;
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  height: 100%;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 26px 32px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
</style>
