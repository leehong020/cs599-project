<script setup lang="ts">
// App.vue — 三栏布局壳。
// 负责：创建共享状态、provide 给子组件、加载初始化数据、切换视图。
import { provide, onMounted, ref } from "vue";
import { createAppState, type AppState } from "./composables/useAppState";
import { fetchHealth } from "./api/health";
import { fetchGoogleStatus } from "./api/auth";
import { fetchContacts, fetchProfile, fetchSignatures } from "./api/settings";
import AppSidebar from "./components/AppSidebar.vue";
import ChatView from "./components/chat/ChatView.vue";
import GmailView from "./components/gmail/GmailView.vue";
import CalendarView from "./components/calendar/CalendarView.vue";
import SettingsView from "./components/settings/SettingsView.vue";

// 共享状态
const { state, todoCount, setNotice, triggerRefresh } = createAppState();
provide<AppState>("appState", { state, todoCount, setNotice, triggerRefresh });

const isLoading = ref(true);
const globalError = ref<string | null>(null);

// 加载初始化数据
async function loadInitialData() {
  const query = new URLSearchParams(window.location.search);
  const authResult = query.get("google_auth");
  if (authResult === "connected") {
    state.notice = "Google 授权成功";
  } else if (authResult === "error" || authResult === "state_mismatch") {
    state.notice = "Google 授权失败";
  }

  try {
    await Promise.all([fetchHealth(), loadGoogleArea()]);
  } catch (e) {
    globalError.value = e instanceof Error ? e.message : "应用初始化失败";
  } finally {
    isLoading.value = false;
    window.history.replaceState({}, document.title, window.location.pathname);
  }
}

async function loadGoogleArea() {
  try {
    const gs = await fetchGoogleStatus();
    state.googleConnected = gs.connected;
    state.googleEmail = gs.email;
    state.googleNeedsReconnect = gs.needs_reconnect;
    state.googleMessage = gs.message;
    state.oauthConfigured = gs.oauth_configured;

    if (gs.connected) {
      const profile = await fetchProfile();
      state.profile = profile;
      const sigs = await fetchSignatures();
      state.signatures = sigs;
      state.contacts = await fetchContacts();
    }
  } catch {
    // Google 未连接不是致命错误
  }
}

onMounted(loadInitialData);
</script>

<template>
  <!-- 加载中 -->
  <div
    v-if="isLoading"
    style="display:flex;align-items:center;justify-content:center;height:100vh;color:var(--color-weak);font-size:16px"
  >
    正在启动 Mailflow Agent...
  </div>

  <!-- 三栏布局 -->
  <main v-else class="app-shell">
    <AppSidebar />

    <div class="main-content">
      <ChatView v-if="state.activeView === 'chat'" />
      <GmailView v-else-if="state.activeView === 'gmail'" />
      <CalendarView v-else-if="state.activeView === 'calendar'" />
      <SettingsView v-else-if="state.activeView === 'settings'" />
    </div>

    <!-- 全局通知 Toast -->
    <div
      v-if="state.notice"
      style="position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:10px 20px;border-radius:var(--radius-pill);background:var(--color-heading);color:#fff;font-size:14px;z-index:100;box-shadow:0 4px 16px rgba(0,0,0,0.15)"
    >
      {{ state.notice }}
    </div>
    <div
      v-if="globalError"
      style="position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:10px 20px;border-radius:var(--radius-pill);background:var(--color-error);color:#fff;font-size:14px;z-index:100"
    >
      {{ globalError }}
    </div>
  </main>
</template>
