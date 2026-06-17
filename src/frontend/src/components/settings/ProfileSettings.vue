<script setup lang="ts">
// 个人设置表单。时区、发件账号、默认日历、会议时长等。
import { ref, reactive, inject } from "vue";
import type { AppState } from "../../composables/useAppState";
import { saveProfile, type ProfileForm } from "../../api/settings";

const appState = inject<AppState>("appState")!;

const form = reactive<ProfileForm>({
  timezone: (appState.state.profile?.timezone as string) || null,
  default_calendar_id: (appState.state.profile?.default_calendar_id as string) || null,
  default_signature_id: (appState.state.profile?.default_signature_id as string) || null,
  default_sender_email: appState.state.profile?.default_sender_email || appState.state.googleEmail || null,
  default_meeting_duration_minutes:
    (appState.state.profile?.default_meeting_duration_minutes as number) || null,
  meeting_buffer_minutes:
    (appState.state.profile?.meeting_buffer_minutes as number) || 0,
  working_hours: null,
  lunch_break: null,
  email_tone_internal: null,
  email_tone_external: null,
});

const isSaving = ref(false);
const error = ref<string | null>(null);

async function handleSave() {
  isSaving.value = true;
  error.value = null;
  try {
    const result = await saveProfile(form);
    appState.state.profile = result;
    appState.setNotice?.("设置已保存");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "保存失败";
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <div class="settings-content">
    <h3 style="font-size:16px;margin-bottom:14px;color:var(--color-heading)">个人设置</h3>
    <form
      @submit.prevent="handleSave"
      style="display:grid;gap:12px;max-width:520px"
    >
      <div class="form-group">
        <label class="form-label">时区</label>
        <input class="form-input" v-model="form.timezone" placeholder="Asia/Shanghai" />
      </div>
      <div class="form-group">
        <label class="form-label">发件账号</label>
        <input class="form-input" v-model="form.default_sender_email" />
      </div>
      <div class="form-group">
        <label class="form-label">默认日历</label>
        <input class="form-input" v-model="form.default_calendar_id" placeholder="primary" />
      </div>
      <div class="form-row two-col">
        <div class="form-group">
          <label class="form-label">默认会议时长（分钟）</label>
          <input
            class="form-input"
            v-model.number="form.default_meeting_duration_minutes"
            type="number"
            min="1"
          />
        </div>
        <div class="form-group">
          <label class="form-label">缓冲时间（分钟）</label>
          <input
            class="form-input"
            v-model.number="form.meeting_buffer_minutes"
            type="number"
            min="0"
          />
        </div>
      </div>
      <button class="btn" type="submit" :disabled="isSaving">
        {{ isSaving ? "保存中" : "保存设置" }}
      </button>
      <p v-if="error" class="inline-error">{{ error }}</p>
    </form>
  </div>
</template>
