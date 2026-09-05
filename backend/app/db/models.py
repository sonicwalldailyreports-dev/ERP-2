import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from sqlalchemy.orm import Session as SyncSession

from app.core.audit import get_audit_context, redact_json_text, redact_sensitive
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Branch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_branches_company_id_id"),
        UniqueConstraint("company_id", "code", name="uq_branches_company_code"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A non-financial customer master record scoped to a company and branch."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("company_id", "customer_code", name="uq_customers_company_code"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("length(trim(customer_code)) > 0", name="customer_code_not_blank"),
        CheckConstraint("length(trim(name)) > 0", name="customer_name_not_blank"),
        CheckConstraint("status IN ('active', 'inactive', 'suspended')", name="customer_status_valid"),
        Index("ix_customers_company_branch", "company_id", "branch_id"),
        Index("ix_customers_company_status", "company_id", "status"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    customer_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200))
    contact_person: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    address_line1: Mapped[str | None] = mapped_column(String(200))
    address_line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(100))
    tax_id: Mapped[str | None] = mapped_column(String(100))
    tax_number: Mapped[str | None] = mapped_column(String(100))
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    payment_terms: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def customer_name(self) -> str:
        return self.name


class Vendor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A non-financial vendor master record scoped to a company and branch."""

    __tablename__ = "vendors"
    __table_args__ = (
        UniqueConstraint("company_id", "vendor_code", name="uq_vendors_company_code"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("length(trim(vendor_code)) > 0", name="vendor_code_not_blank"),
        CheckConstraint("length(trim(name)) > 0", name="vendor_name_not_blank"),
        CheckConstraint("status IN ('active', 'inactive', 'suspended')", name="vendor_status_valid"),
        Index("ix_vendors_company_branch", "company_id", "branch_id"),
        Index("ix_vendors_company_status", "company_id", "status"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    vendor_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200))
    contact_person: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    address_line1: Mapped[str | None] = mapped_column(String(200))
    address_line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(100))
    tax_id: Mapped[str | None] = mapped_column(String(100))
    tax_number: Mapped[str | None] = mapped_column(String(100))
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    payment_terms: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def vendor_name(self) -> str:
        return self.name


class FinancialYear(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_years"
    __table_args__ = (
        CheckConstraint("start_date < end_date", name="financial_year_dates"),
        UniqueConstraint("company_id", "name", name="uq_financial_years_company_name"),
        UniqueConstraint("company_id", "start_date", name="uq_financial_years_company_start"),
        UniqueConstraint("company_id", "id", name="uq_financial_years_company_id"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def contains(self, value: date) -> bool:
        """Return whether a date belongs to this financial year (inclusive)."""
        return self.start_date <= value <= self.end_date

    def validate_date(self, value: date) -> date:
        if not self.contains(value):
            raise ValueError(f"Date must fall between {self.start_date} and {self.end_date}.")
        if not self.is_active or self.is_closed:
            raise ValueError("Financial year is not open for transactions.")
        return value


class AccountType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A system or company-defined account classification."""

    __tablename__ = "account_types"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_account_types_company_code"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        CheckConstraint(
            "code IN ('cash', 'bank', 'customer', 'vendor', 'income', 'expense', 'asset', 'liability', 'equity')",
            name="account_type_code_valid",
        ),
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Company-owned hierarchical chart-of-accounts entry."""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_accounts_company_id_id"),
        UniqueConstraint("company_id", "account_code", name="uq_accounts_company_code"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(["account_type_id"], ["account_types.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["company_id", "parent_account_id"],
            ["accounts.company_id", "accounts.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("length(trim(account_code)) > 0", name="account_code_not_blank"),
        CheckConstraint("length(trim(name)) > 0", name="account_name_not_blank"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_type_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    parent_account_id: Mapped[uuid.UUID | None] = mapped_column()
    is_group: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    parent_account: Mapped["Account | None"] = relationship(
        "Account", remote_side="Account.id", back_populates="children"
    )
    children: Mapped[list["Account"]] = relationship("Account", back_populates="parent_account")


class NumberSequence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A counter keyed by company, optional branch and financial year."""

    __tablename__ = "number_sequences"
    __table_args__ = (
        UniqueConstraint("scope_key", name="uq_number_sequences_scope_key"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(["financial_year_id"], ["financial_years.id"], ondelete="CASCADE"),
        CheckConstraint("next_number > 0", name="sequence_next_number_positive"),
        CheckConstraint("number_padding BETWEEN 1 AND 12", name="sequence_padding_valid"),
        CheckConstraint("length(trim(document_type)) > 0", name="sequence_document_type_not_blank"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    financial_year_id: Mapped[uuid.UUID | None] = mapped_column()
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(300), nullable=False)
    prefix: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    separator: Mapped[str] = mapped_column(String(5), default="", nullable=False)
    next_number: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    number_padding: Mapped[int] = mapped_column(default=4, server_default="4", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def format_number(self, number: int) -> str:
        value = str(number).zfill(self.number_padding)
        parts = [part for part in (self.prefix, value) if part]
        return self.separator.join(parts)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    password_status: Mapped[str] = mapped_column(String(30), default="set", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_user_active", "user_id", "revoked_at"),
        UniqueConstraint("refresh_token_hash", name="uq_auth_sessions_refresh_token_hash"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("auth_sessions.id", ondelete="SET NULL"))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip_address: Mapped[str | None] = mapped_column(String(64))


class PasswordResetToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_roles_company_name"),)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class UserPermissionOverride(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-specific grant or deny, optionally scoped to a company/branch."""

    __tablename__ = "user_permission_overrides"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "user_id", "permission_id", "company_id", "branch_id",
            name="uq_user_permission_override_scope",
        ),
        Index("ix_user_permission_overrides_user", "user_id"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[uuid.UUID | None] = mapped_column()
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    is_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserCompany(Base):
    __tablename__ = "user_companies"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)


class UserBranch(Base):
    __tablename__ = "user_branches"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"),
        Index("ix_user_branches_company_branch", "company_id", "branch_id"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_company_created_at", "company_id", "created_at"),
        Index("ix_audit_logs_user_created_at", "user_id", "created_at"),
        Index("ix_audit_logs_module_action_created_at", "module", "action", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_logs_branch_created_at", "branch_id", "created_at"),
        Index("ix_audit_logs_request_id", "request_id"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="SET NULL"),
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    user_id: Mapped[uuid.UUID | None] = mapped_column()
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    module: Mapped[str | None] = mapped_column(String(80), nullable=False, server_default="system")
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column()
    before_data: Mapped[dict | None] = mapped_column(JSON)
    after_data: Mapped[dict | None] = mapped_column(JSON)
    details: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    request_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    # Compatibility aliases for the public audit vocabulary and old call sites.
    timestamp = synonym("created_at")
    entity = synonym("entity_type")
    before = synonym("before_data")
    after = synonym("after_data")
    before_json = synonym("before_data")
    after_json = synonym("after_data")


@event.listens_for(AuditLog, "before_insert")
def _prepare_audit_log(_mapper, _connection, target: AuditLog) -> None:
    """Populate request metadata and redact all legacy/direct inserts."""
    context = get_audit_context()
    if target.user_id is None:
        target.user_id = context.user_id
    target.ip_address = target.ip_address or context.ip_address
    target.user_agent = target.user_agent or context.user_agent
    target.request_id = target.request_id or context.request_id
    if not target.module or target.module == "system":
        module_by_entity = {
            "cash_account": "cashbook",
            "cash_transaction": "cashbook",
            "expense": "expenses",
            "expense_category": "expenses",
            "number_sequence": "numbering",
            "transaction": "transactions",
        }
        target.module = module_by_entity.get(
            target.entity_type,
            "auth" if target.action.startswith(("LOGIN", "PASSWORD_")) else (target.entity_type or "system").split(".", 1)[0],
        )
    if target.details is not None:
        target.details = redact_json_text(target.details)
        if target.after_data is None:
            try:
                import json

                parsed = json.loads(target.details)
                if isinstance(parsed, dict):
                    target.after_data = redact_sensitive(parsed)
            except (TypeError, ValueError):
                pass
    target.before_data = redact_sensitive(target.before_data)
    target.after_data = redact_sensitive(target.after_data)


@event.listens_for(AuditLog, "before_update")
def _protect_audit_update(_mapper, _connection, _target: AuditLog) -> None:
    raise ValueError("Audit logs are append-only and cannot be updated.")


@event.listens_for(AuditLog, "before_delete")
def _protect_audit_delete(_mapper, _connection, _target: AuditLog) -> None:
    raise ValueError("Audit logs are append-only and cannot be deleted.")


@event.listens_for(SyncSession, "do_orm_execute")
def _protect_bulk_audit_mutation(execute_state) -> None:
    """Cover SQLAlchemy bulk UPDATE/DELETE, which bypass mapper events."""
    if not (execute_state.is_update or execute_state.is_delete):
        return
    table = getattr(execute_state.statement, "table", None)
    if table is not None and table.name == AuditLog.__tablename__:
        raise ValueError("Audit logs are append-only and cannot be mutated.")


class LoginHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "login_history"
    __table_args__ = (Index("ix_login_history_user_created_at", "user_id", "created_at"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    successful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(100))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class CashAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A cash or bank ledger used by the cash book."""

    __tablename__ = "cash_accounts"
    __table_args__ = (
        UniqueConstraint("company_id", "account_code", name="uq_cash_accounts_company_code"),
        UniqueConstraint("company_id", "id", name="uq_cash_accounts_company_id"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["company_id", "account_id"], ["accounts.company_id", "accounts.id"], ondelete="RESTRICT"),
        Index("ix_cash_accounts_company_branch", "company_id", "branch_id"),
        CheckConstraint("length(trim(name)) > 0", name="cash_account_name_not_blank"),
        CheckConstraint("opening_balance >= 0", name="cash_account_opening_nonnegative"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    account_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CashOpeningBalance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Opening balance for a cash account in a financial year."""

    __tablename__ = "cash_opening_balances"
    __table_args__ = (
        UniqueConstraint("cash_account_id", "financial_year_id", name="uq_cash_opening_account_year"),
        ForeignKeyConstraint(["cash_account_id"], ["cash_accounts.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["financial_year_id"], ["financial_years.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["company_id", "cash_account_id"], ["cash_accounts.company_id", "cash_accounts.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["company_id", "financial_year_id"], ["financial_years.company_id", "financial_years.id"], ondelete="CASCADE"),
        CheckConstraint("amount >= 0", name="cash_opening_amount_nonnegative"),
    )
    cash_account_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    financial_year_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class CashTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An auditable cash receipt, payment, or transfer."""

    __tablename__ = "cash_transactions"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["company_id", "cash_account_id"], ["cash_accounts.company_id", "cash_accounts.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "target_cash_account_id"], ["cash_accounts.company_id", "cash_accounts.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "financial_year_id"], ["financial_years.company_id", "financial_years.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["reversed_by"], ["users.id"], ondelete="SET NULL"),
        CheckConstraint(
            "transaction_type IN ('receipt', 'payment', 'transfer')",
            name="cash_transaction_type_valid",
        ),
        CheckConstraint(
            "state IN ('DRAFT', 'SUBMITTED', 'APPROVED', 'POSTED', 'REJECTED', 'CANCELLED')",
            name="cash_transaction_state_valid",
        ),
        CheckConstraint("amount > 0", name="cash_transaction_amount_positive"),
        CheckConstraint(
            "(transaction_type = 'transfer' AND target_cash_account_id IS NOT NULL) OR "
            "(transaction_type <> 'transfer' AND target_cash_account_id IS NULL)",
            name="cash_transfer_target_valid",
        ),
        Index("ix_cash_transactions_company_date", "company_id", "transaction_date"),
        Index("ix_cash_transactions_account_state", "cash_account_id", "state"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    cash_account_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    target_cash_account_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    financial_year_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    document_number: Mapped[str | None] = mapped_column(String(50), unique=True)
    state: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cash_transactions.id", ondelete="RESTRICT"), index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column()
    submitted_by: Mapped[uuid.UUID | None] = mapped_column()
    approved_by: Mapped[uuid.UUID | None] = mapped_column()
    posted_by: Mapped[uuid.UUID | None] = mapped_column()
    reversed_by: Mapped[uuid.UUID | None] = mapped_column()
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_expense_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expenses.id", ondelete="SET NULL"), index=True, unique=True
    )


class CashDailySummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted daily totals, rebuilt transactionally when a transaction posts."""

    __tablename__ = "cash_daily_summaries"
    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", "cash_account_id", "summary_date",
                         name="uq_cash_daily_summary_scope"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["cash_account_id"], ["cash_accounts.id"], ondelete="CASCADE"),
        CheckConstraint("receipts >= 0", name="cash_summary_receipts_nonnegative"),
        CheckConstraint("payments >= 0", name="cash_summary_payments_nonnegative"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    cash_account_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    summary_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    receipts: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    payments: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    transfers_in: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    transfers_out: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)


class ExpenseCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Company/branch scoped expense classification."""

    __tablename__ = "expense_categories"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_expense_categories_company_code"),
        UniqueConstraint("company_id", "id", name="uq_expense_categories_company_id"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
        ),
        CheckConstraint("length(trim(code)) > 0", name="expense_category_code_not_blank"),
        CheckConstraint("length(trim(name)) > 0", name="expense_category_name_not_blank"),
        Index("ix_expense_categories_company_branch", "company_id", "branch_id"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Expense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Auditable expense document and approval workflow."""

    __tablename__ = "expenses"
    __table_args__ = (
        UniqueConstraint("company_id", "expense_number", name="uq_expenses_company_number"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["company_id", "financial_year_id"], ["financial_years.company_id", "financial_years.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "category_id"], ["expense_categories.company_id", "expense_categories.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "account_id"], ["accounts.company_id", "accounts.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "cash_account_id"], ["cash_accounts.company_id", "cash_accounts.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["reversal_of_id"], ["expenses.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["correction_of_id"], ["expenses.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["reversed_by"], ["users.id"], ondelete="SET NULL"),
        CheckConstraint("status IN ('DRAFT','SUBMITTED','APPROVED','POSTED','REJECTED','CANCELLED')", name="expense_status_valid"),
        CheckConstraint("amount > 0", name="expense_amount_positive"),
        CheckConstraint("tax_amount >= 0", name="expense_tax_nonnegative"),
        Index("ix_expenses_company_date", "company_id", "date"),
        Index("ix_expenses_company_status", "company_id", "status"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    financial_year_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    expense_number: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    vendor: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), default="cash", nullable=False)
    cash_account_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    reference: Mapped[str | None] = mapped_column(String(100))
    attachment: Mapped[dict | list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column()
    approved_by: Mapped[uuid.UUID | None] = mapped_column()
    posted_by: Mapped[uuid.UUID | None] = mapped_column()
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    correction_of_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    reversed_by: Mapped[uuid.UUID | None] = mapped_column()
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A balanced, immutable general-ledger transaction."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_transactions_company_id_id"),
        UniqueConstraint("company_id", "transaction_number", name="uq_transactions_company_number"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["financial_year_id"], ["financial_years.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["reversed_by"], ["users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["company_id", "reversal_of_id"], ["transactions.company_id", "transactions.id"], ondelete="RESTRICT"),
        CheckConstraint("length(trim(transaction_number)) > 0", name="transaction_number_not_blank"),
        CheckConstraint("status IN ('DRAFT','POSTED','REVERSED')", name="transaction_status_valid"),
        Index("ix_transactions_company_date", "company_id", "transaction_date"),
        Index("ix_transactions_company_year", "company_id", "financial_year_id"),
        Index("ix_transactions_source", "company_id", "source_module", "source_document"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    financial_year_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    transaction_number: Mapped[str] = mapped_column(String(80), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reference: Mapped[str | None] = mapped_column(String(200))
    source_module: Mapped[str | None] = mapped_column(String(80))
    source_document: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT", nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column()
    posted_by: Mapped[uuid.UUID | None] = mapped_column()
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_by: Mapped[uuid.UUID | None] = mapped_column()
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column()

    lines: Mapped[list["TransactionLine"]] = relationship(
        "TransactionLine", back_populates="transaction", cascade="all, delete-orphan",
        order_by="TransactionLine.line_number",
    )


class TransactionLine(UUIDPrimaryKeyMixin, Base):
    """One debit or credit side of a general-ledger transaction."""

    __tablename__ = "transaction_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "transaction_id"], ["transactions.company_id", "transactions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["company_id", "account_id"], ["accounts.company_id", "accounts.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("transaction_id", "line_number", name="uq_transaction_lines_number"),
        CheckConstraint("debit >= 0", name="transaction_line_debit_nonnegative"),
        CheckConstraint("credit >= 0", name="transaction_line_credit_nonnegative"),
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)",
            name="transaction_line_one_side",
        ),
        Index("ix_transaction_lines_company_account", "company_id", "account_id"),
        Index("ix_transaction_lines_transaction", "transaction_id"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    line_number: Mapped[int] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0", nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0", nullable=False)

    transaction: Mapped[Transaction] = relationship("Transaction", back_populates="lines")


@event.listens_for(Transaction, "before_update")
def _protect_posted_transaction(_mapper, connection, target: Transaction) -> None:
    """Allow only the reversal marker to change after posting."""
    state = inspect(target)
    old_states = state.attrs.status.history.deleted
    old_status = old_states[0] if old_states else target.status
    if old_status in {"POSTED", "REVERSED"}:
        changed = {
            attribute.key for attribute in state.attrs
            if attribute.history.has_changes()
        }
        if changed - {"status", "reversed_by", "reversed_at", "updated_at"}:
            raise ValueError("Posted transactions are immutable.")


@event.listens_for(Transaction, "before_delete")
def _protect_deleted_transaction(_mapper, connection, target: Transaction) -> None:
    if target.status in {"POSTED", "REVERSED"}:
        raise ValueError("Posted transactions are immutable.")


def _protect_transaction_line(_mapper, connection, target: TransactionLine) -> None:
    status = connection.execute(
        select(Transaction.status).where(
            Transaction.id == target.transaction_id,
            Transaction.company_id == target.company_id,
        )
    ).scalar_one_or_none()
    if status in {"POSTED", "REVERSED"}:
        raise ValueError("Lines of posted transactions are immutable.")


event.listen(TransactionLine, "before_update", _protect_transaction_line)
event.listen(TransactionLine, "before_delete", _protect_transaction_line)


# Explicit aliases keep integrations readable while preserving the canonical
# ``Transaction`` table/model name used by the accounting engine.
FinancialTransaction = Transaction
FinancialTransactionLine = TransactionLine


class Notification(UUIDPrimaryKeyMixin, Base):
    """Durable in-app notification delivered to one user."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_notifications_idempotency_key"),
        Index("ix_notifications_user_unread_created", "user_id", "read_at", "created_at"),
        Index("ix_notifications_company_created", "company_id", "created_at"),
        ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
        ),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column()
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class BackgroundJob(UUIDPrimaryKeyMixin, Base):
    """Durable job record shared by in-process and external workers."""

    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_background_jobs_idempotency_key"),
        Index("ix_background_jobs_status_available", "status", "available_at"),
        Index("ix_background_jobs_kind_created", "kind", "created_at"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="CASCADE"
        ),
    )
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    max_attempts: Mapped[int] = mapped_column(default=3, server_default="3", nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


InAppNotification = Notification
Job = BackgroundJob
