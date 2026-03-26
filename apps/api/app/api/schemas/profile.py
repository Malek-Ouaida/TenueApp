from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ProfileView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str | None
    display_name: str | None
    bio: str | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime


class ProfileResponse(BaseModel):
    profile: ProfileView


class ProfileUpdateRequest(BaseModel):
    username: str | None = None
    display_name: str | None = None
    bio: str | None = None
    avatar_path: str | None = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip().lower()
        if not normalized:
            return None

        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None

        if len(normalized) > 80:
            raise ValueError("Display name must be 80 characters or fewer.")

        return normalized

    @field_validator("bio")
    @classmethod
    def normalize_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None

        if len(normalized) > 280:
            raise ValueError("Bio must be 280 characters or fewer.")

        return normalized

    @field_validator("avatar_path")
    @classmethod
    def normalize_avatar_path(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None

        if len(normalized) > 512:
            raise ValueError("Avatar reference must be 512 characters or fewer.")

        return normalized
