from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 阶段 1 的表结构先由手写 migration 定义，因此当前 metadata 还是空的。
# 后续补 SQLAlchemy ORM model 时，应统一继承 Base，这样 Alembic
# autogenerate 才能比较模型元数据和真实数据库之间的差异。
target_metadata = Base.metadata


def get_url() -> str:
    """返回和应用运行时完全一致的数据库 URL。"""
    settings = get_settings()
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    return settings.database_url


def run_migrations_offline() -> None:
    """离线生成 SQL，不打开数据库连接。

    本地 MVP 很少用离线模式，但保留它能让未来发布脚本继续使用
    Alembic 的标准能力。
    """
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """在 Alembic 提供的同步连接上执行迁移。"""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """把 Alembic 的迁移执行器桥接到异步 SQLite engine。

    应用使用 `sqlite+aiosqlite`，迁移时也要创建 async engine，
    再通过 `connection.run_sync` 执行 Alembic 的同步迁移主体。
    """
    settings = get_settings()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """普通 `alembic upgrade head` 的在线迁移入口。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
