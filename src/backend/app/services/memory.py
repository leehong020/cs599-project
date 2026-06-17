from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.graph.runner import get_assistant_thread_state
from app.schemas.memory import (
    ContactNoteResponse,
    MarkdownExportResponse,
    MemoryCandidateCreateRequest,
    MemoryRecordResponse,
    RecentMessage,
    ShortTermMemoryResponse,
)
from app.services.oauth import ConnectedUser, now_iso
from app.services.workflow import list_open_work_items, list_pending_proposals

RECENT_MESSAGE_LIMIT = 12
LONG_CONVERSATION_THRESHOLD = 18
LONG_TERM_MARKERS = ("记住", "以后", "长期", "默认", "偏好")
TEMPORARY_MARKERS = ("这次", "临时", "今天先", "仅本次")


async def build_short_term_memory(
    session: AsyncSession,
    user: ConnectedUser,
    thread_id: str,
) -> ShortTermMemoryResponse:
    """构建短期记忆。

    短期记忆只取最近消息窗口和必要状态摘要，不把完整长对话、完整邮件正文
    或完整 Prompt 塞回模型上下文。
    """
    state = get_assistant_thread_state(thread_id)
    messages = _normalize_messages(state.get("messages", []))
    return ShortTermMemoryResponse(
        thread_id=thread_id,
        recent_messages=_recent_messages(messages),
        conversation_summary=_summarize_messages(messages),
        open_work_items=[item.model_dump() for item in await list_open_work_items(session, user, thread_id)],
        pending_proposals=[
            item.model_dump() for item in await list_pending_proposals(session, user)
        ],
        task_dag=[dict(task) for task in state.get("tasks", [])],
        task_batches=state.get("task_batches", []),
        artifact_summaries=_summarize_artifacts(state.get("artifacts", [])),
        action_results=list(state.get("action_results", [])),
    )


async def create_memory_candidate(
    session: AsyncSession,
    user: ConnectedUser,
    payload: MemoryCandidateCreateRequest,
) -> MemoryRecordResponse | None:
    """从用户消息创建长期记忆候选。

    只有出现“记住/以后/默认/偏好”等长期信号，且没有“临时/这次”等临时
    标记时才写入 `memories`。这样可以避免把一次性指令误写为长期偏好。
    """
    if not should_store_long_term_memory(payload.message):
        return None

    timestamp = now_iso()
    memory_id = f"mem_{uuid.uuid4().hex}"
    memory_key = _memory_key_from_message(payload.message)
    content = {
        "text": payload.message,
        "source": "explicit_user_message",
    }
    await session.execute(
        text(
            """
            INSERT INTO memories (
                id,
                user_id,
                namespace,
                memory_key,
                memory_type,
                content_json,
                confidence,
                status,
                source_thread_id,
                source_message_id,
                expires_at,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :user_id,
                :namespace,
                :memory_key,
                'preference_candidate',
                :content_json,
                0.85,
                'candidate',
                :source_thread_id,
                NULL,
                NULL,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": memory_id,
            "user_id": user.user_id,
            "namespace": payload.namespace,
            "memory_key": memory_key,
            "content_json": json.dumps(content, ensure_ascii=False),
            "source_thread_id": payload.thread_id,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    return await get_memory_record(session, user, memory_id)


def should_store_long_term_memory(message: str) -> bool:
    """判断自然语言是否允许写入长期记忆候选。"""
    return any(marker in message for marker in LONG_TERM_MARKERS) and not any(
        marker in message for marker in TEMPORARY_MARKERS
    )


async def get_memory_record(
    session: AsyncSession,
    user: ConnectedUser,
    memory_id: str,
) -> MemoryRecordResponse:
    """读取单条长期记忆记录。"""
    result = await session.execute(
        text(
            """
            SELECT
                id,
                namespace,
                memory_key,
                memory_type,
                content_json,
                confidence,
                status,
                source_thread_id,
                source_message_id,
                created_at,
                updated_at
            FROM memories
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": memory_id, "user_id": user.user_id},
    )
    row = result.mappings().one()
    return _memory_from_row(row)


async def recall_contact_notes(
    session: AsyncSession,
    user: ConnectedUser,
    contact_email: str,
) -> ContactNoteResponse:
    """按需召回联系人备注。

    联系人备注不注入所有 Prompt，只在明确涉及联系人邮箱时读取。
    """
    result = await session.execute(
        text(
            """
            SELECT
                id,
                namespace,
                memory_key,
                memory_type,
                content_json,
                confidence,
                status,
                source_thread_id,
                source_message_id,
                created_at,
                updated_at
            FROM memories
            WHERE user_id = :user_id
              AND namespace = 'contact_notes'
              AND memory_key = :memory_key
              AND status IN ('candidate', 'active')
            ORDER BY updated_at DESC
            """
        ),
        {"user_id": user.user_id, "memory_key": contact_email.lower()},
    )
    return ContactNoteResponse(
        contact_email=contact_email,
        notes=[_memory_from_row(row) for row in result.mappings()],
    )


async def export_markdown_bundle(
    session: AsyncSession,
    user: ConnectedUser,
    *,
    include_audit: bool = True,
) -> MarkdownExportResponse:
    """从 SQLite 事实来源导出 Markdown 文件。"""
    settings = get_settings()
    settings.exports_dir.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    files.append(await _export_preferences(session, user, settings.exports_dir))
    files.append(await _export_signatures(session, user, settings.exports_dir))
    files.extend(await _export_contacts(session, user, settings.exports_dir))
    if include_audit:
        files.append(await _export_audit(session, user, settings.exports_dir))
    return MarkdownExportResponse(files=[str(path) for path in files])


def _normalize_messages(raw_messages: list[dict[str, Any]]) -> list[RecentMessage]:
    """把 checkpoint 消息转换成短期记忆消息。"""
    messages: list[RecentMessage] = []
    for item in raw_messages:
        content = item.get("content")
        if isinstance(content, str) and content:
            messages.append(RecentMessage(role=str(item.get("role", "unknown")), content=content))
    return messages


def _recent_messages(messages: list[RecentMessage]) -> list[RecentMessage]:
    """截取最近消息窗口。"""
    return messages[-RECENT_MESSAGE_LIMIT:]


def _summarize_messages(messages: list[RecentMessage]) -> str | None:
    """生成长对话摘要。"""
    if len(messages) <= LONG_CONVERSATION_THRESHOLD:
        return None
    first = messages[0].content[:80]
    last = messages[-1].content[:80]
    return f"对话共 {len(messages)} 条消息。开头：{first}。最近：{last}。"


def _summarize_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """生成 Artifact 摘要，避免把完整正文塞进短期记忆。"""
    summaries: list[dict[str, Any]] = []
    for artifact in artifacts:
        content = artifact.get("content", {})
        summary = content.get("summary") if isinstance(content, dict) else None
        summaries.append(
            {
                "id": artifact.get("id"),
                "task_id": artifact.get("task_id"),
                "artifact_type": artifact.get("artifact_type"),
                "summary": summary,
            }
        )
    return summaries


def _memory_key_from_message(message: str) -> str:
    """根据消息生成稳定的记忆 key。"""
    normalized = re.sub(r"\s+", "_", message.strip().lower())
    return normalized[:80] or "preference"


def _memory_from_row(row: Any) -> MemoryRecordResponse:
    """把数据库行转换成长期记忆响应。"""
    return MemoryRecordResponse(
        id=row["id"],
        namespace=row["namespace"],
        memory_key=row["memory_key"],
        memory_type=row["memory_type"],
        content=json.loads(row["content_json"]),
        confidence=row["confidence"],
        status=row["status"],
        source_thread_id=row["source_thread_id"],
        source_message_id=row["source_message_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _export_preferences(
    session: AsyncSession,
    user: ConnectedUser,
    exports_dir: Path,
) -> Path:
    """导出用户确定性偏好。"""
    result = await session.execute(
        text(
            """
            SELECT
                timezone,
                default_calendar_id,
                default_signature_id,
                default_sender_email,
                default_meeting_duration_minutes,
                meeting_buffer_minutes,
                working_hours_json,
                lunch_break_json,
                email_tone_internal,
                email_tone_external
            FROM user_settings
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user.user_id},
    )
    row = result.mappings().first()
    path = exports_dir / "preferences.md"
    lines = ["# Preferences", ""]
    if row is None:
        lines.append("No preferences configured.")
    else:
        for key, value in row.items():
            lines.append(f"- **{key}**: {_markdown_value(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


async def _export_signatures(
    session: AsyncSession,
    user: ConnectedUser,
    exports_dir: Path,
) -> Path:
    """导出邮件署名。"""
    result = await session.execute(
        text(
            """
            SELECT label, content, is_default, updated_at
            FROM signatures
            WHERE user_id = :user_id
            ORDER BY is_default DESC, updated_at DESC
            """
        ),
        {"user_id": user.user_id},
    )
    path = exports_dir / "signatures.md"
    lines = ["# Signatures", ""]
    for row in result.mappings():
        lines.extend(
            [
                f"## {row['label']}",
                "",
                f"- Default: {'yes' if row['is_default'] else 'no'}",
                f"- Updated: {row['updated_at']}",
                "",
                "```text",
                row["content"],
                "```",
                "",
            ]
        )
    if len(lines) == 2:
        lines.append("No signatures configured.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


async def _export_contacts(
    session: AsyncSession,
    user: ConnectedUser,
    exports_dir: Path,
) -> list[Path]:
    """导出联系人备注。"""
    contacts_dir = exports_dir / "contacts"
    contacts_dir.mkdir(parents=True, exist_ok=True)
    result = await session.execute(
        text(
            """
            SELECT display_name, email, source_type, metadata_json, updated_at
            FROM contacts
            WHERE user_id = :user_id AND email IS NOT NULL
            ORDER BY display_name ASC
            """
        ),
        {"user_id": user.user_id},
    )
    files: list[Path] = []
    for row in result.mappings():
        email = row["email"]
        notes = await recall_contact_notes(session, user, email)
        path = contacts_dir / f"{_safe_filename(email)}.md"
        lines = [
            f"# Contact: {row['display_name']}",
            "",
            f"- Email: {email}",
            f"- Source: {row['source_type']}",
            f"- Updated: {row['updated_at']}",
            "",
            "## Notes",
            "",
        ]
        if notes.notes:
            lines.extend(f"- {note.content.get('text', note.content)}" for note in notes.notes)
        else:
            lines.append("No notes.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        files.append(path)
    return files


async def _export_audit(
    session: AsyncSession,
    user: ConnectedUser,
    exports_dir: Path,
) -> Path:
    """导出当天审计摘要。"""
    audit_dir = exports_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).date().isoformat()
    result = await session.execute(
        text(
            """
            SELECT ae.event_type, ae.status, ae.external_provider, ae.external_resource_id, ae.updated_at
            FROM action_events ae
            JOIN proposal_items pi ON pi.id = ae.proposal_item_id
            JOIN proposal_groups pg ON pg.id = pi.proposal_group_id
            WHERE pg.user_id = :user_id
            ORDER BY ae.updated_at DESC
            """
        ),
        {"user_id": user.user_id},
    )
    path = audit_dir / f"{today}.md"
    lines = ["# Audit", "", f"Date: {today}", ""]
    rows = list(result.mappings())
    if rows:
        for row in rows:
            lines.append(
                "- "
                f"{row['updated_at']} / {row['event_type']} / {row['status']} / "
                f"{_markdown_value(row['external_provider'])} / "
                f"{_markdown_value(row['external_resource_id'])}"
            )
    else:
        lines.append("No action events.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _markdown_value(value: Any) -> str:
    """把 SQLite 值转换成可读 Markdown 文本。"""
    if value is None or value == "":
        return "not set"
    return str(value)


def _safe_filename(value: str) -> str:
    """生成适合本地文件名的联系人文件名。"""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.lower())
