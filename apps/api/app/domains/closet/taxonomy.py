from __future__ import annotations

import re

from app.domains.closet.models import LifecycleStatus, ProcessingStatus, ReviewStatus

TAXONOMY_VERSION = "closet-taxonomy-v1"
REQUIRED_CONFIRMATION_FIELDS = ("category", "subcategory")
SUPPORTED_FIELD_ORDER = (
    "title",
    "category",
    "subcategory",
    "colors",
    "material",
    "pattern",
    "brand",
    "style_tags",
    "occasion_tags",
    "season_tags",
)
SUPPORTED_FIELD_NAMES = frozenset(SUPPORTED_FIELD_ORDER)

CATEGORY_SUBCATEGORIES = {
    "tops": ["t-shirt", "shirt", "blouse", "tank top", "sweater", "hoodie"],
    "bottoms": ["jeans", "trousers", "shorts", "skirt", "leggings"],
    "dresses": ["mini dress", "midi dress", "maxi dress"],
    "outerwear": ["jacket", "coat", "blazer", "cardigan"],
    "shoes": ["sneakers", "boots", "heels", "flats", "sandals", "loafers"],
    "bags": ["tote", "shoulder bag", "crossbody", "backpack", "clutch"],
    "accessories": ["belt", "hat", "scarf", "sunglasses", "jewelry"],
}

COLORS = [
    "black",
    "white",
    "gray",
    "beige",
    "brown",
    "blue",
    "navy",
    "green",
    "red",
    "pink",
    "purple",
    "yellow",
    "orange",
    "silver",
    "gold",
    "multicolor",
]

MATERIALS = [
    "cotton",
    "denim",
    "wool",
    "leather",
    "faux leather",
    "linen",
    "silk",
    "satin",
    "knit",
    "polyester",
    "suede",
    "chiffon",
]

PATTERNS = [
    "solid",
    "striped",
    "plaid",
    "floral",
    "animal print",
    "polka dot",
    "graphic",
    "textured",
]

STYLE_TAGS = ["casual", "sporty"]
OCCASION_TAGS = ["formal", "business", "evening"]
SEASON_TAGS = ["summer", "winter"]

CATEGORY_VALUES = tuple(CATEGORY_SUBCATEGORIES.keys())
SUBCATEGORY_VALUES = tuple(
    subcategory
    for subcategories in CATEGORY_SUBCATEGORIES.values()
    for subcategory in subcategories
)


def build_metadata_options() -> dict[str, object]:
    return {
        "taxonomy_version": TAXONOMY_VERSION,
        "required_confirmation_fields": list(REQUIRED_CONFIRMATION_FIELDS),
        "lifecycle_statuses": enum_members(LifecycleStatus),
        "processing_statuses": enum_members(ProcessingStatus),
        "review_statuses": enum_members(ReviewStatus),
        "categories": [
            {"name": category, "subcategories": subcategories}
            for category, subcategories in CATEGORY_SUBCATEGORIES.items()
        ],
        "colors": COLORS,
        "materials": MATERIALS,
        "patterns": PATTERNS,
        "style_tags": STYLE_TAGS,
        "occasion_tags": OCCASION_TAGS,
        "season_tags": SEASON_TAGS,
    }


def enum_members(
    enum_cls: type[LifecycleStatus] | type[ProcessingStatus] | type[ReviewStatus],
) -> list[str]:
    return [value.value for value in enum_cls]


def is_supported_field_name(field_name: str) -> bool:
    return field_name in SUPPORTED_FIELD_NAMES


def is_supported_taxonomy_version(value: str) -> bool:
    return value == TAXONOMY_VERSION


def canonicalize_category_filter(value: str) -> str | None:
    return _canonicalize_controlled_value(value, CATEGORY_VALUES)


def canonicalize_subcategory_filter(value: str) -> str | None:
    return _canonicalize_controlled_value(value, SUBCATEGORY_VALUES)


def canonicalize_color_filter(value: str) -> str | None:
    return _canonicalize_controlled_value(value, tuple(COLORS))


def canonicalize_material_filter(value: str) -> str | None:
    return _canonicalize_controlled_value(value, tuple(MATERIALS))


def canonicalize_pattern_filter(value: str) -> str | None:
    return _canonicalize_controlled_value(value, tuple(PATTERNS))


def is_valid_category_subcategory_pair(*, category: str, subcategory: str) -> bool:
    return subcategory in CATEGORY_SUBCATEGORIES.get(category, [])


def _canonicalize_controlled_value(
    value: str,
    allowed_values: tuple[str, ...],
) -> str | None:
    normalized = _normalize_filter_value(value)
    if not normalized:
        return None

    for allowed_value in allowed_values:
        if _normalize_filter_value(allowed_value) == normalized:
            return allowed_value

    return None


def _normalize_filter_value(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    return collapsed.casefold()
