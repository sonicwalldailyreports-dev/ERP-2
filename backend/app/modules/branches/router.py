from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.branches.schemas import BranchCreate, BranchRead, BranchUpdate
from app.modules.branches.service import BranchService

router = APIRouter(prefix="/companies/{company_id}/branches", tags=["branches"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
ReadContext = Annotated[RequestContext, Depends(require_permission("branches.branch.view", company_param="company_id", branch_param="branch_id"))]
CreateContext = Annotated[RequestContext, Depends(require_permission("branches.branch.create", company_param="company_id"))]
UpdateContext = Annotated[RequestContext, Depends(require_permission("branches.branch.edit", company_param="company_id", branch_param="branch_id"))]
ActivateContext = Annotated[RequestContext, Depends(require_permission("branches.branch.activate", company_param="company_id", branch_param="branch_id"))]


@router.get("", response_model=list[BranchRead])
async def list_branches(company_id: UUID, session: Session, context: ReadContext):
    return await BranchService(session).list(company_id, context.user_id)


@router.post("", response_model=BranchRead, status_code=status.HTTP_201_CREATED)
async def create_branch(company_id: UUID, data: BranchCreate, session: Session, context: CreateContext):
    if data.company_id != company_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Branch company does not match route company.")
    return await BranchService(session).create(data, context.user_id)


@router.get("/{branch_id}", response_model=BranchRead)
async def get_branch(company_id: UUID, branch_id: UUID, session: Session, context: ReadContext):
    return await BranchService(session).get(company_id, branch_id, context.user_id)


@router.patch("/{branch_id}", response_model=BranchRead)
async def update_branch(company_id: UUID, branch_id: UUID, data: BranchUpdate, session: Session, context: UpdateContext):
    return await BranchService(session).update(company_id, branch_id, data, context.user_id)


@router.post("/{branch_id}/activate", response_model=BranchRead)
async def activate_branch(company_id: UUID, branch_id: UUID, session: Session, context: ActivateContext):
    return await BranchService(session).set_active(company_id, branch_id, True, context.user_id)


@router.post("/{branch_id}/deactivate", response_model=BranchRead)
async def deactivate_branch(company_id: UUID, branch_id: UUID, session: Session, context: ActivateContext):
    return await BranchService(session).set_active(company_id, branch_id, False, context.user_id)
