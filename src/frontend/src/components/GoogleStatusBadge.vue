<script setup lang="ts">
// 右侧面板 Google 账号状态徽章。
import { inject } from "vue";
import type { AppState } from "../composables/useAppState";

const appState = inject<AppState>("appState")!;
</script>

<template>
  <!-- 未配置 OAuth -->
  <div v-if="!appState.state.oauthConfigured" class="google-badge disconnected">
    <span class="google-badge-check">⚠️</span>
    <div>
      <div style="font-weight:600;font-size:13px;color:#92400e">OAuth 未配置</div>
      <div style="font-size:11px;color:#a16207">放置 google_oauth.json 后重启</div>
    </div>
  </div>

  <!-- 已连接 -->
  <div
    v-else-if="appState.state.googleConnected"
    class="google-badge connected"
  >
    <span class="google-badge-check">✓</span>
    <div>
      <div style="font-weight:600;font-size:13px">
        {{ appState.state.googleEmail }}
      </div>
      <div style="color:var(--color-success);font-size:11px">Gmail · Calendar 已授权</div>
    </div>
  </div>

  <!-- 已配置未连接 -->
  <div v-else class="google-badge disconnected">
    <span class="google-badge-check">—</span>
    <div>
      <div style="font-weight:600;font-size:13px">未连接 Google</div>
      <div style="color:var(--color-weak);font-size:11px">到设置页连接账号</div>
    </div>
  </div>
</template>
