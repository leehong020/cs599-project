from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import audit_log_event, log_error_trace
from app.schemas.workflow import (
    AuthorizeProposalRequest,
    ArtifactSummary,
    CreateProposalRequest,
    ExecuteProposalRequest,
    ExecutionResultResponse,
    ProposalItemResponse,
    ResolveConfirmationResponse,
    WorkItemSummary,
)
from app.services.calendar import (
    build_calendar_client_for_user,
    commit_create_calendar_event_for_authorized_proposal,
    commit_delete_calendar_event_for_authorized_proposal,
    commit_update_calendar_event_for_authorized_proposal,
)
from app.services.gmail import (
    build_gmail_client_for_user,
    commit_send_email_for_authorized_proposal,
)
from app.services.oauth import ConnectedUser, now_iso

PROPOSAL_READY_ACTIONS = {
    "send_email": "email_draft",
    "create_calendar_event": "calendar_event_draft",
    "update_calendar_event": "calendar_event_draft",
    "delete_calendar_event": "calendar_event_draft",
}


class WorkflowSafetyError(RuntimeError):
    """工作流安全规则阻止当前操作。"""


async def _get_user_default_signature_content(
    session: AsyncSession,
    user: ConnectedUser,
) -> str | None:
    """读取用户的默认署名内容。"""
    try:
        result = await session.execute(
            text(
                """
                SELECT content FROM signatures
                WHERE user_id = :user_id AND is_default = 1
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"user_id": user.user_id},
        )
        row = result.mappings().first()
        if row:
            return row["content"]
    except Exception:
        pass
    return None


async def persist_graph_artifacts(
    session: AsyncSession,
    user: ConnectedUser,
    thread_id: str,
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """将图生成的 artifacts 持久化为 Work Item，返回持久化后的 artifact 列表。

    这样聊天中创建的邮件/日程草稿就能在邮箱页和日程页中看到，
    并且可以通过确认→授权→执行的路径实际发送或创建。
    """
    from app.services.gmail import _create_email_artifact, EmailDraftPayload
    from app.services.calendar import _create_calendar_artifact, CalendarEventPayload
    from app.services.gmail import EmailAddress as GmailEmailAddress

    persisted = []
    for a in artifacts:
        atype = a.get("artifact_type", "")
        content = a.get("content", {}) or {}

        try:
            if atype == "email_draft":
                # 查询用户默认署名
                default_sig_content = await _get_user_default_signature_content(session, user)

                # 将图生成的邮件内容转换为 EmailDraftPayload
                to_raw = content.get("to", "")
                to_list: list[Any] = []
                if isinstance(to_raw, list):
                    to_list = [GmailEmailAddress(email=e.get("email", e) if isinstance(e, dict) else e, name=None) for e in to_raw]
                elif isinstance(to_raw, str) and to_raw.strip() and to_raw != "需要确认":
                    to_list = [GmailEmailAddress(email=addr.strip(), name=None) for addr in to_raw.split(",") if "@" in addr]

                body = str(content.get("body", content.get("raw", "")))
                signature_policy = "no_signature"
                if default_sig_content:
                    body = body.rstrip() + "\n\n" + default_sig_content
                    signature_policy = "append_signature"

                payload = EmailDraftPayload(
                    draft_type="new_email",
                    sender_email=user.email,
                    to=to_list,
                    cc=[],
                    bcc=[],
                    subject=str(content.get("subject", "无主题")),
                    body=body,
                    signature_policy=signature_policy,
                )
                result = await _create_email_artifact(session, user, thread_id, payload.subject, payload)
                persisted.append({"artifact_id": result.artifact_id, "work_item_id": result.work_item_id, "type": "email_draft"})

            elif atype == "calendar_event_draft":
                cal_payload = CalendarEventPayload(
                    title=str(content.get("title", "未命名日程")),
                    start_time=str(content.get("start_time", "")),
                    end_time=str(content.get("end_time", content.get("start_time", ""))),
                    timezone=str(content.get("timezone", "Asia/Shanghai")),
                    calendar_id="primary",
                    organizer_email=user.email,
                    attendees=content.get("attendees", []),
                    location=str(content.get("location", "") or ""),
                    description=str(content.get("description", "") or ""),
                    video_conference=False,
                    recurrence_rule=None,
                    reminders=[],
                    conflict_override=False,
                    conflict_summary=[],
                )
                result = await _create_calendar_artifact(session, user, thread_id, cal_payload, "reviewable")
                persisted.append({"artifact_id": result.artifact_id, "work_item_id": result.work_item_id, "type": "calendar_event_draft"})

        except Exception:
            continue

    return persisted


def stable_json_dumps(payload: dict[str, Any]) -> str:
    """生成稳定 JSON 文本。

    fingerprint 必须只受业务 payload 影响，不受字典插入顺序或空格影响。
    """
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_payload_fingerprint(payload: dict[str, Any]) -> str:
    """计算 Proposal payload fingerprint。"""
    return hashlib.sha256(stable_json_dumps(payload).encode("utf-8")).hexdigest()


def _loads_payload(raw: str) -> dict[str, Any]:
    """从 SQLite 文本字段恢复 JSON payload。"""
    return json.loads(raw)


def _proposal_from_row(row: Any) -> ProposalItemResponse:
    """把数据库行转换成 ProposalItemResponse。"""
    return ProposalItemResponse(
        id=row["id"],
        proposal_group_id=row["proposal_group_id"],
        work_item_id=row["work_item_id"],
        action_type=row["action_type"],
        payload=_loads_payload(row["payload_json"]),
        version=row["version"],
        fingerprint=row["fingerprint"],
        status=row["status"],
        expires_at=row["expires_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def list_open_work_items(
    session: AsyncSession,
    user: ConnectedUser,
    thread_id: str | None = None,
) -> list[WorkItemSummary]:
    """列出当前用户打开中的 Work Item。

    多 Open Work Item 是阶段 6 的核心能力：用户可以先暂缓一封邮件，
    再创建日程，随后回到邮件继续处理。
    """
    sql = """
        SELECT id, thread_id, work_item_type, title, summary, maturity, status, updated_at
        FROM work_items
        WHERE user_id = :user_id AND status = 'open'
    """
    params: dict[str, Any] = {"user_id": user.user_id}
    if thread_id:
        sql += " AND thread_id = :thread_id"
        params["thread_id"] = thread_id
    sql += " ORDER BY updated_at DESC"
    result = await session.execute(text(sql), params)
    return [
        WorkItemSummary(
            id=row["id"],
            thread_id=row["thread_id"],
            work_item_type=row["work_item_type"],
            title=row["title"],
            summary=row["summary"],
            maturity=row["maturity"],
            status=row["status"],
            updated_at=row["updated_at"],
        )
        for row in result.mappings()
    ]


async def get_artifact_for_user(
    session: AsyncSession,
    user: ConnectedUser,
    artifact_id: str,
) -> ArtifactSummary:
    """读取属于当前用户的 Artifact。"""
    result = await session.execute(
        text(
            """
            SELECT a.id, a.work_item_id, a.artifact_type, a.version, a.content_json
            FROM artifacts a
            JOIN work_items wi ON wi.id = a.work_item_id
            WHERE a.id = :artifact_id AND wi.user_id = :user_id
            """
        ),
        {"artifact_id": artifact_id, "user_id": user.user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise WorkflowSafetyError("Artifact 不存在或不属于当前用户。")
    return ArtifactSummary(
        id=row["id"],
        work_item_id=row["work_item_id"],
        artifact_type=row["artifact_type"],
        version=row["version"],
        content=_loads_payload(row["content_json"]),
    )


async def create_proposal_from_artifact(
    session: AsyncSession,
    user: ConnectedUser,
    payload: CreateProposalRequest,
) -> ProposalItemResponse:
    """从本地 Artifact 创建可确认 Proposal。"""
    artifact = await get_artifact_for_user(session, user, payload.artifact_id)
    expected_artifact_type = PROPOSAL_READY_ACTIONS[payload.action_type]
    if artifact.artifact_type != expected_artifact_type:
        raise WorkflowSafetyError("Artifact 类型和 Proposal 动作不匹配。")

    fingerprint = compute_payload_fingerprint(artifact.content)
    timestamp = now_iso()
    expires_at = (datetime.now(UTC) + timedelta(hours=payload.expires_in_hours)).isoformat()

    # 同一 Work Item + action_type 的旧待确认 Proposal 会被 superseded。
    # 这样 Artifact 修改或重新生成 Proposal 后，旧授权不能执行新内容。
    await session.execute(
        text(
            """
            UPDATE proposal_items
            SET status = 'superseded', updated_at = :updated_at
            WHERE work_item_id = :work_item_id
              AND action_type = :action_type
              AND status IN ('draft', 'awaiting_confirmation', 'approved')
            """
        ),
        {
            "work_item_id": artifact.work_item_id,
            "action_type": payload.action_type,
            "updated_at": timestamp,
        },
    )

    proposal_group_id = f"pg_{uuid.uuid4().hex}"
    proposal_item_id = f"pi_{uuid.uuid4().hex}"
    await session.execute(
        text(
            """
            INSERT INTO proposal_groups (id, thread_id, user_id, status, created_at, updated_at)
            SELECT :id, thread_id, user_id, 'awaiting_confirmation', :created_at, :updated_at
            FROM work_items
            WHERE id = :work_item_id AND user_id = :user_id
            """
        ),
        {
            "id": proposal_group_id,
            "work_item_id": artifact.work_item_id,
            "user_id": user.user_id,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO proposal_items (
                id,
                proposal_group_id,
                work_item_id,
                action_type,
                payload_json,
                version,
                fingerprint,
                status,
                expires_at,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :proposal_group_id,
                :work_item_id,
                :action_type,
                :payload_json,
                :version,
                :fingerprint,
                'awaiting_confirmation',
                :expires_at,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": proposal_item_id,
            "proposal_group_id": proposal_group_id,
            "work_item_id": artifact.work_item_id,
            "action_type": payload.action_type,
            "payload_json": stable_json_dumps(artifact.content),
            "version": artifact.version,
            "fingerprint": fingerprint,
            "expires_at": expires_at,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    created = await get_proposal_item(session, user, proposal_item_id)
    audit_log_event(
        "proposal.created",
        work_item_id=created.work_item_id,
        proposal_item_id=created.id,
        action_type=created.action_type,
        status=created.status,
    )
    return created


async def get_proposal_item(
    session: AsyncSession,
    user: ConnectedUser,
    proposal_item_id: str,
) -> ProposalItemResponse:
    """读取当前用户的 Proposal Item。"""
    result = await session.execute(
        text(
            """
            SELECT
                pi.id,
                pi.proposal_group_id,
                pi.work_item_id,
                pi.action_type,
                pi.payload_json,
                pi.version,
                pi.fingerprint,
                pi.status,
                pi.expires_at,
                pi.created_at,
                pi.updated_at
            FROM proposal_items pi
            JOIN proposal_groups pg ON pg.id = pi.proposal_group_id
            WHERE pi.id = :proposal_item_id AND pg.user_id = :user_id
            """
        ),
        {"proposal_item_id": proposal_item_id, "user_id": user.user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise WorkflowSafetyError("Proposal 不存在或不属于当前用户。")
    return _proposal_from_row(row)


async def list_pending_proposals(
    session: AsyncSession,
    user: ConnectedUser,
    action_type: str | None = None,
) -> list[ProposalItemResponse]:
    """列出待确认或已授权但未执行的 Proposal。"""
    sql = """
        SELECT
            pi.id,
            pi.proposal_group_id,
            pi.work_item_id,
            pi.action_type,
            pi.payload_json,
            pi.version,
            pi.fingerprint,
            pi.status,
            pi.expires_at,
            pi.created_at,
            pi.updated_at
        FROM proposal_items pi
        JOIN proposal_groups pg ON pg.id = pi.proposal_group_id
        WHERE pg.user_id = :user_id
          AND pi.status IN ('awaiting_confirmation', 'approved')
    """
    params: dict[str, Any] = {"user_id": user.user_id}
    if action_type:
        sql += " AND pi.action_type = :action_type"
        params["action_type"] = action_type
    sql += " ORDER BY pi.updated_at DESC"
    result = await session.execute(text(sql), params)
    return [_proposal_from_row(row) for row in result.mappings()]


async def resolve_confirmation_candidates(
    session: AsyncSession,
    user: ConnectedUser,
    action_type: str | None = None,
) -> ResolveConfirmationResponse:
    """根据动作类型解析用户确认目标。

    “确认发送”会传入 `send_email`，因此只筛选邮件 Proposal，不会误创建日程。
    """
    candidates = await list_pending_proposals(session, user, action_type)
    if not candidates:
        return ResolveConfirmationResponse(
            status="none",
            candidates=[],
            message="没有可确认的 Proposal。",
        )
    if len(candidates) == 1:
        return ResolveConfirmationResponse(
            status="unique",
            candidates=candidates,
            message="已唯一匹配一个 Proposal。",
        )
    return ResolveConfirmationResponse(
        status="ambiguous",
        candidates=candidates,
        message="存在多个候选 Proposal，请明确要确认哪一个。",
    )


async def authorize_proposal(
    session: AsyncSession,
    user: ConnectedUser,
    proposal_item_id: str,
    payload: AuthorizeProposalRequest,
) -> ProposalItemResponse:
    """记录用户对 Proposal 的确认或拒绝。"""
    proposal = await get_proposal_item(session, user, proposal_item_id)
    if proposal.status != "awaiting_confirmation":
        raise WorkflowSafetyError("Proposal 当前状态不允许授权。")
    if proposal.version != payload.version or proposal.fingerprint != payload.fingerprint:
        raise WorkflowSafetyError("Proposal 版本或 fingerprint 不匹配，旧授权失效。")
    if proposal.expires_at and datetime.fromisoformat(proposal.expires_at) <= datetime.now(UTC):
        raise WorkflowSafetyError("Proposal 已过期，需要重新生成。")

    timestamp = now_iso()
    await session.execute(
        text(
            """
            INSERT INTO action_authorizations (
                id,
                proposal_item_id,
                proposal_version,
                fingerprint,
                user_id,
                decision,
                source,
                user_message_id,
                created_at
            )
            VALUES (
                :id,
                :proposal_item_id,
                :proposal_version,
                :fingerprint,
                :user_id,
                :decision,
                :source,
                :user_message_id,
                :created_at
            )
            """
        ),
        {
            "id": f"auth_{uuid.uuid4().hex}",
            "proposal_item_id": proposal_item_id,
            "proposal_version": payload.version,
            "fingerprint": payload.fingerprint,
            "user_id": user.user_id,
            "decision": payload.decision,
            "source": payload.source,
            "user_message_id": payload.user_message_id,
            "created_at": timestamp,
        },
    )
    next_status = "approved" if payload.decision == "approved" else "rejected"
    await session.execute(
        text(
            """
            UPDATE proposal_items
            SET status = :status, updated_at = :updated_at
            WHERE id = :proposal_item_id
            """
        ),
        {
            "status": next_status,
            "updated_at": timestamp,
            "proposal_item_id": proposal_item_id,
        },
    )
    await session.commit()
    authorized = await get_proposal_item(session, user, proposal_item_id)
    audit_log_event(
        "proposal.approved" if payload.decision == "approved" else "proposal.rejected",
        work_item_id=authorized.work_item_id,
        proposal_item_id=authorized.id,
        action_type=authorized.action_type,
        from_status="awaiting_confirmation",
        to_status=authorized.status,
    )
    return authorized


async def execute_authorized_proposal(
    session: AsyncSession,
    user: ConnectedUser,
    proposal_item_id: str,
    payload: ExecuteProposalRequest,
) -> ExecutionResultResponse:
    """执行已授权 Proposal。

    这里是统一执行入口，负责动作分发。每个具体执行函数仍会再次校验
    Authorization、version、fingerprint 和幂等事件。
    """
    proposal = await get_proposal_item(session, user, proposal_item_id)
    if proposal.status == "executed":
        existing = await _load_latest_action_event(session, proposal_item_id)
        if existing:
            return ExecutionResultResponse.model_validate(existing)
    if proposal.status != "approved":
        raise WorkflowSafetyError("Proposal 尚未获得用户授权，不能执行。")

    audit_log_event(
        "action.executing",
        work_item_id=proposal.work_item_id,
        proposal_item_id=proposal.id,
        action_type=proposal.action_type,
        status="executing",
    )
    try:
        if proposal.action_type == "send_email":
            gmail_client = await build_gmail_client_for_user(session, user)
            result = await commit_send_email_for_authorized_proposal(
                session,
                proposal_item_id,
                gmail_client,
            )
        elif proposal.action_type == "create_calendar_event":
            calendar_client = await build_calendar_client_for_user(session, user)
            result = await commit_create_calendar_event_for_authorized_proposal(
                session,
                proposal_item_id,
                calendar_client,
            )
        elif proposal.action_type == "update_calendar_event":
            if not payload.external_resource_id:
                raise WorkflowSafetyError("更新日程需要 external_resource_id。")
            calendar_client = await build_calendar_client_for_user(session, user)
            result = await commit_update_calendar_event_for_authorized_proposal(
                session,
                proposal_item_id,
                payload.external_resource_id,
                calendar_client,
            )
        elif proposal.action_type == "delete_calendar_event":
            if not payload.external_resource_id:
                raise WorkflowSafetyError("删除日程需要 external_resource_id。")
            calendar_client = await build_calendar_client_for_user(session, user)
            result = await commit_delete_calendar_event_for_authorized_proposal(
                session,
                proposal_item_id,
                payload.external_resource_id,
                calendar_client,
            )
        else:
            raise WorkflowSafetyError("未知 Proposal 动作类型。")
    except Exception:
        log_error_trace(
            "action_execution_failed",
            work_item_id=proposal.work_item_id,
            proposal_item_id=proposal.id,
            action_type=proposal.action_type,
        )
        audit_log_event(
            "action.failed",
            work_item_id=proposal.work_item_id,
            proposal_item_id=proposal.id,
            action_type=proposal.action_type,
            status="failed",
            error_category="action_execution_failed",
        )
        raise
    audit_log_event(
        "action.succeeded",
        work_item_id=proposal.work_item_id,
        proposal_item_id=proposal.id,
        action_type=proposal.action_type,
        status=result.get("status"),
    )
    return ExecutionResultResponse.model_validate(result)


async def _load_latest_action_event(
    session: AsyncSession,
    proposal_item_id: str,
) -> dict[str, Any] | None:
    """读取某个 Proposal 最近的 Action Event，用于重复执行返回已有结果。"""
    result = await session.execute(
        text(
            """
            SELECT status, idempotency_key, external_resource_id, payload_json
            FROM action_events
            WHERE proposal_item_id = :proposal_item_id
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"proposal_item_id": proposal_item_id},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return {
        "status": row["status"],
        "idempotency_key": row["idempotency_key"],
        "external_resource_id": row["external_resource_id"],
        "payload": json.loads(row["payload_json"] or "{}"),
    }
