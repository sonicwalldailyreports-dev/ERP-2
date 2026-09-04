from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import DashboardResponse
from app.modules.dashboard.service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
ReadContext = Annotated[
    RequestContext,
    Depends(require_permission("dashboard.view", allow_any_company=True)),
]


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    session: Session,
    context: ReadContext,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    financial_year_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> DashboardResponse:
    scoped_company = company_id if context.is_dev_context else context.company_id
    scoped_branch = branch_id if context.is_dev_context else context.branch_id
    if scoped_company is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="company_id is required.")
    return await DashboardService(DashboardRepository(session)).build(
        user_id=context.user_id,
        company_id=scoped_company,
        branch_id=scoped_branch,
        financial_year_id=financial_year_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
        is_dev_context=context.is_dev_context,
    )
