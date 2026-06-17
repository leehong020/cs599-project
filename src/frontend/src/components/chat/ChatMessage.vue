<script setup lang="ts">
// 单条消息气泡。支持 user / assistant / system 三种角色。
// 对 assistant 消息进行基本 Markdown 渲染。
import { computed } from "vue";

const props = defineProps<{
  role: "user" | "assistant" | "system";
  content: string;
  systemType?: "warning" | "error" | "success";
  attachments?: {
    filename: string;
    status: "succeeded" | "failed";
  }[];
}>();

function renderMarkdown(text: string): string {
  if (!text) return "";
  // 转义 HTML 防止 XSS
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // 代码块（```...```）
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g,
    '<pre><code>$2</code></pre>');
  // 行内代码 `...`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // 粗体 **text**
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // 斜体 *text*
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // 标题 ###, ##
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  // 无序列表项 - item 或 * item
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  // 有序列表项 1. item
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  // 包裹连续的 <li> 为 <ul>
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
  // 换行转 <br>（在非块级元素后）
  html = html.replace(/\n/g, '<br>');

  return html;
}

const renderedContent = computed(() => {
  if (props.role === "assistant") {
    return renderMarkdown(props.content);
  }
  return props.content
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>");
});
</script>

<template>
  <div
    class="chat-message-stack"
    :class="[role, systemType && `system ${systemType}`]"
  >
    <div v-if="attachments?.length" class="message-attachments">
      <div
        v-for="attachment in attachments"
        :key="attachment.filename"
        class="message-attachment-chip"
        :class="{ failed: attachment.status === 'failed' }"
      >
        <span class="message-attachment-icon">📄</span>
        <span class="message-attachment-name">{{ attachment.filename }}</span>
        <span v-if="attachment.status === 'failed'" class="message-attachment-status">解析失败</span>
      </div>
    </div>
    <div class="chat-bubble" :class="[role, systemType && `system ${systemType}`]">
      <span v-if="role === 'assistant'" v-html="renderedContent"></span>
      <span v-else v-html="renderedContent"></span>
    </div>

  </div>
</template>

<style scoped>
.chat-message-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 860px;
}

.message-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.message-attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 360px;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #fff;
  color: var(--color-body);
  font-size: 14px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.message-attachment-chip.failed {
  border-color: var(--color-error-border);
  background: var(--color-error-bg);
}

.message-attachment-icon {
  flex-shrink: 0;
  font-size: 16px;
}

.message-attachment-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-attachment-status {
  flex-shrink: 0;
  color: var(--color-error);
  font-size: 12px;
  font-weight: 600;
}

.chat-bubble :deep(ul) {
  padding-left: 22px;
  margin: 8px 0;
}

.chat-bubble :deep(li) {
  margin: 5px 0;
}

.chat-bubble :deep(strong) {
  color: var(--color-heading);
}

.chat-message-stack.user {
  align-self: flex-end;
  align-items: flex-end;
}

.chat-message-stack.assistant {
  align-self: flex-start;
  align-items: flex-start;
}

.chat-message-stack.system {
  align-self: center;
  align-items: center;
}

</style>
