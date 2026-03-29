from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.domains.closet.models import ApplicabilityState
from app.domains.closet.taxonomy import (
    CATEGORY_SUBCATEGORIES,
    COLORS,
    MATERIALS,
    OCCASION_TAGS,
    PATTERNS,
    SEASON_TAGS,
    STYLE_TAGS,
)


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def lookup_key(value: str) -> str:
    normalized = collapse_whitespace(value).lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", normalized)


def _build_lookup(values: list[str] | tuple[str, ...]) -> dict[str, str]:
    return {lookup_key(value): value for value in values}


CATEGORY_VALUES = tuple(CATEGORY_SUBCATEGORIES.keys())
SUBCATEGORY_TO_CATEGORY = {
    subcategory: category
    for category, subcategories in CATEGORY_SUBCATEGORIES.items()
    for subcategory in subcategories
}

CATEGORY_LOOKUP = _build_lookup(CATEGORY_VALUES)
SUBCATEGORY_LOOKUP = _build_lookup(tuple(SUBCATEGORY_TO_CATEGORY.keys()))
COLOR_LOOKUP = _build_lookup(tuple(COLORS))
MATERIAL_LOOKUP = _build_lookup(tuple(MATERIALS))
PATTERN_LOOKUP = _build_lookup(tuple(PATTERNS))
STYLE_TAG_LOOKUP = _build_lookup(tuple(STYLE_TAGS))
OCCASION_TAG_LOOKUP = _build_lookup(tuple(OCCASION_TAGS))
SEASON_TAG_LOOKUP = _build_lookup(tuple(SEASON_TAGS))

CATEGORY_ALIASES = {
    lookup_key("top"): "tops",
    lookup_key("bottom"): "bottoms",
    lookup_key("shoe"): "shoes",
    lookup_key("bag"): "bags",
    lookup_key("accessory"): "accessories",
}

SUBCATEGORY_ALIASES = {
    lookup_key("tee shirt"): "t-shirt",
    lookup_key("tee-shirt"): "t-shirt",
    lookup_key("tshirt"): "t-shirt",
    lookup_key("tanktop"): "tank top",
}

COLOR_ALIASES = {
    lookup_key("grey"): "gray",
    lookup_key("navy blue"): "navy",
    lookup_key("charcoal"): "gray",
}

MATERIAL_ALIASES = {
    lookup_key("fake leather"): "faux leather",
    lookup_key("vegan leather"): "faux leather",
}

PATTERN_ALIASES = {
    lookup_key("polka-dot"): "polka dot",
}

STYLE_TAG_ALIASES = {
    lookup_key("everyday"): "casual",
    lookup_key("athleisure"): "sporty",
}

OCCASION_TAG_ALIASES = {
    lookup_key("office"): "business",
    lookup_key("night out"): "evening",
}

SEASON_TAG_ALIASES: dict[str, str] = {}


@dataclass(frozen=True)
class NormalizedFieldValue:
    field_name: str
    canonical_value: Any | None
    applicability_state: ApplicabilityState
    confidence: float | None
    notes: tuple[str, ...]


def normalize_field_value(
    *,
    field_name: str,
    raw_value: Any,
    applicability_state: ApplicabilityState,
    confidence: float | None,
) -> NormalizedFieldValue:
    if applicability_state != ApplicabilityState.VALUE:
        return NormalizedFieldValue(
            field_name=field_name,
            canonical_value=None,
            applicability_state=applicability_state,
            confidence=confidence,
            notes=(),
        )

    if field_name == "title":
        return _normalize_free_text(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label="title",
        )
    if field_name == "brand":
        return _normalize_free_text(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label="brand",
        )
    if field_name == "category":
        return _normalize_controlled_scalar(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label="category",
            lookup=CATEGORY_LOOKUP,
            aliases=CATEGORY_ALIASES,
        )
    if field_name == "subcategory":
        return _normalize_controlled_scalar(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label="subcategory",
            lookup=SUBCATEGORY_LOOKUP,
            aliases=SUBCATEGORY_ALIASES,
        )
    if field_name == "material":
        return _normalize_controlled_scalar(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label="material",
            lookup=MATERIAL_LOOKUP,
            aliases=MATERIAL_ALIASES,
        )
    if field_name == "pattern":
        return _normalize_controlled_scalar(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label="pattern",
            lookup=PATTERN_LOOKUP,
            aliases=PATTERN_ALIASES,
        )
    if field_name == "colors":
        return _normalize_controlled_list(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label="color",
            lookup=COLOR_LOOKUP,
            aliases=COLOR_ALIASES,
        )
    if field_name == "style_tags":
        return _normalize_controlled_list(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label="style tag",
            lookup=STYLE_TAG_LOOKUP,
            aliases=STYLE_TAG_ALIASES,
        )
    if field_name == "occasion_tags":
        return _normalize_controlled_list(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label="occasion tag",
            lookup=OCCASION_TAG_LOOKUP,
            aliases=OCCASION_TAG_ALIASES,
        )
    if field_name == "season_tags":
        return _normalize_controlled_list(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label="season tag",
            lookup=SEASON_TAG_LOOKUP,
            aliases=SEASON_TAG_ALIASES,
        )

    return NormalizedFieldValue(
        field_name=field_name,
        canonical_value=None,
        applicability_state=ApplicabilityState.UNKNOWN,
        confidence=None,
        notes=(f"Unsupported normalization field '{field_name}'.",),
    )


def derive_category_for_subcategory(subcategory: str) -> str | None:
    return SUBCATEGORY_TO_CATEGORY.get(subcategory)


def _normalize_free_text(
    *,
    field_name: str,
    raw_value: Any,
    confidence: float | None,
    label: str,
) -> NormalizedFieldValue:
    value = first_string(raw_value)
    if value is None:
        return NormalizedFieldValue(
            field_name=field_name,
            canonical_value=None,
            applicability_state=ApplicabilityState.VALUE,
            confidence=confidence,
            notes=(f"No usable {label} value was available.",),
        )
    return NormalizedFieldValue(
        field_name=field_name,
        canonical_value=value,
        applicability_state=ApplicabilityState.VALUE,
        confidence=confidence,
        notes=(),
    )


def _normalize_controlled_scalar(
    *,
    field_name: str,
    raw_value: Any,
    confidence: float | None,
    label: str,
    lookup: dict[str, str],
    aliases: dict[str, str],
) -> NormalizedFieldValue:
    value = first_string(raw_value)
    if value is None:
        return NormalizedFieldValue(
            field_name=field_name,
            canonical_value=None,
            applicability_state=ApplicabilityState.VALUE,
            confidence=confidence,
            notes=(f"No usable {label} value was available.",),
        )

    canonical = lookup.get(lookup_key(value)) or aliases.get(lookup_key(value))
    if canonical is None:
        return NormalizedFieldValue(
            field_name=field_name,
            canonical_value=None,
            applicability_state=ApplicabilityState.VALUE,
            confidence=confidence,
            notes=(f"Unmapped {label} value '{value}'.",),
        )

    return NormalizedFieldValue(
        field_name=field_name,
        canonical_value=canonical,
        applicability_state=ApplicabilityState.VALUE,
        confidence=confidence,
        notes=(),
    )


def _normalize_controlled_list(
    *,
    field_name: str,
    raw_value: Any,
    confidence: float | None,
    label: str,
    lookup: dict[str, str],
    aliases: dict[str, str],
) -> NormalizedFieldValue:
    values = string_list(raw_value)
    if not values:
        return NormalizedFieldValue(
            field_name=field_name,
            canonical_value=None,
            applicability_state=ApplicabilityState.VALUE,
            confidence=confidence,
            notes=(f"No usable {label} values were available.",),
        )

    mapped: list[str] = []
    seen: set[str] = set()
    unmapped: list[str] = []
    for value in values:
        canonical = lookup.get(lookup_key(value)) or aliases.get(lookup_key(value))
        if canonical is None:
            unmapped.append(value)
            continue
        if canonical.casefold() in seen:
            continue
        seen.add(canonical.casefold())
        mapped.append(canonical)

    notes: list[str] = []
    if unmapped:
        notes.append(f"Unmapped {label} values: {', '.join(sorted(unmapped, key=str.casefold))}.")
    if not mapped:
        return NormalizedFieldValue(
            field_name=field_name,
            canonical_value=None,
            applicability_state=ApplicabilityState.VALUE,
            confidence=confidence,
            notes=tuple(notes),
        )

    return NormalizedFieldValue(
        field_name=field_name,
        canonical_value=mapped,
        applicability_state=ApplicabilityState.VALUE,
        confidence=confidence,
        notes=tuple(notes),
    )


def first_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = collapse_whitespace(value)
        return stripped or None
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, str):
                continue
            stripped = collapse_whitespace(item)
            if stripped:
                return stripped
    return None


def string_list(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        stripped = collapse_whitespace(value)
        if stripped:
            values.append(stripped)
    elif isinstance(value, list):
        for item in value:
            if not isinstance(item, str):
                continue
            stripped = collapse_whitespace(item)
            if stripped:
                values.append(stripped)
    return values
