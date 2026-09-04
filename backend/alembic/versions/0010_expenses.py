"""Add expense categories, expense workflow, and cashbook posting link."""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "0010_expenses"
down_revision = "0009_cash_book"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("expenses.category.view", "View expense categories"),
    ("expenses.category.create", "Create expense categories"),
    ("expenses.category.edit", "Edit expense categories"),
    ("expenses.expense.view", "View expenses"),
    ("expenses.expense.create", "Create expenses"),
    ("expenses.expense.edit", "Edit draft expenses"),
    ("expenses.expense.submit", "Submit expenses"),
    ("expenses.expense.approve", "Approve expenses"),
    ("expenses.expense.reject", "Reject expenses"),
    ("expenses.expense.post", "Post expenses"),
    ("expenses.expense.cancel", "Cancel expenses"),
    ("expenses.expense.reverse", "Reverse posted expenses"),
    ("expenses.expense.adjust", "Create expense adjustments"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "expense_categories" not in tables:
        op.create_table(
            "expense_categories",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("company_id", sa.Uuid(), nullable=False),
            sa.Column("branch_id", sa.Uuid()),
            sa.Column("code", sa.String(50), nullable=False),
            sa.Column("name", sa.String(150), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint("company_id", "code", name="uq_expense_categories_company_code"),
            sa.CheckConstraint("length(trim(code)) > 0", name="expense_category_code_not_blank"),
            sa.CheckConstraint("length(trim(name)) > 0", name="expense_category_name_not_blank"),
        )
        op.create_index("ix_expense_categories_company_id", "expense_categories", ["company_id"])
        op.create_index("ix_expense_categories_company_branch", "expense_categories", ["company_id", "branch_id"])

    if "expenses" not in tables:
        op.create_table(
            "expenses",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("company_id", sa.Uuid(), nullable=False),
            sa.Column("branch_id", sa.Uuid()),
            sa.Column("financial_year_id", sa.Uuid(), nullable=False),
            sa.Column("expense_number", sa.String(50), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("category_id", sa.Uuid(), nullable=False),
            sa.Column("account_id", sa.Uuid(), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("vendor", sa.String(200)),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("payment_method", sa.String(30), nullable=False, server_default="cash"),
            sa.Column("cash_account_id", sa.Uuid()),
            sa.Column("reference", sa.String(100)),
            sa.Column("attachment", sa.JSON()),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("created_by", sa.Uuid()),
            sa.Column("approved_by", sa.Uuid()),
            sa.Column("posted_by", sa.Uuid()),
            sa.Column("approved_at", sa.DateTime(timezone=True)),
            sa.Column("posted_at", sa.DateTime(timezone=True)),
            sa.Column("rejection_reason", sa.Text()),
            sa.Column("cancellation_reason", sa.Text()),
            sa.Column("reversal_of_id", sa.Uuid()),
            sa.Column("correction_of_id", sa.Uuid()),
            sa.Column("reversed_by", sa.Uuid()),
            sa.Column("reversed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["financial_year_id"], ["financial_years.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["category_id"], ["expense_categories.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["cash_account_id"], ["cash_accounts.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reversed_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reversal_of_id"], ["expenses.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["correction_of_id"], ["expenses.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint("company_id", "expense_number", name="uq_expenses_company_number"),
            sa.CheckConstraint(
                "status IN ('DRAFT','SUBMITTED','APPROVED','POSTED','REJECTED','CANCELLED')",
                name="expense_status_valid",
            ),
            sa.CheckConstraint("amount > 0", name="expense_amount_positive"),
            sa.CheckConstraint("tax_amount >= 0", name="expense_tax_nonnegative"),
        )
        op.create_index("ix_expenses_company_id", "expenses", ["company_id"])
        op.create_index("ix_expenses_company_date", "expenses", ["company_id", "date"])
        op.create_index("ix_expenses_company_status", "expenses", ["company_id", "status"])
        op.create_index("ix_expenses_financial_year_id", "expenses", ["financial_year_id"])
        op.create_index("ix_expenses_category_id", "expenses", ["category_id"])
        op.create_index("ix_expenses_account_id", "expenses", ["account_id"])
        op.create_index("ix_expenses_cash_account_id", "expenses", ["cash_account_id"])
        op.create_index("ix_expenses_reversal_of_id", "expenses", ["reversal_of_id"])
        op.create_index("ix_expenses_correction_of_id", "expenses", ["correction_of_id"])

    if "source_expense_id" not in {column["name"] for column in inspector.get_columns("cash_transactions")}:
        with op.batch_alter_table("cash_transactions") as batch:
            batch.add_column(sa.Column("source_expense_id", sa.Uuid()))
            batch.create_foreign_key(
                "fk_cash_transactions_source_expense", "expenses", ["source_expense_id"], ["id"], ondelete="SET NULL"
            )
            batch.create_unique_constraint("uq_cash_transactions_source_expense", ["source_expense_id"])
            batch.create_index("ix_cash_transactions_source_expense_id", ["source_expense_id"])

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
    if "cash_transactions" in sa.inspect(bind).get_table_names():
        with op.batch_alter_table("cash_transactions") as batch:
            batch.drop_constraint("uq_cash_transactions_source_expense", type_="unique")
            batch.drop_constraint("fk_cash_transactions_source_expense", type_="foreignkey")
            batch.drop_index("ix_cash_transactions_source_expense_id")
            batch.drop_column("source_expense_id")
    table = sa.table("permissions", sa.column("code", sa.String()))
    bind.execute(table.delete().where(table.c.code.like("expenses.%")))
    if "expenses" in sa.inspect(bind).get_table_names():
        op.drop_table("expenses")
    if "expense_categories" in sa.inspect(bind).get_table_names():
        op.drop_table("expense_categories")
