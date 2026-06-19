"""Agent 工具函数——封装所有 Gmail、Calendar、用户偏好操作。

关键设计：
- 所有工具通过全局 _ctx_* 变量获取依赖，不在闭包中捕获（避免图编译时捕获 None）
- _run_async 用线程池执行异步协程，兼容 FastAPI 的正在运行的事件循环
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool
from sqlalchemy import text

BEIJING_TZ = dt_timezone(timedelta(hours=8))
EMAIL_IN_TEXT_PATTERN = re.compile(r"[^@\s,;，；<>（）()]+@[^@\s,;，；<>（）()]+\.[^@\s,;，；<>（）()]+")

# ═══════════════════════════════════════════════════════════════════════
# 全局依赖（由 runner 在每个请求前通过 set_tool_context 设置）
# 直接存储已创建的客户端对象，避免工厂函数 + 异步包装的复杂性
# ═══════════════════════════════════════════════════════════════════════

_ctx_gmail_client: Any = None
_ctx_calendar_client: Any = None
_ctx_session: Any = None
_ctx_user: Any = None
_ctx_thread_id: str | None = None


def set_tool_context(
    *,
    thread_id: str | None = None,
    gmail_client: Any = None,
    calendar_client: Any = None,
    db_session: Any = None,
    user: Any = None,
) -> None:
    """每个请求开始时调用，注入当前用户上下文（已创建好的客户端对象）。"""
    global _ctx_thread_id, _ctx_gmail_client, _ctx_calendar_client, _ctx_session, _ctx_user
    _ctx_thread_id = thread_id
    _ctx_gmail_client = gmail_client
    _ctx_calendar_client = calendar_client
    _ctx_session = db_session
    _ctx_user = user


def _get_gmail_client() -> Any | None:
    return _ctx_gmail_client


def _get_calendar_client() -> Any | None:
    return _ctx_calendar_client


def _get_user() -> Any | None:
    return _ctx_user


def _get_session() -> Any | None:
    return _ctx_session


def _get_thread_id() -> str | None:
    return _ctx_thread_id


def _json_result(
    *,
    ok: bool,
    code: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> str:
    """把工具结果统一编码成 JSON 字符串，方便 agent 稳定读取。"""
    return json.dumps(
        {
            "ok": ok,
            "code": code,
            "message": message,
            "data": data or {},
        },
        ensure_ascii=False,
    )


def _ok(code: str, message: str, data: dict[str, Any] | None = None) -> str:
    """返回成功工具结果。"""
    return _json_result(ok=True, code=code, message=message, data=data)


def _fail(code: str, message: str, data: dict[str, Any] | None = None) -> str:
    """返回失败工具结果。"""
    return _json_result(ok=False, code=code, message=message, data=data)


def _email_addresses_to_json(addresses: list[Any]) -> list[dict[str, Any]]:
    """把 EmailAddress/CalendarAttendee 这类 Pydantic 对象转成前端可用字典。"""
    result: list[dict[str, Any]] = []
    for item in addresses:
        if hasattr(item, "model_dump"):
            result.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            result.append(item)
        else:
            result.append({"email": str(item)})
    return result


def _split_email_addresses(raw: str) -> list[str]:
    """把逗号分隔邮箱字符串清洗成列表。"""
    return [addr.strip() for addr in raw.split(",") if "@" in addr and addr.strip()]


def _split_recipient_tokens(raw: str) -> list[str]:
    """把模型传入的收件人文本拆成邮箱或联系人姓名。"""
    normalized = re.sub(r"[，；;、\n]+", ",", raw)
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _get_default_signature_content(session: Any, user: Any) -> str:
    """读取当前用户默认署名；历史数据没有默认标记时退回第一条署名。"""
    try:
        from app.services.settings import list_signatures
        sigs = _run_async(list_signatures(session, user))
        default = next((s for s in sigs if s.is_default), None) or (sigs[0] if sigs else None)
        return str(default.content).strip() if default else ""
    except Exception:
        return ""


def _resolve_contact_emails(raw: str, session: Any, user: Any) -> list[dict[str, str]]:
    """把邮箱或联系人姓名解析为邮箱字典。

    这层兜底很重要：即使模型把 `to` 参数写成“赵涛”，工具也会查询
    设置页联系人并解析出邮箱，避免再次追问用户。
    """
    tokens = _split_recipient_tokens(raw)
    if not tokens:
        return []

    contacts: list[Any] = []
    try:
        from app.services.settings import list_contacts
        contacts = _run_async(list_contacts(session, user))
    except Exception:
        contacts = []

    resolved: list[dict[str, str]] = []
    seen: set[str] = set()
    for token in tokens:
        direct_emails = EMAIL_IN_TEXT_PATTERN.findall(token)
        if direct_emails:
            for email in direct_emails:
                if email not in seen:
                    resolved.append({"email": email, "name": ""})
                    seen.add(email)
            continue

        matches = [
            c for c in contacts
            if str(c.display_name).strip() == token or token in str(c.display_name)
        ]
        if len(matches) == 1:
            email = str(matches[0].email).strip()
            if email and email not in seen:
                resolved.append({"email": email, "name": str(matches[0].display_name).strip()})
                seen.add(email)
    return resolved


def _contact_to_json(contact: Any) -> dict[str, str]:
    """把设置页联系人对象转成稳定 JSON 字典，避免工具结果暴露 ORM/Pydantic 细节。"""
    return {
        "id": str(getattr(contact, "id", "") or ""),
        "display_name": str(getattr(contact, "display_name", "") or "").strip(),
        "email": str(getattr(contact, "email", "") or "").strip(),
    }


def _resolve_contact_matches(name: str, session: Any, user: Any) -> list[Any]:
    """从设置页联系人中按姓名做宽松匹配。

    这里不是硬规则，只是“用户手动维护的联系人优先”：先精确匹配姓名，再做包含匹配。
    如果没有唯一结果，调用方会继续让模型搜索邮件历史或向用户确认。
    """
    query = name.strip()
    if not query:
        return []
    try:
        from app.services.settings import list_contacts
        contacts = _run_async(list_contacts(session, user))
    except Exception:
        return []

    exact_matches = [c for c in contacts if str(c.display_name).strip() == query]
    contains_matches = [
        c for c in contacts
        if query in str(c.display_name).strip() or str(c.display_name).strip() in query
    ]
    matches = exact_matches or contains_matches
    unique: list[Any] = []
    seen: set[str] = set()
    for contact in matches:
        marker = str(getattr(contact, "id", "") or getattr(contact, "email", "") or id(contact))
        if marker not in seen:
            unique.append(contact)
            seen.add(marker)
    return unique


def _resolve_calendar_attendees(raw: str, session: Any, user: Any) -> list[Any]:
    """把日程参会人文本解析为 CalendarAttendee 列表。

    与邮件收件人保持同一套兜底：模型传邮箱时直接使用，传联系人姓名时读取设置页联系人。
    """
    from app.schemas.calendar import CalendarAttendee

    return [
        CalendarAttendee(email=item["email"], display_name=item.get("name") or None)
        for item in _resolve_contact_emails(raw, session, user)
    ]


def _local_email_draft_from_row(row: Any) -> dict[str, Any]:
    """把本地邮件草稿查询结果转成工具可返回的稳定结构。"""
    content = json.loads(row["content_json"] or "{}")
    to_items = content.get("to") or []
    recipients: list[dict[str, str]] = []
    for item in to_items:
        if isinstance(item, dict):
            recipients.append(
                {
                    "email": str(item.get("email") or "").strip(),
                    "name": str(item.get("name") or "").strip(),
                }
            )
        else:
            recipients.append({"email": str(item).strip(), "name": ""})
    subject = str(content.get("subject") or row["title"] or "未命名邮件草稿")
    body = str(content.get("body") or "")
    preview = re.sub(r"\s+", " ", body).strip()
    return {
        "work_item_id": row["work_item_id"],
        "artifact_id": row["artifact_id"],
        "thread_id": row["thread_id"],
        "version": row["version"],
        "title": row["title"],
        "subject": subject,
        "summary": row["summary"],
        "status": row["status"],
        "maturity": row["maturity"],
        "updated_at": row["updated_at"],
        "to": recipients,
        "body": body,
        "preview": preview[:180],
    }


def _format_local_email_draft_line(index: int, draft: dict[str, Any]) -> str:
    """生成本地邮件草稿列表中的单行摘要。"""
    recipients = draft.get("to") or []
    recipient_text = ", ".join(
        item.get("email", "") for item in recipients if item.get("email")
    ) or "未填写收件人"
    return (
        f"{index}. [{draft['work_item_id']}] {draft['subject']}\n"
        f"   收件人: {recipient_text}\n"
        f"   本地 Artifact: {draft['artifact_id']} | 状态: {draft['status']} | 更新时间: {draft['updated_at']}"
    )


def _format_email_items_for_text(raw: Any) -> str:
    """把工具数据里的邮箱列表转成适合回复的短文本。"""
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


def _delete_local_work_items(session: Any, user: Any, work_item_ids: list[str]) -> int:
    """删除当前用户指定 Work Item 及其本地草稿关联数据。

    只删除 SQLite 本地数据，不调用 Gmail，也不会删除 Gmail 远端邮件或 Gmail Draft。
    """
    deleted = 0
    for work_item_id in work_item_ids:
        # 删除顺序要先清理引用 Proposal Item / Artifact 的表，避免留下孤儿记录。
        _run_async(
            session.execute(
                text(
                    """
                    DELETE FROM action_events
                    WHERE proposal_item_id IN (
                        SELECT id FROM proposal_items WHERE work_item_id = :work_item_id
                    )
                    """
                ),
                {"work_item_id": work_item_id},
            )
        )
        _run_async(
            session.execute(
                text(
                    """
                    DELETE FROM action_authorizations
                    WHERE proposal_item_id IN (
                        SELECT id FROM proposal_items WHERE work_item_id = :work_item_id
                    )
                    """
                ),
                {"work_item_id": work_item_id},
            )
        )
        _run_async(
            session.execute(
                text("DELETE FROM proposal_items WHERE work_item_id = :work_item_id"),
                {"work_item_id": work_item_id},
            )
        )
        _run_async(
            session.execute(
                text(
                    """
                    DELETE FROM field_evidence
                    WHERE artifact_id IN (
                        SELECT id FROM artifacts WHERE work_item_id = :work_item_id
                    )
                    """
                ),
                {"work_item_id": work_item_id},
            )
        )
        _run_async(
            session.execute(
                text("DELETE FROM artifacts WHERE work_item_id = :work_item_id"),
                {"work_item_id": work_item_id},
            )
        )
        result = _run_async(
            session.execute(
                text(
                    """
                    DELETE FROM work_items
                    WHERE id = :work_item_id
                      AND user_id = :user_id
                      AND work_item_type = 'email_draft'
                    """
                ),
                {"work_item_id": work_item_id, "user_id": user.user_id},
            )
        )
        deleted += int(getattr(result, "rowcount", 0) or 0)
    _run_async(
        session.execute(
            text(
                """
                DELETE FROM proposal_groups
                WHERE user_id = :user_id
                  AND id NOT IN (SELECT proposal_group_id FROM proposal_items)
                """
            ),
            {"user_id": user.user_id},
        )
    )
    _run_async(session.commit())
    return deleted


def _append_signature_once(body: str, signature: str | None) -> str:
    """把默认署名追加到正文末尾，避免重复追加同一段署名。"""
    clean_body = body.rstrip()
    clean_signature = (signature or "").strip()
    if not clean_signature:
        return clean_body
    if clean_body.endswith(clean_signature):
        return clean_body
    return f"{clean_body}\n\n{clean_signature}" if clean_body else clean_signature


def _format_email_body(body: str, signature: str | None = None) -> str:
    """按项目约定规整邮件正文格式。

    这里做确定性后处理：去掉 Markdown 表格倾向，给正文段落补两个中文空格，
    再追加默认署名。它不是文学改写，只负责基础邮件格式一致性。
    """
    raw_lines = [line.strip() for line in body.replace("\r\n", "\n").split("\n")]
    paragraphs = [line for line in raw_lines if line and not line.startswith("|")]
    if not paragraphs:
        return _append_signature_once("", signature)

    formatted: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        if index == 0 or paragraph in {"祝好", "此致", "谢谢", "Regards", "Best regards"}:
            formatted.append(paragraph)
        elif signature and paragraph.strip() == signature.strip():
            formatted.append(paragraph)
        else:
            formatted.append(f"  {paragraph}")
    return _append_signature_once("\n\n".join(formatted), signature)


def _extract_existing_signature(body: str) -> str:
    """从现有邮件正文里粗略提取最后一段署名。"""
    parts = [part.strip() for part in body.replace("\r\n", "\n").split("\n\n") if part.strip()]
    if not parts:
        return ""
    candidate = parts[-1]
    return candidate if len(candidate) <= 120 and "\n" not in candidate else ""


def _email_missing_fields(to: list[Any], subject: str, body: str) -> list[str]:
    """判断邮件草稿是否还缺少发送必填字段。"""
    missing: list[str] = []
    if not to:
        missing.append("to")
    if not subject.strip():
        missing.append("subject")
    if not body.strip():
        missing.append("body")
    return missing


def _calendar_missing_fields(payload: dict[str, Any]) -> list[str]:
    """判断日程草稿是否还缺少创建必填字段。"""
    missing: list[str] = []
    for key in ("title", "start_time", "end_time", "timezone", "calendar_id"):
        if not str(payload.get(key) or "").strip():
            missing.append(key)
    return missing


def _timezone_for_calendar(name: str) -> Any:
    """返回日程时区对象；配置异常时退回北京时间。"""
    try:
        return ZoneInfo(name or "Asia/Shanghai")
    except ZoneInfoNotFoundError:
        return BEIJING_TZ


def _normalize_calendar_datetime(value: str, timezone_name: str) -> str:
    """把 ISO 时间规范成用户时区，避免 UTC `Z` 让日历按错误日期分组。"""
    text_value = str(value or "").strip()
    if not text_value:
        return ""
    try:
        parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError:
        return text_value
    tz = _timezone_for_calendar(timezone_name)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    else:
        parsed = parsed.astimezone(tz)
    return parsed.isoformat()


def _work_item_status_from_missing(missing: list[str]) -> str:
    """根据缺失字段决定草稿成熟度。"""
    return "incomplete" if missing else "reviewable"


def _jsonable_list(items: list[Any]) -> list[dict[str, Any]]:
    """把 BusySlot / Pydantic 对象 / dict 列表统一转成 JSON 字典。"""
    result: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "model_dump"):
            result.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            result.append(item)
        else:
            result.append({"value": str(item)})
    return result


def _calendar_card_data(
    *,
    artifact_id: str,
    work_item_id: str,
    version: int,
    payload: dict[str, Any],
    missing_fields: list[str],
    warnings: list[str] | None = None,
    status: str = "draft",
    external_event_id: str | None = None,
    html_link: str | None = None,
) -> dict[str, Any]:
    """构造日程草稿工具返回数据。

    `card_type` 只作为旧客户端兼容字段保留；阶段 14 起聊天页不会渲染
    邮件/日程 DraftCard，assistant 需要用文本说明草稿内容。
    """
    conflicts = payload.get("conflict_summary") or []
    return {
        "card_type": "calendar_event_draft",
        "artifact_id": artifact_id,
        "work_item_id": work_item_id,
        "version": version,
        "status": status,
        "missing_fields": missing_fields,
        "title": payload.get("title", ""),
        "start_time": payload.get("start_time", ""),
        "end_time": payload.get("end_time", ""),
        "timezone": payload.get("timezone", "Asia/Shanghai"),
        "calendar_id": payload.get("calendar_id", "primary"),
        "organizer_email": payload.get("organizer_email", ""),
        "organizer_display_name": payload.get("organizer_display_name", ""),
        "attendees": payload.get("attendees", []),
        "location": payload.get("location", ""),
        "description": payload.get("description", ""),
        "conflict_override": bool(payload.get("conflict_override", False)),
        "conflict_summary": _jsonable_list(conflicts if isinstance(conflicts, list) else []),
        "warnings": warnings or [],
        "external_event_id": external_event_id,
        "calendar_action": payload.get("calendar_action"),
        "html_link": html_link,
    }


def _run_async(coro: Any) -> Any:
    """在独立线程的事件循环中执行异步协程。

    LangGraph ToolNode 同步调用工具函数，但我们需要的 Google API
    客户端都是 async 的。用线程池绕开 FastAPI 正在运行的事件循环。
    """
    import asyncio

    def _runner():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


# ═══════════════════════════════════════════════════════════════════════
# 工具定义（全部引用全局 _ctx_* / _get_* 函数，不捕获参数）
# ═══════════════════════════════════════════════════════════════════════

def create_tools() -> list:
    """创建工具列表。每个工具通过全局上下文获取依赖。"""
    tools: list = []

    # ── 邮件 ──────────────────────────────────────────────────────

    @tool
    def search_emails(query: str, max_results: int = 10) -> str:
        """搜索 Gmail 邮件。请将用户的中文日期表达转换为 Gmail 搜索语法：
        - "6月份" → "after:2026/5/31 before:2026/7/1"
        - "今天" → "newer_than:1d"
        - "本周" → "newer_than:7d"
        - "上周" → "older_than:7d newer_than:14d"
        完整语法：from:sender, to:recipient, subject:关键词, has:attachment, is:unread,
        newer_than:Nd, older_than:Nd, after:YYYY/MM/DD, before:YYYY/MM/DD。

        Args:
            query: Gmail 搜索查询字符串（务必使用英文 Gmail 语法）
            max_results: 最大返回数量
        """
        client = _get_gmail_client()
        if not client:
            return _fail("gmail_not_connected", "Gmail 未连接，无法搜索邮件。")
        try:
            result = _run_async(client.search_messages(query=query, max_results=max_results))
            if not result.messages:
                return _ok(
                    "gmail_search_empty",
                    f"未找到匹配「{query}」的邮件。",
                    {"query": query, "messages": []},
                )
            lines = [f"找到 {len(result.messages)} 封邮件："]
            messages = []
            for i, msg in enumerate(result.messages[:max_results]):
                subject = str(msg.subject or "无主题")
                sender = str(msg.from_email or "未知")
                date = str(msg.date or "")
                snippet = str(msg.snippet or "")[:120]
                thread_id = str(getattr(msg, "thread_id", "") or "")
                messages.append(
                    {
                        "id": str(msg.id),
                        "thread_id": thread_id,
                        "subject": subject,
                        "from_email": sender,
                        "date": date,
                        "snippet": snippet,
                    }
                )
                lines.append(f"\n{i+1}. [{msg.id}] **{subject}**")
                lines.append(f"   发件人: {sender} | 日期: {date}")
                if snippet:
                    lines.append(f"   摘要: {snippet}")
            return _ok(
                "gmail_search_succeeded",
                "\n".join(lines),
                {"query": query, "messages": messages},
            )
        except Exception as e:
            return _fail("gmail_search_failed", f"搜索邮件失败：{e}")

    tools.append(search_emails)

    @tool
    def read_email(message_id: str) -> str:
        """读取指定 Gmail 邮件的完整内容。

        Args:
            message_id: Gmail 邮件 ID
        """
        client = _get_gmail_client()
        if not client:
            return _fail("gmail_not_connected", "Gmail 未连接。")
        try:
            detail = _run_async(client.get_message(message_id))
            lines = [
                f"📧 **{detail.subject or '无主题'}**",
                f"发件人: {detail.from_email}",
                f"收件人: {', '.join(detail.to) if detail.to else '未知'}",
                f"日期: {detail.date}",
                f"抄送: {', '.join(detail.cc) if detail.cc else '无'}",
                "",
                detail.body.text if detail.body else "(无正文)",
            ]
            return _ok(
                "gmail_message_read",
                "\n".join(lines),
                {
                    "id": detail.id,
                    "thread_id": detail.thread_id,
                    "subject": detail.subject,
                    "from_email": detail.from_email,
                    "to": detail.to,
                    "cc": detail.cc,
                    "date": detail.date,
                    "body": detail.body.text if detail.body else "",
                },
            )
        except Exception as e:
            return _fail("gmail_read_failed", f"读取邮件失败：{e}")

    tools.append(read_email)

    @tool
    def create_email_draft(to: str = "", subject: str = "", body: str = "") -> str:
        """创建新的本地邮件草稿（不发送）。

        只有用户明确开始一封新邮件时才调用。如果当前会话已经有
        active_email_draft，用户只是补充或修改字段，应调用 update_email_draft。
        允许字段暂时不完整，缺失字段会显示在卡片上等待用户补充。

        Args:
            to: 收件人邮箱（多个用逗号分隔，可为空）
            subject: 邮件主题（可为空）
            body: 邮件正文（可为空）
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("google_not_connected", "请先连接 Google 账号。")
        try:
            from app.services.gmail import EmailDraftPayload, EmailAddress, _create_email_artifact

            sig_content = _get_default_signature_content(session, user)
            resolved_to = _resolve_contact_emails(to, session, user)
            to_list = [
                EmailAddress(email=item["email"], name=item.get("name") or None)
                for item in resolved_to
            ]
            final_body = _format_email_body(body, sig_content)
            final_subject = subject.strip()
            missing_fields = _email_missing_fields(to_list, final_subject, final_body)

            payload = EmailDraftPayload(
                draft_type="new_email",
                sender_email=user.email,
                to=to_list, cc=[], bcc=[],
                subject=final_subject,
                body=final_body,
                signature_policy="append_signature" if sig_content else "no_signature",
            )
            result = _run_async(
                _create_email_artifact(
                    session,
                    user,
                    _get_thread_id(),
                    final_subject or "未命名邮件草稿",
                    payload,
                )
            )
            if missing_fields:
                _run_async(
                    session.execute(
                        text(
                            """
                            UPDATE work_items
                            SET maturity = 'incomplete', updated_at = :updated_at
                            WHERE id = :work_item_id
                            """
                        ),
                        {
                            "updated_at": datetime.now(BEIJING_TZ).isoformat(),
                            "work_item_id": result.work_item_id,
                        },
                    )
                )
                _run_async(session.commit())
            preview = final_body[:150] + "..." if len(final_body) > 150 else final_body
            return _ok(
                "email_draft_created",
                (
                    f"邮件草稿已创建。草稿 ID: {result.artifact_id}。"
                    f"{'还缺少：' + ', '.join(missing_fields) if missing_fields else '字段已完整，可确认发送。'}"
                ),
                {
                    "card_type": "email_draft",
                    "artifact_id": result.artifact_id,
                    "work_item_id": result.work_item_id,
                    "thread_id": result.thread_id,
                    "version": result.version,
                    "status": "draft",
                    "missing_fields": missing_fields,
                    "to": _email_addresses_to_json(payload.to),
                    "cc": _email_addresses_to_json(payload.cc),
                    "bcc": _email_addresses_to_json(payload.bcc),
                    "subject": payload.subject,
                    "body": payload.body,
                    "signature": sig_content or "",
                    "preview": preview,
                },
            )
        except Exception as e:
            return _fail("email_draft_create_failed", f"创建草稿失败：{e}")

    tools.append(create_email_draft)

    @tool
    def update_email_draft(
        artifact_id: str = "",
        to: str = "",
        subject: str = "",
        body: str = "",
    ) -> str:
        """修改已有本地邮件草稿，并返回更新后的聊天卡片数据。

        Args:
            artifact_id: 本地邮件 Artifact ID；为空时使用当前会话 active_email_draft
            to: 新收件人邮箱，多个用逗号分隔；为空则不修改
            subject: 新主题；为空则不修改
            body: 新正文；为空则不修改
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("google_not_connected", "请先连接 Google 账号。")
        try:
            from app.services.gmail import EmailAddress, EmailDraftPayload
            from app.services.draft_context import load_active_artifact

            if not artifact_id:
                active = _run_async(
                    load_active_artifact(session, user, _get_thread_id(), "email_draft")
                )
                artifact_id = str((active or {}).get("artifact_id") or "")
            if not artifact_id:
                return _fail("email_draft_missing", "没有找到当前可修改的邮件草稿。")

            row_result = _run_async(
                session.execute(
                    text(
                        """
                        SELECT a.id, a.work_item_id, a.version, a.content_json
                        FROM artifacts a
                        JOIN work_items wi ON wi.id = a.work_item_id
                        WHERE a.id = :artifact_id
                          AND wi.user_id = :user_id
                          AND a.artifact_type = 'email_draft'
                        """
                    ),
                    {"artifact_id": artifact_id, "user_id": user.user_id},
                )
            )
            row = row_result.mappings().first()
            if not row:
                return _fail("email_draft_not_found", f"未找到邮件草稿：{artifact_id}")

            payload = EmailDraftPayload.model_validate(json.loads(row["content_json"] or "{}"))
            if to:
                resolved_to = _resolve_contact_emails(to, session, user)
                payload.to = [
                    EmailAddress(email=item["email"], name=item.get("name") or None)
                    for item in resolved_to
                ]
            if subject:
                payload.subject = subject
            if body:
                signature = _get_default_signature_content(session, user)
                payload.body = _format_email_body(body, signature)
                payload.signature_policy = "append_signature" if signature else "no_signature"
            missing_fields = _email_missing_fields(payload.to, payload.subject, payload.body)

            new_version = int(row["version"] or 1) + 1
            timestamp = datetime.now(BEIJING_TZ).isoformat()
            _run_async(
                session.execute(
                    text(
                        """
                        UPDATE artifacts
                        SET version = :version, content_json = :content_json, updated_at = :updated_at
                        WHERE id = :artifact_id
                        """
                    ),
                    {
                        "version": new_version,
                        "content_json": payload.model_dump_json(),
                        "updated_at": timestamp,
                        "artifact_id": artifact_id,
                    },
                )
            )
            _run_async(
                session.execute(
                    text(
                        """
                        UPDATE work_items
                        SET title = :title, summary = :summary, updated_at = :updated_at
                        WHERE id = :work_item_id
                        """
                    ),
                    {
                        "title": payload.subject,
                        "summary": payload.body[:200],
                        "updated_at": timestamp,
                        "work_item_id": row["work_item_id"],
                    },
                )
            )
            _run_async(session.commit())
            maturity = _work_item_status_from_missing(missing_fields)
            _run_async(
                session.execute(
                    text(
                        """
                        UPDATE work_items
                        SET maturity = :maturity, updated_at = :updated_at
                        WHERE id = :work_item_id
                        """
                    ),
                    {
                        "maturity": maturity,
                        "updated_at": timestamp,
                        "work_item_id": row["work_item_id"],
                    },
                )
            )
            _run_async(session.commit())
            return _ok(
                "email_draft_updated",
                f"邮件草稿已更新。草稿 ID: {artifact_id}。",
                {
                    "card_type": "email_draft",
                    "artifact_id": artifact_id,
                    "work_item_id": row["work_item_id"],
                    "version": new_version,
                    "status": "draft",
                    "missing_fields": missing_fields,
                    "to": _email_addresses_to_json(payload.to),
                    "cc": _email_addresses_to_json(payload.cc),
                    "bcc": _email_addresses_to_json(payload.bcc),
                    "subject": payload.subject,
                    "body": payload.body,
                    "signature": _extract_existing_signature(payload.body),
                },
            )
        except Exception as e:
            return _fail("email_draft_update_failed", f"更新邮件草稿失败：{e}")

    tools.append(update_email_draft)

    @tool
    def send_email_draft(artifact_id: str = "") -> str:
        """发送当前本地邮件草稿。

        只能在用户明确说“确认发送”后调用。工具内部会走
        Proposal -> Authorization -> Execution，不直接裸调 Gmail。

        Args:
            artifact_id: 邮件 Artifact ID；为空时使用当前会话 active_email_draft
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("google_not_connected", "请先连接 Google 账号。")
        try:
            from app.schemas.gmail import EmailDraftPayload
            from app.schemas.workflow import (
                AuthorizeProposalRequest,
                CreateProposalRequest,
                ExecuteProposalRequest,
            )
            from app.services.draft_context import (
                close_work_item,
                load_active_artifact,
                load_artifact_for_update,
            )
            from app.services.workflow import (
                authorize_proposal,
                create_proposal_from_artifact,
                execute_authorized_proposal,
            )

            if not artifact_id:
                active = _run_async(
                    load_active_artifact(session, user, _get_thread_id(), "email_draft")
                )
                artifact_id = str((active or {}).get("artifact_id") or "")
            artifact = _run_async(
                load_artifact_for_update(session, user, artifact_id, "email_draft")
            )
            if not artifact:
                return _fail("email_draft_not_found", "没有找到可发送的邮件草稿。")

            payload = EmailDraftPayload.model_validate(artifact["content"])
            missing_fields = _email_missing_fields(payload.to, payload.subject, payload.body)
            if missing_fields:
                return _fail(
                    "email_draft_incomplete",
                    f"邮件草稿还缺少：{', '.join(missing_fields)}，不能发送。",
                    {"artifact_id": artifact_id, "missing_fields": missing_fields},
                )

            proposal = _run_async(
                create_proposal_from_artifact(
                    session,
                    user,
                    CreateProposalRequest(artifact_id=artifact_id, action_type="send_email"),
                )
            )
            authorized = _run_async(
                authorize_proposal(
                    session,
                    user,
                    proposal.id,
                    AuthorizeProposalRequest(
                        version=proposal.version,
                        fingerprint=proposal.fingerprint,
                        source="chat_confirm",
                    ),
                )
            )
            result = _run_async(
                execute_authorized_proposal(
                    session,
                    user,
                    authorized.id,
                    ExecuteProposalRequest(),
                )
            )
            if result.status in {"succeeded", "executed"}:
                _run_async(close_work_item(session, work_item_id=artifact["work_item_id"], status="sent"))
            return _ok(
                "email_draft_sent",
                "邮件已发送。",
                {
                    "card_type": "email_draft",
                    "artifact_id": artifact_id,
                    "work_item_id": artifact["work_item_id"],
                    "version": artifact["version"],
                    "status": "sent",
                    "missing_fields": [],
                    "to": _email_addresses_to_json(payload.to),
                    "cc": _email_addresses_to_json(payload.cc),
                    "bcc": _email_addresses_to_json(payload.bcc),
                    "subject": payload.subject,
                    "body": payload.body,
                    "signature": _extract_existing_signature(payload.body),
                    "external_message_id": result.external_resource_id,
                },
            )
        except Exception as e:
            return _fail("email_draft_send_failed", f"发送邮件失败：{e}")

    tools.append(send_email_draft)

    @tool
    def send_all_local_email_drafts(confirm: bool = False, thread_only: bool = True) -> str:
        """批量发送当前线程打开中的本地邮件草稿。

        这个工具用于“用户要求两封/多封/全部草稿一起发送”的确认场景。
        每封邮件仍逐封走现有 `send_email_draft` 的 Proposal -> Authorization
        -> Execution 链路，不绕过安全闭环。

        Args:
            confirm: 用户是否已经明确确认发送这些本地草稿
            thread_only: 是否只发送当前聊天线程的本地草稿
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("local_drafts_unavailable", "当前无法读取本地草稿。")
        if not confirm:
            return _fail(
                "local_email_drafts_send_confirmation_required",
                "批量发送本地邮件草稿前需要用户明确确认。",
            )
        try:
            params: dict[str, Any] = {"user_id": user.user_id}
            thread_filter = ""
            thread_id = _get_thread_id()
            if thread_only and thread_id:
                thread_filter = "AND wi.thread_id = :thread_id"
                params["thread_id"] = thread_id
            result = _run_async(
                session.execute(
                    text(
                        f"""
                        SELECT
                            wi.id AS work_item_id,
                            wi.thread_id,
                            wi.title,
                            wi.summary,
                            wi.maturity,
                            wi.status,
                            wi.updated_at,
                            a.id AS artifact_id,
                            a.version,
                            a.content_json
                        FROM work_items wi
                        JOIN artifacts a ON a.work_item_id = wi.id
                        WHERE wi.user_id = :user_id
                          AND wi.work_item_type = 'email_draft'
                          AND wi.status = 'open'
                          AND a.artifact_type = 'email_draft'
                          {thread_filter}
                        ORDER BY wi.updated_at DESC
                        """
                    ),
                    params,
                )
            )
            drafts = [_local_email_draft_from_row(row) for row in result.mappings()]
            if not drafts:
                return _fail("local_email_drafts_empty", "没有找到可发送的本地邮件草稿。")

            # 如果同一线程里残留了“合并收件人草稿”和“单人分别草稿”，优先发送单人草稿。
            # 这能避免用户要求“分别发送”后，旧的合并草稿也被批量发出。
            single_recipient_drafts = [
                draft for draft in drafts
                if len([item for item in draft.get("to", []) if item.get("email")]) == 1
            ]
            selected_drafts = single_recipient_drafts if len(single_recipient_drafts) >= 2 else drafts

            successes: list[dict[str, Any]] = []
            failures: list[dict[str, Any]] = []
            for draft in selected_drafts:
                result_text = str(send_email_draft.invoke({"artifact_id": draft["artifact_id"]}))
                parsed = json.loads(result_text)
                if parsed.get("ok"):
                    successes.append(parsed.get("data") or {})
                else:
                    failures.append(
                        {
                            "draft": draft,
                            "code": parsed.get("code"),
                            "message": parsed.get("message"),
                        }
                    )

            lines = [f"已发送 {len(successes)} 封本地邮件草稿。"]
            if successes:
                lines.append("")
                lines.append("发送成功：")
                for index, item in enumerate(successes, 1):
                    recipients = _format_email_items_for_text(item.get("to")) or "未返回收件人"
                    lines.append(f"{index}. {recipients} - {item.get('subject') or '无主题'}")
            if failures:
                lines.append("")
                lines.append(f"发送失败 {len(failures)} 封：")
                for index, item in enumerate(failures, 1):
                    draft = item.get("draft") or {}
                    lines.append(
                        f"{index}. {draft.get('subject') or '无主题'} - {item.get('message') or item.get('code')}"
                    )
            return _ok(
                "local_email_drafts_sent",
                "\n".join(lines),
                {
                    "sent_count": len(successes),
                    "failed_count": len(failures),
                    "sent": successes,
                    "failed": failures,
                    "selected_artifact_ids": [draft["artifact_id"] for draft in selected_drafts],
                },
            )
        except Exception as e:
            return _fail("local_email_drafts_send_failed", f"批量发送本地邮件草稿失败：{e}")

    tools.append(send_all_local_email_drafts)

    @tool
    def list_local_email_drafts(include_closed: bool = False, limit: int = 20) -> str:
        """列出本地邮件草稿。

        本地草稿来自 SQLite Work Item / Artifact，不等同于 Gmail 草稿箱。

        Args:
            include_closed: 是否包含已发送、已删除等关闭状态的历史草稿
            limit: 最多返回多少条
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("local_drafts_unavailable", "当前无法读取本地草稿。")
        safe_limit = max(1, min(int(limit or 20), 50))
        status_filter = "" if include_closed else "AND wi.status = 'open'"
        try:
            result = _run_async(
                session.execute(
                    text(
                        f"""
                        SELECT
                            wi.id AS work_item_id,
                            wi.thread_id,
                            wi.title,
                            wi.summary,
                            wi.maturity,
                            wi.status,
                            wi.updated_at,
                            a.id AS artifact_id,
                            a.version,
                            a.content_json
                        FROM work_items wi
                        JOIN artifacts a ON a.work_item_id = wi.id
                        WHERE wi.user_id = :user_id
                          AND wi.work_item_type = 'email_draft'
                          AND a.artifact_type = 'email_draft'
                          {status_filter}
                        ORDER BY wi.updated_at DESC
                        LIMIT :limit
                        """
                    ),
                    {"user_id": user.user_id, "limit": safe_limit},
                )
            )
            drafts = [_local_email_draft_from_row(row) for row in result.mappings()]
            if not drafts:
                scope = "本地历史邮件草稿" if include_closed else "打开中的本地邮件草稿"
                return _ok("local_email_drafts_empty", f"没有找到{scope}。", {"drafts": []})
            lines = [f"找到 {len(drafts)} 封本地邮件草稿："]
            lines.extend(_format_local_email_draft_line(i, draft) for i, draft in enumerate(drafts, 1))
            return _ok(
                "local_email_drafts_listed",
                "\n\n".join(lines),
                {"drafts": drafts, "include_closed": include_closed},
            )
        except Exception as e:
            return _fail("local_email_drafts_list_failed", f"读取本地邮件草稿失败：{e}")

    tools.append(list_local_email_drafts)

    @tool
    def read_local_email_draft(draft_id: str = "") -> str:
        """读取单封本地邮件草稿详情。

        Args:
            draft_id: 本地 work_item_id 或 artifact_id；为空时读取当前会话 active_email_draft
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("local_drafts_unavailable", "当前无法读取本地草稿。")
        try:
            from app.services.draft_context import load_active_artifact

            target_id = draft_id.strip()
            if not target_id:
                active = _run_async(
                    load_active_artifact(session, user, _get_thread_id(), "email_draft")
                )
                target_id = str((active or {}).get("artifact_id") or "")
            if not target_id:
                return _fail("local_email_draft_missing", "没有找到当前会话的本地邮件草稿。")

            result = _run_async(
                session.execute(
                    text(
                        """
                        SELECT
                            wi.id AS work_item_id,
                            wi.thread_id,
                            wi.title,
                            wi.summary,
                            wi.maturity,
                            wi.status,
                            wi.updated_at,
                            a.id AS artifact_id,
                            a.version,
                            a.content_json
                        FROM work_items wi
                        JOIN artifacts a ON a.work_item_id = wi.id
                        WHERE wi.user_id = :user_id
                          AND wi.work_item_type = 'email_draft'
                          AND a.artifact_type = 'email_draft'
                          AND (wi.id = :draft_id OR a.id = :draft_id)
                        ORDER BY a.updated_at DESC
                        LIMIT 1
                        """
                    ),
                    {"user_id": user.user_id, "draft_id": target_id},
                )
            )
            row = result.mappings().first()
            if not row:
                return _fail("local_email_draft_not_found", f"没有找到本地邮件草稿：{target_id}")
            draft = _local_email_draft_from_row(row)
            recipients = ", ".join(
                item.get("email", "") for item in draft["to"] if item.get("email")
            ) or "未填写"
            message = (
                f"本地邮件草稿：{draft['subject']}\n\n"
                f"- Work Item: {draft['work_item_id']}\n"
                f"- Artifact: {draft['artifact_id']}\n"
                f"- 状态: {draft['status']}\n"
                f"- 收件人: {recipients}\n"
                f"- 正文:\n{draft['body'] or '未填写正文'}"
            )
            return _ok("local_email_draft_read", message, {"draft": draft})
        except Exception as e:
            return _fail("local_email_draft_read_failed", f"读取本地邮件草稿失败：{e}")

    tools.append(read_local_email_draft)

    @tool
    def delete_local_email_draft(draft_id: str = "", confirm: bool = False) -> str:
        """删除单封本地邮件草稿。

        只能在用户明确确认删除后把 confirm 设为 true。这个工具只删本地 SQLite
        草稿，不会删除 Gmail 邮件，也不会删除 Gmail Draft。

        Args:
            draft_id: 本地 work_item_id 或 artifact_id；为空时使用当前会话 active_email_draft
            confirm: 用户是否已经明确确认删除
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("local_drafts_unavailable", "当前无法删除本地草稿。")
        try:
            from app.services.draft_context import load_active_artifact

            target_id = draft_id.strip()
            if not target_id:
                active = _run_async(
                    load_active_artifact(session, user, _get_thread_id(), "email_draft")
                )
                target_id = str((active or {}).get("artifact_id") or "")
            if not target_id:
                return _fail("local_email_draft_missing", "没有找到当前会话的本地邮件草稿。")

            result = _run_async(
                session.execute(
                    text(
                        """
                        SELECT
                            wi.id AS work_item_id,
                            wi.thread_id,
                            wi.title,
                            wi.summary,
                            wi.maturity,
                            wi.status,
                            wi.updated_at,
                            a.id AS artifact_id,
                            a.version,
                            a.content_json
                        FROM work_items wi
                        JOIN artifacts a ON a.work_item_id = wi.id
                        WHERE wi.user_id = :user_id
                          AND wi.work_item_type = 'email_draft'
                          AND a.artifact_type = 'email_draft'
                          AND wi.status = 'open'
                          AND (wi.id = :draft_id OR a.id = :draft_id)
                        ORDER BY a.updated_at DESC
                        LIMIT 1
                        """
                    ),
                    {"user_id": user.user_id, "draft_id": target_id},
                )
            )
            row = result.mappings().first()
            if not row:
                return _fail("local_email_draft_not_found", f"没有找到可删除的本地邮件草稿：{target_id}")
            draft = _local_email_draft_from_row(row)
            if not confirm:
                return _fail(
                    "local_email_draft_delete_confirmation_required",
                    f"将删除本地邮件草稿「{draft['subject']}」。如确认删除，请回复“确认删除这封本地草稿”。",
                    {"draft": draft},
                )

            deleted = _delete_local_work_items(session, user, [draft["work_item_id"]])
            return _ok(
                "local_email_draft_deleted",
                f"已删除本地邮件草稿「{draft['subject']}」。",
                {"deleted_count": deleted, "draft": draft},
            )
        except Exception as e:
            return _fail("local_email_draft_delete_failed", f"删除本地邮件草稿失败：{e}")

    tools.append(delete_local_email_draft)

    @tool
    def delete_all_local_email_drafts(confirm: bool = False) -> str:
        """删除所有打开中的本地邮件草稿。

        只能在用户明确确认清空本地草稿后把 confirm 设为 true。这个工具不影响
        Gmail 远端草稿箱。

        Args:
            confirm: 用户是否已经明确确认删除所有本地邮件草稿
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("local_drafts_unavailable", "当前无法删除本地草稿。")
        try:
            result = _run_async(
                session.execute(
                    text(
                        """
                        SELECT
                            wi.id AS work_item_id,
                            wi.thread_id,
                            wi.title,
                            wi.summary,
                            wi.maturity,
                            wi.status,
                            wi.updated_at,
                            a.id AS artifact_id,
                            a.version,
                            a.content_json
                        FROM work_items wi
                        JOIN artifacts a ON a.work_item_id = wi.id
                        WHERE wi.user_id = :user_id
                          AND wi.work_item_type = 'email_draft'
                          AND a.artifact_type = 'email_draft'
                          AND wi.status = 'open'
                        ORDER BY wi.updated_at DESC
                        """
                    ),
                    {"user_id": user.user_id},
                )
            )
            drafts = [_local_email_draft_from_row(row) for row in result.mappings()]
            if not drafts:
                return _ok("local_email_drafts_empty", "没有打开中的本地邮件草稿可删除。", {"drafts": []})
            if not confirm:
                lines = [f"将删除 {len(drafts)} 封本地邮件草稿："]
                lines.extend(_format_local_email_draft_line(i, draft) for i, draft in enumerate(drafts, 1))
                lines.append("如确认清空，请回复“确认删除所有本地邮件草稿”。")
                return _fail(
                    "local_email_drafts_delete_confirmation_required",
                    "\n\n".join(lines),
                    {"drafts": drafts, "deleted_count": 0},
                )

            deleted = _delete_local_work_items(
                session,
                user,
                [str(draft["work_item_id"]) for draft in drafts],
            )
            return _ok(
                "local_email_drafts_deleted",
                f"已删除 {deleted} 封本地邮件草稿。",
                {"deleted_count": deleted, "drafts": drafts},
            )
        except Exception as e:
            return _fail("local_email_drafts_delete_failed", f"删除本地邮件草稿失败：{e}")

    tools.append(delete_all_local_email_drafts)

    @tool
    def delete_email(message_id: str) -> str:
        """将 Gmail 邮件移至垃圾箱（30天内可恢复）。

        Args:
            message_id: 要删除的邮件 ID
        """
        client = _get_gmail_client()
        if not client:
            return _fail("gmail_not_connected", "Gmail 未连接。")
        try:
            _run_async(client.trash_message(message_id))
            return _ok(
                "gmail_message_deleted",
                f"邮件 {message_id} 已移至垃圾箱。",
                {"message_id": message_id},
            )
        except Exception as e:
            return _fail("gmail_delete_failed", f"删除邮件失败：{e}")

    tools.append(delete_email)

    # ── 日程 ──────────────────────────────────────────────────────

    @tool
    def list_calendar_events(time_min: str = "", time_max: str = "") -> str:
        """列出 Google Calendar 日程。默认从现在起未来 7 天。

        Args:
            time_min: 开始时间（ISO 8601），默认当前
            time_max: 结束时间（ISO 8601），默认 7 天后
        """
        client = _get_calendar_client()
        if not client:
            return _fail("calendar_not_connected", "Google Calendar 未连接。")
        try:
            now = datetime.now(BEIJING_TZ)
            if not time_min:
                time_min = now.isoformat()
            if not time_max:
                time_max = (now + timedelta(days=7)).isoformat()

            result = _run_async(client.list_events(
                calendar_id="primary", time_min=time_min, time_max=time_max, max_results=20,
            ))
            if not result.events:
                return _ok(
                    "calendar_events_empty",
                    "该时间段内没有日程。",
                    {"time_min": time_min, "time_max": time_max, "events": []},
                )
            lines = ["📅 **日程列表**："]
            events = []
            for i, ev in enumerate(result.events[:15]):
                title = ev.summary or "无标题"
                start = ev.start.date_time if ev.start else "未知"
                end = ev.end.date_time if ev.end else ""
                loc = f" 📍{ev.location}" if ev.location else ""
                att = ""
                if ev.attendees:
                    att = f" 👥{', '.join(a.email for a in ev.attendees[:3])}"
                events.append(
                    {
                        "id": ev.id,
                        "title": title,
                        "start_time": start,
                        "end_time": end,
                        "location": ev.location,
                        "attendees": _email_addresses_to_json(ev.attendees),
                    }
                )
                lines.append(f"{i+1}. [{ev.id}] **{title}**\n   {start} → {end}{loc}{att}")
            return _ok(
                "calendar_events_listed",
                "\n".join(lines),
                {"time_min": time_min, "time_max": time_max, "events": events},
            )
        except Exception as e:
            return _fail("calendar_list_failed", f"读取日程失败：{e}")

    tools.append(list_calendar_events)

    @tool
    def create_calendar_event_draft(
        title: str = "",
        start_time: str = "",
        end_time: str = "",
        attendees: str = "",
        description: str = "",
        location: str = "",
        conflict_override: bool = False,
    ) -> str:
        """创建新的本地日程草稿，不直接写 Google Calendar。

        Args:
            title: 日程标题，可暂时为空
            start_time: 开始时间（ISO 8601），可暂时为空
            end_time: 结束时间（ISO 8601），可暂时为空
            attendees: 参会人邮箱（逗号分隔）
            description: 描述
            location: 地点
            conflict_override: 用户是否明确要求忽略冲突继续创建
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("google_not_connected", "请先连接 Google 账号。")
        try:
            from app.schemas.calendar import CalendarEventPayload, FreebusyRequest
            from app.services.calendar import _create_calendar_artifact, validate_attendee_emails
            from app.services.settings import get_user_profile

            profile = _run_async(get_user_profile(session, user))
            timezone = profile.timezone or "Asia/Shanghai"
            calendar_id = profile.default_calendar_id or "primary"
            organizer_display_name = (
                _get_default_signature_content(session, user)
                or profile.display_name
                or user.email
            )
            attendee_list = _resolve_calendar_attendees(attendees, session, user)
            validate_attendee_emails(attendee_list)

            final_start = _normalize_calendar_datetime(start_time, timezone)
            final_end = _normalize_calendar_datetime(end_time, timezone)
            if final_start and not final_end and profile.default_meeting_duration_minutes:
                final_end = (
                    datetime.fromisoformat(final_start.replace("Z", "+00:00"))
                    + timedelta(minutes=profile.default_meeting_duration_minutes)
                ).isoformat()

            conflict_summary: list[Any] = []
            warnings: list[str] = []
            client = _get_calendar_client()
            if client and final_start and final_end:
                freebusy = _run_async(
                    client.query_freebusy(
                        FreebusyRequest(
                            time_min=final_start,
                            time_max=final_end,
                            timezone=timezone,
                            calendar_ids=[calendar_id],
                        )
                    )
                )
                conflict_summary = list(freebusy.conflicts)
                warnings = list(freebusy.warnings)

            content = CalendarEventPayload(
                title=title.strip(),
                start_time=final_start,
                end_time=final_end,
                timezone=timezone,
                calendar_id=calendar_id,
                organizer_email=user.email,
                attendees=attendee_list,
                location=location or "",
                description=description or "",
                video_conference=False,
                recurrence_rule=None,
                reminders=[],
                conflict_override=conflict_override,
                conflict_summary=conflict_summary,
            )
            missing_fields = _calendar_missing_fields(content.model_dump(mode="json"))
            maturity = _work_item_status_from_missing(missing_fields)
            result = _run_async(
                _create_calendar_artifact(session, user, _get_thread_id(), content, maturity)
            )
            display_payload = content.model_dump(mode="json")
            display_payload["organizer_display_name"] = organizer_display_name
            return _ok(
                "calendar_event_draft_created",
                (
                    f"日程草稿已创建。草稿 ID: {result.artifact_id}。"
                    f"{'还缺少：' + ', '.join(missing_fields) if missing_fields else '字段已完整，可确认创建。'}"
                ),
                _calendar_card_data(
                    artifact_id=result.artifact_id,
                    work_item_id=result.work_item_id,
                    version=result.version,
                    payload=display_payload,
                    missing_fields=missing_fields,
                    warnings=warnings,
                ),
            )
        except Exception as e:
            return _fail("calendar_event_draft_create_failed", f"创建日程草稿失败：{e}")

    tools.append(create_calendar_event_draft)

    @tool
    def update_calendar_event_draft(
        artifact_id: str = "",
        title: str = "",
        start_time: str = "",
        end_time: str = "",
        attendees: str = "",
        description: str = "",
        location: str = "",
        conflict_override: bool = False,
    ) -> str:
        """修改已有本地日程草稿，不直接写 Google Calendar。

        Args:
            artifact_id: 本地日程 Artifact ID；为空时使用当前 active_calendar_draft
            title: 新标题
            start_time: 新开始时间
            end_time: 新结束时间
            attendees: 新参会人邮箱，逗号分隔；为空则不修改
            description: 新描述
            location: 新地点
            conflict_override: 用户是否明确要求忽略冲突继续创建
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("google_not_connected", "请先连接 Google 账号。")
        try:
            from app.schemas.calendar import FreebusyRequest
            from app.services.calendar import validate_attendee_emails
            from app.services.draft_context import (
                load_active_artifact,
                load_artifact_for_update,
                update_artifact_content,
            )

            if not artifact_id:
                active = _run_async(
                    load_active_artifact(session, user, _get_thread_id(), "calendar_event_draft")
                )
                artifact_id = str((active or {}).get("artifact_id") or "")
            artifact = _run_async(
                load_artifact_for_update(session, user, artifact_id, "calendar_event_draft")
            )
            if not artifact:
                return _fail("calendar_event_draft_not_found", "没有找到可修改的日程草稿。")

            content = dict(artifact["content"])
            if title:
                content["title"] = title.strip()
            if start_time:
                content["start_time"] = start_time.strip()
            if end_time:
                content["end_time"] = end_time.strip()
            if attendees:
                attendee_list = _resolve_calendar_attendees(attendees, session, user)
                validate_attendee_emails(attendee_list)
                content["attendees"] = [item.model_dump(mode="json") for item in attendee_list]
            if description:
                content["description"] = description
            if location:
                content["location"] = location
            if conflict_override:
                content["conflict_override"] = True

            conflict_summary: list[Any] = []
            warnings: list[str] = []
            client = _get_calendar_client()
            if client and content.get("start_time") and content.get("end_time"):
                freebusy = _run_async(
                    client.query_freebusy(
                        FreebusyRequest(
                            time_min=str(content["start_time"]),
                            time_max=str(content["end_time"]),
                            timezone=str(content.get("timezone") or "Asia/Shanghai"),
                            calendar_ids=[str(content.get("calendar_id") or "primary")],
                        )
                    )
                )
                conflict_summary = list(freebusy.conflicts)
                warnings = list(freebusy.warnings)
                content["conflict_summary"] = [
                    item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                    for item in conflict_summary
                ]

            missing_fields = _calendar_missing_fields(content)
            maturity = _work_item_status_from_missing(missing_fields)
            next_version = _run_async(
                update_artifact_content(
                    session,
                    artifact_id=artifact_id,
                    work_item_id=artifact["work_item_id"],
                    version=artifact["version"],
                    content=content,
                    title=str(content.get("title") or "未命名日程草稿"),
                    summary=f"{content.get('start_time', '')} - {content.get('end_time', '')}",
                    maturity=maturity,
                )
            )
            return _ok(
                "calendar_event_draft_updated",
                f"日程草稿已更新。草稿 ID: {artifact_id}。",
                _calendar_card_data(
                    artifact_id=artifact_id,
                    work_item_id=artifact["work_item_id"],
                    version=next_version,
                    payload=content,
                    missing_fields=missing_fields,
                    warnings=warnings,
                ),
            )
        except Exception as e:
            return _fail("calendar_event_draft_update_failed", f"更新日程草稿失败：{e}")

    tools.append(update_calendar_event_draft)

    @tool
    def create_calendar_update_draft(
        event_id: str,
        calendar_id: str = "primary",
        title: str = "",
        start_time: str = "",
        end_time: str = "",
        attendees: str = "",
        description: str = "",
        location: str = "",
        conflict_override: bool = False,
    ) -> str:
        """为已有 Google Calendar 日程创建本地更新草稿。

        这个工具不会直接更新 Google Calendar。它会读取旧事件，把用户要修改
        的字段合并成本地 `calendar_event_draft`，等待用户确认后执行。

        Args:
            event_id: 要更新的 Google Calendar Event ID
            calendar_id: 事件所在日历
            title: 新标题；为空则沿用旧标题
            start_time: 新开始时间；为空则沿用旧时间
            end_time: 新结束时间；为空则沿用旧时间
            attendees: 新参会人邮箱，逗号分隔；为空则沿用旧参会人
            description: 新描述；为空则沿用旧描述
            location: 新地点；为空则沿用旧地点
            conflict_override: 用户是否明确要求忽略冲突继续更新
        """
        client = _get_calendar_client()
        user = _get_user()
        session = _get_session()
        if not client or not user or not session:
            return _fail("calendar_not_connected", "Google Calendar 未连接。")
        try:
            from app.schemas.calendar import CalendarEventPayload, FreebusyRequest
            from app.services.calendar import _create_calendar_artifact, validate_attendee_emails

            old_event = _run_async(client.get_event_for_update(calendar_id, event_id))
            old_start = old_event.start.date_time if old_event.start else ""
            old_end = old_event.end.date_time if old_event.end else ""
            attendee_list = old_event.attendees or []
            if attendees:
                attendee_list = _resolve_calendar_attendees(attendees, session, user)
                validate_attendee_emails(attendee_list)

            final_start = start_time or old_start
            final_end = end_time or old_end
            timezone = old_event.start.timezone if old_event.start else "Asia/Shanghai"
            conflict_summary: list[Any] = []
            warnings: list[str] = []
            if final_start and final_end:
                freebusy = _run_async(
                    client.query_freebusy(
                        FreebusyRequest(
                            time_min=final_start,
                            time_max=final_end,
                            timezone=timezone,
                            calendar_ids=[calendar_id],
                        )
                    )
                )
                conflict_summary = list(freebusy.conflicts)
                warnings = list(freebusy.warnings)

            payload = CalendarEventPayload(
                title=title or (old_event.summary or ""),
                start_time=final_start,
                end_time=final_end,
                timezone=timezone,
                calendar_id=calendar_id,
                organizer_email=old_event.raw.get("organizer", {}).get("email", user.email),
                attendees=attendee_list,
                location=location or (old_event.location or ""),
                description=description or (old_event.description or ""),
                video_conference=False,
                recurrence_rule=None,
                reminders=[],
                conflict_override=conflict_override,
                conflict_summary=conflict_summary,
            )
            content = payload.model_dump(mode="json")
            content["external_event_id"] = event_id
            content["calendar_action"] = "update_calendar_event"
            missing_fields = _calendar_missing_fields(content)
            maturity = _work_item_status_from_missing(missing_fields)
            result = _run_async(
                _create_calendar_artifact(session, user, _get_thread_id(), payload, maturity)
            )
            _run_async(
                session.execute(
                    text(
                        """
                        UPDATE artifacts
                        SET content_json = :content_json, updated_at = :updated_at
                        WHERE id = :artifact_id
                        """
                    ),
                    {
                        "content_json": json.dumps(content, ensure_ascii=False, sort_keys=True),
                        "updated_at": datetime.now(BEIJING_TZ).isoformat(),
                        "artifact_id": result.artifact_id,
                    },
                )
            )
            _run_async(session.commit())
            return _ok(
                "calendar_event_update_draft_created",
                f"日程更新草稿已创建。草稿 ID: {result.artifact_id}。",
                _calendar_card_data(
                    artifact_id=result.artifact_id,
                    work_item_id=result.work_item_id,
                    version=result.version,
                    payload=content,
                    missing_fields=missing_fields,
                    warnings=warnings,
                ),
            )
        except Exception as e:
            return _fail("calendar_event_update_draft_create_failed", f"创建日程更新草稿失败：{e}")

    tools.append(create_calendar_update_draft)

    @tool
    def execute_calendar_event_draft(artifact_id: str = "", conflict_override: bool = False) -> str:
        """确认创建当前本地日程草稿。

        只能在用户明确说“创建日程/确认创建日程”后调用。工具内部走
        Proposal -> Authorization -> Execution，并在执行前由 Calendar 服务二次
        Freebusy 校验。

        Args:
            artifact_id: 日程 Artifact ID；为空时使用当前 active_calendar_draft
            conflict_override: 用户是否明确要求忽略冲突仍然创建
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("google_not_connected", "请先连接 Google 账号。")
        try:
            from app.schemas.calendar import CalendarEventPayload
            from app.schemas.workflow import (
                AuthorizeProposalRequest,
                CreateProposalRequest,
                ExecuteProposalRequest,
            )
            from app.services.draft_context import (
                close_work_item,
                load_active_artifact,
                load_artifact_for_update,
                update_artifact_content,
            )
            from app.services.workflow import (
                authorize_proposal,
                create_proposal_from_artifact,
                execute_authorized_proposal,
            )

            if not artifact_id:
                active = _run_async(
                    load_active_artifact(session, user, _get_thread_id(), "calendar_event_draft")
                )
                artifact_id = str((active or {}).get("artifact_id") or "")
            artifact = _run_async(
                load_artifact_for_update(session, user, artifact_id, "calendar_event_draft")
            )
            if not artifact:
                return _fail("calendar_event_draft_not_found", "没有找到可创建的日程草稿。")

            content = dict(artifact["content"])
            if conflict_override:
                content["conflict_override"] = True
            timezone_name = str(content.get("timezone") or "Asia/Shanghai")
            normalized_start = _normalize_calendar_datetime(str(content.get("start_time") or ""), timezone_name)
            normalized_end = _normalize_calendar_datetime(str(content.get("end_time") or ""), timezone_name)
            content_changed = False
            if normalized_start and normalized_start != content.get("start_time"):
                content["start_time"] = normalized_start
                content_changed = True
            if normalized_end and normalized_end != content.get("end_time"):
                content["end_time"] = normalized_end
                content_changed = True
            missing_fields = _calendar_missing_fields(content)
            if missing_fields:
                return _fail(
                    "calendar_event_draft_incomplete",
                    f"日程草稿还缺少：{', '.join(missing_fields)}，不能创建。",
                    {"artifact_id": artifact_id, "missing_fields": missing_fields},
                )
            conflicts = content.get("conflict_summary") or []
            if conflicts and not content.get("conflict_override"):
                return _fail(
                    "calendar_event_conflict",
                    "该时段存在日程冲突。如仍要创建，请明确回复“仍然创建”。",
                    _calendar_card_data(
                        artifact_id=artifact_id,
                        work_item_id=artifact["work_item_id"],
                        version=artifact["version"],
                        payload=content,
                        missing_fields=[],
                    ),
                )

            # 执行前把用户时区时间和本轮安全决策写回 Artifact，保证 Proposal
            # fingerprint 和执行 payload 与最终写入 Google Calendar 的内容一致。
            if conflict_override or content_changed:
                next_version = _run_async(
                    update_artifact_content(
                        session,
                        artifact_id=artifact_id,
                        work_item_id=artifact["work_item_id"],
                        version=artifact["version"],
                        content=content,
                        title=str(content.get("title") or "未命名日程草稿"),
                        summary=f"{content.get('start_time', '')} - {content.get('end_time', '')}",
                        maturity="reviewable",
                    )
                )
                artifact["version"] = next_version

            CalendarEventPayload.model_validate(content)
            proposal = _run_async(
                create_proposal_from_artifact(
                    session,
                    user,
                    CreateProposalRequest(
                        artifact_id=artifact_id,
                        action_type="create_calendar_event",
                    ),
                )
            )
            authorized = _run_async(
                authorize_proposal(
                    session,
                    user,
                    proposal.id,
                    AuthorizeProposalRequest(
                        version=proposal.version,
                        fingerprint=proposal.fingerprint,
                        source="chat_confirm",
                    ),
                )
            )
            result = _run_async(
                execute_authorized_proposal(
                    session,
                    user,
                    authorized.id,
                    ExecuteProposalRequest(),
                )
            )
            if result.status in {"succeeded", "executed"}:
                _run_async(close_work_item(session, work_item_id=artifact["work_item_id"], status="created"))
            event_payload = (result.payload or {}).get("event") if isinstance(result.payload, dict) else {}
            return _ok(
                "calendar_event_draft_executed",
                "日程已创建。",
                _calendar_card_data(
                    artifact_id=artifact_id,
                    work_item_id=artifact["work_item_id"],
                    version=int(artifact["version"]),
                    payload=content,
                    missing_fields=[],
                    status="created",
                    external_event_id=result.external_resource_id,
                    html_link=(event_payload or {}).get("html_link") if isinstance(event_payload, dict) else None,
                ),
            )
        except Exception as e:
            return _fail("calendar_event_draft_execute_failed", f"创建日程失败：{e}")

    tools.append(execute_calendar_event_draft)

    @tool
    def execute_calendar_event_update_draft(
        artifact_id: str = "",
        event_id: str = "",
        conflict_override: bool = False,
    ) -> str:
        """确认执行已有日程的更新草稿。

        Args:
            artifact_id: 本地日程更新草稿 Artifact ID；为空时使用 active_calendar_draft
            event_id: 要更新的 Google Calendar Event ID；为空时读取草稿里的 external_event_id
            conflict_override: 用户是否明确要求忽略冲突仍然更新
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("google_not_connected", "请先连接 Google 账号。")
        try:
            from app.schemas.calendar import CalendarEventPayload
            from app.schemas.workflow import (
                AuthorizeProposalRequest,
                CreateProposalRequest,
                ExecuteProposalRequest,
            )
            from app.services.draft_context import (
                close_work_item,
                load_active_artifact,
                load_artifact_for_update,
                update_artifact_content,
            )
            from app.services.workflow import (
                authorize_proposal,
                create_proposal_from_artifact,
                execute_authorized_proposal,
            )

            if not artifact_id:
                active = _run_async(
                    load_active_artifact(session, user, _get_thread_id(), "calendar_event_draft")
                )
                artifact_id = str((active or {}).get("artifact_id") or "")
            artifact = _run_async(
                load_artifact_for_update(session, user, artifact_id, "calendar_event_draft")
            )
            if not artifact:
                return _fail("calendar_event_update_draft_not_found", "没有找到可执行的日程更新草稿。")

            content = dict(artifact["content"])
            target_event_id = event_id or str(content.get("external_event_id") or "")
            if not target_event_id:
                return _fail("calendar_event_target_missing", "日程更新草稿缺少要更新的日程标识。")
            if conflict_override:
                content["conflict_override"] = True
            missing_fields = _calendar_missing_fields(content)
            if missing_fields:
                return _fail(
                    "calendar_event_update_draft_incomplete",
                    f"日程更新草稿还缺少：{', '.join(missing_fields)}，不能执行。",
                    {"artifact_id": artifact_id, "missing_fields": missing_fields},
                )
            conflicts = content.get("conflict_summary") or []
            if conflicts and not content.get("conflict_override"):
                return _fail(
                    "calendar_event_update_conflict",
                    "该时段存在日程冲突。如仍要更新，请明确回复“仍然创建”或“仍然更新”。",
                    _calendar_card_data(
                        artifact_id=artifact_id,
                        work_item_id=artifact["work_item_id"],
                        version=artifact["version"],
                        payload=content,
                        missing_fields=[],
                    ),
                )
            if conflict_override:
                next_version = _run_async(
                    update_artifact_content(
                        session,
                        artifact_id=artifact_id,
                        work_item_id=artifact["work_item_id"],
                        version=artifact["version"],
                        content=content,
                        title=str(content.get("title") or "未命名日程更新草稿"),
                        summary=f"{content.get('start_time', '')} - {content.get('end_time', '')}",
                        maturity="reviewable",
                    )
                )
                artifact["version"] = next_version

            CalendarEventPayload.model_validate(content)
            proposal = _run_async(
                create_proposal_from_artifact(
                    session,
                    user,
                    CreateProposalRequest(
                        artifact_id=artifact_id,
                        action_type="update_calendar_event",
                    ),
                )
            )
            authorized = _run_async(
                authorize_proposal(
                    session,
                    user,
                    proposal.id,
                    AuthorizeProposalRequest(
                        version=proposal.version,
                        fingerprint=proposal.fingerprint,
                        source="chat_confirm",
                    ),
                )
            )
            result = _run_async(
                execute_authorized_proposal(
                    session,
                    user,
                    authorized.id,
                    ExecuteProposalRequest(external_resource_id=target_event_id),
                )
            )
            if result.status in {"succeeded", "executed"}:
                _run_async(close_work_item(session, work_item_id=artifact["work_item_id"], status="updated"))
            return _ok(
                "calendar_event_update_draft_executed",
                "日程已更新。",
                _calendar_card_data(
                    artifact_id=artifact_id,
                    work_item_id=artifact["work_item_id"],
                    version=int(artifact["version"]),
                    payload=content,
                    missing_fields=[],
                    status="updated",
                    external_event_id=target_event_id,
                ),
            )
        except Exception as e:
            return _fail("calendar_event_update_draft_execute_failed", f"更新日程失败：{e}")

    tools.append(execute_calendar_event_update_draft)

    @tool
    def delete_calendar_event(event_id: str, calendar_id: str = "primary") -> str:
        """为已有 Google Calendar 事件创建删除草稿，不直接删除。

        Args:
            event_id: 要删除的 Google Calendar Event ID
            calendar_id: 事件所在日历
        """
        client = _get_calendar_client()
        user = _get_user()
        session = _get_session()
        if not client or not user or not session:
            return _fail("calendar_not_connected", "Calendar 未连接。")
        try:
            from app.services.calendar import CalendarEventPayload, _create_calendar_artifact

            old_event = _run_async(client.get_event_for_update(calendar_id, event_id))
            content = CalendarEventPayload(
                title=old_event.summary or "未命名日程",
                start_time=old_event.start.date_time if old_event.start else "",
                end_time=old_event.end.date_time if old_event.end else "",
                timezone=(old_event.start.timezone if old_event.start else "Asia/Shanghai"),
                calendar_id=calendar_id,
                organizer_email=user.email,
                attendees=old_event.attendees,
                location=old_event.location or "",
                description=old_event.description or "",
                video_conference=False,
                recurrence_rule=None,
                reminders=[],
                conflict_override=False,
                conflict_summary=[],
                external_event_id=event_id,
                calendar_action="delete",
            )
            result = _run_async(
                _create_calendar_artifact(session, user, _get_thread_id(), content, "reviewable")
            )
            return _ok(
                "calendar_delete_draft_created",
                (
                    "日程删除草稿已创建。请确认是否删除："
                    f"{content.title}（{content.start_time} - {content.end_time}）。"
                ),
                _calendar_card_data(
                    artifact_id=result.artifact_id,
                    work_item_id=result.work_item_id,
                    version=result.version,
                    payload=content.model_dump(mode="json"),
                    missing_fields=[],
                    warnings=["删除日程需要再次确认。"],
                ),
            )
        except Exception as e:
            return _fail("calendar_delete_draft_create_failed", f"创建日程删除草稿失败：{e}")

    tools.append(delete_calendar_event)

    @tool
    def execute_calendar_event_delete_draft(artifact_id: str = "", event_id: str = "") -> str:
        """确认删除当前日程删除草稿。"""
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("google_not_connected", "请先连接 Google 账号。")
        try:
            from app.schemas.calendar import CalendarEventPayload
            from app.schemas.workflow import (
                AuthorizeProposalRequest,
                CreateProposalRequest,
                ExecuteProposalRequest,
            )
            from app.services.draft_context import close_work_item, load_active_artifact, load_artifact_for_update
            from app.services.workflow import (
                authorize_proposal,
                create_proposal_from_artifact,
                execute_authorized_proposal,
            )

            if not artifact_id:
                active = _run_async(
                    load_active_artifact(session, user, _get_thread_id(), "calendar_event_draft")
                )
                artifact_id = str((active or {}).get("artifact_id") or "")
            artifact = _run_async(
                load_artifact_for_update(session, user, artifact_id, "calendar_event_draft")
            )
            if not artifact:
                return _fail("calendar_delete_draft_not_found", "没有找到可删除的日程草稿。")

            payload = CalendarEventPayload.model_validate(artifact["content"])
            if payload.calendar_action != "delete":
                return _fail("calendar_delete_draft_mismatch", "当前日程草稿不是删除操作，不能删除。")
            target_event_id = event_id or payload.external_event_id
            if not target_event_id:
                return _fail("calendar_delete_missing_event_id", "缺少要删除的日程标识。")

            proposal = _run_async(
                create_proposal_from_artifact(
                    session,
                    user,
                    CreateProposalRequest(
                        artifact_id=artifact_id,
                        action_type="delete_calendar_event",
                    ),
                )
            )
            authorized = _run_async(
                authorize_proposal(
                    session,
                    user,
                    proposal.id,
                    AuthorizeProposalRequest(
                        version=proposal.version,
                        fingerprint=proposal.fingerprint,
                        source="chat_confirm",
                    ),
                )
            )
            result = _run_async(
                execute_authorized_proposal(
                    session,
                    user,
                    authorized.id,
                    ExecuteProposalRequest(external_resource_id=target_event_id),
                )
            )
            if result.status in {"succeeded", "executed"}:
                _run_async(close_work_item(session, work_item_id=artifact["work_item_id"], status="deleted"))
            return _ok(
                "calendar_event_delete_draft_executed",
                "日程已删除。",
                {
                    "artifact_id": artifact_id,
                    "work_item_id": artifact["work_item_id"],
                    "status": "deleted",
                    "title": payload.title,
                    "calendar_id": payload.calendar_id,
                    "external_event_id": target_event_id,
                },
            )
        except Exception as e:
            return _fail("calendar_event_delete_draft_execute_failed", f"删除日程失败：{e}")

    tools.append(execute_calendar_event_delete_draft)

    # ── 上下文 ────────────────────────────────────────────────────

    @tool
    def resolve_contact(name: str) -> str:
        """按姓名或邮箱查询设置页联系人。

        这个工具用于“事实源优先级”的第一层：用户手动维护的联系人。
        如果结果不唯一或不存在，agent 仍可继续搜索 Gmail/历史记录，最后再追问用户。

        Args:
            name: 联系人姓名、称呼片段或用户直接给出的邮箱
        """
        user = _get_user()
        session = _get_session()
        query = name.strip()
        if not query:
            return _fail("contact_name_missing", "请提供要查询的联系人姓名。")

        direct_emails = EMAIL_IN_TEXT_PATTERN.findall(query)
        if direct_emails:
            email = direct_emails[0]
            return _ok(
                "contact_email_provided",
                f"用户已直接提供邮箱：{email}",
                {
                    "query": query,
                    "contact": {"id": "", "display_name": "", "email": email},
                    "candidates": [],
                },
            )

        if not user or not session:
            return _fail(
                "contacts_unavailable",
                "当前没有可用的设置页联系人上下文，可继续搜索邮件历史或向用户确认。",
                {"query": query, "candidates": []},
            )

        matches = _resolve_contact_matches(query, session, user)
        if len(matches) == 1:
            contact = _contact_to_json(matches[0])
            return _ok(
                "contact_resolved",
                f"找到联系人 {contact['display_name']}：{contact['email']}",
                {"query": query, "contact": contact, "candidates": [contact]},
            )
        if len(matches) > 1:
            candidates = [_contact_to_json(item) for item in matches]
            names = "、".join(f"{item['display_name']} <{item['email']}>" for item in candidates)
            return _fail(
                "contact_ambiguous",
                f"找到多个可能的联系人：{names}。请让用户确认使用哪一个。",
                {"query": query, "candidates": candidates},
            )
        return _fail(
            "contact_not_found",
            f"设置页联系人中没有找到「{query}」。可继续搜索 Gmail/历史记录，仍找不到再追问用户。",
            {"query": query, "candidates": []},
        )

    tools.append(resolve_contact)

    @tool
    def get_user_signatures() -> str:
        """获取用户的所有邮件署名，包括默认署名。"""
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _ok("signatures_unavailable", "未配置署名。", {"signatures": []})
        try:
            from app.services.settings import list_signatures
            sigs = _run_async(list_signatures(session, user))
            if not sigs:
                return _ok("signatures_empty", "未配置署名。可在设置页创建。", {"signatures": []})
            lines = ["📝 **用户署名**："]
            signatures = []
            for s in sigs:
                marker = " ⭐默认" if s.is_default else ""
                signatures.append(
                    {
                        "id": s.id,
                        "label": s.label,
                        "content": s.content,
                        "is_default": s.is_default,
                    }
                )
                lines.append(f"- {s.label}{marker}: {s.content}")
            return _ok(
                "signatures_listed",
                "\n".join(lines),
                {"signatures": signatures},
            )
        except Exception as e:
            return _fail("signatures_read_failed", f"获取署名失败：{e}")

    tools.append(get_user_signatures)

    @tool
    def get_user_profile() -> str:
        """获取用户设置：时区、默认日历、会议时长、语气偏好等。"""
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("user_not_connected", "用户未连接。")
        try:
            from app.services.settings import get_user_profile
            profile = _run_async(get_user_profile(session, user))
            message = (
                "👤 **用户设置**\n"
                f"邮箱: {profile.email}\n"
                f"显示名: {profile.display_name or '未设置'}\n"
                f"时区: {profile.timezone or 'Asia/Shanghai'}\n"
                f"默认日历: {profile.default_calendar_id or 'primary'}\n"
                f"默认会议时长: {profile.default_meeting_duration_minutes or 60} 分钟\n"
                f"内部语气: {profile.email_tone_internal or '未设置'}\n"
                f"外部语气: {profile.email_tone_external or '未设置'}"
            )
            return _ok(
                "user_profile_read",
                message,
                {
                    "email": profile.email,
                    "display_name": profile.display_name,
                    "timezone": profile.timezone or "Asia/Shanghai",
                    "default_calendar_id": profile.default_calendar_id or "primary",
                    "default_meeting_duration_minutes": (
                        profile.default_meeting_duration_minutes or 60
                    ),
                    "email_tone_internal": profile.email_tone_internal,
                    "email_tone_external": profile.email_tone_external,
                },
            )
        except Exception as e:
            return _fail("user_profile_read_failed", f"获取设置失败：{e}")

    tools.append(get_user_profile)

    # ── 记忆 ──────────────────────────────────────────────────────

    @tool
    def remember_user_fact(key: str, fact: str) -> str:
        """记住用户偏好/习惯/信息，未来对话自动召回。

        Args:
            key: 记忆关键词
            fact: 要记住的内容
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _fail("memory_context_missing", "暂时无法保存。")
        try:
            import uuid
            ts = datetime.now().isoformat()
            content = json.dumps({"text": fact, "source": "tool_call"}, ensure_ascii=False)
            _run_async(session.execute(
                text(
                    """INSERT INTO memories (id, user_id, namespace, memory_key,
                       memory_type, content_json, confidence, status, created_at, updated_at)
                       VALUES (:id, :uid, 'preferences', :key, 'preference',
                       :content, 0.9, 'active', :ts, :ts)"""
                ),
                {"id": f"mem_{uuid.uuid4().hex}", "uid": user.user_id,
                 "key": key[:80], "content": content, "ts": ts},
            ))
            _run_async(session.commit())
            return _ok(
                "memory_saved",
                f"已记住：{key} → {fact}",
                {"memory_key": key[:80], "text": fact},
            )
        except Exception as e:
            return _fail("memory_save_failed", f"保存失败：{e}")

    tools.append(remember_user_fact)

    @tool
    def recall_memories(query: str = "") -> str:
        """召回之前记住的用户偏好和重要信息。

        Args:
            query: 搜索关键词，留空返回最近 10 条
        """
        user = _get_user()
        session = _get_session()
        if not user or not session:
            return _ok("memories_unavailable", "暂无记忆。", {"memories": []})
        try:
            sql = "SELECT memory_key, content_json, updated_at FROM memories WHERE user_id = :uid AND status = 'active'"
            params: dict[str, Any] = {"uid": user.user_id}
            if query:
                sql += " AND (memory_key LIKE :q OR content_json LIKE :q)"
                params["q"] = f"%{query}%"
            sql += " ORDER BY updated_at DESC LIMIT 10"

            result = _run_async(session.execute(text(sql), params))
            rows = list(result.mappings())
            if not rows:
                return _ok("memories_empty", "暂无相关记忆。", {"memories": []})
            lines = ["🧠 **用户记忆**："]
            memories = []
            for row in rows:
                c = json.loads(row["content_json"] or "{}")
                memories.append(
                    {
                        "memory_key": row["memory_key"],
                        "text": c.get("text", str(c)),
                        "updated_at": row["updated_at"],
                    }
                )
                lines.append(f"- {row['memory_key']}: {c.get('text', str(c))}")
            return _ok("memories_recalled", "\n".join(lines), {"memories": memories})
        except Exception as e:
            return _fail("memories_recall_failed", f"召回失败：{e}")

    tools.append(recall_memories)

    return tools


# 各 LLM Agent 的工具白名单。这里先做逻辑分层，后续可把同名工具物理移动到
# gmail_tools/local_email_draft_tools/calendar_tools 等模块，外部接口保持不变。
AGENT_TOOL_NAMES: dict[str, set[str]] = {
    "supervisor_agent": set(),
    "context_agent": {
        "search_emails",
        "read_email",
        "list_calendar_events",
        "read_local_email_draft",
        "list_local_email_drafts",
    },
    "mail_agent": {
        "search_emails",
        "read_email",
        "create_email_draft",
        "update_email_draft",
        "list_local_email_drafts",
        "read_local_email_draft",
        "delete_local_email_draft",
        "delete_all_local_email_drafts",
        "delete_email",
        "resolve_contact",
        "get_user_signatures",
        "get_user_profile",
    },
    "calendar_agent": {
        "list_calendar_events",
        "create_calendar_event_draft",
        "update_calendar_event_draft",
        "create_calendar_update_draft",
        "delete_calendar_event",
        "resolve_contact",
        "get_user_profile",
    },
    "memory_agent": {
        "remember_user_fact",
        "recall_memories",
    },
    "response_agent": set(),
}


def create_tools_for_agent(agent_name: str) -> list:
    """按 Agent 职责返回工具子集。

    多 Agent 架构中，每个 LLM Agent 只能看到自己的工具，避免 Mail Agent
    意外操作日程、Response Agent 意外执行外部写操作。
    """
    allowed = AGENT_TOOL_NAMES.get(agent_name)
    if allowed is None:
        return []
    return [item for item in create_tools() if item.name in allowed]
