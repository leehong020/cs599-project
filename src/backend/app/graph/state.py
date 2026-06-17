from typing import Any, Literal

from typing_extensions import TypedDict


TaskDomain = Literal["mail", "calendar", "general"]
TaskStatus = Literal["planned", "blocked", "completed"]


class AssistantTask(TypedDict, total=False):
    """主图内部使用的任务结构。

    这里使用 `TypedDict` 而不是 ORM model，是因为 LangGraph checkpoint
    需要保存可序列化状态。后续真正持久化仍然写入 SQLite 业务表。
    """

    id: str
    domain: TaskDomain
    title: str
    depends_on: list[str]
    status: TaskStatus
    reason: str | None


class AssistantState(TypedDict, total=False):
    """阶段 7 主图状态。

    状态只保存编排必需的信息：用户输入、解析结果、任务 DAG、子图结果、
    回复文本和恢复计数。敏感 token、Google 客户端对象、数据库 session
    绝不能放进这里，否则 checkpoint 会把它们持久化。
    """

    thread_id: str
    user_id: str
    user_message: str
    messages: list[dict[str, Any]]
    selected_context_refs: list[dict[str, Any]]
    available_contacts: list[dict[str, Any]]
    user_profile: dict[str, Any]
    default_signature: dict[str, Any] | None
    active_email_draft: dict[str, Any] | None
    active_calendar_draft: dict[str, Any] | None
    supervisor_plan: dict[str, Any]
    context_result: dict[str, Any] | None
    mail_result: dict[str, Any] | None
    calendar_result: dict[str, Any] | None
    review_result: dict[str, Any] | None
    confirmation_result: dict[str, Any] | None
    execution_result: dict[str, Any] | None
    agent_runs: list[dict[str, Any]]
    turn_intent: dict[str, Any]
    resolved_references: list[dict[str, Any]]
    resolved_entities: dict[str, Any]
    clarification_needed: bool
    clarification_question: str | None
    tasks: list[AssistantTask]
    task_batches: list[list[str]]
    read_tasks: list[AssistantTask]
    task_results: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    artifact_reviews: list[dict[str, Any]]
    proposal_group: dict[str, Any] | None
    confirmation_prompt: str | None
    authorization_decisions: list[dict[str, Any]]
    action_results: list[dict[str, Any]]
    response: str
    memory_candidates: list[dict[str, Any]]
    short_term_memory: dict[str, Any]
    recalled_memories: list[dict[str, Any]]
    conversation_summary: str | None
    node_timings: list[dict[str, Any]]
    route_trace: list[str]
    turn_count: int
