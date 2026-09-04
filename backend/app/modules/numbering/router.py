from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.numbering.schemas import (
    GeneratedNumberRead,
    NumberSequenceCreate,
    NumberSequenceNextRequest,
    NumberSequenceRead,
    NumberSequenceUpdate,
)
from app.modules.numbering.service import NumberingService

router = APIRouter(prefix="/number-sequences", tags=["numbering"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
ReadContext = Annotated[
    RequestContext, Depends(require_permission("numbering.sequence.view", allow_any_company=True))
]
CreateContext = Annotated[
    RequestContext, Depends(require_permission("numbering.sequence.create", allow_any_company=True))
]
GenerateContext = Annotated[
    RequestContext, Depends(require_permission("numbering.sequence.generate", allow_any_company=True))
]
ManageContext = Annotated[
    RequestContext, Depends(require_permission("numbering.sequence.edit", allow_any_company=True))
]


@router.get("", response_model=list[NumberSequenceRead])
async def list_sequences(
    session: Session, context: ReadContext, company_id: UUID | None = None, branch_id: UUID | None = None
):
    company = company_id if context.is_dev_context else context.company_id
    branch = branch_id if context.is_dev_context else context.branch_id
    if company is None:
        raise HTTPException(status_code=422, detail="company_id is required.")
    return await NumberingService(session).list(company, branch)


@router.post("", response_model=NumberSequenceRead, status_code=status.HTTP_201_CREATED)
async def create_sequence(data: NumberSequenceCreate, session: Session, context: CreateContext):
    return await NumberingService(session).create(data, context.user_id, context.is_dev_context)


@router.post("/next", response_model=GeneratedNumberRead)
async def generate_next(
    data: NumberSequenceNextRequest, session: Session, context: GenerateContext
):
    return await NumberingService(session).generate(
        data.sequence_id, context.user_id, context.is_dev_context
    )


@router.patch("/{sequence_id}", response_model=NumberSequenceRead)
async def update_sequence(
    sequence_id: UUID, data: NumberSequenceUpdate, session: Session, context: ManageContext
):
    return await NumberingService(session).update(
        sequence_id, data, context.user_id, context.is_dev_context
    )
