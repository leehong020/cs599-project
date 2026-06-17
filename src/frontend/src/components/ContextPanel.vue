<script setup lang="ts">
// 右侧 240px 上下文面板。始终可见，从上到下：待办列表 → Google 状态 → 快捷操作。
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
