from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.config import get_settings
from app.core.security import TokenEncryptionError
from app.schemas.auth import GoogleAuthStatusResponse
from app.services.oauth import (
    OAuthConfigurationError,
    OAuthProviderError,
    build_authorization_url,
    create_oauth_state,
    disconnect_google_user,
    exchange_code_for_token,
    fetch_google_userinfo,
    get_google_connection_status,
    upsert_connected_google_user,
)

router = APIRouter(tags=["auth"])


@router.get("/auth/google/login")
async def start_google_login() -> Response:
    """启动 Google OAuth 授权流程。

    前端只需要跳转到这个后端地址。真正的 client secret 留在后端 `.env`，
    不进入前端 bundle，也不会被浏览器看到。
    """
    state = create_oauth_state()
    try:
        authorization_url = build_authorization_url(state)
    except OAuthConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    response = RedirectResponse(authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.set_cookie(
        key="mailflow_google_oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        max_age=10 * 60,
    )
    return response


@router.get("/auth/google/status", response_model=GoogleAuthStatusResponse)
async def get_google_status(
    session: AsyncSession = Depends(get_db_session),
) -> GoogleAuthStatusResponse:
    """返回前端渲染“已连接 / 需要重新连接”所需的状态。"""
    try:
        status_payload = await get_google_connection_status(session)
    except OAuthConfigurationError as exc:
        return GoogleAuthStatusResponse(
            connected=False,
            oauth_configured=False,
            message=str(exc),
        )
    except TokenEncryptionError as exc:
        return GoogleAuthStatusResponse(
            connected=False,
            needs_reconnect=True,
            message=str(exc),
        )
    return GoogleAuthStatusResponse.model_validate(status_payload)


@router.post("/auth/google/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_google(
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """删除本地保存的 Google OAuth token。"""
    await disconnect_google_user(session)


callback_router = APIRouter(tags=["auth"])


@callback_router.get("/gmail/auth/callback")
async def handle_google_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """处理 Google OAuth callback，并把结果跳回前端。"""
    frontend_url = get_settings().frontend_base_url
    if error:
        return RedirectResponse(f"{frontend_url}/?google_auth=error&reason={error}")

    expected_state = request.cookies.get("mailflow_google_oauth_state")
    if not code or not state or not expected_state or state != expected_state:
        return RedirectResponse(f"{frontend_url}/?google_auth=state_mismatch")

    try:
        token_payload = await exchange_code_for_token(code)
        userinfo = await fetch_google_userinfo(token_payload["access_token"])
        await upsert_connected_google_user(session, token_payload, userinfo)
    except (OAuthConfigurationError, OAuthProviderError, TokenEncryptionError) as exc:
        return RedirectResponse(f"{frontend_url}/?google_auth=error&reason={type(exc).__name__}")

    response = RedirectResponse(f"{frontend_url}/?google_auth=connected")
    response.delete_cookie("mailflow_google_oauth_state")
    return response
