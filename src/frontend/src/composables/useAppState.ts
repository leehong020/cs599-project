// 共享应用状态。通过 provide/inject 在组件树中传递，
// 避免每个视图独立请求相同数据。
import { reactive, computed, type ComputedRef } from "vue";
import type { UserProfile, Signature, Contact } from "../api/settings";

export interface TodoItem {
  id: string;
  icon: string;
  title: string;
  desc: string;
  status: "awaiting" | "draft" | "approved" | "executed";
}

export interface ThreadSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_preview: string | null;
}

export interface AppStateData {
  googleConnected: boolean;
  googleEmail: string | null;
  googleNeedsReconnect: boolean;
  googleMessage: string | null;
  oauthConfigured: boolean;
  profile: UserProfile | null;
  signatures: Signature[];
  contacts: Contact[];
  todos: TodoItem[];
  notice: string | null;
  activeView: string;
  refreshSignal: number;
  sessions: ThreadSummary[];
  selectedContextRefs: Record<string, unknown>[];
}

export function createAppState() {
  const state = reactive<AppStateData>({
    googleConnected: false,
    googleEmail: null,
    googleNeedsReconnect: false,
    googleMessage: null,
    oauthConfigured: true,
    profile: null,
    signatures: [],
    contacts: [],
    todos: [],
    notice: null,
    activeView: "chat",
    refreshSignal: 0,
    sessions: [],
    selectedContextRefs: [],
  });

  const todoCount: ComputedRef<number> = computed(
    () => state.todos.filter((t: TodoItem) => t.status === "awaiting").length,
  );

  function setNotice(msg: string | null) {
    state.notice = msg;
    if (msg) {
      setTimeout(() => {
        if (state.notice === msg) state.notice = null;
      }, 5000);
    }
  }

  function triggerRefresh() {
    state.refreshSignal++;
  }

  return { state, todoCount, setNotice, triggerRefresh };
}

export interface AppState {
  state: AppStateData;
  todoCount: ComputedRef<number>;
  setNotice: (msg: string | null) => void;
  triggerRefresh: () => void;
}
