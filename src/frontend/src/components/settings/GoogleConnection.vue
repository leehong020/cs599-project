<script setup lang="ts">
// Google 连接管理。三种状态：未配置 / 未连接 / 已连接。
import { inject } from "vue";
import type { AppState } from "../../composables/useAppState";
import { startGoogleLogin, disconnectGoogle } from "../../api/auth";

const appState = inject<AppState>("appState")!;

async function handleDisconnect() {
  try {
    await disconnectGoogle();
    appState.state.googleConnected = false;
    appState.state.googleEmail = null;
    appState.setNotice?.("Google 已断开");
  } catch (e) {
    appState.setNotice?.(e instanceof Error ? e.message : "断开失败");
  }
}
</script>

<template>
  <div class="settings-content">
    <h3 style="font-size:16px;margin-bottom:14px;color:var(--color-heading)">Google 连接</h3>

    <!-- 未配置 OAuth -->
    <div
      v-if="!appState.state.oauthConfigured"
      class="google-badge disconnected"
      style="margin-bottom:12px"
    >
      <span class="google-badge-check">⚠️</span>
      <div>
        <div style="font-weight:600;font-size:13px;color:#92400e">OAuth 凭据未配置</div>
        <div style="font-size:12px;color:#a16207;margin-top:3px">
          将 google_oauth.json 放到项目根目录，或 .env 中填写 GOOGLE_CLIENT_ID
        </div>
      </div>
    </div>

    <!-- 已配置但未连接 -->
    <div
      v-else-if="!appState.state.googleConnected"
      class="google-badge disconnected"
      style="margin-bottom:12px"
    >
      <span class="google-badge-check">—</span>
      <div>
        <div style="font-weight:600;font-size:13px">未连接</div>
        <div v-if="appState.state.googleMessage" style="font-size:12px;color:var(--color-weak);margin-top:3px">
          {{ appState.state.googleMessage }}
        </div>
      </div>
    </div>

    <!-- 已连接 -->
    <div
      v-else
      class="google-badge connected"
      style="margin-bottom:12px"
    >
      <span class="google-badge-check">✓</span>
      <div>
        <div style="font-weight:600;font-size:13px">{{ appState.state.googleEmail }}</div>
        <div style="color:var(--color-success);font-size:11px">Gmail · Calendar 已授权</div>
      </div>
    </div>

    <div class="action-row">
      <button
        v-if="appState.state.oauthConfigured"
        class="btn"
        @click="startGoogleLogin"
      >
        {{ appState.state.googleConnected ? "重新连接" : "连接 Google" }}
      </button>
      <button
        v-if="appState.state.googleConnected"
        class="btn-secondary"
        @click="handleDisconnect"
      >
        断开连接
      </button>
    </div>
  </div>
</template>
