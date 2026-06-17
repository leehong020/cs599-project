from typing import Any, Literal

from pydantic import BaseModel, Field


class GmailSearchRequest(BaseModel):
    """Gmail 搜索请求。"""

    query: str = Field(default="", max_length=500)
    max_results: int = Field(default=10, ge=1, le=25)


class GmailMessageSummary(BaseModel):
    """Gmail 搜索结果中的轻量邮件摘要（含发件人、主题、日期、摘要）。"""

    id: str
    thread_id: str
    subject: str | None = None
    from_email: str | None = None
    date: str | None = None
    snippet: str | None = None
    label_ids: list[str] = []


class GmailSearchResponse(BaseModel):
    """Gmail 搜索响应。"""

    messages: list[GmailMessageSummary]
    result_size_estimate: int = 0


class GmailParsedBody(BaseModel):
    """MIME 解析后的邮件正文。"""

    text: str
    html: str | None = None


class GmailMessageDetail(BaseModel):
    """Gmail 邮件详情。"""

    id: str
    thread_id: str
    subject: str | None = None
    from_email: str | None = None
    to: list[str] = []
    cc: list[str] = []
    date: str | None = None
    snippet: str | None = None
    body: GmailParsedBody
    headers: dict[str, str] = {}
    raw: dict[str, Any] = {}


class GmailThreadDetail(BaseModel):
    """Gmail 线程详情。"""

    id: str
    messages: list[GmailMessageDetail]


class EmailAddress(BaseModel):
    """邮件地址。"""

    email: str
    name: str | None = None


class EmailDraftPayload(BaseModel):
    """本地邮件 Artifact 的内容结构。"""

    draft_type: Literal["new_email", "reply_email", "forward_email"]
    sender_email: str
    to: list[EmailAddress] = []
    cc: list[EmailAddress] = []
    bcc: list[EmailAddress] = []
    subject: str
    body: str
    signature_policy: str
    gmail_thread_id: str | None = None
    reply_to_message_id: str | None = None
    source_message_id: str | None = None
    additional_note: str | None = None


class PrepareNewEmailRequest(BaseModel):
    """准备新邮件本地草稿的请求。"""

    thread_id: str | None = None
    sender_email: str
    to: list[EmailAddress]
    cc: list[EmailAddress] = []
    bcc: list[EmailAddress] = []
    subject: str
    body: str
    signature_policy: str


class PrepareReplyEmailRequest(BaseModel):
    """准备回复邮件本地草稿的请求。"""

    thread_id: str | None = None
    gmail_thread_id: str
    reply_to_message_id: str
    sender_email: str
    to: list[EmailAddress]
    cc: list[EmailAddress] = []
    subject: str
    body: str
    signature_policy: str


class PrepareForwardEmailRequest(BaseModel):
    """准备转发邮件本地草稿的请求。"""

    thread_id: str | None = None
    source_message_id: str
    sender_email: str
    forward_to: list[EmailAddress]
    subject: str
    additional_note: str | None = None
    signature_policy: str = "no_signature"


class EmailArtifactResponse(BaseModel):
    """本地邮件 Artifact 响应。"""

    thread_id: str
    work_item_id: str
    artifact_id: str
    version: int
    maturity: str
    content: EmailDraftPayload
