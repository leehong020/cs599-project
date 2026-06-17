import pytest

from app.schemas.calendar import CalendarAttendee, CalendarEventPayload
from app.services.calendar import (
    CalendarExecutionBlocked,
    calculate_end_time,
    collect_busy_slots,
    find_conflicts,
    parse_calendar_event,
    to_google_event_payload,
    validate_attendee_emails,
)


def test_calculate_end_time_uses_duration_when_end_missing() -> None:
    result = calculate_end_time("2026-06-11T15:00:00+08:00", None, 60)

    assert result == "2026-06-11T16:00:00+08:00"


def test_calculate_end_time_blocks_missing_duration_and_end() -> None:
    with pytest.raises(CalendarExecutionBlocked):
        calculate_end_time("2026-06-11T15:00:00+08:00", None, None)


def test_find_conflicts_detects_overlapping_busy_slots() -> None:
    busy, warnings = collect_busy_slots(
        {
            "calendars": {
                "primary": {
                    "busy": [
                        {
                            "start": "2026-06-11T15:30:00+08:00",
                            "end": "2026-06-11T16:30:00+08:00",
                        }
                    ]
                }
            }
        }
    )

    conflicts = find_conflicts(
        busy,
        "2026-06-11T15:00:00+08:00",
        "2026-06-11T16:00:00+08:00",
    )

    assert warnings == []
    assert len(conflicts) == 1
    assert conflicts[0].calendar_id == "primary"


def test_collect_busy_slots_reports_unreadable_calendar() -> None:
    busy, warnings = collect_busy_slots(
        {
            "calendars": {
                "primary": {
                    "errors": [{"reason": "notFound"}],
                    "busy": [],
                }
            }
        }
    )

    assert busy == []
    assert warnings == ["primary busy 信息不可读：notFound"]


def test_validate_attendee_emails_rejects_invalid_email() -> None:
    with pytest.raises(CalendarExecutionBlocked):
        validate_attendee_emails([CalendarAttendee(email="not-an-email")])


def test_to_google_event_payload_preserves_timezone_and_attendees() -> None:
    payload = CalendarEventPayload(
        title="复盘会议",
        start_time="2026-06-11T15:00:00+08:00",
        end_time="2026-06-11T16:00:00+08:00",
        timezone="Asia/Shanghai",
        calendar_id="primary",
        organizer_email="me@example.com",
        attendees=[CalendarAttendee(email="li@example.com", display_name="李明")],
        video_conference=True,
    )

    result = to_google_event_payload(payload)

    assert result["start"]["timeZone"] == "Asia/Shanghai"
    assert result["end"]["timeZone"] == "Asia/Shanghai"
    assert result["attendees"][0]["email"] == "li@example.com"
    assert result["conferenceData"]["createRequest"]["conferenceSolutionKey"]["type"] == "hangoutsMeet"


def test_parse_calendar_event_reads_start_end_and_attendees() -> None:
    result = parse_calendar_event(
        {
            "id": "event_1",
            "summary": "复盘会议",
            "start": {"dateTime": "2026-06-11T15:00:00+08:00", "timeZone": "Asia/Shanghai"},
            "end": {"dateTime": "2026-06-11T16:00:00+08:00", "timeZone": "Asia/Shanghai"},
            "attendees": [{"email": "li@example.com", "displayName": "李明"}],
        },
        "primary",
    )

    assert result.id == "event_1"
    assert result.start is not None
    assert result.start.timezone == "Asia/Shanghai"
    assert result.attendees[0].email == "li@example.com"
