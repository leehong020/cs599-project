<script setup lang="ts">
// 日视图 / 周视图时间轴。按小时分段展示当日日程。
import { computed } from "vue";
import type { CalendarEventResponse } from "../../api/calendar";

const props = defineProps<{
  viewMode: "day" | "week";
  date: Date;
  events: CalendarEventResponse[];
}>();

const emit = defineEmits<{
  selectEvent: [event: CalendarEventResponse];
}>();

// 生成小时槽位（7:00 - 22:00）
const hours = Array.from({ length: 16 }, (_, i) => i + 7);

// 展示的日期列表（日视图 1 天，周视图 7 天）
const displayDates = computed(() => {
  if (props.viewMode === "day") {
    return [props.date];
  }
  const startOfWeek = new Date(props.date);
  const dow = startOfWeek.getDay(); // 0=Sun
  const mondayOffset = dow === 0 ? -6 : 1 - dow;
  startOfWeek.setDate(startOfWeek.getDate() + mondayOffset);

  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startOfWeek);
    d.setDate(d.getDate() + i);
    return d;
  });
});

function formatDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function eventDateStr(dateTime?: string): string {
  if (!dateTime) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateTime)) return dateTime;
  const d = new Date(dateTime);
  return Number.isNaN(d.getTime()) ? dateTime.slice(0, 10) : formatDateStr(d);
}

function isToday(d: Date): boolean {
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

function formatDayHeader(d: Date): string {
  const days = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return `${d.getMonth() + 1}/${d.getDate()} ${days[d.getDay()]}`;
}

function getEventsForDateAndHour(date: Date, hour: number): CalendarEventResponse[] {
  const dateStr = formatDateStr(date);
  return props.events.filter((ev) => {
    const evDate = eventDateStr(ev.start?.date_time);
    if (evDate !== dateStr) return false;
    try {
      const evHour = new Date(ev.start!.date_time!).getHours();
      return evHour === hour;
    } catch {
      return false;
    }
  });
}

function formatEventTime(ev: CalendarEventResponse): string {
  try {
    const s = new Date(ev.start!.date_time!);
    const e = ev.end?.date_time ? new Date(ev.end.date_time) : null;
    const startStr = s.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
    const endStr = e
      ? e.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
      : "";
    return endStr ? `${startStr} - ${endStr}` : startStr;
  } catch {
    return "";
  }
}
</script>

<template>
  <div class="day-view-wrapper">
    <!-- 日期头 -->
    <div
      class="day-headers"
      :class="{ week: viewMode === 'week' }"
    >
      <div v-for="d in displayDates" :key="d.toISOString()" class="day-header-cell">
        <span class="day-header-date">{{ formatDayHeader(d) }}</span>
        <span v-if="isToday(d)" class="today-badge">今天</span>
      </div>
    </div>

    <!-- 时间轴 -->
    <div class="day-body">
      <div class="day-body-scroll">
        <div
          v-for="hour in hours"
          :key="hour"
          class="hour-row"
        >
          <div class="hour-label">{{ String(hour).padStart(2, "0") }}:00</div>
          <div
            v-for="d in displayDates"
            :key="d.toISOString()"
            class="hour-slot"
          >
            <div
              v-for="ev in getEventsForDateAndHour(d, hour)"
              :key="ev.id"
              class="hour-event"
              @click="emit('selectEvent', ev)"
            >
              <strong>{{ ev.summary || "无标题" }}</strong>
              <span>{{ formatEventTime(ev) }}</span>
              <span v-if="ev.location">📍 {{ ev.location }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.day-view-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.day-headers {
  display: flex;
  border-bottom: 1px solid var(--color-border, #e0e0e0);
  flex-shrink: 0;
}
.day-header-cell {
  flex: 1;
  text-align: center;
  padding: 10px 4px;
  font-size: 14px;
  border-right: 1px solid var(--color-border, #e0e0e0);
}
.day-header-cell:last-child {
  border-right: none;
}
.day-headers.week .day-header-cell {
  font-size: 13px;
}
.day-header-date {
  color: var(--color-heading, #1a1a1a);
  font-weight: 600;
  display: block;
}
.today-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 8px;
  background: var(--color-primary, #3b82f6);
  color: #fff;
  font-size: 10px;
  margin-top: 3px;
}
.day-body {
  flex: 1;
  overflow: hidden;
}
.day-body-scroll {
  overflow-y: auto;
  height: 100%;
}
.hour-row {
  display: flex;
  border-bottom: 1px solid var(--color-border, #f0f0f0);
  min-height: 56px;
}
.hour-label {
  width: 56px;
  padding: 6px 8px;
  font-size: 12px;
  color: var(--color-weak);
  text-align: right;
  flex-shrink: 0;
  border-right: 1px solid var(--color-border, #e0e0e0);
}
.hour-slot {
  flex: 1;
  padding: 3px;
  min-height: 56px;
  border-right: 1px solid var(--color-border, #f5f5f5);
}
.hour-slot:last-child {
  border-right: none;
}
.hour-event {
  padding: 5px 8px;
  margin: 2px 0;
  border-radius: 5px;
  background: var(--color-calendar-bg, #ecfdf5);
  border-left: 3px solid var(--color-calendar-btn, #059669);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.hour-event:hover {
  background: var(--color-calendar-border, #a7f3d0);
}
.hour-event strong {
  font-size: 12px;
  color: var(--color-heading, #1a1a1a);
}
.hour-event span {
  color: var(--color-weak);
  font-size: 11px;
}
</style>
