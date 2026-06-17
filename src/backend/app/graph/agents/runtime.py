"""LLM Agent 通用运行时。

这里集中处理 LangChain tool_calls、DeepSeek DSML 文本工具调用、工具结果
观察和最终回复收敛。各专业 Agent 只需要提供 prompt 和工具集。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.graph.state import AssistantState
from app.services import llm_client

logger = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    """单个 LLM Agent 的运行结果。"""

    agent_name: str
    content: str
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0

    def as_dict(self) -> dict[str, Any]:
        """转成可写入 LangGraph checkpoint 的普通字典。"""
        return {
            "agent_name": self.agent_name,
            "content": self.content,
            "tool_results": self.tool_results,
            "iterations": self.iterations,
        }


def _normalize_tool_call(tc: Any) -> dict[str, Any]:
    """把 LangChain tool_call 统一成 dict。"""
    if isinstance(tc, dict):
        return {
            "name": str(tc.get("name", "")),
            "args": tc.get("args", {}) or {},
            "id": str(tc.get("id", "")),
        }
    return {
        "name": str(getattr(tc, "name", "") or ""),
        "args": dict(getattr(tc, "args", {}) or {}),
        "id": str(getattr(tc, "id", "") or ""),
    }


def _message_content_to_text(content: Any) -> str:
    """把模型 content 规整为字符串。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(item) for item in content)
    if content is None:
        return ""
    return str(content)


def _parse_dsml_tool_calls(content: str) -> list[dict[str, Any]]:
    """解析 DeepSeek DSML 文本工具调用。"""
    if "DSML" not in content or "tool_calls" not in content:
        return []
    calls: list[dict[str, Any]] = []
    invoke_pattern = re.compile(
        r"<\s*｜｜DSML｜｜invoke\s+name=\"([^\"]+)\"\s*>([\s\S]*?)</\s*｜｜DSML｜｜invoke\s*>"
    )
    parameter_pattern = re.compile(
        r"<\s*｜｜DSML｜｜parameter\s+name=\"([^\"]+)\"[^>]*>([\s\S]*?)</\s*｜｜DSML｜｜parameter\s*>"
    )
    for index, match in enumerate(invoke_pattern.finditer(content)):
        args: dict[str, Any] = {}
        for param in parameter_pattern.finditer(match.group(2)):
            args[param.group(1).strip()] = param.group(2).strip()
        calls.append({"name": match.group(1).strip(), "args": args, "id": f"dsml_call_{index}"})
    return calls


def _contains_tool_protocol(content: str) -> bool:
    """判断最终文本是否还泄漏工具协议。"""
    return any(marker in content for marker in ("<｜｜DSML｜｜tool_calls>", "<｜｜DSML｜｜invoke", "tool_calls"))


def _load_tool_json(result_text: str) -> dict[str, Any] | None:
    """解析工具统一 JSON 返回。"""
    try:
        parsed = json.loads(result_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _tool_result_message(result_text: str) -> str:
    """把工具结果压缩成适合继续喂给模型的观察文本。"""
    parsed = _load_tool_json(result_text)
    if not parsed:
        return result_text
    return json.dumps(
        {
            "ok": parsed.get("ok"),
            "code": parsed.get("code"),
            "message": parsed.get("message"),
            "data": parsed.get("data", {}),
        },
        ensure_ascii=False,
    )


def _fallback_tool_summary(tool_results: list[dict[str, Any]]) -> str:
    """模型没有自然语言输出时，用工具 message 生成保底文本。"""
    messages: list[str] = []
    for item in tool_results:
        parsed = _load_tool_json(str(item.get("result", "")))
        if parsed and parsed.get("message"):
            messages.append(str(parsed["message"]))
    return "\n".join(messages) if messages else "我已经处理了这个 Agent 的任务。"


def _build_agent_messages(
    *,
    system_prompt: str,
    state: AssistantState,
    agent_input: str,
) -> list[Any]:
    """构建单个 Agent 的对话消息。"""
    messages: list[Any] = [SystemMessage(content=system_prompt)]
    for item in state.get("messages", [])[-10:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = str(item.get("content", ""))
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=agent_input))
    return messages


def run_llm_agent(
    *,
    agent_name: str,
    state: AssistantState,
    system_prompt: str,
    agent_input: str,
    tools: list[Any],
    max_iterations: int = 3,
) -> AgentRunResult:
    """运行一个可调用工具的 LLM Agent。"""
    model = llm_client.get_chat_model()
    model_with_tools = model.bind_tools(tools) if tools else model
    tool_map = {item.name: item for item in tools}
    chat_messages = _build_agent_messages(
        system_prompt=system_prompt,
        state=state,
        agent_input=agent_input,
    )
    tool_results: list[dict[str, Any]] = []
    final_text = ""
    iterations = 0

    for iteration in range(max_iterations):
        iterations = iteration + 1
        try:
            response = model_with_tools.invoke(chat_messages)
        except Exception as exc:
            logger.exception("%s 调用模型失败", agent_name)
            final_text = f"{agent_name} 处理失败：{exc}"
            break

        content_text = _message_content_to_text(getattr(response, "content", ""))
        raw_tool_calls = getattr(response, "tool_calls", None) or []
        tool_calls = [_normalize_tool_call(item) for item in raw_tool_calls]
        dsml_calls: list[dict[str, Any]] = []
        if not tool_calls:
            dsml_calls = _parse_dsml_tool_calls(content_text)
            tool_calls = dsml_calls

        logger.info("%s iteration %s: %s tool call(s)", agent_name, iterations, len(tool_calls))
        if not tool_calls:
            final_text = content_text
            break

        chat_messages.append(AIMessage(content="我需要调用工具获取结果。") if dsml_calls else response)

        for call in tool_calls:
            tool_name = call["name"]
            tool_args = call["args"]
            tool_id = call["id"] or f"{agent_name}_{iteration}_{len(tool_results)}"
            tool_func = tool_map.get(tool_name)
            if not tool_func:
                result_text = json.dumps(
                    {
                        "ok": False,
                        "code": "unknown_tool",
                        "message": f"{agent_name} 无权调用工具：{tool_name}",
                        "data": {"tool": tool_name},
                    },
                    ensure_ascii=False,
                )
            else:
                try:
                    logger.info("%s 调用工具 %s(%s)", agent_name, tool_name, json.dumps(tool_args, ensure_ascii=False)[:500])
                    result_text = str(tool_func.invoke(tool_args))
                except Exception as exc:
                    result_text = json.dumps(
                        {
                            "ok": False,
                            "code": "tool_execution_failed",
                            "message": f"工具执行失败：{exc}",
                            "data": {"tool": tool_name},
                        },
                        ensure_ascii=False,
                    )
            tool_results.append({"name": tool_name, "result": result_text})
            if dsml_calls:
                chat_messages.append(HumanMessage(content=f"工具 {tool_name} 执行结果：{_tool_result_message(result_text)}"))
            else:
                chat_messages.append(ToolMessage(content=_tool_result_message(result_text), tool_call_id=tool_id))

    if not final_text and tool_results:
        final_text = _fallback_tool_summary(tool_results)
    if _contains_tool_protocol(final_text):
        final_text = _fallback_tool_summary(tool_results)
    if not final_text:
        final_text = f"{agent_name} 已完成。"
    return AgentRunResult(
        agent_name=agent_name,
        content=final_text,
        tool_results=tool_results,
        iterations=iterations,
    )
