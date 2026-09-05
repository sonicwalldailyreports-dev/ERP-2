from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuthSession, PasswordResetToken, User


class AuthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_user(self, username: str) -> User | None:
        return await self.session.scalar(
            select(User).where(
                (User.email == username.lower()) | (User.username == username.lower()),
                User.deleted_at.is_(None),
            )
        )

    async def get_user(self, user_id: UUID) -> User | None:
        return await self.session.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))

    async def get_session(self, token_hash: str, *, lock: bool = False) -> AuthSession | None:
        query = select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def revoke_user_sessions(self, user_id: UUID) -> None:
        sessions = await self.session.scalars(
            select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        )
        now = datetime.now(UTC)
        for session in sessions:
            session.revoked_at = now

    async def find_password_reset_token(
        self, token_hash: str, *, lock: bool = False
    ) -> PasswordResetToken | None:
        query = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)
