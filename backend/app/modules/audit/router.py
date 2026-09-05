from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.audit.schemas import AuditLogFilters, AuditLogListResponse
from app.modules.audit.service import AuditService

router = APIRouter(tags=["audit"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
AuditContext = Annotated[
    RequestContext,
    Depends(require_permission("audit.audit.view", allow_any_company=True)),
]


@router.get("/audit/logs", response_model=AuditLogListResponse)
@router.get("/audit-logs", response_model=AuditLogListResponse, include_in_schema=False)
async def list_audit_logs(
    session: Session,
    context: AuditContext,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: UUID | None = None,
    module: str | None = None,
    action: str | None = None,
    entity: str | None = None,
    entity_type: str | None = Query(default=None, include_in_schema=False),
    entity_id: UUID | None = None,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(25, ge=1, le=100),
):
    filters = AuditLogFilters(
        date_from=date_from, date_to=date_to, user_id=user_id, module=module,
        action=action, entity=entity or entity_type, entity_id=entity_id, company_id=company_id,
        branch_id=branch_id, page=page, page_size=page_size,
    )
    return await AuditService(session).list(context.user_id, filters, context.is_dev_context)
