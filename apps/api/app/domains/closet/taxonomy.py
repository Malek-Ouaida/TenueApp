from __future__ import annotations

import re

from app.domains.closet.models import LifecycleStatus, ProcessingStatus, ReviewStatus

TAXONOMY_VERSION = "closet-taxonomy-v3"
REQUIRED_CONFIRMATION_FIELDS = ("category", "subcategory")
SUPPORTED_FIELD_ORDER = (
    "title",
    "category",
    "subcategory",
    "primary_color",
    "secondary_colors",
    "material",
    "pattern",
    "brand",
    "style_tags",
    "fit_tags",
    "occasion_tags",
    "season_tags",
    "silhouette",
    "attributes",
    "formality",
    "warmth",
    "coverage",
    "statement_level",
    "versatility",
)
SUPPORTED_FIELD_NAMES = frozenset(SUPPORTED_FIELD_ORDER)
SUPPORTED_INPUT_FIELD_NAMES = SUPPORTED_FIELD_NAMES | {"colors"}
FREE_TEXT_FIELDS = frozenset({"title", "brand"})
SCALAR_CONTROLLED_FIELDS = frozenset(
    {
        "category",
        "subcategory",
        "primary_color",
        "material",
        "pattern",
        "silhouette",
        "formality",
        "warmth",
        "coverage",
        "statement_level",
        "versatility",
    }
)
LIST_FIELD_NAMES = frozenset(
    {
        "secondary_colors",
        "style_tags",
        "fit_tags",
        "occasion_tags",
        "season_tags",
        "attributes",
    }
)

CATEGORY_SUBCATEGORIES = {
    "tops": [
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
    ],
    "bottoms": [
        "jeans",
        "trousers",
        "shorts",
        "skirt",
        "leggings",
        "joggers",
        "cargo_pants",
    ],
    "dresses": [
        "shirt_dress",
        "sweater_dress",
        "bodycon_dress",
        "wrap_dress",
        "strapless_dress",
        "evening_dress",
    ],
    "outerwear": [
        "blazer",
        "jacket",
        "coat",
        "trench_coat",
        "cardigan",
        "vest",
        "denim_jacket",
        "leather_jacket",
        "puffer_jacket",
        "bomber_jacket",
        "shacket",
        "rain_jacket",
    ],
    "one_piece": [
        "jumpsuit",
        "romper",
        "catsuit",
        "overalls",
    ],
    "shoes": [
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
    ],
    "bags": [
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
    ],
    "jewelry": [
        "necklace",
        "earrings",
        "bracelet",
        "ring",
        "watch",
        "anklet",
        "brooch",
    ],
    "accessories": [
        "belt",
        "hat",
        "scarf",
        "sunglasses",
        "wallet",
        "gloves",
        "hair_accessory",
        "tie",
        "socks",
        "tights",
    ],
}

COLORS = [
    "black",
    "white",
    "gray",
    "charcoal",
    "beige",
    "cream",
    "taupe",
    "brown",
    "camel",
    "blue",
    "navy",
    "light_blue",
    "denim_blue",
    "green",
    "olive",
    "sage",
    "red",
    "burgundy",
    "pink",
    "blush",
    "purple",
    "lavender",
    "yellow",
    "mustard",
    "orange",
    "silver",
    "gold",
    "bronze",
    "multicolor",
]

MATERIALS = [
    "cotton",
    "denim",
    "wool",
    "cashmere",
    "leather",
    "faux_leather",
    "linen",
    "silk",
    "satin",
    "knit",
    "polyester",
    "nylon",
    "suede",
    "chiffon",
    "velvet",
    "lace",
    "mesh",
    "ribbed_knit",
    "jersey",
    "tweed",
    "corduroy",
    "canvas",
    "faux_fur",
]

PATTERNS = [
    "solid",
    "striped",
    "plaid",
    "checkered",
    "floral",
    "animal_print",
    "polka_dot",
    "graphic",
    "gingham",
    "abstract",
    "houndstooth",
    "camo",
    "paisley",
    "colorblock",
]

STYLE_TAGS = [
    "minimal",
    "classic",
    "tailored",
    "sporty",
    "romantic",
    "edgy",
    "bohemian",
    "streetwear",
    "preppy",
    "casual",
    "chic",
    "feminine",
    "elegant",
    "trendy",
    "vintage",
    "modern",
    "business_casual",
    "glam",
    "relaxed",
    "polished",
]

FIT_TAGS = [
    "oversized",
    "relaxed",
    "fitted",
    "slim",
    "cropped",
    "wide_leg",
    "straight_leg",
    "tapered",
    "bodycon",
    "loose",
    "boxy",
    "regular_fit",
    "high_rise",
    "mid_rise",
    "low_rise",
    "full_length",
    "ankle_length",
]

OCCASION_TAGS = [
    "everyday",
    "work",
    "formal",
    "evening",
    "event",
    "active",
    "travel",
    "lounge",
    "vacation",
    "party",
    "date_night",
    "wedding",
    "beach",
    "brunch",
    "school",
    "winter_event",
    "summer_event",
]

SEASON_TAGS = ["spring", "summer", "fall", "winter"]

SILHOUETTES = [
    "a_line",
    "straight",
    "fit_and_flare",
    "pencil",
    "column",
    "wide_leg",
    "tapered",
    "flared",
    "bodycon",
    "boxy",
    "oversized",
    "shift",
]

ATTRIBUTES = [
    "crew_neck",
    "v_neck",
    "scoop_neck",
    "square_neck",
    "sweetheart_neckline",
    "mock_neck",
    "turtleneck",
    "collared",
    "off_shoulder",
    "halter",
    "strapless",
    "one_shoulder",
    "button_front",
    "zip_front",
    "open_front",
    "wrap_closure",
    "tie_front",
    "belted",
    "sleeveless",
    "cap_sleeve",
    "short_sleeve",
    "three_quarter_sleeve",
    "long_sleeve",
    "puff_sleeve",
    "racerback",
    "spaghetti_strap",
    "wide_strap",
    "slit",
    "pleated",
    "ruched",
    "tiered",
    "asymmetrical",
    "mini_length",
    "midi_length",
    "maxi_length",
    "quilted",
    "waterproof",
    "hooded",
    "double_breasted",
    "single_breasted",
    "padded",
    "cropped_jacket",
    "oversized_blazer",
    "distressed",
    "ripped",
    "cargo_pockets",
    "pleated_front",
    "drawstring",
    "cuffed",
    "pointed_toe",
    "round_toe",
    "square_toe",
    "open_toe",
    "closed_toe",
    "ankle_strap",
    "lace_up",
    "slip_on",
    "platform",
    "stiletto_heel",
    "block_heel",
    "kitten_heel",
    "wedge_heel",
    "chunky_sole",
    "structured",
    "soft_structure",
    "chain_strap",
    "top_handle",
    "shoulder_strap",
    "detachable_strap",
    "quilted_bag",
    "oversized_bag",
    "embellished",
    "metallic",
    "sheer",
    "transparent",
    "sequined",
    "beaded",
    "lace_trim",
    "textured",
]

FORMALITY_VALUES = [
    "casual",
    "smart_casual",
    "dressy",
    "formal",
    "semi_formal",
]

WARMTH_VALUES = [
    "lightweight",
    "midweight",
    "heavyweight",
]

COVERAGE_VALUES = [
    "revealing",
    "balanced",
    "covered",
]

STATEMENT_LEVEL_VALUES = [
    "basic",
    "staple",
    "statement",
]

VERSATILITY_VALUES = [
    "low",
    "medium",
    "high",
]

CATEGORY_VALUES = tuple(CATEGORY_SUBCATEGORIES.keys())
SUBCATEGORY_VALUES = tuple(
    subcategory
    for subcategories in CATEGORY_SUBCATEGORIES.values()
    for subcategory in subcategories
)
CONTROLLED_SCALAR_VALUES = {
    "category": frozenset(CATEGORY_VALUES),
    "subcategory": frozenset(SUBCATEGORY_VALUES),
    "primary_color": frozenset(COLORS),
    "material": frozenset(MATERIALS),
    "pattern": frozenset(PATTERNS),
    "silhouette": frozenset(SILHOUETTES),
    "formality": frozenset(FORMALITY_VALUES),
    "warmth": frozenset(WARMTH_VALUES),
    "coverage": frozenset(COVERAGE_VALUES),
    "statement_level": frozenset(STATEMENT_LEVEL_VALUES),
    "versatility": frozenset(VERSATILITY_VALUES),
}
CONTROLLED_LIST_VALUES = {
    "secondary_colors": frozenset(COLORS),
    "style_tags": frozenset(STYLE_TAGS),
    "fit_tags": frozenset(FIT_TAGS),
    "occasion_tags": frozenset(OCCASION_TAGS),
    "season_tags": frozenset(SEASON_TAGS),
    "attributes": frozenset(ATTRIBUTES),
}


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
        "subcategory_by_category": CATEGORY_SUBCATEGORIES,
        "primary_colors": COLORS,
        "secondary_colors": COLORS,
        "colors": COLORS,
        "materials": MATERIALS,
        "patterns": PATTERNS,
        "style_tags": STYLE_TAGS,
        "fit_tags": FIT_TAGS,
        "occasion_tags": OCCASION_TAGS,
        "season_tags": SEASON_TAGS,
        "silhouettes": SILHOUETTES,
        "attributes": ATTRIBUTES,
        "formality": FORMALITY_VALUES,
        "warmth": WARMTH_VALUES,
        "coverage": COVERAGE_VALUES,
        "statement_level": STATEMENT_LEVEL_VALUES,
        "versatility": VERSATILITY_VALUES,
    }


def enum_members(
    enum_cls: type[LifecycleStatus] | type[ProcessingStatus] | type[ReviewStatus],
) -> list[str]:
    return [value.value for value in enum_cls]


def is_supported_field_name(field_name: str) -> bool:
    return field_name in SUPPORTED_FIELD_NAMES


def is_supported_input_field_name(field_name: str) -> bool:
    return field_name in SUPPORTED_INPUT_FIELD_NAMES


def is_supported_taxonomy_version(value: str) -> bool:
    return value in {"closet-taxonomy-v1", "closet-taxonomy-v2", TAXONOMY_VERSION}


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
    normalized = collapsed.replace("_", " ").replace("-", " ")
    return normalized.casefold()
