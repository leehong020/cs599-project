<script setup lang="ts">
// 左侧 72px 图标导航栏。4 个导航项 + 品牌标识 M。
// 点击切换 activeView，通过 inject 获取共享状态。
import { inject } from "vue";
import type { AppState } from "../composables/useAppState";

const appState = inject<AppState>("appState")!;

const navItems = [
  { id: "chat", icon: "💬", label: "聊天" },
  { id: "gmail", icon: "📧", label: "Gmail" },
  { id: "calendar", icon: "📅", label: "Calendar" },
  { id: "settings", icon: "⚙️", label: "设置" },
];

function switchView(viewId: string) {
  appState.state.activeView = viewId;
}
</script>

<template>
  <nav class="icon-sidebar" aria-label="主导航">
    <div class="icon-sidebar-brand" title="Mailflow Agent">M</div>
    <button
      v-for="item in navItems"
      :key="item.id"
      class="icon-sidebar-item"
      :class="{ active: appState.state.activeView === item.id }"
      :title="item.label"
      :aria-label="item.label"
      @click="switchView(item.id)"
    >
      {{ item.icon }}
    </button>
    <div class="icon-sidebar-spacer"></div>
  </nav>
</template>
