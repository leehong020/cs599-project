"""本地草稿上下文服务。

这个模块只处理 SQLite 中的 Work Item / Artifact，不调用 Gmail 或
Google Calendar。聊天 agent 每轮都需要知道“当前正在修改哪封邮件或哪
个日程”，否则模型很容易把用户的补充信息当成新任务，重复创建草稿。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.oauth import ConnectedUser, now_iso


async def load_active_artifact(
    session: AsyncSession,
    user: ConnectedUser,
    thread_id: str | None,
    artifact_type: str,
) -> dict[str, Any] | None:
    """读取当前会话最近一个打开中的指定类型 Artifact。

    `artifact_type` 目前主要是 `email_draft` 和 `calendar_event_draft`。
    返回值会被注入系统 prompt，也会被工具在用户省略 artifact_id 时作为
    默认目标使用。
    """
    if not thread_id:
        return None
    result = await session.execute(
        text(
            """
            SELECT
                a.id AS artifact_id,
                a.work_item_id,
                a.artifact_type,
                a.version,
                a.content_json,
                wi.title,
                wi.summary,
                wi.maturity,
                wi.status,
                wi.updated_at
            FROM artifacts a
            JOIN work_items wi ON wi.id = a.work_item_id
            WHERE wi.user_id = :user_id
              AND wi.thread_id = :thread_id
              AND wi.status = 'open'
              AND a.artifact_type = :artifact_type
            ORDER BY wi.updated_at DESC
            LIMIT 1
            """
        ),
        {
            "user_id": user.user_id,
            "thread_id": thread_id,
            "artifact_type": artifact_type,
        },
    )
    row = result.mappings().first()
    return _row_to_artifact(row) if row else None


async def load_artifact_for_update(
    session: AsyncSession,
    user: ConnectedUser,
    artifact_id: str,
    artifact_type: str,
) -> dict[str, Any] | None:
    """按 id 读取当前用户可修改的 Artifact。"""
    result = await session.execute(
        text(
            """
            SELECT
                a.id AS artifact_id,
                a.work_item_id,
                a.artifact_type,
                a.version,
                a.content_json,
                wi.title,
                wi.summary,
                wi.maturity,
                wi.status,
                wi.updated_at
            FROM artifacts a
            JOIN work_items wi ON wi.id = a.work_item_id
            WHERE a.id = :artifact_id
              AND wi.user_id = :user_id
              AND a.artifact_type = :artifact_type
            """
        ),
        {
            "artifact_id": artifact_id,
            "user_id": user.user_id,
            "artifact_type": artifact_type,
        },
    )
    row = result.mappings().first()
    return _row_to_artifact(row) if row else None


async def update_artifact_content(
    session: AsyncSession,
    *,
    artifact_id: str,
    work_item_id: str,
    version: int,
    content: dict[str, Any],
    title: str,
    summary: str | None,
    maturity: str | None = None,
    status: str | None = None,
) -> int:
    """更新 Artifact 内容并同步 Work Item 摘要。

    返回新的 Artifact version。每次修改版本号递增，旧 Proposal 会因为
    version / fingerprint 不匹配而失效。
    """
    timestamp = now_iso()
    next_version = int(version or 1) + 1
    await session.execute(
        text(
            """
            UPDATE artifacts
            SET version = :version,
                content_json = :content_json,
                updated_at = :updated_at
            WHERE id = :artifact_id
            """
        ),
        {
            "version": next_version,
            "content_json": json.dumps(content, ensure_ascii=False, sort_keys=True),
            "updated_at": timestamp,
            "artifact_id": artifact_id,
        },
    )

    updates = [
        "title = :title",
        "summary = :summary",
        "updated_at = :updated_at",
    ]
    params: dict[str, Any] = {
        "work_item_id": work_item_id,
        "title": title,
        "summary": summary,
        "updated_at": timestamp,
    }
    if maturity is not None:
        updates.append("maturity = :maturity")
        params["maturity"] = maturity
    if status is not None:
        updates.append("status = :status")
        params["status"] = status

    await session.execute(
        text(f"UPDATE work_items SET {', '.join(updates)} WHERE id = :work_item_id"),
        params,
    )
    await session.commit()
    return next_version


async def close_work_item(
    session: AsyncSession,
    *,
    work_item_id: str,
    status: str,
) -> None:
    """关闭已经执行完成的 Work Item。"""
    await session.execute(
        text(
            """
            UPDATE work_items
            SET status = :status, updated_at = :updated_at
            WHERE id = :work_item_id
            """
        ),
        {"status": status, "updated_at": now_iso(), "work_item_id": work_item_id},
    )
    await session.commit()


def _row_to_artifact(row: Any) -> dict[str, Any]:
    """把 SQLAlchemy RowMapping 转成 prompt 和工具都能使用的普通字典。"""
    content = json.loads(row["content_json"] or "{}")
    return {
        "artifact_id": row["artifact_id"],
        "work_item_id": row["work_item_id"],
        "artifact_type": row["artifact_type"],
        "version": row["version"],
        "title": row["title"],
        "summary": row["summary"],
        "maturity": row["maturity"],
        "status": row["status"],
        "updated_at": row["updated_at"],
        "content": content,
    }
