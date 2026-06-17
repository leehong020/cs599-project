from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


def get_engine():
    """创建访问 MVP SQLite 数据库的异步 SQLAlchemy engine。

    这里主动创建 runtime 目录，是因为健康检查、测试或 Alembic 迁移
    都可能成为第一个触碰数据库的代码路径。
    """
    settings = get_settings()
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    return create_async_engine(settings.database_url, future=True)


# 阶段 1 的 MVP 是单进程本地应用，因此 engine 和 sessionmaker 先作为
# 模块级单例存在。若后续支持多租户或按请求切换数据库，需要在这里
# 替换成更显式的 engine/session registry。
engine = get_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """暴露 session factory，供需要自行管理生命周期的服务层代码使用。"""
    return AsyncSessionLocal


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每个请求提供一个独立的异步数据库 session。"""
    async with AsyncSessionLocal() as session:
        yield session
