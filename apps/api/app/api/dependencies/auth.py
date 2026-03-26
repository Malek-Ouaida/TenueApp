from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db_session
from app.domains.auth.models import User
from app.domains.auth.provider import SupabaseAuthProvider
from app.domains.auth.repository import UserRepository
from app.domains.auth.service import AuthService, AuthServiceError

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_provider() -> SupabaseAuthProvider:
    return SupabaseAuthProvider(
        base_url=settings.supabase_url,
        api_key=settings.supabase_client_key,
        timeout_seconds=settings.supabase_auth_timeout_seconds,
    )


def get_auth_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    provider: Annotated[SupabaseAuthProvider, Depends(get_auth_provider)],
) -> AuthService:
    return AuthService(
        session=db_session,
        repository=UserRepository(db_session),
        provider=provider,
    )


def get_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


def get_current_user(
    access_token: Annotated[str, Depends(get_access_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    try:
        return auth_service.get_current_user(access_token=access_token)
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[User, Depends(get_current_user)]
