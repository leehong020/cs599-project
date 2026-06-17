export interface ShortTermMemoryResponse {
  thread_id: string;
  recent_messages: Array<{ role: string; content: string }>;
  conversation_summary: string | null;
  open_work_items: Record<string, unknown>[];
  pending_proposals: Record<string, unknown>[];
  task_dag: Record<string, unknown>[];
  task_batches: string[][];
  artifact_summaries: Record<string, unknown>[];
  action_results: Record<string, unknown>[];
}

export interface MemoryRecordResponse {
  id: string;
  namespace: string;
  memory_key: string;
  memory_type: string;
  content: Record<string, unknown>;
  confidence: number;
  status: string;
  source_thread_id: string | null;
  source_message_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarkdownExportResponse {
  files: string[];
}

// 阶段 9 的 memory 客户端只访问后端事实来源。前端不自行决定长期记忆
// 是否生效，避免把临时聊天指令写成长期偏好。
export async function fetchShortTermMemory(threadId: string): Promise<ShortTermMemoryResponse> {
  const response = await fetch(`/api/memory/threads/${encodeURIComponent(threadId)}/short-term`);

  if (!response.ok) {
    throw new Error(`Fetch short-term memory failed with ${response.status}`);
  }

  return response.json() as Promise<ShortTermMemoryResponse>;
}

export async function createMemoryCandidate(
  threadId: string,
  message: string,
): Promise<MemoryRecordResponse | null> {
  const response = await fetch("/api/memory/candidates", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ thread_id: threadId, message }),
  });

  if (!response.ok) {
    throw new Error(`Create memory candidate failed with ${response.status}`);
  }

  return response.json() as Promise<MemoryRecordResponse | null>;
}

export async function exportMarkdownBundle(): Promise<MarkdownExportResponse> {
  const response = await fetch("/api/memory/exports/markdown", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ include_audit: true }),
  });

  if (!response.ok) {
    throw new Error(`Export markdown failed with ${response.status}`);
  }

  return response.json() as Promise<MarkdownExportResponse>;
}
