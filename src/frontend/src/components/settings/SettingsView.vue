<script setup lang="ts">
// 设置页。子标签切换：个人设置 / 署名管理 / Google 连接。
import { ref } from "vue";
import ProfileSettings from "./ProfileSettings.vue";
import SignatureManager from "./SignatureManager.vue";
import ContactManager from "./ContactManager.vue";
import GoogleConnection from "./GoogleConnection.vue";

const activeTab = ref("profile");

const tabs = [
  { id: "profile", label: "个人设置" },
  { id: "signatures", label: "署名管理" },
  { id: "contacts", label: "联系人" },
  { id: "google", label: "Google 连接" },
];
</script>

<template>
  <div class="chat-view">
    <div class="view-header">
      <h1>⚙️ 设置</h1>
    </div>
    <div class="settings-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="settings-tab"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>
    <ProfileSettings v-if="activeTab === 'profile'" />
    <SignatureManager v-else-if="activeTab === 'signatures'" />
    <ContactManager v-else-if="activeTab === 'contacts'" />
    <GoogleConnection v-else />
  </div>
</template>
