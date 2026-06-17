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
    <div style="color:var(--color-weak);font-size:13px">发件：{{ detail.from_email }}</div>
    <div style="color:var(--color-weak);font-size:13px">收件：{{ detail.to?.join(", ") }}</div>
    <pre>{{ detail.body?.text }}</pre>
  </div>
</template>
