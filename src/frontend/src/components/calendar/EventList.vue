<script setup lang="ts">
// 日程列表。按日期分组展示，支持快捷筛选。
import { ref, computed, onMounted, watch } from "vue";
import {
  listCalendarEvents,
  type CalendarEventResponse,
} from "../../api/calendar";

const props = defineProps<{
  calendarId: string;
  googleConnected: boolean;
}>();

const emit = defineEmits<{
  selectEvent: [event: CalendarEventResponse];
}>();

const events = ref<CalendarEventResponse[]>([]);
const isLoading = ref(false);
const error = ref<string | null>(null);
const filter = ref<"all" | "today" | "week">("all");

// 按日期分组
const groupedEvents = computed(() => {
  const groups: Record<string, CalendarEventResponse[]> = {};
  for (const ev of events.value) {
    const dateStr = ev.start?.date_time?.slice(0, 10) || "未知日期";
    if (!groups[dateStr]) groups[dateStr] = [];
    groups[dateStr].push(ev);
  }
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
});

async function handleLoad() {
  isLoading.value = true;
  error.value = null;
  try {
    const now = new Date().toISOString();
    let timeMin = now;
    let timeMax: string | null = null;
    if (filter.value === "today") {
      const end = new Date();
      end.setHours(23, 59, 59, 999);
      timeMax = end.toISOString();
    } else if (filter.value === "week") {
      const end = new Date();
      end.setDate(end.getDate() + 7);
      timeMax = end.toISOString();
    }
    const resp = await listCalendarEvents({
      calendar_id: props.calendarId,
      time_min: timeMin,
      time_max: timeMax,
      max_results: 20,
    });
    events.value = resp.events;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "读取失败";
  } finally {
    isLoading.value = false;
  }
}

function formatTime(dateTime?: string): string {
  if (!dateTime) return "";
  try {
    const d = new Date(dateTime);
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return dateTime;
  }
}

onMounted(() => {
  if (props.googleConnected) {
    handleLoad();
  }
});

watch(
  () => [props.calendarId, props.googleConnected],
  () => {
    if (props.googleConnected) {
      handleLoad();
    }
  },
);
</script>

<template>
  <div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;flex-wrap:wrap;gap:8px">
      <h3 style="font-size:15px;color:var(--color-heading);margin:0">日程列表</h3>
      <div class="action-row">
        <button
          v-for="f in [{id:'all',label:'全部'},{id:'today',label:'今天'},{id:'week',label:'本周'}]"
          :key="f.id"
          class="btn-secondary"
          style="font-size:12px;padding:5px 12px"
          :style="filter === f.id ? 'background:var(--color-primary);color:#fff;border-color:var(--color-primary)' : ''"
          @click="filter = f.id as any; handleLoad()"
        >
          {{ f.label }}
        </button>
        <button
          class="btn"
          style="font-size:12px;padding:5px 12px"
          :disabled="isLoading || !googleConnected"
          @click="handleLoad"
        >
          {{ isLoading ? "读取中" : "刷新" }}
        </button>
      </div>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>

    <div v-if="groupedEvents.length">
      <div v-for="[date, dayEvents] in groupedEvents" :key="date" style="margin-bottom:12px">
        <div style="font-weight:600;font-size:13px;color:var(--color-muted);margin-bottom:6px;padding:3px 0">
          {{ date }}
        </div>
        <div class="result-list">
          <div
            v-for="event in dayEvents"
            :key="event.id"
            class="result-item"
            style="cursor:pointer"
            @click="emit('selectEvent', event)"
          >
            <div style="flex:1;min-width:0">
              <div style="font-weight:600;font-size:14px;color:var(--color-heading)">
                {{ event.summary || "无标题" }}
              </div>
              <div class="result-item-meta">
                {{ formatTime(event.start?.date_time) }} - {{ formatTime(event.end?.date_time) }}
                <span v-if="event.attendees?.length">
                  · {{ event.attendees.length }} 位参会人
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <p v-if="!isLoading && !events.length && !error" style="color:var(--color-weak);font-size:14px;padding:10px 0">
      暂无日程，点击"刷新"加载。
    </p>
  </div>
</template>
