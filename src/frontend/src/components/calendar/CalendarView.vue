<script setup lang="ts">
// Calendar 工作台——日/周/月视图日程浏览器。
// 日程页是用户手动操作界面：新增、修改、删除会直接写入 Google Calendar。
// Assistant 聊天代办仍然走草稿、确认和执行链路，不复用这里的直写入口。
import { ref, inject, onMounted, computed, watch } from "vue";
import type { AppState } from "../../composables/useAppState";
import {
  createCalendarEvent,
  deleteCalendarEvent,
  listCalendarEvents,
  updateCalendarEvent,
  type CalendarAttendee,
  type CalendarEventPayload,
  type CalendarEventResponse,
} from "../../api/calendar";
import { fetchOpenWorkItems, type WorkItemSummary } from "../../api/workflow";
import CalendarGrid from "./CalendarGrid.vue";
import CalendarDayView from "./CalendarDayView.vue";
import EventList from "./EventList.vue";

const appState = inject<AppState>("appState")!;

type ViewMode = "month" | "week" | "day" | "list";
const viewMode = ref<ViewMode>("month");
const selectedDate = ref<string | null>(null);
const selectedEvent = ref<CalendarEventResponse | null>(null);
const events = ref<CalendarEventResponse[]>([]);
const isLoading = ref(false);
const error = ref<string | null>(null);
const isSaving = ref(false);
const isDeleting = ref(false);
const formError = ref<string | null>(null);
const showEventForm = ref(false);
const formMode = ref<"create" | "edit">("create");
const eventForm = ref({
  title: "",
  start_time: "",
  end_time: "",
  location: "",
  description: "",
  attendees_text: "",
});

// 当前查看的年月
const now = new Date();
const viewYear = ref(now.getFullYear());
const viewMonth = ref(now.getMonth() + 1); // 1-12

const viewDate = ref(new Date(now.getFullYear(), now.getMonth(), now.getDate()));

const calendarId = "primary";

// 当前视图的日期范围
const timeRange = computed(() => {
  if (viewMode.value === "month") {
    const firstDay = new Date(viewYear.value, viewMonth.value - 1, 1);
    const lastDay = new Date(viewYear.value, viewMonth.value, 0);
    lastDay.setHours(23, 59, 59, 999);
    return {
      time_min: firstDay.toISOString(),
      time_max: lastDay.toISOString(),
    };
  }
  if (viewMode.value === "week") {
    const d = new Date(viewDate.value);
    const dow = d.getDay();
    const mondayOffset = dow === 0 ? -6 : 1 - dow;
    d.setDate(d.getDate() + mondayOffset);
    const weekStart = new Date(d);
    weekStart.setHours(0, 0, 0, 0);
    const weekEnd = new Date(d);
    weekEnd.setDate(weekEnd.getDate() + 6);
    weekEnd.setHours(23, 59, 59, 999);
    return {
      time_min: weekStart.toISOString(),
      time_max: weekEnd.toISOString(),
    };
  }
  // day
  const d = new Date(viewDate.value);
  d.setHours(0, 0, 0, 0);
  const dayStart = d.toISOString();
  d.setHours(23, 59, 59, 999);
  return { time_min: dayStart, time_max: d.toISOString() };
});

const monthLabel = computed(() => `${viewYear.value}年${viewMonth.value}月`);

onMounted(() => {
  if (appState.state.googleConnected) {
    loadEvents();
  }
});

// 跨页面同步
watch(
  () => appState.state.refreshSignal,
  () => {
    loadEvents();
  },
);

async function loadEvents() {
  isLoading.value = true;
  error.value = null;
  try {
    const resp = await listCalendarEvents({
      calendar_id: calendarId,
      time_min: timeRange.value.time_min,
      time_max: timeRange.value.time_max,
      max_results: 50,
    });
    events.value = resp.events;

    // 额外合并本地日程草稿
    try {
      const workItems = await fetchOpenWorkItems();
      const localEvents: CalendarEventResponse[] = workItems
        .filter((w: WorkItemSummary) => w.work_item_type === "calendar_event_draft")
        .map((w: WorkItemSummary) => ({
          id: w.id,
          calendar_id: "primary",
          summary: w.title,
          description: w.summary || null,
          location: null,
          start: null,
          end: null,
          attendees: [],
          html_link: null,
        }));
      events.value = [...events.value, ...localEvents];
    } catch {
      // 本地草稿加载失败不影响 Google 日程展示
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "加载日程失败";
  } finally {
    isLoading.value = false;
  }
}

function prevPeriod() {
  if (viewMode.value === "month") {
    if (viewMonth.value === 1) {
      viewYear.value--;
      viewMonth.value = 12;
    } else {
      viewMonth.value--;
    }
  } else if (viewMode.value === "week") {
    const d = new Date(viewDate.value);
    d.setDate(d.getDate() - 7);
    viewDate.value = d;
  } else {
    const d = new Date(viewDate.value);
    d.setDate(d.getDate() - 1);
    viewDate.value = d;
  }
  loadEvents();
}

function nextPeriod() {
  if (viewMode.value === "month") {
    if (viewMonth.value === 12) {
      viewYear.value++;
      viewMonth.value = 1;
    } else {
      viewMonth.value++;
    }
  } else if (viewMode.value === "week") {
    const d = new Date(viewDate.value);
    d.setDate(d.getDate() + 7);
    viewDate.value = d;
  } else {
    const d = new Date(viewDate.value);
    d.setDate(d.getDate() + 1);
    viewDate.value = d;
  }
  loadEvents();
}

function goToday() {
  const n = new Date();
  viewYear.value = n.getFullYear();
  viewMonth.value = n.getMonth() + 1;
  viewDate.value = new Date(n.getFullYear(), n.getMonth(), n.getDate());
  loadEvents();
}

function switchView(mode: ViewMode) {
  viewMode.value = mode;
  loadEvents();
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function toDateTimeLocal(value?: string | null): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function localDateTimeToIso(value: string): string {
  const d = new Date(value);
  const offsetMinutes = -d.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const abs = Math.abs(offsetMinutes);
  const normalized = value.length === 16 ? `${value}:00` : value;
  return `${normalized}${sign}${pad2(Math.floor(abs / 60))}:${pad2(abs % 60)}`;
}

function defaultStartForDate(dateStr?: string | null): string {
  if (dateStr) return `${dateStr}T09:00`;
  const d = new Date();
  d.setMinutes(0, 0, 0);
  d.setHours(d.getHours() + 1);
  return toDateTimeLocal(d.toISOString());
}

function plusOneHour(localValue: string): string {
  const d = new Date(localValue);
  d.setHours(d.getHours() + 1);
  return toDateTimeLocal(d.toISOString());
}

function parseAttendees(value: string): CalendarAttendee[] {
  return value
    .split(/[\n,;，；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((email) => ({ email, display_name: null }));
}

function openCreateForm() {
  const start = defaultStartForDate(selectedDate.value);
  formMode.value = "create";
  formError.value = null;
  selectedEvent.value = null;
  eventForm.value = {
    title: "",
    start_time: start,
    end_time: plusOneHour(start),
    location: "",
    description: "",
    attendees_text: "",
  };
  showEventForm.value = true;
}

function openEditForm(event: CalendarEventResponse) {
  formMode.value = "edit";
  formError.value = null;
  selectedEvent.value = event;
  eventForm.value = {
    title: event.summary || "",
    start_time: toDateTimeLocal(event.start?.date_time),
    end_time: toDateTimeLocal(event.end?.date_time),
    location: event.location || "",
    description: event.description || "",
    attendees_text: event.attendees?.map((item) => item.email).join("\n") || "",
  };
  showEventForm.value = true;
}

function buildEventPayload(): CalendarEventPayload | null {
  const title = eventForm.value.title.trim();
  if (!title) {
    formError.value = "请填写日程标题。";
    return null;
  }
  if (!eventForm.value.start_time || !eventForm.value.end_time) {
    formError.value = "请填写开始和结束时间。";
    return null;
  }
  if (new Date(eventForm.value.end_time) <= new Date(eventForm.value.start_time)) {
    formError.value = "结束时间必须晚于开始时间。";
    return null;
  }
  return {
    title,
    start_time: localDateTimeToIso(eventForm.value.start_time),
    end_time: localDateTimeToIso(eventForm.value.end_time),
    timezone: appState.state.profile?.timezone || "Asia/Shanghai",
    calendar_id: selectedEvent.value?.calendar_id || calendarId,
    organizer_email: appState.state.googleEmail || "",
    attendees: parseAttendees(eventForm.value.attendees_text),
    location: eventForm.value.location.trim() || null,
    description: eventForm.value.description.trim() || null,
    video_conference: false,
    recurrence_rule: null,
    reminders: [],
    conflict_override: false,
    conflict_summary: [],
    external_event_id: selectedEvent.value?.id || null,
    calendar_action: formMode.value === "edit" ? "update" : null,
  };
}

async function submitEventForm() {
  const payload = buildEventPayload();
  if (!payload) return;
  isSaving.value = true;
  formError.value = null;
  try {
    if (formMode.value === "edit" && selectedEvent.value) {
      await updateCalendarEvent(selectedEvent.value.id, payload);
      appState.setNotice?.("日程已更新到 Google Calendar");
    } else {
      await createCalendarEvent(payload);
      appState.setNotice?.("日程已创建到 Google Calendar");
    }
    showEventForm.value = false;
    selectedEvent.value = null;
    await loadEvents();
    appState.triggerRefresh?.();
  } catch (e) {
    formError.value = e instanceof Error ? e.message : "保存日程失败";
  } finally {
    isSaving.value = false;
  }
}

async function handleDeleteSelectedEvent() {
  if (!selectedEvent.value) return;
  if (selectedEvent.value.id.startsWith("wi_")) {
    appState.setNotice?.("这是本地日程草稿，请在聊天中确认或处理。");
    return;
  }
  const ok = window.confirm(`确定删除「${selectedEvent.value.summary || "无标题日程"}」吗？`);
  if (!ok) return;
  isDeleting.value = true;
  try {
    await deleteCalendarEvent(selectedEvent.value.calendar_id, selectedEvent.value.id);
    appState.setNotice?.("日程已从 Google Calendar 删除");
    selectedEvent.value = null;
    await loadEvents();
    appState.triggerRefresh?.();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "删除日程失败";
  } finally {
    isDeleting.value = false;
  }
}

function handleSelectDate(dateStr: string) {
  selectedDate.value = dateStr;
  // 日视图下点击日期直接设置
  if (viewMode.value === "month") {
    const parts = dateStr.split("-").map(Number);
    viewDate.value = new Date(parts[0], parts[1] - 1, parts[2]);
  }
}

function handleSelectEvent(ev: CalendarEventResponse) {
  selectedEvent.value = ev;
  appState.state.selectedContextRefs = [
    {
      ref_type: "calendar_event",
      ref_id: ev.id,
      calendar_id: ev.calendar_id,
      title: ev.summary,
      start_time: ev.start?.date_time,
      end_time: ev.end?.date_time,
      timezone: ev.start?.timezone,
      attendees: ev.attendees,
      location: ev.location,
      description: ev.description,
    },
  ];
  appState.setNotice?.("已选中日程，可在聊天中要求修改");
}

function formatDateRange(): string {
  if (viewMode.value === "day") {
    return viewDate.value.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "short",
    });
  }
  if (viewMode.value === "week") {
    const d = new Date(viewDate.value);
    const dow = d.getDay();
    const mondayOffset = dow === 0 ? -6 : 1 - dow;
    d.setDate(d.getDate() + mondayOffset);
    const start = new Date(d);
    const end = new Date(d);
    end.setDate(end.getDate() + 6);
    return `${start.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })} - ${end.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })}`;
  }
  return monthLabel.value;
}
</script>

<template>
  <div class="chat-view">
    <div class="view-header">
      <h1>📅 日程</h1>
      <div style="display:flex;align-items:center;gap:8px">
        <button class="btn" style="padding:7px 14px;font-size:14px" @click="openCreateForm">
          新建日程
        </button>
        <!-- 视图切换 -->
        <div class="view-toggle">
          <button
            v-for="mode in (['month','week','day','list'] as ViewMode[])"
            :key="mode"
            class="view-toggle-btn"
            :class="{ active: viewMode === mode }"
            @click="switchView(mode)"
          >
            {{ { month: "月", week: "周", day: "日", list: "列表" }[mode] }}
          </button>
        </div>
      </div>
    </div>

    <!-- 导航栏 -->
    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 16px;border-bottom:1px solid var(--color-border);flex-shrink:0">
      <div style="display:flex;align-items:center;gap:10px">
        <button class="btn-secondary" style="padding:6px 12px;font-size:13px" @click="prevPeriod">←</button>
        <button class="btn-secondary" style="padding:6px 12px;font-size:13px" @click="goToday">今天</button>
        <button class="btn-secondary" style="padding:6px 12px;font-size:13px" @click="nextPeriod">→</button>
      </div>
      <span style="font-weight:600;font-size:16px;color:var(--color-heading)">{{ formatDateRange() }}</span>
      <button class="btn-secondary" style="padding:6px 12px;font-size:13px" :disabled="isLoading" @click="loadEvents">
        {{ isLoading ? "加载中" : "刷新" }}
      </button>
    </div>

    <p v-if="error" class="inline-error" style="margin:4px 14px">{{ error }}</p>

    <!-- 视图内容 -->
    <div class="view-body" style="display:flex;flex-direction:column;overflow:hidden">
      <!-- 月视图：日历网格 -->
      <CalendarGrid
        v-if="viewMode === 'month'"
        :year="viewYear"
        :month="viewMonth"
        :events="events"
        :selected-date="selectedDate"
        @select-date="handleSelectDate"
        @select-event="handleSelectEvent"
      />

      <!-- 日/周视图：时间轴 -->
      <CalendarDayView
        v-else-if="viewMode === 'day' || viewMode === 'week'"
        :view-mode="viewMode"
        :date="viewDate"
        :events="events"
        @select-event="handleSelectEvent"
      />

      <!-- 列表视图 -->
      <div v-else-if="viewMode === 'list'" style="padding:16px;overflow-y:auto;flex:1">
        <EventList
          :calendar-id="calendarId"
          :google-connected="appState.state.googleConnected"
          @select-event="handleSelectEvent"
        />
      </div>
    </div>

    <!-- 新建 / 编辑事件弹窗 -->
    <div v-if="showEventForm" class="event-detail-overlay" @click.self="showEventForm = false">
      <form class="event-detail-card calendar-form-card" @submit.prevent="submitEventForm">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <h3 style="margin:0;font-size:18px;color:var(--color-heading)">
            {{ formMode === "edit" ? "编辑日程" : "新建日程" }}
          </h3>
          <button type="button" class="btn-secondary" style="padding:6px 12px;font-size:14px" @click="showEventForm = false">✕</button>
        </div>
        <label class="calendar-form-field">
          <span>标题</span>
          <input v-model="eventForm.title" class="form-input" placeholder="例如：项目会议" />
        </label>
        <div class="calendar-form-grid">
          <label class="calendar-form-field">
            <span>开始时间</span>
            <input v-model="eventForm.start_time" class="form-input" type="datetime-local" />
          </label>
          <label class="calendar-form-field">
            <span>结束时间</span>
            <input v-model="eventForm.end_time" class="form-input" type="datetime-local" />
          </label>
        </div>
        <label class="calendar-form-field">
          <span>地点</span>
          <input v-model="eventForm.location" class="form-input" placeholder="可选" />
        </label>
        <label class="calendar-form-field">
          <span>参会人邮箱</span>
          <textarea
            v-model="eventForm.attendees_text"
            class="form-input calendar-form-textarea"
            placeholder="每行一个邮箱，可选"
          ></textarea>
        </label>
        <label class="calendar-form-field">
          <span>描述</span>
          <textarea
            v-model="eventForm.description"
            class="form-input calendar-form-textarea"
            placeholder="可选"
          ></textarea>
        </label>
        <p v-if="formError" class="inline-error">{{ formError }}</p>
        <div class="calendar-form-actions">
          <button type="button" class="btn-secondary" @click="showEventForm = false">取消</button>
          <button type="submit" class="btn" :disabled="isSaving">
            {{ isSaving ? "保存中" : (formMode === "edit" ? "保存修改" : "创建日程") }}
          </button>
        </div>
      </form>
    </div>

    <!-- 选中事件详情弹窗 -->
    <div v-if="selectedEvent && !showEventForm" class="event-detail-overlay" @click.self="selectedEvent = null">
      <div class="event-detail-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <h3 style="margin:0;font-size:18px;color:var(--color-heading)">{{ selectedEvent.summary || "无标题" }}</h3>
          <button class="btn-secondary" style="padding:6px 12px;font-size:14px" @click="selectedEvent = null">✕</button>
        </div>
        <div v-if="selectedEvent.start" class="detail-row">
          <span class="detail-label">时间</span>
          <span>{{ selectedEvent.start.date_time }} - {{ selectedEvent.end?.date_time }}</span>
        </div>
        <div v-if="selectedEvent.attendees?.length" class="detail-row">
          <span class="detail-label">参会人</span>
          <span>{{ selectedEvent.attendees.map(a => a.email).join(", ") }}</span>
        </div>
        <div v-if="selectedEvent.description" class="detail-row">
          <span class="detail-label">描述</span>
          <span>{{ selectedEvent.description }}</span>
        </div>
        <div v-if="selectedEvent.html_link" class="detail-row">
          <a :href="selectedEvent.html_link" target="_blank" rel="noopener">在 Google Calendar 中打开</a>
        </div>
        <div class="calendar-form-actions" style="margin-top:18px">
          <button class="btn-secondary" @click="openEditForm(selectedEvent)">编辑</button>
          <button class="btn-danger" :disabled="isDeleting" @click="handleDeleteSelectedEvent">
            {{ isDeleting ? "删除中" : "删除" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-toggle {
  display: flex;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}
.view-toggle-btn {
  padding: 6px 16px;
  border: none;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  color: var(--color-weak);
  font-weight: 500;
  border-right: 1px solid var(--color-border);
}
.view-toggle-btn:last-child {
  border-right: none;
}
.view-toggle-btn.active {
  background: var(--color-primary);
  color: #fff;
  font-weight: 600;
}
.view-toggle-btn:hover:not(.active) {
  background: var(--color-panel);
}

.event-detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.event-detail-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px 28px;
  max-width: 520px;
  width: 90%;
  max-height: 65vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}
.detail-row {
  display: flex;
  gap: 14px;
  margin-bottom: 10px;
  font-size: 15px;
  color: var(--color-body);
}
.detail-label {
  color: var(--color-weak);
  flex-shrink: 0;
  width: 70px;
  text-align: right;
}
.detail-row a {
  color: var(--color-primary);
  text-decoration: none;
}
.calendar-form-card {
  display: grid;
  gap: 12px;
}
.calendar-form-field {
  display: grid;
  gap: 6px;
  font-size: 14px;
  color: var(--color-muted);
}
.calendar-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.calendar-form-textarea {
  min-height: 82px;
  resize: vertical;
}
.calendar-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
