from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.workflow import (
    AuthorizeProposalRequest,
    CreateProposalRequest,
    ExecuteProposalRequest,
    ExecutionResultResponse,
    ProposalItemResponse,
    ResolveConfirmationRequest,
    ResolveConfirmationResponse,
    WorkItemDetail,
    WorkItemSummary,
    WorkItemUpdateRequest,
)
from app.services.oauth import now_iso
from app.services.settings import require_connected_user
from app.services.workflow import (
    WorkflowSafetyError,
    authorize_proposal,
    create_proposal_from_artifact,
    execute_authorized_proposal,
    list_open_work_items,
    list_pending_proposals,
    resolve_confirmation_candidates,
)

router = APIRouter(tags=["workflow"])


def _workflow_error(exc: WorkflowSafetyError) -> HTTPException:
    """把工作流安全错误转换成用户可见 HTTP 错误。"""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/work-items/open", response_model=list[WorkItemSummary])
async def read_open_work_items(
    thread_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[WorkItemSummary]:
    """列出当前用户打开中的 Work Item。"""
    user = await require_connected_user(session)
    return await list_open_work_items(session, user, thread_id)


@router.get("/proposals/pending", response_model=list[ProposalItemResponse])
async def read_pending_proposals(
    action_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProposalItemResponse]:
    """列出当前用户待确认或已授权未执行的 Proposal。"""
    user = await require_connected_user(session)
    return await list_pending_proposals(session, user, action_type)


@router.post("/proposals", response_model=ProposalItemResponse)
async def create_proposal(
    payload: CreateProposalRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ProposalItemResponse:
    """从本地 Artifact 创建 Proposal。"""
    user = await require_connected_user(session)
    try:
        return await create_proposal_from_artifact(session, user, payload)
    except WorkflowSafetyError as exc:
        raise _workflow_error(exc) from exc


@router.post("/proposals/resolve-confirmation", response_model=ResolveConfirmationResponse)
async def resolve_confirmation(
    payload: ResolveConfirmationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ResolveConfirmationResponse:
    """根据用户确认意图筛选 Proposal 候选。"""
    user = await require_connected_user(session)
    return await resolve_confirmation_candidates(session, user, payload.action_type)


@router.post("/proposals/{proposal_item_id}/authorize", response_model=ProposalItemResponse)
async def authorize(
    proposal_item_id: str,
    payload: AuthorizeProposalRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ProposalItemResponse:
    """记录用户对 Proposal 的确认或拒绝。"""
    user = await require_connected_user(session)
    try:
        return await authorize_proposal(session, user, proposal_item_id, payload)
    except WorkflowSafetyError as exc:
        raise _workflow_error(exc) from exc


@router.post("/proposals/{proposal_item_id}/execute", response_model=ExecutionResultResponse)
async def execute(
    proposal_item_id: str,
    payload: ExecuteProposalRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionResultResponse:
    """执行已授权 Proposal。"""
    user = await require_connected_user(session)
    try:
        return await execute_authorized_proposal(session, user, proposal_item_id, payload)
    except WorkflowSafetyError as exc:
        raise _workflow_error(exc) from exc


@router.get("/work-items/{work_item_id}", response_model=WorkItemDetail)
async def read_work_item(
    work_item_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> WorkItemDetail:
    """读取单个 Work Item 详情，包含 Artifact 完整内容。"""
    user = await require_connected_user(session)
    result = await session.execute(
        text(
            """
            SELECT wi.id, wi.thread_id, wi.work_item_type, wi.title, wi.summary,
                   wi.maturity, wi.status, wi.updated_at,
                   a.id AS artifact_id, a.artifact_type, a.version, a.content_json
            FROM work_items wi
            LEFT JOIN artifacts a ON a.work_item_id = wi.id
            WHERE wi.id = :id AND wi.user_id = :user_id
            ORDER BY a.updated_at DESC
            LIMIT 1
            """
        ),
        {"id": work_item_id, "user_id": user.user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work Item 不存在。")
    import json
    return WorkItemDetail(
        id=row["id"],
        thread_id=row["thread_id"],
        work_item_type=row["work_item_type"],
        title=row["title"],
        summary=row["summary"],
        maturity=row["maturity"],
        status=row["status"],
        updated_at=row["updated_at"],
        artifact_id=row["artifact_id"],
        artifact_type=row["artifact_type"],
        artifact_version=row["version"],
        artifact_content=json.loads(row["content_json"] or "{}"),
    )


@router.put("/work-items/{work_item_id}", response_model=WorkItemDetail)
async def update_work_item(
    work_item_id: str,
    payload: WorkItemUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> WorkItemDetail:
    """更新 Work Item 及其关联 Artifact 的内容。"""
    user = await require_connected_user(session)
    import json

    # 验证所有权
    check = await session.execute(
        text("SELECT id FROM work_items WHERE id = :id AND user_id = :user_id"),
        {"id": work_item_id, "user_id": user.user_id},
    )
    if check.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work Item 不存在。")

    timestamp = now_iso()

    # 更新 work_item
    if payload.title is not None or payload.summary is not None:
        updates = []
        params: dict[str, Any] = {"id": work_item_id, "updated_at": timestamp}
        if payload.title is not None:
            updates.append("title = :title")
            params["title"] = payload.title
        if payload.summary is not None:
            updates.append("summary = :summary")
            params["summary"] = payload.summary
        if updates:
            updates.append("updated_at = :updated_at")
            await session.execute(
                text(f"UPDATE work_items SET {', '.join(updates)} WHERE id = :id"),
                params,
            )

    # 更新 artifact
    if payload.artifact_content is not None:
        await session.execute(
            text(
                """
                UPDATE artifacts
                SET content_json = :content_json, version = version + 1, updated_at = :updated_at
                WHERE work_item_id = :work_item_id
                """
            ),
            {
                "work_item_id": work_item_id,
                "content_json": json.dumps(payload.artifact_content, ensure_ascii=False),
                "updated_at": timestamp,
            },
        )

    await session.commit()

    # 重新查询返回
    result = await session.execute(
        text(
            """
            SELECT wi.id, wi.thread_id, wi.work_item_type, wi.title, wi.summary,
                   wi.maturity, wi.status, wi.updated_at,
                   a.id AS artifact_id, a.artifact_type, a.version, a.content_json
            FROM work_items wi
            LEFT JOIN artifacts a ON a.work_item_id = wi.id
            WHERE wi.id = :id
            ORDER BY a.updated_at DESC
            LIMIT 1
            """
        ),
        {"id": work_item_id},
    )
    row = result.mappings().one()
    return WorkItemDetail(
        id=row["id"],
        thread_id=row["thread_id"],
        work_item_type=row["work_item_type"],
        title=row["title"],
        summary=row["summary"],
        maturity=row["maturity"],
        status=row["status"],
        updated_at=row["updated_at"],
        artifact_id=row["artifact_id"],
        artifact_type=row["artifact_type"],
        artifact_version=row["version"],
        artifact_content=json.loads(row["content_json"] or "{}"),
    )


@router.delete("/work-items/{work_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_item(
    work_item_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """删除 Work Item 及其关联的 Artifacts、Proposals。"""
    user = await require_connected_user(session)

    check = await session.execute(
        text("SELECT id FROM work_items WHERE id = :id AND user_id = :user_id"),
        {"id": work_item_id, "user_id": user.user_id},
    )
    if check.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work Item 不存在。")

    # 级联删除关联数据
    await session.execute(text("DELETE FROM artifacts WHERE work_item_id = :id"), {"id": work_item_id})
    await session.execute(
        text(
            """
            DELETE FROM proposal_items
            WHERE work_item_id = :id
            """
        ),
        {"id": work_item_id},
    )
    await session.execute(text("DELETE FROM work_items WHERE id = :id"), {"id": work_item_id})
    await session.commit()
