<script setup lang="ts">
// Gmail 搜索栏 + 邮件列表。展示发件人、主题、日期、摘要。
import { ref } from "vue";
import {
  searchGmail,
  readGmailMessage,
  readGmailThread,
  type GmailMessageSummary,
  type GmailMessageDetail,
} from "../../api/gmail";

const query = ref("newer_than:7d");
const maxResults = ref(10);
const isSearching = ref(false);
const results = ref<GmailMessageSummary[]>([]);
const isLoadingDetail = ref(false);
const error = ref<string | null>(null);

const emit = defineEmits<{
  select: [detail: GmailMessageDetail];
}>();

const quickSearches = [
  { label: "最近一周", query: "newer_than:7d" },
  { label: "未读", query: "is:unread" },
  { label: "收件箱", query: "in:inbox" },
];

async function handleSearch(q?: string) {
  if (q) query.value = q;
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
  isLoadingDetail.value = true;
  try {
    const detail = await readGmailMessage(id);
    emit("select", detail);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "读取失败";
  } finally {
    isLoadingDetail.value = false;
  }
}

async function handleReadThread(id: string) {
  isLoadingDetail.value = true;
  try {
    const thread = await readGmailThread(id);
    if (thread.messages.length) {
      const lastId = thread.messages[thread.messages.length - 1].id;
      const detail = await readGmailMessage(lastId);
      emit("select", detail);
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "读取线程失败";
  } finally {
    isLoadingDetail.value = false;
  }
}
</script>

<template>
  <div>
    <!-- 快捷搜索 -->
    <div class="action-row" style="margin-bottom:10px">
      <button
        v-for="qs in quickSearches"
        :key="qs.query"
        class="btn-secondary"
        style="font-size:12px;padding:5px 12px"
        @click="handleSearch(qs.query)"
      >
        {{ qs.label }}
      </button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <input
        v-model="query"
        placeholder="搜索 Gmail… 例如：from:someone@example.com"
        :disabled="isSearching"
        @keyup.enter="handleSearch()"
      />
      <input
        v-model.number="maxResults"
        type="number" min="1" max="25"
        style="width:70px"
        :disabled="isSearching"
      />
      <button class="btn" :disabled="isSearching" @click="handleSearch()">
        {{ isSearching ? "搜索中" : "搜索" }}
      </button>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>

    <!-- 邮件列表 -->
    <div v-if="results.length" class="result-list">
      <div
        v-for="item in results"
        :key="item.id"
        class="result-item"
        style="cursor:pointer"
        @click="handleReadMessage(item.id)"
      >
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;font-size:14px;color:var(--color-heading);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            {{ item.id }}
          </div>
          <div class="result-item-meta">
            Thread: {{ item.thread_id }}
          </div>
        </div>
        <div class="action-row">
          <button
            class="btn-secondary"
            style="font-size:12px;padding:5px 12px"
            @click.stop="handleReadThread(item.thread_id)"
          >
            线程
          </button>
        </div>
      </div>
    </div>

    <p v-if="!isSearching && !results.length && !error" style="color:var(--color-weak);font-size:14px;padding:14px 0">
      输入搜索条件查看邮件，或点击快捷搜索按钮。
    </p>
  </div>
</template>
