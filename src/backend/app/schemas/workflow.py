from typing import Any, Literal

from pydantic import BaseModel, Field

ActionType = Literal[
    "send_email",
    "create_calendar_event",
    "update_calendar_event",
    "delete_calendar_event",
]
Decision = Literal["approved", "rejected"]


class WorkItemSummary(BaseModel):
    """打开中的 Work Item 摘要。"""

    id: str
    thread_id: str
    work_item_type: str
    title: str
    summary: str | None = None
    maturity: str
    status: str
    updated_at: str


class ArtifactSummary(BaseModel):
    """Artifact 摘要。"""

    id: str
    work_item_id: str
    artifact_type: str
    version: int
    content: dict[str, Any]


class ProposalItemResponse(BaseModel):
    """Proposal Item 响应。"""

    id: str
    proposal_group_id: str
    work_item_id: str
    action_type: str
    payload: dict[str, Any]
    version: int
    fingerprint: str
    status: str
    expires_at: str | None = None
    created_at: str
    updated_at: str


class CreateProposalRequest(BaseModel):
    """从本地 Artifact 创建 Proposal 的请求。"""

    artifact_id: str
    action_type: ActionType
    expires_in_hours: int = Field(default=24, ge=1, le=24 * 7)


class AuthorizeProposalRequest(BaseModel):
    """用户确认或拒绝 Proposal 的请求。"""

    version: int
    fingerprint: str
    decision: Decision = "approved"
    source: str = "button"
    user_message_id: str | None = None


class ExecuteProposalRequest(BaseModel):
    """执行 Proposal 的请求。

    `external_resource_id` 目前用于 `update_calendar_event` 和
    `delete_calendar_event`，表示目标 Google Calendar Event ID。
    """

    external_resource_id: str | None = None


class ResolveConfirmationRequest(BaseModel):
    """根据用户确认意图筛选候选 Proposal。"""

    action_type: ActionType | None = None


class ResolveConfirmationResponse(BaseModel):
    """确认意图解析结果。"""

    status: Literal["none", "unique", "ambiguous"]
    candidates: list[ProposalItemResponse]
    message: str


class WorkItemDetail(BaseModel):
    """Work Item 详情，包含 Artifact 完整内容。"""

    id: str
    thread_id: str
    work_item_type: str
    title: str
    summary: str | None = None
    maturity: str
    status: str
    updated_at: str
    artifact_id: str | None = None
    artifact_type: str | None = None
    artifact_version: int | None = None
    artifact_content: dict[str, Any] = {}


class WorkItemUpdateRequest(BaseModel):
    """更新 Work Item 的请求。"""

    title: str | None = None
    summary: str | None = None
    artifact_content: dict[str, Any] | None = None


class ExecutionResultResponse(BaseModel):
    """执行服务响应。"""

    status: str
    idempotency_key: str | None = None
    external_resource_id: str | None = None
    payload: dict[str, Any] = {}
