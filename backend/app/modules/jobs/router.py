from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import RequestContext, require_permission
from app.core.audit import redact_sensitive
from app.core.dependencies import get_db_session
from app.db.models import BackgroundJob

router = APIRouter(prefix="/jobs", tags=["jobs"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Context = Annotated[
    RequestContext,
    Depends(
        require_permission(
            "jobs.job.view", company_param="company_id", branch_param="branch_id", allow_any_company=True
        )
    ),
]
RetryContext = Annotated[
    RequestContext,
    Depends(
        require_permission(
            "jobs.job.retry", company_param="company_id", branch_param="branch_id", allow_any_company=True
        )
    ),
]


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    status: str
    payload: dict
    idempotency_key: str
    attempts: int
    max_attempts: int
    available_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    last_error: str | None
    created_at: datetime

    @field_serializer("payload")
    def serialize_payload(self, payload: dict) -> dict:
        return redact_sensitive(payload)


@router.get("", response_model=list[JobRead])
async def list_jobs(session: Session, context: Context, status: str | None = None, limit: int = 100):
    query = select(BackgroundJob)
    if not context.is_dev_context and context.company_id is None:
        raise HTTPException(status_code=422, detail="company_id is required.")
    if context.company_id is not None:
        query = query.where(BackgroundJob.company_id == context.company_id)
    if context.branch_id is not None:
        query = query.where(BackgroundJob.branch_id == context.branch_id)
    if status:
        query = query.where(BackgroundJob.status == status)
    return list(await session.scalars(query.order_by(BackgroundJob.created_at.desc()).limit(max(1, min(limit, 500)))))


@router.post("/{job_id}/retry", response_model=JobRead)
async def retry_job(job_id: UUID, session: Session, context: RetryContext):
    if not context.is_dev_context and context.company_id is None:
        raise HTTPException(status_code=422, detail="company_id is required.")
    query = select(BackgroundJob).where(BackgroundJob.id == job_id)
    if context.company_id is not None:
        query = query.where(BackgroundJob.company_id == context.company_id)
    if context.branch_id is not None:
        query = query.where(BackgroundJob.branch_id == context.branch_id)
    job = await session.scalar(query)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status not in {"failed", "pending"}:
        raise HTTPException(status_code=409, detail="Only failed or pending jobs can be retried.")
    job.status, job.last_error, job.available_at = "pending", None, datetime.now(UTC)
    await session.commit()
    await session.refresh(job)
    return job
