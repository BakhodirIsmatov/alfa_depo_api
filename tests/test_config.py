import pytest
from pydantic import ValidationError

from app.core.config import MAX_JWT_EXPIRE_MINUTES, Settings


def test_existing_thirty_day_jwt_expiration_contract_is_valid() -> None:
    settings = Settings(
        _env_file=None,
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
        jwt_expire_minutes=43_200,
    )

    assert settings.jwt_expire_minutes == MAX_JWT_EXPIRE_MINUTES


def test_jwt_expiration_remains_bounded() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            jwt_secret_key="test-secret-key-with-at-least-32-characters",
            jwt_expire_minutes=MAX_JWT_EXPIRE_MINUTES + 1,
        )
