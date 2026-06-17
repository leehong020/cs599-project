from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.graph.state import AssistantState


def timed_node(
    node_name: str,
    node: Callable[[AssistantState], dict[str, Any]],
) -> Callable[[AssistantState], dict[str, Any]]:
    """给 LangGraph 节点增加耗时记录。

    包装后的节点仍然只返回普通 dict，因此不会改变 LangGraph 的运行模型。
    每次节点执行后会把 `{node, duration_ms}` 追加到 `node_timings`，前端和测试
    可以据此判断一次对话卡在哪个节点。
    """

    def wrapped(state: AssistantState) -> dict[str, Any]:
        started_at = time.perf_counter()
        result = node(state)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        # `state_loader` 是多 Agent 主图的第一个节点。这里重置上一轮 checkpoint
        # 中的耗时，确保 API 返回的是本轮观测数据，而不是历史累计值。
        existing_timings = [] if node_name in {"load_context", "state_loader"} else state.get("node_timings", [])
        return {
            **result,
            "node_timings": [
                *existing_timings,
                *result.get("node_timings", []),
                {"node": node_name, "duration_ms": duration_ms},
            ],
        }

    wrapped.__name__ = getattr(node, "__name__", node_name)
    wrapped.__doc__ = getattr(node, "__doc__", None)
    return wrapped
