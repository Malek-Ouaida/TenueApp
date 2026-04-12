from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.domains.closet.models import ApplicabilityState
from app.domains.closet.taxonomy import (
    ATTRIBUTES,
    CATEGORY_SUBCATEGORIES,
    COLORS,
    CONTROLLED_LIST_VALUES,
    CONTROLLED_SCALAR_VALUES,
    COVERAGE_VALUES,
    FIT_TAGS,
    FORMALITY_VALUES,
    MATERIALS,
    OCCASION_TAGS,
    PATTERNS,
    SEASON_TAGS,
    SILHOUETTES,
    STATEMENT_LEVEL_VALUES,
    STYLE_TAGS,
    VERSATILITY_VALUES,
    WARMTH_VALUES,
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
FIT_TAG_LOOKUP = _build_lookup(tuple(FIT_TAGS))
OCCASION_TAG_LOOKUP = _build_lookup(tuple(OCCASION_TAGS))
SEASON_TAG_LOOKUP = _build_lookup(tuple(SEASON_TAGS))
SILHOUETTE_LOOKUP = _build_lookup(tuple(SILHOUETTES))
ATTRIBUTE_LOOKUP = _build_lookup(tuple(ATTRIBUTES))
FORMALITY_LOOKUP = _build_lookup(tuple(FORMALITY_VALUES))
WARMTH_LOOKUP = _build_lookup(tuple(WARMTH_VALUES))
COVERAGE_LOOKUP = _build_lookup(tuple(COVERAGE_VALUES))
STATEMENT_LEVEL_LOOKUP = _build_lookup(tuple(STATEMENT_LEVEL_VALUES))
VERSATILITY_LOOKUP = _build_lookup(tuple(VERSATILITY_VALUES))

CATEGORY_ALIASES = {
    lookup_key("top"): "tops",
    lookup_key("bottom"): "bottoms",
    lookup_key("shoe"): "shoes",
    lookup_key("bag"): "bags",
    lookup_key("accessory"): "accessories",
    lookup_key("one piece"): "one_piece",
    lookup_key("one-piece"): "one_piece",
    lookup_key("jewellery"): "jewelry",
}

SUBCATEGORY_ALIASES = {
    lookup_key("tee shirt"): "t_shirt",
    lookup_key("tee-shirt"): "t_shirt",
    lookup_key("tshirt"): "t_shirt",
    lookup_key("tee"): "t_shirt",
    lookup_key("tanktop"): "tank_top",
    lookup_key("vest top"): "vest_top",
    lookup_key("shirt dress"): "shirt_dress",
    lookup_key("sweater dress"): "sweater_dress",
    lookup_key("wrap dress"): "wrap_dress",
    lookup_key("bodycon dress"): "bodycon_dress",
    lookup_key("strapless dress"): "strapless_dress",
    lookup_key("evening dress"): "evening_dress",
    lookup_key("trench"): "trench_coat",
    lookup_key("denim jacket"): "denim_jacket",
    lookup_key("leather jacket"): "leather_jacket",
    lookup_key("puffer jacket"): "puffer_jacket",
    lookup_key("bomber jacket"): "bomber_jacket",
    lookup_key("rain jacket"): "rain_jacket",
    lookup_key("cargo pants"): "cargo_pants",
    lookup_key("ankle boots"): "ankle_boots",
    lookup_key("knee high boots"): "knee_high_boots",
    lookup_key("ballet flats"): "ballet_flats",
    lookup_key("shoulder bag"): "shoulder_bag",
    lookup_key("mini bag"): "mini_bag",
    lookup_key("top handle bag"): "top_handle_bag",
    lookup_key("hobo bag"): "hobo_bag",
    lookup_key("evening bag"): "evening_bag",
    lookup_key("hair accessory"): "hair_accessory",
}

COLOR_ALIASES = {
    lookup_key("grey"): "gray",
    lookup_key("navy blue"): "navy",
    lookup_key("light blue"): "light_blue",
    lookup_key("denim blue"): "denim_blue",
    lookup_key("burgandy"): "burgundy",
}

MATERIAL_ALIASES = {
    lookup_key("fake leather"): "faux_leather",
    lookup_key("vegan leather"): "faux_leather",
    lookup_key("faux leather"): "faux_leather",
    lookup_key("rib knit"): "ribbed_knit",
    lookup_key("faux fur"): "faux_fur",
}

PATTERN_ALIASES = {
    lookup_key("animal print"): "animal_print",
    lookup_key("polka dot"): "polka_dot",
    lookup_key("checker"): "checkered",
    lookup_key("checks"): "checkered",
    lookup_key("color block"): "colorblock",
}

STYLE_TAG_ALIASES = {
    lookup_key("everyday"): "casual",
    lookup_key("athleisure"): "sporty",
    lookup_key("business casual"): "business_casual",
}

FIT_TAG_ALIASES = {
    lookup_key("wide leg"): "wide_leg",
    lookup_key("straight leg"): "straight_leg",
    lookup_key("regular fit"): "regular_fit",
    lookup_key("high rise"): "high_rise",
    lookup_key("mid rise"): "mid_rise",
    lookup_key("low rise"): "low_rise",
    lookup_key("full length"): "full_length",
    lookup_key("ankle length"): "ankle_length",
}

OCCASION_TAG_ALIASES = {
    lookup_key("office"): "work",
    lookup_key("night out"): "evening",
    lookup_key("date night"): "date_night",
    lookup_key("winter event"): "winter_event",
    lookup_key("summer event"): "summer_event",
}

SEASON_TAG_ALIASES = {
    lookup_key("autumn"): "fall",
}

SILHOUETTE_ALIASES = {
    lookup_key("a-line"): "a_line",
    lookup_key("fit and flare"): "fit_and_flare",
    lookup_key("wide leg"): "wide_leg",
}

ATTRIBUTE_ALIASES = {
    lookup_key("crew neck"): "crew_neck",
    lookup_key("v neck"): "v_neck",
    lookup_key("scoop neck"): "scoop_neck",
    lookup_key("square neck"): "square_neck",
    lookup_key("sweetheart neckline"): "sweetheart_neckline",
    lookup_key("mock neck"): "mock_neck",
    lookup_key("off shoulder"): "off_shoulder",
    lookup_key("button down"): "button_front",
    lookup_key("button front"): "button_front",
    lookup_key("zip front"): "zip_front",
    lookup_key("open front"): "open_front",
    lookup_key("wrap"): "wrap_closure",
    lookup_key("tie front"): "tie_front",
    lookup_key("short sleeve"): "short_sleeve",
    lookup_key("three quarter sleeve"): "three_quarter_sleeve",
    lookup_key("long sleeve"): "long_sleeve",
    lookup_key("spaghetti strap"): "spaghetti_strap",
    lookup_key("wide strap"): "wide_strap",
    lookup_key("mini length"): "mini_length",
    lookup_key("midi length"): "midi_length",
    lookup_key("maxi length"): "maxi_length",
    lookup_key("double breasted"): "double_breasted",
    lookup_key("single breasted"): "single_breasted",
    lookup_key("cargo pockets"): "cargo_pockets",
    lookup_key("pleated front"): "pleated_front",
    lookup_key("pointed toe"): "pointed_toe",
    lookup_key("round toe"): "round_toe",
    lookup_key("square toe"): "square_toe",
    lookup_key("open toe"): "open_toe",
    lookup_key("closed toe"): "closed_toe",
    lookup_key("ankle strap"): "ankle_strap",
    lookup_key("lace up"): "lace_up",
    lookup_key("slip on"): "slip_on",
    lookup_key("stiletto"): "stiletto_heel",
    lookup_key("block heel"): "block_heel",
    lookup_key("kitten heel"): "kitten_heel",
    lookup_key("wedge heel"): "wedge_heel",
    lookup_key("chunky sole"): "chunky_sole",
    lookup_key("soft structure"): "soft_structure",
    lookup_key("chain strap"): "chain_strap",
    lookup_key("top handle"): "top_handle",
    lookup_key("shoulder strap"): "shoulder_strap",
    lookup_key("detachable strap"): "detachable_strap",
    lookup_key("quilted bag"): "quilted_bag",
    lookup_key("oversized bag"): "oversized_bag",
    lookup_key("lace trim"): "lace_trim",
}

FIELD_SPECS = {
    "category": ("scalar", CATEGORY_LOOKUP, CATEGORY_ALIASES, "category"),
    "subcategory": ("scalar", SUBCATEGORY_LOOKUP, SUBCATEGORY_ALIASES, "subcategory"),
    "primary_color": ("scalar", COLOR_LOOKUP, COLOR_ALIASES, "primary color"),
    "secondary_colors": ("list", COLOR_LOOKUP, COLOR_ALIASES, "secondary color"),
    "colors": ("list", COLOR_LOOKUP, COLOR_ALIASES, "color"),
    "material": ("scalar", MATERIAL_LOOKUP, MATERIAL_ALIASES, "material"),
    "pattern": ("scalar", PATTERN_LOOKUP, PATTERN_ALIASES, "pattern"),
    "style_tags": ("list", STYLE_TAG_LOOKUP, STYLE_TAG_ALIASES, "style tag"),
    "fit_tags": ("list", FIT_TAG_LOOKUP, FIT_TAG_ALIASES, "fit tag"),
    "occasion_tags": ("list", OCCASION_TAG_LOOKUP, OCCASION_TAG_ALIASES, "occasion tag"),
    "season_tags": ("list", SEASON_TAG_LOOKUP, SEASON_TAG_ALIASES, "season tag"),
    "silhouette": ("scalar", SILHOUETTE_LOOKUP, SILHOUETTE_ALIASES, "silhouette"),
    "attributes": ("list", ATTRIBUTE_LOOKUP, ATTRIBUTE_ALIASES, "attribute"),
    "formality": ("scalar", FORMALITY_LOOKUP, {}, "formality"),
    "warmth": ("scalar", WARMTH_LOOKUP, {}, "warmth"),
    "coverage": ("scalar", COVERAGE_LOOKUP, {}, "coverage"),
    "statement_level": ("scalar", STATEMENT_LEVEL_LOOKUP, {}, "statement level"),
    "versatility": ("scalar", VERSATILITY_LOOKUP, {}, "versatility"),
}


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

    if field_name in {"title", "brand"}:
        return _normalize_free_text(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label=field_name,
        )

    spec = FIELD_SPECS.get(field_name)
    if spec is None:
        return NormalizedFieldValue(
            field_name=field_name,
            canonical_value=None,
            applicability_state=ApplicabilityState.UNKNOWN,
            confidence=None,
            notes=(f"Unsupported normalization field '{field_name}'.",),
        )

    field_kind, lookup, aliases, label = spec
    if field_kind == "scalar":
        return _normalize_controlled_scalar(
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            label=label,
            lookup=lookup,
            aliases=aliases,
        )
    return _normalize_controlled_list(
        field_name=field_name,
        raw_value=raw_value,
        confidence=confidence,
        label=label,
        lookup=lookup,
        aliases=aliases,
    )


def derive_category_for_subcategory(subcategory: str) -> str | None:
    return SUBCATEGORY_TO_CATEGORY.get(subcategory)


def normalize_scalar_field_value(field_name: str, raw_value: Any) -> str | None:
    normalized = normalize_field_value(
        field_name=field_name,
        raw_value=raw_value,
        applicability_state=ApplicabilityState.VALUE,
        confidence=None,
    )
    if normalized.applicability_state != ApplicabilityState.VALUE:
        return None
    return normalized.canonical_value if isinstance(normalized.canonical_value, str) else None


def normalize_list_field_value(field_name: str, raw_value: Any) -> list[str]:
    normalized = normalize_field_value(
        field_name=field_name,
        raw_value=raw_value,
        applicability_state=ApplicabilityState.VALUE,
        confidence=None,
    )
    if normalized.applicability_state != ApplicabilityState.VALUE:
        return []
    return normalized.canonical_value if isinstance(normalized.canonical_value, list) else []


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
