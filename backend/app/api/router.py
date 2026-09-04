from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_current_settings, get_db_session
from app.modules.accounts.router import account_types_router
from app.modules.accounts.router import router as accounts_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.branches.router import router as branches_router
from app.modules.cashbook.router import router as cashbook_router
from app.modules.companies.router import router as companies_router
from app.modules.customers.router import router as customers_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.expenses.router import router as expenses_router
from app.modules.jobs.router import router as jobs_router
from app.modules.notifications.router import router as notifications_router
from app.modules.numbering.router import router as numbering_router
from app.modules.reports.router import router as reports_router
from app.modules.roles.router import router as roles_router
from app.modules.transactions.router import router as transactions_router
from app.modules.users.router import router as users_router
from app.modules.vendors.router import router as vendors_router

api_router = APIRouter()
api_router.include_router(companies_router)
api_router.include_router(cashbook_router)
api_router.include_router(accounts_router)
api_router.include_router(account_types_router)
api_router.include_router(numbering_router)
api_router.include_router(customers_router)
api_router.include_router(vendors_router)
api_router.include_router(expenses_router)
api_router.include_router(branches_router)
api_router.include_router(auth_router)
api_router.include_router(roles_router)
api_router.include_router(users_router)
api_router.include_router(transactions_router)
api_router.include_router(dashboard_router)
api_router.include_router(reports_router)
api_router.include_router(audit_router)
api_router.include_router(notifications_router)
api_router.include_router(jobs_router)


@api_router.get("/health", tags=["system"])
async def health(settings: Annotated[Settings, Depends(get_current_settings)]) -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@api_router.get("/readiness", tags=["system"])
async def readiness(session: Annotated[AsyncSession, Depends(get_db_session)]) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}
