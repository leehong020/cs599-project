"""Assistant Graph API — agent + tools 架构的 REST 端点。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.graph.builder import (
    export_assistant_mermaid,
    export_calendar_subgraph_mermaid,
    export_mail_subgraph_mermaid,
)
from app.graph.runner import get_assistant_thread_state, run_assistant_turn
from app.schemas.assistant_graph import (
    AssistantStateResponse,
    AssistantTurnRequest,
    AssistantTurnResponse,
    MermaidResponse,
)
router = APIRouter(prefix="/assistant", tags=["assistant-graph"])


# ── 上下文准备 ─────────────────────────────────────────────────────────

async def _prepare_turn_context(
    session: AsyncSession,
    thread_id: str,
) -> dict[str, Any]:
    """每轮对话前准备上下文：长期记忆 + 签名 + Google 客户端。

    所有数据在 API 层查询好，通过 runner 注入到图中。
    """
    ctx: dict[str, Any] = {}

    try:
        from app.services.oauth import get_connected_google_user
        user = await get_connected_google_user(session)
    except Exception:
        return ctx

    if user is None:
        return ctx

    # 长期记忆召回
    try:
        memory_rows = await session.execute(
            text(
                """
                SELECT id, namespace, memory_key, memory_type, content_json,
                       confidence, status
                FROM memories
                WHERE user_id = :user_id AND status = 'active'
                ORDER BY updated_at DESC LIMIT 10
                """
            ),
            {"user_id": user.user_id},
        )
        ctx["recalled_memories"] = [
            {
                "id": r["id"], "namespace": r["namespace"],
                "memory_key": r["memory_key"], "memory_type": r["memory_type"],
                "content": json.loads(r["content_json"] or "{}"),
                "confidence": r["confidence"], "status": r["status"],
            }
            for r in memory_rows.mappings()
        ]
    except Exception:
        ctx["recalled_memories"] = []

    # 签名
    try:
        from app.services.settings import get_user_profile, list_contacts, list_signatures
        sigs = await list_signatures(session, user)
        ctx["available_signatures"] = [
            {"id": s.id, "label": s.label, "content": s.content, "is_default": s.is_default}
            for s in sigs
        ]
        defaults = [s for s in sigs if s.is_default]
        if defaults:
            s = defaults[0]
            ctx["default_signature"] = {"id": s.id, "label": s.label, "content": s.content}
        profile = await get_user_profile(session, user)
        ctx["user_profile"] = profile.model_dump(mode="json")
        contacts = await list_contacts(session, user)
        ctx["available_contacts"] = [c.model_dump(mode="json") for c in contacts]
    except Exception:
        ctx["available_signatures"] = []
        ctx["default_signature"] = None
        ctx["user_profile"] = None
        ctx["available_contacts"] = []

    # 当前会话打开中的草稿。它是“继续修改原草稿”的确定性来源。
    try:
        from app.services.draft_context import load_active_artifact
        ctx["active_email_draft"] = await load_active_artifact(
            session, user, thread_id, "email_draft"
        )
        ctx["active_calendar_draft"] = await load_active_artifact(
            session, user, thread_id, "calendar_event_draft"
        )
    except Exception:
        ctx["active_email_draft"] = None
        ctx["active_calendar_draft"] = None

    # 会话摘要
    try:
        existing = get_assistant_thread_state(thread_id)
        if existing and existing.get("conversation_summary"):
            ctx["conversation_summary"] = existing["conversation_summary"]
    except Exception:
        pass

    # 在 async 上下文中直接创建 Google 客户端，避免同步/异步跨线问题
    try:
        from app.services.gmail import build_gmail_client_for_user
        ctx["gmail_client"] = await build_gmail_client_for_user(session, user)
    except Exception:
        ctx["gmail_client"] = None

    try:
        from app.services.calendar import build_calendar_client_for_user
        ctx["calendar_client"] = await build_calendar_client_for_user(session, user)
    except Exception:
        ctx["calendar_client"] = None

    ctx["db_session"] = session
    ctx["user"] = user

    return ctx


# ── 记忆持久化 ─────────────────────────────────────────────────────────

async def _persist_memory_candidates(
    session: AsyncSession,
    user: Any,
    thread_id: str,
    candidates: list[dict[str, Any]],
) -> None:
    import uuid
    from datetime import datetime as _dt
    timestamp = _dt.now().isoformat()

    for c in candidates:
        memory_id = f"mem_{uuid.uuid4().hex}"
        content_json = json.dumps(c.get("content", {}), ensure_ascii=False)
        try:
            await session.execute(
                text(
                    """
                    INSERT INTO memories (
                        id, user_id, namespace, memory_key, memory_type,
                        content_json, confidence, status, source_thread_id,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :user_id, :namespace, :memory_key, 'preference_candidate',
                        :content_json, 0.85, :status, :source_thread_id,
                        :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": memory_id,
                    "user_id": user.user_id,
                    "namespace": c.get("namespace", "preferences"),
                    "memory_key": c.get("memory_key", "auto")[:80],
                    "content_json": content_json,
                    "status": c.get("status", "active"),
                    "source_thread_id": thread_id,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
        except Exception:
            continue
    try:
        await session.commit()
    except Exception:
        pass


# ── API 端点 ───────────────────────────────────────────────────────────

@router.post("/turn", response_model=AssistantTurnResponse)
async def run_turn(
    payload: AssistantTurnRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AssistantTurnResponse:
    """运行一轮 agent 图（非流式）。"""
    ctx = await _prepare_turn_context(session, payload.thread_id)

    state = run_assistant_turn(
        thread_id=payload.thread_id,
        user_message=payload.message,
        user_id=payload.user_id,
        selected_context_refs=payload.selected_context_refs,
        available_contacts=ctx.get("available_contacts") or payload.available_contacts,
        recalled_memories=ctx.get("recalled_memories"),
        available_signatures=ctx.get("available_signatures"),
        default_signature=ctx.get("default_signature"),
        user_profile=ctx.get("user_profile"),
        active_email_draft=ctx.get("active_email_draft"),
        active_calendar_draft=ctx.get("active_calendar_draft"),
        conversation_summary=ctx.get("conversation_summary"),
        gmail_client=ctx.get("gmail_client"),
        calendar_client=ctx.get("calendar_client"),
        db_session=ctx.get("db_session"),
        user=ctx.get("user"),
    )

    # 持久化长期记忆
    memory_candidates = state.get("memory_candidates", [])
    if memory_candidates and ctx.get("user"):
        try:
            await _persist_memory_candidates(
                session, ctx["user"], payload.thread_id, memory_candidates
            )
        except Exception:
            pass

    return _turn_response(payload.thread_id, state)


@router.post("/turn/stream")
async def stream_turn(
    payload: AssistantTurnRequest,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """SSE 流式聊天。"""
    ctx = await _prepare_turn_context(session, payload.thread_id)

    async def event_iterator():
        # 先把进度事件交给前端，再运行同步 LangGraph，避免模型慢时页面完全静默。
        yield _sse("progress", step="state_loader", message="正在准备对话…")
        try:
            yield _sse("progress", step="supervisor_agent", message="正在理解你的意思…")
            state = run_assistant_turn(
                thread_id=payload.thread_id,
                user_message=payload.message,
                user_id=payload.user_id,
                selected_context_refs=payload.selected_context_refs,
                available_contacts=ctx.get("available_contacts") or payload.available_contacts,
                recalled_memories=ctx.get("recalled_memories"),
                available_signatures=ctx.get("available_signatures"),
                default_signature=ctx.get("default_signature"),
                user_profile=ctx.get("user_profile"),
                active_email_draft=ctx.get("active_email_draft"),
                active_calendar_draft=ctx.get("active_calendar_draft"),
                conversation_summary=ctx.get("conversation_summary"),
                gmail_client=ctx.get("gmail_client"),
                calendar_client=ctx.get("calendar_client"),
                db_session=ctx.get("db_session"),
                user=ctx.get("user"),
            )
            memory_candidates = state.get("memory_candidates", [])
            if memory_candidates and ctx.get("user"):
                try:
                    await _persist_memory_candidates(
                        session, ctx["user"], payload.thread_id, memory_candidates
                    )
                except Exception:
                    pass

            final_text = state.get("response", "")
            response_data = _turn_response(payload.thread_id, state)
            response_data.response = final_text
            yield _sse("final", step="done", message=final_text, data=response_data.model_dump())
        except Exception as exc:
            yield _sse("error", step="failed", message=str(exc))

    return StreamingResponse(
        event_iterator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── 线程管理 ───────────────────────────────────────────────────────────

class ThreadTitleUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=50)


@router.get("/threads")
async def list_threads(
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """列出当前用户的所有线程。"""
    try:
        from app.services.oauth import get_connected_google_user
        user = await get_connected_google_user(session)
        if not user:
            return []
        result = await session.execute(
            text(
                """
                SELECT id, title, summary, status, created_at, updated_at
                FROM threads WHERE user_id = :uid ORDER BY updated_at DESC LIMIT 50
                """
            ),
            {"uid": user.user_id},
        )
        return [
            {
                "id": r["id"], "title": r["title"] or "未命名",
                "summary": r["summary"], "status": r["status"],
                "created_at": r["created_at"], "updated_at": r["updated_at"],
            }
            for r in result.mappings()
        ]
    except Exception:
        return []


@router.put("/threads/{thread_id}/title")
async def update_thread_title(
    thread_id: str,
    payload: ThreadTitleUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """更新线程标题（由 LLM 生成会话名）。"""
    try:
        from app.services.oauth import get_connected_google_user
        from app.services.oauth import now_iso
        user = await get_connected_google_user(session)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        await session.execute(
            text(
                "UPDATE threads SET title = :title, updated_at = :ts "
                "WHERE id = :tid AND user_id = :uid"
            ),
            {"title": payload.title, "ts": now_iso(), "tid": thread_id, "uid": user.user_id},
        )
        await session.commit()
        return {"status": "ok", "title": payload.title}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """删除线程及其关联数据。"""
    try:
        from app.services.oauth import get_connected_google_user
        user = await get_connected_google_user(session)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        work_items = await session.execute(
            text("SELECT id FROM work_items WHERE thread_id = :tid AND user_id = :uid"),
            {"tid": thread_id, "uid": user.user_id},
        )
        for wi in work_items.mappings():
            await session.execute(text("DELETE FROM artifacts WHERE work_item_id = :id"), {"id": wi["id"]})
            await session.execute(text("DELETE FROM proposal_items WHERE work_item_id = :id"), {"id": wi["id"]})
        await session.execute(text("DELETE FROM work_items WHERE thread_id = :tid AND user_id = :uid"),
                              {"tid": thread_id, "uid": user.user_id})
        await session.execute(text("DELETE FROM threads WHERE id = :tid AND user_id = :uid"),
                              {"tid": thread_id, "uid": user.user_id})
        await session.commit()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── 图形诊断 ───────────────────────────────────────────────────────────

@router.get("/threads/{thread_id}/state", response_model=AssistantStateResponse)
async def read_thread_state(thread_id: str) -> AssistantStateResponse:
    state = get_assistant_thread_state(thread_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread state not found")
    return AssistantStateResponse(thread_id=thread_id, state=dict(state))


@router.get("/graph/mermaid", response_model=MermaidResponse)
async def read_assistant_mermaid() -> MermaidResponse:
    return MermaidResponse(graph_name="assistant", mermaid=export_assistant_mermaid())


@router.get("/subgraphs/{subgraph}/mermaid", response_model=MermaidResponse)
async def read_subgraph_mermaid(subgraph: str) -> MermaidResponse:
    if subgraph == "mail":
        return MermaidResponse(graph_name="mail", mermaid=export_mail_subgraph_mermaid())
    if subgraph == "calendar":
        return MermaidResponse(graph_name="calendar", mermaid=export_calendar_subgraph_mermaid())
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


# ── 辅助函数 ───────────────────────────────────────────────────────────

def _turn_response(thread_id: str, state: dict[str, Any]) -> AssistantTurnResponse:
    return AssistantTurnResponse(
        thread_id=thread_id,
        response=state.get("response", ""),
        turn_count=state.get("turn_count", 0),
        tasks=state.get("tasks", []),
        task_batches=state.get("task_batches", []),
        route_trace=state.get("route_trace", []),
        node_timings=state.get("node_timings", []),
        clarification_needed=state.get("clarification_needed", False),
        clarification_question=state.get("clarification_question"),
        proposal_group=state.get("proposal_group"),
        # 聊天页只展示 assistant 文本，不再展示邮件/日程卡片。
        # 后端仍会在工具层维护数据库 Artifact，用于确认发送和日程创建。
        artifacts=[],
    )


def _progress_steps() -> list[tuple[str, str]]:
    return [
        ("state_loader", "正在加载对话上下文…"),
        ("supervisor_agent", "正在理解任务…"),
        ("context_agent", "正在整理上下文…"),
        ("mail_agent", "正在处理邮件任务…"),
        ("calendar_agent", "正在处理日程任务…"),
        ("review_gate", "正在检查风险…"),
        ("confirmation_gate", "正在识别确认意图…"),
        ("executor", "正在执行已确认操作…"),
        ("response_agent", "正在生成回复…"),
        ("save_turn", "正在保存…"),
    ]


def _sse(event: str, *, step: str | None = None, message: str = "", data: dict[str, Any] | None = None) -> str:
    payload = json.dumps(
        {"event": event, "step": step, "message": message, "data": data or {}},
        ensure_ascii=False,
    )
    return f"event: {event}\ndata: {payload}\n\n"
