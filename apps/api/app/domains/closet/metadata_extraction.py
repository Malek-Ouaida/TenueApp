from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import settings
from app.domains.closet.models import ProviderResultStatus
from app.domains.closet.taxonomy import (
    CATEGORY_SUBCATEGORIES,
    OCCASION_TAGS,
    SEASON_TAGS,
    STYLE_TAGS,
)

METADATA_EXTRACTION_TASK_TYPE = "metadata_extraction"
GEMINI_PROVIDER_NAME = "gemini"
NOOP_PROVIDER_NAME = "noop"


@dataclass(frozen=True)
class MetadataExtractionResult:
    provider_name: str
    provider_model: str | None
    provider_version: str | None
    status: ProviderResultStatus
    sanitized_payload: dict[str, Any]
    raw_fields: dict[str, Any] | None


class MetadataExtractionProvider(Protocol):
    provider_name: str

    def extract_metadata(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> MetadataExtractionResult: ...


class NoopMetadataExtractionProvider:
    provider_name = NOOP_PROVIDER_NAME

    def __init__(self, *, reason: str) -> None:
        self.reason = reason

    def extract_metadata(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> MetadataExtractionResult:
        del image_bytes, filename, mime_type
        return MetadataExtractionResult(
            provider_name=self.provider_name,
            provider_model=None,
            provider_version=None,
            status=ProviderResultStatus.FAILED,
            sanitized_payload={
                "reason_code": "provider_disabled",
                "message": self.reason,
            },
            raw_fields=None,
        )


class GeminiMetadataExtractionProvider:
    provider_name = GEMINI_PROVIDER_NAME

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract_metadata(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> MetadataExtractionResult:
        url = resolve_gemini_endpoint(base_url=self.base_url, model=self.model)
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": build_extraction_prompt()},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    url,
                    params={"key": self.api_key},
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
        except httpx.RequestError as exc:
            return MetadataExtractionResult(
                provider_name=self.provider_name,
                provider_model=self.model,
                provider_version=None,
                status=ProviderResultStatus.FAILED,
                sanitized_payload={
                    "request_url": url,
                    "filename": filename,
                    "mime_type": mime_type,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                raw_fields=None,
            )

        provider_version = response.headers.get("x-goog-api-client")
        if not response.is_success:
            return MetadataExtractionResult(
                provider_name=self.provider_name,
                provider_model=self.model,
                provider_version=provider_version,
                status=ProviderResultStatus.FAILED,
                sanitized_payload={
                    "request_url": url,
                    "status_code": response.status_code,
                    "error": _extract_error_payload(response),
                },
                raw_fields=None,
            )

        try:
            response_payload = response.json()
        except ValueError:
            text = response.text.strip()
            return MetadataExtractionResult(
                provider_name=self.provider_name,
                provider_model=self.model,
                provider_version=provider_version,
                status=ProviderResultStatus.FAILED,
                sanitized_payload={
                    "request_url": url,
                    "status_code": response.status_code,
                    "message": "Gemini returned non-JSON output.",
                    "response_preview": text[:500],
                },
                raw_fields=None,
            )

        extracted_text = _extract_response_text(response_payload)
        if extracted_text is None:
            return MetadataExtractionResult(
                provider_name=self.provider_name,
                provider_model=self.model,
                provider_version=provider_version,
                status=ProviderResultStatus.FAILED,
                sanitized_payload={
                    "request_url": url,
                    "status_code": response.status_code,
                    "message": "Gemini response did not contain a text payload.",
                },
                raw_fields=None,
            )

        normalized_text = _strip_code_fences(extracted_text)
        try:
            raw_fields = json.loads(normalized_text)
        except ValueError as exc:
            return MetadataExtractionResult(
                provider_name=self.provider_name,
                provider_model=self.model,
                provider_version=provider_version,
                status=ProviderResultStatus.FAILED,
                sanitized_payload={
                    "request_url": url,
                    "status_code": response.status_code,
                    "message": "Gemini returned invalid extraction JSON.",
                    "error_type": type(exc).__name__,
                    "response_preview": normalized_text[:500],
                },
                raw_fields=None,
            )

        if not isinstance(raw_fields, dict):
            return MetadataExtractionResult(
                provider_name=self.provider_name,
                provider_model=self.model,
                provider_version=provider_version,
                status=ProviderResultStatus.FAILED,
                sanitized_payload={
                    "request_url": url,
                    "status_code": response.status_code,
                    "message": "Gemini returned a non-object extraction payload.",
                    "response_preview": normalized_text[:500],
                },
                raw_fields=None,
            )

        return MetadataExtractionResult(
            provider_name=self.provider_name,
            provider_model=self.model,
            provider_version=provider_version,
            status=ProviderResultStatus.SUCCEEDED,
            sanitized_payload={
                "request_url": url,
                "status_code": response.status_code,
                "fields_present": sorted(str(key) for key in raw_fields.keys()),
            },
            raw_fields=raw_fields,
        )


def build_metadata_extraction_provider() -> MetadataExtractionProvider:
    provider_name = settings.closet_metadata_extraction_provider.strip().lower()
    if provider_name != GEMINI_PROVIDER_NAME:
        return NoopMetadataExtractionProvider(reason="Metadata extraction is disabled.")

    if not settings.gemini_api_key:
        return NoopMetadataExtractionProvider(
            reason="Metadata extraction provider credentials are not configured.",
        )

    return GeminiMetadataExtractionProvider(
        api_key=settings.gemini_api_key,
        base_url=settings.gemini_base_url,
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
    )


def resolve_gemini_endpoint(*, base_url: str, model: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith(":generateContent"):
        return normalized
    if "/models/" in normalized:
        return normalized
    return f"{normalized}/models/{model}:generateContent"


def build_extraction_prompt() -> str:
    categories = ", ".join(CATEGORY_SUBCATEGORIES.keys())
    subcategories = "; ".join(
        f"{category}: {', '.join(options)}" for category, options in CATEGORY_SUBCATEGORIES.items()
    )
    return (
        "You extract raw structured garment metadata from a single clothing-item image. "
        "Return JSON only, with no markdown. "
        "Use only these top-level fields when present: "
        "title, category, subcategory, colors, material, pattern, brand, style_tags, "
        "occasion_tags, season_tags. "
        "Scalar fields must be objects with keys: value, confidence, applicability_state, notes. "
        "List fields must be objects with keys: values, confidence, applicability_state, notes. "
        "applicability_state must be one of value, unknown, not_applicable. "
        f"Allowed categories: {categories}. "
        f"Allowed subcategories by category: {subcategories}. "
        f"Style tags should prefer: {', '.join(STYLE_TAGS)}. "
        f"Occasion tags should prefer: {', '.join(OCCASION_TAGS)}. "
        f"Season tags should prefer: {', '.join(SEASON_TAGS)}. "
        "Do not invent unsupported fields."
    )


def _extract_response_text(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return None

    texts: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])

    if not texts:
        return None
    return "\n".join(texts).strip() or None


def _strip_code_fences(value: str) -> str:
    stripped = value.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_error_payload(response: httpx.Response) -> dict[str, Any] | str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:500] if text else "Gemini returned an empty error response."

    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"items": payload}
    return str(payload)
