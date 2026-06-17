export interface WorkItemSummary {
  id: string;
  thread_id: string;
  work_item_type: string;
  title: string;
  summary: string | null;
  maturity: string;
  status: string;
  updated_at: string;
}

export interface ProposalItem {
  id: string;
  proposal_group_id: string;
  work_item_id: string;
  action_type: "send_email" | "create_calendar_event" | "update_calendar_event" | "delete_calendar_event";
  payload: Record<string, unknown>;
  version: number;
  fingerprint: string;
  status: string;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateProposalRequest {
  artifact_id: string;
  action_type: "send_email" | "create_calendar_event" | "update_calendar_event" | "delete_calendar_event";
  expires_in_hours: number;
}

export interface AuthorizeProposalRequest {
  version: number;
  fingerprint: string;
  decision: "approved" | "rejected";
  source: string;
  user_message_id: string | null;
}

export interface ExecutionResult {
  status: string;
  idempotency_key: string | null;
  external_resource_id: string | null;
  payload: Record<string, unknown>;
}

export interface ResolveConfirmationResponse {
  status: "none" | "unique" | "ambiguous";
  candidates: ProposalItem[];
  message: string;
}

// 阶段 6 的 workflow 客户端只处理本地安全闭环状态。真正外部写操作
// 仍然由后端 Execution Service 触发，前端不能绕过 Proposal 和 Authorization。
export async function fetchOpenWorkItems(): Promise<WorkItemSummary[]> {
  const response = await fetch("/api/work-items/open");

  if (!response.ok) {
    throw new Error(`Open work items failed with ${response.status}`);
  }

  return response.json() as Promise<WorkItemSummary[]>;
}

export async function fetchPendingProposals(actionType?: string): Promise<ProposalItem[]> {
  const suffix = actionType ? `?action_type=${encodeURIComponent(actionType)}` : "";
  const response = await fetch(`/api/proposals/pending${suffix}`);

  if (!response.ok) {
    throw new Error(`Pending proposals failed with ${response.status}`);
  }

  return response.json() as Promise<ProposalItem[]>;
}

export async function createProposal(payload: CreateProposalRequest): Promise<ProposalItem> {
  const response = await fetch("/api/proposals", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Create proposal failed with ${response.status}`);
  }

  return response.json() as Promise<ProposalItem>;
}

export async function resolveSendConfirmation(): Promise<ResolveConfirmationResponse> {
  const response = await fetch("/api/proposals/resolve-confirmation", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ action_type: "send_email" }),
  });

  if (!response.ok) {
    throw new Error(`Resolve confirmation failed with ${response.status}`);
  }

  return response.json() as Promise<ResolveConfirmationResponse>;
}

export async function authorizeProposal(
  proposal: ProposalItem,
  decision: "approved" | "rejected",
): Promise<ProposalItem> {
  const payload: AuthorizeProposalRequest = {
    version: proposal.version,
    fingerprint: proposal.fingerprint,
    decision,
    source: "button",
    user_message_id: null,
  };
  const response = await fetch(`/api/proposals/${proposal.id}/authorize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Authorize proposal failed with ${response.status}`);
  }

  return response.json() as Promise<ProposalItem>;
}

export async function executeProposal(proposal: ProposalItem): Promise<ExecutionResult> {
  const response = await fetch(`/api/proposals/${proposal.id}/execute`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ external_resource_id: null }),
  });

  if (!response.ok) {
    throw new Error(`Execute proposal failed with ${response.status}`);
  }

  return response.json() as Promise<ExecutionResult>;
}

export interface WorkItemDetail {
  id: string;
  thread_id: string;
  work_item_type: string;
  title: string;
  summary: string | null;
  maturity: string;
  status: string;
  updated_at: string;
  artifact_id: string | null;
  artifact_type: string | null;
  artifact_version: number | null;
  artifact_content: Record<string, unknown>;
}

export async function fetchWorkItem(id: string): Promise<WorkItemDetail> {
  const response = await fetch(`/api/work-items/${encodeURIComponent(id)}`);
  if (!response.ok) {
    throw new Error(`Fetch work item failed with ${response.status}`);
  }
  return response.json() as Promise<WorkItemDetail>;
}

export async function updateWorkItem(
  id: string,
  payload: { title?: string; summary?: string; artifact_content?: Record<string, unknown> },
): Promise<WorkItemDetail> {
  const response = await fetch(`/api/work-items/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Update work item failed with ${response.status}`);
  }
  return response.json() as Promise<WorkItemDetail>;
}

export async function deleteWorkItem(id: string): Promise<void> {
  const response = await fetch(`/api/work-items/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Delete work item failed with ${response.status}`);
  }
}
