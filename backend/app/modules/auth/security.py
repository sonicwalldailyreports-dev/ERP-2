import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

password_hasher = PasswordHasher()
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "x3YsURoI9sjAtq9WTdsYmw$"
    "iMyoOVqmqtyu8yJmDDVF9ogilZNbv67DxbnzYAofwLE"
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def dummy_password_hash() -> str:
    return _DUMMY_PASSWORD_HASH


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_reset_token(token_id: str, settings: Settings) -> str:
    """Derive a delivery token from the protected reset reference.

    The database stores only its hash; workers can reconstruct the token from
    the reference without putting the secret in a job payload.
    """
    digest = hmac.new(settings.secret_key.encode("utf-8"), token_id.encode("ascii"), hashlib.sha256)
    return f"{token_id}.{digest.hexdigest()}"


def create_access_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": user_id, "type": "access", "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes)},
        settings.secret_key,
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: Settings) -> str:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload.get("type") != "access" or not isinstance(payload.get("sub"), str):
        raise ValueError("Invalid access token")
    return payload["sub"]
