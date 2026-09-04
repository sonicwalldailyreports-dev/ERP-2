from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.companies.schemas import CompanyCreate, CompanyRead, CompanyUpdate
from app.modules.companies.service import CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
ReadContext = Annotated[RequestContext, Depends(require_permission("companies.company.view", allow_any_company=True))]
CreateContext = Annotated[RequestContext, Depends(require_permission("companies.company.create"))]
UpdateContext = Annotated[RequestContext, Depends(require_permission("companies.company.edit", company_param="company_id"))]
ActivateContext = Annotated[RequestContext, Depends(require_permission("companies.company.activate", company_param="company_id"))]


@router.get("", response_model=list[CompanyRead])
async def list_companies(session: Session, context: ReadContext):
    return await CompanyService(session).list(context.user_id)


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def create_company(data: CompanyCreate, session: Session, context: CreateContext):
    return await CompanyService(session).create(data, context.user_id)


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(company_id: UUID, session: Session, context: ReadContext):
    return await CompanyService(session).get(company_id, context.user_id)


@router.patch("/{company_id}", response_model=CompanyRead)
async def update_company(company_id: UUID, data: CompanyUpdate, session: Session, context: UpdateContext):
    return await CompanyService(session).update(company_id, data, context.user_id)


@router.post("/{company_id}/activate", response_model=CompanyRead)
async def activate_company(company_id: UUID, session: Session, context: ActivateContext):
    return await CompanyService(session).set_active(company_id, True, context.user_id)


@router.post("/{company_id}/deactivate", response_model=CompanyRead)
async def deactivate_company(company_id: UUID, session: Session, context: ActivateContext):
    return await CompanyService(session).set_active(company_id, False, context.user_id)
