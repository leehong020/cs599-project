<script setup lang="ts">
// 左侧竖向会话列表。类似 ChatGPT / Claude 的会话侧边栏。
defineProps<{
  sessions: { id: string; title: string }[];
  activeId: string;
}>();

const emit = defineEmits<{
  (e: "switch", threadId: string): void;
  (e: "delete", threadId: string): void;
  (e: "new"): void;
}>();
</script>

<template>
  <div class="session-sidebar">
    <button class="new-session-btn" @click="emit('new')">
      <span class="new-session-icon">+</span>
      <span>新会话</span>
    </button>

    <div class="session-list">
      <button
        v-for="s in sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === activeId }"
        :title="s.title"
        @click="emit('switch', s.id)"
      >
        <span class="session-icon">💬</span>
        <span class="session-title">{{ s.title || '新会话' }}</span>
        <span
          class="session-delete"
          @click.stop="emit('delete', s.id)"
        >×</span>
      </button>

      <div v-if="sessions.length === 0" class="session-empty">
        暂无会话
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-sidebar {
  width: 300px;
  min-width: 280px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f9fafb;
  border-right: 1px solid var(--color-border, #e5e7eb);
  overflow: hidden;
}
.new-session-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 16px 14px 10px;
  padding: 13px 18px;
  border: 1px dashed var(--color-border, #d1d5db);
  border-radius: 8px;
  background: #fff;
  font-size: 15px;
  color: var(--color-primary, #3b82f6);
  cursor: pointer;
  transition: all 0.15s;
  font-weight: 500;
}
.new-session-btn:hover {
  background: var(--color-primary, #3b82f6);
  color: #fff;
  border-color: var(--color-primary, #3b82f6);
}
.new-session-icon {
  font-size: 20px;
  font-weight: 700;
}
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px 14px;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 44px;
  padding: 11px 14px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 15px;
  color: var(--color-body, #374151);
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
  position: relative;
}
.session-item:hover {
  background: #e5e7eb;
}
.session-item.active {
  background: #dbeafe;
  color: var(--color-primary, #1d4ed8);
  font-weight: 600;
}
.session-icon {
  font-size: 17px;
  flex-shrink: 0;
}
.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-delete {
  opacity: 0;
  font-size: 18px;
  font-weight: 700;
  color: #9ca3af;
  flex-shrink: 0;
  padding: 0 4px;
  transition: opacity 0.1s, color 0.1s;
}
.session-item:hover .session-delete {
  opacity: 0.6;
}
.session-delete:hover {
  color: #ef4444;
  opacity: 1 !important;
}
.session-empty {
  padding: 22px 14px;
  font-size: 14px;
  color: var(--color-weak, #9ca3af);
  text-align: center;
}
</style>
