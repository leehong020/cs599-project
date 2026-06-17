from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.files import UploadedFileListResponse, UploadedFileResponse
from app.services.files import (
    delete_uploaded_file,
    extract_uploaded_file,
    get_uploaded_file,
    list_uploaded_files,
    upload_and_extract_file,
)

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", response_model=UploadedFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    thread_id: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> UploadedFileResponse:
    """上传文件并立即解析文本。"""
    return await upload_and_extract_file(session, file=file, thread_id=thread_id)


@router.get("", response_model=UploadedFileListResponse)
async def read_files(
    thread_id: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> UploadedFileListResponse:
    """读取当前用户或本地文件用户的上传文件列表。"""
    return UploadedFileListResponse(items=await list_uploaded_files(session, thread_id=thread_id))


@router.get("/{uploaded_file_id}", response_model=UploadedFileResponse)
async def read_file(
    uploaded_file_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> UploadedFileResponse:
    """读取单个上传文件及最近解析结果。"""
    return await get_uploaded_file(session, uploaded_file_id)


@router.post("/{uploaded_file_id}/extract", response_model=UploadedFileResponse)
async def extract_file(
    uploaded_file_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> UploadedFileResponse:
    """重新解析上传文件。"""
    await extract_uploaded_file(session, uploaded_file_id)
    return await get_uploaded_file(session, uploaded_file_id)


@router.delete("/{uploaded_file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_file(
    uploaded_file_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """软删除上传文件并移除本地原始文件。"""
    await delete_uploaded_file(session, uploaded_file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
