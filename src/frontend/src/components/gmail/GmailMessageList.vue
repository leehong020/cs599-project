<script setup lang="ts">
// 增强的邮件列表组件，显示发件人、主题、日期、摘要。
// 支持点击选择邮件、线程查看。
import { computed } from "vue";
import type { GmailMessageSummary } from "../../api/gmail";

const props = defineProps<{
  messages: GmailMessageSummary[];
  isLoading: boolean;
  selectedId: string | null;
}>();

const emit = defineEmits<{
  select: [id: string];
  selectThread: [threadId: string];
}>();

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor(
      (now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24)
    );
    if (diffDays === 0) {
      return d.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      });
    }
    if (diffDays === 1) return "昨天";
    if (diffDays < 7) {
      const days = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
      return days[d.getDay()];
    }
    return d.toLocaleDateString("zh-CN", {
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function extractName(fromEmail: string | null): string {
  if (!fromEmail) return "未知";
  // 尝试解析 "Name <email>" 格式
  const match = fromEmail.match(/^(.+?)\s*<[^>]+>$/);
  if (match) return match[1].trim();
  // 如果没有尖括号，显示邮箱前缀
  const atPos = fromEmail.indexOf("@");
  if (atPos > 0) return fromEmail.substring(0, atPos);
  return fromEmail;
}

function isInbox(msg: GmailMessageSummary): boolean {
  return msg.label_ids?.includes("INBOX") ?? false;
}
</script>

<template>
  <div class="message-list">
    <!-- 加载态 -->
    <div v-if="isLoading" class="list-loading">加载中…</div>

    <!-- 空态 -->
    <div v-else-if="!messages.length" class="list-empty">
      暂无邮件
    </div>

    <!-- 邮件列表 -->
    <div
      v-for="msg in messages"
      :key="msg.id"
      class="message-item"
      :class="{
        selected: selectedId === msg.id,
        unread: isInbox(msg),
      }"
      @click="emit('select', msg.id)"
    >
      <div class="msg-main">
        <div class="msg-from">{{ extractName(msg.from_email) }}</div>
        <div class="msg-subject">{{ msg.subject || "无主题" }}</div>
        <div class="msg-snippet">{{ msg.snippet }}</div>
      </div>
      <div class="msg-meta">
        <div class="msg-date">{{ formatDate(msg.date) }}</div>
        <button
          v-if="msg.thread_id"
          class="msg-thread-btn"
          title="查看线程"
          @click.stop="emit('selectThread', msg.thread_id)"
        >
          线程
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.list-loading,
.list-empty {
  padding: 36px 20px;
  text-align: center;
  color: var(--color-weak);
  font-size: 15px;
}
.message-item {
  display: flex;
  align-items: flex-start;
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border, #e8e8e8);
  transition: background 0.12s;
  gap: 14px;
}
.message-item:hover {
  background: var(--color-bg-hover, #f5f5f5);
}
.message-item.selected {
  background: var(--color-primary-light, #e8f0fe);
}
.message-item.unread {
  font-weight: 600;
}
.msg-main {
  flex: 1;
  min-width: 0;
}
.msg-from {
  font-size: 15px;
  color: var(--color-heading, #1a1a1a);
  margin-bottom: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.msg-subject {
  font-size: 14px;
  color: var(--color-text, #333);
  margin-bottom: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.message-item.unread .msg-subject {
  color: var(--color-heading, #1a1a1a);
}
.msg-snippet {
  font-size: 13px;
  color: var(--color-weak);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.msg-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  flex-shrink: 0;
}
.msg-date {
  font-size: 12px;
  color: var(--color-weak);
  white-space: nowrap;
}
.msg-thread-btn {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 5px;
  border: 1px solid var(--color-border, #ddd);
  background: var(--color-bg, #fff);
  color: var(--color-weak);
  cursor: pointer;
}
.msg-thread-btn:hover {
  background: var(--color-bg-hover, #f0f0f0);
}
</style>
