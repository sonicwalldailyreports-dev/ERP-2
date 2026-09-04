import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import DEFAULT_SECRET_KEY, Settings
from app.db.models import BackgroundJob
from app.modules.auth.service import AuthService
from app.modules.reports.export import CsvExporter
from app.modules.reports.schemas import ReportPage, ReportType


def test_development_user_header_is_opt_in_and_local_only() -> None:
    assert Settings().dev_user_header_enabled is False
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key=DEFAULT_SECRET_KEY)
    with pytest.raises(ValidationError):
        Settings(environment="production", dev_user_header_enabled=True, secret_key="A" * 32)


def test_csv_exporter_neutralizes_formula_cells() -> None:
    report = ReportPage(
        report_type=ReportType.CASH_SUMMARY,
        company_id="00000000-0000-0000-0000-000000000001",
        items=[{"value": "=HYPERLINK(\"https://evil.invalid\")"}, {"value": "@SUM(1,1)"}],
    )
    output = CsvExporter().render(report).decode("utf-8-sig")
    assert "'=HYPERLINK" in output
    assert "'@SUM" in output


@pytest.mark.asyncio
async def test_password_reset_job_contains_reference_not_raw_token(test_app) -> None:
    settings = Settings(email_enabled=True)
    async with test_app.state.session_factory() as session:
        token = await AuthService(session, settings).request_password_reset("test@example.com")
        job = await session.scalar(select(BackgroundJob).where(BackgroundJob.kind == "email"))
    assert job is not None
    assert token is not None
    assert token not in str(job.payload)
    assert "password_reset_token_id" in job.payload
