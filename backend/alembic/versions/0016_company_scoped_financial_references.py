"""Scope financial reference foreign keys to their owning company."""

import sqlalchemy as sa

from alembic import op

revision = "0016_financial_scope"
down_revision = "0015_security_scopes"
branch_labels = None
depends_on = None


def _add_constraints(table: str, constraints: list[tuple[str, list[str], str, list[str], str]]) -> None:
    with op.batch_alter_table(table) as batch:
        for name, columns, referred_table, referred_columns, ondelete in constraints:
            batch.create_foreign_key(
                name,
                referred_table,
                columns,
                referred_columns,
                ondelete=ondelete,
            )


def upgrade() -> None:
    # Composite references require a matching unique key on each parent.  The
    # keys are additive and safe for databases created by earlier revisions.
    for table, name in (
        ("financial_years", "uq_financial_years_company_id"),
        ("expense_categories", "uq_expense_categories_company_id"),
        ("cash_accounts", "uq_cash_accounts_company_id"),
    ):
        inspector = sa.inspect(op.get_bind())
        uniques = {item["name"] for item in inspector.get_unique_constraints(table)}
        if name not in uniques:
            with op.batch_alter_table(table) as batch:
                batch.create_unique_constraint(name, ["company_id", "id"])

    _add_constraints(
        "expenses",
        [
            ("fk_expenses_company_year", ["company_id", "financial_year_id"], "financial_years", ["company_id", "id"], "RESTRICT"),
            ("fk_expenses_company_category", ["company_id", "category_id"], "expense_categories", ["company_id", "id"], "RESTRICT"),
            ("fk_expenses_company_account", ["company_id", "account_id"], "accounts", ["company_id", "id"], "RESTRICT"),
            ("fk_expenses_company_cash_account", ["company_id", "cash_account_id"], "cash_accounts", ["company_id", "id"], "RESTRICT"),
        ],
    )
    _add_constraints(
        "cash_opening_balances",
        [
            ("fk_cash_opening_company_cash_account", ["company_id", "cash_account_id"], "cash_accounts", ["company_id", "id"], "CASCADE"),
            ("fk_cash_opening_company_year", ["company_id", "financial_year_id"], "financial_years", ["company_id", "id"], "CASCADE"),
        ],
    )
    _add_constraints(
        "cash_transactions",
        [
            ("fk_cash_transactions_company_cash_account", ["company_id", "cash_account_id"], "cash_accounts", ["company_id", "id"], "RESTRICT"),
            ("fk_cash_transactions_company_target_cash_account", ["company_id", "target_cash_account_id"], "cash_accounts", ["company_id", "id"], "RESTRICT"),
            ("fk_cash_transactions_company_year", ["company_id", "financial_year_id"], "financial_years", ["company_id", "id"], "RESTRICT"),
        ],
    )
    _add_constraints(
        "cash_accounts",
        [
            ("fk_cash_accounts_company_account", ["company_id", "account_id"], "accounts", ["company_id", "id"], "SET NULL"),
        ],
    )


def downgrade() -> None:
    for table, names in (
        ("cash_accounts", ["fk_cash_accounts_company_account"]),
        ("cash_transactions", [
            "fk_cash_transactions_company_year",
            "fk_cash_transactions_company_target_cash_account",
            "fk_cash_transactions_company_cash_account",
        ]),
        ("cash_opening_balances", ["fk_cash_opening_company_year", "fk_cash_opening_company_cash_account"]),
        ("expenses", [
            "fk_expenses_company_cash_account",
            "fk_expenses_company_account",
            "fk_expenses_company_category",
            "fk_expenses_company_year",
        ]),
    ):
        with op.batch_alter_table(table) as batch:
            for name in names:
                batch.drop_constraint(name, type_="foreignkey")
    for table, name in (
        ("cash_accounts", "uq_cash_accounts_company_id"),
        ("expense_categories", "uq_expense_categories_company_id"),
        ("financial_years", "uq_financial_years_company_id"),
    ):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(name, type_="unique")
