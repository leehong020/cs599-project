<script setup lang="ts">
// 联系人管理。联系人是邮件收件人和日程参会人的共同事实来源。
import { inject, reactive, ref } from "vue";
import type { AppState } from "../../composables/useAppState";
import {
  createContact,
  deleteContact,
  fetchContacts,
  updateContact,
  type Contact,
} from "../../api/settings";

const appState = inject<AppState>("appState")!;

const form = reactive({ display_name: "", email: "" });
const editingId = ref<string | null>(null);
const isSaving = ref(false);
const error = ref<string | null>(null);

function startEdit(contact: Contact) {
  editingId.value = contact.id;
  form.display_name = contact.display_name;
  form.email = contact.email;
}

function resetForm() {
  editingId.value = null;
  form.display_name = "";
  form.email = "";
}

async function reloadContacts() {
  appState.state.contacts = await fetchContacts();
}

async function handleSubmit() {
  if (!form.display_name.trim() || !form.email.trim()) return;
  isSaving.value = true;
  error.value = null;
  try {
    const payload = {
      display_name: form.display_name.trim(),
      email: form.email.trim(),
    };
    if (editingId.value) {
      await updateContact(editingId.value, payload);
      appState.setNotice?.("联系人已更新");
    } else {
      await createContact(payload);
      appState.setNotice?.("联系人已创建");
    }
    await reloadContacts();
    resetForm();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "保存联系人失败";
  } finally {
    isSaving.value = false;
  }
}

async function handleDelete(contactId: string) {
  isSaving.value = true;
  error.value = null;
  try {
    await deleteContact(contactId);
    await reloadContacts();
    if (editingId.value === contactId) resetForm();
    appState.setNotice?.("联系人已删除");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "删除联系人失败";
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <div class="settings-content">
    <h3 style="font-size:16px;margin-bottom:14px;color:var(--color-heading)">联系人</h3>

    <div v-if="appState.state.contacts.length" style="display:grid;gap:8px;max-width:520px;margin-bottom:14px">
      <div
        v-for="contact in appState.state.contacts"
        :key="contact.id"
        class="signature-item"
      >
        <div class="signature-item-body">
          <span class="signature-item-label">{{ contact.display_name }}</span>
          <div class="signature-item-content">{{ contact.email }}</div>
        </div>
        <div style="display:flex;gap:6px">
          <button class="btn-secondary" style="font-size:12px;padding:5px 12px" @click="startEdit(contact)">
            编辑
          </button>
          <button class="btn-danger" style="font-size:12px;padding:5px 12px" @click="handleDelete(contact.id)">
            删除
          </button>
        </div>
      </div>
    </div>
    <p v-else style="color:var(--color-weak);font-size:14px;margin-bottom:14px">
      暂无联系人
    </p>

    <form @submit.prevent="handleSubmit" style="display:grid;gap:8px;max-width:400px">
      <div class="form-group">
        <label class="form-label">姓名</label>
        <input class="form-input" v-model="form.display_name" />
      </div>
      <div class="form-group">
        <label class="form-label">邮箱</label>
        <input class="form-input" v-model="form.email" type="email" />
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn" type="submit" :disabled="isSaving">
          {{ editingId ? "保存联系人" : "创建联系人" }}
        </button>
        <button v-if="editingId" class="btn-secondary" type="button" @click="resetForm">
          取消
        </button>
      </div>
      <p v-if="error" class="inline-error">{{ error }}</p>
    </form>
  </div>
</template>
