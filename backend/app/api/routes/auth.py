from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.errors import ApiError
from app.config import Settings, get_settings
from app.db.session import get_db
from app.models.identity import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.security import create_access_token, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = session.scalar(select(User).where(User.username == payload.username.strip()))
    if user is None or not user.is_active or not verify_password(
        payload.password, user.password_hash
    ):
        raise ApiError(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Usuario o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        subject=user.username,
        role=user.role.value,
        settings=settings,
    )
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(user)
