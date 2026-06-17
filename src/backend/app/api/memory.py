from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.memory import (
    ContactNoteResponse,
    MarkdownExportRequest,
    MarkdownExportResponse,
    MemoryCandidateCreateRequest,
    MemoryRecordResponse,
    ShortTermMemoryResponse,
)
from app.services.memory import (
    build_short_term_memory,
    create_memory_candidate,
    export_markdown_bundle,
    recall_contact_notes,
)
from app.services.settings import require_connected_user

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/threads/{thread_id}/short-term", response_model=ShortTermMemoryResponse)
async def read_short_term_memory(
    thread_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ShortTermMemoryResponse:
    """读取某个 Thread 的短期记忆。"""
    user = await require_connected_user(session)
    return await build_short_term_memory(session, user, thread_id)


@router.post("/candidates", response_model=MemoryRecordResponse | None)
async def add_memory_candidate(
    payload: MemoryCandidateCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MemoryRecordResponse | None:
    """创建长期记忆候选。"""
    user = await require_connected_user(session)
    return await create_memory_candidate(session, user, payload)


@router.get("/contacts/{contact_email}/notes", response_model=ContactNoteResponse)
async def read_contact_notes(
    contact_email: str,
    session: AsyncSession = Depends(get_db_session),
) -> ContactNoteResponse:
    """按需召回联系人备注。"""
    user = await require_connected_user(session)
    return await recall_contact_notes(session, user, contact_email)


@router.post("/exports/markdown", response_model=MarkdownExportResponse)
async def export_markdown(
    payload: MarkdownExportRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MarkdownExportResponse:
    """导出用户偏好、署名、联系人和审计 Markdown。"""
    user = await require_connected_user(session)
    return await export_markdown_bundle(session, user, include_audit=payload.include_audit)
