export interface AssistantTurnRequest {
  thread_id: string;
  message: string;
  user_id?: string;
  selected_context_refs?: Record<string, unknown>[];
  available_contacts?: Record<string, unknown>[];
}

export interface AssistantTurnResponse {
  thread_id: string;
  response: string;
  turn_count: number;
  tasks: Record<string, unknown>[];
  task_batches: string[][];
  route_trace: string[];
  node_timings: Record<string, unknown>[];
  clarification_needed: boolean;
  clarification_question: string | null;
  proposal_group: Record<string, unknown> | null;
  artifacts: ArtifactItem[];
}

export interface ArtifactItem {
  id: string;
  task_id: string;
  artifact_type: "email_draft" | "calendar_event_draft" | "note";
  content: Record<string, unknown>;
}

export interface AssistantStreamEvent {
  event: "progress" | "token" | "final" | "error";
  message: string;
  step: string | null;
  data: Record<string, unknown>;
}

export interface AssistantStateResponse {
  thread_id: string;
  state: Record<string, unknown>;
}

export interface MermaidResponse {
  graph_name: string;
  mermaid: string;
}

export interface SubgraphRunResponse {
  subgraph: string;
  task_results: Record<string, unknown>[];
  route_trace: string[];
}

// 阶段 8 的 assistant 客户端用于主图调试、SSE 聊天流和后续聊天界面衔接。
// 它不会直接调用 Gmail 或 Calendar 外部写接口。
export async function runAssistantTurn(
  payload: AssistantTurnRequest,
): Promise<AssistantTurnResponse> {
  const response = await fetch("/api/assistant/turn", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Run assistant turn failed with ${response.status}`);
  }

  return response.json() as Promise<AssistantTurnResponse>;
}

export async function streamAssistantTurn(
  payload: AssistantTurnRequest,
  onEvent: (event: AssistantStreamEvent) => void,
): Promise<AssistantTurnResponse> {
  const response = await fetch("/api/assistant/turn/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream assistant turn failed with ${response.status}`);
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let buffer = "";
  let finalResponse: AssistantTurnResponse | null = null;

  // 后端按 SSE 标准使用空行分隔事件。这里逐块读取流，避免等待整个
  // 响应结束后才更新 UI。
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const parsed = parseSsePart(part);
      if (!parsed) {
        continue;
      }
      onEvent(parsed);
      if (parsed.event === "error") {
        throw new Error(parsed.message);
      }
      if (parsed.event === "final") {
        finalResponse = parsed.data as unknown as AssistantTurnResponse;
      }
    }
  }

  if (!finalResponse) {
    throw new Error("Assistant stream ended without final event");
  }

  return finalResponse;
}

export async function fetchAssistantState(threadId: string): Promise<AssistantStateResponse> {
  const response = await fetch(`/api/assistant/threads/${encodeURIComponent(threadId)}/state`);

  if (!response.ok) {
    throw new Error(`Fetch assistant state failed with ${response.status}`);
  }

  return response.json() as Promise<AssistantStateResponse>;
}

function parseSsePart(part: string): AssistantStreamEvent | null {
  const dataLine = part
    .split("\n")
    .find((line) => line.startsWith("data: "));
  if (!dataLine) {
    return null;
  }
  return JSON.parse(dataLine.slice(6)) as AssistantStreamEvent;
}

export async function fetchAssistantMermaid(): Promise<MermaidResponse> {
  const response = await fetch("/api/assistant/graph/mermaid");

  if (!response.ok) {
    throw new Error(`Fetch assistant mermaid failed with ${response.status}`);
  }

  return response.json() as Promise<MermaidResponse>;
}

export async function runAssistantSubgraph(
  subgraph: "mail" | "calendar",
  message: string,
): Promise<SubgraphRunResponse> {
  const response = await fetch("/api/assistant/subgraphs/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ subgraph, message }),
  });

  if (!response.ok) {
    throw new Error(`Run assistant subgraph failed with ${response.status}`);
  }

  return response.json() as Promise<SubgraphRunResponse>;
}

export interface ThreadInfo {
  id: string;
  title: string;
  summary: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export async function fetchThreads(): Promise<ThreadInfo[]> {
  const response = await fetch("/api/assistant/threads");
  if (!response.ok) return [];
  return response.json() as Promise<ThreadInfo[]>;
}

export async function deleteThread(threadId: string): Promise<void> {
  await fetch(`/api/assistant/threads/${encodeURIComponent(threadId)}`, {
    method: "DELETE",
  });
}

export async function updateThreadTitle(threadId: string, title: string): Promise<void> {
  await fetch(`/api/assistant/threads/${encodeURIComponent(threadId)}/title`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}
