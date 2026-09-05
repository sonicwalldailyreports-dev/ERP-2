from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.dependencies import get_db_session
from app.db.models import ExpenseCategory
from app.modules.expenses.schemas import (
    ExpenseCancel,
    ExpenseCategoryCreate,
    ExpenseCategoryRead,
    ExpenseCategoryUpdate,
    ExpenseCorrection,
    ExpenseCreate,
    ExpenseRead,
    ExpenseReject,
    ExpenseUpdate,
)
from app.modules.expenses.service import ExpenseService

router = APIRouter(prefix="/expenses", tags=["expenses"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Read = Annotated[RequestContext, Depends(require_permission("expenses.expense.view", allow_any_company=True))]
Create = Annotated[RequestContext, Depends(require_permission("expenses.expense.create", allow_any_company=True))]
Edit = Annotated[RequestContext, Depends(require_permission("expenses.expense.edit", allow_any_company=True))]
Submit = Annotated[RequestContext, Depends(require_permission("expenses.expense.submit", allow_any_company=True))]
Approve = Annotated[RequestContext, Depends(require_permission("expenses.expense.approve", allow_any_company=True))]
Post = Annotated[RequestContext, Depends(require_permission("expenses.expense.post", allow_any_company=True))]
Reject = Annotated[RequestContext, Depends(require_permission("expenses.expense.reject", allow_any_company=True))]
Cancel = Annotated[RequestContext, Depends(require_permission("expenses.expense.cancel", allow_any_company=True))]
Reverse = Annotated[RequestContext, Depends(require_permission("expenses.expense.reverse", allow_any_company=True))]
Adjust = Annotated[RequestContext, Depends(require_permission("expenses.expense.adjust", allow_any_company=True))]
CategoryManage = Annotated[RequestContext, Depends(require_permission("expenses.category.create", allow_any_company=True))]
CategoryRead = Annotated[RequestContext, Depends(require_permission("expenses.category.view", allow_any_company=True))]
CategoryEdit = Annotated[RequestContext, Depends(require_permission("expenses.category.edit", allow_any_company=True))]


def _company(context: RequestContext, company_id: UUID | None) -> UUID:
    value = company_id if context.is_dev_context else context.company_id
    if value is None:
        raise HTTPException(status_code=422, detail="company_id is required.")
    return value


@router.get("/categories", response_model=list[ExpenseCategoryRead])
async def list_categories(
    session: Session, context: CategoryRead, company_id: UUID | None = None, branch_id: UUID | None = None
):
    return await ExpenseService(session).list_categories(
        _company(context, company_id), branch_id if context.is_dev_context else context.branch_id
    )


@router.post("/categories", response_model=ExpenseCategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(data: ExpenseCategoryCreate, session: Session, context: CategoryManage):
    return await ExpenseService(session).create_category(data, context.user_id, context.is_dev_context)


@router.get("/categories/{category_id}", response_model=ExpenseCategoryRead)
async def get_category(category_id: UUID, session: Session, context: CategoryRead):
    category = await session.scalar(select(ExpenseCategory).where(ExpenseCategory.id == category_id))
    if category is None:
        raise HTTPException(status_code=404, detail="Expense category not found.")
    await ExpenseService(session)._allowed(
        context.user_id, "expenses.category.view", category.company_id, category.branch_id, context.is_dev_context
    )
    return category


@router.patch("/categories/{category_id}", response_model=ExpenseCategoryRead)
async def update_category(
    category_id: UUID, data: ExpenseCategoryUpdate, session: Session, context: CategoryEdit
):
    return await ExpenseService(session).update_category(
        category_id, data, context.user_id, context.is_dev_context
    )


@router.get("/approval-queue", response_model=list[ExpenseRead])
async def approval_queue(
    session: Session, context: Read, company_id: UUID | None = None, branch_id: UUID | None = None
):
    return await ExpenseService(session).list(
        _company(context, company_id), branch_id if context.is_dev_context else context.branch_id,
        "SUBMITTED", None, None, None, None, context.user_id, context.is_dev_context,
    )


@router.get("", response_model=list[ExpenseRead])
async def list_expenses(
    session: Session,
    context: Read,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    expense_status: str | None = Query(default=None, alias="status"),
    category_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
):
    return await ExpenseService(session).list(
        _company(context, company_id), branch_id if context.is_dev_context else context.branch_id,
        expense_status, category_id, start_date, end_date, search,
        context.user_id, context.is_dev_context,
    )


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(data: ExpenseCreate, session: Session, context: Create):
    return await ExpenseService(session).create(data, context.user_id, context.is_dev_context)


@router.get("/{expense_id}", response_model=ExpenseRead)
async def get_expense(expense_id: UUID, session: Session, context: Read):
    return await ExpenseService(session).get(expense_id, context.user_id, context.is_dev_context)


@router.patch("/{expense_id}", response_model=ExpenseRead)
async def update_expense(
    expense_id: UUID, data: ExpenseUpdate, session: Session, context: Edit
):
    return await ExpenseService(session).update(
        expense_id, data, context.user_id, context.is_dev_context
    )


@router.post("/{expense_id}/submit", response_model=ExpenseRead)
async def submit_expense(expense_id: UUID, session: Session, context: Submit):
    return await ExpenseService(session).transition(
        expense_id, "SUBMITTED", context.user_id, context.is_dev_context
    )


@router.post("/{expense_id}/approve", response_model=ExpenseRead)
async def approve_expense(expense_id: UUID, session: Session, context: Approve):
    return await ExpenseService(session).transition(
        expense_id, "APPROVED", context.user_id, context.is_dev_context
    )


@router.post("/{expense_id}/post", response_model=ExpenseRead)
async def post_expense(expense_id: UUID, session: Session, context: Post):
    return await ExpenseService(session).transition(
        expense_id, "POSTED", context.user_id, context.is_dev_context
    )


@router.post("/{expense_id}/reject", response_model=ExpenseRead)
async def reject_expense(
    expense_id: UUID, data: ExpenseReject, session: Session, context: Reject
):
    return await ExpenseService(session).transition(
        expense_id, "REJECTED", context.user_id, context.is_dev_context, data.reason
    )


@router.post("/{expense_id}/cancel", response_model=ExpenseRead)
async def cancel_expense(
    expense_id: UUID, data: ExpenseCancel, session: Session, context: Cancel
):
    return await ExpenseService(session).transition(
        expense_id, "CANCELLED", context.user_id, context.is_dev_context, data.reason
    )


@router.post("/{expense_id}/reverse", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def reverse_expense(expense_id: UUID, session: Session, context: Reverse):
    return await ExpenseService(session).reverse(expense_id, context.user_id, context.is_dev_context)


@router.post("/{expense_id}/adjust", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def adjust_expense(
    expense_id: UUID, data: ExpenseCorrection, session: Session, context: Adjust
):
    return await ExpenseService(session).correct(
        expense_id, data, context.user_id, context.is_dev_context
    )


@router.get("/{expense_id}/history")
async def expense_history(expense_id: UUID, session: Session, context: Read):
    rows = await ExpenseService(session).history(expense_id, context.user_id, context.is_dev_context)
    return [
        {"id": row.id, "action": row.action, "user_id": row.user_id, "details": row.details, "created_at": row.created_at}
        for row in rows
    ]
