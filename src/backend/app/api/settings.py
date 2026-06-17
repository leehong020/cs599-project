from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.settings import (
    ContactCreateRequest,
    ContactResponse,
    ContactUpdateRequest,
    SignatureCreateRequest,
    SignatureResponse,
    SignatureUpdateRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.services.settings import (
    create_contact,
    create_signature,
    delete_contact,
    delete_signature,
    get_user_profile,
    list_contacts,
    list_signatures,
    require_connected_user,
    update_contact,
    update_signature,
    update_user_profile,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/profile", response_model=UserProfileResponse)
async def read_profile(session: AsyncSession = Depends(get_db_session)) -> UserProfileResponse:
    """读取当前 Google 连接账号的用户设置。"""
    user = await require_connected_user(session)
    return await get_user_profile(session, user)


@router.put("/profile", response_model=UserProfileResponse)
async def write_profile(
    payload: UserProfileUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UserProfileResponse:
    """更新当前 Google 连接账号的用户设置。"""
    user = await require_connected_user(session)
    return await update_user_profile(session, user, payload)


@router.get("/signatures", response_model=list[SignatureResponse])
async def read_signatures(
    session: AsyncSession = Depends(get_db_session),
) -> list[SignatureResponse]:
    """列出当前用户的邮件署名。"""
    user = await require_connected_user(session)
    return await list_signatures(session, user)


@router.post(
    "/signatures",
    response_model=SignatureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_signature(
    payload: SignatureCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SignatureResponse:
    """创建邮件署名。"""
    user = await require_connected_user(session)
    return await create_signature(session, user, payload)


@router.put("/signatures/{signature_id}", response_model=SignatureResponse)
async def edit_signature(
    signature_id: str,
    payload: SignatureUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SignatureResponse:
    """更新邮件署名。"""
    user = await require_connected_user(session)
    return await update_signature(session, user, signature_id, payload)


@router.delete("/signatures/{signature_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_signature(
    signature_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """删除邮件署名。"""
    user = await require_connected_user(session)
    await delete_signature(session, user, signature_id)


@router.get("/contacts", response_model=list[ContactResponse])
async def read_contacts(
    session: AsyncSession = Depends(get_db_session),
) -> list[ContactResponse]:
    """列出当前用户联系人。"""
    user = await require_connected_user(session)
    return await list_contacts(session, user)


@router.post(
    "/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_contact(
    payload: ContactCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ContactResponse:
    """创建联系人。"""
    user = await require_connected_user(session)
    return await create_contact(session, user, payload)


@router.put("/contacts/{contact_id}", response_model=ContactResponse)
async def edit_contact(
    contact_id: str,
    payload: ContactUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ContactResponse:
    """更新联系人。"""
    user = await require_connected_user(session)
    return await update_contact(session, user, contact_id, payload)


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_contact(
    contact_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """删除联系人。"""
    user = await require_connected_user(session)
    await delete_contact(session, user, contact_id)
