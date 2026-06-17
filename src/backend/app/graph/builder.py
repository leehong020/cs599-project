"""Agent Graph Builder —— 多 LLM Agent + 确定性工作流节点。

Graph 结构：
    START → state_loader → supervisor_agent → context_agent → mail_agent
    → calendar_agent → review_gate → confirmation_gate → executor
    → response_agent → save_turn → memory_extractor → END
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph.multi_nodes import (
    calendar_agent,
    confirmation_gate,
    context_agent,
    executor,
    mail_agent,
    memory_extractor,
    response_agent,
    review_gate,
    save_turn_state,
    state_loader,
    supervisor_agent,
)
from app.graph.observability import timed_node
from app.graph.state import AssistantState


def build_assistant_graph(*, checkpointer: Any = None):
    """编译 agent 图。"""
    builder = StateGraph(AssistantState)

    def add_timed_node(node_name: str, node):
        builder.add_node(node_name, timed_node(node_name, node))

    add_timed_node("state_loader", state_loader)
    add_timed_node("supervisor_agent", supervisor_agent)
    add_timed_node("context_agent", context_agent)
    add_timed_node("mail_agent", mail_agent)
    add_timed_node("calendar_agent", calendar_agent)
    add_timed_node("review_gate", review_gate)
    add_timed_node("confirmation_gate", confirmation_gate)
    add_timed_node("executor", executor)
    add_timed_node("response_agent", response_agent)
    add_timed_node("save_turn", save_turn_state)
    add_timed_node("memory_extractor", memory_extractor)

    builder.add_edge(START, "state_loader")
    builder.add_edge("state_loader", "supervisor_agent")
    builder.add_edge("supervisor_agent", "context_agent")
    builder.add_edge("context_agent", "mail_agent")
    builder.add_edge("mail_agent", "calendar_agent")
    builder.add_edge("calendar_agent", "review_gate")
    builder.add_edge("review_gate", "confirmation_gate")
    builder.add_edge("confirmation_gate", "executor")
    builder.add_edge("executor", "response_agent")
    builder.add_edge("response_agent", "save_turn")
    builder.add_edge("save_turn", "memory_extractor")
    builder.add_edge("memory_extractor", END)

    return builder.compile(checkpointer=checkpointer)


def export_assistant_mermaid() -> str:
    return build_assistant_graph().get_graph().draw_mermaid()


def export_mail_subgraph_mermaid() -> str:
    from app.graph.subgraphs import build_mail_subgraph

    return build_mail_subgraph().get_graph().draw_mermaid()


def export_calendar_subgraph_mermaid() -> str:
    from app.graph.subgraphs import build_calendar_subgraph

    return build_calendar_subgraph().get_graph().draw_mermaid()
