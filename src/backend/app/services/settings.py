import json
import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.settings import (
    ContactCreateRequest,
    ContactResponse,
    ContactUpdateRequest,
    SignatureCreateRequest,
    SignatureResponse,
    SignatureUpdateRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
    WorkingHours,
)
from app.services.oauth import ConnectedUser, get_connected_google_user, now_iso

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def require_connected_user(session: AsyncSession) -> ConnectedUser:
    """要求当前本地应用已经连接 Google 账号。"""
    user = await get_connected_google_user(session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先连接 Google 账号。",
        )
    return user


def _loads_hours(raw: str | None) -> WorkingHours | None:
    """从 SQLite 文本字段恢复时间段结构。"""
    if raw is None:
        return None
    return WorkingHours.model_validate(json.loads(raw))


def _dumps_hours(value: WorkingHours | None) -> str | None:
    """把时间段结构序列化为 SQLite 文本字段。"""
    if value is None:
        return None
    return json.dumps(value.model_dump(), ensure_ascii=False)


async def get_user_profile(session: AsyncSession, user: ConnectedUser) -> UserProfileResponse:
    """读取用户设置页资料。"""
    result = await session.execute(
        text(
            """
            SELECT
                u.id AS user_id,
                u.email,
                u.display_name,
                us.timezone,
                us.default_calendar_id,
                us.default_signature_id,
                us.default_sender_email,
                us.default_meeting_duration_minutes,
                us.meeting_buffer_minutes,
                us.working_hours_json,
                us.lunch_break_json,
                us.email_tone_internal,
                us.email_tone_external
            FROM users u
            LEFT JOIN user_settings us ON us.user_id = u.id
            WHERE u.id = :user_id
            """
        ),
        {"user_id": user.user_id},
    )
    row = result.mappings().one()
    return UserProfileResponse(
        user_id=row["user_id"],
        email=row["email"],
        display_name=row["display_name"],
        timezone=row["timezone"],
        default_calendar_id=row["default_calendar_id"],
        default_signature_id=row["default_signature_id"],
        default_sender_email=row["default_sender_email"],
        default_meeting_duration_minutes=row["default_meeting_duration_minutes"],
        meeting_buffer_minutes=row["meeting_buffer_minutes"] or 0,
        working_hours=_loads_hours(row["working_hours_json"]),
        lunch_break=_loads_hours(row["lunch_break_json"]),
        email_tone_internal=row["email_tone_internal"],
        email_tone_external=row["email_tone_external"],
    )


async def update_user_profile(
    session: AsyncSession,
    user: ConnectedUser,
    payload: UserProfileUpdateRequest,
) -> UserProfileResponse:
    """更新用户确定性偏好。"""
    timestamp = now_iso()
    await session.execute(
        text(
            """
            INSERT INTO user_settings (
                user_id,
                timezone,
                default_calendar_id,
                default_signature_id,
                default_sender_email,
                default_meeting_duration_minutes,
                meeting_buffer_minutes,
                working_hours_json,
                lunch_break_json,
                email_tone_internal,
                email_tone_external,
                created_at,
                updated_at
            )
            VALUES (
                :user_id,
                :timezone,
                :default_calendar_id,
                :default_signature_id,
                :default_sender_email,
                :default_meeting_duration_minutes,
                :meeting_buffer_minutes,
                :working_hours_json,
                :lunch_break_json,
                :email_tone_internal,
                :email_tone_external,
                :created_at,
                :updated_at
            )
            ON CONFLICT(user_id) DO UPDATE SET
                timezone = excluded.timezone,
                default_calendar_id = excluded.default_calendar_id,
                default_signature_id = excluded.default_signature_id,
                default_sender_email = excluded.default_sender_email,
                default_meeting_duration_minutes = excluded.default_meeting_duration_minutes,
                meeting_buffer_minutes = excluded.meeting_buffer_minutes,
                working_hours_json = excluded.working_hours_json,
                lunch_break_json = excluded.lunch_break_json,
                email_tone_internal = excluded.email_tone_internal,
                email_tone_external = excluded.email_tone_external,
                updated_at = excluded.updated_at
            """
        ),
        {
            "user_id": user.user_id,
            "timezone": payload.timezone,
            "default_calendar_id": payload.default_calendar_id,
            "default_signature_id": payload.default_signature_id,
            "default_sender_email": payload.default_sender_email,
            "default_meeting_duration_minutes": payload.default_meeting_duration_minutes,
            "meeting_buffer_minutes": payload.meeting_buffer_minutes,
            "working_hours_json": _dumps_hours(payload.working_hours),
            "lunch_break_json": _dumps_hours(payload.lunch_break),
            "email_tone_internal": payload.email_tone_internal,
            "email_tone_external": payload.email_tone_external,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    return await get_user_profile(session, user)


async def list_signatures(session: AsyncSession, user: ConnectedUser) -> list[SignatureResponse]:
    """列出当前用户的署名。"""
    result = await session.execute(
        text(
            """
            SELECT id, label, content, is_default, created_at, updated_at
            FROM signatures
            WHERE user_id = :user_id
            ORDER BY is_default DESC, updated_at DESC
            """
        ),
        {"user_id": user.user_id},
    )
    return [
        SignatureResponse(
            id=row["id"],
            label=row["label"],
            content=row["content"],
            is_default=bool(row["is_default"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in result.mappings()
    ]


async def create_signature(
    session: AsyncSession,
    user: ConnectedUser,
    payload: SignatureCreateRequest,
) -> SignatureResponse:
    """保存邮件署名。

    当前产品只保留一个署名。创建新署名前会清理历史署名，避免 agent
    在多个候选署名之间选择错误。
    """
    timestamp = now_iso()
    signature_id = f"sig_{uuid.uuid4().hex}"
    await session.execute(
        text("DELETE FROM signatures WHERE user_id = :user_id"),
        {"user_id": user.user_id},
    )

    await session.execute(
        text(
            """
            INSERT INTO signatures (id, user_id, label, content, is_default, created_at, updated_at)
            VALUES (:id, :user_id, :label, :content, :is_default, :created_at, :updated_at)
            """
        ),
        {
            "id": signature_id,
            "user_id": user.user_id,
            "label": payload.label,
            "content": payload.content,
            "is_default": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await _set_profile_default_signature(session, user.user_id, signature_id)
    await session.commit()
    return (await _get_signature(session, user.user_id, signature_id))


async def update_signature(
    session: AsyncSession,
    user: ConnectedUser,
    signature_id: str,
    payload: SignatureUpdateRequest,
) -> SignatureResponse:
    """更新邮件署名，并保持当前用户只有这一条署名。"""
    existing = await _get_signature(session, user.user_id, signature_id)
    timestamp = now_iso()

    await session.execute(
        text(
            """
            UPDATE signatures
            SET label = :label,
                content = :content,
                is_default = :is_default,
                updated_at = :updated_at
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {
            "id": signature_id,
            "user_id": user.user_id,
            "label": payload.label if payload.label is not None else existing.label,
            "content": payload.content if payload.content is not None else existing.content,
            "is_default": 1,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text("DELETE FROM signatures WHERE user_id = :user_id AND id != :id"),
        {"user_id": user.user_id, "id": signature_id},
    )
    await _set_profile_default_signature(session, user.user_id, signature_id)
    await session.commit()
    return await _get_signature(session, user.user_id, signature_id)


async def delete_signature(session: AsyncSession, user: ConnectedUser, signature_id: str) -> None:
    """删除邮件署名，并清理默认署名引用。"""
    await _get_signature(session, user.user_id, signature_id)
    await session.execute(
        text("DELETE FROM signatures WHERE id = :id AND user_id = :user_id"),
        {"id": signature_id, "user_id": user.user_id},
    )
    await session.execute(
        text(
            """
            UPDATE user_settings
            SET default_signature_id = NULL, updated_at = :updated_at
            WHERE user_id = :user_id AND default_signature_id = :signature_id
            """
        ),
        {
            "user_id": user.user_id,
            "signature_id": signature_id,
            "updated_at": now_iso(),
        },
    )
    await session.commit()


async def list_contacts(session: AsyncSession, user: ConnectedUser) -> list[ContactResponse]:
    """列出当前用户的手动联系人。

    联系人同时服务邮件收件人和日程参会人解析。聊天 agent 使用它时只能
    做唯一匹配；如果同名或缺失，必须追问，不能猜邮箱。
    """
    result = await session.execute(
        text(
            """
            SELECT id, display_name, email, created_at, updated_at
            FROM contacts
            WHERE user_id = :user_id
            ORDER BY display_name COLLATE NOCASE ASC, updated_at DESC
            """
        ),
        {"user_id": user.user_id},
    )
    return [
        ContactResponse(
            id=row["id"],
            display_name=row["display_name"],
            email=row["email"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in result.mappings()
    ]


async def create_contact(
    session: AsyncSession,
    user: ConnectedUser,
    payload: ContactCreateRequest,
) -> ContactResponse:
    """创建联系人。"""
    email = _validate_contact_email(payload.email)
    timestamp = now_iso()
    contact_id = f"contact_{uuid.uuid4().hex}"
    await session.execute(
        text(
            """
            INSERT INTO contacts (
                id, user_id, display_name, email, source_type, source_ref,
                metadata_json, created_at, updated_at
            )
            VALUES (
                :id, :user_id, :display_name, :email, 'manual', NULL,
                NULL, :created_at, :updated_at
            )
            """
        ),
        {
            "id": contact_id,
            "user_id": user.user_id,
            "display_name": payload.display_name.strip(),
            "email": email,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    return await _get_contact(session, user.user_id, contact_id)


async def update_contact(
    session: AsyncSession,
    user: ConnectedUser,
    contact_id: str,
    payload: ContactUpdateRequest,
) -> ContactResponse:
    """更新联系人姓名或邮箱。"""
    existing = await _get_contact(session, user.user_id, contact_id)
    display_name = payload.display_name.strip() if payload.display_name is not None else existing.display_name
    email = _validate_contact_email(payload.email) if payload.email is not None else existing.email
    await session.execute(
        text(
            """
            UPDATE contacts
            SET display_name = :display_name,
                email = :email,
                updated_at = :updated_at
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {
            "id": contact_id,
            "user_id": user.user_id,
            "display_name": display_name,
            "email": email,
            "updated_at": now_iso(),
        },
    )
    await session.commit()
    return await _get_contact(session, user.user_id, contact_id)


async def delete_contact(session: AsyncSession, user: ConnectedUser, contact_id: str) -> None:
    """删除联系人。"""
    await _get_contact(session, user.user_id, contact_id)
    await session.execute(
        text("DELETE FROM contacts WHERE id = :id AND user_id = :user_id"),
        {"id": contact_id, "user_id": user.user_id},
    )
    await session.commit()


async def _get_signature(
    session: AsyncSession,
    user_id: str,
    signature_id: str,
) -> SignatureResponse:
    """读取单个署名，不存在时返回 404。"""
    result = await session.execute(
        text(
            """
            SELECT id, label, content, is_default, created_at, updated_at
            FROM signatures
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": signature_id, "user_id": user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="署名不存在。")
    return SignatureResponse(
        id=row["id"],
        label=row["label"],
        content=row["content"],
        is_default=bool(row["is_default"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _get_contact(
    session: AsyncSession,
    user_id: str,
    contact_id: str,
) -> ContactResponse:
    """读取单个联系人，不存在时返回 404。"""
    result = await session.execute(
        text(
            """
            SELECT id, display_name, email, created_at, updated_at
            FROM contacts
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": contact_id, "user_id": user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="联系人不存在。")
    return ContactResponse(
        id=row["id"],
        display_name=row["display_name"],
        email=row["email"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _validate_contact_email(value: str) -> str:
    """校验联系人邮箱格式。"""
    email = value.strip()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="联系人邮箱格式不正确。")
    return email


async def _clear_default_signature(session: AsyncSession, user_id: str) -> None:
    """确保同一用户只有一个默认署名。"""
    await session.execute(
        text("UPDATE signatures SET is_default = 0 WHERE user_id = :user_id"),
        {"user_id": user_id},
    )


async def _set_profile_default_signature(
    session: AsyncSession,
    user_id: str,
    signature_id: str,
) -> None:
    """同步 user_settings.default_signature_id。"""
    await session.execute(
        text(
            """
            UPDATE user_settings
            SET default_signature_id = :signature_id, updated_at = :updated_at
            WHERE user_id = :user_id
            """
        ),
        {
            "user_id": user_id,
            "signature_id": signature_id,
            "updated_at": now_iso(),
        },
    )
