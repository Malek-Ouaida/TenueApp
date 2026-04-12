from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Protocol

from app.core.config import settings
from app.domains.closet.models import ApplicabilityState
from app.domains.closet.normalization import derive_category_for_subcategory, normalize_field_value
from app.domains.closet.taxonomy import (
    ATTRIBUTES,
    CATEGORY_SUBCATEGORIES,
    COLORS,
    CONTROLLED_SCALAR_VALUES,
    FIT_TAGS,
    LIST_FIELD_NAMES,
    MATERIALS,
    PATTERNS,
    SILHOUETTES,
    SUPPORTED_FIELD_ORDER,
    is_valid_category_subcategory_pair,
)
from app.domains.wear.metadata import normalize_detected_metadata_fields
from app.domains.wear.models import WearProviderResultStatus

OUTFIT_DETECTION_TASK_TYPE = "outfit_detection"
NOOP_PROVIDER_NAME = "noop"
GEMINI_PROVIDER_NAME = "gemini"

_ALLOWED_ROLES = (
    "top",
    "bottom",
    "footwear",
    "outerwear",
    "dress",
    "full_body",
    "bag",
    "accessory",
    "jewelry",
    "hat",
    "scarf",
    "eyewear",
)

_ALLOWED_CATEGORIES = tuple(CATEGORY_SUBCATEGORIES.keys())
_ALLOWED_SUBCATEGORIES = tuple(
    subcategory
    for subcategories in CATEGORY_SUBCATEGORIES.values()
    for subcategory in subcategories
)
_ALLOWED_COLORS = tuple(COLORS)
_ALLOWED_MATERIALS = tuple(MATERIALS)
_ALLOWED_PATTERNS = tuple(PATTERNS)
_ALLOWED_FIT_TAGS = tuple(FIT_TAGS)
_ALLOWED_SILHOUETTES = tuple(SILHOUETTES)
_ALLOWED_ATTRIBUTES = tuple(ATTRIBUTES)

_UPPER_BODY_ROLES = {"top", "outerwear", "dress", "full_body"}
_LOWER_BODY_ROLES = {"bottom", "dress", "full_body"}
_CORE_GARMENT_ROLES = {"top", "outerwear", "bottom", "dress", "full_body"}

_ROLE_SYNONYMS = {
    "glasses": "eyewear",
    "eyeglasses": "eyewear",
    "sunglasses": "eyewear",
    "shoe": "footwear",
    "shoes": "footwear",
    "jacket": "outerwear",
    "coat": "outerwear",
    "blazer": "outerwear",
    "vest": "outerwear",
    "pants": "bottom",
    "trousers": "bottom",
    "jeans": "bottom",
    "skirt": "bottom",
    "shorts": "bottom",
    "bag": "bag",
    "handbag": "bag",
    "purse": "bag",
    "necklace": "jewelry",
    "bracelet": "jewelry",
    "ring": "jewelry",
    "watch": "jewelry",
    "earrings": "jewelry",
    "earring": "jewelry",
}


@dataclass(frozen=True)
class DetectedOutfitItem:
    role: str | None = None
    category: str | None = None
    subcategory: str | None = None
    colors: list[str] = field(default_factory=list)
    material: str | None = None
    pattern: str | None = None
    fit_tags: list[str] = field(default_factory=list)
    silhouette: str | None = None
    attributes: list[str] = field(default_factory=list)
    confidence: float | None = None
    bbox: dict[str, float] | None = None
    metadata: dict[str, Any] | None = None
    sort_index: int | None = None


@dataclass(frozen=True)
class OutfitDetectionResult:
    provider_name: str
    provider_model: str | None
    provider_version: str | None
    status: WearProviderResultStatus
    sanitized_payload: dict[str, Any]
    detections: list[DetectedOutfitItem]


class OutfitDetectionProvider(Protocol):
    provider_name: str

    def detect_outfit_items(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> OutfitDetectionResult: ...


class NoopOutfitDetectionProvider:
    provider_name = NOOP_PROVIDER_NAME

    def __init__(self, *, reason: str) -> None:
        self.reason = reason

    def detect_outfit_items(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> OutfitDetectionResult:
        del image_bytes, filename, mime_type
        return OutfitDetectionResult(
            provider_name=self.provider_name,
            provider_model=None,
            provider_version=None,
            status=_failure_status(),
            sanitized_payload={
                "reason_code": "provider_disabled",
                "message": self.reason,
            },
            detections=[],
        )


class GeminiOutfitDetectionProvider:
    provider_name = GEMINI_PROVIDER_NAME

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds

    def detect_outfit_items(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> OutfitDetectionResult:
        if not self.api_key:
            return self._build_failed_result(
                reason_code="missing_api_key",
                message="Gemini API key is not configured.",
            )

        if not image_bytes:
            return self._build_failed_result(
                reason_code="empty_image",
                message="No image bytes were provided.",
            )

        primary_result = self._run_detection_pass(
            image_bytes=image_bytes,
            filename=filename,
            mime_type=mime_type,
            prompt=_build_primary_prompt(filename=filename, mime_type=mime_type),
            pass_name="primary",
        )
        if primary_result.status == WearProviderResultStatus.FAILED:
            return primary_result

        if not _should_run_fallback(primary_result.detections):
            return primary_result

        fallback_result = self._run_detection_pass(
            image_bytes=image_bytes,
            filename=filename,
            mime_type=mime_type,
            prompt=_build_fallback_prompt(filename=filename, mime_type=mime_type),
            pass_name="fallback",
        )
        if fallback_result.status == WearProviderResultStatus.FAILED:
            merged_payload = dict(primary_result.sanitized_payload)
            merged_payload["fallback_attempted"] = True
            merged_payload["fallback_status"] = "failed"
            merged_payload["fallback_reason_code"] = fallback_result.sanitized_payload.get(
                "reason_code"
            )
            merged_payload["fallback_message"] = fallback_result.sanitized_payload.get("message")
            return OutfitDetectionResult(
                provider_name=primary_result.provider_name,
                provider_model=primary_result.provider_model,
                provider_version=primary_result.provider_version,
                status=primary_result.status,
                sanitized_payload=merged_payload,
                detections=primary_result.detections,
            )

        selected_result = _choose_better_result(primary_result, fallback_result)

        merged_payload = dict(selected_result.sanitized_payload)
        merged_payload["fallback_attempted"] = True
        merged_payload["primary_detections_count"] = len(primary_result.detections)
        merged_payload["fallback_detections_count"] = len(fallback_result.detections)
        merged_payload["selected_pass"] = (
            "fallback" if selected_result is fallback_result else "primary"
        )

        merged_detections = selected_result.detections
        if _should_run_lower_body_recovery(merged_detections):
            lower_body_result = self._run_detection_pass(
                image_bytes=image_bytes,
                filename=filename,
                mime_type=mime_type,
                prompt=_build_lower_body_recovery_prompt(
                    filename=filename,
                    mime_type=mime_type,
                ),
                pass_name="lower_body_recovery",
            )
            merged_payload["lower_body_recovery_attempted"] = True
            if lower_body_result.status == WearProviderResultStatus.FAILED:
                merged_payload["lower_body_recovery_status"] = "failed"
                merged_payload["lower_body_recovery_reason_code"] = (
                    lower_body_result.sanitized_payload.get("reason_code")
                )
                merged_payload["lower_body_recovery_message"] = (
                    lower_body_result.sanitized_payload.get("message")
                )
            else:
                merged_payload["lower_body_recovery_status"] = "succeeded"
                merged_payload["lower_body_recovery_detections_count"] = len(
                    lower_body_result.detections
                )
                merged_detections = _merge_lower_body_recovery_detections(
                    base_detections=merged_detections,
                    recovery_detections=lower_body_result.detections,
                )
                merged_payload["detections_count_after_lower_body_recovery"] = len(
                    merged_detections
                )

        return OutfitDetectionResult(
            provider_name=selected_result.provider_name,
            provider_model=selected_result.provider_model,
            provider_version=selected_result.provider_version,
            status=selected_result.status,
            sanitized_payload=merged_payload,
            detections=merged_detections,
        )

    def _run_detection_pass(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
        prompt: str,
        pass_name: str,
    ) -> OutfitDetectionResult:
        url = resolve_gemini_endpoint(base_url=self.base_url, model=self.model)
        request_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": _build_generation_config(),
        }

        try:
            raw_response = self._post_json(url=url, payload=request_payload)
        except urllib.error.HTTPError as exc:
            error_body = _read_http_error_body(exc)
            extracted_error = _extract_http_error_payload(error_body)
            return OutfitDetectionResult(
                provider_name=self.provider_name,
                provider_model=self.model or None,
                provider_version=None,
                status=_failure_status(),
                sanitized_payload={
                    "reason_code": (
                        "invalid_request" if exc.code == 400 else "http_error"
                    ),
                    "message": _format_http_error_message(
                        status_code=exc.code,
                        extracted_error=extracted_error,
                    ),
                    "http_status": exc.code,
                    "error_body": extracted_error,
                    "request_url": url,
                    "pass_name": pass_name,
                },
                detections=[],
            )
        except urllib.error.URLError as exc:
            return OutfitDetectionResult(
                provider_name=self.provider_name,
                provider_model=self.model or None,
                provider_version=None,
                status=_failure_status(),
                sanitized_payload={
                    "reason_code": "network_error",
                    "message": f"Gemini request failed: {exc.reason}",
                    "pass_name": pass_name,
                },
                detections=[],
            )
        except Exception as exc:
            return OutfitDetectionResult(
                provider_name=self.provider_name,
                provider_model=self.model or None,
                provider_version=None,
                status=_failure_status(),
                sanitized_payload={
                    "reason_code": "unexpected_error",
                    "message": str(exc),
                    "pass_name": pass_name,
                },
                detections=[],
            )

        model_text = _extract_response_text(raw_response)
        if not model_text:
            return OutfitDetectionResult(
                provider_name=self.provider_name,
                provider_model=self.model or None,
                provider_version=_extract_model_version(raw_response),
                status=_failure_status(),
                sanitized_payload={
                    "reason_code": "empty_model_output",
                    "message": "Gemini returned no text output.",
                    "raw_response": _sanitize_raw_response(raw_response),
                    "pass_name": pass_name,
                },
                detections=[],
            )

        try:
            parsed_output = json.loads(_strip_code_fences(model_text))
        except json.JSONDecodeError:
            return OutfitDetectionResult(
                provider_name=self.provider_name,
                provider_model=self.model or None,
                provider_version=_extract_model_version(raw_response),
                status=_failure_status(),
                sanitized_payload={
                    "reason_code": "invalid_json",
                    "message": "Gemini returned non-JSON output.",
                    "model_text": model_text,
                    "raw_response": _sanitize_raw_response(raw_response),
                    "pass_name": pass_name,
                },
                detections=[],
            )

        detections = _parse_detected_items(parsed_output)

        return OutfitDetectionResult(
            provider_name=self.provider_name,
            provider_model=self.model or None,
            provider_version=_extract_model_version(raw_response),
            status=_success_status(),
            sanitized_payload={
                "task_type": OUTFIT_DETECTION_TASK_TYPE,
                "filename": filename,
                "mime_type": mime_type,
                "parsed_output": parsed_output,
                "detections_count": len(detections),
                "metadata_richness_score": _score_detection_result(detections),
                "finish_reason": _extract_finish_reason(raw_response),
                "pass_name": pass_name,
            },
            detections=detections,
        )

    def _post_json(self, *, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)

    def _build_failed_result(self, *, reason_code: str, message: str) -> OutfitDetectionResult:
        return OutfitDetectionResult(
            provider_name=self.provider_name,
            provider_model=self.model or None,
            provider_version=None,
            status=_failure_status(),
            sanitized_payload={
                "reason_code": reason_code,
                "message": message,
            },
            detections=[],
        )


def resolve_gemini_endpoint(*, base_url: str, model: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith(":generateContent"):
        return normalized
    if "/models/" in normalized:
        return f"{normalized}:generateContent"
    return f"{normalized}/models/{model}:generateContent"


def build_wear_detection_provider() -> OutfitDetectionProvider:
    provider_name = settings.wear_detection_provider.strip().lower()

    if provider_name == "disabled":
        return NoopOutfitDetectionProvider(reason="Wear-event detection is disabled.")

    if provider_name in {"gemini", "google", "google-gemini"}:
        if not settings.gemini_api_key.strip():
            return NoopOutfitDetectionProvider(
                reason="Wear-event detection provider is Gemini, but GEMINI_API_KEY is missing."
            )

        return GeminiOutfitDetectionProvider(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
            model=settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
        )

    return NoopOutfitDetectionProvider(reason="Unsupported wear-event detection provider.")


def _build_primary_prompt(*, filename: str, mime_type: str) -> str:
    return f"""
You are extracting structured outfit detections from a single outfit photo for Tenue.

Your goal is to identify visible fashion items the person is actually wearing or clearly carrying.

Return JSON only.

Return exactly one JSON object with this shape:
{{
  "detections": [
    {{
      "role": "top",
      "confidence": 0.93,
      "sort_index": 0,
      "bbox": {{"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.4}},
      "metadata": {{
        "category": {{"value": "tops", "confidence": 0.93, "applicability_state": "value"}},
        "subcategory": {{"value": "t_shirt", "confidence": 0.91, "applicability_state": "value"}},
        "primary_color": {{"value": "black", "confidence": 0.88, "applicability_state": "value"}},
        "secondary_colors": {{"values": ["white"], "confidence": 0.62, "applicability_state": "value"}},
        "fit_tags": {{"values": ["relaxed"], "confidence": 0.58, "applicability_state": "value"}},
        "material": {{"applicability_state": "unknown"}}
      }}
    }}
  ]
}}

Critical rules:
- Use the shared closet taxonomy exactly. Canonical values must use underscore form.
- Each detection must include `role`, item-level `confidence`, `bbox`, `sort_index`, and `metadata`.
- `metadata` uses the same per-field structure as closet extraction:
  - scalar fields: `{{"value": ..., "confidence": ..., "applicability_state": ..., "notes": ...}}`
  - list fields: `{{"values": [...], "confidence": ..., "applicability_state": ..., "notes": ...}}`
- For fields that are not visually inferable, set `applicability_state` to `"unknown"` and omit `value` / `values` instead of guessing.
- When a structural cue is visible, do not leave it unknown. Capture visible neckline, sleeve shape, strap type, leg shape, rise, silhouette, closures, pockets, and trim or embellishment cues such as lace.
- For tops, dresses, and outerwear, prioritize visible neckline and sleeve attributes. For bottoms, prioritize visible leg shape, rise, and silhouette.
- Do not guess non-visual fields. Brand, title, occasion, season, statement level, and versatility should usually be unknown unless they are visually obvious.
- Detect separate visible layers separately. If both a base top and outerwear are visible, return both.
- Do not invent hidden items. Do not return duplicate detections.
- Accessories do not replace garments. If clothing is visible, return the clothing too.
- Use `sort_index` to order detections from top-to-bottom / primary visible garment order.

Canonical category values:
{_format_allowed_categories()}

Canonical subcategory values:
{_format_allowed_subcategories()}

Canonical color values:
{_format_allowed_colors()}

Canonical material values:
{_format_allowed_materials()}

Canonical pattern values:
{_format_allowed_patterns()}

Canonical fit tag values:
{_format_allowed_fit_tags()}

Canonical silhouette values:
{_format_allowed_silhouettes()}

Canonical attribute values:
{_format_allowed_attributes()}

Canonical formality values:
{_format_allowed_values("formality")}

Canonical warmth values:
{_format_allowed_values("warmth")}

Canonical coverage values:
{_format_allowed_values("coverage")}

Canonical statement level values:
{_format_allowed_values("statement_level")}

Canonical versatility values:
{_format_allowed_values("versatility")}

Role rules:
- role must be one of: {", ".join(_ALLOWED_ROLES)}
- dresses usually use role="dress" and category="dresses"
- jumpsuits, rompers, catsuits, and overalls usually use role="full_body" and category="one_piece"
- outer layers use role="outerwear" and category="outerwear"
- tops use role="top" and category="tops"
- bottoms use role="bottom" and category="bottoms"
- shoes use role="footwear" and category="shoes"
- bags use role="bag" and category="bags"
- jewelry uses role="jewelry" and category="jewelry"
- hats, scarves, eyewear, belts, socks, tights, and similar pieces use accessory-style roles/categories

Input file:
- filename: {filename}
- mime_type: {mime_type}
""".strip()


def _build_fallback_prompt(*, filename: str, mime_type: str) -> str:
    return f"""
You are performing a second-pass recovery for outfit detection on a single outfit photo.

The first pass was sparse or incomplete. Recover missed wearable items while staying truthful to the image.

Return JSON only.

Return exactly one JSON object with this shape:
{{
  "detections": [
    {{
      "role": "top",
      "confidence": 0.93,
      "sort_index": 0,
      "bbox": {{"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.4}},
      "metadata": {{
        "category": {{"value": "tops", "applicability_state": "value"}},
        "subcategory": {{"value": "t_shirt", "applicability_state": "value"}}
      }}
    }}
  ]
}}

Recovery rules:
- Focus on core garments first.
- If an upper-body garment is visible, return it.
- If an outer layer is visible over a base top, return both.
- If a lower-body garment is visible, return it unless the look is clearly a dress or one-piece.
- Only after core garments, include clearly visible bags/accessories/jewelry.
- Never return an empty detections array unless no visible wearable item is present.
- When uncertain between nearby labels, choose the nearest canonical taxonomy value instead of omitting the item.
- Encode visible structural cues in `subcategory`, `fit_tags`, `silhouette`, and `attributes`.
- If the neckline, sleeve shape, leg shape, pockets, or trim details are visible, encode them instead of leaving those fields unknown.
- Keep non-visual metadata unknown rather than guessed.

Canonical category values:
{_format_allowed_categories()}

Canonical subcategory values:
{_format_allowed_subcategories()}

Canonical color values:
{_format_allowed_colors()}

Canonical material values:
{_format_allowed_materials()}

Canonical pattern values:
{_format_allowed_patterns()}

Canonical fit tag values:
{_format_allowed_fit_tags()}

Canonical silhouette values:
{_format_allowed_silhouettes()}

Canonical attribute values:
{_format_allowed_attributes()}

Input file:
- filename: {filename}
- mime_type: {mime_type}
""".strip()


def _build_lower_body_recovery_prompt(*, filename: str, mime_type: str) -> str:
    return f"""
You are performing a targeted lower-body recovery pass for a single outfit photo.

The earlier pass likely found an upper-body garment but missed the lower-body garment.

Return JSON only.

Return exactly one JSON object with this shape:
{{
  "detections": [
    {{
      "role": "bottom",
      "confidence": 0.9,
      "sort_index": 1,
      "bbox": {{"x": 0.15, "y": 0.42, "width": 0.55, "height": 0.42}},
      "metadata": {{
        "category": {{"value": "bottoms", "applicability_state": "value"}},
        "subcategory": {{"value": "jeans", "applicability_state": "value"}},
        "primary_color": {{"value": "beige", "applicability_state": "value"}}
      }}
    }}
  ]
}}

Rules:
- Focus only on the lower-body garment the person is wearing.
- If pants, jeans, shorts, or a skirt are visible, return that garment.
- Do not return tops, bags, jewelry, hats, scarves, or phones.
- Do not return accessories or handheld objects.
- If no lower-body garment is clearly visible, return `{{"detections":[]}}`.

Canonical subcategory values:
{_format_allowed_subcategories()}

Canonical color values:
{_format_allowed_colors()}

Input file:
- filename: {filename}
- mime_type: {mime_type}
""".strip()


def _build_generation_config() -> dict[str, Any]:
    return {
        "responseMimeType": "application/json",
        "temperature": 0.05,
        "topP": 0.9,
        "maxOutputTokens": 3072,
    }


def _parse_detected_items(payload: Any) -> list[DetectedOutfitItem]:
    if not isinstance(payload, dict):
        return []

    raw_items = payload.get("detections", [])
    if not isinstance(raw_items, list):
        return []

    parsed_items: list[DetectedOutfitItem] = []

    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue

        raw_metadata = _metadata_payload_from_detection_item(item)
        normalized_metadata, field_confidences, field_notes = normalize_detected_metadata_fields(
            dict(raw_metadata)
        )
        category = _as_string(normalized_metadata.get("category"))
        subcategory = _as_string(normalized_metadata.get("subcategory"))
        role = _normalize_role(
            item.get("role"),
            category=category,
            subcategory=subcategory,
        )

        if subcategory is not None and category is None:
            category = derive_category_for_subcategory(subcategory)
            normalized_metadata["category"] = category

        if category is not None and subcategory is not None:
            if not is_valid_category_subcategory_pair(category=category, subcategory=subcategory):
                subcategory = None
                normalized_metadata["subcategory"] = None

        if category is None:
            category = _infer_category_from_role(role)
            normalized_metadata["category"] = category

        if role is None:
            role = _infer_role_from_category_subcategory(
                category=category,
                subcategory=subcategory,
            )

        confidence = _normalize_confidence(item.get("confidence"))
        bbox = _normalize_bbox(item.get("bbox"))
        sort_index = _normalize_sort_index(item.get("sort_index"), default=index)

        if (
            role is None
            and not _metadata_contains_values(normalized_metadata)
        ):
            continue

        parsed_items.append(
            DetectedOutfitItem(
                role=role,
                category=category,
                subcategory=subcategory,
                colors=_legacy_colors_from_metadata(normalized_metadata),
                material=_as_string(normalized_metadata.get("material")),
                pattern=_as_string(normalized_metadata.get("pattern")),
                fit_tags=_as_string_list(normalized_metadata.get("fit_tags")),
                silhouette=_as_string(normalized_metadata.get("silhouette")),
                attributes=_as_string_list(normalized_metadata.get("attributes")),
                confidence=confidence,
                bbox=bbox,
                metadata=_serialize_metadata_payload(
                    raw_metadata=raw_metadata,
                    normalized_metadata=normalized_metadata,
                    field_confidences=field_confidences,
                    field_notes=field_notes,
                ),
                sort_index=sort_index,
            )
        )

    return _dedupe_detections(parsed_items)


def _metadata_payload_from_detection_item(item: dict[str, Any]) -> dict[str, Any]:
    raw_metadata = item.get("metadata")
    if isinstance(raw_metadata, dict):
        return raw_metadata

    metadata: dict[str, Any] = {}
    for field_name in (
        "category",
        "subcategory",
        "colors",
        "material",
        "pattern",
        "fit_tags",
        "silhouette",
        "attributes",
    ):
        raw_value = item.get(field_name)
        payload = _legacy_metadata_field_payload(field_name=field_name, raw_value=raw_value)
        if payload is not None:
            metadata[field_name] = payload
    return metadata


def _legacy_metadata_field_payload(*, field_name: str, raw_value: Any) -> dict[str, Any] | None:
    if field_name in {"colors", "fit_tags", "attributes"}:
        values = _as_string_list(raw_value)
        if not values:
            return None
        return {
            "values": values,
            "confidence": None,
            "applicability_state": ApplicabilityState.VALUE.value,
            "notes": None,
        }

    value = _as_string(raw_value)
    if value is None:
        return None
    return {
        "value": value,
        "confidence": None,
        "applicability_state": ApplicabilityState.VALUE.value,
        "notes": None,
    }


def _serialize_metadata_payload(
    *,
    raw_metadata: dict[str, Any],
    normalized_metadata: dict[str, Any],
    field_confidences: dict[str, float | None],
    field_notes: dict[str, str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field_name in SUPPORTED_FIELD_ORDER:
        raw_field = raw_metadata.get(field_name)
        applicability_state = _extract_raw_applicability_state(raw_field)
        value = normalized_metadata.get(field_name)
        if applicability_state is None:
            applicability_state = (
                ApplicabilityState.VALUE.value if _metadata_value_has_value(value) else ApplicabilityState.UNKNOWN.value
            )

        if field_name in LIST_FIELD_NAMES:
            payload[field_name] = {
                "values": _as_string_list(value) or None,
                "confidence": field_confidences.get(field_name),
                "applicability_state": applicability_state,
                "notes": field_notes.get(field_name),
            }
            continue

        payload[field_name] = {
            "value": _as_string(value),
            "confidence": field_confidences.get(field_name),
            "applicability_state": applicability_state,
            "notes": field_notes.get(field_name),
        }
    return payload


def _extract_raw_applicability_state(raw_field: Any) -> str | None:
    if not isinstance(raw_field, dict):
        return None
    raw_state = raw_field.get("applicability_state")
    if isinstance(raw_state, ApplicabilityState):
        return raw_state.value
    if not isinstance(raw_state, str):
        return None
    normalized = raw_state.strip().lower()
    if normalized in {
        ApplicabilityState.VALUE.value,
        ApplicabilityState.UNKNOWN.value,
        ApplicabilityState.NOT_APPLICABLE.value,
    }:
        return normalized
    return None


def _metadata_contains_values(metadata: dict[str, Any]) -> bool:
    return any(_metadata_value_has_value(value) for value in metadata.values())


def _metadata_value_has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(_as_string_list(value))
    return True


def _field_payload_has_value(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if "values" in payload:
        return bool(_as_string_list(payload.get("values")))
    return _as_string(payload.get("value")) is not None


def _legacy_colors_from_metadata(metadata: dict[str, Any]) -> list[str]:
    colors: list[str] = []
    primary_color = _as_string(metadata.get("primary_color"))
    if primary_color is not None:
        colors.append(primary_color)
    colors.extend(_as_string_list(metadata.get("secondary_colors")))
    return colors


def _dedupe_detections(detections: list[DetectedOutfitItem]) -> list[DetectedOutfitItem]:
    deduped: list[DetectedOutfitItem] = []
    seen: set[tuple[Any, ...]] = set()

    for detection in detections:
        key = (
            detection.role,
            detection.category,
            detection.subcategory,
            tuple(detection.colors),
            detection.material,
            detection.pattern,
            tuple(detection.fit_tags),
            detection.silhouette,
            tuple(detection.attributes),
            _rounded_bbox_key(detection.bbox),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(detection)

    return deduped


def _should_run_fallback(detections: list[DetectedOutfitItem]) -> bool:
    if not detections:
        return True

    roles = {item.role for item in detections if item.role}
    if not roles:
        return True

    core_roles = roles & _CORE_GARMENT_ROLES
    if not core_roles:
        return True

    has_upper = bool(roles & _UPPER_BODY_ROLES)
    has_lower = bool(roles & _LOWER_BODY_ROLES)
    has_full_body = bool(roles & {"dress", "full_body"})

    if has_full_body:
        return False

    if has_upper and has_lower and _score_detection_result(detections) >= 12:
        return False

    return True


def _should_run_lower_body_recovery(detections: list[DetectedOutfitItem]) -> bool:
    roles = {item.role for item in detections if item.role}
    has_upper = bool(roles & _UPPER_BODY_ROLES)
    has_lower = bool(roles & _LOWER_BODY_ROLES)
    has_full_body = bool(roles & {"dress", "full_body"})
    return has_upper and not has_lower and not has_full_body


def _merge_lower_body_recovery_detections(
    *,
    base_detections: list[DetectedOutfitItem],
    recovery_detections: list[DetectedOutfitItem],
) -> list[DetectedOutfitItem]:
    if any(item.role in _LOWER_BODY_ROLES for item in base_detections):
        return base_detections

    recovery_candidates = [
        item for item in recovery_detections if item.role in {"bottom"}
    ]
    if not recovery_candidates:
        return base_detections

    selected_recovery = sorted(
        recovery_candidates,
        key=lambda item: (
            -(item.confidence or 0.0),
            item.sort_index if item.sort_index is not None else 999,
        ),
    )[0]
    merged = _dedupe_detections(base_detections + [selected_recovery])
    ordered = sorted(
        merged,
        key=lambda item: item.sort_index if item.sort_index is not None else 999,
    )
    return [
        replace(item, sort_index=index)
        for index, item in enumerate(ordered)
    ]


def _choose_better_result(
    primary: OutfitDetectionResult,
    fallback: OutfitDetectionResult,
) -> OutfitDetectionResult:
    primary_score = _score_detection_result(primary.detections)
    fallback_score = _score_detection_result(fallback.detections)
    return fallback if fallback_score > primary_score else primary


def _score_detection_result(detections: list[DetectedOutfitItem]) -> int:
    roles = {item.role for item in detections if item.role}

    score = len(detections) * 2
    if roles & _UPPER_BODY_ROLES:
        score += 4
    if roles & _LOWER_BODY_ROLES:
        score += 4
    if roles & {"dress", "full_body"}:
        score += 6
    if roles & {"outerwear"}:
        score += 2
    if roles & _CORE_GARMENT_ROLES:
        score += 3

    for item in detections:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        if item.material:
            score += 1
        if item.pattern:
            score += 1
        if item.fit_tags:
            score += 1
        if item.silhouette:
            score += 1
        if item.attributes:
            score += min(2, len(item.attributes))
        if _field_payload_has_value(metadata.get("primary_color")):
            score += 1
        if _field_payload_has_value(metadata.get("secondary_colors")):
            score += 1
        if _field_payload_has_value(metadata.get("formality")):
            score += 1

    return score


def _normalize_role(
    value: Any,
    *,
    category: Any,
    subcategory: Any,
) -> str | None:
    text = _normalize_optional_string(value)
    if text:
        lowered = text.lower()
        lowered = _ROLE_SYNONYMS.get(lowered, lowered)
        if lowered in _ALLOWED_ROLES:
            return lowered

    inferred = _infer_role_from_category_subcategory(
        category=_normalize_scalar_field("category", category),
        subcategory=_normalize_scalar_field("subcategory", subcategory),
    )
    return inferred


def _infer_role_from_category_subcategory(
    *,
    category: str | None,
    subcategory: str | None,
) -> str | None:
    text = " ".join(part for part in [category, subcategory] if part).strip().lower()

    if category == "outerwear":
        return "outerwear"
    if category == "tops":
        return "top"
    if category == "bottoms":
        return "bottom"
    if category == "shoes":
        return "footwear"
    if category == "bags":
        return "bag"
    if category == "jewelry":
        return "jewelry"
    if category == "dresses":
        return "dress"
    if category == "one_piece":
        return "full_body"
    if category == "accessories":
        if "hat" in text:
            return "hat"
        if "scarf" in text:
            return "scarf"
        if "sunglasses" in text:
            return "eyewear"
        return "accessory"

    if subcategory in {
        "cardigan",
        "blazer",
        "jacket",
        "coat",
        "trench_coat",
        "vest",
        "denim_jacket",
        "leather_jacket",
        "puffer_jacket",
        "bomber_jacket",
        "shacket",
        "rain_jacket",
    }:
        return "outerwear"
    if subcategory in {
        "t_shirt",
        "shirt",
        "blouse",
        "tank_top",
        "camisole",
        "polo",
        "sweater",
        "sweatshirt",
        "hoodie",
        "bodysuit",
        "knit_top",
        "tunic",
        "vest_top",
    }:
        return "top"
    if subcategory in {
        "jeans",
        "trousers",
        "shorts",
        "skirt",
        "leggings",
        "joggers",
        "cargo_pants",
    }:
        return "bottom"
    if subcategory in {
        "sneakers",
        "boots",
        "ankle_boots",
        "knee_high_boots",
        "heels",
        "pumps",
        "flats",
        "ballet_flats",
        "loafers",
        "sandals",
        "mules",
        "slippers",
        "clogs",
    }:
        return "footwear"
    if subcategory in {
        "tote",
        "shoulder_bag",
        "crossbody",
        "backpack",
        "clutch",
        "mini_bag",
        "top_handle_bag",
        "hobo_bag",
        "satchel",
        "evening_bag",
    }:
        return "bag"
    if subcategory in {"necklace", "earrings", "bracelet", "ring", "watch", "anklet", "brooch"}:
        return "jewelry"
    if subcategory in {
        "shirt_dress",
        "sweater_dress",
        "bodycon_dress",
        "wrap_dress",
        "strapless_dress",
        "evening_dress",
    }:
        return "dress"
    if subcategory in {"jumpsuit", "romper", "catsuit", "overalls"}:
        return "full_body"
    if subcategory == "hat":
        return "hat"
    if subcategory == "scarf":
        return "scarf"
    if subcategory == "sunglasses":
        return "eyewear"

    return None


def _infer_category_from_role(role: str | None) -> str | None:
    if role == "top":
        return "tops"
    if role == "bottom":
        return "bottoms"
    if role == "outerwear":
        return "outerwear"
    if role == "footwear":
        return "shoes"
    if role == "bag":
        return "bags"
    if role == "jewelry":
        return "jewelry"
    if role == "dress":
        return "dresses"
    if role == "full_body":
        return "one_piece"
    if role in {"hat", "scarf", "eyewear", "accessory"}:
        return "accessories"
    return None


def _normalize_scalar_field(field_name: str, raw_value: Any) -> str | None:
    normalized = normalize_field_value(
        field_name=field_name,
        raw_value=raw_value,
        applicability_state=ApplicabilityState.VALUE,
        confidence=None,
    )
    value = normalized.canonical_value
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _normalize_list_field(field_name: str, raw_value: Any) -> list[str]:
    normalized = normalize_field_value(
        field_name=field_name,
        raw_value=raw_value,
        applicability_state=ApplicabilityState.VALUE,
        confidence=None,
    )
    value = normalized.canonical_value
    if not isinstance(value, list):
        return []

    deduped: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def _as_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        deduped: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                continue
            stripped = item.strip()
            if not stripped:
                continue
            lowered = stripped.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(stripped)
        return deduped
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return []


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def _normalize_confidence(value: Any) -> float | None:
    if value is None:
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if numeric < 0:
        return 0.0
    if numeric > 1:
        return 1.0
    return numeric


def _normalize_sort_index(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value >= 0:
        return value
    return default


def _normalize_bbox(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None

    required_keys = ("x", "y", "width", "height")
    normalized: dict[str, float] = {}

    for key in required_keys:
        raw = value.get(key)
        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            return None

        if numeric < 0:
            numeric = 0.0
        if numeric > 1:
            numeric = 1.0

        normalized[key] = numeric

    return normalized


def _rounded_bbox_key(bbox: dict[str, float] | None) -> tuple[float, float, float, float] | None:
    if not isinstance(bbox, dict):
        return None
    try:
        return (
            round(float(bbox.get("x", 0.0)), 3),
            round(float(bbox.get("y", 0.0)), 3),
            round(float(bbox.get("width", 0.0)), 3),
            round(float(bbox.get("height", 0.0)), 3),
        )
    except (TypeError, ValueError):
        return None


def _extract_response_text(raw_response: dict[str, Any]) -> str | None:
    candidates = raw_response.get("candidates", [])
    if not isinstance(candidates, list):
        return None

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        content = candidate.get("content", {})
        if not isinstance(content, dict):
            continue

        parts = content.get("parts", [])
        if not isinstance(parts, list):
            continue

        text_chunks: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                text_chunks.append(text)

        if text_chunks:
            return "".join(text_chunks).strip()

    return None


def _extract_finish_reason(raw_response: dict[str, Any]) -> str | None:
    candidates = raw_response.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        return None

    first = candidates[0]
    if not isinstance(first, dict):
        return None

    value = first.get("finishReason")
    return _normalize_optional_string(value)


def _extract_model_version(raw_response: dict[str, Any]) -> str | None:
    value = raw_response.get("modelVersion")
    return _normalize_optional_string(value)


def _sanitize_raw_response(raw_response: dict[str, Any]) -> dict[str, Any]:
    return {
        "modelVersion": raw_response.get("modelVersion"),
        "usageMetadata": raw_response.get("usageMetadata"),
        "promptFeedback": raw_response.get("promptFeedback"),
        "candidates_count": len(raw_response.get("candidates", []) or []),
    }


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8")
    except Exception:
        return ""
    return body[:4000]


def _extract_http_error_payload(error_body: str) -> dict[str, Any] | str | None:
    if not error_body.strip():
        return None

    try:
        payload = json.loads(error_body)
    except ValueError:
        return error_body[:500]

    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"items": payload}
    return str(payload)


def _extract_http_error_message(extracted_error: dict[str, Any] | str | None) -> str | None:
    if isinstance(extracted_error, str):
        message = extracted_error.strip()
        return message or None

    if not isinstance(extracted_error, dict):
        return None

    nested_error = extracted_error.get("error")
    if isinstance(nested_error, dict):
        nested_message = nested_error.get("message")
        if isinstance(nested_message, str) and nested_message.strip():
            return nested_message.strip()

    direct_message = extracted_error.get("message")
    if isinstance(direct_message, str) and direct_message.strip():
        return direct_message.strip()

    return None


def _format_http_error_message(
    *,
    status_code: int,
    extracted_error: dict[str, Any] | str | None,
) -> str:
    detail = _extract_http_error_message(extracted_error)
    if detail:
        return f"Gemini request failed with HTTP {status_code}: {detail}"
    return f"Gemini request failed with HTTP {status_code}."


def _success_status() -> WearProviderResultStatus:
    enum_cls = WearProviderResultStatus

    for name in ("COMPLETED", "SUCCEEDED", "SUCCESS"):
        member = getattr(enum_cls, name, None)
        if member is not None:
            return member

    members = getattr(enum_cls, "__members__", {})
    for name in ("COMPLETED", "SUCCEEDED", "SUCCESS"):
        member = members.get(name)
        if member is not None:
            return member

    raise RuntimeError(
        "Could not find a success status on WearProviderResultStatus. "
        "Add one of: COMPLETED, SUCCEEDED, SUCCESS."
    )


def _failure_status() -> WearProviderResultStatus:
    return WearProviderResultStatus.FAILED


def _resolve_status_enum(*, preferred_names: tuple[str, ...]) -> WearProviderResultStatus:
    enum_cls = WearProviderResultStatus

    for name in preferred_names:
        member = getattr(enum_cls, name, None)
        if member is not None:
            return member

    if issubclass(enum_cls, Enum):
        members = getattr(enum_cls, "__members__", {})
        for name in preferred_names:
            member = members.get(name)
            if member is not None:
                return member

    raise RuntimeError(
        f"Could not resolve a status member on {enum_cls.__name__} from {preferred_names!r}."
    )


def _format_allowed_categories() -> str:
    return ", ".join(_ALLOWED_CATEGORIES)


def _format_allowed_subcategories() -> str:
    return ", ".join(_ALLOWED_SUBCATEGORIES)


def _format_allowed_colors() -> str:
    return ", ".join(_ALLOWED_COLORS)


def _format_allowed_materials() -> str:
    return ", ".join(_ALLOWED_MATERIALS)


def _format_allowed_patterns() -> str:
    return ", ".join(_ALLOWED_PATTERNS)


def _format_allowed_fit_tags() -> str:
    return ", ".join(_ALLOWED_FIT_TAGS)


def _format_allowed_silhouettes() -> str:
    return ", ".join(_ALLOWED_SILHOUETTES)


def _format_allowed_attributes() -> str:
    return ", ".join(_ALLOWED_ATTRIBUTES)


def _format_allowed_values(field_name: str) -> str:
    values = CONTROLLED_SCALAR_VALUES.get(field_name, frozenset())
    return ", ".join(sorted(values))
