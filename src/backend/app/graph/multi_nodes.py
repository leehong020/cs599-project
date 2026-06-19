"""多 LLM Agent 主图节点。

LLM Agent 负责理解、生成和调用自己可见的工具；Gate/Executor 负责确定性
安全控制，避免模型绕过确认链路。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

from app.graph.agents.runtime import AgentRunResult, run_llm_agent
from app.graph.nodes import (
    _is_calendar_create_confirmation,
    _is_calendar_delete_confirmation,
    _is_email_send_confirmation,
    _should_batch_email_send,
    _trace,
    _try_deterministic_confirmation,
    extract_memory_candidates,
    load_context,
    save_turn_state,
)
from app.graph.state import AssistantState
from app.graph.tools import create_tools, create_tools_for_agent
from app.services.llm_client import load_prompt


BEIJING_TZ = dt_timezone(timedelta(hours=8))


def _append_agent_run(state: AssistantState, result: AgentRunResult) -> list[dict[str, Any]]:
    """把 Agent 运行结果追加到 checkpoint 友好的列表。"""
    return [*state.get("agent_runs", []), result.as_dict()]


def _time_context() -> dict[str, str]:
    """给专业 Agent 的相对日期解析提供稳定北京时间上下文。"""
    now = datetime.now(BEIJING_TZ)
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    tomorrow = now + timedelta(days=1)
    return {
        "today": now.strftime(f"%Y-%m-%d {weekday_names[now.weekday()]}"),
        "tomorrow": tomorrow.strftime(f"%Y-%m-%d {weekday_names[tomorrow.weekday()]}"),
        "current_time": now.strftime("%H:%M"),
        "timezone": "Asia/Shanghai (UTC+8, 北京时间)",
    }


def _json_context(state: AssistantState, *, audience: str = "agent") -> str:
    """生成给不同 Agent 使用的紧凑上下文 JSON。

    active draft 是多轮修改和确认的背景，不应该默认变成最终回复的主角。
    因此 Response Agent 使用更收敛的上下文，避免模型把历史草稿误当成当前任务汇总。
    """
    active_email = state.get("active_email_draft")
    active_calendar = state.get("active_calendar_draft")
    payload = {
        "user_message": state.get("user_message", ""),
        "current_time_context": _time_context(),
        "current_turn_guidance": {
            "focus": "优先处理 user_message 表达的本轮任务。",
            "old_context_usage": "旧草稿、旧日程和历史消息只在用户明确说继续、修改、确认、删除或引用它们时使用。",
            "response_style": "最终回复只说明本轮处理结果和必要下一步，不主动汇总无关旧任务。",
        },
        "supervisor_plan": state.get("supervisor_plan") or {},
        "context_result": state.get("context_result"),
        "mail_result": state.get("mail_result"),
        "calendar_result": state.get("calendar_result"),
        "review_result": state.get("review_result"),
        "confirmation_result": state.get("confirmation_result"),
        "execution_result": state.get("execution_result"),
        "available_contacts": state.get("available_contacts") or [],
        "default_signature": state.get("default_signature"),
        "selected_context_refs": state.get("selected_context_refs") or [],
    }
    if audience == "response":
        payload["active_context_summary"] = {
            "has_active_email_draft": bool(active_email),
            "has_active_calendar_draft": bool(active_calendar),
            "usage": "这些只是可能存在的旧上下文；除非本轮 Agent 结果明确使用，否则最终回复不要主动列出或提醒。",
        }
    else:
        payload["active_email_draft"] = active_email
        payload["active_calendar_draft"] = active_calendar
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _message_has_any(message: str, keywords: tuple[str, ...]) -> bool:
    """做轻量关键词判断，只用于路由兜底，不替代 LLM Agent 判断。"""
    compact = re.sub(r"\s+", "", message)
    return any(keyword in compact for keyword in keywords)


def _route_agents_from_message(state: AssistantState, supervisor_text: str) -> list[str]:
    """根据用户消息和 Supervisor 文本得到本轮需要运行的专业 Agent。"""
    message = state.get("user_message", "")
    routes: list[str] = []
    if state.get("selected_context_refs") or _message_has_any(message, ("这封", "选中", "文件", "附件", "文档", "pdf", "word")):
        routes.append("context_agent")
    if _message_has_any(message, ("邮件", "草稿", "收件人", "发给", "发送", "回信", "回复")) or "mail_agent" in supervisor_text:
        routes.append("mail_agent")
    if _message_has_any(message, ("日程", "会议", "日历", "冲突", "改到", "删除明天", "创建一个日程")) or "calendar_agent" in supervisor_text:
        routes.append("calendar_agent")
    if not routes:
        routes.append("response_agent")
    # 去重并保持顺序。
    deduped: list[str] = []
    for item in routes:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _parse_supervisor_json(content: str) -> dict[str, Any]:
    """解析 Supervisor 的结构化 JSON；解析失败时返回空 dict 走兼容兜底。"""
    text = content.strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_route_agents(value: Any) -> list[str]:
    """把模型输出的路由列表清洗成主图已知的 Agent 名称。"""
    allowed = {"context_agent", "mail_agent", "calendar_agent", "response_agent"}
    if not isinstance(value, list):
        return []
    routes: list[str] = []
    for item in value:
        name = str(item).strip()
        if name in allowed and name not in routes:
            routes.append(name)
    return routes


def state_loader(state: AssistantState) -> dict[str, Any]:
    """加载上下文，是多 Agent 主图的入口节点。"""
    loaded = load_context(state)
    trace = loaded.get("route_trace", [])
    if trace and trace[-1] == "load_context":
        trace = [*trace[:-1], "state_loader"]
    loaded["route_trace"] = trace or _trace(state, "state_loader")
    return loaded


def supervisor_agent(state: AssistantState) -> dict[str, Any]:
    """Supervisor Agent：调用模型理解意图并产生路由计划。"""
    prompt = load_prompt("supervisor_agent")
    result = run_llm_agent(
        agent_name="supervisor_agent",
        state=state,
        system_prompt=prompt,
        agent_input=f"请分析本轮请求并决定需要哪些 Agent。\n\n上下文：\n{_json_context(state)}",
        tools=create_tools_for_agent("supervisor_agent"),
        max_iterations=1,
    )
    parsed_plan = _parse_supervisor_json(result.content)
    route_agents = _normalize_route_agents(parsed_plan.get("route_agents"))
    if not route_agents:
        route_agents = _route_agents_from_message(state, result.content)
    # 确认类请求直接交给 Gate/Executor，避免专业 Agent 再次生成或修改草稿。
    if (
        _is_email_send_confirmation(state.get("user_message", ""), state)
        or _is_calendar_create_confirmation(state.get("user_message", ""), state)
        or _is_calendar_delete_confirmation(state.get("user_message", ""), state)
    ):
        route_agents = []
    return {
        "supervisor_plan": {
            "intent": parsed_plan.get("intent") or "",
            "summary": parsed_plan.get("summary") or result.content,
            "route_agents": route_agents,
            "direct_response": parsed_plan.get("direct_response") or "",
            "reason": parsed_plan.get("reason") or "",
        },
        "agent_runs": _append_agent_run(state, result),
        "route_trace": _trace(state, "supervisor_agent"),
    }


def context_agent(state: AssistantState) -> dict[str, Any]:
    """Context Agent：整理选中邮件、日程、文件和历史上下文。"""
    if "context_agent" not in (state.get("supervisor_plan") or {}).get("route_agents", []):
        return {"route_trace": _trace(state, "context_agent")}
    result = run_llm_agent(
        agent_name="context_agent",
        state=state,
        system_prompt=load_prompt("context_agent"),
        agent_input=f"请整理本轮任务需要的上下文。\n\n上下文：\n{_json_context(state)}",
        tools=create_tools_for_agent("context_agent"),
        max_iterations=2,
    )
    return {
        "context_result": result.as_dict(),
        "agent_runs": _append_agent_run(state, result),
        "route_trace": _trace(state, "context_agent"),
    }


def mail_agent(state: AssistantState) -> dict[str, Any]:
    """Mail Agent：处理邮件和本地邮件草稿。"""
    if "mail_agent" not in (state.get("supervisor_plan") or {}).get("route_agents", []):
        return {"route_trace": _trace(state, "mail_agent")}
    result = run_llm_agent(
        agent_name="mail_agent",
        state=state,
        system_prompt=load_prompt("mail_agent_tools"),
        agent_input=f"请处理邮件相关任务。外部发送必须等待 Executor。\n\n上下文：\n{_json_context(state)}",
        tools=create_tools_for_agent("mail_agent"),
        max_iterations=4,
    )
    return {
        "mail_result": result.as_dict(),
        "tool_results": [*state.get("tool_results", []), *result.tool_results],
        "agent_runs": _append_agent_run(state, result),
        "route_trace": _trace(state, "mail_agent"),
    }


def calendar_agent(state: AssistantState) -> dict[str, Any]:
    """Calendar Agent：处理日程草稿、查询和冲突说明。"""
    if "calendar_agent" not in (state.get("supervisor_plan") or {}).get("route_agents", []):
        return {"route_trace": _trace(state, "calendar_agent")}
    result = run_llm_agent(
        agent_name="calendar_agent",
        state=state,
        system_prompt=load_prompt("calendar_agent_tools"),
        agent_input=f"请处理日程相关任务。外部执行必须等待 Executor。\n\n上下文：\n{_json_context(state)}",
        tools=create_tools_for_agent("calendar_agent"),
        max_iterations=4,
    )
    return {
        "calendar_result": result.as_dict(),
        "tool_results": [*state.get("tool_results", []), *result.tool_results],
        "agent_runs": _append_agent_run(state, result),
        "route_trace": _trace(state, "calendar_agent"),
    }


def review_gate(state: AssistantState) -> dict[str, Any]:
    """Review Gate：确定性检查本轮是否存在执行风险。"""
    result = {
        "has_mail_result": bool(state.get("mail_result")),
        "has_calendar_result": bool(state.get("calendar_result")),
        "active_email_draft": bool(state.get("active_email_draft")),
        "active_calendar_draft": bool(state.get("active_calendar_draft")),
        "requires_confirmation": False,
    }
    return {
        "review_result": result,
        "route_trace": _trace(state, "review_gate"),
    }


def confirmation_gate(state: AssistantState) -> dict[str, Any]:
    """Confirmation Gate：确定性识别用户是否在确认高风险操作。"""
    message = state.get("user_message", "")
    confirmation: dict[str, Any] = {"status": "none"}
    if _is_email_send_confirmation(message, state):
        confirmation = {
            "status": "pending_execution",
            "action": "send_email_batch" if _should_batch_email_send(message, state) else "send_email",
        }
    elif _is_calendar_delete_confirmation(message, state):
        confirmation = {"status": "pending_execution", "action": "delete_calendar_event"}
    elif _is_calendar_create_confirmation(message, state):
        confirmation = {"status": "pending_execution", "action": "create_calendar_event"}
    return {
        "confirmation_result": confirmation,
        "route_trace": _trace(state, "confirmation_gate"),
    }


def executor(state: AssistantState) -> dict[str, Any]:
    """Executor：只执行已经由 Confirmation Gate 确认的动作。"""
    confirmation = state.get("confirmation_result") or {}
    if confirmation.get("status") != "pending_execution":
        return {
            "execution_result": {"status": "none"},
            "route_trace": _trace(state, "executor"),
        }
    tool_map = {item.name: item for item in create_tools()}
    result = _try_deterministic_confirmation(state, tool_map)
    if result is None:
        return {
            "execution_result": {
                "status": "failed",
                "response": "没有找到可执行的确认动作。",
                "tool_results": [],
            },
            "route_trace": _trace(state, "executor"),
        }
    response_text, tool_results = result
    return {
        "execution_result": {
            "status": "executed",
            "response": response_text,
            "tool_results": tool_results,
        },
        "tool_results": [*state.get("tool_results", []), *tool_results],
        "route_trace": _trace(state, "executor"),
    }


def response_agent(state: AssistantState) -> dict[str, Any]:
    """Response Agent：整合上游结果，生成最终用户回复。"""
    execution = state.get("execution_result") or {}
    supervisor_plan = state.get("supervisor_plan") or {}
    if execution.get("status") == "executed":
        final_text = str(execution.get("response") or "已执行完成。")
        agent_runs = list(state.get("agent_runs", []))
    elif (
        supervisor_plan.get("direct_response")
        and supervisor_plan.get("route_agents") == ["response_agent"]
        and not state.get("mail_result")
        and not state.get("calendar_result")
        and not state.get("context_result")
    ):
        # 普通对话由 Supervisor 的 LLM 理解结果直接承接，避免同一轮重复调用模型。
        final_text = str(supervisor_plan.get("direct_response"))
        agent_runs = list(state.get("agent_runs", []))
    else:
        result = run_llm_agent(
            agent_name="response_agent",
            state=state,
            system_prompt=load_prompt("response_agent"),
            agent_input=f"请基于本轮请求和本轮 Agent 结果生成最终回复。\n\n上下文：\n{_json_context(state, audience='response')}",
            tools=create_tools_for_agent("response_agent"),
            max_iterations=1,
        )
        final_text = result.content
        agent_runs = _append_agent_run(state, result)

    new_messages = list(state.get("messages", []))
    new_messages.append({"role": "user", "content": state.get("user_message", "")})
    new_messages.append({"role": "assistant", "content": final_text})
    return {
        "messages": new_messages,
        "response": final_text,
        "artifacts": [],
        "agent_runs": agent_runs,
        "route_trace": _trace(state, "response_agent"),
    }


def memory_extractor(state: AssistantState) -> dict[str, Any]:
    """Memory Extractor：复用现有长期记忆候选提取逻辑。"""
    result = extract_memory_candidates(state)
    trace = result.get("route_trace", [])
    if trace and trace[-1] == "extract_memory_candidates":
        trace = [*trace[:-1], "memory_extractor"]
    result["route_trace"] = trace or _trace(state, "memory_extractor")
    return result


__all__ = [
    "state_loader",
    "supervisor_agent",
    "context_agent",
    "mail_agent",
    "calendar_agent",
    "review_gate",
    "confirmation_gate",
    "executor",
    "response_agent",
    "save_turn_state",
    "memory_extractor",
]
