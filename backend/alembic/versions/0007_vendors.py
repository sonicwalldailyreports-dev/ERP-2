"""Create the company/branch-scoped vendor master."""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "0007_vendors"
down_revision = "0006_customers"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("vendors.vendor.view", "View vendors"),
    ("vendors.vendor.create", "Create vendors"),
    ("vendors.vendor.edit", "Edit vendors"),
    ("vendors.vendor.activate", "Activate or deactivate vendors"),
    ("vendors.vendor.delete", "Delete vendors"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "vendors" not in inspector.get_table_names():
        op.create_table(
            "vendors",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("company_id", sa.Uuid(), nullable=False),
            sa.Column("branch_id", sa.Uuid(), nullable=True),
            sa.Column("vendor_code", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("company_name", sa.String(length=200), nullable=True),
            sa.Column("contact_person", sa.String(length=150), nullable=True),
            sa.Column("email", sa.String(length=320), nullable=True),
            sa.Column("phone", sa.String(length=40), nullable=True),
            sa.Column("address_line1", sa.String(length=200), nullable=True),
            sa.Column("address_line2", sa.String(length=200), nullable=True),
            sa.Column("city", sa.String(length=100), nullable=True),
            sa.Column("state", sa.String(length=100), nullable=True),
            sa.Column("postal_code", sa.String(length=20), nullable=True),
            sa.Column("country", sa.String(length=100), nullable=True),
            sa.Column("tax_id", sa.String(length=100), nullable=True),
            sa.Column("tax_number", sa.String(length=100), nullable=True),
            sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("credit_limit", sa.Numeric(14, 2), nullable=True),
            sa.Column("payment_terms", sa.String(length=100), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("company_id", "vendor_code", name="uq_vendors_company_code"),
            sa.CheckConstraint("length(trim(vendor_code)) > 0", name="vendor_code_not_blank"),
            sa.CheckConstraint("length(trim(name)) > 0", name="vendor_name_not_blank"),
            sa.CheckConstraint("status IN ('active', 'inactive', 'suspended')", name="vendor_status_valid"),
        )
        op.create_index("ix_vendors_company_id", "vendors", ["company_id"])
        op.create_index("ix_vendors_company_branch", "vendors", ["company_id", "branch_id"])
        op.create_index("ix_vendors_company_status", "vendors", ["company_id", "status"])

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
    if "vendors" in sa.inspect(bind).get_table_names():
        op.drop_index("ix_vendors_company_status", table_name="vendors")
        op.drop_index("ix_vendors_company_branch", table_name="vendors")
        op.drop_index("ix_vendors_company_id", table_name="vendors")
        op.drop_table("vendors")
