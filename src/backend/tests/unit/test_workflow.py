import json

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.schemas.workflow import AuthorizeProposalRequest, CreateProposalRequest
from app.services.oauth import ConnectedUser, now_iso
from app.services.workflow import (
    WorkflowSafetyError,
    authorize_proposal,
    compute_payload_fingerprint,
    create_proposal_from_artifact,
    resolve_confirmation_candidates,
    stable_json_dumps,
)


@pytest_asyncio.fixture
async def workflow_session() -> AsyncSession:
    """创建阶段 6 测试专用 SQLite 数据库。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        for statement in WORKFLOW_TEST_SCHEMA:
            await connection.execute(text(statement))
    async with session_factory() as session:
        yield session
    await engine.dispose()


WORKFLOW_TEST_SCHEMA = [
    """
    CREATE TABLE threads (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT,
        summary TEXT,
        status TEXT NOT NULL,
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
    CREATE TABLE artifacts (
        id TEXT PRIMARY KEY,
        work_item_id TEXT NOT NULL,
        artifact_type TEXT NOT NULL,
        version INTEGER NOT NULL,
        content_json TEXT NOT NULL,
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
    CREATE TABLE action_authorizations (
        id TEXT PRIMARY KEY,
        proposal_item_id TEXT NOT NULL,
        proposal_version INTEGER NOT NULL,
        fingerprint TEXT NOT NULL,
        user_id TEXT NOT NULL,
        decision TEXT NOT NULL,
        source TEXT NOT NULL,
        user_message_id TEXT,
        created_at TEXT NOT NULL
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
]


async def seed_artifact(
    session: AsyncSession,
    *,
    artifact_id: str,
    work_item_id: str,
    artifact_type: str,
    payload: dict[str, object],
) -> None:
    """写入测试用 Work Item 和 Artifact。"""
    timestamp = now_iso()
    await session.execute(
        text(
            """
            INSERT INTO threads (id, user_id, title, summary, status, created_at, updated_at)
            VALUES (:id, :user_id, :title, :summary, 'active', :created_at, :updated_at)
            """
        ),
        {
            "id": f"thread_{work_item_id}",
            "user_id": "google:test@example.com",
            "title": "测试 Thread",
            "summary": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO work_items (
                id, thread_id, user_id, work_item_type, title, summary,
                maturity, status, created_at, updated_at
            )
            VALUES (
                :id, :thread_id, :user_id, :work_item_type, :title, :summary,
                'reviewable', 'open', :created_at, :updated_at
            )
            """
        ),
        {
            "id": work_item_id,
            "thread_id": f"thread_{work_item_id}",
            "user_id": "google:test@example.com",
            "work_item_type": artifact_type,
            "title": "测试事项",
            "summary": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO artifacts (
                id, work_item_id, artifact_type, version, content_json, created_at, updated_at
            )
            VALUES (:id, :work_item_id, :artifact_type, 1, :content_json, :created_at, :updated_at)
            """
        ),
        {
            "id": artifact_id,
            "work_item_id": work_item_id,
            "artifact_type": artifact_type,
            "content_json": json.dumps(payload, ensure_ascii=False),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()


def test_stable_json_and_fingerprint_ignore_key_order() -> None:
    first = {"subject": "项目", "to": [{"email": "li@example.com"}]}
    second = {"to": [{"email": "li@example.com"}], "subject": "项目"}

    assert stable_json_dumps(first) == stable_json_dumps(second)
    assert compute_payload_fingerprint(first) == compute_payload_fingerprint(second)


@pytest.mark.asyncio
async def test_create_proposal_supersedes_old_proposal(workflow_session: AsyncSession) -> None:
    user = ConnectedUser("google:test@example.com", "test@example.com", None)
    await seed_artifact(
        workflow_session,
        artifact_id="art_email",
        work_item_id="wi_email",
        artifact_type="email_draft",
        payload={"subject": "项目", "body": "正文"},
    )

    first = await create_proposal_from_artifact(
        workflow_session,
        user,
        CreateProposalRequest(artifact_id="art_email", action_type="send_email"),
    )
    second = await create_proposal_from_artifact(
        workflow_session,
        user,
        CreateProposalRequest(artifact_id="art_email", action_type="send_email"),
    )

    result = await workflow_session.execute(
        text("SELECT status FROM proposal_items WHERE id = :id"),
        {"id": first.id},
    )
    assert result.scalar_one() == "superseded"
    assert second.status == "awaiting_confirmation"
    assert second.fingerprint == compute_payload_fingerprint({"subject": "项目", "body": "正文"})


@pytest.mark.asyncio
async def test_resolve_confirmation_filters_send_email_only(
    workflow_session: AsyncSession,
) -> None:
    user = ConnectedUser("google:test@example.com", "test@example.com", None)
    await seed_artifact(
        workflow_session,
        artifact_id="art_email",
        work_item_id="wi_email",
        artifact_type="email_draft",
        payload={"subject": "项目", "body": "正文"},
    )
    await seed_artifact(
        workflow_session,
        artifact_id="art_calendar",
        work_item_id="wi_calendar",
        artifact_type="calendar_event_draft",
        payload={"title": "会议"},
    )
    email_proposal = await create_proposal_from_artifact(
        workflow_session,
        user,
        CreateProposalRequest(artifact_id="art_email", action_type="send_email"),
    )
    await create_proposal_from_artifact(
        workflow_session,
        user,
        CreateProposalRequest(artifact_id="art_calendar", action_type="create_calendar_event"),
    )

    result = await resolve_confirmation_candidates(workflow_session, user, "send_email")

    assert result.status == "unique"
    assert result.candidates[0].id == email_proposal.id


@pytest.mark.asyncio
async def test_authorize_rejects_stale_fingerprint(workflow_session: AsyncSession) -> None:
    user = ConnectedUser("google:test@example.com", "test@example.com", None)
    await seed_artifact(
        workflow_session,
        artifact_id="art_email",
        work_item_id="wi_email",
        artifact_type="email_draft",
        payload={"subject": "项目", "body": "正文"},
    )
    proposal = await create_proposal_from_artifact(
        workflow_session,
        user,
        CreateProposalRequest(artifact_id="art_email", action_type="send_email"),
    )

    with pytest.raises(WorkflowSafetyError):
        await authorize_proposal(
            workflow_session,
            user,
            proposal.id,
            AuthorizeProposalRequest(version=proposal.version, fingerprint="stale"),
        )

    authorized = await authorize_proposal(
        workflow_session,
        user,
        proposal.id,
        AuthorizeProposalRequest(version=proposal.version, fingerprint=proposal.fingerprint),
    )
    assert authorized.status == "approved"


@pytest.mark.asyncio
async def test_authorize_rejects_expired_proposal(workflow_session: AsyncSession) -> None:
    user = ConnectedUser("google:test@example.com", "test@example.com", None)
    await seed_artifact(
        workflow_session,
        artifact_id="art_email_expired",
        work_item_id="wi_email_expired",
        artifact_type="email_draft",
        payload={"subject": "项目", "body": "正文"},
    )
    proposal = await create_proposal_from_artifact(
        workflow_session,
        user,
        CreateProposalRequest(artifact_id="art_email_expired", action_type="send_email"),
    )
    await workflow_session.execute(
        text("UPDATE proposal_items SET expires_at = :expires_at WHERE id = :id"),
        {"expires_at": "2000-01-01T00:00:00+00:00", "id": proposal.id},
    )
    await workflow_session.commit()

    with pytest.raises(WorkflowSafetyError):
        await authorize_proposal(
            workflow_session,
            user,
            proposal.id,
            AuthorizeProposalRequest(version=proposal.version, fingerprint=proposal.fingerprint),
        )


@pytest.mark.asyncio
async def test_repeated_authorization_does_not_write_duplicate_rows(
    workflow_session: AsyncSession,
) -> None:
    user = ConnectedUser("google:test@example.com", "test@example.com", None)
    await seed_artifact(
        workflow_session,
        artifact_id="art_email_once",
        work_item_id="wi_email_once",
        artifact_type="email_draft",
        payload={"subject": "项目", "body": "正文"},
    )
    proposal = await create_proposal_from_artifact(
        workflow_session,
        user,
        CreateProposalRequest(artifact_id="art_email_once", action_type="send_email"),
    )

    authorized = await authorize_proposal(
        workflow_session,
        user,
        proposal.id,
        AuthorizeProposalRequest(version=proposal.version, fingerprint=proposal.fingerprint),
    )
    with pytest.raises(WorkflowSafetyError):
        await authorize_proposal(
            workflow_session,
            user,
            proposal.id,
            AuthorizeProposalRequest(version=proposal.version, fingerprint=proposal.fingerprint),
        )
    count_result = await workflow_session.execute(
        text("SELECT COUNT(*) FROM action_authorizations WHERE proposal_item_id = :id"),
        {"id": proposal.id},
    )

    assert authorized.status == "approved"
    assert count_result.scalar_one() == 1
