from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.closet.models import ApplicabilityState
from app.domains.closet.normalization import normalize_field_value
from app.domains.closet.similarity import ComparableItem, compute_similarity
from app.domains.wear.models import WearEventDetectedItem
from app.domains.wear.repository import WearRepository


@dataclass(frozen=True)
class WearDetectionInput:
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


@dataclass(frozen=True)
class WearMatchCandidateResult:
    closet_item_id: UUID
    rank: int
    score: float
    signals_json: object | None


class WearMatchingService:
    DEFAULT_LIMIT = 3

    STRICT_MIN_SCORE = 0.58
    RELAXED_MIN_SCORE = 0.44

    ROLE_FAMILY_MAP = {
        "top": "top",
        "bottom": "bottom",
        "outerwear": "outerwear",
        "footwear": "footwear",
        "dress": "dress",
        "full_body": "one_piece",
        "bag": "bag",
        "jewelry": "jewelry",
        "accessory": "accessory",
        "hat": "accessory",
        "scarf": "accessory",
        "eyewear": "accessory",
        "glasses": "accessory",
    }

    CATEGORY_FAMILY_MAP = {
        "tops": "top",
        "bottoms": "bottom",
        "outerwear": "outerwear",
        "dresses": "dress",
        "one_piece": "one_piece",
        "shoes": "footwear",
        "bags": "bag",
        "jewelry": "jewelry",
        "accessories": "accessory",
    }

    FAMILY_KEYWORDS = {
        "top": {
            "top",
            "tops",
            "t-shirt",
            "t shirt",
            "tee",
            "shirt",
            "blouse",
            "tank",
            "tank top",
            "camisole",
            "cami",
            "polo",
            "sweater",
            "sweatshirt",
            "hoodie",
            "bodysuit",
        },
        "bottom": {
            "bottom",
            "bottoms",
            "pants",
            "trousers",
            "jeans",
            "shorts",
            "skirt",
            "leggings",
            "joggers",
            "cargo",
        },
        "outerwear": {
            "outerwear",
            "cardigan",
            "blazer",
            "jacket",
            "coat",
            "trench coat",
            "vest",
        },
        "footwear": {
            "footwear",
            "shoe",
            "shoes",
            "sneaker",
            "sneakers",
            "heel",
            "heels",
            "boot",
            "boots",
            "loafer",
            "loafers",
            "flat",
            "flats",
            "sandal",
            "sandals",
            "mule",
            "mules",
        },
        "dress": {
            "dress",
            "mini dress",
            "midi dress",
            "maxi dress",
            "slip dress",
            "shirt dress",
            "sweater dress",
        },
        "one_piece": {
            "one piece",
            "one_piece",
            "jumpsuit",
            "romper",
        },
        "bag": {
            "bag",
            "bags",
            "shoulder bag",
            "crossbody",
            "crossbody bag",
            "tote",
            "backpack",
            "clutch",
            "handbag",
            "purse",
        },
        "jewelry": {
            "jewelry",
            "necklace",
            "bracelet",
            "ring",
            "watch",
            "earring",
            "earrings",
        },
        "accessory": {
            "accessory",
            "accessories",
            "hat",
            "scarf",
            "sunglasses",
            "glasses",
            "eyewear",
            "belt",
            "wallet",
        },
    }

    ACCESSORY_TYPE_KEYWORDS = {
        "hat": {"hat", "cap", "beanie", "beret"},
        "scarf": {"scarf"},
        "eyewear": {"eyewear", "glasses", "eyeglasses", "sunglasses", "spectacles"},
        "belt": {"belt"},
        "wallet": {"wallet"},
    }

    SUBCATEGORY_EQUIVALENT_GROUPS = {
        "top": [
            {"t-shirt", "shirt", "polo"},
            {"tank top", "camisole", "bodysuit"},
            {"sweater", "sweatshirt", "hoodie"},
        ],
        "bottom": [
            {"jeans", "trousers"},
        ],
        "outerwear": [
            {"cardigan", "blazer", "jacket", "coat", "trench coat", "vest"},
        ],
        "footwear": [
            {"sneakers", "boots", "heels", "flats", "loafers", "sandals", "mules"},
        ],
        "bag": [
            {"shoulder bag", "crossbody", "tote", "backpack", "clutch"},
        ],
        "jewelry": [
            {"necklace"},
            {"bracelet"},
            {"ring"},
            {"watch"},
            {"earrings"},
        ],
        "accessory": [
            {"hat"},
            {"scarf"},
            {"sunglasses"},
            {"belt"},
            {"wallet"},
        ],
    }

    def __init__(
        self,
        *,
        session: Session,
        repository: WearRepository,
    ) -> None:
        self.session = session
        self.repository = repository

    def rank_candidates_for_detected_item(
        self,
        *,
        user_id: UUID,
        detected_item: WearEventDetectedItem,
        limit: int = DEFAULT_LIMIT,
    ) -> list[WearMatchCandidateResult]:
        return self._rank_candidates(
            user_id=user_id,
            role=self._normalize_role(getattr(detected_item, "predicted_role", None)),
            category=getattr(detected_item, "predicted_category", None),
            subcategory=getattr(detected_item, "predicted_subcategory", None),
            colors=list(getattr(detected_item, "predicted_colors_json", None) or []),
            material=getattr(detected_item, "predicted_material", None),
            pattern=getattr(detected_item, "predicted_pattern", None),
            fit_tags=list(getattr(detected_item, "predicted_fit_tags_json", None) or []),
            silhouette=getattr(detected_item, "predicted_silhouette", None),
            attributes=list(getattr(detected_item, "predicted_attributes_json", None) or []),
            confidence=getattr(detected_item, "confidence", None),
            limit=limit,
        )

    def rank_candidates_for_detection(
        self,
        *,
        user_id: UUID,
        detection: WearDetectionInput,
        limit: int = DEFAULT_LIMIT,
    ) -> list[WearMatchCandidateResult]:
        return self._rank_candidates(
            user_id=user_id,
            role=detection.role,
            category=detection.category,
            subcategory=detection.subcategory,
            colors=list(detection.colors or []),
            material=detection.material,
            pattern=detection.pattern,
            fit_tags=list(detection.fit_tags or []),
            silhouette=detection.silhouette,
            attributes=list(detection.attributes or []),
            confidence=detection.confidence,
            limit=limit,
        )

    def should_surface_detection(
        self,
        *,
        user_id: UUID,
        detection: WearDetectionInput,
    ) -> bool:
        return bool(
            self.rank_candidates_for_detection(
                user_id=user_id,
                detection=detection,
                limit=1,
            )
        )

    def _rank_candidates(
        self,
        *,
        user_id: UUID,
        role: str | None,
        category: str | None,
        subcategory: str | None,
        colors: list[str],
        material: str | None,
        pattern: str | None,
        fit_tags: list[str],
        silhouette: str | None,
        attributes: list[str],
        confidence: float | None,
        limit: int,
    ) -> list[WearMatchCandidateResult]:
        detected_role = self._normalize_role(role)
        detected_category = _normalize_scalar_field("category", category)
        detected_subcategory = _normalize_scalar_field("subcategory", subcategory)
        detected_colors = _normalize_colors(list(colors or []))
        detected_material = _normalize_scalar_field("material", material)
        detected_pattern = _normalize_scalar_field("pattern", pattern)
        detected_fit_tags = _normalize_list_field("fit_tags", list(fit_tags or []))
        detected_silhouette = _normalize_scalar_field("silhouette", silhouette)
        detected_attributes = _normalize_list_field("attributes", list(attributes or []))
        detected_confidence = self._normalize_confidence(confidence)

        detected_family = self._infer_family(
            role=detected_role,
            category=detected_category,
            subcategory=detected_subcategory,
            title=None,
        )
        detected_accessory_type = self._infer_accessory_type(
            family=detected_family,
            title=None,
            category=detected_category,
            subcategory=detected_subcategory,
            role=detected_role,
        )

        anchor = self._build_anchor_from_values(
            category=detected_category,
            subcategory=detected_subcategory,
            colors=detected_colors,
            material=detected_material,
            pattern=detected_pattern,
        )

        strict_ranked: list[tuple[UUID, float, dict]] = []
        relaxed_ranked: list[tuple[UUID, float, dict]] = []

        for closet_item, projection in self.repository.list_active_confirmed_closet_items_with_projections_for_user(
            user_id=user_id
        ):
            peer_title = _normalize_optional_string(projection.title)
            peer_category = _normalize_scalar_field("category", projection.category)
            peer_subcategory = _normalize_scalar_field("subcategory", projection.subcategory)
            peer_colors = _extract_projection_colors(
                primary_color=projection.primary_color,
                secondary_colors=list(projection.secondary_colors or []),
            )
            peer_material = _normalize_scalar_field("material", projection.material)
            peer_pattern = _normalize_scalar_field("pattern", projection.pattern)
            peer_fit_tags = _normalize_list_field("fit_tags", list(projection.fit_tags or []))
            peer_silhouette = _normalize_scalar_field("silhouette", projection.silhouette)
            peer_attributes = _normalize_list_field("attributes", list(projection.attributes or []))

            peer_family = self._infer_family(
                role=None,
                category=peer_category,
                subcategory=peer_subcategory,
                title=peer_title,
            )
            peer_accessory_type = self._infer_accessory_type(
                family=peer_family,
                title=peer_title,
                category=peer_category,
                subcategory=peer_subcategory,
                role=None,
            )

            mode, compatibility_signals = self._compatibility_gate(
                detected_family=detected_family,
                detected_category=detected_category,
                detected_subcategory=detected_subcategory,
                detected_accessory_type=detected_accessory_type,
                peer_family=peer_family,
                peer_category=peer_category,
                peer_subcategory=peer_subcategory,
                peer_accessory_type=peer_accessory_type,
            )
            if mode is None:
                continue

            peer = ComparableItem(
                title=None,
                category=projection.category,
                subcategory=projection.subcategory,
                primary_color=projection.primary_color,
                secondary_colors=list(projection.secondary_colors or []),
                material=projection.material,
                pattern=projection.pattern,
                brand=projection.brand,
                image_bytes=None,
                image_role=None,
            )

            similarity = compute_similarity(anchor, peer)
            raw_similarity = float(similarity.score)
            normalized_similarity = self._normalize_similarity_score(raw_similarity)

            score, score_breakdown = self._score_candidate(
                normalized_similarity=normalized_similarity,
                detected_family=detected_family,
                detected_category=detected_category,
                detected_subcategory=detected_subcategory,
                detected_colors=detected_colors,
                detected_material=detected_material,
                detected_pattern=detected_pattern,
                detected_fit_tags=detected_fit_tags,
                detected_silhouette=detected_silhouette,
                detected_attributes=detected_attributes,
                detected_confidence=detected_confidence,
                detected_accessory_type=detected_accessory_type,
                peer_family=peer_family,
                peer_category=peer_category,
                peer_subcategory=peer_subcategory,
                peer_colors=peer_colors,
                peer_material=peer_material,
                peer_pattern=peer_pattern,
                peer_fit_tags=peer_fit_tags,
                peer_silhouette=peer_silhouette,
                peer_attributes=peer_attributes,
                peer_accessory_type=peer_accessory_type,
            )

            signals = {
                "mode": mode,
                "raw_similarity": raw_similarity,
                "normalized_similarity": normalized_similarity,
                "compatibility": compatibility_signals,
                "score_breakdown": score_breakdown,
                "similarity_payload": similarity.to_payload(),
            }

            if mode == "strict" and score >= self.STRICT_MIN_SCORE:
                strict_ranked.append((closet_item.id, score, signals))
            elif mode == "relaxed" and score >= self.RELAXED_MIN_SCORE:
                relaxed_ranked.append((closet_item.id, score, signals))

        strict_ranked.sort(key=lambda value: (-value[1], str(value[0])))
        relaxed_ranked.sort(key=lambda value: (-value[1], str(value[0])))

        final_ranked = strict_ranked[:limit]
        if not final_ranked:
            final_ranked = relaxed_ranked[:limit]

        return [
            WearMatchCandidateResult(
                closet_item_id=closet_item_id,
                rank=index + 1,
                score=self._clamp_score(score),
                signals_json=signals_json,
            )
            for index, (closet_item_id, score, signals_json) in enumerate(final_ranked)
        ]

    def _build_anchor(self, *, detected_item: WearEventDetectedItem) -> ComparableItem:
        normalized_category = _normalize_scalar_field("category", getattr(detected_item, "predicted_category", None))
        normalized_subcategory = _normalize_scalar_field("subcategory", getattr(detected_item, "predicted_subcategory", None))
        normalized_colors = _normalize_colors(list(getattr(detected_item, "predicted_colors_json", None) or []))
        normalized_material = _normalize_scalar_field("material", getattr(detected_item, "predicted_material", None))
        normalized_pattern = _normalize_scalar_field("pattern", getattr(detected_item, "predicted_pattern", None))
        return self._build_anchor_from_values(
            category=normalized_category,
            subcategory=normalized_subcategory,
            colors=normalized_colors,
            material=normalized_material,
            pattern=normalized_pattern,
        )

    def _build_anchor_from_values(
        self,
        *,
        category: str | None,
        subcategory: str | None,
        colors: list[str],
        material: str | None,
        pattern: str | None,
    ) -> ComparableItem:
        return ComparableItem(
            title=None,
            category=category,
            subcategory=subcategory,
            primary_color=colors[0] if colors else None,
            secondary_colors=colors[1:] if len(colors) > 1 else [],
            material=material,
            pattern=pattern,
            brand=None,
            image_bytes=None,
            image_role=None,
        )

    def _compatibility_gate(
        self,
        *,
        detected_family: str | None,
        detected_category: str | None,
        detected_subcategory: str | None,
        detected_accessory_type: str | None,
        peer_family: str | None,
        peer_category: str | None,
        peer_subcategory: str | None,
        peer_accessory_type: str | None,
    ) -> tuple[str | None, dict]:
        signals = {
            "detected_family": detected_family,
            "detected_category": detected_category,
            "detected_subcategory": detected_subcategory,
            "detected_accessory_type": detected_accessory_type,
            "peer_family": peer_family,
            "peer_category": peer_category,
            "peer_subcategory": peer_subcategory,
            "peer_accessory_type": peer_accessory_type,
        }

        if detected_family is None or peer_family is None:
            return None, signals

        if detected_family != peer_family:
            if {detected_family, peer_family} == {"dress", "one_piece"}:
                return "relaxed", signals
            return None, signals

        if detected_family in {"bag", "jewelry"}:
            if detected_subcategory and peer_subcategory:
                if detected_subcategory == peer_subcategory:
                    return "strict", signals
                if self._subcategories_equivalent(
                    family=detected_family,
                    left=detected_subcategory,
                    right=peer_subcategory,
                ):
                    return "relaxed", signals
                return None, signals
            return "relaxed", signals

        if detected_family == "accessory":
            if detected_accessory_type and peer_accessory_type:
                if detected_accessory_type == peer_accessory_type:
                    return "strict", signals
                return None, signals
            if detected_subcategory and peer_subcategory and detected_subcategory == peer_subcategory:
                return "strict", signals
            return "relaxed", signals

        if detected_category and peer_category and detected_category == peer_category:
            if detected_subcategory and peer_subcategory and detected_subcategory == peer_subcategory:
                return "strict", signals
            if (
                detected_subcategory
                and peer_subcategory
                and self._subcategories_equivalent(
                    family=detected_family,
                    left=detected_subcategory,
                    right=peer_subcategory,
                )
            ):
                return "relaxed", signals
            return "strict", signals

        if (
            detected_subcategory
            and peer_subcategory
            and self._subcategories_equivalent(
                family=detected_family,
                left=detected_subcategory,
                right=peer_subcategory,
            )
        ):
            return "relaxed", signals

        if detected_category or peer_category or detected_subcategory or peer_subcategory:
            return "relaxed", signals

        return None, signals

    def _score_candidate(
        self,
        *,
        normalized_similarity: float,
        detected_family: str | None,
        detected_category: str | None,
        detected_subcategory: str | None,
        detected_colors: list[str],
        detected_material: str | None,
        detected_pattern: str | None,
        detected_fit_tags: list[str],
        detected_silhouette: str | None,
        detected_attributes: list[str],
        detected_confidence: float | None,
        detected_accessory_type: str | None,
        peer_family: str | None,
        peer_category: str | None,
        peer_subcategory: str | None,
        peer_colors: list[str],
        peer_material: str | None,
        peer_pattern: str | None,
        peer_fit_tags: list[str],
        peer_silhouette: str | None,
        peer_attributes: list[str],
        peer_accessory_type: str | None,
    ) -> tuple[float, dict]:
        score = 0.0

        family_exact = bool(detected_family and peer_family and detected_family == peer_family)
        category_exact = bool(detected_category and peer_category and detected_category == peer_category)
        subcategory_exact = bool(
            detected_subcategory and peer_subcategory and detected_subcategory == peer_subcategory
        )
        subcategory_equivalent = bool(
            detected_family
            and detected_subcategory
            and peer_subcategory
            and self._subcategories_equivalent(
                family=detected_family,
                left=detected_subcategory,
                right=peer_subcategory,
            )
        )
        accessory_type_exact = bool(
            detected_accessory_type
            and peer_accessory_type
            and detected_accessory_type == peer_accessory_type
        )

        color_overlap = len(set(detected_colors) & set(peer_colors))
        fit_overlap = len(set(detected_fit_tags) & set(peer_fit_tags))
        attribute_overlap = len(set(detected_attributes) & set(peer_attributes))
        material_exact = bool(detected_material and peer_material and detected_material == peer_material)
        pattern_exact = bool(detected_pattern and peer_pattern and detected_pattern == peer_pattern)
        silhouette_exact = bool(
            detected_silhouette and peer_silhouette and detected_silhouette == peer_silhouette
        )

        score += normalized_similarity * 0.15

        if family_exact:
            score += 0.18

        if category_exact:
            score += 0.16
        elif detected_category and peer_category:
            score -= 0.04

        if subcategory_exact:
            score += 0.16
        elif subcategory_equivalent:
            score += 0.08
        elif detected_subcategory and peer_subcategory:
            score -= 0.02

        if color_overlap > 0:
            score += min(0.12, color_overlap * 0.06)

        if material_exact:
            score += 0.08

        if pattern_exact:
            score += 0.05

        if fit_overlap > 0:
            score += min(0.10, fit_overlap * 0.05)

        if silhouette_exact:
            score += 0.08

        if attribute_overlap > 0:
            score += min(0.14, attribute_overlap * 0.04)

        if accessory_type_exact:
            score += 0.10

        confidence_bonus = 0.0
        low_confidence_penalty = 0.0
        if detected_confidence is not None:
            confidence_bonus = min(0.03, detected_confidence * 0.03)
            score += confidence_bonus
            if detected_confidence < 0.20:
                low_confidence_penalty = 0.04
                score -= low_confidence_penalty

        final_score = self._clamp_score(score)

        breakdown = {
            "family_exact": family_exact,
            "category_exact": category_exact,
            "subcategory_exact": subcategory_exact,
            "subcategory_equivalent": subcategory_equivalent,
            "color_overlap_count": color_overlap,
            "material_exact": material_exact,
            "pattern_exact": pattern_exact,
            "fit_overlap_count": fit_overlap,
            "silhouette_exact": silhouette_exact,
            "attribute_overlap_count": attribute_overlap,
            "accessory_type_exact": accessory_type_exact,
            "confidence_bonus": confidence_bonus,
            "low_confidence_penalty": low_confidence_penalty,
            "final_score": final_score,
        }
        return final_score, breakdown

    def _subcategories_equivalent(
        self,
        *,
        family: str,
        left: str | None,
        right: str | None,
    ) -> bool:
        if not left or not right:
            return False
        if left == right:
            return True

        groups = self.SUBCATEGORY_EQUIVALENT_GROUPS.get(family, [])
        for group in groups:
            if left in group and right in group:
                return True
        return False

    def _normalize_role(self, value: object) -> str | None:
        if value is None:
            return None
        if hasattr(value, "value"):
            value = getattr(value, "value")
        normalized = str(value).strip().lower()
        return normalized or None

    def _infer_family(
        self,
        *,
        role: str | None,
        category: str | None,
        subcategory: str | None,
        title: str | None,
    ) -> str | None:
        if role:
            mapped = self.ROLE_FAMILY_MAP.get(role)
            if mapped is not None:
                return mapped

        if category:
            mapped = self.CATEGORY_FAMILY_MAP.get(category)
            if mapped is not None:
                return mapped

        haystack = _join_text(title, category, subcategory)
        if not haystack:
            return None

        ordered_families = (
            "outerwear",
            "top",
            "bottom",
            "footwear",
            "dress",
            "one_piece",
            "bag",
            "jewelry",
            "accessory",
        )
        for family in ordered_families:
            if _contains_any_phrase(haystack, self.FAMILY_KEYWORDS[family]):
                return family

        return None

    def _infer_accessory_type(
        self,
        *,
        family: str | None,
        title: str | None,
        category: str | None,
        subcategory: str | None,
        role: str | None,
    ) -> str | None:
        if family == "bag":
            return "bag"
        if family == "jewelry":
            return "jewelry"

        normalized_role = self._normalize_role(role)
        if normalized_role in {"hat", "scarf", "eyewear", "glasses"}:
            return "eyewear" if normalized_role == "glasses" else normalized_role

        haystack = _join_text(title, category, subcategory)
        if not haystack:
            return None

        for accessory_type, keywords in self.ACCESSORY_TYPE_KEYWORDS.items():
            if _contains_any_phrase(haystack, keywords):
                return accessory_type

        return None

    def _normalize_confidence(self, value: object) -> float | None:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, min(1.0, numeric))

    def _normalize_similarity_score(self, raw_score: float) -> float:
        if raw_score <= 0:
            return 0.0
        if raw_score <= 1:
            return raw_score
        if raw_score <= 10:
            return raw_score / 10.0
        if raw_score <= 100:
            return raw_score / 100.0
        return 1.0

    def _clamp_score(self, score: float) -> float:
        return max(0.0, min(1.0, float(score)))


def _normalize_scalar_field(field_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_field_value(
        field_name=field_name,
        raw_value=value,
        applicability_state=ApplicabilityState.VALUE,
        confidence=None,
    )
    if not isinstance(normalized.canonical_value, str):
        return None
    cleaned = normalized.canonical_value.strip()
    return cleaned or None


def _normalize_list_field(field_name: str, values: list[str]) -> list[str]:
    normalized = normalize_field_value(
        field_name=field_name,
        raw_value=list(values or []),
        applicability_state=ApplicabilityState.VALUE,
        confidence=None,
    )
    canonical = normalized.canonical_value
    if not isinstance(canonical, list):
        return []

    deduped: list[str] = []
    seen: set[str] = set()
    for item in canonical:
        if not isinstance(item, str):
            continue
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_colors(colors: list[str]) -> list[str]:
    return _normalize_list_field("colors", list(colors or []))


def _extract_projection_colors(
    *,
    primary_color: str | None,
    secondary_colors: list[str],
) -> list[str]:
    raw_colors: list[str] = []
    if primary_color:
        raw_colors.append(primary_color)
    raw_colors.extend(secondary_colors)
    return _normalize_colors(raw_colors)


def _join_text(*parts: str | None) -> str:
    return " | ".join(part.strip().lower() for part in parts if part and part.strip())


def _contains_any_phrase(haystack: str, phrases: set[str]) -> bool:
    return any(phrase in haystack for phrase in phrases)