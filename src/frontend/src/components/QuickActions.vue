<script setup lang="ts">
// 右侧面板快捷操作按钮：上传文件、导出 Markdown。
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
