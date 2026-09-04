from collections.abc import AsyncIterator
from uuid import UUID

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.dependencies import get_db_session
from app.db.base import Base
from app.db.models import User
from app.main import create_app
from app.modules.auth.security import hash_password

TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def test_app() -> AsyncIterator:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        session.add(User(id=TEST_USER_ID, email="test@example.com", password_hash=hash_password("test-password-123"), full_name="Test User"))
        await session.commit()
    application = create_app(
        settings=Settings(environment="test", dev_user_header_enabled=True),
        engine=engine,
        session_factory=session_factory,
    )

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_session
    yield application
    await engine.dispose()
