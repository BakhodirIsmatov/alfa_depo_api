from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(
    subject: str, *, session_id: str | None = None, auth_version: int = 1
) -> tuple[str, int, str, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.jwt_expire_minutes)
    jti = session_id or str(uuid4())
    payload = {
        "sub": subject,
        "jti": jti,
        "ver": auth_version,
        "iat": now,
        "exp": expires,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "type": "access",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, settings.jwt_expire_minutes * 60, jti, expires


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "jti", "ver", "iat", "exp", "iss", "aud", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired access token") from exc
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid access token")
    return payload
