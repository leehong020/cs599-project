from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import decrypt_secret, encrypt_secret

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class OAuthConfigurationError(RuntimeError):
    """OAuth 应用级配置缺失时抛出的异常。"""


class OAuthProviderError(RuntimeError):
    """Google OAuth 返回失败响应时抛出的异常。"""


@dataclass(frozen=True)
class ConnectedUser:
    """本地单用户 MVP 当前已连接的 Google 用户。"""

    user_id: str
    email: str
    display_name: str | None


def now_iso() -> str:
    """生成统一的 UTC ISO 时间字符串，便于 SQLite 文本字段排序和调试。"""
    return datetime.now(UTC).isoformat()


def build_google_user_id(email: str) -> str:
    """把 Google 邮箱转换成本地用户 ID。

    MVP 先按单用户本地应用处理，不引入复杂 session 系统。使用稳定前缀
    可以避免未来接入其他 provider 时和普通内部 ID 混淆。
    """
    return f"google:{email.strip().lower()}"


def configured_google_scopes(settings: Settings | None = None) -> list[str]:
    """返回当前 Google OAuth scope 列表。"""
    active_settings = settings or get_settings()
    return [
        scope.strip()
        for scope in active_settings.google_oauth_scopes.split()
        if scope.strip()
    ]


def ensure_oauth_configured(settings: Settings | None = None) -> Settings:
    """确认 OAuth 应用级配置已经填好。

    `GOOGLE_CLIENT_SECRET` 只能在后端 `.env` 中出现。前端连接按钮不会、
    也不应该接收这个值。
    """
    active_settings = settings or get_settings()
    missing_fields = [
        field_name
        for field_name, value in {
            "GOOGLE_CLIENT_ID": active_settings.google_client_id,
            "GOOGLE_CLIENT_SECRET": active_settings.google_client_secret,
            "GOOGLE_REDIRECT_URI": active_settings.google_redirect_uri,
        }.items()
        if not value or value == "replace-me"
    ]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise OAuthConfigurationError(f"Google OAuth 配置缺失：{joined}")
    return active_settings


def create_oauth_state() -> str:
    """创建防 CSRF 的 state 值，callback 时需要和 cookie 中的值一致。"""
    return secrets.token_urlsafe(24)


def build_authorization_url(state: str, settings: Settings | None = None) -> str:
    """生成 Google 授权跳转地址。"""
    active_settings = ensure_oauth_configured(settings)
    params = {
        "client_id": active_settings.google_client_id,
        "redirect_uri": active_settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(configured_google_scopes(active_settings)),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str, settings: Settings | None = None) -> dict[str, Any]:
    """用 Google callback code 换取 access token 和 refresh token。"""
    active_settings = ensure_oauth_configured(settings)
    payload = {
        "code": code,
        "client_id": active_settings.google_client_id,
        "client_secret": active_settings.google_client_secret,
        "redirect_uri": active_settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=payload)

    if response.status_code >= 400:
        raise OAuthProviderError("Google token 交换失败，请检查 OAuth Client 配置。")
    return response.json()


async def fetch_google_userinfo(access_token: str) -> dict[str, Any]:
    """读取当前授权账号的邮箱和展示名。"""
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code >= 400:
        raise OAuthProviderError("Google 用户信息读取失败，请重新授权。")
    return response.json()


async def refresh_access_token(
    session: AsyncSession,
    user_id: str,
    settings: Settings | None = None,
) -> bool:
    """刷新已过期的 access token。

    如果没有 refresh token 或刷新失败，调用方应把状态展示为“需要重新连接”，
    而不是继续尝试 Gmail/Calendar 外部操作。
    """
    active_settings = ensure_oauth_configured(settings)
    result = await session.execute(
        text(
            """
            SELECT encrypted_refresh_token
            FROM oauth_credentials
            WHERE user_id = :user_id AND provider = 'google'
            """
        ),
        {"user_id": user_id},
    )
    row = result.mappings().first()
    if row is None or row["encrypted_refresh_token"] is None:
        return False

    refresh_token = decrypt_secret(row["encrypted_refresh_token"], active_settings)
    payload = {
        "client_id": active_settings.google_client_id,
        "client_secret": active_settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=payload)
    if response.status_code >= 400:
        return False

    token_payload = response.json()
    expires_at = datetime.now(UTC) + timedelta(seconds=int(token_payload.get("expires_in", 3600)))
    await session.execute(
        text(
            """
            UPDATE oauth_credentials
            SET encrypted_access_token = :access_token,
                expires_at = :expires_at,
                scopes_json = :scopes_json,
                updated_at = :updated_at
            WHERE user_id = :user_id AND provider = 'google'
            """
        ),
        {
            "user_id": user_id,
            "access_token": encrypt_secret(token_payload["access_token"], active_settings),
            "expires_at": expires_at.isoformat(),
            "scopes_json": json.dumps(configured_google_scopes(active_settings), ensure_ascii=False),
            "updated_at": now_iso(),
        },
    )
    await session.commit()
    return True


async def upsert_connected_google_user(
    session: AsyncSession,
    token_payload: dict[str, Any],
    userinfo: dict[str, Any],
    settings: Settings | None = None,
) -> ConnectedUser:
    """保存或更新 OAuth 用户、默认设置和加密后的 token。"""
    active_settings = settings or get_settings()
    email = str(userinfo.get("email", "")).strip().lower()
    if not email:
        raise OAuthProviderError("Google 未返回邮箱，无法建立本地用户。")

    display_name = userinfo.get("name")
    user_id = build_google_user_id(email)
    timestamp = now_iso()
    expires_at = datetime.now(UTC) + timedelta(seconds=int(token_payload.get("expires_in", 3600)))

    # 先写 users 和 user_settings，再写 token。这样即使后续设置页马上打开，
    # 也能读到一条稳定的本地用户记录。
    await session.execute(
        text(
            """
            INSERT INTO users (id, email, display_name, created_at, updated_at)
            VALUES (:id, :email, :display_name, :created_at, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                email = excluded.email,
                display_name = excluded.display_name,
                updated_at = excluded.updated_at
            """
        ),
        {
            "id": user_id,
            "email": email,
            "display_name": display_name,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO user_settings (
                user_id, default_sender_email, meeting_buffer_minutes, created_at, updated_at
            )
            VALUES (:user_id, :default_sender_email, 0, :created_at, :updated_at)
            ON CONFLICT(user_id) DO NOTHING
            """
        ),
        {
            "user_id": user_id,
            "default_sender_email": email,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )

    old_refresh = await session.execute(
        text(
            """
            SELECT encrypted_refresh_token
            FROM oauth_credentials
            WHERE user_id = :user_id AND provider = 'google'
            """
        ),
        {"user_id": user_id},
    )
    old_row = old_refresh.mappings().first()
    refresh_token = token_payload.get("refresh_token")
    encrypted_refresh_token = (
        encrypt_secret(refresh_token, active_settings)
        if refresh_token
        else (old_row["encrypted_refresh_token"] if old_row else None)
    )

    await session.execute(
        text(
            """
            INSERT INTO oauth_credentials (
                user_id,
                provider,
                encrypted_access_token,
                encrypted_refresh_token,
                expires_at,
                scopes_json,
                created_at,
                updated_at
            )
            VALUES (
                :user_id,
                'google',
                :encrypted_access_token,
                :encrypted_refresh_token,
                :expires_at,
                :scopes_json,
                :created_at,
                :updated_at
            )
            ON CONFLICT(user_id) DO UPDATE SET
                encrypted_access_token = excluded.encrypted_access_token,
                encrypted_refresh_token = excluded.encrypted_refresh_token,
                expires_at = excluded.expires_at,
                scopes_json = excluded.scopes_json,
                updated_at = excluded.updated_at
            """
        ),
        {
            "user_id": user_id,
            "encrypted_access_token": encrypt_secret(token_payload["access_token"], active_settings),
            "encrypted_refresh_token": encrypted_refresh_token,
            "expires_at": expires_at.isoformat(),
            "scopes_json": json.dumps(configured_google_scopes(active_settings), ensure_ascii=False),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    return ConnectedUser(user_id=user_id, email=email, display_name=display_name)


async def get_connected_google_user(session: AsyncSession) -> ConnectedUser | None:
    """读取当前本地已连接的 Google 用户。

    阶段 2 按单用户本地应用处理，所以这里取最近更新的 Google credential。
    后续如果引入多用户 session，应把 user_id 从登录态传入，而不是这样推断。
    """
    result = await session.execute(
        text(
            """
            SELECT u.id, u.email, u.display_name
            FROM users u
            JOIN oauth_credentials oc ON oc.user_id = u.id
            WHERE oc.provider = 'google'
            ORDER BY oc.updated_at DESC
            LIMIT 1
            """
        )
    )
    row = result.mappings().first()
    if row is None:
        return None
    return ConnectedUser(
        user_id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
    )


async def get_google_connection_status(session: AsyncSession) -> dict[str, Any]:
    """返回前端显示连接状态所需的最小信息。"""
    result = await session.execute(
        text(
            """
            SELECT u.id, u.email, u.display_name, oc.expires_at, oc.scopes_json
            FROM users u
            JOIN oauth_credentials oc ON oc.user_id = u.id
            WHERE oc.provider = 'google'
            ORDER BY oc.updated_at DESC
            LIMIT 1
            """
        )
    )
    row = result.mappings().first()
    if row is None:
        return {"connected": False, "needs_reconnect": False, "scopes": []}

    needs_reconnect = False
    expires_at_raw = row["expires_at"]
    if expires_at_raw:
        expires_at = datetime.fromisoformat(expires_at_raw)
        if expires_at <= datetime.now(UTC):
            refreshed = await refresh_access_token(session, row["id"])
            needs_reconnect = not refreshed

    return {
        "connected": not needs_reconnect,
        "needs_reconnect": needs_reconnect,
        "email": row["email"],
        "display_name": row["display_name"],
        "scopes": json.loads(row["scopes_json"] or "[]"),
        "message": "Google 授权已失效，请重新连接账号。" if needs_reconnect else None,
    }


async def get_valid_google_access_token(
    session: AsyncSession,
    user_id: str,
    settings: Settings | None = None,
) -> str:
    """读取可用的 Google access token。

    Gmail 和 Calendar 客户端只能通过这个函数拿 token。这样 token 解密、
    过期刷新和重新连接提示都集中在 OAuth 服务层，避免外部 API 客户端
    各自处理密钥，增加泄露风险。
    """
    active_settings = ensure_oauth_configured(settings)
    result = await session.execute(
        text(
            """
            SELECT encrypted_access_token, expires_at
            FROM oauth_credentials
            WHERE user_id = :user_id AND provider = 'google'
            """
        ),
        {"user_id": user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise OAuthProviderError("请先连接 Google 账号。")

    expires_at_raw = row["expires_at"]
    if expires_at_raw:
        expires_at = datetime.fromisoformat(expires_at_raw)
        if expires_at <= datetime.now(UTC):
            refreshed = await refresh_access_token(session, user_id, active_settings)
            if not refreshed:
                raise OAuthProviderError("Google 授权已失效，请重新连接账号。")
            result = await session.execute(
                text(
                    """
                    SELECT encrypted_access_token
                    FROM oauth_credentials
                    WHERE user_id = :user_id AND provider = 'google'
                    """
                ),
                {"user_id": user_id},
            )
            row = result.mappings().one()

    encrypted_access_token = row["encrypted_access_token"]
    if not encrypted_access_token:
        raise OAuthProviderError("Google access token 缺失，请重新连接账号。")
    return decrypt_secret(encrypted_access_token, active_settings)


async def disconnect_google_user(session: AsyncSession) -> None:
    """断开本地 Google 连接。

    这里删除的是本地加密 token，不会删除用户设置和本地草稿。用户如果想让
    Google 侧也撤销授权，需要到 Google 账号安全页撤销第三方应用访问。
    """
    await session.execute(text("DELETE FROM oauth_credentials WHERE provider = 'google'"))
    await session.commit()
