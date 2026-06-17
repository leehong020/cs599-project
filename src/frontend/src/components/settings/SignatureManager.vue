<script setup lang="ts">
// 单一署名设置。界面只暴露一个署名内容，避免用户在“标签/默认”之间来回选择。
// 后端仍使用 signatures 表保存，但这里始终把当前署名保存为默认署名。
import { computed, inject, ref, watch } from "vue";
import type { AppState } from "../../composables/useAppState";
import { createSignature, fetchSignatures, updateSignature } from "../../api/settings";

const appState = inject<AppState>("appState")!;

const content = ref("");
const isSaving = ref(false);
const error = ref<string | null>(null);

// 兼容历史数据：优先使用默认署名；如果没有默认署名，就使用第一条署名。
const currentSignature = computed(() => {
  return (
    appState.state.signatures.find((item) => item.is_default)
    ?? appState.state.signatures[0]
    ?? null
  );
});

watch(
  currentSignature,
  (signature) => {
    content.value = signature?.content ?? "";
  },
  { immediate: true },
);

async function refreshSignatures() {
  appState.state.signatures = await fetchSignatures();
}

async function handleSave() {
  const signatureText = content.value.trim();
  if (!signatureText) {
    error.value = "请填写署名内容";
    return;
  }

  isSaving.value = true;
  error.value = null;
  try {
    if (currentSignature.value) {
      await updateSignature(currentSignature.value.id, {
        label: currentSignature.value.label || "默认署名",
        content: signatureText,
        is_default: true,
      });
    } else {
      await createSignature({
        label: "默认署名",
        content: signatureText,
        is_default: true,
      });
    }
    await refreshSignatures();
    appState.setNotice?.("署名已保存");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "保存署名失败";
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <div class="settings-content">
    <h3 style="font-size:16px;margin-bottom:14px;color:var(--color-heading)">署名</h3>
    <form @submit.prevent="handleSave" style="display:grid;gap:10px;max-width:480px">
      <div class="form-group">
        <label class="form-label">署名</label>
        <input class="form-input" v-model="content" />
      </div>
      <button class="btn" type="submit" :disabled="isSaving">
        {{ isSaving ? "保存中" : "保存署名" }}
      </button>
      <p v-if="error" class="inline-error">{{ error }}</p>
    </form>
  </div>
</template>
