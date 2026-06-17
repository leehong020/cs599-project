import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.graph.subgraphs import run_calendar_subgraph_once, run_mail_subgraph_once
from app.schemas.memory import MemoryCandidateCreateRequest
from app.services.memory import (
    RECENT_MESSAGE_LIMIT,
    build_short_term_memory,
    create_memory_candidate,
    export_markdown_bundle,
    recall_contact_notes,
    should_store_long_term_memory,
)
from app.services.oauth import ConnectedUser, now_iso


@pytest_asyncio.fixture
async def memory_session() -> AsyncSession:
    """创建阶段 9 测试专用 SQLite 数据库。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        for statement in MEMORY_TEST_SCHEMA:
            await connection.execute(text(statement))
    async with session_factory() as session:
        yield session
    await engine.dispose()


MEMORY_TEST_SCHEMA = [
    """
    CREATE TABLE users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        display_name TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE user_settings (
        user_id TEXT PRIMARY KEY,
        timezone TEXT,
        default_calendar_id TEXT,
        default_signature_id TEXT,
        default_sender_email TEXT,
        default_meeting_duration_minutes INTEGER,
        meeting_buffer_minutes INTEGER,
        working_hours_json TEXT,
        lunch_break_json TEXT,
        email_tone_internal TEXT,
        email_tone_external TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE signatures (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        label TEXT NOT NULL,
        content TEXT NOT NULL,
        is_default INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE contacts (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        display_name TEXT NOT NULL,
        email TEXT,
        source_type TEXT NOT NULL,
        source_ref TEXT,
        metadata_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE work_items (
        id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        work_item_type TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT,
        maturity TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE proposal_groups (
        id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE proposal_items (
        id TEXT PRIMARY KEY,
        proposal_group_id TEXT NOT NULL,
        work_item_id TEXT NOT NULL,
        action_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        version INTEGER NOT NULL,
        fingerprint TEXT NOT NULL,
        status TEXT NOT NULL,
        expires_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE action_events (
        id TEXT PRIMARY KEY,
        proposal_item_id TEXT,
        event_type TEXT NOT NULL,
        status TEXT NOT NULL,
        idempotency_key TEXT,
        external_provider TEXT,
        external_resource_id TEXT,
        payload_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE memories (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        namespace TEXT NOT NULL,
        memory_key TEXT NOT NULL,
        memory_type TEXT NOT NULL,
        content_json TEXT NOT NULL,
        confidence REAL NOT NULL,
        status TEXT NOT NULL,
        source_thread_id TEXT,
        source_message_id TEXT,
        expires_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
]


async def seed_memory_user(session: AsyncSession) -> ConnectedUser:
    """写入阶段 9 测试用户和基础事实。"""
    timestamp = now_iso()
    user = ConnectedUser("google:test@example.com", "test@example.com", None)
    await session.execute(
        text(
            """
            INSERT INTO users (id, email, display_name, created_at, updated_at)
            VALUES (:id, :email, 'Test User', :created_at, :updated_at)
            """
        ),
        {
            "id": user.user_id,
            "email": user.email,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO user_settings (
                user_id, timezone, default_calendar_id, default_signature_id,
                default_sender_email, default_meeting_duration_minutes,
                meeting_buffer_minutes, working_hours_json, lunch_break_json,
                email_tone_internal, email_tone_external, created_at, updated_at
            )
            VALUES (
                :user_id, 'Asia/Shanghai', 'primary', 'sig_default',
                'test@example.com', 45, 10, NULL, NULL,
                '简洁', '礼貌', :created_at, :updated_at
            )
            """
        ),
        {"user_id": user.user_id, "created_at": timestamp, "updated_at": timestamp},
    )
    await session.execute(
        text(
            """
            INSERT INTO signatures (id, user_id, label, content, is_default, created_at, updated_at)
            VALUES ('sig_default', :user_id, '默认署名', 'Regards', 1, :created_at, :updated_at)
            """
        ),
        {"user_id": user.user_id, "created_at": timestamp, "updated_at": timestamp},
    )
    await session.execute(
        text(
            """
            INSERT INTO contacts (
                id, user_id, display_name, email, source_type, source_ref,
                metadata_json, created_at, updated_at
            )
            VALUES (
                'contact_1', :user_id, 'Alice', 'alice@example.com', 'manual',
                NULL, NULL, :created_at, :updated_at
            )
            """
        ),
        {"user_id": user.user_id, "created_at": timestamp, "updated_at": timestamp},
    )
    await session.commit()
    return user


def test_long_term_memory_requires_explicit_non_temporary_signal() -> None:
    assert should_store_long_term_memory("请记住以后会议默认 45 分钟")
    assert not should_store_long_term_memory("这次临时用更正式的语气")


@pytest.mark.asyncio
async def test_create_memory_candidate_blocks_temporary_instruction(
    memory_session: AsyncSession,
) -> None:
    user = await seed_memory_user(memory_session)

    skipped = await create_memory_candidate(
        memory_session,
        user,
        MemoryCandidateCreateRequest(message="这次临时用更正式的语气"),
    )
    stored = await create_memory_candidate(
        memory_session,
        user,
        MemoryCandidateCreateRequest(thread_id="thread_1", message="请记住以后会议默认 45 分钟"),
    )

    assert skipped is None
    assert stored is not None
    assert stored.status == "candidate"


@pytest.mark.asyncio
async def test_short_term_memory_uses_recent_window_and_summary(
    memory_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await seed_memory_user(memory_session)
    timestamp = now_iso()
    await memory_session.execute(
        text(
            """
            INSERT INTO work_items (
                id, thread_id, user_id, work_item_type, title, summary,
                maturity, status, created_at, updated_at
            )
            VALUES (
                'wi_1', 'thread_memory', :user_id, 'email_draft', '邮件',
                '摘要', 'reviewable', 'open', :created_at, :updated_at
            )
            """
        ),
        {"user_id": user.user_id, "created_at": timestamp, "updated_at": timestamp},
    )
    await memory_session.commit()
    messages = [{"role": "user", "content": f"消息 {index}"} for index in range(24)]
    monkeypatch.setattr(
        "app.services.memory.get_assistant_thread_state",
        lambda thread_id: {
            "messages": messages,
            "tasks": [{"id": "task_mail_1", "domain": "mail"}],
            "task_batches": [["task_mail_1"]],
            "artifacts": [
                {
                    "id": "artifact_1",
                    "task_id": "task_mail_1",
                    "artifact_type": "email_draft",
                    "content": {"summary": "邮件摘要"},
                }
            ],
            "action_results": [{"status": "skipped"}],
        },
    )

    result = await build_short_term_memory(memory_session, user, "thread_memory")

    assert len(result.recent_messages) == RECENT_MESSAGE_LIMIT
    assert result.conversation_summary is not None
    assert result.open_work_items[0]["id"] == "wi_1"
    assert result.task_dag[0]["domain"] == "mail"
    assert result.artifact_summaries[0]["summary"] == "邮件摘要"


@pytest.mark.asyncio
async def test_contact_notes_are_recalled_on_demand(memory_session: AsyncSession) -> None:
    user = await seed_memory_user(memory_session)
    timestamp = now_iso()
    await memory_session.execute(
        text(
            """
            INSERT INTO memories (
                id, user_id, namespace, memory_key, memory_type, content_json,
                confidence, status, source_thread_id, source_message_id,
                expires_at, created_at, updated_at
            )
            VALUES (
                'mem_contact', :user_id, 'contact_notes', 'alice@example.com',
                'note', :content_json, 0.9, 'active', NULL, NULL,
                NULL, :created_at, :updated_at
            )
            """
        ),
        {
            "user_id": user.user_id,
            "content_json": json.dumps({"text": "Alice 偏好上午开会"}, ensure_ascii=False),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await memory_session.commit()

    notes = await recall_contact_notes(memory_session, user, "alice@example.com")

    assert notes.notes[0].content["text"] == "Alice 偏好上午开会"


@pytest.mark.asyncio
async def test_markdown_export_uses_sqlite_facts(
    memory_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await seed_memory_user(memory_session)

    class DummySettings:
        exports_dir = tmp_path

    monkeypatch.setattr("app.services.memory.get_settings", lambda: DummySettings())

    result = await export_markdown_bundle(memory_session, user)

    exported = {Path(path).name for path in result.files}
    assert "preferences.md" in exported
    assert "signatures.md" in exported
    assert "2026-" in next(path for path in result.files if "audit" in path)
    assert "default_meeting_duration_minutes" in (tmp_path / "preferences.md").read_text(
        encoding="utf-8"
    )
    assert "Regards" in (tmp_path / "signatures.md").read_text(encoding="utf-8")


def test_mail_and_calendar_subgraphs_do_not_inject_unrelated_context() -> None:
    tasks = [
        {
            "id": "task_mail_1",
            "domain": "mail",
            "title": "邮件",
            "depends_on": [],
            "status": "planned",
            "reason": None,
        },
        {
            "id": "task_calendar_1",
            "domain": "calendar",
            "title": "日程",
            "depends_on": [],
            "status": "planned",
            "reason": None,
        },
    ]

    mail_result = run_mail_subgraph_once(tasks)
    calendar_result = run_calendar_subgraph_once(tasks)

    assert all(item["domain"] == "mail" for item in mail_result["task_results"])
    assert all(item["domain"] == "calendar" for item in calendar_result["task_results"])
