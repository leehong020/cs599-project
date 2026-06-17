from pydantic import BaseModel, Field


class WorkingHours(BaseModel):
    """用户工作时间或午休时间。"""

    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")


class UserProfileResponse(BaseModel):
    """用户设置页展示的完整资料。"""

    user_id: str
    email: str
    display_name: str | None = None
    timezone: str | None = None
    default_calendar_id: str | None = None
    default_signature_id: str | None = None
    default_sender_email: str | None = None
    default_meeting_duration_minutes: int | None = None
    meeting_buffer_minutes: int = 0
    working_hours: WorkingHours | None = None
    lunch_break: WorkingHours | None = None
    email_tone_internal: str | None = None
    email_tone_external: str | None = None


class UserProfileUpdateRequest(BaseModel):
    """用户可修改的确定性偏好。

    这些字段会被后续 Completeness Gate 当作事实来源，所以接口只接收
    结构化值，不从聊天自然语言里静默猜默认值。
    """

    timezone: str | None = None
    default_calendar_id: str | None = None
    default_signature_id: str | None = None
    default_sender_email: str | None = None
    default_meeting_duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    meeting_buffer_minutes: int = Field(default=0, ge=0, le=240)
    working_hours: WorkingHours | None = None
    lunch_break: WorkingHours | None = None
    email_tone_internal: str | None = None
    email_tone_external: str | None = None


class SignatureResponse(BaseModel):
    """邮件署名记录。"""

    id: str
    label: str
    content: str
    is_default: bool
    created_at: str
    updated_at: str


class SignatureCreateRequest(BaseModel):
    """创建邮件署名的请求。"""

    label: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=4000)
    is_default: bool = False


class SignatureUpdateRequest(BaseModel):
    """更新邮件署名的请求。"""

    label: str | None = Field(default=None, min_length=1, max_length=80)
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    is_default: bool | None = None


class ContactResponse(BaseModel):
    """设置页展示的联系人记录。"""

    id: str
    display_name: str
    email: str
    created_at: str
    updated_at: str


class ContactCreateRequest(BaseModel):
    """创建联系人的请求。"""

    display_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)


class ContactUpdateRequest(BaseModel):
    """更新联系人的请求。"""

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, min_length=3, max_length=320)
