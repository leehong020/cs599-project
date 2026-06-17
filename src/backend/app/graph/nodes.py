"""Agent Graph Nodes — 单 agent 节点，工具调用 + 结果整合。

关键设计：
- agent_node 内部处理工具调用，将 LangChain tool_calls 转为标准 dict 格式
- 每条 tool_call 后紧跟对应 ToolMessage，避免 API 的 "insufficient tool messages" 错误
- 支持多轮工具调用循环，兼容 DeepSeek 可能返回的 DSML 文本工具调用格式
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

from app.graph.state import AssistantState
from app.services.llm_client import (
    build_system_prompt,
    get_chat_model,
    load_prompt,
)

logger = logging.getLogger(__name__)
BEIJING_TZ = dt_timezone(timedelta(hours=8))
MAX_TOOL_ITERATIONS = 4


def _trace(state: AssistantState, node_name: str) -> list[str]:
    return [*state.get("route_trace", []), node_name]


class _MemoryExtraction(BaseModel):
    should_remember: bool = Field(default=False)
    memory_key: str = Field(default="")
    memory_text: str = Field(default="")
    namespace: str = Field(default="preferences")
    reason: str = Field(default="")


# ═══════════════════════════════════════════════════════════════════════
# 工具调用辅助
# ═══════════════════════════════════════════════════════════════════════

def _normalize_tool_call(tc: Any) -> dict[str, Any]:
    """将 LangChain tool_call（可能是 dict 或对象）统一转为 dict 格式。"""
    if isinstance(tc, dict):
        return {
            "name": str(tc.get("name", "")),
            "args": tc.get("args", {}) or {},
            "id": str(tc.get("id", "")),
        }
    # 对象格式（ToolCall namedtuple / Pydantic model）
    name = getattr(tc, "name", "") or ""
    args = getattr(tc, "args", {}) or {}
    tc_id = getattr(tc, "id", "") or ""
    return {"name": str(name), "args": dict(args) if args else {}, "id": str(tc_id)}


def _message_content_to_text(content: Any) -> str:
    """把模型返回的 content 统一转成字符串，避免 list/dict 泄漏到用户回复。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(item) for item in content)
    if content is None:
        return ""
    return str(content)


def _parse_dsml_tool_calls(content: str) -> list[dict[str, Any]]:
    """解析 DeepSeek DSML 文本工具调用。

    DeepSeek 在部分场景不会填充 LangChain 标准 tool_calls，而是把工具调用写成
    `<｜｜DSML｜｜tool_calls>` 文本。这里将其转回标准工具调用结构，防止原始协议
    出现在用户消息里。
    """
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
        name = match.group(1).strip()
        body = match.group(2)
        args: dict[str, Any] = {}
        for param in parameter_pattern.finditer(body):
            args[param.group(1).strip()] = param.group(2).strip()
        if name:
            calls.append({"name": name, "args": args, "id": f"dsml_call_{index}"})
    return calls


def _contains_tool_protocol(content: str) -> bool:
    """判断最终回复是否仍包含工具协议，避免内部协议暴露给用户。"""
    markers = ("<｜｜DSML｜｜tool_calls>", "<｜｜DSML｜｜invoke", "tool_calls")
    return any(marker in content for marker in markers)


def _load_tool_json(result_text: str) -> dict[str, Any] | None:
    """解析工具统一 JSON 返回；解析失败时返回 None。"""
    try:
        parsed = json.loads(result_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _tool_result_message(result_text: str) -> str:
    """把工具 JSON 结果压缩成模型容易阅读的观察文本。"""
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
    """当模型最终仍返回工具协议时，基于工具结果生成保底自然语言回复。"""
    if not tool_results:
        return "我已经处理了你的请求，但没有获得可展示的结果。"

    messages: list[str] = []
    for item in tool_results:
        parsed = _load_tool_json(str(item.get("result", "")))
        if parsed and parsed.get("message"):
            messages.append(str(parsed["message"]))
        elif item.get("result"):
            messages.append(str(item["result"]))

    return "\n".join(messages) if messages else "我已经处理了你的请求。"


def _has_negative_intent(message: str) -> bool:
    """判断用户是否在否定执行，避免把“不要发送”误判成确认。"""
    return any(keyword in message for keyword in ("不要", "别", "先不", "暂不", "取消", "别发", "不要发"))


def _is_email_send_confirmation(message: str, state: AssistantState) -> bool:
    """识别邮件发送确认。

    发送邮件是外部写操作。这里用确定性分支兜底，避免模型明明没有调用
    `send_email_draft` 却直接回复“已发送”。
    """
    if not state.get("active_email_draft") or _has_negative_intent(message):
        return False
    compact = re.sub(r"\s+", "", message)
    return any(keyword in compact for keyword in ("确认发送", "可以发送", "直接发送", "发出去", "发送吧"))


def _previous_assistant_requested_batch_send(state: AssistantState) -> bool:
    """判断上一条 assistant 是否刚刚要求确认发送多封邮件。"""
    for message in reversed(state.get("messages", []) or []):
        role = message.get("role") if isinstance(message, dict) else getattr(message, "type", "")
        if role not in {"assistant", "ai"}:
            continue
        content = str(message.get("content", "") if isinstance(message, dict) else getattr(message, "content", ""))
        compact = re.sub(r"\s+", "", content)
        if ("两封" in compact or "多封" in compact or ("邮件1" in compact and "邮件2" in compact)) and (
            "确认发送" in compact or "发送" in compact
        ):
            return True
        return False
    return False


def _should_batch_email_send(message: str, state: AssistantState) -> bool:
    """判断本次确认是否应发送当前线程的多封本地邮件草稿。"""
    compact = re.sub(r"\s+", "", message)
    if any(keyword in compact for keyword in ("全部发送", "都发送", "都发", "两封", "多封", "所有草稿", "一起发送")):
        return True
    return _previous_assistant_requested_batch_send(state)


def _is_calendar_create_confirmation(message: str, state: AssistantState) -> bool:
    """识别日程创建确认。

    为避免把“创建一个日程，内容是……”误判成执行，这里只接受较短的确认式
    表达。真正的新建需求仍交给 LLM 调用 `create_calendar_event_draft`。
    """
    if not state.get("active_calendar_draft") or _has_negative_intent(message):
        return False
    compact = re.sub(r"\s+", "", message)
    if len(compact) > 24:
        return False
    return any(
        keyword in compact
        for keyword in ("确认创建", "确认日程", "可以创建", "直接创建", "创建日程", "添加到日历", "加入日历")
    )


def _is_calendar_delete_confirmation(message: str, state: AssistantState) -> bool:
    """识别日程删除确认。"""
    active = state.get("active_calendar_draft")
    if not isinstance(active, dict) or _has_negative_intent(message):
        return False
    content = active.get("content") if isinstance(active.get("content"), dict) else {}
    if content.get("calendar_action") != "delete":
        return False
    compact = re.sub(r"\s+", "", message)
    if len(compact) > 24:
        return False
    return any(keyword in compact for keyword in ("确认删除", "可以删除", "直接删除", "删除吧"))


def _wants_conflict_override(message: str) -> bool:
    """识别用户是否明确要求忽略日程冲突继续创建。"""
    compact = re.sub(r"\s+", "", message)
    return any(keyword in compact for keyword in ("仍然创建", "忽略冲突", "继续创建", "知道冲突"))


def _format_addresses(raw: Any) -> str:
    """把工具返回的邮箱列表格式化成自然语言。"""
    if not isinstance(raw, list):
        return ""
    values: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            email = str(item.get("email") or "").strip()
            name = str(item.get("name") or item.get("display_name") or "").strip()
            values.append(f"{name} <{email}>" if name and email else email or name)
        else:
            values.append(str(item))
    return "、".join(value for value in values if value)


def _deterministic_tool_reply(tool_name: str, result_text: str) -> str:
    """把确定性执行工具的 JSON 结果转换成用户可读回复。

    只有工具返回成功时才说“已发送/已创建”；工具失败时直接展示失败原因。
    """
    parsed = _load_tool_json(result_text)
    if not parsed:
        return result_text

    message = str(parsed.get("message") or "")
    data = parsed.get("data") if isinstance(parsed.get("data"), dict) else {}
    if not parsed.get("ok"):
        return message or "执行失败，请检查草稿信息后再试。"

    if tool_name == "send_email_draft":
        to_text = _format_addresses(data.get("to"))
        subject = str(data.get("subject") or "无主题")
        return (
            "✅ 邮件已成功发送。\n\n"
            f"- 收件人：{to_text or '未返回'}\n"
            f"- 主题：{subject}"
        )

    if tool_name == "send_all_local_email_drafts":
        sent_count = int(data.get("sent_count") or 0)
        failed_count = int(data.get("failed_count") or 0)
        lines = [f"✅ 已成功发送 {sent_count} 封邮件。"]
        sent_items = data.get("sent") if isinstance(data.get("sent"), list) else []
        for index, item in enumerate(sent_items, 1):
            if not isinstance(item, dict):
                continue
            to_text = _format_addresses(item.get("to"))
            subject = str(item.get("subject") or "无主题")
            lines.append(f"{index}. {to_text or '未返回收件人'} - {subject}")
        if failed_count:
            lines.append(f"\n有 {failed_count} 封发送失败，请查看失败原因后重试。")
        return "\n".join(lines)

    if tool_name == "execute_calendar_event_draft":
        title = str(data.get("title") or "未命名日程")
        start_time = str(data.get("start_time") or "")
        end_time = str(data.get("end_time") or "")
        location = str(data.get("location") or "")
        lines = [
            "✅ 日程已成功创建。",
            "",
            f"- 标题：{title}",
            f"- 时间：{start_time} - {end_time}".rstrip(" - "),
        ]
        if location:
            lines.append(f"- 地点：{location}")
        return "\n".join(lines)

    if tool_name == "execute_calendar_event_delete_draft":
        title = str(data.get("title") or "未命名日程")
        lines = ["✅ 日程已成功删除。", "", f"- 标题：{title}"]
        return "\n".join(lines)

    return message or "已执行完成。"


def _try_deterministic_confirmation(
    state: AssistantState,
    tool_map: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]] | None:
    """对高风险确认操作做确定性执行兜底。

    这一步在 LLM 调用前执行。只要用户表达的是确认发送/确认创建，并且当前
    会话存在对应 active draft，就直接调用工具。这样最终回复一定来自真实
    工具结果，而不是模型自行生成的“成功”文本。
    """
    user_msg = state.get("user_message", "")
    tool_name = ""
    tool_args: dict[str, Any] = {}

    if _is_email_send_confirmation(user_msg, state):
        if _should_batch_email_send(user_msg, state):
            tool_name = "send_all_local_email_drafts"
            tool_args = {"confirm": True, "thread_only": True}
        else:
            tool_name = "send_email_draft"
    elif _is_calendar_delete_confirmation(user_msg, state):
        tool_name = "execute_calendar_event_delete_draft"
    elif _is_calendar_create_confirmation(user_msg, state):
        tool_name = "execute_calendar_event_draft"
        tool_args = {"conflict_override": _wants_conflict_override(user_msg)}

    if not tool_name:
        return None

    tool_func = tool_map.get(tool_name)
    if not tool_func:
        result_text = json.dumps(
            {
                "ok": False,
                "code": "confirmation_tool_missing",
                "message": f"确认工具不可用：{tool_name}",
                "data": {},
            },
            ensure_ascii=False,
        )
    else:
        try:
            result_text = str(tool_func.invoke(tool_args))
        except Exception as exc:
            result_text = json.dumps(
                {
                    "ok": False,
                    "code": "confirmation_tool_failed",
                    "message": f"确认执行失败：{exc}",
                    "data": {"tool": tool_name},
                },
                ensure_ascii=False,
            )

    logger.info("Deterministic confirmation executed: %s", tool_name)
    tool_results = [{"name": tool_name, "result": result_text}]
    return _deterministic_tool_reply(tool_name, result_text), tool_results


def _compact_active_artifact(value: Any) -> dict[str, Any] | None:
    """压缩 active draft，避免把过长正文反复塞进系统 prompt。"""
    if not isinstance(value, dict):
        return None
    content = value.get("content") if isinstance(value.get("content"), dict) else {}
    compact = {
        "artifact_id": value.get("artifact_id"),
        "work_item_id": value.get("work_item_id"),
        "artifact_type": value.get("artifact_type"),
        "version": value.get("version"),
        "maturity": value.get("maturity"),
        "status": value.get("status"),
        "content": {},
    }
    for key in (
        "to", "cc", "bcc", "subject", "body", "signature", "signature_policy",
        "title", "start_time", "end_time", "timezone", "calendar_id",
        "attendees", "location", "description", "conflict_override",
        "conflict_summary", "missing_fields", "external_event_id", "calendar_action",
    ):
        if key not in content:
            continue
        item = content[key]
        if isinstance(item, str) and len(item) > 800:
            item = item[:800] + "..."
        compact["content"][key] = item
    return compact


def _compact_selected_context_refs(raw_refs: Any) -> list[dict[str, Any]]:
    """压缩前端显式选中的邮件、日程或文件上下文。"""
    if not isinstance(raw_refs, list):
        return []
    result: list[dict[str, Any]] = []
    for ref in raw_refs[:10]:
        if not isinstance(ref, dict):
            continue
        result.append(
            {
                "ref_type": ref.get("ref_type") or ref.get("type"),
                "ref_id": ref.get("ref_id") or ref.get("id"),
                "calendar_id": ref.get("calendar_id"),
                "title": ref.get("title"),
                "subject": ref.get("subject"),
                "start_time": ref.get("start_time"),
                "end_time": ref.get("end_time"),
                "timezone": ref.get("timezone"),
                "location": ref.get("location"),
                "attendees": ref.get("attendees"),
            }
        )
    return result


# ═══════════════════════════════════════════════════════════════════════
# 图节点
# ═══════════════════════════════════════════════════════════════════════

def load_context(state: AssistantState) -> dict[str, Any]:
    """加载对话上下文，构建系统 prompt。"""
    messages = list(state.get("messages", []))
    recalled = list(state.get("recalled_memories", []))

    rolling_summary = state.get("conversation_summary")
    if len(messages) > 16 and not rolling_summary:
        try:
            older_text = "\n".join(
                f"[{m.get('role', '?')}]: {str(m.get('content', ''))[:200]}"
                for m in messages[:-8]
            )
            from app.services.llm_client import llm_invoke
            result = llm_invoke([
                SystemMessage(content="请用1-2句话中文总结这段对话的关键信息。"),
                HumanMessage(content=older_text),
            ])
            rolling_summary = result.strip() if result else None
        except Exception:
            rolling_summary = None

    now = datetime.now(BEIJING_TZ)
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

    context = {
        "today": now.strftime(f"%Y年%m月%d日 {weekday_names[now.weekday()]}"),
        "current_time": now.strftime("%H:%M"),
        "timezone": "Asia/Shanghai (UTC+8, 北京时间)",
        "conversation_summary": rolling_summary,
        "long_term_memories": [
            {"key": m.get("memory_key", ""), "content": m.get("content", {})}
            for m in recalled[:10]
        ],
        "available_signatures": [
            {"label": s.get("label", ""), "content": s.get("content", ""),
             "is_default": s.get("is_default", False)}
            for s in (state.get("available_signatures", []) or [])
        ],
        "available_contacts": [
            {"id": c.get("id", ""), "display_name": c.get("display_name", ""), "email": c.get("email", "")}
            for c in (state.get("available_contacts", []) or [])[:100]
        ],
        "default_signature": (
            state.get("default_signature", {}).get("content", "")
            if state.get("default_signature") else ""
        ),
        "user_profile": state.get("user_profile") or {},
        "active_email_draft": _compact_active_artifact(state.get("active_email_draft")),
        "active_calendar_draft": _compact_active_artifact(state.get("active_calendar_draft")),
        "selected_context_refs": _compact_selected_context_refs(state.get("selected_context_refs")),
        "user_message": state.get("user_message", ""),
    }

    system_prompt = build_system_prompt(context)

    return {
        "messages": messages,
        "conversation_summary": rolling_summary,
        "system_prompt": system_prompt,
        "route_trace": _trace(state, "load_context"),
    }


def agent_node(state: AssistantState) -> dict[str, Any]:
    """Agent 节点：多轮 LLM → tool → observe → final 循环。"""
    from app.graph.tools import create_tools

    # ── 准备工具。工具调用过程只写日志，不直接展示到前端。 ──
    tools: list = []
    tool_map: dict[str, Any] = {}
    try:
        tools = create_tools()
        tool_map = {t.name: t for t in tools}
    except Exception as e:
        logger.warning(f"Failed to create tools: {e}")

    deterministic_result = _try_deterministic_confirmation(state, tool_map)
    if deterministic_result is not None:
        final_text, tool_results = deterministic_result
        new_msgs = list(state.get("messages", []))
        new_msgs.append({"role": "user", "content": state.get("user_message", "")})
        new_msgs.append({"role": "assistant", "content": final_text})
        return {
            "messages": new_msgs,
            "response": final_text,
            "artifacts": [],
            "tool_results": tool_results,
            "route_trace": _trace(state, "agent"),
        }

    # ── 非确认类请求再交给 LLM 决定是否调用工具。 ──
    model = get_chat_model()
    model_with_tools = model.bind_tools(tools) if tools else model
    system_prompt = state.get("system_prompt", "你是 Mailflow Agent。")

    # ── 从 dict 状态重建 LangChain 消息 ──────────────────────────
    chat_messages: list = [SystemMessage(content=system_prompt)]
    user_msg = state.get("user_message", "")

    for m in state.get("messages", []):
        if not isinstance(m, dict):
            continue
        role = m.get("role", "")
        content = str(m.get("content", ""))

        if role == "user":
            chat_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            chat_messages.append(AIMessage(content=content))
        # 跳过旧格式的 tool 消息（本轮由 agent 内部处理）

    # 追加当前用户消息
    chat_messages.append(HumanMessage(content=user_msg))

    tool_results: list[dict[str, Any]] = []
    final_text = ""

    # ── 多轮工具调用循环。每轮允许多个工具，最多执行 MAX_TOOL_ITERATIONS 轮。 ──
    for iteration in range(MAX_TOOL_ITERATIONS):
        try:
            response = model_with_tools.invoke(chat_messages)
        except Exception as e:
            logger.error(f"LLM invoke failed: {e}")
            final_text = f"抱歉，处理请求时出错了：{e}"
            break

        content_text = _message_content_to_text(getattr(response, "content", ""))
        raw_tool_calls = getattr(response, "tool_calls", None) or []
        tool_calls = [_normalize_tool_call(tc) for tc in raw_tool_calls]
        dsml_calls: list[dict[str, Any]] = []

        # DeepSeek 可能把工具调用写在文本里。此时不允许原文进入最终回复。
        if not tool_calls:
            dsml_calls = _parse_dsml_tool_calls(content_text)
            tool_calls = dsml_calls

        logger.info(
            "Agent iteration %s: %s tool call(s), content='%s'",
            iteration + 1,
            len(tool_calls),
            content_text[:100],
        )

        if not tool_calls:
            final_text = content_text
            break

        if dsml_calls:
            chat_messages.append(AIMessage(content="我需要调用工具获取结果。"))
        else:
            chat_messages.append(response)

        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_id = tc["id"] or f"tool_call_{iteration}_{len(tool_results)}"

            logger.info(
                "  Executing tool: %s(%s)",
                tool_name,
                json.dumps(tool_args, ensure_ascii=False)[:500],
            )

            tool_func = tool_map.get(tool_name)
            if tool_func:
                try:
                    result_text = str(tool_func.invoke(tool_args))
                except Exception as e:
                    result_text = json.dumps(
                        {
                            "ok": False,
                            "code": "tool_execution_failed",
                            "message": f"工具执行失败：{e}",
                            "data": {"tool": tool_name},
                        },
                        ensure_ascii=False,
                    )
                    logger.error("  Tool %s failed: %s", tool_name, e)
            else:
                result_text = json.dumps(
                    {
                        "ok": False,
                        "code": "unknown_tool",
                        "message": f"未知工具：{tool_name}",
                        "data": {"tool": tool_name},
                    },
                    ensure_ascii=False,
                )
                logger.warning("  Unknown tool: %s", tool_name)

            tool_results.append({"name": tool_name, "result": result_text})

            # 标准 tool_calls 必须紧跟 ToolMessage；DSML 是文本协议，只作为观察文本喂回模型。
            if dsml_calls:
                chat_messages.append(
                    HumanMessage(content=f"工具 {tool_name} 执行结果：{_tool_result_message(result_text)}")
                )
            else:
                chat_messages.append(
                    ToolMessage(content=_tool_result_message(result_text), tool_call_id=tool_id)
                )
    else:
        final_text = ""

    # 如果工具循环结束后还没有自然语言回复，再让模型基于观察结果生成最终回复。
    if not final_text and tool_results:
        try:
            final_prompt = (
                "请根据以上工具执行结果，用中文给用户一个简洁自然的最终回复。"
                "不要输出工具调用、XML、DSML 或 JSON。"
            )
            final_response = get_chat_model().invoke([*chat_messages, HumanMessage(content=final_prompt)])
            final_text = _message_content_to_text(getattr(final_response, "content", ""))
        except Exception:
            final_text = _fallback_tool_summary(tool_results)

    if _contains_tool_protocol(final_text):
        final_text = _fallback_tool_summary(tool_results)

    if not final_text:
        final_text = "我已经处理了你的请求。"

    new_msgs = list(state.get("messages", []))
    new_msgs.append({"role": "user", "content": user_msg})
    assistant_message: dict[str, Any] = {"role": "assistant", "content": final_text}
    new_msgs.append(assistant_message)

    return {
        "messages": new_msgs,
        "response": final_text,
        # 邮件/日程草稿仍写入数据库 Artifact，但聊天页不再返回或渲染卡片。
        # 用户需要看的内容由 assistant 自然语言回复直接列出，避免出现双重展示。
        "artifacts": [],
        "tool_results": tool_results,
        "route_trace": _trace(state, "agent"),
    }


def save_turn_state(state: AssistantState) -> dict[str, Any]:
    return {
        "messages": list(state.get("messages", [])),
        "turn_count": int(state.get("turn_count", 0)) + 1,
        "route_trace": _trace(state, "save_turn_state"),
    }


def extract_memory_candidates(state: AssistantState) -> dict[str, Any]:
    message = state.get("user_message", "")
    candidates = list(state.get("memory_candidates", []))

    if any(kw in message for kw in ("记住", "以后", "长期", "默认", "偏好")):
        candidates.append({
            "source": "user_message", "content": {"text": message},
            "status": "active", "namespace": "preferences",
            "memory_key": message.strip()[:80],
        })
        return {"memory_candidates": candidates, "route_trace": _trace(state, "extract_memory_candidates")}

    if len(message.strip()) < 15:
        return {"memory_candidates": candidates, "route_trace": _trace(state, "extract_memory_candidates")}

    try:
        from app.services.llm_client import llm_invoke_structured
        system = load_prompt("system_prompt").split("##")[0]
        result = llm_invoke_structured(
            [SystemMessage(content=f"{system}\n\n判断以下消息是否值得长期记忆（偏好/习惯/联系人/背景）。"),
             HumanMessage(content=message)],
            _MemoryExtraction,
        )
        if result and result.get("should_remember"):
            candidates.append({
                "source": "llm_detection", "content": {"text": result.get("memory_text", message)},
                "status": "active", "namespace": result.get("namespace", "preferences"),
                "memory_key": result.get("memory_key", message.strip()[:80]),
            })
    except Exception:
        pass

    return {"memory_candidates": candidates, "route_trace": _trace(state, "extract_memory_candidates")}
