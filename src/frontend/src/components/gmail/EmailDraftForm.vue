<script setup lang="ts">
// 新邮件草稿表单。提交时调用后端 API 创建本地 Artifact。
import { ref, reactive, inject } from "vue";
import type { AppState } from "../../composables/useAppState";
import {
  prepareNewEmailDraft,
  type EmailArtifactResponse,
  type EmailAddress,
} from "../../api/gmail";

const appState = inject<AppState>("appState")!;

const form = reactive({
  to: "",
  subject: "",
  body: "",
  signature_policy: "no_signature",
});

const isSubmitting = ref(false);
const error = ref<string | null>(null);

const emit = defineEmits<{
  created: [artifact: EmailArtifactResponse];
}>();

function parseAddressList(value: string): EmailAddress[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((email) => ({ email, name: null }));
}

async function handleSubmit() {
  if (!form.to.trim() || !form.subject.trim()) return;
  isSubmitting.value = true;
  error.value = null;
  try {
    const senderEmail =
      appState.state.profile?.default_sender_email ||
      appState.state.googleEmail ||
      "";
    const artifact = await prepareNewEmailDraft({
      thread_id: null,
      sender_email: senderEmail,
      to: parseAddressList(form.to),
      cc: [],
      bcc: [],
      subject: form.subject.trim(),
      body: form.body.trim(),
      signature_policy: form.signature_policy,
    });
    emit("created", artifact);
    form.to = "";
    form.subject = "";
    form.body = "";
  } catch (e) {
    error.value = e instanceof Error ? e.message : "创建草稿失败";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <form
    @submit.prevent="handleSubmit"
    style="display:grid;gap:10px;margin-top:12px"
  >
    <h3 style="font-size:15px;color:var(--color-heading)">新邮件草稿</h3>
    <div class="form-group">
      <label class="form-label">收件人</label>
      <input class="form-input" v-model="form.to" placeholder="name@example.com" />
    </div>
    <div class="form-group">
      <label class="form-label">主题</label>
      <input class="form-input" v-model="form.subject" />
    </div>
    <div class="form-group">
      <label class="form-label">正文</label>
      <textarea class="form-input form-textarea" v-model="form.body" rows="5" />
    </div>
    <button class="btn" type="submit" :disabled="isSubmitting">
      {{ isSubmitting ? "创建中" : "保存本地草稿" }}
    </button>
    <p v-if="error" class="inline-error">{{ error }}</p>
  </form>
</template>
