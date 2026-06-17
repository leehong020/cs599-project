from typing import Any

from pydantic import BaseModel, Field


class CalendarAttendee(BaseModel):
    """日程参会人。"""

    email: str
    display_name: str | None = None


class CalendarEventTime(BaseModel):
    """Google Calendar 使用的时间结构。"""

    date_time: str
    timezone: str


class CalendarEventPayload(BaseModel):
    """本地日程 Artifact 和 Proposal payload 使用的结构。"""

    title: str
    start_time: str
    end_time: str
    timezone: str
    calendar_id: str
    organizer_email: str
    attendees: list[CalendarAttendee] = []
    location: str | None = None
    description: str | None = None
    video_conference: bool = False
    recurrence_rule: str | None = None
    reminders: list[dict[str, Any]] = []
    conflict_override: bool = False
    conflict_summary: list["BusySlot"] = []
    external_event_id: str | None = None
    calendar_action: str | None = None


class CalendarEventResponse(BaseModel):
    """Calendar 事件详情。"""

    id: str
    calendar_id: str
    summary: str | None = None
    description: str | None = None
    location: str | None = None
    start: CalendarEventTime | None = None
    end: CalendarEventTime | None = None
    attendees: list[CalendarAttendee] = []
    html_link: str | None = None
    raw: dict[str, Any] = {}


class ListEventsRequest(BaseModel):
    """读取未来日程请求。"""

    calendar_id: str = "primary"
    time_min: str
    time_max: str | None = None
    max_results: int = Field(default=10, ge=1, le=50)


class ListEventsResponse(BaseModel):
    """读取未来日程响应。"""

    events: list[CalendarEventResponse]


class FreebusyRequest(BaseModel):
    """Freebusy 查询请求。"""

    time_min: str
    time_max: str
    timezone: str
    calendar_ids: list[str] = ["primary"]


class BusySlot(BaseModel):
    """忙碌时间段。"""

    calendar_id: str
    start: str
    end: str


class FreebusyResponse(BaseModel):
    """Freebusy 查询响应。"""

    busy: list[BusySlot]
    conflicts: list[BusySlot]
    warnings: list[str] = []
    raw: dict[str, Any] = {}


class PrepareCalendarEventRequest(BaseModel):
    """准备日程本地草稿的请求。"""

    thread_id: str | None = None
    title: str
    start_time: str
    end_time: str | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    timezone: str
    calendar_id: str = "primary"
    organizer_email: str
    attendees: list[CalendarAttendee] = []
    location: str | None = None
    description: str | None = None
    video_conference: bool = False
    recurrence_rule: str | None = None
    conflict_override: bool = False


class CalendarArtifactResponse(BaseModel):
    """本地日程 Artifact 响应。"""

    thread_id: str
    work_item_id: str
    artifact_id: str
    version: int
    maturity: str
    conflicts: list[BusySlot]
    warnings: list[str]
    content: CalendarEventPayload
