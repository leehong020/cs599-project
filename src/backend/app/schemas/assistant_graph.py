from typing import Any, Literal

from pydantic import BaseModel, Field


class AssistantTurnRequest(BaseModel):
    """阶段 7 主图单轮运行请求。"""

    thread_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    user_id: str = "local-dev-user"
    selected_context_refs: list[dict[str, Any]] = Field(default_factory=list)
    available_contacts: list[dict[str, Any]] = Field(default_factory=list)


class AssistantTurnResponse(BaseModel):
    """阶段 7 主图单轮运行响应。"""

    thread_id: str
    response: str
    turn_count: int
    tasks: list[dict[str, Any]]
    task_batches: list[list[str]]
    route_trace: list[str]
    node_timings: list[dict[str, Any]]
    clarification_needed: bool = False
    clarification_question: str | None = None
    proposal_group: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class AssistantStreamEvent(BaseModel):
    """阶段 8 SSE 事件结构。"""

    event: Literal["progress", "final", "error"]
    message: str
    step: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class AssistantStateResponse(BaseModel):
    """checkpoint 状态读取响应。"""

    thread_id: str
    state: dict[str, Any]


class MermaidResponse(BaseModel):
    """Mermaid 图响应。"""

    graph_name: str
    mermaid: str


class SubgraphRunRequest(BaseModel):
    """单独运行子图的请求。"""

    subgraph: Literal["mail", "calendar"]
    message: str = Field(min_length=1)


class SubgraphRunResponse(BaseModel):
    """单独运行子图的响应。"""

    subgraph: str
    task_results: list[dict[str, Any]]
    route_trace: list[str]
