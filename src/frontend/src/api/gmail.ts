export interface GmailSearchRequest {
  query: string;
  max_results: number;
}

export interface GmailMessageSummary {
  id: string;
  thread_id: string;
  subject: string | null;
  from_email: string | null;
  date: string | null;
  snippet: string | null;
  label_ids: string[];
}

export interface GmailSearchResponse {
  messages: GmailMessageSummary[];
  result_size_estimate: number;
}

export interface GmailParsedBody {
  text: string;
  html: string | null;
}

export interface GmailMessageDetail {
  id: string;
  thread_id: string;
  subject: string | null;
  from_email: string | null;
  to: string[];
  cc: string[];
  date: string | null;
  snippet: string | null;
  body: GmailParsedBody;
  headers: Record<string, string>;
}

export interface GmailThreadDetail {
  id: string;
  messages: GmailMessageDetail[];
}

export interface EmailAddress {
  email: string;
  name: string | null;
}

export interface PrepareNewEmailRequest {
  thread_id: string | null;
  sender_email: string;
  to: EmailAddress[];
  cc: EmailAddress[];
  bcc: EmailAddress[];
  subject: string;
  body: string;
  signature_policy: string;
}

export interface PrepareReplyEmailRequest {
  thread_id: string | null;
  gmail_thread_id: string;
  reply_to_message_id: string;
  sender_email: string;
  to: EmailAddress[];
  cc: EmailAddress[];
  subject: string;
  body: string;
  signature_policy: string;
}

export interface EmailArtifactResponse {
  thread_id: string;
  work_item_id: string;
  artifact_id: string;
  version: number;
  maturity: string;
  content: {
    draft_type: "new_email" | "reply_email" | "forward_email";
    sender_email: string;
    to: EmailAddress[];
    cc: EmailAddress[];
    bcc: EmailAddress[];
    subject: string;
    body: string;
    signature_policy: string;
    gmail_thread_id: string | null;
    reply_to_message_id: string | null;
    source_message_id: string | null;
    additional_note: string | null;
  };
}

// 阶段 4 的 Gmail 客户端只负责前端到后端的类型化请求。
// OAuth token、Gmail access token 和 client secret 都留在后端，浏览器看不到。
export async function searchGmail(payload: GmailSearchRequest): Promise<GmailSearchResponse> {
  const response = await fetch("/api/gmail/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Gmail search failed with ${response.status}`);
  }

  return response.json() as Promise<GmailSearchResponse>;
}

export async function readGmailMessage(messageId: string): Promise<GmailMessageDetail> {
  const response = await fetch(`/api/gmail/messages/${encodeURIComponent(messageId)}`);

  if (!response.ok) {
    throw new Error(`Gmail message fetch failed with ${response.status}`);
  }

  return response.json() as Promise<GmailMessageDetail>;
}

export async function readGmailThread(threadId: string): Promise<GmailThreadDetail> {
  const response = await fetch(`/api/gmail/threads/${encodeURIComponent(threadId)}`);

  if (!response.ok) {
    throw new Error(`Gmail thread fetch failed with ${response.status}`);
  }

  return response.json() as Promise<GmailThreadDetail>;
}

export async function prepareNewEmailDraft(
  payload: PrepareNewEmailRequest,
): Promise<EmailArtifactResponse> {
  const response = await fetch("/api/gmail/prepare/new", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Prepare new email failed with ${response.status}`);
  }

  return response.json() as Promise<EmailArtifactResponse>;
}

export async function prepareReplyEmailDraft(
  payload: PrepareReplyEmailRequest,
): Promise<EmailArtifactResponse> {
  const response = await fetch("/api/gmail/prepare/reply", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Prepare reply email failed with ${response.status}`);
  }

  return response.json() as Promise<EmailArtifactResponse>;
}

export async function deleteGmailMessage(messageId: string): Promise<void> {
  const response = await fetch(`/api/gmail/messages/${encodeURIComponent(messageId)}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`Delete email failed with ${response.status}`);
  }
}
