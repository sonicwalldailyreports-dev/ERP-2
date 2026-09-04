"""Cash book accounts, workflow transactions, and daily summaries."""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "0009_cash_book"
down_revision = "0008_financial_foundation"
branch_labels = None
depends_on = None


PERMISSIONS = (
    ("cashbook.account.view", "View cash accounts"),
    ("cashbook.account.create", "Create cash accounts"),
    ("cashbook.account.edit", "Edit cash accounts"),
    ("cashbook.cash_account.view", "View cash accounts"),
    ("cashbook.cash_account.create", "Create cash accounts"),
    ("cashbook.cash_account.edit", "Edit cash accounts"),
    ("cashbook.opening_balance.manage", "Manage cash opening balances"),
    ("cashbook.transaction.view", "View cash transactions"),
    ("cashbook.transaction.create", "Create cash transactions"),
    ("cashbook.transaction.submit", "Submit cash transactions"),
    ("cashbook.transaction.approve", "Approve cash transactions"),
    ("cashbook.transaction.post", "Post cash transactions"),
    ("cashbook.transaction.reject", "Reject cash transactions"),
    ("cashbook.transaction.cancel", "Cancel cash transactions"),
    ("cashbook.transaction.reverse", "Reverse posted cash transactions"),
    ("cashbook.summary.view", "View cash daily summaries"),
)


def upgrade() -> None:
    op.create_table(
        "cash_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid()),
        sa.Column("account_id", sa.Uuid()),
        sa.Column("account_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("company_id", "account_code", name="uq_cash_accounts_company_code"),
        sa.CheckConstraint("length(trim(name)) > 0", name="cash_account_name_not_blank"),
        sa.CheckConstraint("opening_balance >= 0", name="cash_account_opening_nonnegative"),
    )
    op.create_index("ix_cash_accounts_company_id", "cash_accounts", ["company_id"])
    op.create_index("ix_cash_accounts_company_branch", "cash_accounts", ["company_id", "branch_id"])
    op.create_index("ix_cash_accounts_account_id", "cash_accounts", ["account_id"])

    op.create_table(
        "cash_opening_balances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cash_account_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("financial_year_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cash_account_id"], ["cash_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["financial_year_id"], ["financial_years.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("cash_account_id", "financial_year_id", name="uq_cash_opening_account_year"),
        sa.CheckConstraint("amount >= 0", name="cash_opening_amount_nonnegative"),
    )
    op.create_index("ix_cash_opening_balances_cash_account_id", "cash_opening_balances", ["cash_account_id"])
    op.create_index("ix_cash_opening_balances_company_id", "cash_opening_balances", ["company_id"])
    op.create_index("ix_cash_opening_balances_financial_year_id", "cash_opening_balances", ["financial_year_id"])

    op.create_table(
        "cash_transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid()),
        sa.Column("cash_account_id", sa.Uuid(), nullable=False),
        sa.Column("target_cash_account_id", sa.Uuid()),
        sa.Column("financial_year_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reference", sa.String(100)),
        sa.Column("description", sa.Text()),
        sa.Column("document_number", sa.String(50), unique=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("cancellation_reason", sa.Text()),
        sa.Column("reversal_of_id", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("submitted_by", sa.Uuid()),
        sa.Column("approved_by", sa.Uuid()),
        sa.Column("posted_by", sa.Uuid()),
        sa.Column("reversed_by", sa.Uuid()),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cash_account_id"], ["cash_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_cash_account_id"], ["cash_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["financial_year_id"], ["financial_years.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversal_of_id"], ["cash_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reversed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("transaction_type IN ('receipt','payment','transfer')", name="cash_transaction_type_valid"),
        sa.CheckConstraint("state IN ('DRAFT','SUBMITTED','APPROVED','POSTED','REJECTED','CANCELLED')", name="cash_transaction_state_valid"),
        sa.CheckConstraint("amount > 0", name="cash_transaction_amount_positive"),
        sa.CheckConstraint("(transaction_type = 'transfer' AND target_cash_account_id IS NOT NULL) OR (transaction_type <> 'transfer' AND target_cash_account_id IS NULL)", name="cash_transfer_target_valid"),
    )
    op.create_index("ix_cash_transactions_company_date", "cash_transactions", ["company_id", "transaction_date"])
    op.create_index("ix_cash_transactions_account_state", "cash_transactions", ["cash_account_id", "state"])
    op.create_index("ix_cash_transactions_target_cash_account_id", "cash_transactions", ["target_cash_account_id"])
    op.create_index("ix_cash_transactions_financial_year_id", "cash_transactions", ["financial_year_id"])
    op.create_index("ix_cash_transactions_reversal_of_id", "cash_transactions", ["reversal_of_id"])

    op.create_table(
        "cash_daily_summaries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid()),
        sa.Column("cash_account_id", sa.Uuid(), nullable=False),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("receipts", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("payments", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("transfers_in", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("transfers_out", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("closing_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cash_account_id"], ["cash_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", "branch_id", "cash_account_id", "summary_date", name="uq_cash_daily_summary_scope"),
    )
    op.create_index("ix_cash_daily_summaries_company_id", "cash_daily_summaries", ["company_id"])
    op.create_index("ix_cash_daily_summaries_cash_account_id", "cash_daily_summaries", ["cash_account_id"])
    op.create_index("ix_cash_daily_summaries_summary_date", "cash_daily_summaries", ["summary_date"])

    bind = op.get_bind()
    table = sa.table("permissions", sa.column("id", sa.Uuid()), sa.column("code", sa.String()), sa.column("description", sa.String()), sa.column("is_active", sa.Boolean()))
    existing = {row[0] for row in bind.execute(sa.select(table.c.code)).all()}
    rows = [{"id": uuid.uuid4(), "code": code, "description": description, "is_active": True} for code, description in PERMISSIONS if code not in existing]
    if rows:
        bind.execute(table.insert(), rows)


def downgrade() -> None:
    bind = op.get_bind()
    table = sa.table("permissions", sa.column("code", sa.String()))
    bind.execute(table.delete().where(table.c.code.like("cashbook.%")))
    for name in ("cash_daily_summaries", "cash_transactions", "cash_opening_balances", "cash_accounts"):
        if name in sa.inspect(bind).get_table_names():
            op.drop_table(name)
