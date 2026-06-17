from __future__ import annotations

import hashlib
import json
import re
import uuid
import zipfile
from html import unescape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.files import FileExtractionResponse, UploadedFileResponse
from app.services.oauth import ConnectedUser, get_connected_google_user, now_iso

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".log",
    ".xml",
    ".html",
    ".htm",
    ".py",
    ".js",
    ".ts",
    ".vue",
    ".docx",
    ".pdf",
}
TEXT_EXTENSIONS = SUPPORTED_EXTENSIONS - {".docx", ".pdf"}


async def upload_and_extract_file(
    session: AsyncSession,
    *,
    file: UploadFile,
    thread_id: str | None,
) -> UploadedFileResponse:
    """保存上传文件并立即解析文本。

    文件内容来自用户或外部文档，永远按“不可信上下文”处理。解析结果可以
    帮助 LLM 起草邮件或日程说明，但不能作为用户确认、授权或系统策略。
    """
    user = await _get_or_create_file_user(session)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件为空。")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件超过 20MB。")

    original_filename = Path(file.filename or "uploaded-file").name
    extension = Path(original_filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="暂不支持该文件类型。")

    await _ensure_thread(session, user, thread_id)
    settings = get_settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    file_id = f"uf_{uuid.uuid4().hex}"
    sha256 = hashlib.sha256(raw).hexdigest()
    storage_path = settings.uploads_dir / f"{file_id}{extension}"
    storage_path.write_bytes(raw)

    timestamp = now_iso()
    await session.execute(
        text(
            """
            INSERT INTO uploaded_files (
                id, user_id, thread_id, original_filename, content_type,
                file_size_bytes, storage_path, sha256, status, created_at, updated_at
            )
            VALUES (
                :id, :user_id, :thread_id, :original_filename, :content_type,
                :file_size_bytes, :storage_path, :sha256, 'uploaded', :created_at, :updated_at
            )
            """
        ),
        {
            "id": file_id,
            "user_id": user.user_id,
            "thread_id": thread_id,
            "original_filename": original_filename,
            "content_type": file.content_type or _content_type_for_extension(extension),
            "file_size_bytes": len(raw),
            "storage_path": str(storage_path),
            "sha256": sha256,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
    await extract_uploaded_file(session, file_id)
    return await get_uploaded_file(session, file_id)


async def list_uploaded_files(
    session: AsyncSession,
    *,
    thread_id: str | None = None,
) -> list[UploadedFileResponse]:
    """列出当前用户上传文件，默认按创建时间倒序。"""
    user = await _get_or_create_file_user(session)
    sql = """
        SELECT id
        FROM uploaded_files
        WHERE user_id = :user_id AND status != 'deleted'
    """
    params: dict[str, Any] = {"user_id": user.user_id}
    if thread_id:
        sql += " AND thread_id = :thread_id"
        params["thread_id"] = thread_id
    sql += " ORDER BY created_at DESC"
    result = await session.execute(text(sql), params)
    return [await get_uploaded_file(session, row["id"]) for row in result.mappings()]


async def get_uploaded_file(session: AsyncSession, uploaded_file_id: str) -> UploadedFileResponse:
    """读取上传文件和最近一次解析结果。"""
    user = await _get_or_create_file_user(session)
    file_result = await session.execute(
        text(
            """
            SELECT
                id, thread_id, original_filename, content_type, file_size_bytes,
                sha256, status, created_at, updated_at
            FROM uploaded_files
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": uploaded_file_id, "user_id": user.user_id},
    )
    row = file_result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="上传文件不存在。")
    extraction = await _latest_extraction(session, uploaded_file_id)
    return UploadedFileResponse(
        id=row["id"],
        thread_id=row["thread_id"],
        original_filename=row["original_filename"],
        content_type=row["content_type"],
        file_size_bytes=row["file_size_bytes"],
        sha256=row["sha256"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        extraction=extraction,
    )


async def extract_uploaded_file(session: AsyncSession, uploaded_file_id: str) -> FileExtractionResponse:
    """重新解析上传文件。"""
    user = await _get_or_create_file_user(session)
    file_result = await session.execute(
        text(
            """
            SELECT id, storage_path, original_filename
            FROM uploaded_files
            WHERE id = :id AND user_id = :user_id AND status != 'deleted'
            """
        ),
        {"id": uploaded_file_id, "user_id": user.user_id},
    )
    row = file_result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="上传文件不存在。")

    extraction_id = f"fx_{uuid.uuid4().hex}"
    timestamp = now_iso()
    storage_path = Path(row["storage_path"])
    extractor_name = _extractor_name(storage_path.suffix.lower())
    try:
        text_content, metadata = _extract_text(storage_path)
        status_value = "succeeded"
        error_message = None
        file_status = "extracted"
    except Exception as exc:
        text_content = None
        metadata = {"filename": row["original_filename"]}
        status_value = "failed"
        error_message = str(exc)
        file_status = "failed"

    await session.execute(
        text(
            """
            INSERT INTO file_extractions (
                id, uploaded_file_id, extractor_name, status, text_content,
                metadata_json, error_message, created_at, updated_at
            )
            VALUES (
                :id, :uploaded_file_id, :extractor_name, :status, :text_content,
                :metadata_json, :error_message, :created_at, :updated_at
            )
            """
        ),
        {
            "id": extraction_id,
            "uploaded_file_id": uploaded_file_id,
            "extractor_name": extractor_name,
            "status": status_value,
            "text_content": text_content,
            "metadata_json": json.dumps(metadata, ensure_ascii=False),
            "error_message": error_message,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text("UPDATE uploaded_files SET status = :status, updated_at = :updated_at WHERE id = :id"),
        {"status": file_status, "updated_at": timestamp, "id": uploaded_file_id},
    )
    await session.commit()
    extraction = await _latest_extraction(session, uploaded_file_id)
    if extraction is None:
        raise RuntimeError("文件解析结果写入失败。")
    return extraction


async def delete_uploaded_file(session: AsyncSession, uploaded_file_id: str) -> None:
    """软删除上传文件，并尝试删除本地原始文件。"""
    user = await _get_or_create_file_user(session)
    result = await session.execute(
        text("SELECT storage_path FROM uploaded_files WHERE id = :id AND user_id = :user_id"),
        {"id": uploaded_file_id, "user_id": user.user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="上传文件不存在。")
    timestamp = now_iso()
    await session.execute(
        text("UPDATE uploaded_files SET status = 'deleted', updated_at = :updated_at WHERE id = :id"),
        {"updated_at": timestamp, "id": uploaded_file_id},
    )
    await session.commit()
    path = Path(row["storage_path"])
    if path.exists():
        path.unlink()


def _extract_text(path: Path) -> tuple[str, dict[str, Any]]:
    """根据文件扩展名分发解析器。"""
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return _extract_text_file(path)
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".pdf":
        return _extract_pdf(path)
    raise ValueError("暂不支持该文件类型。")


def _extract_text_file(path: Path) -> tuple[str, dict[str, Any]]:
    """解析普通文本类文件，按常见编码依次尝试。"""
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            text_content = raw.decode(encoding)
            return _normalize_text(text_content), {"encoding": encoding, "pages": None}
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别文本编码。")


def _extract_docx(path: Path) -> tuple[str, dict[str, Any]]:
    """用标准库解析 DOCX 主文档文本。"""
    paragraphs: list[str] = []
    with zipfile.ZipFile(path) as archive:
        with archive.open("word/document.xml") as document:
            root = ElementTree.fromstring(document.read())
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for paragraph in root.findall(".//w:p", namespace):
        runs = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        text_line = "".join(runs).strip()
        if text_line:
            paragraphs.append(text_line)
    if not paragraphs:
        raise ValueError("DOCX 中没有可解析文本。")
    return _normalize_text("\n".join(paragraphs)), {"paragraphs": len(paragraphs)}


def _extract_pdf(path: Path) -> tuple[str, dict[str, Any]]:
    """使用 pypdf 提取 PDF 文本。"""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("当前环境缺少 pypdf，无法解析 PDF。") from exc

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text_content = _normalize_text("\n".join(pages))
    if not text_content:
        raise ValueError("PDF 中没有可解析文本。")
    return text_content, {"pages": len(reader.pages)}


def _normalize_text(value: str) -> str:
    """清理解析文本，限制超长空白并保留换行结构。"""
    text_content = unescape(value).replace("\x00", "")
    text_content = re.sub(r"[ \t]+", " ", text_content)
    text_content = re.sub(r"\n{3,}", "\n\n", text_content)
    return text_content.strip()


def _extractor_name(extension: str) -> str:
    """返回解析器名称，便于审计和调试。"""
    if extension == ".docx":
        return "docx-stdlib"
    if extension == ".pdf":
        return "pypdf"
    return "plain-text"


def _content_type_for_extension(extension: str) -> str:
    """根据扩展名给出保守 content type。"""
    mapping = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".md": "text/markdown",
        ".html": "text/html",
        ".htm": "text/html",
        ".json": "application/json",
    }
    return mapping.get(extension, "text/plain")


async def _latest_extraction(
    session: AsyncSession,
    uploaded_file_id: str,
) -> FileExtractionResponse | None:
    """读取某个文件最近一次解析结果。"""
    result = await session.execute(
        text(
            """
            SELECT
                id, uploaded_file_id, extractor_name, status, text_content,
                metadata_json, error_message, created_at, updated_at
            FROM file_extractions
            WHERE uploaded_file_id = :uploaded_file_id
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"uploaded_file_id": uploaded_file_id},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return FileExtractionResponse(
        id=row["id"],
        uploaded_file_id=row["uploaded_file_id"],
        extractor_name=row["extractor_name"],
        status=row["status"],
        text_content=row["text_content"],
        metadata=json.loads(row["metadata_json"] or "{}"),
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _get_or_create_file_user(session: AsyncSession) -> ConnectedUser:
    """获取 Google 用户；未连接时创建本地文件用户。

    聊天页允许在未连接 Google 时上传文件做本地解析。外部写操作仍然要求
    Google 授权；这里的本地用户只用于满足 SQLite 外键和文件归属。
    """
    connected = await get_connected_google_user(session)
    if connected is not None:
        return connected
    timestamp = now_iso()
    await session.execute(
        text(
            """
            INSERT OR IGNORE INTO users (id, email, display_name, created_at, updated_at)
            VALUES ('local-file-user', 'local-file-user@localhost', 'Local File User', :created_at, :updated_at)
            """
        ),
        {"created_at": timestamp, "updated_at": timestamp},
    )
    await session.commit()
    return ConnectedUser("local-file-user", "local-file-user@localhost", "Local File User")


async def _ensure_thread(
    session: AsyncSession,
    user: ConnectedUser,
    thread_id: str | None,
) -> None:
    """确保上传文件关联的会话存在。"""
    if not thread_id:
        return
    timestamp = now_iso()
    await session.execute(
        text(
            """
            INSERT OR IGNORE INTO threads (id, user_id, title, summary, status, created_at, updated_at)
            VALUES (:id, :user_id, '文件上传会话', NULL, 'active', :created_at, :updated_at)
            """
        ),
        {
            "id": thread_id,
            "user_id": user.user_id,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.commit()
