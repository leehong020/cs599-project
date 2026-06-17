from __future__ import annotations

import base64
import html
import json
import re
import uuid
from email.message import EmailMessage
from email.utils import formataddr
from html.parser import HTMLParser
from typing import Any, Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.gmail import (
    EmailAddress,
    EmailArtifactResponse,
    EmailDraftPayload,
    GmailMessageDetail,
    GmailMessageSummary,
    GmailParsedBody,
    GmailSearchResponse,
    GmailThreadDetail,
    PrepareForwardEmailRequest,
    PrepareNewEmailRequest,
    PrepareReplyEmailRequest,
)
from app.schemas.completeness import FieldEvidenceInput
from app.services.completeness import upsert_field_evidence
from app.services.oauth import ConnectedUser, get_valid_google_access_token, now_iso

GMAIL_API_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailApiError(RuntimeError):
    """Gmail API 调用失败。"""


class GmailExecutionBlocked(RuntimeError):
    """发送执行被安全规则阻止。"""


class GmailSendClient(Protocol):
    """发送执行所需的最小 Gmail 客户端协议。"""

    async def create_draft_for_execution(
        self,
        payload: EmailDraftPayload,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """创建 Gmail Draft。"""

    async def send_draft_for_execution(self, draft_id: str) -> dict[str, Any]:
        """发送 Gmail Draft。"""


class _HtmlTextExtractor(HTMLParser):
    """把 HTML 正文转换成尽量可读的纯文本。"""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text_value = data.strip()
        if text_value:
            self.parts.append(text_value)

    def get_text(self) -> str:
        """返回规整后的纯文本。"""
        joined = " ".join(self.parts)
        joined = re.sub(r"[ \t]+\n", "\n", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return html.unescape(joined).strip()


def html_to_text(html_body: str) -> str:
    """把 Gmail HTML 正文转换成纯文本。

    这里不引入额外依赖，先用标准库解析器满足 MVP。后续如果遇到复杂
    邮件模板，再考虑引入专门的 HTML 清洗库。
    """
    parser = _HtmlTextExtractor()
    parser.feed(html_body)
    return parser.get_text()


def decode_base64url(data: str | None) -> str:
    """解码 Gmail payload 中的 base64url 文本。"""
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")


def encode_base64url(data: bytes) -> str:
    """把 RFC 822 邮件内容编码成 Gmail API 需要的 raw 字符串。"""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def headers_to_dict(headers: list[dict[str, str]] | None) -> dict[str, str]:
    """把 Gmail headers 列表转换成大小写不敏感的字典。"""
    result: dict[str, str] = {}
    for item in headers or []:
        name = item.get("name")
        value = item.get("value")
        if name and value:
            result[name.lower()] = value
    return result


def split_address_header(value: str | None) -> list[str]:
    """粗略拆分邮件地址头。

    MVP 先用于展示和 evidence，不在这里做最终收件人唯一性判定。
    """
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def extract_body_from_payload(payload: dict[str, Any]) -> GmailParsedBody:
    """从 Gmail MIME payload 中提取正文。

    优先使用 `text/plain`。如果只有 HTML，则转换成纯文本，同时保留
    原始 HTML，方便后续需要更丰富展示时使用。
    """
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def visit(part: dict[str, Any]) -> None:
        mime_type = part.get("mimeType")
        body_data = (part.get("body") or {}).get("data")
        if mime_type == "text/plain":
            plain_parts.append(decode_base64url(body_data))
        elif mime_type == "text/html":
            html_parts.append(decode_base64url(body_data))
        for child in part.get("parts") or []:
            visit(child)

    visit(payload)
    plain_text = "\n".join(part for part in plain_parts if part.strip()).strip()
    html_text = "\n".join(part for part in html_parts if part.strip()).strip()
    if plain_text:
        return GmailParsedBody(text=plain_text, html=html_text or None)
    return GmailParsedBody(text=html_to_text(html_text), html=html_text or None)


def parse_gmail_message(raw_message: dict[str, Any]) -> GmailMessageDetail:
    """把 Gmail API 原始 message 转换成应用内部可用结构。"""
    payload = raw_message.get("payload") or {}
    headers = headers_to_dict(payload.get("headers"))
    return GmailMessageDetail(
        id=raw_message["id"],
        thread_id=raw_message["threadId"],
        subject=headers.get("subject"),
        from_email=headers.get("from"),
        to=split_address_header(headers.get("to")),
        cc=split_address_header(headers.get("cc")),
        date=headers.get("date"),
        snippet=raw_message.get("snippet"),
        body=extract_body_from_payload(payload),
        headers=headers,
        raw=raw_message,
    )


def format_email_address(address: EmailAddress) -> str:
    """把结构化邮箱转换成 RFC 822 地址字符串。"""
    return formataddr((address.name or "", address.email))


def build_rfc822_message(payload: EmailDraftPayload) -> EmailMessage:
    """根据本地邮件 Artifact 构造 RFC 822 邮件。

    这里不直接发送，只生成 Gmail Draft 所需 raw 内容。真正写入 Gmail
    只能由受授权保护的执行路径调用。
    """
    message = EmailMessage()
    message["From"] = payload.sender_email
    message["To"] = ", ".join(format_email_address(item) for item in payload.to)
    if payload.cc:
        message["Cc"] = ", ".join(format_email_address(item) for item in payload.cc)
    if payload.bcc:
        message["Bcc"] = ", ".join(format_email_address(item) for item in payload.bcc)
    message["Subject"] = payload.subject
    if payload.reply_to_message_id:
        message["In-Reply-To"] = payload.reply_to_message_id
        message["References"] = payload.reply_to_message_id
    message.set_content(payload.body)
    return message


class GmailClient:
    """Gmail REST 客户端。

    这个客户端只负责和 Gmail API 通信，不做 Proposal 授权判断。发送类方法
    名字带 `for_execution`，提醒调用方它们只能被 Execution Service 使用。
    """

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token

    @property
    def _headers(self) -> dict[str, str]:
        """Gmail API 请求头。"""
        return {"Authorization": f"Bearer {self.access_token}"}

    async def search_messages(self, query: str = "", max_results: int = 10) -> GmailSearchResponse:
        """搜索 Gmail 邮件，返回含主题、发件人、日期的摘要列表。"""
        import asyncio

        async with httpx.AsyncClient(timeout=20) as client:
            list_response = await client.get(
                f"{GMAIL_API_BASE_URL}/messages",
                headers=self._headers,
                params={"q": query, "maxResults": min(max_results, 15)},
            )
            if list_response.status_code >= 400:
                raise GmailApiError("Gmail 搜索失败，请检查授权或查询语法。")
            list_payload = list_response.json()
            message_refs = list_payload.get("messages", [])

            if not message_refs:
                return GmailSearchResponse(messages=[], result_size_estimate=0)

            semaphore = asyncio.Semaphore(6)

            async def fetch_one(msg_id: str) -> GmailMessageSummary | None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"{GMAIL_API_BASE_URL}/messages/{msg_id}",
                            headers=self._headers,
                            params={"format": "metadata"},
                        )
                        if resp.status_code >= 400:
                            return None
                        data = resp.json()
                        headers_list = (
                            (data.get("payload") or {}).get("headers", [])
                        )
                        headers_dict: dict[str, str] = {}
                        for h in headers_list:
                            headers_dict[h.get("name", "").lower()] = h.get("value", "")
                        return GmailMessageSummary(
                            id=data["id"],
                            thread_id=data["threadId"],
                            subject=headers_dict.get("subject"),
                            from_email=headers_dict.get("from"),
                            date=headers_dict.get("date") or data.get("internalDate"),
                            snippet=data.get("snippet"),
                            label_ids=data.get("labelIds", []),
                        )
                    except Exception:
                        return None

            results = await asyncio.gather(
                *(fetch_one(item["id"]) for item in message_refs),
                return_exceptions=True,
            )
            summaries = [r for r in results if r is not None and not isinstance(r, Exception)]

        return GmailSearchResponse(
            messages=summaries,
            result_size_estimate=list_payload.get("resultSizeEstimate", 0),
        )

    async def trash_message(self, message_id: str) -> dict[str, Any]:
        """将邮件移至垃圾箱。"""
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{GMAIL_API_BASE_URL}/messages/{message_id}/trash",
                headers=self._headers,
            )
        if response.status_code >= 400:
            raise GmailApiError("邮件删除失败，请检查权限。")
        return response.json()

    async def get_message(self, message_id: str) -> GmailMessageDetail:
        """读取 Gmail 邮件详情，并解析 MIME 正文。"""
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{GMAIL_API_BASE_URL}/messages/{message_id}",
                headers=self._headers,
                params={"format": "full"},
            )
        if response.status_code >= 400:
            raise GmailApiError("Gmail 邮件读取失败。")
        return parse_gmail_message(response.json())

    async def get_thread(self, thread_id: str) -> GmailThreadDetail:
        """读取 Gmail 线程详情。"""
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{GMAIL_API_BASE_URL}/threads/{thread_id}",
                headers=self._headers,
                params={"format": "full"},
            )
        if response.status_code >= 400:
            raise GmailApiError("Gmail 线程读取失败。")
        payload = response.json()
        return GmailThreadDetail(
            id=payload["id"],
            messages=[parse_gmail_message(item) for item in payload.get("messages", [])],
        )

    async def create_draft_for_execution(
        self,
        payload: EmailDraftPayload,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """创建 Gmail Draft。

        这是外部写操作，只能由已校验授权的执行服务调用。
        """
        raw_message = encode_base64url(build_rfc822_message(payload).as_bytes())
        body: dict[str, Any] = {"message": {"raw": raw_message}}
        if thread_id:
            body["message"]["threadId"] = thread_id
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{GMAIL_API_BASE_URL}/drafts",
                headers=self._headers,
                json=body,
            )
        if response.status_code >= 400:
            raise GmailApiError("Gmail Draft 创建失败。")
        return response.json()

    async def update_draft_for_execution(
        self,
        draft_id: str,
        payload: EmailDraftPayload,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """更新 Gmail Draft，只能由执行服务调用。"""
        raw_message = encode_base64url(build_rfc822_message(payload).as_bytes())
        body: dict[str, Any] = {"id": draft_id, "message": {"raw": raw_message}}
        if thread_id:
            body["message"]["threadId"] = thread_id
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.put(
                f"{GMAIL_API_BASE_URL}/drafts/{draft_id}",
                headers=self._headers,
                json=body,
            )
        if response.status_code >= 400:
            raise GmailApiError("Gmail Draft 更新失败。")
        return response.json()

    async def send_draft_for_execution(self, draft_id: str) -> dict[str, Any]:
        """发送 Gmail Draft，只能由执行服务调用。"""
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{GMAIL_API_BASE_URL}/drafts/send",
                headers=self._headers,
                json={"id": draft_id},
            )
        if response.status_code >= 400:
            raise GmailApiError("Gmail Draft 发送失败。")
        return response.json()


async def build_gmail_client_for_user(session: AsyncSession, user: ConnectedUser) -> GmailClient:
    """根据当前已连接用户创建 GmailClient。"""
    access_token = await get_valid_google_access_token(session, user.user_id)
    return GmailClient(access_token)


def _json_payload(model: EmailDraftPayload) -> str:
    """把邮件草稿 payload 序列化为稳定 JSON 文本。"""
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


async def _ensure_thread(
    session: AsyncSession,
    user: ConnectedUser,
    thread_id: str | None,
    title: str,
) -> str:
    """确保本地聊天 Thread 存在。

    准备草稿时允许调用方传入现有 thread_id；如果没有，就创建一个
    轻量本地 Thread，便于后续 Work Item 和 Artifact 持久化。
    """
    timestamp = now_iso()
    if thread_id:
        result = await session.execute(
            text("SELECT id FROM threads WHERE id = :thread_id AND user_id = :user_id"),
            {"thread_id": thread_id, "user_id": user.user_id},
        )
        if result.scalar_one_or_none() is not None:
            return thread_id

    new_thread_id = thread_id or f"thread_{uuid.uuid4().hex}"
    await session.execute(
        text(
            """
            INSERT INTO threads (id, user_id, title, summary, status, created_at, updated_at)
            VALUES (:id, :user_id, :title, :summary, 'active', :created_at, :updated_at)
            """
        ),
        {
            "id": new_thread_id,
            "user_id": user.user_id,
            "title": title,
            "summary": "阶段 4 Gmail 本地邮件草稿。",
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    return new_thread_id


async def _create_email_artifact(
    session: AsyncSession,
    user: ConnectedUser,
    thread_id: str | None,
    title: str,
    payload: EmailDraftPayload,
) -> EmailArtifactResponse:
    """创建本地邮件 Work Item 和 Artifact。

    这个函数只写 SQLite，本地草稿不会同步到 Gmail Draft。写 Gmail Draft
    属于外部副作用，必须等用户确认 Proposal 后走执行路径。
    """
    timestamp = now_iso()
    actual_thread_id = await _ensure_thread(session, user, thread_id, title)
    work_item_id = f"wi_{uuid.uuid4().hex}"
    artifact_id = f"art_{uuid.uuid4().hex}"
    await session.execute(
        text(
            """
            INSERT INTO work_items (
                id,
                thread_id,
                user_id,
                work_item_type,
                title,
                summary,
                maturity,
                status,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :thread_id,
                :user_id,
                'email_draft',
                :title,
                :summary,
                'reviewable',
                'open',
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": work_item_id,
            "thread_id": actual_thread_id,
            "user_id": user.user_id,
            "title": title,
            "summary": payload.body[:200],
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO artifacts (
                id,
                work_item_id,
                artifact_type,
                version,
                content_json,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :work_item_id,
                'email_draft',
                1,
                :content_json,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": artifact_id,
            "work_item_id": work_item_id,
            "content_json": _json_payload(payload),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    await _record_email_evidence(session, artifact_id, payload)
    return EmailArtifactResponse(
        thread_id=actual_thread_id,
        work_item_id=work_item_id,
        artifact_id=artifact_id,
        version=1,
        maturity="reviewable",
        content=payload,
    )


async def _record_email_evidence(
    session: AsyncSession,
    artifact_id: str,
    payload: EmailDraftPayload,
) -> None:
    """为本地邮件草稿写入基础 Field Evidence。"""
    evidence_values: dict[str, Any] = {
        "sender_email": payload.sender_email,
        "to": [item.model_dump(mode="json") for item in payload.to],
        "subject": payload.subject,
        "body": payload.body,
        "signature_policy": payload.signature_policy,
    }
    if payload.gmail_thread_id:
        evidence_values["gmail_thread_id"] = payload.gmail_thread_id
    if payload.reply_to_message_id:
        evidence_values["reply_to_message_id"] = payload.reply_to_message_id
    if payload.source_message_id:
        evidence_values["source_message_id"] = payload.source_message_id

    for field_path, value in evidence_values.items():
        await upsert_field_evidence(
            session,
            artifact_id,
            FieldEvidenceInput(
                field_path=field_path,
                value=value,
                source_type="user_message",
                source_ref="prepare_email_api",
                confidence=1,
                confirmation_status="explicit_user_input",
            ),
        )


async def prepare_new_email_artifact(
    session: AsyncSession,
    user: ConnectedUser,
    payload: PrepareNewEmailRequest,
) -> EmailArtifactResponse:
    """准备新邮件本地 Artifact。"""
    content = EmailDraftPayload(
        draft_type="new_email",
        sender_email=payload.sender_email,
        to=payload.to,
        cc=payload.cc,
        bcc=payload.bcc,
        subject=payload.subject,
        body=payload.body,
        signature_policy=payload.signature_policy,
    )
    return await _create_email_artifact(session, user, payload.thread_id, payload.subject, content)


async def prepare_reply_email_artifact(
    session: AsyncSession,
    user: ConnectedUser,
    payload: PrepareReplyEmailRequest,
) -> EmailArtifactResponse:
    """准备回复邮件本地 Artifact，并保留 Gmail thread 关系。"""
    content = EmailDraftPayload(
        draft_type="reply_email",
        sender_email=payload.sender_email,
        to=payload.to,
        cc=payload.cc,
        subject=payload.subject,
        body=payload.body,
        signature_policy=payload.signature_policy,
        gmail_thread_id=payload.gmail_thread_id,
        reply_to_message_id=payload.reply_to_message_id,
    )
    return await _create_email_artifact(session, user, payload.thread_id, payload.subject, content)


async def prepare_forward_email_artifact(
    session: AsyncSession,
    user: ConnectedUser,
    payload: PrepareForwardEmailRequest,
) -> EmailArtifactResponse:
    """准备转发邮件本地 Artifact。"""
    body = payload.additional_note or ""
    content = EmailDraftPayload(
        draft_type="forward_email",
        sender_email=payload.sender_email,
        to=payload.forward_to,
        subject=payload.subject,
        body=body,
        signature_policy=payload.signature_policy,
        source_message_id=payload.source_message_id,
        additional_note=payload.additional_note,
    )
    return await _create_email_artifact(session, user, payload.thread_id, payload.subject, content)


async def commit_send_email_for_authorized_proposal(
    session: AsyncSession,
    proposal_item_id: str,
    gmail_client: GmailSendClient,
) -> dict[str, Any]:
    """执行已授权的 send_email Proposal。

    这是阶段 4 的提交工具实现，但它不挂普通 API 路由。后续阶段 6 的
    Execution Service 会在解析“确认发送”并写入 Authorization 后调用它。
    """
    proposal = await _load_authorized_send_email_proposal(session, proposal_item_id)
    idempotency_key = (
        f"gmail_send:{proposal['id']}:{proposal['version']}:{proposal['fingerprint']}"
    )
    existing_event = await _load_action_event_by_idempotency(session, idempotency_key)
    if existing_event is not None:
        return existing_event

    timestamp = now_iso()
    event_id = f"ae_{uuid.uuid4().hex}"
    await session.execute(
        text(
            """
            INSERT INTO action_events (
                id,
                proposal_item_id,
                event_type,
                status,
                idempotency_key,
                external_provider,
                payload_json,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :proposal_item_id,
                'send_email',
                'started',
                :idempotency_key,
                'gmail',
                :payload_json,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": event_id,
            "proposal_item_id": proposal_item_id,
            "idempotency_key": idempotency_key,
            "payload_json": json.dumps({"stage": "started"}, ensure_ascii=False),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()

    email_payload = EmailDraftPayload.model_validate(json.loads(proposal["payload_json"]))
    try:
        draft = await gmail_client.create_draft_for_execution(
            email_payload,
            thread_id=email_payload.gmail_thread_id,
        )
        draft_id = draft["id"]
        sent_message = await gmail_client.send_draft_for_execution(draft_id)
    except Exception as exc:
        await _mark_action_event_failed(session, event_id, str(exc))
        raise

    result_payload = {
        "stage": "sent",
        "draft_id": draft_id,
        "message": sent_message,
    }
    await session.execute(
        text(
            """
            UPDATE action_events
            SET status = 'succeeded',
                external_resource_id = :external_resource_id,
                payload_json = :payload_json,
                updated_at = :updated_at
            WHERE id = :id
            """
        ),
        {
            "id": event_id,
            "external_resource_id": sent_message.get("id"),
            "payload_json": json.dumps(result_payload, ensure_ascii=False),
            "updated_at": now_iso(),
        },
    )
    await session.execute(
        text(
            """
            UPDATE proposal_items
            SET status = 'executed', updated_at = :updated_at
            WHERE id = :proposal_item_id
            """
        ),
        {"proposal_item_id": proposal_item_id, "updated_at": now_iso()},
    )
    await session.commit()
    return {
        "status": "succeeded",
        "idempotency_key": idempotency_key,
        "external_resource_id": sent_message.get("id"),
        "payload": result_payload,
    }


async def _load_authorized_send_email_proposal(
    session: AsyncSession,
    proposal_item_id: str,
) -> dict[str, Any]:
    """读取并校验已授权的 send_email Proposal。"""
    result = await session.execute(
        text(
            """
            SELECT
                pi.id,
                pi.action_type,
                pi.payload_json,
                pi.version,
                pi.fingerprint,
                pi.status,
                pg.user_id
            FROM proposal_items pi
            JOIN proposal_groups pg ON pg.id = pi.proposal_group_id
            WHERE pi.id = :proposal_item_id
            """
        ),
        {"proposal_item_id": proposal_item_id},
    )
    proposal = result.mappings().first()
    if proposal is None:
        raise GmailExecutionBlocked("Proposal 不存在，不能发送。")
    if proposal["action_type"] != "send_email":
        raise GmailExecutionBlocked("该 Proposal 不是 send_email，不能发送。")
    if proposal["status"] in {"executed", "superseded", "cancelled"}:
        raise GmailExecutionBlocked("该 Proposal 当前状态不能发送。")

    authorization = await session.execute(
        text(
            """
            SELECT id
            FROM action_authorizations
            WHERE proposal_item_id = :proposal_item_id
              AND proposal_version = :proposal_version
              AND fingerprint = :fingerprint
              AND user_id = :user_id
              AND decision = 'approved'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {
            "proposal_item_id": proposal_item_id,
            "proposal_version": proposal["version"],
            "fingerprint": proposal["fingerprint"],
            "user_id": proposal["user_id"],
        },
    )
    if authorization.scalar_one_or_none() is None:
        raise GmailExecutionBlocked("缺少匹配的用户授权，不能发送。")
    return dict(proposal)


async def _load_action_event_by_idempotency(
    session: AsyncSession,
    idempotency_key: str,
) -> dict[str, Any] | None:
    """根据幂等 key 查找已有执行事件。"""
    result = await session.execute(
        text(
            """
            SELECT status, external_resource_id, payload_json
            FROM action_events
            WHERE idempotency_key = :idempotency_key
            """
        ),
        {"idempotency_key": idempotency_key},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return {
        "status": row["status"],
        "idempotency_key": idempotency_key,
        "external_resource_id": row["external_resource_id"],
        "payload": json.loads(row["payload_json"] or "{}"),
    }


async def _mark_action_event_failed(session: AsyncSession, event_id: str, error_message: str) -> None:
    """把执行事件标记为失败，并保留恢复线索。"""
    await session.execute(
        text(
            """
            UPDATE action_events
            SET status = 'failed',
                payload_json = :payload_json,
                updated_at = :updated_at
            WHERE id = :id
            """
        ),
        {
            "id": event_id,
            "payload_json": json.dumps(
                {"stage": "failed", "error": error_message},
                ensure_ascii=False,
            ),
            "updated_at": now_iso(),
        },
    )
    await session.commit()
