from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from app.core.config import settings
from app.domains.closet.models import ApplicabilityState
from app.domains.closet.normalization import derive_category_for_subcategory, normalize_field_value
from app.domains.closet.taxonomy import (
    ATTRIBUTES,
    CATEGORY_SUBCATEGORIES,
    COLORS,
    FIT_TAGS,
    MATERIALS,
    PATTERNS,
    SILHOUETTES,
    is_valid_category_subcategory_pair,
)
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
    role: str | None
    category: str | None
    subcategory: str | None
    colors: list[str]
    material: str | None
    pattern: str | None
    fit_tags: list[str]
    silhouette: str | None
    attributes: list[str]
    confidence: float | None
    bbox: dict[str, float] | None


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

        return OutfitDetectionResult(
            provider_name=selected_result.provider_name,
            provider_model=selected_result.provider_model,
            provider_version=selected_result.provider_version,
            status=selected_result.status,
            sanitized_payload=merged_payload,
            detections=selected_result.detections,
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
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _response_json_schema(),
                "temperature": 0.05,
                "topP": 0.9,
                "maxOutputTokens": 3072,
            },
        }

        url = f"{self.base_url}/models/{self.model}:generateContent"

        try:
            raw_response = self._post_json(url=url, payload=request_payload)
        except urllib.error.HTTPError as exc:
            error_body = _read_http_error_body(exc)
            return OutfitDetectionResult(
                provider_name=self.provider_name,
                provider_model=self.model or None,
                provider_version=None,
                status=_failure_status(),
                sanitized_payload={
                    "reason_code": "http_error",
                    "message": f"Gemini request failed with HTTP {exc.code}.",
                    "http_status": exc.code,
                    "error_body": error_body,
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
You are extracting structured outfit detections from a single outfit photo for a wardrobe app.

Your goal is to identify visible fashion items the person is actually wearing or clearly carrying.

Return JSON only and follow the provided schema exactly.

Important behavior:
- Prefer the wardrobe app's canonical taxonomy values.
- Detect distinct visible items separately.
- Layered outfits matter: if both a base top and an outer layer are visible, return both.
- Do not invent hidden items.
- Do not return duplicate detections for the same item.
- Use null only when a field is truly unclear.
- If an item is clearly visible, do not omit it just because the exact subtype is uncertain.
- If the torso is visible, there is usually at least one upper-body garment.
- If the hips/legs are visible, there is usually at least one lower-body garment, unless the person is wearing a dress or a one-piece.
- Accessories should not replace core garments. If a bag or jewelry is visible along with clothing, include the clothing too.

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

Role rules:
- role must be one of: {", ".join(_ALLOWED_ROLES)}
- dresses should usually use role="dress" and category="dresses"
- jumpsuits and rompers should usually use role="full_body" and category="one_piece"
- cardigans, blazers, jackets, coats, trench coats, and vests should use role="outerwear" and category="outerwear"
- t-shirts, shirts, blouses, tank tops, camisoles, polos, sweaters, sweatshirts, hoodies, and bodysuits should usually use role="top" and category="tops"
- jeans, trousers, shorts, skirts, leggings, and joggers should usually use role="bottom" and category="bottoms"
- sneakers, boots, heels, flats, loafers, sandals, and mules should usually use role="footwear" and category="shoes"
- bags should usually use role="bag" and category="bags"
- necklaces, earrings, bracelets, rings, and watches should usually use role="jewelry" and category="jewelry"
- hats, scarves, sunglasses, belts, and wallets should usually use accessory-style roles/categories

Field rules:
- category should be a canonical category value when possible
- subcategory should be a canonical subcategory value when possible
- colors should be a short list of dominant visible colors from the canonical color values
- material should only be set when visually plausible
- pattern should only be set when visually plausible
- fit_tags should include visible shape cues like wide_leg, straight_leg, fitted, cropped, oversized, relaxed, slim, tapered, bodycon
- silhouette should only be set when visually plausible
- attributes should include visible garment cues like v_neck, crew_neck, sleeveless, short_sleeve, long_sleeve, collared, halter, racerback, wrap, off_shoulder
- confidence must be a number between 0 and 1
- bbox must be normalized to the image size with keys x, y, width, height and values between 0 and 1

Examples:
- A sleeveless fitted ribbed top can map to category="tops", subcategory="tank top", fit_tags=["fitted"], attributes=["sleeveless"]
- A cardigan layered over a top should be returned separately as role="outerwear", category="outerwear", subcategory="cardigan"
- Wide-leg denim pants can map to category="bottoms", subcategory="jeans" or "trousers", fit_tags=["wide_leg"], silhouette="wide_leg"

Input file:
- filename: {filename}
- mime_type: {mime_type}
""".strip()


def _build_fallback_prompt(*, filename: str, mime_type: str) -> str:
    return f"""
You are performing a second-pass recovery for outfit detection on a single outfit photo.

The first pass was sparse or incomplete. Your job is to recover missed clothing items while still staying truthful to the image.

Return JSON only and follow the provided schema exactly.

Recovery rules:
- Focus on core garments first.
- If a visible upper-body garment exists, return it.
- If a visible outer layer exists, return it separately from the base top.
- If a visible lower-body garment exists, return it.
- Use role="dress" for dresses and role="full_body" for jumpsuits/rompers.
- Only after core garments, include clearly visible bags/accessories.
- Never return an empty detections array unless no visible wearable item is actually present in the image.
- When uncertain between close fashion labels, choose the nearest canonical taxonomy value rather than omitting the item.
- Prefer visible structural metadata over generic labels.

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

Practical guidance:
- A blouse-like white top with visible v-neck or decorative trim should not be collapsed into a generic t-shirt if blouse-like structure is visible.
- A sleeveless fitted knit top usually maps to category="tops" with subcategory="tank top" or "sweater", depending on appearance.
- A cardigan should be returned separately as role="outerwear", category="outerwear", subcategory="cardigan" when visible over another top.
- Wide-leg denim bottoms should still be mapped to role="bottom", category="bottoms", and the closest supported subcategory such as "jeans" or "trousers", with fit_tags=["wide_leg"] when visible.
- Mirror selfies and phone occlusion do not justify omitting clearly visible garments.
- If neckline, sleeve shape, or silhouette are visible, encode them in attributes / fit_tags / silhouette.

Field rules:
- role must be one of: {", ".join(_ALLOWED_ROLES)}
- category should be a canonical category value when possible
- subcategory should be a canonical subcategory value when possible
- colors should use canonical color values
- material and pattern should only be set when visually plausible
- fit_tags, silhouette, and attributes should capture visible garment identity cues
- confidence must be a number between 0 and 1
- bbox must be normalized to the image size with keys x, y, width, height and values between 0 and 1

Input file:
- filename: {filename}
- mime_type: {mime_type}
""".strip()


def _response_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["detections"],
        "properties": {
            "detections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "role",
                        "category",
                        "subcategory",
                        "colors",
                        "material",
                        "pattern",
                        "fit_tags",
                        "silhouette",
                        "attributes",
                        "confidence",
                        "bbox",
                    ],
                    "properties": {
                        "role": {
                            "anyOf": [
                                {"type": "string", "enum": list(_ALLOWED_ROLES)},
                                {"type": "null"},
                            ]
                        },
                        "category": {
                            "anyOf": [
                                {"type": "string", "enum": list(_ALLOWED_CATEGORIES)},
                                {"type": "null"},
                            ]
                        },
                        "subcategory": {
                            "anyOf": [
                                {"type": "string", "enum": list(_ALLOWED_SUBCATEGORIES)},
                                {"type": "null"},
                            ]
                        },
                        "colors": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": list(_ALLOWED_COLORS),
                            },
                            "maxItems": 8,
                        },
                        "material": {
                            "anyOf": [
                                {"type": "string", "enum": list(_ALLOWED_MATERIALS)},
                                {"type": "null"},
                            ]
                        },
                        "pattern": {
                            "anyOf": [
                                {"type": "string", "enum": list(_ALLOWED_PATTERNS)},
                                {"type": "null"},
                            ]
                        },
                        "fit_tags": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": list(_ALLOWED_FIT_TAGS),
                            },
                            "maxItems": 8,
                        },
                        "silhouette": {
                            "anyOf": [
                                {"type": "string", "enum": list(_ALLOWED_SILHOUETTES)},
                                {"type": "null"},
                            ]
                        },
                        "attributes": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": list(_ALLOWED_ATTRIBUTES),
                            },
                            "maxItems": 12,
                        },
                        "confidence": {
                            "anyOf": [
                                {"type": "number", "minimum": 0, "maximum": 1},
                                {"type": "null"},
                            ]
                        },
                        "bbox": {
                            "anyOf": [
                                {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["x", "y", "width", "height"],
                                    "properties": {
                                        "x": {"type": "number", "minimum": 0, "maximum": 1},
                                        "y": {"type": "number", "minimum": 0, "maximum": 1},
                                        "width": {
                                            "type": "number",
                                            "minimum": 0,
                                            "maximum": 1,
                                        },
                                        "height": {
                                            "type": "number",
                                            "minimum": 0,
                                            "maximum": 1,
                                        },
                                    },
                                },
                                {"type": "null"},
                            ]
                        },
                    },
                },
            }
        },
    }


def _parse_detected_items(payload: Any) -> list[DetectedOutfitItem]:
    if not isinstance(payload, dict):
        return []

    raw_items = payload.get("detections", [])
    if not isinstance(raw_items, list):
        return []

    parsed_items: list[DetectedOutfitItem] = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        role = _normalize_role(
            item.get("role"),
            category=item.get("category"),
            subcategory=item.get("subcategory"),
        )
        category = _normalize_scalar_field("category", item.get("category"))
        subcategory = _normalize_scalar_field("subcategory", item.get("subcategory"))

        if subcategory is not None and category is None:
            category = derive_category_for_subcategory(subcategory)

        if category is not None and subcategory is not None:
            if not is_valid_category_subcategory_pair(category=category, subcategory=subcategory):
                subcategory = None

        if category is None:
            category = _infer_category_from_role(role)

        if role is None:
            role = _infer_role_from_category_subcategory(
                category=category,
                subcategory=subcategory,
            )

        colors = _normalize_list_field("colors", item.get("colors"))
        material = _normalize_scalar_field("material", item.get("material"))
        pattern = _normalize_scalar_field("pattern", item.get("pattern"))
        fit_tags = _normalize_list_field("fit_tags", item.get("fit_tags"))
        silhouette = _normalize_scalar_field("silhouette", item.get("silhouette"))
        attributes = _normalize_list_field("attributes", item.get("attributes"))
        confidence = _normalize_confidence(item.get("confidence"))
        bbox = _normalize_bbox(item.get("bbox"))

        if (
            role is None
            and category is None
            and subcategory is None
            and not colors
            and material is None
            and pattern is None
            and not fit_tags
            and silhouette is None
            and not attributes
        ):
            continue

        parsed_items.append(
            DetectedOutfitItem(
                role=role,
                category=category,
                subcategory=subcategory,
                colors=colors,
                material=material,
                pattern=pattern,
                fit_tags=fit_tags,
                silhouette=silhouette,
                attributes=attributes,
                confidence=confidence,
                bbox=bbox,
            )
        )

    return _dedupe_detections(parsed_items)


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

    if subcategory in {"cardigan", "blazer", "jacket", "coat", "trench coat", "vest"}:
        return "outerwear"
    if subcategory in {
        "t-shirt",
        "shirt",
        "blouse",
        "tank top",
        "camisole",
        "polo",
        "sweater",
        "sweatshirt",
        "hoodie",
        "bodysuit",
    }:
        return "top"
    if subcategory in {"jeans", "trousers", "shorts", "skirt", "leggings", "joggers"}:
        return "bottom"
    if subcategory in {"sneakers", "boots", "heels", "flats", "loafers", "sandals", "mules"}:
        return "footwear"
    if subcategory in {"tote", "shoulder bag", "crossbody", "backpack", "clutch"}:
        return "bag"
    if subcategory in {"necklace", "earrings", "bracelet", "ring", "watch"}:
        return "jewelry"
    if subcategory in {"mini dress", "midi dress", "maxi dress", "slip dress", "shirt dress", "sweater dress"}:
        return "dress"
    if subcategory in {"jumpsuit", "romper"}:
        return "full_body"
    if subcategory in {"hat"}:
        return "hat"
    if subcategory in {"scarf"}:
        return "scarf"
    if subcategory in {"sunglasses"}:
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