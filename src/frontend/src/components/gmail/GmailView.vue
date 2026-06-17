<script setup lang="ts">
// Gmail 工作台——Gmail 风格的文件夹+邮件列表+详情+搜索。
import { ref, inject, onMounted, watch } from "vue";
import type { AppState } from "../../composables/useAppState";
import {
  searchGmail,
  readGmailMessage,
  readGmailThread,
  deleteGmailMessage,
  type GmailMessageSummary,
  type GmailMessageDetail,
} from "../../api/gmail";
import {
  deleteWorkItem,
  fetchOpenWorkItems,
  fetchWorkItem,
  type WorkItemDetail,
  type WorkItemSummary,
} from "../../api/workflow";
import GmailFolderList from "./GmailFolderList.vue";
import type { FolderItem } from "./GmailFolderList.vue";
import GmailMessageList from "./GmailMessageList.vue";
import GmailDetail from "./GmailDetail.vue";
import GmailSearch from "./GmailSearch.vue";

const appState = inject<AppState>("appState")!;

const activeFolder = ref<FolderItem>({
  id: "inbox", label: "收件箱", icon: "📥", query: "in:inbox",
});
const messages = ref<GmailMessageSummary[]>([]);
const isLoading = ref(false);
const selectedId = ref<string | null>(null);
const selectedDetail = ref<GmailMessageDetail | null>(null);
const selectedLocalWorkItemId = ref<string | null>(null);
const isLoadingDetail = ref(false);
const showSearch = ref(false);
const error = ref<string | null>(null);

onMounted(() => {
  if (appState.state.googleConnected) {
    loadFolder(activeFolder.value);
  }
});

// 跨页面同步：当聊天页操作后自动刷新
watch(
  () => appState.state.refreshSignal,
  () => {
    loadFolder(activeFolder.value);
  },
);

async function loadFolder(folder: FolderItem) {
  activeFolder.value = folder;
  selectedId.value = null;
  selectedDetail.value = null;
  isLoading.value = true;
  error.value = null;
  try {
    const resp = await searchGmail({ query: folder.query, max_results: 20 });
    messages.value = resp.messages;

    // 草稿箱：额外合并本地 Work Item 草稿
    if (folder.id === "drafts") {
      try {
        const workItems = await fetchOpenWorkItems();
        const localDrafts = workItems
          .filter((w: WorkItemSummary) => w.work_item_type === "email_draft")
          .map((w: WorkItemSummary) => ({
            id: w.id,
            thread_id: "",
            subject: w.title,
            from_email: "本地草稿",
            date: null,
            snippet: w.summary || "",
            label_ids: ["DRAFT", "LOCAL_DRAFT"],
          } as GmailMessageSummary));
        messages.value = [...localDrafts, ...messages.value];
      } catch {
        // 本地草稿加载失败不影响 Gmail 展示
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载失败";
  } finally {
    isLoading.value = false;
  }
}

async function handleSelectMessage(id: string) {
  selectedId.value = id;
  selectedLocalWorkItemId.value = null;
  isLoadingDetail.value = true;
  try {
    const selected = messages.value.find((msg) => msg.id === id);
    if (selected?.label_ids?.includes("LOCAL_DRAFT")) {
      const workItem = await fetchWorkItem(id);
      selectedLocalWorkItemId.value = id;
      selectedDetail.value = localDraftToDetail(workItem);
    } else {
      selectedDetail.value = await readGmailMessage(id);
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "读取邮件失败";
  } finally {
    isLoadingDetail.value = false;
  }
}

async function handleSelectThread(threadId: string) {
  if (!threadId) return;
  selectedLocalWorkItemId.value = null;
  isLoadingDetail.value = true;
  try {
    const thread = await readGmailThread(threadId);
    if (thread.messages.length) {
      const lastId = thread.messages[thread.messages.length - 1].id;
      selectedDetail.value = await readGmailMessage(lastId);
      selectedId.value = lastId;
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "读取线程失败";
  } finally {
    isLoadingDetail.value = false;
  }
}

function handleSearchSelect(detail: GmailMessageDetail) {
  selectedDetail.value = detail;
  selectedId.value = detail.id;
  selectedLocalWorkItemId.value = null;
}

async function handleDelete(messageId: string) {
  const isLocalDraft = Boolean(selectedLocalWorkItemId.value);
  const prompt = isLocalDraft
    ? "确定要删除这封本地草稿吗？"
    : "确定要将此邮件移至垃圾箱吗？";
  if (!confirm(prompt)) return;
  try {
    if (isLocalDraft && selectedLocalWorkItemId.value) {
      await deleteWorkItem(selectedLocalWorkItemId.value);
    } else {
      await deleteGmailMessage(messageId);
    }
    selectedDetail.value = null;
    selectedId.value = null;
    selectedLocalWorkItemId.value = null;
    // 重新加载当前文件夹
    await loadFolder(activeFolder.value);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "删除失败";
  }
}

function localDraftToDetail(workItem: WorkItemDetail): GmailMessageDetail {
  const content = workItem.artifact_content || {};
  const toItems = Array.isArray(content.to) ? content.to : [];
  const ccItems = Array.isArray(content.cc) ? content.cc : [];
  const formatAddress = (item: unknown): string => {
    if (item && typeof item === "object") {
      const value = item as { email?: string; name?: string | null };
      return value.name ? `${value.name} <${value.email || ""}>` : value.email || "";
    }
    return String(item || "");
  };

  return {
    id: workItem.id,
    thread_id: workItem.thread_id,
    subject: typeof content.subject === "string" ? content.subject : workItem.title,
    from_email: "本地草稿",
    to: toItems.map(formatAddress).filter(Boolean),
    cc: ccItems.map(formatAddress).filter(Boolean),
    date: workItem.updated_at,
    snippet: workItem.summary,
    body: {
      text: typeof content.body === "string" ? content.body : "",
      html: null,
    },
    headers: {
      "x-mailflow-local-draft": "true",
      "x-mailflow-artifact-id": workItem.artifact_id || "",
      "x-mailflow-status": workItem.status,
    },
  };
}
</script>

<template>
  <div class="chat-view">
    <div class="view-header">
      <h1>📧 邮箱</h1>
      <button
        class="btn-secondary"
        style="font-size:13px;padding:6px 14px"
        @click="showSearch = !showSearch"
      >
        {{ showSearch ? "关闭搜索" : "🔍 搜索" }}
      </button>
    </div>

    <!-- 搜索栏（可折叠） -->
    <div v-if="showSearch" style="padding:0 14px 10px">
      <GmailSearch @select="handleSearchSelect" />
    </div>

    <p v-if="error" class="inline-error" style="margin:6px 14px">{{ error }}</p>

    <div class="view-body gmail-layout">
      <!-- 左侧：文件夹导航 -->
      <GmailFolderList @select="loadFolder" />

      <!-- 中间：邮件列表 -->
      <div class="gmail-center">
        <GmailMessageList
          :messages="messages"
          :is-loading="isLoading"
          :selected-id="selectedId"
          @select="handleSelectMessage"
          @select-thread="handleSelectThread"
        />
      </div>

      <!-- 右侧：邮件详情 -->
      <div class="gmail-detail">
        <GmailDetail :detail="selectedDetail" />
        <div v-if="selectedDetail" style="padding:10px 16px">
          <button
            class="btn-danger"
            style="font-size:13px;padding:6px 14px"
            @click="handleDelete(selectedDetail!.id)"
          >
            🗑️ 删除
          </button>
        </div>
        <div
          v-if="isLoadingDetail"
          style="padding:16px;color:var(--color-weak);font-size:12px"
        >
          加载邮件详情…
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gmail-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.gmail-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
.gmail-detail {
  flex: 1.2;
  overflow-y: auto;
  border-left: 1px solid var(--color-border, #e0e0e0);
  min-width: 0;
}
</style>
