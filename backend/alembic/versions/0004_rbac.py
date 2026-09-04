"""Add scoped RBAC, active role state, and user permission overrides."""

import uuid

import sqlalchemy as sa
from sqlalchemy import inspect, select

from alembic import op

revision = "0004_rbac"
down_revision = "0003_auth"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("companies.company.view", "View companies"),
    ("companies.company.create", "Create companies"),
    ("companies.company.edit", "Edit companies"),
    ("companies.company.delete", "Delete companies"),
    ("companies.company.activate", "Activate or deactivate companies"),
    ("branches.branch.view", "View branches"),
    ("branches.branch.create", "Create branches"),
    ("branches.branch.edit", "Edit branches"),
    ("branches.branch.delete", "Delete branches"),
    ("branches.branch.activate", "Activate or deactivate branches"),
    ("customers.customer.view", "View customers"),
    ("customers.customer.create", "Create customers"),
    ("customers.customer.edit", "Edit customers"),
    ("customers.customer.delete", "Delete customers"),
    ("vendors.vendor.view", "View vendors"),
    ("vendors.vendor.create", "Create vendors"),
    ("vendors.vendor.edit", "Edit vendors"),
    ("vendors.vendor.delete", "Delete vendors"),
    ("cashbook.transaction.view", "View cash book transactions"),
    ("cashbook.transaction.create", "Create cash book transactions"),
    ("cashbook.transaction.edit", "Edit cash book transactions"),
    ("cashbook.transaction.approve", "Approve cash book transactions"),
    ("cashbook.transaction.post", "Post cash book transactions"),
    ("cashbook.transaction.delete", "Delete cash book transactions"),
    ("expenses.expense.view", "View expenses"),
    ("expenses.expense.create", "Create expenses"),
    ("expenses.expense.edit", "Edit expenses"),
    ("expenses.expense.approve", "Approve expenses"),
    ("expenses.expense.reject", "Reject expenses"),
    ("reports.report.view", "View reports"),
    ("reports.report.export", "Export reports"),
    ("roles.role.view", "View roles"),
    ("roles.role.manage", "Manage roles"),
    ("roles.permission.view", "View permissions"),
    ("roles.assignment.manage", "Assign roles to users"),
    ("roles.override.manage", "Manage user permission overrides"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    role_columns = {column["name"] for column in inspector.get_columns("roles")}
    permission_columns = {column["name"] for column in inspector.get_columns("permissions")}
    if "is_active" not in role_columns:
        op.add_column("roles", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    if "status" not in role_columns:
        op.add_column("roles", sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))
    if "is_active" not in permission_columns:
        op.add_column("permissions", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    if "user_permission_overrides" not in inspector.get_table_names():
        op.create_table(
            "user_permission_overrides",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("permission_id", sa.Uuid(), nullable=False),
            sa.Column("company_id", sa.Uuid(), nullable=True),
            sa.Column("branch_id", sa.Uuid(), nullable=True),
            sa.Column("is_granted", sa.Boolean(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "permission_id", "company_id", "branch_id",
                               name="uq_user_permission_override_scope"),
        )
        op.create_index("ix_user_permission_overrides_user", "user_permission_overrides", ["user_id"])

    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    existing = {row[0] for row in bind.execute(select(permission_table.c.code)).all()}
    rows = [
        {"id": uuid.uuid4(), "code": code, "description": description, "is_active": True}
        for code, description in PERMISSIONS
        if code not in existing
    ]
    if rows:
        bind.execute(permission_table.insert(), rows)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "user_permission_overrides" in inspector.get_table_names():
        op.drop_index("ix_user_permission_overrides_user", table_name="user_permission_overrides")
        op.drop_table("user_permission_overrides")
    columns = {column["name"] for column in inspector.get_columns("roles")}
    if "status" in columns:
        op.drop_column("roles", "status")
    if "is_active" in columns:
        op.drop_column("roles", "is_active")
    permission_columns = {column["name"] for column in inspector.get_columns("permissions")}
    if "is_active" in permission_columns:
        op.drop_column("permissions", "is_active")
