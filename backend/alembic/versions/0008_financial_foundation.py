"""Add chart of accounts and transaction-safe number sequences."""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "0008_financial_foundation"
down_revision = "0007_vendors"
branch_labels = None
depends_on = None

ACCOUNT_TYPES = (
    ("cash", "Cash"),
    ("bank", "Bank"),
    ("customer", "Customer"),
    ("vendor", "Vendor"),
    ("income", "Income"),
    ("expense", "Expense"),
    ("asset", "Asset"),
    ("liability", "Liability"),
    ("equity", "Equity"),
)
PERMISSIONS = (
    ("accounts.account.view", "View chart of accounts"),
    ("accounts.account.create", "Create accounts"),
    ("accounts.account.edit", "Edit accounts"),
    ("accounts.account.activate", "Activate or deactivate accounts"),
    ("accounts.account.delete", "Delete accounts"),
    ("numbering.sequence.view", "View number sequences"),
    ("numbering.sequence.create", "Configure number sequences"),
    ("numbering.sequence.edit", "Edit number sequences"),
    ("numbering.sequence.generate", "Generate document numbers"),
)


def _seed_rows(bind: sa.Connection, table_name: str, rows: list[dict]) -> None:
    table = sa.table(
        table_name,
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("is_system", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
    )
    existing = {row[0] for row in bind.execute(sa.select(table.c.code)).all()}
    if rows:
        bind.execute(table.insert(), [row for row in rows if row["code"] not in existing])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "account_types" not in tables:
        op.create_table(
            "account_types",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("company_id", sa.Uuid(), nullable=True),
            sa.Column("code", sa.String(length=30), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("company_id", "code", name="uq_account_types_company_code"),
            sa.CheckConstraint(
                "code IN ('cash', 'bank', 'customer', 'vendor', 'income', 'expense', 'asset', 'liability', 'equity')",
                name="account_type_code_valid",
            ),
        )
        op.create_index("ix_account_types_company_id", "account_types", ["company_id"])

    _seed_rows(
        bind,
        "account_types",
        [
            {
                "id": uuid.uuid4(),
                "code": code,
                "name": name,
                "description": f"{name} account",
                "is_system": True,
                "is_active": True,
            }
            for code, name in ACCOUNT_TYPES
        ],
    )

    if "accounts" not in tables:
        op.create_table(
            "accounts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("company_id", sa.Uuid(), nullable=False),
            sa.Column("branch_id", sa.Uuid(), nullable=True),
            sa.Column("account_code", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("account_type_id", sa.Uuid(), nullable=False),
            sa.Column("parent_account_id", sa.Uuid(), nullable=True),
            sa.Column("is_group", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["account_type_id"], ["account_types.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(
                ["company_id", "parent_account_id"],
                ["accounts.company_id", "accounts.id"],
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("company_id", "id", name="uq_accounts_company_id_id"),
            sa.UniqueConstraint("company_id", "account_code", name="uq_accounts_company_code"),
            sa.CheckConstraint("length(trim(account_code)) > 0", name="account_code_not_blank"),
            sa.CheckConstraint("length(trim(name)) > 0", name="account_name_not_blank"),
        )
        op.create_index("ix_accounts_company_id", "accounts", ["company_id"])
        op.create_index("ix_accounts_company_branch", "accounts", ["company_id", "branch_id"])
        op.create_index("ix_accounts_account_type_id", "accounts", ["account_type_id"])

    if "number_sequences" not in tables:
        op.create_table(
            "number_sequences",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("company_id", sa.Uuid(), nullable=False),
            sa.Column("branch_id", sa.Uuid(), nullable=True),
            sa.Column("financial_year_id", sa.Uuid(), nullable=True),
            sa.Column("document_type", sa.String(length=50), nullable=False),
            sa.Column("scope_key", sa.String(length=300), nullable=False),
            sa.Column("prefix", sa.String(length=30), nullable=False, server_default=""),
            sa.Column("separator", sa.String(length=5), nullable=False, server_default=""),
            sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("number_padding", sa.Integer(), nullable=False, server_default="4"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["financial_year_id"], ["financial_years.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("scope_key", name="uq_number_sequences_scope_key"),
            sa.CheckConstraint("next_number > 0", name="sequence_next_number_positive"),
            sa.CheckConstraint("number_padding BETWEEN 1 AND 12", name="sequence_padding_valid"),
            sa.CheckConstraint("length(trim(document_type)) > 0", name="sequence_document_type_not_blank"),
        )
        op.create_index("ix_number_sequences_company_id", "number_sequences", ["company_id"])

    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    existing_permissions = {row[0] for row in bind.execute(sa.select(permission_table.c.code)).all()}
    rows = [
        {"id": uuid.uuid4(), "code": code, "description": description, "is_active": True}
        for code, description in PERMISSIONS
        if code not in existing_permissions
    ]
    if rows:
        bind.execute(permission_table.insert(), rows)


def downgrade() -> None:
    bind = op.get_bind()
    if "number_sequences" in sa.inspect(bind).get_table_names():
        op.drop_index("ix_number_sequences_company_id", table_name="number_sequences")
        op.drop_table("number_sequences")
    if "accounts" in sa.inspect(bind).get_table_names():
        op.drop_index("ix_accounts_account_type_id", table_name="accounts")
        op.drop_index("ix_accounts_company_branch", table_name="accounts")
        op.drop_index("ix_accounts_company_id", table_name="accounts")
        op.drop_table("accounts")
    if "account_types" in sa.inspect(bind).get_table_names():
        op.drop_index("ix_account_types_company_id", table_name="account_types")
        op.drop_table("account_types")
