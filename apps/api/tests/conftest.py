from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.auth import get_auth_provider
from app.db.base import Base
from app.db.session import get_db_session
from app.domains.auth.provider import (
    AuthProviderError,
    ProviderRegistration,
    ProviderSession,
    ProviderUser,
)
from app.main import app

engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class FakeAuthProvider:
    def __init__(self) -> None:
        self.users_by_email: dict[str, dict[str, str]] = {}
        self.access_tokens: dict[str, str] = {}
        self.refresh_tokens: dict[str, str] = {}
        self.require_email_verification_on_signup = False

    def sign_up(self, *, email: str, password: str) -> ProviderRegistration:
        normalized_email = email.strip().lower()
        if normalized_email in self.users_by_email:
            raise AuthProviderError(400, "User already registered.")

        subject = str(uuid4())
        self.users_by_email[normalized_email] = {
            "subject": subject,
            "email": normalized_email,
            "password": password,
        }

        if self.require_email_verification_on_signup:
            return ProviderRegistration(
                user=ProviderUser(subject=subject, email=normalized_email),
                session=None,
                email_verification_required=True,
            )

        return ProviderRegistration(
            user=ProviderUser(subject=subject, email=normalized_email),
            session=self._issue_session(subject=subject, email=normalized_email),
            email_verification_required=False,
        )

    def sign_in_with_password(self, *, email: str, password: str) -> ProviderSession:
        normalized_email = email.strip().lower()
        user = self.users_by_email.get(normalized_email)
        if user is None or user["password"] != password:
            raise AuthProviderError(401, "Invalid login credentials.")

        return self._issue_session(subject=user["subject"], email=normalized_email)

    def refresh_session(self, *, refresh_token: str) -> ProviderSession:
        subject = self.refresh_tokens.pop(refresh_token, None)
        if subject is None:
            raise AuthProviderError(401, "Invalid refresh token.")

        email = self._email_for_subject(subject)
        return self._issue_session(subject=subject, email=email)

    def sign_out(self, *, access_token: str) -> None:
        subject = self.access_tokens.pop(access_token, None)
        if subject is None:
            raise AuthProviderError(401, "Session not found.")

        stale_refresh_tokens = [
            token
            for token, token_subject in self.refresh_tokens.items()
            if token_subject == subject
        ]
        for token in stale_refresh_tokens:
            self.refresh_tokens.pop(token, None)

    def get_user(self, *, access_token: str) -> ProviderUser:
        subject = self.access_tokens.get(access_token)
        if subject is None:
            raise AuthProviderError(401, "Invalid access token.")

        return ProviderUser(subject=subject, email=self._email_for_subject(subject))

    def _issue_session(self, *, subject: str, email: str) -> ProviderSession:
        access_token = f"access-{uuid4()}"
        refresh_token = f"refresh-{uuid4()}"
        self.access_tokens[access_token] = subject
        self.refresh_tokens[refresh_token] = subject
        expires_in = 3600

        return ProviderSession(
            user=ProviderUser(subject=subject, email=email),
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        )

    def _email_for_subject(self, subject: str) -> str:
        for user in self.users_by_email.values():
            if user["subject"] == subject:
                return user["email"]

        raise AuthProviderError(404, "User not found.")


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def fake_auth_provider() -> FakeAuthProvider:
    return FakeAuthProvider()


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(fake_auth_provider: FakeAuthProvider) -> Generator[TestClient, None, None]:
    def override_get_db_session() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_auth_provider] = lambda: fake_auth_provider

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
