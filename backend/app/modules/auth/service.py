import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import AuditLog, AuthSession, LoginHistory, PasswordResetToken, User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    TokenResponse,
)
from app.modules.auth.security import (
    create_access_token,
    dummy_password_hash,
    hash_password,
    hash_token,
    new_refresh_token,
    password_reset_token,
    verify_password,
)
from app.modules.notifications.events import PASSWORD_RESET, DomainEvent
from app.modules.notifications.service import NotificationService


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.repository = AuthRepository(session)

    async def login(self, data: LoginRequest, user_agent: str | None, ip_address: str | None) -> TokenResponse:
        user = await self.repository.find_user(data.username)
        now = datetime.now(UTC)
        password_valid = verify_password(data.password, user.password_hash if user else dummy_password_hash())
        if user is None or not self._can_attempt(user, now) or not password_valid:
            if user is not None:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= self.settings.max_failed_logins:
                    user.locked_until = now + timedelta(minutes=self.settings.lockout_minutes)
                await self._audit("LOGIN_FAILED", user)
                self.session.add(LoginHistory(
                    user_id=user.id, successful=False, failure_reason="invalid_credentials",
                    user_agent=user_agent, ip_address=ip_address,
                ))
                await self.session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
        if not user.is_active:
            self.session.add(LoginHistory(
                user_id=user.id, successful=False, failure_reason="inactive",
                user_agent=user_agent, ip_address=ip_address,
            ))
            await self.session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        tokens, _ = await self._issue_session(user, user_agent, ip_address)
        await self._audit("LOGIN", user)
        self.session.add(LoginHistory(
            user_id=user.id, successful=True, user_agent=user_agent, ip_address=ip_address,
        ))
        await self.session.commit()
        return tokens

    async def refresh(self, refresh_token: str, user_agent: str | None, ip_address: str | None) -> TokenResponse:
        session = await self.repository.get_session(hash_token(refresh_token), lock=True)
        now = datetime.now(UTC)
        if session is None or session.revoked_at is not None or self._is_expired(session.expires_at, now):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")
        user = await self.repository.get_user(session.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")
        session.revoked_at = now
        tokens, replacement = await self._issue_session(user, user_agent, ip_address)
        session.replaced_by_id = replacement.id
        session.last_used_at = now
        await self.session.commit()
        return tokens

    async def logout(self, refresh_token: str) -> None:
        session = await self.repository.get_session(hash_token(refresh_token))
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def change_password(self, user: User, data: ChangePasswordRequest) -> None:
        if not verify_password(data.current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
        user.password_hash = hash_password(data.new_password)
        user.password_status = "set"
        await self.repository.revoke_user_sessions(user.id)
        await self._audit("PASSWORD_CHANGED", user)
        await self.session.commit()

    async def request_password_reset(self, email: str) -> str | None:
        user = await self.repository.find_user(email)
        if user is None or not user.is_active:
            return None
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash="pending",
            expires_at=datetime.now(UTC) + timedelta(minutes=self.settings.password_reset_minutes),
        )
        self.session.add(reset)
        await self.session.flush()
        raw_token = password_reset_token(str(reset.id), self.settings)
        reset.token_hash = hash_token(raw_token)
        await NotificationService(self.session, self.settings).publish(
            DomainEvent(
                event_type=PASSWORD_RESET,
                subject_id=user.id,
                user_id=user.id,
                payload={"password_reset_token_id": reset.id},
                idempotency_key=f"password-reset:{reset.id}",
            ),
            email=True,
        )
        await self.session.commit()
        return raw_token

    async def confirm_password_reset(self, data: PasswordResetConfirm) -> None:
        reset_token = await self.repository.find_password_reset_token(hash_token(data.token), lock=True)
        now = datetime.now(UTC)
        if (
            reset_token is None
            or reset_token.used_at is not None
            or self._is_expired(reset_token.expires_at, now)
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")
        user = await self.repository.get_user(reset_token.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")
        user.password_hash = hash_password(data.new_password)
        user.password_status = "set"
        reset_token.used_at = now
        await self.repository.revoke_user_sessions(user.id)
        await self._audit("PASSWORD_RESET", user)
        await self.session.commit()

    async def _issue_session(self, user: User, user_agent: str | None, ip_address: str | None) -> tuple[TokenResponse, AuthSession]:
        refresh = new_refresh_token()
        auth_session = AuthSession(
            user_id=user.id,
            refresh_token_hash=hash_token(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=self.settings.refresh_token_days),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.session.add(auth_session)
        return TokenResponse(
            access_token=create_access_token(str(user.id), self.settings),
            refresh_token=refresh,
            expires_in=self.settings.access_token_minutes * 60,
        ), auth_session

    async def _audit(self, action: str, user: User) -> None:
        self.session.add(AuditLog(
            user_id=user.id, action=action, entity_type="user", entity_id=user.id,
            details=json.dumps({"email": user.email}),
        ))

    @staticmethod
    def _can_attempt(user: User, now: datetime) -> bool:
        locked_until = user.locked_until
        if locked_until is None:
            return True
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=UTC)
        return locked_until <= now

    @staticmethod
    def _is_expired(expires_at: datetime, now: datetime) -> bool:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at <= now
