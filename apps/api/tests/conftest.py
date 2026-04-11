from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.auth import get_auth_provider
from app.api.dependencies.closet import (
    get_background_removal_provider,
    get_metadata_extraction_provider,
    get_storage_client,
)
from app.api.dependencies.wear import get_wear_detection_provider
from app.core.storage import InMemoryStorageClient
from app.db.base import Base
from app.db.session import get_db_session
from app.domains.auth.provider import (
    AuthProviderError,
    ProviderRegistration,
    ProviderSession,
    ProviderUser,
)
from app.domains.closet.background_removal import BackgroundRemovalResult
from app.domains.closet.metadata_extraction import MetadataExtractionResult
from app.domains.closet.models import ProviderResultStatus
from app.domains.wear.detection import DetectedOutfitItem, OutfitDetectionResult
from app.domains.wear.models import WearProviderResultStatus
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


class FakeBackgroundRemovalProvider:
    provider_name = "fake_background_removal"

    def __init__(self) -> None:
        self.status = ProviderResultStatus.FAILED
        self.result_image_bytes: bytes | None = None
        self.result_mime_type: str | None = None
        self.payload: dict[str, Any] = {
            "reason_code": "provider_disabled",
            "message": "Background removal is disabled in tests.",
        }
        self.raise_error: Exception | None = None

    def succeed(
        self,
        *,
        image_bytes: bytes,
        mime_type: str = "image/png",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.status = ProviderResultStatus.SUCCEEDED
        self.result_image_bytes = image_bytes
        self.result_mime_type = mime_type
        self.payload = payload or {"message": "Processed by fake provider."}
        self.raise_error = None

    def fail(self, *, payload: dict[str, Any] | None = None) -> None:
        self.status = ProviderResultStatus.FAILED
        self.result_image_bytes = None
        self.result_mime_type = None
        self.payload = payload or {
            "reason_code": "provider_failed",
            "message": "Fake provider fallback.",
        }
        self.raise_error = None

    def crash(self, exc: Exception) -> None:
        self.raise_error = exc

    def remove_background(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> BackgroundRemovalResult:
        del image_bytes, filename, mime_type
        if self.raise_error is not None:
            raise self.raise_error

        return BackgroundRemovalResult(
            provider_name=self.provider_name,
            provider_model=None,
            provider_version="test",
            status=self.status,
            sanitized_payload=self.payload,
            image_bytes=self.result_image_bytes,
            mime_type=self.result_mime_type,
        )


class FakeMetadataExtractionProvider:
    provider_name = "fake_metadata_extraction"

    def __init__(self) -> None:
        self.status = ProviderResultStatus.FAILED
        self.raw_fields: dict[str, Any] | None = None
        self.payload: dict[str, Any] = {
            "reason_code": "provider_disabled",
            "message": "Metadata extraction is disabled in tests.",
        }
        self.raise_error: Exception | None = None
        self.calls: list[dict[str, Any]] = []

    def succeed(
        self,
        *,
        raw_fields: dict[str, Any],
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.status = ProviderResultStatus.SUCCEEDED
        self.raw_fields = raw_fields
        self.payload = payload or {"message": "Extracted by fake provider."}
        self.raise_error = None

    def partial(
        self,
        *,
        raw_fields: dict[str, Any],
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.status = ProviderResultStatus.PARTIAL
        self.raw_fields = raw_fields
        self.payload = payload or {"message": "Partially extracted by fake provider."}
        self.raise_error = None

    def fail(self, *, payload: dict[str, Any] | None = None) -> None:
        self.status = ProviderResultStatus.FAILED
        self.raw_fields = None
        self.payload = payload or {
            "reason_code": "provider_failed",
            "message": "Fake metadata extraction fallback.",
        }
        self.raise_error = None

    def crash(self, exc: Exception) -> None:
        self.raise_error = exc

    def extract_metadata(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> MetadataExtractionResult:
        self.calls.append(
            {
                "image_bytes": image_bytes,
                "filename": filename,
                "mime_type": mime_type,
            }
        )
        if self.raise_error is not None:
            raise self.raise_error

        return MetadataExtractionResult(
            provider_name=self.provider_name,
            provider_model="fake-model",
            provider_version="test",
            status=self.status,
            sanitized_payload=self.payload,
            raw_fields=self.raw_fields,
        )


class FakeWearDetectionProvider:
    provider_name = "fake_wear_detection"

    def __init__(self) -> None:
        self.status = WearProviderResultStatus.FAILED
        self.detections: list[DetectedOutfitItem] = []
        self.payload: dict[str, Any] = {
            "reason_code": "provider_disabled",
            "message": "Wear detection is disabled in tests.",
        }
        self.raise_error: Exception | None = None

    def succeed(
        self,
        *,
        detections: list[DetectedOutfitItem],
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.status = WearProviderResultStatus.SUCCEEDED
        self.detections = detections
        self.payload = payload or {"message": "Detected by fake provider."}
        self.raise_error = None

    def fail(self, *, payload: dict[str, Any] | None = None) -> None:
        self.status = WearProviderResultStatus.FAILED
        self.detections = []
        self.payload = payload or {
            "reason_code": "provider_failed",
            "message": "Fake wear detection fallback.",
        }
        self.raise_error = None

    def crash(self, exc: Exception) -> None:
        self.raise_error = exc

    def detect_outfit_items(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> OutfitDetectionResult:
        del image_bytes, filename, mime_type
        if self.raise_error is not None:
            raise self.raise_error

        return OutfitDetectionResult(
            provider_name=self.provider_name,
            provider_model="fake-model",
            provider_version="test",
            status=self.status,
            sanitized_payload=self.payload,
            detections=self.detections,
        )


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
def fake_storage_client() -> InMemoryStorageClient:
    return InMemoryStorageClient()


@pytest.fixture()
def fake_background_removal_provider() -> FakeBackgroundRemovalProvider:
    provider = FakeBackgroundRemovalProvider()
    provider.fail()
    return provider


@pytest.fixture()
def fake_metadata_extraction_provider() -> FakeMetadataExtractionProvider:
    provider = FakeMetadataExtractionProvider()
    provider.fail()
    return provider


@pytest.fixture()
def fake_wear_detection_provider() -> FakeWearDetectionProvider:
    provider = FakeWearDetectionProvider()
    provider.fail()
    return provider


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(
    fake_auth_provider: FakeAuthProvider,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: FakeBackgroundRemovalProvider,
    fake_metadata_extraction_provider: FakeMetadataExtractionProvider,
    fake_wear_detection_provider: FakeWearDetectionProvider,
) -> Generator[TestClient, None, None]:
    def override_get_db_session() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_auth_provider] = lambda: fake_auth_provider
    app.dependency_overrides[get_storage_client] = lambda: fake_storage_client
    app.dependency_overrides[get_background_removal_provider] = lambda: (
        fake_background_removal_provider
    )
    app.dependency_overrides[get_metadata_extraction_provider] = lambda: (
        fake_metadata_extraction_provider
    )
    app.dependency_overrides[get_wear_detection_provider] = lambda: fake_wear_detection_provider

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def client_without_storage_override(
    fake_auth_provider: FakeAuthProvider,
    fake_background_removal_provider: FakeBackgroundRemovalProvider,
    fake_metadata_extraction_provider: FakeMetadataExtractionProvider,
    fake_wear_detection_provider: FakeWearDetectionProvider,
) -> Generator[TestClient, None, None]:
    def override_get_db_session() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_auth_provider] = lambda: fake_auth_provider
    app.dependency_overrides[get_background_removal_provider] = lambda: (
        fake_background_removal_provider
    )
    app.dependency_overrides[get_metadata_extraction_provider] = lambda: (
        fake_metadata_extraction_provider
    )
    app.dependency_overrides[get_wear_detection_provider] = lambda: fake_wear_detection_provider

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
