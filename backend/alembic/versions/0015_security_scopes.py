"""Add tenant scope to jobs and protected reset-token delivery."""

import sqlalchemy as sa

from alembic import op

revision = "0015_security_scopes"
down_revision = "0014_job_retry_permission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    job_columns = {column["name"] for column in inspector.get_columns("background_jobs")}
    if "company_id" not in job_columns:
        op.add_column("background_jobs", sa.Column("company_id", sa.Uuid(), nullable=True))
    if "branch_id" not in job_columns:
        op.add_column("background_jobs", sa.Column("branch_id", sa.Uuid(), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("background_jobs")}
    if "ix_background_jobs_company_id" not in indexes:
        op.create_index("ix_background_jobs_company_id", "background_jobs", ["company_id"])
    with op.batch_alter_table("background_jobs") as batch:
        batch.create_foreign_key(
            "fk_background_jobs_company_id", "companies", ["company_id"], ["id"], ondelete="CASCADE"
        )
        batch.create_foreign_key(
            "fk_background_jobs_branch_company",
            "branches",
            ["branch_id", "company_id"],
            ["id", "company_id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("background_jobs") as batch:
        batch.drop_constraint("fk_background_jobs_branch_company", type_="foreignkey")
        batch.drop_constraint("fk_background_jobs_company_id", type_="foreignkey")
        batch.drop_column("branch_id")
        batch.drop_column("company_id")
    op.drop_index("ix_background_jobs_company_id", table_name="background_jobs")
