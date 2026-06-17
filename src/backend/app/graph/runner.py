"""Graph Runner — 注入工具上下文并执行 agent 图。"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from app.core.config import get_settings
from app.graph.builder import build_assistant_graph
from app.graph.state import AssistantState
from app.graph.tools import set_tool_context

DEFAULT_RECURSION_LIMIT = 80


def build_thread_config(
    thread_id: str,
    *,
    recursion_limit: int = DEFAULT_RECURSION_LIMIT,
) -> dict[str, Any]:
    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": recursion_limit,
    }


def run_assistant_turn(
    *,
    thread_id: str,
    user_message: str,
    user_id: str = "local-dev-user",
    selected_context_refs: list[dict[str, Any]] | None = None,
    available_contacts: list[dict[str, Any]] | None = None,
    recalled_memories: list[dict[str, Any]] | None = None,
    available_signatures: list[dict[str, Any]] | None = None,
    default_signature: dict[str, Any] | None = None,
    user_profile: dict[str, Any] | None = None,
    active_email_draft: dict[str, Any] | None = None,
    active_calendar_draft: dict[str, Any] | None = None,
    conversation_summary: str | None = None,
    gmail_client: Any = None,
    calendar_client: Any = None,
    db_session: Any = None,
    user: Any = None,
) -> AssistantState:
    """运行一轮 agent 图。

    通过 set_tool_context 注入外部依赖（已创建的 Gmail/Calendar 客户端、
    数据库 session 等），工具函数内部通过全局上下文获取这些依赖。
    """
    set_tool_context(
        thread_id=thread_id,
        gmail_client=gmail_client,
        calendar_client=calendar_client,
        db_session=db_session,
        user=user,
    )

    graph = get_persistent_assistant_graph()
    initial_state: AssistantState = {
        "thread_id": thread_id,
        "user_id": user_id,
        "user_message": user_message,
    }
    if selected_context_refs is not None:
        initial_state["selected_context_refs"] = selected_context_refs
    if available_contacts is not None:
        initial_state["available_contacts"] = available_contacts
    if recalled_memories is not None:
        initial_state["recalled_memories"] = recalled_memories
    if available_signatures is not None:
        initial_state["available_signatures"] = available_signatures
    if default_signature is not None:
        initial_state["default_signature"] = default_signature
    if user_profile is not None:
        initial_state["user_profile"] = user_profile
    if active_email_draft is not None:
        initial_state["active_email_draft"] = active_email_draft
    if active_calendar_draft is not None:
        initial_state["active_calendar_draft"] = active_calendar_draft
    if conversation_summary is not None:
        initial_state["conversation_summary"] = conversation_summary

    return graph.invoke(initial_state, config=build_thread_config(thread_id))


def get_assistant_thread_state(thread_id: str) -> AssistantState:
    graph = get_persistent_assistant_graph()
    snapshot = graph.get_state(config=build_thread_config(thread_id))
    return snapshot.values


@lru_cache
def get_persistent_assistant_graph():
    settings = get_settings()
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.langgraph_db_path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    return build_assistant_graph(checkpointer=checkpointer)


def clear_graph_cache_for_tests() -> None:
    get_persistent_assistant_graph.cache_clear()
