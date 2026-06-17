from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal[
    "user_message",
    "user_profile",
    "contact_store",
    "gmail_message",
    "gmail_thread",
    "calendar_event",
    "calendar_freebusy",
    "uploaded_file",
    "file_extraction",
    "selected_context",
    "system_default",
    "llm_inference",
    "unresolved",
]

ConfirmationStatus = Literal[
    "verified",
    "explicit_user_input",
    "inferred_needs_review",
    "missing",
    "ambiguous",
]

Maturity = Literal["incomplete", "reviewable", "proposal_ready"]


class FieldEvidenceInput(BaseModel):
    """关键字段来源。

    后续所有可执行 Proposal 都必须能追到每个关键字段的来源。字段值本身
    放在 draft payload 中；这里记录“这个值为什么可信”。
    """

    field_path: str
    value: Any | None = None
    source_type: SourceType
    source_ref: str | None = None
    confidence: float = Field(ge=0, le=1)
    confirmation_status: ConfirmationStatus
    updated_at: str | None = None


class FieldEvidenceRecord(FieldEvidenceInput):
    """数据库中的 Field Evidence 记录。"""

    id: str
    artifact_id: str
    created_at: str


class CompletenessResult(BaseModel):
    """字段完整性校验结果。

    `proposal_ready` 只表示字段完整且来源可信；真正执行外部写操作仍然
    必须经过后续 Proposal、Authorization 和 Execution Service。
    """

    maturity: Maturity
    missing_fields: list[str] = []
    ambiguous_fields: list[str] = []
    inferred_fields: list[str] = []
    questions: list[str] = []


class DraftValidationRequest(BaseModel):
    """开发期校验接口请求。

    `draft_type` 决定使用哪一套必填字段规则。`draft` 是本地 Artifact
    payload 的候选结构，`evidence` 是字段来源列表。
    """

    draft_type: Literal["new_email", "reply_email", "forward_email", "calendar_event"]
    draft: dict[str, Any]
    evidence: list[FieldEvidenceInput] = []


class FieldEvidenceUpsertRequest(FieldEvidenceInput):
    """用户补充字段后写入来源记录的请求。"""


class FieldEvidenceListResponse(BaseModel):
    """某个 Artifact 的所有字段来源。"""

    artifact_id: str
    items: list[FieldEvidenceRecord]
