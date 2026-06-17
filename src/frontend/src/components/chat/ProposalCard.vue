<script setup lang="ts">
// 内嵌在聊天流中的 Proposal 确认卡片。
// 邮件卡片蓝色系，日程卡片绿色系。
import type { ProposalItem } from "../../api/workflow";

const props = defineProps<{
  proposal: ProposalItem;
}>();

defineEmits<{
  approve: [];
  reject: [];
  revise: [];
  defer: [];
}>();

function isEmail(): boolean {
  return props.proposal.action_type === "send_email";
}

function title(): string {
  const p = props.proposal.payload as Record<string, unknown>;
  return isEmail()
    ? (typeof p.subject === "string" ? p.subject : "未命名邮件")
    : (typeof p.title === "string" ? p.title : "未命名日程");
}

function statusLabel(): string {
  if (props.proposal.status === "awaiting_confirmation") return "等待确认";
  if (props.proposal.status === "approved") return "已确认";
  return "草稿中";
}

function statusClass(): string {
  if (props.proposal.status === "awaiting_confirmation") return "awaiting";
  if (props.proposal.status === "approved") return "approved";
  return "draft";
}

function primaryActionLabel(): string {
  if (isEmail()) return "确认发送";
  return "创建日程";
}

function fieldValue(key: string): string {
  const v = (props.proposal.payload as Record<string, unknown>)[key];
  if (typeof v === "string") return v;
  if (typeof v === "number") return String(v);
  if (typeof v === "boolean") return v ? "是" : "否";
  return "";
}

function fingerprintShort(): string {
  return props.proposal.fingerprint.slice(0, 12);
}

function hasConflict(): boolean {
  if (isEmail()) return false;
  return !!(props.proposal.payload as Record<string, unknown>).conflict_override;
}

function formatAddressList(key: string): string {
  const v = (props.proposal.payload as Record<string, unknown>)[key];
  if (!Array.isArray(v)) return "";
  return v
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        return (item as Record<string, unknown>).email || "";
      }
      return "";
    })
    .filter(Boolean)
    .join(", ");
}
</script>

<template>
  <div class="proposal-card" :class="isEmail() ? 'email' : 'calendar'">
    <div class="proposal-header">
      <div class="proposal-title">
        <span>{{ isEmail() ? "📧" : "📅" }}</span>
        {{ title() }}
      </div>
      <span class="proposal-status" :class="statusClass()">
        {{ statusLabel() }}
      </span>
    </div>

    <div class="proposal-body">
      <!-- 邮件字段 -->
      <template v-if="isEmail()">
        <div class="proposal-field">
          <span class="proposal-field-label">发件</span>
          <span class="proposal-field-value">{{ fieldValue("sender_email") }}</span>
        </div>
        <div class="proposal-field">
          <span class="proposal-field-label">收件</span>
          <span class="proposal-field-value">{{ formatAddressList("to") }}</span>
        </div>
        <div class="proposal-field">
          <span class="proposal-field-label">主题</span>
          <span class="proposal-field-value">{{ fieldValue("subject") }}</span>
        </div>
        <div class="proposal-preview">
          {{ fieldValue("body") }}
        </div>
      </template>

      <!-- 日程字段 -->
      <template v-else>
        <div class="proposal-field">
          <span class="proposal-field-label">时间</span>
          <span class="proposal-field-value">
            {{ fieldValue("start_time") }} - {{ fieldValue("end_time") || fieldValue("duration_minutes") + " 分钟" }}
          </span>
        </div>
        <div class="proposal-field">
          <span class="proposal-field-label">时区</span>
          <span class="proposal-field-value">{{ fieldValue("timezone") }}</span>
        </div>
        <div class="proposal-field">
          <span class="proposal-field-label">参会</span>
          <span class="proposal-field-value">{{ formatAddressList("attendees") }}</span>
        </div>
        <div v-if="fieldValue('location')" class="proposal-field">
          <span class="proposal-field-label">地点</span>
          <span class="proposal-field-value">{{ fieldValue("location") }}</span>
        </div>
        <div v-if="hasConflict()" class="proposal-conflict">
          <span class="proposal-conflict-icon">⚠️</span>
          <div class="proposal-conflict-text">
            该时段存在日程冲突
          </div>
        </div>
      </template>
    </div>

    <div class="proposal-actions">
      <button
        class="btn-primary"
        :disabled="proposal.status !== 'awaiting_confirmation'"
        @click="$emit('approve')"
      >
        {{ primaryActionLabel() }}
      </button>
      <button class="btn-secondary" @click="$emit('revise')">修改</button>
      <button class="btn-secondary" @click="$emit('defer')">暂缓</button>
      <span class="proposal-fingerprint">
        v{{ proposal.version }} · {{ fingerprintShort() }}
      </span>
    </div>
  </div>
</template>
