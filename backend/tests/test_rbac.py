from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from app.core.access import effective_permissions, has_permission
from app.db.models import (
    Branch,
    Company,
    Permission,
    Role,
    RolePermission,
    UserBranch,
    UserCompany,
    UserPermissionOverride,
    UserRole,
)
from tests.conftest import TEST_USER_ID


async def test_company_role_and_branch_scope(test_app) -> None:
    company_id = uuid4()
    branch_id = uuid4()
    permission = Permission(code="reports.invoice.read", description="Read invoices")
    role = Role(company_id=company_id, name="Accountant")
    async with test_app.state.session_factory() as session:
        session.add(Company(id=company_id, name="Acme", code=f"ACME-{company_id.hex[:8]}"))
        await session.flush()
        session.add_all([Branch(id=branch_id, company_id=company_id, name="Main", code="MAIN"), permission, role])
        await session.flush()
        session.add_all([
            UserCompany(user_id=TEST_USER_ID, company_id=company_id),
            UserBranch(user_id=TEST_USER_ID, company_id=company_id, branch_id=branch_id),
            UserRole(user_id=TEST_USER_ID, role_id=role.id),
            RolePermission(role_id=role.id, permission_id=permission.id),
        ])
        await session.commit()
        assert await has_permission(session, TEST_USER_ID, permission.code, company_id, branch_id)
        assert not await has_permission(session, TEST_USER_ID, permission.code, UUID(int=99), branch_id)


async def test_specific_deny_override_beats_role_grant(test_app) -> None:
    company_id = uuid4()
    permission = Permission(code="reports.invoice.export")
    role = Role(company_id=company_id, name="Exporter")
    async with test_app.state.session_factory() as session:
        session.add(Company(id=company_id, name="Beta", code=f"BETA-{company_id.hex[:8]}"))
        await session.flush()
        session.add_all([permission, role])
        await session.flush()
        session.add_all([
            UserCompany(user_id=TEST_USER_ID, company_id=company_id),
            UserRole(user_id=TEST_USER_ID, role_id=role.id),
            RolePermission(role_id=role.id, permission_id=permission.id),
            UserPermissionOverride(
                user_id=TEST_USER_ID, permission_id=permission.id,
                company_id=company_id, is_granted=False,
            ),
        ])
        await session.commit()
        assert not await has_permission(session, TEST_USER_ID, permission.code, company_id)
        assert permission.code not in await effective_permissions(session, TEST_USER_ID, company_id)


async def test_inactive_role_is_not_effective(test_app) -> None:
    permission = Permission(code="reports.invoice.archive")
    role = Role(name="Disabled", is_active=False, status="inactive")
    async with test_app.state.session_factory() as session:
        session.add_all([permission, role])
        await session.flush()
        session.add_all([
            UserRole(user_id=TEST_USER_ID, role_id=role.id),
            RolePermission(role_id=role.id, permission_id=permission.id),
        ])
        await session.commit()
        assert not await has_permission(session, TEST_USER_ID, permission.code)


async def test_bearer_permission_dependency_enforces_tenant_scope(test_app) -> None:
    company_id = uuid4()
    permission = Permission(code="companies.company.read")
    role = Role(company_id=company_id, name="Viewer")
    async with test_app.state.session_factory() as session:
        session.add(Company(id=company_id, name="Scoped", code=f"SCOPED-{company_id.hex[:8]}"))
        await session.flush()
        session.add_all([permission, role])
        await session.flush()
        session.add_all([
            UserCompany(user_id=TEST_USER_ID, company_id=company_id),
            UserRole(user_id=TEST_USER_ID, role_id=role.id),
            RolePermission(role_id=role.id, permission_id=permission.id),
        ])
        await session.commit()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "test@example.com", "password": "test-password-123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        allowed = await client.get(f"/api/v1/companies/{company_id}", headers=headers)
        denied = await client.get(f"/api/v1/companies/{uuid4()}", headers=headers)
    assert allowed.status_code == 200
    assert denied.status_code == 403
