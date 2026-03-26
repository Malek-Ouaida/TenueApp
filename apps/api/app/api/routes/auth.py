from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.auth import CurrentUser, get_access_token, get_auth_service
from app.api.schemas.auth import (
    AuthCredentialsRequest,
    AuthMeResponse,
    AuthRegistrationResponse,
    AuthSession,
    AuthSessionResponse,
    AuthUser,
    LogoutResponse,
    RefreshSessionRequest,
)
from app.domains.auth.models import User
from app.domains.auth.provider import ProviderSession
from app.domains.auth.service import AuthService, AuthServiceError, RegistrationResult

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: AuthCredentialsRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthRegistrationResponse:
    try:
        registration = auth_service.register(email=payload.email, password=payload.password)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_auth_registration_response(registration=registration)


@router.post("/login", response_model=AuthSessionResponse)
def login(
    payload: AuthCredentialsRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    try:
        user, session = auth_service.login(email=payload.email, password=payload.password)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_auth_session_response(user=user, session=session)


@router.post("/refresh", response_model=AuthSessionResponse)
def refresh_session(
    payload: RefreshSessionRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    try:
        user, session = auth_service.refresh(refresh_token=payload.refresh_token)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_auth_session_response(user=user, session=session)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    access_token: Annotated[str, Depends(get_access_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LogoutResponse:
    try:
        auth_service.logout(access_token=access_token)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return LogoutResponse(success=True)


@router.get("/me", response_model=AuthMeResponse)
def read_me(current_user: CurrentUser) -> AuthMeResponse:
    return AuthMeResponse(user=AuthUser.model_validate(current_user))


def build_auth_session_response(*, user: User, session: ProviderSession) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=AuthUser.model_validate(user),
        session=AuthSession(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            token_type=session.token_type,
            expires_in=session.expires_in,
            expires_at=session.expires_at,
        ),
    )


def build_auth_registration_response(
    *,
    registration: RegistrationResult,
) -> AuthRegistrationResponse:
    session = registration.session

    return AuthRegistrationResponse(
        user=AuthUser.model_validate(registration.user),
        session=(
            AuthSession(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                token_type=session.token_type,
                expires_in=session.expires_in,
                expires_at=session.expires_at,
            )
            if session is not None
            else None
        ),
        email_verification_required=registration.email_verification_required,
    )
