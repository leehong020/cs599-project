from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.gmail import (
    EmailArtifactResponse,
    GmailMessageDetail,
    GmailSearchRequest,
    GmailSearchResponse,
    GmailThreadDetail,
    PrepareForwardEmailRequest,
    PrepareNewEmailRequest,
    PrepareReplyEmailRequest,
)
from app.services.gmail import (
    build_gmail_client_for_user,
    prepare_forward_email_artifact,
    prepare_new_email_artifact,
    prepare_reply_email_artifact,
)
from app.services.settings import require_connected_user

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.post("/search", response_model=GmailSearchResponse)
async def search_emails(
    payload: GmailSearchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> GmailSearchResponse:
    """搜索 Gmail 邮件。"""
    user = await require_connected_user(session)
    client = await build_gmail_client_for_user(session, user)
    return await client.search_messages(payload.query, payload.max_results)


@router.get("/messages/{message_id}", response_model=GmailMessageDetail)
async def read_email(
    message_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> GmailMessageDetail:
    """读取单封 Gmail 邮件详情。"""
    user = await require_connected_user(session)
    client = await build_gmail_client_for_user(session, user)
    return await client.get_message(message_id)


@router.get("/threads/{thread_id}", response_model=GmailThreadDetail)
async def read_email_thread(
    thread_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> GmailThreadDetail:
    """读取 Gmail Thread 详情。"""
    user = await require_connected_user(session)
    client = await build_gmail_client_for_user(session, user)
    return await client.get_thread(thread_id)


@router.post("/prepare/new", response_model=EmailArtifactResponse)
async def prepare_new_email(
    payload: PrepareNewEmailRequest,
    session: AsyncSession = Depends(get_db_session),
) -> EmailArtifactResponse:
    """准备新邮件本地草稿。"""
    user = await require_connected_user(session)
    return await prepare_new_email_artifact(session, user, payload)


@router.post("/prepare/reply", response_model=EmailArtifactResponse)
async def prepare_reply_email(
    payload: PrepareReplyEmailRequest,
    session: AsyncSession = Depends(get_db_session),
) -> EmailArtifactResponse:
    """准备回复邮件本地草稿，并保存 Gmail thread 关系。"""
    user = await require_connected_user(session)
    return await prepare_reply_email_artifact(session, user, payload)


@router.post("/prepare/forward", response_model=EmailArtifactResponse)
async def prepare_forward_email(
    payload: PrepareForwardEmailRequest,
    session: AsyncSession = Depends(get_db_session),
) -> EmailArtifactResponse:
    """准备转发邮件本地草稿。"""
    user = await require_connected_user(session)
    return await prepare_forward_email_artifact(session, user, payload)


@router.delete("/messages/{message_id}")
async def delete_email(
    message_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """将邮件移至垃圾箱。"""
    user = await require_connected_user(session)
    client = await build_gmail_client_for_user(session, user)
    await client.trash_message(message_id)
    return {"status": "trashed", "message_id": message_id}
