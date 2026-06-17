from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.completeness import (
    CompletenessResult,
    DraftValidationRequest,
    FieldEvidenceListResponse,
    FieldEvidenceRecord,
    FieldEvidenceUpsertRequest,
)
from app.services.completeness import (
    list_field_evidence,
    upsert_field_evidence,
    validate_draft_by_type,
)

router = APIRouter(tags=["completeness"])


@router.post("/completeness/validate", response_model=CompletenessResult)
async def validate_draft(payload: DraftValidationRequest) -> CompletenessResult:
    """校验草稿是否具备进入 Proposal 的字段条件。

    这个接口只做“字段和值来源是否足够”的判断，不会写 Gmail、
    不会写 Calendar，也不会创建 Proposal。
    """
    return validate_draft_by_type(payload.draft_type, payload.draft, payload.evidence)


@router.get(
    "/artifacts/{artifact_id}/field-evidence",
    response_model=FieldEvidenceListResponse,
)
async def read_artifact_field_evidence(
    artifact_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> FieldEvidenceListResponse:
    """查询某个 Artifact 的字段来源列表。"""
    return FieldEvidenceListResponse(
        artifact_id=artifact_id,
        items=await list_field_evidence(session, artifact_id),
    )


@router.post(
    "/artifacts/{artifact_id}/field-evidence",
    response_model=FieldEvidenceRecord,
    status_code=status.HTTP_201_CREATED,
)
async def write_artifact_field_evidence(
    artifact_id: str,
    payload: FieldEvidenceUpsertRequest,
    session: AsyncSession = Depends(get_db_session),
) -> FieldEvidenceRecord:
    """记录用户补充或系统解析得到的字段来源。"""
    return await upsert_field_evidence(session, artifact_id, payload)
