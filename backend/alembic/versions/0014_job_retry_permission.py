"""Add the administrator permission for retrying background jobs."""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "0014_job_retry_permission"
down_revision = "0013_background_processing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    if bind.execute(sa.select(permissions.c.id).where(permissions.c.code == "jobs.job.retry")).first() is None:
        bind.execute(
            permissions.insert().values(
                id=uuid.uuid4(),
                code="jobs.job.retry",
                description="Retry failed background jobs",
                is_active=True,
            )
        )


def downgrade() -> None:
    permissions = sa.table("permissions", sa.column("code", sa.String()))
    op.get_bind().execute(permissions.delete().where(permissions.c.code == "jobs.job.retry"))
