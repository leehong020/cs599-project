from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """验证 API 进程和 SQLite 连接都处于可用状态。

    阶段 1 前端会调用这个接口，证明 Vite 代理和后端数据库初始化
    在 OAuth、聊天流等复杂功能接入前已经跑通。
    """
    settings = get_settings()
    session_factory = get_session_factory()

    # 这里故意执行一次真实数据库往返，而不是直接返回内存里的 "ok"。
    # 这样能更早发现 SQLite 路径错误、迁移未执行或数据库连接不可用。
    async with session_factory() as session:
        await session.execute(text("SELECT 1"))

    return HealthResponse(status="ok", environment=settings.app_env)
