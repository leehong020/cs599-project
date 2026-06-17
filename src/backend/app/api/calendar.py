from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.calendar import (
    CalendarArtifactResponse,
    CalendarEventPayload,
    CalendarEventResponse,
    FreebusyRequest,
    FreebusyResponse,
    ListEventsRequest,
    ListEventsResponse,
    PrepareCalendarEventRequest,
)
from app.services.calendar import (
    build_calendar_client_for_user,
    prepare_calendar_event_artifact,
)
from app.services.settings import require_connected_user

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/events/list", response_model=ListEventsResponse)
async def list_events(
    payload: ListEventsRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ListEventsResponse:
    """读取未来 Calendar 事件。"""
    user = await require_connected_user(session)
    client = await build_calendar_client_for_user(session, user)
    return await client.list_events(
        calendar_id=payload.calendar_id,
        time_min=payload.time_min,
        time_max=payload.time_max,
        max_results=payload.max_results,
    )


@router.post("/freebusy", response_model=FreebusyResponse)
async def query_freebusy(
    payload: FreebusyRequest,
    session: AsyncSession = Depends(get_db_session),
) -> FreebusyResponse:
    """查询 Calendar Freebusy，并返回冲突信息。"""
    user = await require_connected_user(session)
    client = await build_calendar_client_for_user(session, user)
    return await client.query_freebusy(payload)


@router.post("/prepare/event", response_model=CalendarArtifactResponse)
async def prepare_calendar_event(
    payload: PrepareCalendarEventRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CalendarArtifactResponse:
    """准备本地日程草稿，不写 Google Calendar。"""
    user = await require_connected_user(session)
    client = await build_calendar_client_for_user(session, user)
    return await prepare_calendar_event_artifact(session, user, client, payload)


@router.post("/events", response_model=CalendarEventResponse)
async def create_event(
    payload: CalendarEventPayload,
    session: AsyncSession = Depends(get_db_session),
) -> CalendarEventResponse:
    """由日程页人工创建 Google Calendar 日程。

    这里和 Assistant 的安全边界不同：日程页按钮是用户显式手动操作，
    可以直接写 Google Calendar。Assistant 代办创建仍必须走本地草稿、
    Proposal、用户确认和 Execution Service。
    """
    user = await require_connected_user(session)
    client = await build_calendar_client_for_user(session, user)
    return await client.insert_event(payload)


@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: str,
    payload: CalendarEventPayload,
    session: AsyncSession = Depends(get_db_session),
) -> CalendarEventResponse:
    """由日程页人工更新 Google Calendar 日程。"""
    user = await require_connected_user(session)
    client = await build_calendar_client_for_user(session, user)
    return await client.update_event(payload.calendar_id, event_id, payload)


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    calendar_id: str = "primary",
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """由日程页人工删除 Google Calendar 日程。"""
    user = await require_connected_user(session)
    client = await build_calendar_client_for_user(session, user)
    return await client.delete_event(calendar_id, event_id)
