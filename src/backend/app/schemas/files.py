from typing import Any, Literal

from pydantic import BaseModel


FileStatus = Literal["uploaded", "extracted", "failed", "deleted"]
ExtractionStatus = Literal["succeeded", "failed"]


class FileExtractionResponse(BaseModel):
    """文件解析结果响应。"""

    id: str
    uploaded_file_id: str
    extractor_name: str
    status: ExtractionStatus
    text_content: str | None = None
    metadata: dict[str, Any] = {}
    error_message: str | None = None
    created_at: str
    updated_at: str


class UploadedFileResponse(BaseModel):
    """上传文件元数据响应。"""

    id: str
    thread_id: str | None = None
    original_filename: str
    content_type: str
    file_size_bytes: int
    sha256: str
    status: FileStatus
    created_at: str
    updated_at: str
    extraction: FileExtractionResponse | None = None


class UploadedFileListResponse(BaseModel):
    """某个会话的上传文件列表。"""

    items: list[UploadedFileResponse]
