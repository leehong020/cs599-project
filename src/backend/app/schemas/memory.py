from typing import Any

from pydantic import BaseModel, Field


class RecentMessage(BaseModel):
    """短期记忆中的最近消息。"""

    role: str
    content: str


class ShortTermMemoryResponse(BaseModel):
    """短期记忆响应。

    该结构面向 Prompt 组装和前端调试，避免把完整 checkpoint 原样注入模型。
    """

    thread_id: str
    recent_messages: list[RecentMessage]
    conversation_summary: str | None = None
    open_work_items: list[dict[str, Any]]
    pending_proposals: list[dict[str, Any]]
    task_dag: list[dict[str, Any]]
    task_batches: list[list[str]]
    artifact_summaries: list[dict[str, Any]]
    action_results: list[dict[str, Any]]


class MemoryCandidateCreateRequest(BaseModel):
    """创建长期记忆候选的请求。"""

    thread_id: str | None = None
    message: str = Field(min_length=1)
    namespace: str = "preferences"


class MemoryRecordResponse(BaseModel):
    """长期记忆记录响应。"""

    id: str
    namespace: str
    memory_key: str
    memory_type: str
    content: dict[str, Any]
    confidence: float
    status: str
    source_thread_id: str | None = None
    source_message_id: str | None = None
    created_at: str
    updated_at: str


class ContactNoteResponse(BaseModel):
    """联系人备注召回响应。"""

    contact_email: str
    notes: list[MemoryRecordResponse]


class MarkdownExportRequest(BaseModel):
    """Markdown 导出请求。"""

    include_audit: bool = True


class MarkdownExportResponse(BaseModel):
    """Markdown 导出响应。"""

    files: list[str]
