import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas.profile import ProfileUpdateRequest
from app.domains.auth.models import User
from app.domains.profile.repository import ProfileRepository

USERNAME_PATTERN = re.compile(r"^[a-z0-9]+(?:[._][a-z0-9]+)*$")
RESERVED_USERNAMES = {
    "api",
    "auth",
    "edit",
    "login",
    "logout",
    "me",
    "profile",
    "profiles",
    "register",
    "settings",
    "u",
}


class ProfileServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ProfileService:
    def __init__(
        self,
        *,
        session: Session,
        repository: ProfileRepository,
    ) -> None:
        self.session = session
        self.repository = repository

    def get_my_profile(self, *, user: User) -> User:
        profile = self.repository.get_by_id(user.id)
        if profile is None:
            raise ProfileServiceError(404, "Profile not found.")

        return profile

    def get_profile_by_username(self, *, username: str) -> User:
        normalized_username = self._normalize_lookup_username(username)
        self._validate_username(normalized_username)

        profile = self.repository.get_by_username(normalized_username)
        if profile is None:
            raise ProfileServiceError(404, "Profile not found.")

        return profile

    def update_my_profile(
        self,
        *,
        user: User,
        payload: ProfileUpdateRequest,
    ) -> User:
        fields = payload.model_fields_set
        if not fields:
            return self.get_my_profile(user=user)

        if "username" in fields:
            self._apply_username_update(user=user, username=payload.username)

        if "display_name" in fields:
            user.display_name = payload.display_name

        if "bio" in fields:
            user.bio = payload.bio

        if "avatar_path" in fields:
            user.avatar_path = payload.avatar_path

        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            if self._is_username_conflict(exc):
                raise ProfileServiceError(409, "Username is already taken.") from exc
            raise

        self.session.refresh(user)
        return user

    def _apply_username_update(self, *, user: User, username: str | None) -> None:
        if username is None:
            user.username = None
            return

        self._validate_username(username)

        existing_profile = self.repository.get_by_username(username)
        if existing_profile is not None and existing_profile.id != user.id:
            raise ProfileServiceError(409, "Username is already taken.")

        user.username = username

    def _normalize_lookup_username(self, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ProfileServiceError(422, "Username is required.")
        return normalized

    def _validate_username(self, username: str) -> None:
        if username in RESERVED_USERNAMES:
            raise ProfileServiceError(422, "That username is reserved.")

        if len(username) < 3 or len(username) > 30:
            raise ProfileServiceError(422, "Username must be between 3 and 30 characters.")

        if not USERNAME_PATTERN.fullmatch(username):
            raise ProfileServiceError(
                422,
                (
                    "Username may contain lowercase letters, numbers, underscores, and "
                    "periods, with separators only between letters or numbers."
                ),
            )

    def _is_username_conflict(self, exc: IntegrityError) -> bool:
        message = str(exc).lower()
        return "username" in message and "unique" in message
