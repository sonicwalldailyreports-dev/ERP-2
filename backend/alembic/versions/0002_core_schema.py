"""Create core tenant, access-control, and audit tables."""

from alembic import op
from app.db import models  # noqa: F401
from app.db.base import Base

revision = "0002_core_schema"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = [
        Base.metadata.tables[name]
        for name in (
            "companies", "branches", "financial_years", "users", "roles",
            "permissions", "role_permissions", "user_roles", "user_companies",
            "user_branches", "audit_logs",
        )
    ]
    Base.metadata.create_all(op.get_bind(), tables=tables)


def downgrade() -> None:
    tables = [
        Base.metadata.tables[name]
        for name in (
            "audit_logs", "user_branches", "user_companies", "user_roles",
            "role_permissions", "permissions", "roles", "users",
            "financial_years", "branches", "companies",
        )
    ]
    Base.metadata.drop_all(op.get_bind(), tables=tables)
