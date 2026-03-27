from __future__ import annotations

from app.domains.closet.models import LifecycleStatus, ProcessingStatus, ReviewStatus

TAXONOMY_VERSION = "closet-taxonomy-v1"
REQUIRED_CONFIRMATION_FIELDS = ("category", "subcategory")
SUPPORTED_FIELD_NAMES = frozenset(
    {
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
    }
)

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
