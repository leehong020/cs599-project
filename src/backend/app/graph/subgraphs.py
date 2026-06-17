"""Mail / Calendar 子图——LLM 生成草稿内容。"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.graph.state import AssistantTask
from app.services.llm_client import load_prompt, llm_invoke


class SubgraphState(TypedDict, total=False):
    tasks: list[AssistantTask]
    task_results: list[dict[str, Any]]
    route_trace: list[str]
    user_message: str
    messages: list[dict[str, Any]]
    available_signatures: list[dict[str, Any]]
    default_signature: dict[str, Any] | None


def build_mail_subgraph():
    """编译 Mail Subgraph（邮件草稿生成）。"""
    builder = StateGraph(SubgraphState)
    builder.add_node("plan_mail_task", plan_mail_task)
    builder.add_edge(START, "plan_mail_task")
    builder.add_edge("plan_mail_task", END)
    return builder.compile()


def build_calendar_subgraph():
    """编译 Calendar Subgraph（日程草稿生成）。"""
    builder = StateGraph(SubgraphState)
    builder.add_node("plan_calendar_task", plan_calendar_task)
    builder.add_edge(START, "plan_calendar_task")
    builder.add_edge("plan_calendar_task", END)
    return builder.compile()


def build_gmail_search_subgraph():
    """编译 Gmail 搜索子图。"""
    builder = StateGraph(SubgraphState)
    builder.add_node("plan_gmail_search_task", plan_gmail_search_task)
    builder.add_edge(START, "plan_gmail_search_task")
    builder.add_edge("plan_gmail_search_task", END)
    return builder.compile()


def build_gmail_delete_subgraph():
    """编译 Gmail 删除子图。"""
    builder = StateGraph(SubgraphState)
    builder.add_node("plan_gmail_delete_task", plan_gmail_delete_task)
    builder.add_edge(START, "plan_gmail_delete_task")
    builder.add_edge("plan_gmail_delete_task", END)
    return builder.compile()


def build_read_calendar_subgraph():
    """编译日历读取子图。"""
    builder = StateGraph(SubgraphState)
    builder.add_node("plan_read_calendar_task", plan_read_calendar_task)
    builder.add_edge(START, "plan_read_calendar_task")
    builder.add_edge("plan_read_calendar_task", END)
    return builder.compile()


def build_update_calendar_subgraph():
    """编译日历修改子图。"""
    builder = StateGraph(SubgraphState)
    builder.add_node("plan_update_calendar_task", plan_update_calendar_task)
    builder.add_edge(START, "plan_update_calendar_task")
    builder.add_edge("plan_update_calendar_task", END)
    return builder.compile()


def build_delete_calendar_subgraph():
    """编译日历删除子图。"""
    builder = StateGraph(SubgraphState)
    builder.add_node("plan_delete_calendar_task", plan_delete_calendar_task)
    builder.add_edge(START, "plan_delete_calendar_task")
    builder.add_edge("plan_delete_calendar_task", END)
    return builder.compile()


def plan_mail_task(state: SubgraphState) -> dict[str, Any]:
    """LLM 生成邮件草稿——返回结构化内容。"""
    results = list(state.get("task_results", []))
    user_message = state.get("user_message", "")
    messages = state.get("messages", [])
    signatures = state.get("available_signatures", [])
    default_sig = state.get("default_signature")
    for task in state.get("tasks", []):
        if task.get("domain") != "mail":
            continue
        draft = _generate_draft("mail_agent", user_message, task, messages,
                                signatures=signatures, default_signature=default_sig)
        results.append({
            "task_id": task["id"],
            "domain": "mail",
            "status": "completed",
            "content": draft,  # 结构化 dict：{to, subject, body, signature, raw}
        })
    return {
        "task_results": results,
        "route_trace": [*state.get("route_trace", []), "mail_subgraph.plan_mail_task"],
    }


def plan_calendar_task(state: SubgraphState) -> dict[str, Any]:
    """LLM 生成日程草稿——返回结构化内容。"""
    results = list(state.get("task_results", []))
    user_message = state.get("user_message", "")
    messages = state.get("messages", [])
    for task in state.get("tasks", []):
        if task.get("domain") != "calendar":
            continue
        draft = _generate_draft("calendar_agent", user_message, task, messages)
        results.append({
            "task_id": task["id"],
            "domain": "calendar",
            "status": "completed",
            "content": draft,  # 结构化 dict：{title, start_time, end_time, ...}
        })
    return {
        "task_results": results,
        "route_trace": [*state.get("route_trace", []), "calendar_subgraph.plan_calendar_task"],
    }


def _generate_draft(
    prompt_name: str,
    user_message: str,
    task: dict[str, Any],
    conversation_history: list[dict[str, Any]] | None = None,
    signatures: list[dict[str, Any]] | None = None,
    default_signature: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """调用 LLM 生成草稿内容，返回结构化 dict。

    邮件草稿返回：{to, subject, body, signature, raw}
    日程草稿返回：{title, start_time, end_time, timezone, attendees, location, description, raw}
    降级时返回包含 summary 的简单 dict。
    """
    import re
    from datetime import datetime, timezone as dt_timezone, timedelta
    beijing_tz = dt_timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz)
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

    date_info = (
        f"今天：{now.strftime(f'%Y年%m月%d日 {weekday_names[now.weekday()]}')}\n"
        f"当前时间：{now.strftime('%H:%M')}\n"
        f"时区：Asia/Shanghai (UTC+8, 北京时间)\n"
    )

    # 构建签名信息
    sigs = signatures or []
    default_sig = default_signature or {}
    signature_info = ""
    if sigs:
        sig_lines = ["## 用户配置的署名"]
        for s in sigs:
            marker = " (默认)" if s.get("is_default") else ""
            sig_lines.append(f"- {s.get('label', '未命名')}{marker}: {s.get('content', '')}")
        signature_info = "\n".join(sig_lines) + "\n"
    elif default_sig:
        signature_info = f"## 用户默认署名\n{default_sig.get('content', '')}\n"

    try:
        prompt = load_prompt(prompt_name)
        task_info = f"{date_info}\n用户请求：{user_message}\n任务：{task.get('title', '未知')}"
        if signature_info:
            task_info += f"\n\n{signature_info}"

        history = conversation_history or []
        if history:
            recent = history[-8:] if len(history) > 8 else history
            history_text = "\n".join(
                f"[{msg.get('role', 'unknown')}]: {msg.get('content', '')}"
                for msg in recent
            )
            task_info += f"\n\n最近对话记录：\n{history_text}"

        raw_output = llm_invoke([SystemMessage(content=prompt), HumanMessage(content=task_info)])

        # 尝试解析为 JSON（calendar_agent 输出 JSON）
        json_match = re.search(r'\{[\s\S]*\}', raw_output)
        if json_match and prompt_name == "calendar_agent":
            try:
                parsed = json.loads(json_match.group(0))
                return {
                    "title": parsed.get("title", "未命名日程"),
                    "start_time": parsed.get("start_time", ""),
                    "end_time": parsed.get("end_time", ""),
                    "timezone": parsed.get("timezone", "Asia/Shanghai"),
                    "attendees": parsed.get("attendees", []),
                    "location": parsed.get("location", ""),
                    "description": parsed.get("description", ""),
                    "duration_minutes": parsed.get("duration_minutes", 60),
                    "missing_info": parsed.get("missing_info", []),
                    "raw": raw_output,
                }
            except (json.JSONDecodeError, TypeError):
                pass

        # 邮件草稿：解析 Markdown 结构
        if prompt_name == "mail_agent":
            to_match = re.search(r'\*?\*?收件人[：:]\*?\*?\s*(.+)', raw_output)
            subject_match = re.search(r'\*?\*?主题[：:]\*?\*?\s*(.+)', raw_output)
            body_match = re.search(r'\*?\*?正文[：:]\*?\*?\s*\n([\s\S]+?)(?:\n\*?\*?署名|\Z)', raw_output)
            sig_match = re.search(r'\*?\*?署名[：:]\*?\*?\s*(.+)', raw_output)

            return {
                "to": to_match.group(1).strip() if to_match else "需要确认",
                "subject": subject_match.group(1).strip() if subject_match else "无主题",
                "body": body_match.group(1).strip() if body_match else raw_output,
                "signature": sig_match.group(1).strip() if sig_match else "",
                "raw": raw_output,
            }

        # 通用降级：返回原始文本作为 summary
        return {"summary": raw_output, "raw": raw_output}

    except Exception:
        domain_name = "邮件" if task.get("domain") == "mail" else "日程"
        return {"summary": f"{domain_name}草稿：请根据「{user_message[:100]}」生成内容。"}


def run_mail_subgraph_once(
    tasks: list[AssistantTask],
    user_message: str = "",
    messages: list[dict[str, Any]] | None = None,
    available_signatures: list[dict[str, Any]] | None = None,
    default_signature: dict[str, Any] | None = None,
) -> SubgraphState:
    """单独运行 Mail Subgraph。"""
    graph = build_mail_subgraph()
    state: SubgraphState = {
        "tasks": tasks,
        "task_results": [],
        "route_trace": [],
        "user_message": user_message,
        "messages": messages or [],
    }
    if available_signatures is not None:
        state["available_signatures"] = available_signatures
    if default_signature is not None:
        state["default_signature"] = default_signature
    return graph.invoke(state)


def plan_gmail_search_task(state: SubgraphState) -> dict[str, Any]:
    """搜索 Gmail 邮件——LLM 生成搜索查询，返回结构化结果供 API 层执行。"""
    results = list(state.get("task_results", []))
    user_message = state.get("user_message", "")
    for task in state.get("tasks", []):
        if task.get("domain") != "gmail_search":
            continue
        # LLM 翻译用户意图为 Gmail 搜索查询
        try:
            from app.services.llm_client import llm_invoke as _llm_invoke
            prompt = "你是 Gmail 搜索助手。根据用户请求生成 Gmail 搜索查询字符串。只返回查询字符串，不要解释。\n\n支持的搜索语法：from:xxx, to:xxx, subject:xxx, has:attachment, is:unread, newer_than:7d, older_than:7d, label:xxx。"
            query = _llm_invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=user_message),
            ]).strip()
        except Exception:
            query = "in:inbox"
        results.append({
            "task_id": task["id"],
            "domain": "gmail_search",
            "status": "completed",
            "content": {"gmail_query": query, "user_intent": user_message},
        })
    return {
        "task_results": results,
        "route_trace": [*state.get("route_trace", []), "gmail_search_subgraph.plan_gmail_search_task"],
    }


def plan_gmail_delete_task(state: SubgraphState) -> dict[str, Any]:
    """删除 Gmail 邮件——LLM 识别要删除的邮件，返回结构化结果供 API 层执行。"""
    results = list(state.get("task_results", []))
    user_message = state.get("user_message", "")
    messages = state.get("messages", [])
    for task in state.get("tasks", []):
        if task.get("domain") != "gmail_delete":
            continue
        # 从最近上下文中查找邮件 ID
        context = "\n".join(
            f"[{m.get('role', '?')}]: {str(m.get('content', ''))[:500]}"
            for m in (messages or [])[-6:]
        )
        results.append({
            "task_id": task["id"],
            "domain": "gmail_delete",
            "status": "completed",
            "content": {
                "user_intent": user_message,
                "context": context,
                "action": "delete_email",
                "needs_confirmation": True,
            },
        })
    return {
        "task_results": results,
        "route_trace": [*state.get("route_trace", []), "gmail_delete_subgraph.plan_gmail_delete_task"],
    }


def plan_read_calendar_task(state: SubgraphState) -> dict[str, Any]:
    """读取 Google Calendar 日程——LLM 解析时间范围，返回结构化结果供 API 层执行。"""
    results = list(state.get("task_results", []))
    user_message = state.get("user_message", "")
    for task in state.get("tasks", []):
        if task.get("domain") != "read_calendar":
            continue
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        beijing_tz = _tz(_td(hours=8))
        now = _dt.now(beijing_tz)
        time_min = now.isoformat()
        # 默认查询未来 7 天
        time_max = (now + _td(days=7)).isoformat()
        results.append({
            "task_id": task["id"],
            "domain": "read_calendar",
            "status": "completed",
            "content": {
                "time_min": time_min,
                "time_max": time_max,
                "calendar_id": "primary",
                "user_intent": user_message,
            },
        })
    return {
        "task_results": results,
        "route_trace": [*state.get("route_trace", []), "calendar_read_subgraph.plan_read_calendar_task"],
    }


def plan_update_calendar_task(state: SubgraphState) -> dict[str, Any]:
    """修改日历日程——LLM 解析修改意图。"""
    results = list(state.get("task_results", []))
    user_message = state.get("user_message", "")
    for task in state.get("tasks", []):
        if task.get("domain") != "update_calendar":
            continue
        results.append({
            "task_id": task["id"],
            "domain": "update_calendar",
            "status": "completed",
            "content": {
                "user_intent": user_message,
                "action": "update_calendar_event",
                "needs_confirmation": True,
            },
        })
    return {
        "task_results": results,
        "route_trace": [*state.get("route_trace", []), "calendar_update_subgraph.plan_update_calendar_task"],
    }


def plan_delete_calendar_task(state: SubgraphState) -> dict[str, Any]:
    """删除日历日程——LLM 识别要删除的日程。"""
    results = list(state.get("task_results", []))
    user_message = state.get("user_message", "")
    for task in state.get("tasks", []):
        if task.get("domain") != "delete_calendar":
            continue
        results.append({
            "task_id": task["id"],
            "domain": "delete_calendar",
            "status": "completed",
            "content": {
                "user_intent": user_message,
                "action": "delete_calendar_event",
                "needs_confirmation": True,
            },
        })
    return {
        "task_results": results,
        "route_trace": [*state.get("route_trace", []), "calendar_delete_subgraph.plan_delete_calendar_task"],
    }


def run_calendar_subgraph_once(
    tasks: list[AssistantTask],
    user_message: str = "",
    messages: list[dict[str, Any]] | None = None,
) -> SubgraphState:
    """单独运行 Calendar Subgraph。"""
    graph = build_calendar_subgraph()
    return graph.invoke({
        "tasks": tasks,
        "task_results": [],
        "route_trace": [],
        "user_message": user_message,
        "messages": messages or [],
    })


def run_gmail_search_subgraph_once(
    tasks: list[AssistantTask],
    user_message: str = "",
    messages: list[dict[str, Any]] | None = None,
) -> SubgraphState:
    """单独运行 Gmail 搜索子图。"""
    graph = build_gmail_search_subgraph()
    return graph.invoke({
        "tasks": tasks,
        "task_results": [],
        "route_trace": [],
        "user_message": user_message,
        "messages": messages or [],
    })


def run_gmail_delete_subgraph_once(
    tasks: list[AssistantTask],
    user_message: str = "",
    messages: list[dict[str, Any]] | None = None,
) -> SubgraphState:
    """单独运行 Gmail 删除子图。"""
    graph = build_gmail_delete_subgraph()
    return graph.invoke({
        "tasks": tasks,
        "task_results": [],
        "route_trace": [],
        "user_message": user_message,
        "messages": messages or [],
    })


def run_read_calendar_subgraph_once(
    tasks: list[AssistantTask],
    user_message: str = "",
    messages: list[dict[str, Any]] | None = None,
) -> SubgraphState:
    """单独运行日历读取子图。"""
    graph = build_read_calendar_subgraph()
    return graph.invoke({
        "tasks": tasks,
        "task_results": [],
        "route_trace": [],
        "user_message": user_message,
        "messages": messages or [],
    })


def run_update_calendar_subgraph_once(
    tasks: list[AssistantTask],
    user_message: str = "",
    messages: list[dict[str, Any]] | None = None,
) -> SubgraphState:
    """单独运行日历修改子图。"""
    graph = build_update_calendar_subgraph()
    return graph.invoke({
        "tasks": tasks,
        "task_results": [],
        "route_trace": [],
        "user_message": user_message,
        "messages": messages or [],
    })


def run_delete_calendar_subgraph_once(
    tasks: list[AssistantTask],
    user_message: str = "",
    messages: list[dict[str, Any]] | None = None,
) -> SubgraphState:
    """单独运行日历删除子图。"""
    graph = build_delete_calendar_subgraph()
    return graph.invoke({
        "tasks": tasks,
        "task_results": [],
        "route_trace": [],
        "user_message": user_message,
        "messages": messages or [],
    })
