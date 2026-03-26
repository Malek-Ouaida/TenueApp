from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.domains.auth.models import User
from app.domains.auth.provider import (
    AuthProviderError,
    ProviderSession,
    ProviderUser,
    SupabaseAuthProvider,
)
from app.domains.auth.repository import UserRepository


class AuthServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class AuthService:
    def __init__(
        self,
        *,
        session: Session,
        repository: UserRepository,
        provider: SupabaseAuthProvider,
    ) -> None:
        self.session = session
        self.repository = repository
        self.provider = provider

    def register(self, *, email: str, password: str) -> tuple[User, ProviderSession]:
        normalized_email = self._normalize_email(email)

        try:
            provider_session = self.provider.sign_up(email=normalized_email, password=password)
            user = self._sync_user(provider_session.user, update_last_login=True)
        except AuthProviderError as exc:
            raise AuthServiceError(exc.status_code, exc.detail) from exc

        return user, provider_session

    def login(self, *, email: str, password: str) -> tuple[User, ProviderSession]:
        normalized_email = self._normalize_email(email)

        try:
            provider_session = self.provider.sign_in_with_password(
                email=normalized_email,
                password=password,
            )
            user = self._sync_user(provider_session.user, update_last_login=True)
        except AuthProviderError as exc:
            raise AuthServiceError(exc.status_code, exc.detail) from exc

        return user, provider_session

    def refresh(self, *, refresh_token: str) -> tuple[User, ProviderSession]:
        token = refresh_token.strip()
        if not token:
            raise AuthServiceError(422, "Refresh token is required.")

        try:
            provider_session = self.provider.refresh_session(refresh_token=token)
            user = self._sync_user(provider_session.user, update_last_login=False)
        except AuthProviderError as exc:
            raise AuthServiceError(exc.status_code, exc.detail) from exc

        return user, provider_session

    def logout(self, *, access_token: str) -> None:
        token = access_token.strip()
        if not token:
            raise AuthServiceError(401, "Authentication required.")

        try:
            self.provider.sign_out(access_token=token)
        except AuthProviderError as exc:
            raise AuthServiceError(exc.status_code, exc.detail) from exc

    def get_current_user(self, *, access_token: str) -> User:
        token = access_token.strip()
        if not token:
            raise AuthServiceError(401, "Authentication required.")

        try:
            provider_user = self.provider.get_user(access_token=token)
            return self._sync_user(provider_user, update_last_login=False)
        except AuthProviderError as exc:
            raise AuthServiceError(exc.status_code, exc.detail) from exc

    def _sync_user(self, provider_user: ProviderUser, *, update_last_login: bool) -> User:
        last_login_at = datetime.now(UTC) if update_last_login else None
        user = self.repository.sync_from_provider(
            email=provider_user.email,
            auth_provider="supabase",
            auth_subject=provider_user.subject,
            last_login_at=last_login_at,
        )
        self.session.commit()
        self.session.refresh(user)
        return user

    def _normalize_email(self, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise AuthServiceError(422, "Email is required.")
        return normalized
