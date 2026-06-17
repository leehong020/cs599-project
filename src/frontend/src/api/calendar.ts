export interface CalendarAttendee {
  email: string;
  display_name: string | null;
}

export interface CalendarEventTime {
  date_time: string;
  timezone: string;
}

export interface CalendarEventResponse {
  id: string;
  calendar_id: string;
  summary: string | null;
  description: string | null;
  location: string | null;
  start: CalendarEventTime | null;
  end: CalendarEventTime | null;
  attendees: CalendarAttendee[];
  html_link: string | null;
}

export interface ListEventsRequest {
  calendar_id: string;
  time_min: string;
  time_max: string | null;
  max_results: number;
}

export interface ListEventsResponse {
  events: CalendarEventResponse[];
}

export interface BusySlot {
  calendar_id: string;
  start: string;
  end: string;
}

export interface FreebusyRequest {
  time_min: string;
  time_max: string;
  timezone: string;
  calendar_ids: string[];
}

export interface FreebusyResponse {
  busy: BusySlot[];
  conflicts: BusySlot[];
  warnings: string[];
}

export interface PrepareCalendarEventRequest {
  thread_id: string | null;
  title: string;
  start_time: string;
  end_time: string | null;
  duration_minutes: number | null;
  timezone: string;
  calendar_id: string;
  organizer_email: string;
  attendees: CalendarAttendee[];
  location: string | null;
  description: string | null;
  video_conference: boolean;
  recurrence_rule: string | null;
  conflict_override: boolean;
}

export interface CalendarEventPayload {
  title: string;
  start_time: string;
  end_time: string;
  timezone: string;
  calendar_id: string;
  organizer_email: string;
  attendees: CalendarAttendee[];
  location: string | null;
  description: string | null;
  video_conference: boolean;
  recurrence_rule: string | null;
  reminders: Record<string, unknown>[];
  conflict_override: boolean;
  conflict_summary: BusySlot[];
  external_event_id?: string | null;
  calendar_action?: string | null;
}

export interface CalendarArtifactResponse {
  thread_id: string;
  work_item_id: string;
  artifact_id: string;
  version: number;
  maturity: string;
  conflicts: BusySlot[];
  warnings: string[];
  content: {
    title: string;
    start_time: string;
    end_time: string;
    timezone: string;
    calendar_id: string;
    organizer_email: string;
    attendees: CalendarAttendee[];
    location: string | null;
    description: string | null;
    video_conference: boolean;
    recurrence_rule: string | null;
    conflict_override: boolean;
    conflict_summary: BusySlot[];
  };
}

// Calendar token 仍然只在后端解密和使用。前端只发送用户显式填写的
// 时间、日历和参会人等业务字段。
export async function listCalendarEvents(payload: ListEventsRequest): Promise<ListEventsResponse> {
  const response = await fetch("/api/calendar/events/list", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Calendar events fetch failed with ${response.status}`);
  }

  return response.json() as Promise<ListEventsResponse>;
}

export async function queryCalendarFreebusy(
  payload: FreebusyRequest,
): Promise<FreebusyResponse> {
  const response = await fetch("/api/calendar/freebusy", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Calendar freebusy failed with ${response.status}`);
  }

  return response.json() as Promise<FreebusyResponse>;
}

export async function prepareCalendarEventDraft(
  payload: PrepareCalendarEventRequest,
): Promise<CalendarArtifactResponse> {
  const response = await fetch("/api/calendar/prepare/event", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Prepare calendar event failed with ${response.status}`);
  }

  return response.json() as Promise<CalendarArtifactResponse>;
}

export async function createCalendarEvent(
  payload: CalendarEventPayload,
): Promise<CalendarEventResponse> {
  const response = await fetch("/api/calendar/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Create calendar event failed with ${response.status}`);
  }

  return response.json() as Promise<CalendarEventResponse>;
}

export async function updateCalendarEvent(
  eventId: string,
  payload: CalendarEventPayload,
): Promise<CalendarEventResponse> {
  const response = await fetch(`/api/calendar/events/${encodeURIComponent(eventId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Update calendar event failed with ${response.status}`);
  }

  return response.json() as Promise<CalendarEventResponse>;
}

export async function deleteCalendarEvent(
  calendarId: string,
  eventId: string,
): Promise<void> {
  const response = await fetch(
    `/api/calendar/events/${encodeURIComponent(eventId)}?calendar_id=${encodeURIComponent(calendarId)}`,
    { method: "DELETE" },
  );

  if (!response.ok) {
    throw new Error(`Delete calendar event failed with ${response.status}`);
  }
}
