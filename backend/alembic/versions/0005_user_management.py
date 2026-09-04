"""Add user management profile, login history, and permissions."""

import uuid

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "0005_user_management"
down_revision = "0004_rbac"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("users.user.view", "View users"),
    ("users.user.create", "Create users"),
    ("users.user.edit", "Edit users"),
    ("users.user.activate", "Activate or deactivate users"),
    ("users.user.reset_password", "Reset user passwords"),
    ("users.user.login_history", "View user login history"),
    ("users.user.audit", "View user audit activity"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}
    additions = (
        ("username", sa.String(length=100), True),
        ("phone", sa.String(length=40), True),
        ("status", sa.String(length=20), False),
        ("password_status", sa.String(length=30), False),
    )
    for name, type_, nullable in additions:
        if name not in columns:
            kwargs = {"nullable": nullable}
            if name == "status":
                kwargs["server_default"] = "active"
            elif name == "password_status":
                kwargs["server_default"] = "set"
            op.add_column("users", sa.Column(name, type_, **kwargs))
    if "username" not in columns:
        op.create_index("ix_users_username", "users", ["username"], unique=True)
    if "login_history" not in inspector.get_table_names():
        op.create_table(
            "login_history",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("successful", sa.Boolean(), nullable=False),
            sa.Column("failure_reason", sa.String(length=100), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_login_history_user_created_at", "login_history", ["user_id", "created_at"])
    permission_table = sa.table(
        "permissions", sa.column("id", sa.Uuid()), sa.column("code", sa.String()),
        sa.column("description", sa.String()), sa.column("is_active", sa.Boolean()),
    )
    existing = {row[0] for row in bind.execute(sa.select(permission_table.c.code)).all()}
    rows = [
        {"id": uuid.uuid4(), "code": code, "description": description, "is_active": True}
        for code, description in PERMISSIONS if code not in existing
    ]
    if rows:
        bind.execute(permission_table.insert(), rows)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "login_history" in inspector.get_table_names():
        op.drop_index("ix_login_history_user_created_at", table_name="login_history")
        op.drop_table("login_history")
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "username" in columns:
        op.drop_index("ix_users_username", table_name="users")
    for name in ("password_status", "status", "phone", "username"):
        if name in columns:
            op.drop_column("users", name)
