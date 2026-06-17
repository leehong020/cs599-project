from io import BytesIO
import zipfile

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.datastructures import UploadFile

from app.services.files import delete_uploaded_file, upload_and_extract_file


@pytest_asyncio.fixture
async def file_session(tmp_path, monkeypatch) -> AsyncSession:
    """创建文件解析测试用内存数据库和隔离上传目录。"""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("LANGGRAPH_DB_PATH", str(tmp_path / "graph.sqlite3"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        for statement in FILE_TEST_SCHEMA:
            await connection.execute(text(statement))
    async with session_factory() as session:
        yield session
    await engine.dispose()
    get_settings.cache_clear()


FILE_TEST_SCHEMA = [
    """
    CREATE TABLE users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        display_name TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE oauth_credentials (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        encrypted_access_token TEXT NOT NULL,
        encrypted_refresh_token TEXT,
        scopes_json TEXT NOT NULL,
        expires_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE threads (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT,
        summary TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE uploaded_files (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        thread_id TEXT,
        original_filename TEXT NOT NULL,
        content_type TEXT NOT NULL,
        file_size_bytes INTEGER NOT NULL,
        storage_path TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE file_extractions (
        id TEXT PRIMARY KEY,
        uploaded_file_id TEXT NOT NULL,
        extractor_name TEXT NOT NULL,
        status TEXT NOT NULL,
        text_content TEXT,
        metadata_json TEXT,
        error_message TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
]


@pytest.mark.asyncio
async def test_upload_text_file_extracts_content(file_session: AsyncSession) -> None:
    upload = UploadFile(filename="brief.md", file=BytesIO("项目延期一天。".encode("utf-8")))

    result = await upload_and_extract_file(file_session, file=upload, thread_id="thread_file")

    assert result.status == "extracted"
    assert result.thread_id == "thread_file"
    assert result.extraction is not None
    assert result.extraction.status == "succeeded"
    assert "项目延期一天" in (result.extraction.text_content or "")


@pytest.mark.asyncio
async def test_upload_docx_file_extracts_paragraphs(file_session: AsyncSession) -> None:
    upload = UploadFile(filename="brief.docx", file=BytesIO(_minimal_docx_bytes()))

    result = await upload_and_extract_file(file_session, file=upload, thread_id=None)

    assert result.status == "extracted"
    assert result.extraction is not None
    assert result.extraction.extractor_name == "docx-stdlib"
    assert "第一段" in (result.extraction.text_content or "")
    assert "第二段" in (result.extraction.text_content or "")


@pytest.mark.asyncio
async def test_delete_uploaded_file_marks_deleted(file_session: AsyncSession) -> None:
    upload = UploadFile(filename="brief.txt", file=BytesIO(b"hello"))
    result = await upload_and_extract_file(file_session, file=upload, thread_id=None)

    await delete_uploaded_file(file_session, result.id)
    row = await file_session.execute(
        text("SELECT status FROM uploaded_files WHERE id = :id"),
        {"id": result.id},
    )

    assert row.scalar_one() == "deleted"


def _minimal_docx_bytes() -> bytes:
    """构造最小 DOCX，避免测试依赖 Word 或 python-docx。"""
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>第一段</w:t></w:r></w:p>
        <w:p><w:r><w:t>第二段</w:t></w:r></w:p>
      </w:body>
    </w:document>
    """
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()
