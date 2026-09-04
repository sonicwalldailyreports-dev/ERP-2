from __future__ import annotations

from math import ceil
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import has_permission
from app.modules.reports.permissions import EXPORT_REPORTS, VIEW_REPORTS
from app.modules.reports.repository import ReportRepository
from app.modules.reports.schemas import ReportFilters, ReportPage, ReportType


class ReportService:
    """Application service shared by JSON, CSV, XLSX and future job workers."""

    def __init__(self, session: AsyncSession):
        self.repository = ReportRepository(session)
        self.session = session

    async def _filters(
        self,
        filters: ReportFilters,
        *,
        user_id: UUID | None,
        is_dev_context: bool,
        export: bool = False,
    ) -> ReportFilters:
        if not await self.repository.company_exists(filters.company_id):
            raise HTTPException(status_code=404, detail="Company not found.")
        if filters.branch_id and not await self.repository.branch_exists(filters.company_id, filters.branch_id):
            raise HTTPException(status_code=404, detail="Branch not found for this company.")
        if not is_dev_context and user_id is not None:
            permission = EXPORT_REPORTS if export else VIEW_REPORTS
            if not await has_permission(
                self.session, user_id, permission, filters.company_id, filters.branch_id
            ):
                raise HTTPException(status_code=403, detail="Permission denied.")

        year = await self.repository.financial_year(filters.company_id, filters.financial_year_id)
        if year is None:
            raise HTTPException(status_code=404, detail="Financial year not found.")
        start = filters.start_date or year.start_date
        end = filters.end_date or year.end_date
        if start < year.start_date or end > year.end_date or start > end:
            raise HTTPException(status_code=422, detail="Date range must be within the financial year.")
        return filters.model_copy(
            update={"financial_year_id": year.id, "start_date": start, "end_date": end}
        )

    async def run(
        self,
        report_type: ReportType,
        filters: ReportFilters,
        *,
        page: int = 1,
        page_size: int = 50,
        user_id: UUID | None = None,
        is_dev_context: bool = False,
        export: bool = False,
    ) -> ReportPage:
        if page < 1 or page_size < 1 or page_size > 5000:
            raise HTTPException(status_code=422, detail="Invalid pagination values.")
        scoped = await self._filters(
            filters, user_id=user_id, is_dev_context=is_dev_context, export=export
        )
        items, total, totals, pages = await self.repository.fetch(report_type, scoped, page, page_size)
        return ReportPage(
            report_type=report_type,
            company_id=scoped.company_id,
            branch_id=scoped.branch_id,
            financial_year_id=scoped.financial_year_id,
            start_date=scoped.start_date,
            end_date=scoped.end_date,
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages if pages is not None else ceil(total / page_size) if total else 0,
            totals=totals,
        )

    async def validate_export(
        self, filters: ReportFilters, *, user_id: UUID, is_dev_context: bool
    ) -> ReportFilters:
        return await self._filters(
            filters, user_id=user_id, is_dev_context=is_dev_context, export=True
        )
