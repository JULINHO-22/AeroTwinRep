from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import Settings, get_settings
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.identity import SensorDevice, User
from app.security import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    username = decode_access_token(credentials.credentials, settings)
    if username is None:
        raise _unauthorized()
    user = session.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


def require_roles(*roles: UserRole) -> Callable:
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise ApiError(
                status_code=403,
                code="ROLE_FORBIDDEN",
                message="Tu rol no permite realizar esta operación.",
                details={"required_roles": [role.value for role in roles]},
            )
        return user

    return dependency


def _unauthorized() -> ApiError:
    return ApiError(
        status_code=401,
        code="INVALID_TOKEN",
        message="El token de acceso es inválido o expiró.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_sensor(
    session: Annotated[Session, Depends(get_db)],
    sensor_token: Annotated[str | None, Header(alias="X-Sensor-Token")] = None,
) -> SensorDevice:
    """Authenticate a physical device with its dedicated opaque token."""
    import hashlib

    if not sensor_token:
        raise ApiError(
            status_code=401,
            code="INVALID_SENSOR_TOKEN",
            message="El dispositivo sensor no está vinculado o su token no es válido.",
        )
    token_hash = hashlib.sha256(sensor_token.encode("utf-8")).hexdigest()
    device = session.scalar(
        select(SensorDevice).where(SensorDevice.token_hash == token_hash)
    )
    if device is None:
        raise ApiError(
            status_code=401,
            code="INVALID_SENSOR_TOKEN",
            message="El dispositivo sensor no está vinculado o su token no es válido.",
        )
    return device
