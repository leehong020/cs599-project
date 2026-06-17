from pydantic import BaseModel


class GoogleAuthStatusResponse(BaseModel):
    """前端恢复 Google 连接状态时使用的响应。"""

    connected: bool
    needs_reconnect: bool = False
    oauth_configured: bool = True
    email: str | None = None
    display_name: str | None = None
    scopes: list[str] = []
    message: str | None = None


class GoogleCallbackErrorResponse(BaseModel):
    """OAuth callback 失败时的结构化错误。"""

    error: str
    message: str
