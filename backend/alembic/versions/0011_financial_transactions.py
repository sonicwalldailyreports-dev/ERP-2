"""Add the centralized double-entry transaction engine."""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "0011_financial_transactions"
down_revision = "0010_expenses"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("transactions.transaction.view", "View financial transactions"),
    ("transactions.transaction.create", "Create financial transactions"),
    ("transactions.transaction.post", "Post financial transactions"),
    ("transactions.transaction.reverse", "Reverse financial transactions"),
)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "transactions" not in tables:
        op.create_table(
            "transactions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("company_id", sa.Uuid(), nullable=False),
            sa.Column("branch_id", sa.Uuid()),
            sa.Column("financial_year_id", sa.Uuid(), nullable=False),
            sa.Column("transaction_number", sa.String(80), nullable=False),
            sa.Column("transaction_date", sa.Date(), nullable=False),
            sa.Column("reference", sa.String(200)),
            sa.Column("source_module", sa.String(80)),
            sa.Column("source_document", sa.String(120)),
            sa.Column("description", sa.Text()),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("created_by", sa.Uuid()),
            sa.Column("posted_by", sa.Uuid()),
            sa.Column("posted_at", sa.DateTime(timezone=True)),
            sa.Column("reversed_by", sa.Uuid()),
            sa.Column("reversed_at", sa.DateTime(timezone=True)),
            sa.Column("reversal_of_id", sa.Uuid()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["financial_year_id"], ["financial_years.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reversed_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["company_id", "reversal_of_id"], ["transactions.company_id", "transactions.id"],
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("company_id", "id", name="uq_transactions_company_id_id"),
            sa.UniqueConstraint("company_id", "transaction_number", name="uq_transactions_company_number"),
            sa.CheckConstraint("length(trim(transaction_number)) > 0", name="transaction_number_not_blank"),
            sa.CheckConstraint("status IN ('DRAFT','POSTED','REVERSED')", name="transaction_status_valid"),
        )
        op.create_index("ix_transactions_company_id", "transactions", ["company_id"])
        op.create_index("ix_transactions_financial_year_id", "transactions", ["financial_year_id"])
        op.create_index("ix_transactions_transaction_date", "transactions", ["transaction_date"])
        op.create_index("ix_transactions_status", "transactions", ["status"])
        op.create_index("ix_transactions_company_date", "transactions", ["company_id", "transaction_date"])
        op.create_index("ix_transactions_company_year", "transactions", ["company_id", "financial_year_id"])
        op.create_index(
            "ix_transactions_source", "transactions", ["company_id", "source_module", "source_document"]
        )

    if "transaction_lines" not in tables:
        op.create_table(
            "transaction_lines",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("company_id", sa.Uuid(), nullable=False),
            sa.Column("transaction_id", sa.Uuid(), nullable=False),
            sa.Column("account_id", sa.Uuid(), nullable=False),
            sa.Column("line_number", sa.Integer(), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(
                ["company_id", "transaction_id"], ["transactions.company_id", "transactions.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["company_id", "account_id"], ["accounts.company_id", "accounts.id"],
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("transaction_id", "line_number", name="uq_transaction_lines_number"),
            sa.CheckConstraint("debit >= 0", name="transaction_line_debit_nonnegative"),
            sa.CheckConstraint("credit >= 0", name="transaction_line_credit_nonnegative"),
            sa.CheckConstraint(
                "(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)",
                name="transaction_line_one_side",
            ),
        )
        op.create_index(
            "ix_transaction_lines_company_id", "transaction_lines", ["company_id"]
        )
        op.create_index(
            "ix_transaction_lines_transaction_id", "transaction_lines", ["transaction_id"]
        )
        op.create_index(
            "ix_transaction_lines_company_account", "transaction_lines", ["company_id", "account_id"]
        )
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
    bind.execute(permission_table.delete().where(permission_table.c.code.like("transactions.%")))
    tables = set(sa.inspect(bind).get_table_names())
    if "transaction_lines" in tables:
        op.drop_index("ix_transaction_lines_company_account", table_name="transaction_lines")
        op.drop_index("ix_transaction_lines_transaction_id", table_name="transaction_lines")
        op.drop_index("ix_transaction_lines_company_id", table_name="transaction_lines")
        op.drop_table("transaction_lines")
    if "transactions" in tables:
        op.drop_index("ix_transactions_source", table_name="transactions")
        op.drop_index("ix_transactions_company_year", table_name="transactions")
        op.drop_index("ix_transactions_company_date", table_name="transactions")
        op.drop_index("ix_transactions_status", table_name="transactions")
        op.drop_index("ix_transactions_transaction_date", table_name="transactions")
        op.drop_index("ix_transactions_financial_year_id", table_name="transactions")
        op.drop_index("ix_transactions_company_id", table_name="transactions")
        op.drop_table("transactions")
