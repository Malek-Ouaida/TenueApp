from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthCredentialsRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshSessionRequest(BaseModel):
    refresh_token: str = Field(min_length=10)

    @field_validator("refresh_token")
    @classmethod
    def normalize_refresh_token(cls, value: str) -> str:
        return value.strip()


class AuthUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    auth_provider: str
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class AuthSession(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    expires_at: datetime | None


class AuthSessionResponse(BaseModel):
    user: AuthUser
    session: AuthSession


class AuthRegistrationResponse(BaseModel):
    user: AuthUser
    session: AuthSession | None
    email_verification_required: bool


class AuthMeResponse(BaseModel):
    user: AuthUser


class LogoutResponse(BaseModel):
    success: Literal[True]
