from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import settings
from app.domains.closet.models import ProviderResultStatus

BACKGROUND_REMOVAL_TASK_TYPE = "background_removal"
PHOTOROOM_PROVIDER_NAME = "photoroom"
NOOP_PROVIDER_NAME = "noop"


@dataclass(frozen=True)
class BackgroundRemovalResult:
    provider_name: str
    provider_model: str | None
    provider_version: str | None
    status: ProviderResultStatus
    sanitized_payload: dict[str, Any]
    image_bytes: bytes | None
    mime_type: str | None


class BackgroundRemovalProvider(Protocol):
    provider_name: str

    def remove_background(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> BackgroundRemovalResult: ...


class NoopBackgroundRemovalProvider:
    provider_name = NOOP_PROVIDER_NAME

    def __init__(self, *, reason: str) -> None:
        self.reason = reason

    def remove_background(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> BackgroundRemovalResult:
        del image_bytes, filename, mime_type
        return BackgroundRemovalResult(
            provider_name=self.provider_name,
            provider_model=None,
            provider_version=None,
            status=ProviderResultStatus.FAILED,
            sanitized_payload={
                "reason_code": "provider_disabled",
                "message": self.reason,
            },
            image_bytes=None,
            mime_type=None,
        )


class PhotoRoomBackgroundRemovalProvider:
    provider_name = PHOTOROOM_PROVIDER_NAME

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def remove_background(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> BackgroundRemovalResult:
        url = resolve_photoroom_endpoint(self.base_url)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    url,
                    headers={
                        "x-api-key": self.api_key,
                        "Accept": "image/png, application/json",
                    },
                    files={"image_file": (filename, image_bytes, mime_type)},
                    data={"format": "png", "channels": "rgba"},
                )
        except httpx.RequestError as exc:
            return BackgroundRemovalResult(
                provider_name=self.provider_name,
                provider_model=None,
                provider_version=None,
                status=ProviderResultStatus.FAILED,
                sanitized_payload={
                    "request_url": url,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                image_bytes=None,
                mime_type=None,
            )

        if response.is_success:
            return BackgroundRemovalResult(
                provider_name=self.provider_name,
                provider_model=None,
                provider_version=response.headers.get("x-photoroom-version"),
                status=ProviderResultStatus.SUCCEEDED,
                sanitized_payload={
                    "request_url": url,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type"),
                    "content_length": len(response.content),
                },
                image_bytes=response.content,
                mime_type=response.headers.get("content-type", "image/png"),
            )

        return BackgroundRemovalResult(
            provider_name=self.provider_name,
            provider_model=None,
            provider_version=response.headers.get("x-photoroom-version"),
            status=ProviderResultStatus.FAILED,
            sanitized_payload={
                "request_url": url,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "error": _extract_error_payload(response),
            },
            image_bytes=None,
            mime_type=None,
        )


def build_background_removal_provider() -> BackgroundRemovalProvider:
    provider_name = settings.closet_background_removal_provider.strip().lower()
    if provider_name != PHOTOROOM_PROVIDER_NAME:
        return NoopBackgroundRemovalProvider(reason="Background removal is disabled.")

    if not settings.photoroom_api_key:
        return NoopBackgroundRemovalProvider(
            reason="Background removal provider credentials are not configured.",
        )

    return PhotoRoomBackgroundRemovalProvider(
        api_key=settings.photoroom_api_key,
        base_url=settings.photoroom_base_url,
        timeout_seconds=settings.photoroom_timeout_seconds,
    )


def resolve_photoroom_endpoint(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if "/v1/" in normalized or "/v2/" in normalized:
        return normalized
    return f"{normalized}/v1/segment"


def _extract_error_payload(response: httpx.Response) -> dict[str, Any] | str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:500] if text else "PhotoRoom returned an empty error response."

    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"items": payload}
    return str(payload)
