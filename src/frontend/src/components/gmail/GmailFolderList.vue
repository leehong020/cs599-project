<script setup lang="ts">
// Gmail 文件夹导航。展示收件箱、已发送、草稿箱等，支持点击切换和未读计数。
import { ref } from "vue";

export interface FolderItem {
  id: string;
  label: string;
  icon: string;
  query: string;
  count?: number;
}

const folders: FolderItem[] = [
  { id: "inbox", label: "收件箱", icon: "📥", query: "in:inbox" },
  { id: "sent", label: "已发送", icon: "📤", query: "in:sent" },
  { id: "drafts", label: "草稿箱", icon: "📝", query: "is:draft" },
  { id: "starred", label: "星标", icon: "⭐", query: "is:starred" },
  { id: "spam", label: "垃圾邮件", icon: "🗑️", query: "in:spam" },
  { id: "trash", label: "已删除", icon: "🚮", query: "in:trash" },
];

const activeFolder = ref<string>("inbox");

const emit = defineEmits<{
  select: [folder: FolderItem];
}>();

function selectFolder(folder: FolderItem) {
  activeFolder.value = folder.id;
  emit("select", folder);
}
</script>

<template>
  <nav class="folder-nav" aria-label="邮件文件夹">
    <div class="folder-nav-title">邮件文件夹</div>
    <button
      v-for="f in folders"
      :key="f.id"
      class="folder-item"
      :class="{ active: activeFolder === f.id }"
      @click="selectFolder(f)"
    >
      <span class="folder-icon">{{ f.icon }}</span>
      <span class="folder-label">{{ f.label }}</span>
      <span v-if="f.count" class="folder-count">{{ f.count }}</span>
    </button>
  </nav>
</template>

<style scoped>
.folder-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 0;
  min-width: 180px;
  border-right: 1px solid var(--color-border, #e0e0e0);
}
.folder-nav-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-weak);
  padding: 6px 14px 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.folder-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 15px;
  color: var(--color-text, #333);
  border-radius: 8px;
  margin: 0 8px;
  text-align: left;
  transition: background 0.15s;
}
.folder-item:hover {
  background: var(--color-bg-hover, #f0f0f0);
}
.folder-item.active {
  background: var(--color-primary-light, #e8f0fe);
  color: var(--color-primary, #1a73e8);
  font-weight: 600;
}
.folder-icon {
  font-size: 18px;
  flex-shrink: 0;
}
.folder-label {
  flex: 1;
}
.folder-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-weak);
  background: var(--color-bg-hover, #e8e8e8);
  padding: 2px 8px;
  border-radius: 10px;
  min-width: 22px;
  text-align: center;
}
</style>
