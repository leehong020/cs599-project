<script setup lang="ts">
// 月视图日历网格。显示当月所有日期，日程事件卡片叠加在日期格子上。
import { computed } from "vue";
import type { CalendarEventResponse } from "../../api/calendar";

const props = defineProps<{
  year: number;
  month: number; // 1-12
  events: CalendarEventResponse[];
  selectedDate: string | null;
}>();

const emit = defineEmits<{
  selectDate: [dateStr: string];
  selectEvent: [event: CalendarEventResponse];
}>();

// 当月第一天和最后一天
const firstDay = computed(() => new Date(props.year, props.month - 1, 1));
const lastDay = computed(() => new Date(props.year, props.month, 0));
const daysInMonth = computed(() => lastDay.value.getDate());
// 第一天是周几（0=周日）
const startDow = computed(() => firstDay.value.getDay());

// 生成日历格子（含前后月填充）
const calendarDays = computed(() => {
  const days: {
    date: Date;
    dateStr: string;
    isCurrentMonth: boolean;
    isToday: boolean;
    events: CalendarEventResponse[];
  }[] = [];

  // 前月填充
  const prevMonthLastDay = new Date(props.year, props.month - 1, 0).getDate();
  for (let i = startDow.value - 1; i >= 0; i--) {
    const d = new Date(props.year, props.month - 2, prevMonthLastDay - i);
    days.push({
      date: d,
      dateStr: formatDateStr(d),
      isCurrentMonth: false,
      isToday: isToday(d),
      events: [],
    });
  }

  // 当月
  for (let day = 1; day <= daysInMonth.value; day++) {
    const d = new Date(props.year, props.month - 1, day);
    const dateStr = formatDateStr(d);
    days.push({
      date: d,
      dateStr,
      isCurrentMonth: true,
      isToday: isToday(d),
      events: getEventsForDate(dateStr),
    });
  }

  // 后月填充
  const remaining = 42 - days.length; // 6 rows * 7 days
  for (let i = 1; i <= remaining; i++) {
    const d = new Date(props.year, props.month, i);
    days.push({
      date: d,
      dateStr: formatDateStr(d),
      isCurrentMonth: false,
      isToday: isToday(d),
      events: [],
    });
  }

  return days;
});

const weekDays = ["一", "二", "三", "四", "五", "六", "日"];

function formatDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function isToday(d: Date): boolean {
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function getEventsForDate(dateStr: string): CalendarEventResponse[] {
  return props.events.filter((ev) => {
    const evDate = ev.start?.date_time?.slice(0, 10);
    return evDate === dateStr;
  });
}

function formatTime(dateTime?: string): string {
  if (!dateTime) return "";
  try {
    return new Date(dateTime).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

const monthLabel = computed(() => `${props.year}年${props.month}月`);
</script>

<template>
  <div class="calendar-grid-wrapper">
    <div class="calendar-weekdays">
      <div v-for="wd in weekDays" :key="wd" class="weekday-cell">{{ wd }}</div>
    </div>
    <div class="calendar-grid">
      <div
        v-for="day in calendarDays"
        :key="day.dateStr"
        class="calendar-cell"
        :class="{
          'other-month': !day.isCurrentMonth,
          today: day.isToday,
          selected: selectedDate === day.dateStr,
        }"
        @click="emit('selectDate', day.dateStr)"
      >
        <span class="cell-date">{{ day.date.getDate() }}</span>
        <div class="cell-events">
          <div
            v-for="ev in day.events.slice(0, 3)"
            :key="ev.id"
            class="cell-event"
            :title="ev.summary || '无标题'"
            @click.stop="emit('selectEvent', ev)"
          >
            <span class="event-dot"></span>
            <span class="event-text">
              {{ formatTime(ev.start?.date_time) }} {{ ev.summary }}
            </span>
          </div>
          <div
            v-if="day.events.length > 3"
            class="cell-more"
          >
            +{{ day.events.length - 3 }} 更多
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.calendar-grid-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.calendar-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border, #e0e0e0);
  flex-shrink: 0;
}
.weekday-cell {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-weak);
}
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  grid-template-rows: repeat(6, 1fr);
  flex: 1;
  min-height: 0;
}
.calendar-cell {
  border: 1px solid var(--color-border, #e8e8e8);
  padding: 6px;
  min-height: 90px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 3px;
  transition: background 0.12s;
  overflow: hidden;
}
.calendar-cell:hover {
  background: var(--color-bg-hover, #f5f5f5);
}
.calendar-cell.other-month {
  background: var(--color-panel, #f8fafc);
  cursor: default;
  opacity: 0.5;
}
.calendar-cell.today {
  background: var(--color-primary-light, #e8f0fe);
}
.calendar-cell.today .cell-date {
  background: var(--color-primary, #3b82f6);
  color: #fff;
  border-radius: 50%;
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.calendar-cell.selected {
  box-shadow: inset 0 0 0 2px var(--color-primary, #3b82f6);
}
.cell-date {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-heading, #1a1a1a);
  padding: 2px 0;
}
.cell-events {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}
.cell-event {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 5px;
  border-radius: 4px;
  background: var(--color-calendar-bg, #ecfdf5);
  font-size: 11px;
  cursor: pointer;
  overflow: hidden;
  white-space: nowrap;
}
.cell-event:hover {
  background: var(--color-calendar-border, #a7f3d0);
}
.event-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-calendar-btn, #059669);
  flex-shrink: 0;
}
.event-text {
  color: var(--color-muted, #475569);
  overflow: hidden;
  text-overflow: ellipsis;
}
.cell-more {
  font-size: 10px;
  color: var(--color-weak);
  padding: 2px 5px;
}
</style>
