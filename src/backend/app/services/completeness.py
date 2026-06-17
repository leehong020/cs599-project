from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.completeness import (
    CompletenessResult,
    FieldEvidenceInput,
    FieldEvidenceRecord,
)
from app.services.oauth import now_iso

EXECUTABLE_CONFIRMATION_STATUSES = {"verified", "explicit_user_input"}
NON_EXECUTABLE_SOURCE_TYPES = {
    "llm_inference",
    "unresolved",
    "system_default",
    "uploaded_file",
    "file_extraction",
}


@dataclass(frozen=True)
class RequiredField:
    """单个关键字段规则。"""

    field_path: str
    label: str
    question: str


def _evidence_by_field(
    evidence_items: Iterable[FieldEvidenceInput],
) -> dict[str, FieldEvidenceInput]:
    """把 evidence 列表转换成按字段索引的字典。"""
    return {item.field_path: item for item in evidence_items}


def _has_value(value: Any) -> bool:
    """判断字段值是否真正存在。"""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple | set | dict):
        return bool(value)
    return True


def _get_nested_value(payload: dict[str, Any], field_path: str) -> Any:
    """按点号路径读取嵌套字段。"""
    current: Any = payload
    for part in field_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _is_inferred_only(evidence: FieldEvidenceInput) -> bool:
    """判断字段是否只能进入 reviewable，不能进入可执行 Proposal。"""
    return (
        evidence.source_type in NON_EXECUTABLE_SOURCE_TYPES
        or evidence.confirmation_status == "inferred_needs_review"
    )


def _field_question_intro(missing: list[str], ambiguous: list[str], inferred: list[str]) -> str:
    """生成合并追问的开头。"""
    total = len(missing) + len(ambiguous) + len(inferred)
    if total <= 1:
        return "还需要补充或确认 1 项信息："
    return f"还需要补充或确认 {total} 项信息："


def _build_questions(
    missing_questions: list[str],
    ambiguous_questions: list[str],
    inferred_questions: list[str],
) -> list[str]:
    """把缺失、歧义、仅推断字段合并成一次追问。"""
    if not missing_questions and not ambiguous_questions and not inferred_questions:
        return []

    lines = [_field_question_intro(missing_questions, ambiguous_questions, inferred_questions)]
    index = 1
    for question in [*missing_questions, *ambiguous_questions, *inferred_questions]:
        lines.append(f"{index}. {question}")
        index += 1
    return ["\n".join(lines)]


def _validate_required_fields(
    draft: dict[str, Any],
    evidence_items: list[FieldEvidenceInput],
    required_fields: list[RequiredField],
) -> CompletenessResult:
    """按统一规则校验关键字段完整性和来源可信度。"""
    evidence_map = _evidence_by_field(evidence_items)
    missing_fields: list[str] = []
    ambiguous_fields: list[str] = []
    inferred_fields: list[str] = []
    missing_questions: list[str] = []
    ambiguous_questions: list[str] = []
    inferred_questions: list[str] = []

    for field in required_fields:
        value = _get_nested_value(draft, field.field_path)
        evidence = evidence_map.get(field.field_path)
        if not _has_value(value) or evidence is None or evidence.confirmation_status == "missing":
            missing_fields.append(field.field_path)
            missing_questions.append(field.question)
            continue

        if evidence.confirmation_status == "ambiguous":
            ambiguous_fields.append(field.field_path)
            ambiguous_questions.append(f"请确认 {field.label}。")
            continue

        if (
            evidence.confirmation_status not in EXECUTABLE_CONFIRMATION_STATUSES
            or _is_inferred_only(evidence)
        ):
            inferred_fields.append(field.field_path)
            inferred_questions.append(f"{field.label} 目前只是候选，请确认是否使用。")

    if missing_fields or ambiguous_fields:
        maturity = "incomplete"
    elif inferred_fields:
        maturity = "reviewable"
    else:
        maturity = "proposal_ready"

    return CompletenessResult(
        maturity=maturity,
        missing_fields=missing_fields,
        ambiguous_fields=ambiguous_fields,
        inferred_fields=inferred_fields,
        questions=_build_questions(
            missing_questions,
            ambiguous_questions,
            inferred_questions,
        ),
    )


def validate_new_email_draft(
    draft: dict[str, Any],
    evidence_items: list[FieldEvidenceInput],
) -> CompletenessResult:
    """校验新邮件草稿。"""
    required = [
        RequiredField("sender_email", "发件账号", "使用哪个发件账号？"),
        RequiredField("to", "To 收件人", "请提供 To 收件人的邮箱。"),
        RequiredField("subject", "主题", "请确认邮件主题。"),
        RequiredField("body", "正文", "请提供或确认邮件正文。"),
        RequiredField("signature_policy", "署名策略", "使用哪个署名，还是明确不加署名？"),
    ]
    if draft.get("cc_requested"):
        required.append(RequiredField("cc", "CC 收件人", "请提供 CC 收件人的邮箱。"))
    if draft.get("bcc_requested"):
        required.append(RequiredField("bcc", "BCC 收件人", "请提供 BCC 收件人的邮箱。"))
    if draft.get("attachment_requested"):
        required.append(RequiredField("attachments", "附件", "请确认要附加的文件。"))
    return _validate_required_fields(draft, evidence_items, required)


def validate_reply_email_draft(
    draft: dict[str, Any],
    evidence_items: list[FieldEvidenceInput],
) -> CompletenessResult:
    """校验回复邮件草稿。"""
    required = [
        RequiredField("gmail_thread_id", "Gmail Thread ID", "请确认要回复哪一个邮件线程。"),
        RequiredField("reply_to_message_id", "Reply-To Message ID", "请确认要回复哪一封邮件。"),
        RequiredField("sender_email", "发件账号", "使用哪个发件账号？"),
        RequiredField("to", "To 收件人", "请确认回复收件人。"),
        RequiredField("subject", "主题", "请确认回复主题。"),
        RequiredField("body", "正文", "请提供或确认回复正文。"),
        RequiredField("signature_policy", "署名策略", "使用哪个署名，还是明确不加署名？"),
    ]
    return _validate_required_fields(draft, evidence_items, required)


def validate_forward_email_draft(
    draft: dict[str, Any],
    evidence_items: list[FieldEvidenceInput],
) -> CompletenessResult:
    """校验转发邮件草稿。"""
    required = [
        RequiredField("source_message_id", "Source Message ID", "请确认要转发哪一封邮件。"),
        RequiredField("forward_to", "转发收件人", "请提供转发收件人的邮箱。"),
        RequiredField("sender_email", "发件账号", "使用哪个发件账号？"),
        RequiredField("subject", "转发主题", "请确认转发主题。"),
    ]
    if _has_value(draft.get("additional_note")):
        required.append(
            RequiredField("signature_policy", "署名策略", "附加说明需要署名，请确认署名策略。")
        )
    return _validate_required_fields(draft, evidence_items, required)


def validate_calendar_event_draft(
    draft: dict[str, Any],
    evidence_items: list[FieldEvidenceInput],
) -> CompletenessResult:
    """校验日程草稿。"""
    required = [
        RequiredField("title", "标题", "请确认日程标题。"),
        RequiredField("start_time", "开始时间", "请确认会议开始时间。"),
        RequiredField("timezone", "时区", "请确认时区。"),
        RequiredField("calendar_id", "目标日历", "请确认要写入哪个日历。"),
        RequiredField("organizer_email", "组织者账号", "请确认组织者账号。"),
    ]
    if not _has_value(draft.get("end_time")) and not _has_value(draft.get("duration_minutes")):
        required.append(
            RequiredField("duration_minutes", "结束时间或持续时长", "请确认会议持续多久。")
        )
    if draft.get("attendees_requested"):
        required.append(
            RequiredField("attendees", "参会人邮箱", "请提供参会人的邮箱。")
        )
    if draft.get("location_requested"):
        required.append(RequiredField("location", "地点", "请确认会议地点。"))
    if draft.get("online_meeting_requested"):
        required.append(
            RequiredField("video_conference", "视频会议策略", "请确认是否创建视频会议。")
        )
    if draft.get("recurrence_requested"):
        required.append(RequiredField("recurrence_rule", "重复规则", "请确认周期会议规则。"))
    return _validate_required_fields(draft, evidence_items, required)


def validate_draft_by_type(
    draft_type: str,
    draft: dict[str, Any],
    evidence_items: list[FieldEvidenceInput],
) -> CompletenessResult:
    """按草稿类型分发到具体校验器。"""
    validators = {
        "new_email": validate_new_email_draft,
        "reply_email": validate_reply_email_draft,
        "forward_email": validate_forward_email_draft,
        "calendar_event": validate_calendar_event_draft,
    }
    validator = validators.get(draft_type)
    if validator is None:
        raise ValueError(f"未知草稿类型：{draft_type}")
    return validator(draft, evidence_items)


async def list_field_evidence(
    session: AsyncSession,
    artifact_id: str,
) -> list[FieldEvidenceRecord]:
    """查询某个 Artifact 的所有字段来源。"""
    result = await session.execute(
        text(
            """
            SELECT
                id,
                artifact_id,
                field_path,
                value_json,
                source_type,
                source_ref,
                confidence,
                confirmation_status,
                created_at,
                updated_at
            FROM field_evidence
            WHERE artifact_id = :artifact_id
            ORDER BY field_path ASC, updated_at DESC
            """
        ),
        {"artifact_id": artifact_id},
    )
    return [
        FieldEvidenceRecord(
            id=row["id"],
            artifact_id=row["artifact_id"],
            field_path=row["field_path"],
            value=json.loads(row["value_json"]) if row["value_json"] is not None else None,
            source_type=row["source_type"],
            source_ref=row["source_ref"],
            confidence=row["confidence"],
            confirmation_status=row["confirmation_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in result.mappings()
    ]


async def upsert_field_evidence(
    session: AsyncSession,
    artifact_id: str,
    payload: FieldEvidenceInput,
) -> FieldEvidenceRecord:
    """写入或更新字段来源记录。

    用户在追问中补充邮箱、署名、时长等信息时，后续聊天层应调用这里
    把来源记为 `user_message` 和 `explicit_user_input`，而不是只改草稿值。
    """
    await _ensure_artifact_exists(session, artifact_id)
    timestamp = now_iso()
    evidence_id = f"fe_{uuid.uuid4().hex}"
    await session.execute(
        text(
            """
            INSERT INTO field_evidence (
                id,
                artifact_id,
                field_path,
                value_json,
                source_type,
                source_ref,
                confidence,
                confirmation_status,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :artifact_id,
                :field_path,
                :value_json,
                :source_type,
                :source_ref,
                :confidence,
                :confirmation_status,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": evidence_id,
            "artifact_id": artifact_id,
            "field_path": payload.field_path,
            "value_json": json.dumps(payload.value, ensure_ascii=False),
            "source_type": payload.source_type,
            "source_ref": payload.source_ref,
            "confidence": payload.confidence,
            "confirmation_status": payload.confirmation_status,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    return await get_field_evidence_by_id(session, evidence_id)


async def get_field_evidence_by_id(
    session: AsyncSession,
    evidence_id: str,
) -> FieldEvidenceRecord:
    """按 ID 读取单条字段来源记录。"""
    result = await session.execute(
        text(
            """
            SELECT
                id,
                artifact_id,
                field_path,
                value_json,
                source_type,
                source_ref,
                confidence,
                confirmation_status,
                created_at,
                updated_at
            FROM field_evidence
            WHERE id = :evidence_id
            """
        ),
        {"evidence_id": evidence_id},
    )
    row = result.mappings().one()
    return FieldEvidenceRecord(
        id=row["id"],
        artifact_id=row["artifact_id"],
        field_path=row["field_path"],
        value=json.loads(row["value_json"]) if row["value_json"] is not None else None,
        source_type=row["source_type"],
        source_ref=row["source_ref"],
        confidence=row["confidence"],
        confirmation_status=row["confirmation_status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _ensure_artifact_exists(session: AsyncSession, artifact_id: str) -> None:
    """确认 Artifact 存在，避免写入悬空的字段来源。"""
    result = await session.execute(
        text("SELECT id FROM artifacts WHERE id = :artifact_id"),
        {"artifact_id": artifact_id},
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact 不存在，无法记录字段来源。",
        )
