"""Add durable notifications and background job records."""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "0013_background_processing"
down_revision = "0012_production_audit"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("notifications.notification.view", "View in-app notifications"),
    ("jobs.job.view", "View background jobs"),
    ("jobs.job.retry", "Retry failed background jobs"),
)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "notifications" not in tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("company_id", sa.Uuid()),
            sa.Column("branch_id", sa.Uuid()),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("payload", sa.JSON()),
            sa.Column("idempotency_key", sa.String(255), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key", name="uq_notifications_idempotency_key"),
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
        op.create_index("ix_notifications_event_type", "notifications", ["event_type"])
        op.create_index("ix_notifications_user_unread_created", "notifications", ["user_id", "read_at", "created_at"])
        op.create_index("ix_notifications_company_created", "notifications", ["company_id", "created_at"])
    if "background_jobs" not in tables:
        op.create_table(
            "background_jobs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("kind", sa.String(100), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("idempotency_key", sa.String(255), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column("last_error", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key", name="uq_background_jobs_idempotency_key"),
        )
        op.create_index("ix_background_jobs_kind", "background_jobs", ["kind"])
        op.create_index("ix_background_jobs_status_available", "background_jobs", ["status", "available_at"])
        op.create_index("ix_background_jobs_kind_created", "background_jobs", ["kind", "created_at"])

    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    existing = {row[0] for row in bind.execute(sa.select(permission_table.c.code)).all()}
    rows = [
        {"id": uuid.uuid4(), "code": code, "description": description, "is_active": True}
        for code, description in PERMISSIONS
        if code not in existing
    ]
    if rows:
        bind.execute(permission_table.insert(), rows)


def downgrade() -> None:
    bind = op.get_bind()
    permission_table = sa.table("permissions", sa.column("code", sa.String()))
    bind.execute(permission_table.delete().where(permission_table.c.code.in_([row[0] for row in PERMISSIONS])))
    for name, table in (
        ("ix_background_jobs_kind_created", "background_jobs"),
        ("ix_background_jobs_status_available", "background_jobs"),
        ("ix_background_jobs_kind", "background_jobs"),
        ("ix_notifications_company_created", "notifications"),
        ("ix_notifications_user_unread_created", "notifications"),
        ("ix_notifications_event_type", "notifications"),
        ("ix_notifications_user_id", "notifications"),
    ):
        op.drop_index(name, table_name=table)
    op.drop_table("background_jobs")
    op.drop_table("notifications")
