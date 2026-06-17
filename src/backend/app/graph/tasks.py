from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.graph.state import AssistantTask
from app.services.llm_client import load_prompt, llm_invoke_structured

MAIL_KEYWORDS = ("邮件", "发信", "发送", "回复", "mail", "email")
CALENDAR_KEYWORDS = ("日程", "会议", "安排", "calendar", "meeting", "schedule")
DEPENDENCY_KEYWORDS = ("会议链接", "日程链接", "calendar link", "meeting link")
GMAIL_SEARCH_KEYWORDS = ("查邮件", "搜索邮件", "找邮件", "收件箱", "inbox", "search email", "有什么邮件", "看看邮件")
GMAIL_DELETE_KEYWORDS = ("删除邮件", "删邮件", "删掉邮件", "delete email", "trash")
CALENDAR_READ_KEYWORDS = ("查看日程", "有什么日程", "我的日历", "日程列表", "有什么会议", "今天有什么", "明天有什么", "calendar", "schedule", "查看日历")
CALENDAR_UPDATE_KEYWORDS = ("改日程", "修改会议", "改时间", "推迟", "提前", "reschedule", "update event")
CALENDAR_DELETE_KEYWORDS = ("删除日程", "取消会议", "删日程", "取消日程", "delete event", "cancel event")


# ── LLM 结构化输出 schema ──────────────────────────────────────────

class _CompiledTask(BaseModel):
    id: str = Field(description="任务 ID，如 task_mail_1")
    domain: str = Field(description="mail | calendar | general")
    operation: str = Field(description="操作类型")
    title: str = Field(description="任务标题")
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class _TaskCompilation(BaseModel):
    action_type: str = Field(default="create_task", description="general_chat | create_task | confirm_action | revise_task")
    summary: str = Field(default="", description="一句话总结用户意图")
    tasks: list[_CompiledTask] = Field(default_factory=list)
    entities: list[dict[str, str]] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: str = ""


# ── 关键词检测（降级方案）───────────────────────────────────────────

def detect_requested_domains(message: str) -> list[str]:
    """关键词匹配业务域。LLM 不可用时降级使用。"""
    lowered = message.lower()
    domains: list[str] = []
    if any(kw in lowered for kw in GMAIL_SEARCH_KEYWORDS):
        domains.append("gmail_search")
    elif any(kw in lowered for kw in MAIL_KEYWORDS):
        domains.append("mail")
    if any(kw in lowered for kw in CALENDAR_READ_KEYWORDS):
        domains.append("read_calendar")
    elif any(kw in lowered for kw in CALENDAR_DELETE_KEYWORDS):
        domains.append("delete_calendar")
    elif any(kw in lowered for kw in CALENDAR_UPDATE_KEYWORDS):
        domains.append("update_calendar")
    elif any(kw in lowered for kw in CALENDAR_KEYWORDS):
        domains.append("calendar")
    if any(kw in lowered for kw in GMAIL_DELETE_KEYWORDS):
        domains.append("gmail_delete")
    if not domains:
        domains.append("general")
    return domains


def extract_contact_mentions(message: str) -> list[str]:
    """正则提取中文语境中的人名候选。"""
    matches = re.findall(r"(?:给|邀请)(.+?)(?:发送|发|回复|安排|创建|开|参加|$)", message)
    names: list[str] = []
    for chunk in matches:
        for name in re.split(r"[、,，和与\s]+", chunk):
            cleaned = _clean_contact_name(name)
            if cleaned and cleaned not in names:
                names.append(cleaned)
    return names


def resolve_contact_mentions(
    mentions: list[str],
    contacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """根据联系人列表解析人名，同名时返回歧义。"""
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for contact in contacts:
        name = str(contact.get("display_name") or "").strip()
        if name:
            by_name[name].append(contact)

    resolved: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in mentions:
        candidates = by_name.get(name, [])
        if len(candidates) == 1:
            resolved.append(candidates[0])
        elif len(candidates) > 1:
            ambiguous.append({"name": name, "candidates": candidates})
        else:
            missing.append(name)
    return {"resolved": resolved, "ambiguous": ambiguous, "missing": missing}


def compile_request_tasks(message: str) -> list[AssistantTask]:
    """关键词降级：确定性编译任务 DAG。"""
    domains = detect_requested_domains(message)
    tasks: list[AssistantTask] = []
    if "gmail_search" in domains:
        tasks.append({
            "id": "task_gmail_search_1", "domain": "gmail_search",
            "title": "搜索 Gmail 邮件", "depends_on": [], "status": "planned", "reason": None,
        })
    if "gmail_delete" in domains:
        tasks.append({
            "id": "task_gmail_delete_1", "domain": "gmail_delete",
            "title": "删除 Gmail 邮件", "depends_on": [], "status": "planned", "reason": None,
        })
    if "read_calendar" in domains:
        tasks.append({
            "id": "task_read_calendar_1", "domain": "read_calendar",
            "title": "读取日程列表", "depends_on": [], "status": "planned", "reason": None,
        })
    if "update_calendar" in domains:
        tasks.append({
            "id": "task_update_calendar_1", "domain": "update_calendar",
            "title": "修改日程", "depends_on": [], "status": "planned", "reason": None,
        })
    if "delete_calendar" in domains:
        tasks.append({
            "id": "task_delete_calendar_1", "domain": "delete_calendar",
            "title": "删除日程", "depends_on": [], "status": "planned", "reason": None,
        })
    if "calendar" in domains:
        tasks.append({
            "id": "task_calendar_1", "domain": "calendar",
            "title": "准备日程任务", "depends_on": [], "status": "planned", "reason": None,
        })
    if "mail" in domains:
        depends_on = ["task_calendar_1"] if _mail_depends_on_calendar(message, domains) else []
        tasks.append({
            "id": "task_mail_1", "domain": "mail",
            "title": "准备邮件任务", "depends_on": depends_on, "status": "planned", "reason": None,
        })
    if "general" in domains:
        tasks.append({
            "id": "task_general_1", "domain": "general",
            "title": "普通对话", "depends_on": [], "status": "planned", "reason": None,
        })
    return tasks


def compile_request_tasks_with_llm(message: str) -> list[AssistantTask]:
    """LLM 编译任务 DAG——主路径。"""
    prompt = load_prompt("task_compiler")
    result = llm_invoke_structured(
        [SystemMessage(content=prompt), HumanMessage(content=message)],
        _TaskCompilation,
    )
    if not result or result.get("action_type") == "general_chat":
        return []

    tasks: list[AssistantTask] = []
    for t in result.get("tasks", []):
        tasks.append({
            "id": t.get("id", f"task_{len(tasks)}"),
            "domain": t.get("domain", "general"),
            "title": t.get("title", "任务"),
            "depends_on": t.get("depends_on", []),
            "status": "planned",
            "reason": None,
        })
    return tasks or compile_request_tasks(message)


def schedule_task_batches(tasks: list[AssistantTask]) -> list[list[str]]:
    """按依赖关系生成执行批次。"""
    remaining = {t["id"]: set(t.get("depends_on", [])) for t in tasks}
    batches: list[list[str]] = []
    completed: set[str] = set()

    while remaining:
        ready = sorted(tid for tid, deps in remaining.items() if deps <= completed)
        if not ready:
            raise ValueError("任务依赖存在循环，无法编译执行批次。")
        batches.append(ready)
        completed.update(ready)
        for tid in ready:
            remaining.pop(tid)
    return batches


def _mail_depends_on_calendar(message: str, domains: list[str]) -> bool:
    lowered = message.lower()
    return "mail" in domains and "calendar" in domains and any(
        kw in lowered for kw in DEPENDENCY_KEYWORDS
    )


def _clean_contact_name(raw_name: str) -> str:
    cleaned = raw_name.strip()
    for suffix in ("邮件", "日程", "会议", "项目"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
    return cleaned.strip()
