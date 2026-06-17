from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.calendar import (
    BusySlot,
    CalendarArtifactResponse,
    CalendarAttendee,
    CalendarEventPayload,
    CalendarEventResponse,
    CalendarEventTime,
    FreebusyRequest,
    FreebusyResponse,
    ListEventsResponse,
    PrepareCalendarEventRequest,
)
from app.schemas.completeness import FieldEvidenceInput
from app.services.completeness import upsert_field_evidence
from app.services.oauth import ConnectedUser, get_valid_google_access_token, now_iso

CALENDAR_API_BASE_URL = "https://www.googleapis.com/calendar/v3"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CalendarApiError(RuntimeError):
    """Google Calendar API 调用失败。"""


class CalendarExecutionBlocked(RuntimeError):
    """Calendar 执行被安全规则阻止。"""


class CalendarWriteClient(Protocol):
    """创建、更新或删除日程执行所需的最小客户端协议。"""

    async def get_event_for_update(self, calendar_id: str, event_id: str) -> CalendarEventResponse:
        """更新前读取旧事件。"""

    async def query_freebusy(self, payload: FreebusyRequest) -> FreebusyResponse:
        """执行 Freebusy 查询。"""

    async def insert_event(self, payload: CalendarEventPayload) -> CalendarEventResponse:
        """创建 Calendar Event。"""

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        payload: CalendarEventPayload,
    ) -> CalendarEventResponse:
        """更新 Calendar Event。"""

    async def delete_event(self, calendar_id: str, event_id: str) -> dict[str, str]:
        """删除 Calendar Event。"""


def parse_iso_datetime(value: str) -> datetime:
    """解析 ISO 时间字符串。

    Google 和前端都可能使用 `Z` 表示 UTC。标准库 `fromisoformat`
    需要把它先转换成 `+00:00`。
    """
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def calculate_end_time(start_time: str, end_time: str | None, duration_minutes: int | None) -> str:
    """根据结束时间或持续时长得到最终结束时间。"""
    if end_time:
        return end_time
    if duration_minutes is None:
        raise CalendarExecutionBlocked("缺少结束时间或持续时长，不能创建日程。")
    return (parse_iso_datetime(start_time) + timedelta(minutes=duration_minutes)).isoformat()


def validate_attendee_emails(attendees: list[CalendarAttendee]) -> None:
    """校验参会人邮箱格式。"""
    invalid = [item.email for item in attendees if not EMAIL_PATTERN.match(item.email)]
    if invalid:
        joined = ", ".join(invalid)
        raise CalendarExecutionBlocked(f"参会人邮箱格式不合法：{joined}")


def to_google_event_payload(payload: CalendarEventPayload) -> dict[str, Any]:
    """把内部日程 payload 转换成 Google Calendar API 请求体。"""
    event: dict[str, Any] = {
        "summary": payload.title,
        "description": payload.description,
        "location": payload.location,
        "start": {"dateTime": payload.start_time, "timeZone": payload.timezone},
        "end": {"dateTime": payload.end_time, "timeZone": payload.timezone},
        "attendees": [
            {"email": item.email, "displayName": item.display_name}
            for item in payload.attendees
        ],
    }
    if payload.recurrence_rule:
        event["recurrence"] = [payload.recurrence_rule]
    if payload.video_conference:
        event["conferenceData"] = {
            "createRequest": {
                "requestId": f"meet_{uuid.uuid4().hex}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
    return {key: value for key, value in event.items() if value not in (None, [], {})}


def parse_calendar_event(raw: dict[str, Any], calendar_id: str) -> CalendarEventResponse:
    """把 Google Calendar 原始事件转换成内部结构。"""
    start = raw.get("start") or {}
    end = raw.get("end") or {}
    return CalendarEventResponse(
        id=raw["id"],
        calendar_id=calendar_id,
        summary=raw.get("summary"),
        description=raw.get("description"),
        location=raw.get("location"),
        start=CalendarEventTime(
            date_time=start.get("dateTime") or start.get("date") or "",
            timezone=start.get("timeZone") or "UTC",
        )
        if start
        else None,
        end=CalendarEventTime(
            date_time=end.get("dateTime") or end.get("date") or "",
            timezone=end.get("timeZone") or "UTC",
        )
        if end
        else None,
        attendees=[
            CalendarAttendee(email=item["email"], display_name=item.get("displayName"))
            for item in raw.get("attendees", [])
            if item.get("email")
        ],
        html_link=raw.get("htmlLink"),
        raw=raw,
    )


def collect_busy_slots(raw: dict[str, Any]) -> tuple[list[BusySlot], list[str]]:
    """从 Freebusy 原始响应提取忙碌时间和警告。"""
    busy: list[BusySlot] = []
    warnings: list[str] = []
    calendars = raw.get("calendars") or {}
    for calendar_id, calendar_payload in calendars.items():
        for error in calendar_payload.get("errors", []) or []:
            reason = error.get("reason", "unknown")
            warnings.append(f"{calendar_id} busy 信息不可读：{reason}")
        for item in calendar_payload.get("busy", []) or []:
            busy.append(
                BusySlot(
                    calendar_id=calendar_id,
                    start=item["start"],
                    end=item["end"],
                )
            )
    for group_id, group_payload in (raw.get("groups") or {}).items():
        for error in group_payload.get("errors", []) or []:
            warnings.append(f"{group_id} group busy 信息不可读：{error.get('reason', 'unknown')}")
    return busy, warnings


def find_conflicts(
    busy: list[BusySlot],
    requested_start: str,
    requested_end: str,
) -> list[BusySlot]:
    """判断 busy slot 是否和目标时间重叠。"""
    start = parse_iso_datetime(requested_start)
    end = parse_iso_datetime(requested_end)
    conflicts: list[BusySlot] = []
    for slot in busy:
        slot_start = parse_iso_datetime(slot.start)
        slot_end = parse_iso_datetime(slot.end)
        if slot_start < end and start < slot_end:
            conflicts.append(slot)
    return conflicts


class CalendarClient:
    """Google Calendar REST 客户端。"""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token

    @property
    def _headers(self) -> dict[str, str]:
        """Calendar API 请求头。"""
        return {"Authorization": f"Bearer {self.access_token}"}

    async def list_events(
        self,
        calendar_id: str,
        time_min: str,
        time_max: str | None = None,
        max_results: int = 10,
    ) -> ListEventsResponse:
        """读取未来日程。"""
        params: dict[str, Any] = {
            "timeMin": time_min,
            "maxResults": max_results,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        if time_max:
            params["timeMax"] = time_max
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{CALENDAR_API_BASE_URL}/calendars/{calendar_id}/events",
                headers=self._headers,
                params=params,
            )
        if response.status_code >= 400:
            raise CalendarApiError("Calendar 事件读取失败。")
        payload = response.json()
        return ListEventsResponse(
            events=[parse_calendar_event(item, calendar_id) for item in payload.get("items", [])]
        )

    async def get_event_for_update(self, calendar_id: str, event_id: str) -> CalendarEventResponse:
        """更新前读取旧事件。"""
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{CALENDAR_API_BASE_URL}/calendars/{calendar_id}/events/{event_id}",
                headers=self._headers,
            )
        if response.status_code >= 400:
            raise CalendarApiError("Calendar 旧事件读取失败，不能更新。")
        return parse_calendar_event(response.json(), calendar_id)

    async def query_freebusy(self, payload: FreebusyRequest) -> FreebusyResponse:
        """查询 Freebusy。"""
        body = {
            "timeMin": payload.time_min,
            "timeMax": payload.time_max,
            "timeZone": payload.timezone,
            "items": [{"id": calendar_id} for calendar_id in payload.calendar_ids],
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{CALENDAR_API_BASE_URL}/freeBusy",
                headers=self._headers,
                json=body,
            )
        if response.status_code >= 400:
            raise CalendarApiError("Calendar Freebusy 查询失败。")
        raw = response.json()
        busy, warnings = collect_busy_slots(raw)
        conflicts = find_conflicts(busy, payload.time_min, payload.time_max)
        return FreebusyResponse(busy=busy, conflicts=conflicts, warnings=warnings, raw=raw)

    async def insert_event(self, payload: CalendarEventPayload) -> CalendarEventResponse:
        """创建 Calendar Event，只能由执行服务调用。"""
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{CALENDAR_API_BASE_URL}/calendars/{payload.calendar_id}/events",
                headers=self._headers,
                params={"conferenceDataVersion": 1 if payload.video_conference else 0},
                json=to_google_event_payload(payload),
            )
        if response.status_code >= 400:
            raise CalendarApiError("Calendar Event 创建失败。")
        return parse_calendar_event(response.json(), payload.calendar_id)

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        payload: CalendarEventPayload,
    ) -> CalendarEventResponse:
        """更新 Calendar Event，只能由执行服务调用。"""
        await self.get_event_for_update(calendar_id, event_id)
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.patch(
                f"{CALENDAR_API_BASE_URL}/calendars/{calendar_id}/events/{event_id}",
                headers=self._headers,
                params={"conferenceDataVersion": 1 if payload.video_conference else 0},
                json=to_google_event_payload(payload),
            )
        if response.status_code >= 400:
            raise CalendarApiError("Calendar Event 更新失败。")
        return parse_calendar_event(response.json(), calendar_id)

    async def delete_event(self, calendar_id: str, event_id: str) -> dict[str, str]:
        """删除 Calendar Event。"""
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.delete(
                f"{CALENDAR_API_BASE_URL}/calendars/{calendar_id}/events/{event_id}",
                headers=self._headers,
            )
        if response.status_code >= 400:
            raise CalendarApiError("Calendar Event 删除失败。")
        return {"status": "deleted", "event_id": event_id}


async def build_calendar_client_for_user(
    session: AsyncSession,
    user: ConnectedUser,
) -> CalendarClient:
    """根据当前已连接用户创建 CalendarClient。"""
    access_token = await get_valid_google_access_token(session, user.user_id)
    return CalendarClient(access_token)


async def _ensure_thread(
    session: AsyncSession,
    user: ConnectedUser,
    thread_id: str | None,
    title: str,
) -> str:
    """确保本地聊天 Thread 存在。"""
    timestamp = now_iso()
    if thread_id:
        result = await session.execute(
            text("SELECT id FROM threads WHERE id = :thread_id AND user_id = :user_id"),
            {"thread_id": thread_id, "user_id": user.user_id},
        )
        if result.scalar_one_or_none() is not None:
            return thread_id

    new_thread_id = thread_id or f"thread_{uuid.uuid4().hex}"
    await session.execute(
        text(
            """
            INSERT INTO threads (id, user_id, title, summary, status, created_at, updated_at)
            VALUES (:id, :user_id, :title, :summary, 'active', :created_at, :updated_at)
            """
        ),
        {
            "id": new_thread_id,
            "user_id": user.user_id,
            "title": title,
            "summary": "阶段 5 Calendar 本地日程草稿。",
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    return new_thread_id


async def prepare_calendar_event_artifact(
    session: AsyncSession,
    user: ConnectedUser,
    client: CalendarWriteClient,
    payload: PrepareCalendarEventRequest,
) -> CalendarArtifactResponse:
    """准备本地日程 Artifact，并在创建前执行 Freebusy。"""
    validate_attendee_emails(payload.attendees)
    end_time = calculate_end_time(payload.start_time, payload.end_time, payload.duration_minutes)
    freebusy = await client.query_freebusy(
        FreebusyRequest(
            time_min=payload.start_time,
            time_max=end_time,
            timezone=payload.timezone,
            calendar_ids=[payload.calendar_id],
        )
    )
    if freebusy.warnings:
        # 用户自己的目标日历 busy 信息不可读时，不允许进入普通可执行 Proposal。
        # 这里仍可创建 reviewable 本地草稿，让用户看到问题并重新授权或改日历。
        maturity = "incomplete"
    elif freebusy.conflicts and not payload.conflict_override:
        maturity = "reviewable"
    else:
        maturity = "reviewable"

    content = CalendarEventPayload(
        title=payload.title,
        start_time=payload.start_time,
        end_time=end_time,
        timezone=payload.timezone,
        calendar_id=payload.calendar_id,
        organizer_email=payload.organizer_email,
        attendees=payload.attendees,
        location=payload.location,
        description=payload.description,
        video_conference=payload.video_conference,
        recurrence_rule=payload.recurrence_rule,
        conflict_override=payload.conflict_override,
        conflict_summary=freebusy.conflicts,
    )
    response = await _create_calendar_artifact(session, user, payload.thread_id, content, maturity)
    response.conflicts.extend(freebusy.conflicts)
    response.warnings.extend(freebusy.warnings)
    return response


async def _create_calendar_artifact(
    session: AsyncSession,
    user: ConnectedUser,
    thread_id: str | None,
    payload: CalendarEventPayload,
    maturity: str,
) -> CalendarArtifactResponse:
    """创建本地日程 Work Item 和 Artifact。"""
    timestamp = now_iso()
    actual_thread_id = await _ensure_thread(session, user, thread_id, payload.title)
    work_item_id = f"wi_{uuid.uuid4().hex}"
    artifact_id = f"art_{uuid.uuid4().hex}"
    await session.execute(
        text(
            """
            INSERT INTO work_items (
                id,
                thread_id,
                user_id,
                work_item_type,
                title,
                summary,
                maturity,
                status,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :thread_id,
                :user_id,
                'calendar_event_draft',
                :title,
                :summary,
                :maturity,
                'open',
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": work_item_id,
            "thread_id": actual_thread_id,
            "user_id": user.user_id,
            "title": payload.title,
            "summary": f"{payload.start_time} - {payload.end_time}",
            "maturity": maturity,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO artifacts (
                id,
                work_item_id,
                artifact_type,
                version,
                content_json,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :work_item_id,
                'calendar_event_draft',
                1,
                :content_json,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": artifact_id,
            "work_item_id": work_item_id,
            "content_json": json.dumps(payload.model_dump(mode="json"), ensure_ascii=False),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    await _record_calendar_evidence(session, artifact_id, payload)
    return CalendarArtifactResponse(
        thread_id=actual_thread_id,
        work_item_id=work_item_id,
        artifact_id=artifact_id,
        version=1,
        maturity=maturity,
        conflicts=[],
        warnings=[],
        content=payload,
    )


async def _record_calendar_evidence(
    session: AsyncSession,
    artifact_id: str,
    payload: CalendarEventPayload,
) -> None:
    """为本地日程草稿写入基础 Field Evidence。"""
    values: dict[str, Any] = {
        "title": payload.title,
        "start_time": payload.start_time,
        "end_time": payload.end_time,
        "timezone": payload.timezone,
        "calendar_id": payload.calendar_id,
        "organizer_email": payload.organizer_email,
    }
    if payload.attendees:
        values["attendees"] = [item.model_dump(mode="json") for item in payload.attendees]
    for field_path, value in values.items():
        await upsert_field_evidence(
            session,
            artifact_id,
            FieldEvidenceInput(
                field_path=field_path,
                value=value,
                source_type="user_message",
                source_ref="prepare_calendar_api",
                confidence=1,
                confirmation_status="explicit_user_input",
            ),
        )


async def commit_create_calendar_event_for_authorized_proposal(
    session: AsyncSession,
    proposal_item_id: str,
    client: CalendarWriteClient,
) -> dict[str, Any]:
    """执行已授权的 create_calendar_event Proposal。"""
    proposal = await _load_authorized_calendar_proposal(session, proposal_item_id, "create_calendar_event")
    idempotency_key = (
        f"calendar_create:{proposal['id']}:{proposal['version']}:{proposal['fingerprint']}"
    )
    existing_event = await _load_action_event_by_idempotency(session, idempotency_key)
    if existing_event is not None:
        return existing_event

    calendar_payload = CalendarEventPayload.model_validate(json.loads(proposal["payload_json"]))
    await _assert_freebusy_allows_execution(client, calendar_payload)
    return await _execute_calendar_write(
        session=session,
        proposal_item_id=proposal_item_id,
        idempotency_key=idempotency_key,
        event_type="create_calendar_event",
        write_call=lambda: client.insert_event(calendar_payload),
    )


async def commit_update_calendar_event_for_authorized_proposal(
    session: AsyncSession,
    proposal_item_id: str,
    event_id: str,
    client: CalendarWriteClient,
) -> dict[str, Any]:
    """执行已授权的 update_calendar_event Proposal。"""
    proposal = await _load_authorized_calendar_proposal(session, proposal_item_id, "update_calendar_event")
    idempotency_key = (
        f"calendar_update:{proposal['id']}:{proposal['version']}:{proposal['fingerprint']}:{event_id}"
    )
    existing_event = await _load_action_event_by_idempotency(session, idempotency_key)
    if existing_event is not None:
        return existing_event

    calendar_payload = CalendarEventPayload.model_validate(json.loads(proposal["payload_json"]))
    await client.get_event_for_update(calendar_payload.calendar_id, event_id)
    await _assert_freebusy_allows_execution(client, calendar_payload)
    return await _execute_calendar_write(
        session=session,
        proposal_item_id=proposal_item_id,
        idempotency_key=idempotency_key,
        event_type="update_calendar_event",
        write_call=lambda: client.update_event(calendar_payload.calendar_id, event_id, calendar_payload),
    )


async def commit_delete_calendar_event_for_authorized_proposal(
    session: AsyncSession,
    proposal_item_id: str,
    event_id: str,
    client: CalendarWriteClient,
) -> dict[str, Any]:
    """执行已授权的 delete_calendar_event Proposal。"""
    proposal = await _load_authorized_calendar_proposal(session, proposal_item_id, "delete_calendar_event")
    calendar_payload = CalendarEventPayload.model_validate(json.loads(proposal["payload_json"]))
    target_event_id = event_id or calendar_payload.external_event_id
    if not target_event_id:
        raise CalendarExecutionBlocked("缺少要删除的日程标识。")

    idempotency_key = (
        f"calendar_delete:{proposal['id']}:{proposal['version']}:{proposal['fingerprint']}:{target_event_id}"
    )
    existing_event = await _load_action_event_by_idempotency(session, idempotency_key)
    if existing_event is not None:
        return existing_event

    await client.get_event_for_update(calendar_payload.calendar_id, target_event_id)
    return await _execute_calendar_delete(
        session=session,
        proposal_item_id=proposal_item_id,
        idempotency_key=idempotency_key,
        event_type="delete_calendar_event",
        calendar_id=calendar_payload.calendar_id,
        event_id=target_event_id,
        write_call=lambda: client.delete_event(calendar_payload.calendar_id, target_event_id),
    )


async def _assert_freebusy_allows_execution(
    client: CalendarWriteClient,
    payload: CalendarEventPayload,
) -> None:
    """执行前二次 Freebusy 校验。"""
    freebusy = await client.query_freebusy(
        FreebusyRequest(
            time_min=payload.start_time,
            time_max=payload.end_time,
            timezone=payload.timezone,
            calendar_ids=[payload.calendar_id],
        )
    )
    if freebusy.warnings:
        raise CalendarExecutionBlocked("目标日历忙闲状态不可读，不能创建或更新日程。")
    if freebusy.conflicts and not payload.conflict_override:
        raise CalendarExecutionBlocked("目标时间存在日程冲突，不能静默创建或更新。")


async def _load_authorized_calendar_proposal(
    session: AsyncSession,
    proposal_item_id: str,
    expected_action_type: str,
) -> dict[str, Any]:
    """读取并校验已授权的 Calendar Proposal。"""
    result = await session.execute(
        text(
            """
            SELECT
                pi.id,
                pi.action_type,
                pi.payload_json,
                pi.version,
                pi.fingerprint,
                pi.status,
                pg.user_id
            FROM proposal_items pi
            JOIN proposal_groups pg ON pg.id = pi.proposal_group_id
            WHERE pi.id = :proposal_item_id
            """
        ),
        {"proposal_item_id": proposal_item_id},
    )
    proposal = result.mappings().first()
    if proposal is None:
        raise CalendarExecutionBlocked("Proposal 不存在，不能执行日程写操作。")
    if proposal["action_type"] != expected_action_type:
        raise CalendarExecutionBlocked("Proposal 动作类型不匹配，不能执行。")
    if proposal["status"] in {"executed", "superseded", "cancelled"}:
        raise CalendarExecutionBlocked("该 Proposal 当前状态不能执行。")

    authorization = await session.execute(
        text(
            """
            SELECT id
            FROM action_authorizations
            WHERE proposal_item_id = :proposal_item_id
              AND proposal_version = :proposal_version
              AND fingerprint = :fingerprint
              AND user_id = :user_id
              AND decision = 'approved'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {
            "proposal_item_id": proposal_item_id,
            "proposal_version": proposal["version"],
            "fingerprint": proposal["fingerprint"],
            "user_id": proposal["user_id"],
        },
    )
    if authorization.scalar_one_or_none() is None:
        raise CalendarExecutionBlocked("缺少匹配的用户授权，不能执行日程写操作。")
    return dict(proposal)


async def _execute_calendar_write(
    session: AsyncSession,
    proposal_item_id: str,
    idempotency_key: str,
    event_type: str,
    write_call: Any,
) -> dict[str, Any]:
    """执行 Calendar 写操作并记录 Action Event。"""
    timestamp = now_iso()
    event_id = f"ae_{uuid.uuid4().hex}"
    await session.execute(
        text(
            """
            INSERT INTO action_events (
                id,
                proposal_item_id,
                event_type,
                status,
                idempotency_key,
                external_provider,
                payload_json,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :proposal_item_id,
                :event_type,
                'started',
                :idempotency_key,
                'google_calendar',
                :payload_json,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": event_id,
            "proposal_item_id": proposal_item_id,
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "payload_json": json.dumps({"stage": "started"}, ensure_ascii=False),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    try:
        event = await write_call()
    except Exception as exc:
        await _mark_action_event_failed(session, event_id, str(exc))
        raise

    result_payload = {"stage": "succeeded", "event": event.model_dump(mode="json")}
    await session.execute(
        text(
            """
            UPDATE action_events
            SET status = 'succeeded',
                external_resource_id = :external_resource_id,
                payload_json = :payload_json,
                updated_at = :updated_at
            WHERE id = :id
            """
        ),
        {
            "id": event_id,
            "external_resource_id": event.id,
            "payload_json": json.dumps(result_payload, ensure_ascii=False),
            "updated_at": now_iso(),
        },
    )
    await session.execute(
        text(
            """
            UPDATE proposal_items
            SET status = 'executed', updated_at = :updated_at
            WHERE id = :proposal_item_id
            """
        ),
        {"proposal_item_id": proposal_item_id, "updated_at": now_iso()},
    )
    await session.commit()
    return {
        "status": "succeeded",
        "idempotency_key": idempotency_key,
        "external_resource_id": event.id,
        "payload": result_payload,
    }


async def _execute_calendar_delete(
    session: AsyncSession,
    proposal_item_id: str,
    idempotency_key: str,
    event_type: str,
    calendar_id: str,
    event_id: str,
    write_call: Any,
) -> dict[str, Any]:
    """执行 Calendar 删除操作并记录 Action Event。"""
    timestamp = now_iso()
    action_event_id = f"ae_{uuid.uuid4().hex}"
    await session.execute(
        text(
            """
            INSERT INTO action_events (
                id,
                proposal_item_id,
                event_type,
                status,
                idempotency_key,
                external_provider,
                payload_json,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :proposal_item_id,
                :event_type,
                'started',
                :idempotency_key,
                'google_calendar',
                :payload_json,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "id": action_event_id,
            "proposal_item_id": proposal_item_id,
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "payload_json": json.dumps(
                {"stage": "started", "calendar_id": calendar_id, "event_id": event_id},
                ensure_ascii=False,
            ),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    try:
        await write_call()
    except Exception as exc:
        await _mark_action_event_failed(session, action_event_id, str(exc))
        raise

    result_payload = {
        "stage": "succeeded",
        "event": {"id": event_id, "calendar_id": calendar_id, "status": "deleted"},
    }
    await session.execute(
        text(
            """
            UPDATE action_events
            SET status = 'succeeded',
                external_resource_id = :external_resource_id,
                payload_json = :payload_json,
                updated_at = :updated_at
            WHERE id = :id
            """
        ),
        {
            "id": action_event_id,
            "external_resource_id": event_id,
            "payload_json": json.dumps(result_payload, ensure_ascii=False),
            "updated_at": now_iso(),
        },
    )
    await session.execute(
        text(
            """
            UPDATE proposal_items
            SET status = 'executed', updated_at = :updated_at
            WHERE id = :proposal_item_id
            """
        ),
        {"proposal_item_id": proposal_item_id, "updated_at": now_iso()},
    )
    await session.commit()
    return {
        "status": "succeeded",
        "idempotency_key": idempotency_key,
        "external_resource_id": event_id,
        "payload": result_payload,
    }


async def _load_action_event_by_idempotency(
    session: AsyncSession,
    idempotency_key: str,
) -> dict[str, Any] | None:
    """根据幂等 key 查找已有执行事件。"""
    result = await session.execute(
        text(
            """
            SELECT status, external_resource_id, payload_json
            FROM action_events
            WHERE idempotency_key = :idempotency_key
            """
        ),
        {"idempotency_key": idempotency_key},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return {
        "status": row["status"],
        "idempotency_key": idempotency_key,
        "external_resource_id": row["external_resource_id"],
        "payload": json.loads(row["payload_json"] or "{}"),
    }


async def _mark_action_event_failed(session: AsyncSession, event_id: str, error_message: str) -> None:
    """把执行事件标记为失败。"""
    await session.execute(
        text(
            """
            UPDATE action_events
            SET status = 'failed',
                payload_json = :payload_json,
                updated_at = :updated_at
            WHERE id = :id
            """
        ),
        {
            "id": event_id,
            "payload_json": json.dumps(
                {"stage": "failed", "error": error_message},
                ensure_ascii=False,
            ),
            "updated_at": now_iso(),
        },
    )
    await session.commit()
