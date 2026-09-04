from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.modules.reports.export import EXPORTERS
from app.modules.reports.permissions import EXPORT_REPORTS, VIEW_REPORTS
from app.modules.reports.schemas import ExportFormat, ReportFilters, ReportPage, ReportType
from app.modules.reports.service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
ReadContext = Annotated[
    RequestContext, Depends(require_permission(VIEW_REPORTS, allow_any_company=True))
]
ExportContext = Annotated[
    RequestContext, Depends(require_permission(EXPORT_REPORTS, allow_any_company=True))
]


def _report_type(value: str) -> ReportType:
    try:
        return ReportType.parse(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _filters(
    context: RequestContext,
    company_id: UUID | None,
    branch_id: UUID | None,
    financial_year_id: UUID | None,
    start_date: date | None,
    end_date: date | None,
    account_id: UUID | None,
    customer_id: UUID | None,
    vendor_id: UUID | None,
    category_id: UUID | None,
    status: str | None,
    user_id: UUID | None,
) -> ReportFilters:
    scoped_company = company_id if context.is_dev_context else context.company_id
    scoped_branch = branch_id if context.is_dev_context else context.branch_id
    if scoped_company is None:
        raise HTTPException(status_code=422, detail="company_id is required.")
    return ReportFilters(
        company_id=scoped_company,
        branch_id=scoped_branch,
        financial_year_id=financial_year_id,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        customer_id=customer_id,
        vendor_id=vendor_id,
        category_id=category_id,
        status=status,
        user_id=user_id,
    )


async def _run(
    report_type: str,
    session: AsyncSession,
    context: RequestContext,
    page: int,
    page_size: int,
    company_id: UUID | None,
    branch_id: UUID | None,
    financial_year_id: UUID | None,
    start_date: date | None,
    end_date: date | None,
    account_id: UUID | None,
    customer_id: UUID | None,
    vendor_id: UUID | None,
    category_id: UUID | None,
    status: str | None,
    user_id: UUID | None,
    export: bool = False,
) -> ReportPage:
    filters = _filters(
        context,
        company_id,
        branch_id,
        financial_year_id,
        start_date,
        end_date,
        account_id,
        customer_id,
        vendor_id,
        category_id,
        status,
        user_id,
    )
    return await ReportService(session).run(
        report_type,
        filters,
        page=page,
        page_size=page_size,
        user_id=context.user_id,
        is_dev_context=context.is_dev_context,
        export=export,
    )


@router.get("/{report_type}", response_model=ReportPage)
async def get_report(
    report_type: str,
    session: Session,
    context: ReadContext,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    financial_year_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: UUID | None = None,
    customer_id: UUID | None = None,
    vendor_id: UUID | None = None,
    category_id: UUID | None = None,
    status: str | None = None,
    user_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=5000),
) -> ReportPage:
    return await _run(
        _report_type(report_type),
        session,
        context,
        page,
        page_size,
        company_id,
        branch_id,
        financial_year_id,
        start_date,
        end_date,
        account_id,
        customer_id,
        vendor_id,
        category_id,
        status,
        user_id,
    )


@router.get("/{report_type}/export")
async def export_report(
    report_type: str,
    session: Session,
    context: ExportContext,
    format: ExportFormat = ExportFormat.CSV,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    financial_year_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: UUID | None = None,
    customer_id: UUID | None = None,
    vendor_id: UUID | None = None,
    category_id: UUID | None = None,
    status: str | None = None,
    user_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(5000, ge=1, le=5000),
) -> Response:
    parsed_type = _report_type(report_type)
    report = await _run(
        parsed_type,
        session,
        context,
        page,
        page_size,
        company_id,
        branch_id,
        financial_year_id,
        start_date,
        end_date,
        account_id,
        customer_id,
        vendor_id,
        category_id,
        status,
        user_id,
        export=True,
    )
    exporter = EXPORTERS[format.value]
    return Response(
        content=exporter.render(report),
        media_type=exporter.media_type,
        headers={"Content-Disposition": f'attachment; filename="{parsed_type.value}.{exporter.extension}"'},
    )
