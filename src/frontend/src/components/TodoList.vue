<script setup lang="ts">
// 待办摘要列表。从 AppState 读取 todos，展示人类可读状态。
import { inject } from "vue";
import type { AppState } from "../composables/useAppState";

const appState = inject<AppState>("appState")!;
</script>

<template>
  <div class="panel-section">
    <div class="panel-title">
      待办事项
      <span v-if="appState.todoCount" class="panel-badge">
        {{ appState.todoCount }}
      </span>
    </div>
    <div
      v-for="todo in appState.state.todos"
      :key="todo.id"
      class="todo-item"
    >
      <span class="todo-item-icon">{{ todo.icon }}</span>
      <div class="todo-item-info">
        <div class="todo-item-title">{{ todo.title }}</div>
        <div class="todo-item-desc">{{ todo.desc }}</div>
        <span class="todo-item-status" :class="todo.status">
          {{ todo.status === "awaiting" ? "等待确认" : "草稿中" }}
        </span>
      </div>
    </div>
    <div
      v-if="!appState.state.todos.length"
      style="color:var(--color-weak);font-size:11px;padding:4px 0"
    >
      暂无待办事项
    </div>
  </div>
</template>
