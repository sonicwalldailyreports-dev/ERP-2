"""Harden audit logs and add searchable request/change metadata."""

import uuid

import sqlalchemy as sa
from sqlalchemy import inspect, select

from alembic import op

revision = "0012_production_audit"
down_revision = "0011_financial_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("audit_logs")}
    additions = (
        ("module", sa.String(length=80), "system"),
        ("before_data", sa.JSON(), None),
        ("after_data", sa.JSON(), None),
        ("ip_address", sa.String(length=64), None),
        ("user_agent", sa.String(length=512), None),
        ("request_id", sa.String(length=128), None),
    )
    for name, column_type, default in additions:
        if name not in columns:
            kwargs = {"nullable": False, "server_default": default} if name == "module" else {"nullable": True}
            op.add_column("audit_logs", sa.Column(name, column_type, **kwargs))

    existing_indexes = {index["name"] for index in inspector.get_indexes("audit_logs")}
    indexes = (
        ("ix_audit_logs_user_created_at", ["user_id", "created_at"]),
        ("ix_audit_logs_module_action_created_at", ["module", "action", "created_at"]),
        ("ix_audit_logs_entity", ["entity_type", "entity_id", "created_at"]),
        ("ix_audit_logs_branch_created_at", ["branch_id", "created_at"]),
        ("ix_audit_logs_request_id", ["request_id"]),
    )
    for name, columns_for_index in indexes:
        if name not in existing_indexes:
            op.create_index(name, "audit_logs", columns_for_index)

    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    if bind.execute(select(permission_table.c.id).where(permission_table.c.code == "audit.audit.view")).first() is None:
        bind.execute(
            permission_table.insert().values(
                id=uuid.uuid4(),
                code="audit.audit.view",
                description="View immutable audit logs",
                is_active=True,
            )
        )

    if bind.dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER IF NOT EXISTS audit_logs_no_update "
            "BEFORE UPDATE ON audit_logs BEGIN SELECT RAISE(ABORT, 'audit_logs are append-only'); END"
        )
        op.execute(
            "CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete "
            "BEFORE DELETE ON audit_logs BEGIN SELECT RAISE(ABORT, 'audit_logs are append-only'); END"
        )
    elif bind.dialect.name == "postgresql":
        op.execute(
            "CREATE OR REPLACE FUNCTION prevent_audit_log_mutation() RETURNS trigger AS $$ "
            "BEGIN RAISE EXCEPTION 'audit_logs are append-only'; END; $$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER audit_logs_no_update_delete BEFORE UPDATE OR DELETE ON audit_logs "
            "FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update")
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete")
    elif bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update_delete ON audit_logs")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
    for name in (
        "ix_audit_logs_request_id",
        "ix_audit_logs_branch_created_at",
        "ix_audit_logs_entity",
        "ix_audit_logs_module_action_created_at",
        "ix_audit_logs_user_created_at",
    ):
        op.drop_index(name, table_name="audit_logs")
    for name in ("request_id", "user_agent", "ip_address", "after_data", "before_data", "module"):
        op.drop_column("audit_logs", name)
