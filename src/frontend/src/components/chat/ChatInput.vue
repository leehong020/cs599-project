<script setup lang="ts">
// 聊天输入区。支持文本输入和文件上传。
import { ref } from "vue";
import { uploadChatFile, type UploadedFile } from "../../api/files";

const input = ref("");
const attachedFile = ref<UploadedFile | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const uploadError = ref<string | null>(null);
const isUploading = ref(false);

const props = defineProps<{
  disabled?: boolean;
  threadId: string;
}>();

interface ChatSendPayload {
  displayMessage: string;
  modelMessage: string;
  fileRefs?: Record<string, unknown>[];
  attachments?: {
    filename: string;
    status: "succeeded" | "failed";
  }[];
}

const emit = defineEmits<{
  send: [payload: ChatSendPayload];
}>();

function handleSubmit() {
  const msg = input.value.trim();
  if (!msg && !attachedFile.value) return;

  let modelMessage = msg;
  const attachments = attachedFile.value
    ? [
        {
          filename: attachedFile.value.original_filename,
          status: attachedFile.value.extraction?.status ?? "failed",
        },
      ]
    : undefined;

  if (attachedFile.value) {
    const extraction = attachedFile.value.extraction;
    const fileHint = extraction?.status === "succeeded"
      ? `已上传附件「${attachedFile.value.original_filename}」，请结合附件解析内容处理。`
      : `已上传附件「${attachedFile.value.original_filename}」，但文件解析失败：${extraction?.error_message || "无可用文本"}`;
    modelMessage = msg ? `${msg}\n\n${fileHint}` : fileHint;
  }

  const refs = attachedFile.value
    ? [
        {
          ref_type: "uploaded_file",
          ref_id: attachedFile.value.id,
          filename: attachedFile.value.original_filename,
          extraction_id: attachedFile.value.extraction?.id ?? null,
          extraction_status: attachedFile.value.extraction?.status ?? "failed",
          // 文件全文只作为隐藏上下文传给 Assistant，不能拼进用户可见气泡。
          extracted_text: attachedFile.value.extraction?.text_content?.slice(0, 12000) ?? null,
          error_message: attachedFile.value.extraction?.error_message ?? null,
        },
      ]
    : undefined;

  emit("send", {
    displayMessage: msg || "请分析这个附件",
    modelMessage,
    fileRefs: refs,
    attachments,
  });
  input.value = "";
  attachedFile.value = null;
}

async function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;

  uploadError.value = null;
  isUploading.value = true;
  try {
    attachedFile.value = await uploadChatFile(file, props.threadId);
  } catch (error) {
    uploadError.value = error instanceof Error ? error.message : "文件上传失败";
  } finally {
    isUploading.value = false;
  }
}

function triggerFileInput() {
  fileInput.value?.click();
}

function removeAttachment() {
  attachedFile.value = null;
  if (fileInput.value) fileInput.value.value = "";
}
</script>

<template>
  <div class="chat-input-area">
    <!-- 附件预览 -->
    <div v-if="attachedFile" class="attachment-preview">
      <span class="attachment-icon">📄</span>
      <span class="attachment-name">
        {{ attachedFile.original_filename }}
        <small v-if="attachedFile.extraction?.status === 'failed'">解析失败</small>
      </span>
      <button type="button" class="attachment-remove" @click="removeAttachment">✕</button>
    </div>
    <div v-if="uploadError" class="attachment-error">{{ uploadError }}</div>

    <form class="chat-input-row" @submit.prevent="handleSubmit">
      <input
        ref="fileInput"
        type="file"
        accept=".txt,.md,.csv,.json,.log,.xml,.html,.htm,.py,.js,.ts,.vue,.docx,.pdf"
        style="display:none"
        @change="handleFileSelect"
      />
      <button
        type="button"
        class="attach-btn"
        :disabled="props.disabled || isUploading"
        title="上传文件（支持 txt, md, docx, pdf）"
        @click="triggerFileInput"
      >
        {{ isUploading ? "…" : "📎" }}
      </button>
      <input
        v-model="input"
        type="text"
        :disabled="props.disabled || isUploading"
        placeholder="描述你要做什么，例如：帮李明写邮件..."
        autofocus
      />
      <button
        type="submit"
        class="btn-send"
        :disabled="props.disabled || isUploading || (!input.trim() && !attachedFile)"
      >
        发送
      </button>
    </form>
    <div class="chat-input-hint">Mailflow Agent · 你的 AI 邮件和日程助理</div>
  </div>
</template>

<style scoped>
.attach-btn {
  background: none;
  border: 0;
  color: var(--color-weak);
  font-size: 20px;
  padding: 6px 10px;
  cursor: pointer;
  border-radius: 6px;
}
.attach-btn:hover {
  background: var(--color-border);
}
.attachment-preview {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  margin-bottom: 12px;
  background: var(--color-panel);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  font-size: 15px;
}
.attachment-icon {
  font-size: 18px;
}
.attachment-name {
  flex: 1;
  color: var(--color-body);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attachment-name small {
  margin-left: 8px;
  color: var(--color-error);
}
.attachment-error {
  margin-bottom: 12px;
  color: var(--color-error);
  font-size: 14px;
}
.attachment-remove {
  background: none;
  border: 0;
  color: var(--color-weak);
  cursor: pointer;
  font-size: 18px;
  padding: 4px 8px;
}
</style>
