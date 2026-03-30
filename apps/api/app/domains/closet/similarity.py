from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError

from app.domains.closet.models import SimilarityType
from app.domains.closet.normalization import collapse_whitespace

SIMILARITY_ALGORITHM_VERSION = "similarity-v1"

SAME_CATEGORY_POINTS = 25.0
SAME_SUBCATEGORY_POINTS = 20.0
HASH_DISTANCE_POINTS = (
    (2, 35.0),
    (6, 25.0),
    (10, 15.0),
)
COLOR_OVERLAP_POINTS = (
    (2, 12.0),
    (1, 8.0),
)
MATERIAL_MATCH_POINTS = 8.0
PATTERN_MATCH_POINTS = 6.0
BRAND_MATCH_POINTS = 4.0
TITLE_TOKEN_MATCH_POINTS = 4.0
CATEGORY_MISMATCH_PENALTY = -30.0
SUBCATEGORY_MISMATCH_PENALTY = -8.0

DUPLICATE_SCORE_THRESHOLD = 70.0
SIMILAR_SCORE_THRESHOLD = 45.0
DUPLICATE_HASH_DISTANCE_THRESHOLD = 6


@dataclass(frozen=True)
class SimilaritySignal:
    code: str
    label: str
    contribution: float
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ComparableItem:
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    secondary_colors: list[str] | None
    material: str | None
    pattern: str | None
    brand: str | None
    image_bytes: bytes | None
    image_role: str | None


@dataclass(frozen=True)
class SimilarityComputation:
    score: float
    similarity_type: SimilarityType | None
    signals: list[SimilaritySignal]
    hash_distance: int | None
    anchor_image_role: str | None
    peer_image_role: str | None
    algorithm_version: str = SIMILARITY_ALGORITHM_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "algorithm_version": self.algorithm_version,
            "hash_distance": self.hash_distance,
            "anchor_image_role": self.anchor_image_role,
            "peer_image_role": self.peer_image_role,
            "signals": [
                {
                    "code": signal.code,
                    "label": signal.label,
                    "contribution": signal.contribution,
                    "metadata": signal.metadata,
                }
                for signal in self.signals
            ],
        }


def compute_similarity(
    anchor: ComparableItem,
    peer: ComparableItem,
) -> SimilarityComputation:
    signals: list[SimilaritySignal] = []
    score = 0.0

    anchor_category = _normalize_scalar(anchor.category)
    peer_category = _normalize_scalar(peer.category)
    anchor_subcategory = _normalize_scalar(anchor.subcategory)
    peer_subcategory = _normalize_scalar(peer.subcategory)

    if anchor_category and peer_category:
        if anchor_category == peer_category:
            signals.append(
                SimilaritySignal(
                    code="category_match",
                    label="Items share the same category.",
                    contribution=SAME_CATEGORY_POINTS,
                    metadata={"category": anchor_category},
                )
            )
            score += SAME_CATEGORY_POINTS
        else:
            signals.append(
                SimilaritySignal(
                    code="category_mismatch",
                    label="Items fall into different categories.",
                    contribution=CATEGORY_MISMATCH_PENALTY,
                    metadata={"anchor": anchor_category, "peer": peer_category},
                )
            )
            score += CATEGORY_MISMATCH_PENALTY

    if anchor_category and peer_category and anchor_category == peer_category:
        if anchor_subcategory and peer_subcategory:
            if anchor_subcategory == peer_subcategory:
                signals.append(
                    SimilaritySignal(
                        code="subcategory_match",
                        label="Items share the same subcategory.",
                        contribution=SAME_SUBCATEGORY_POINTS,
                        metadata={"subcategory": anchor_subcategory},
                    )
                )
                score += SAME_SUBCATEGORY_POINTS
            else:
                signals.append(
                    SimilaritySignal(
                        code="subcategory_mismatch",
                        label="Items differ at the subcategory level.",
                        contribution=SUBCATEGORY_MISMATCH_PENALTY,
                        metadata={"anchor": anchor_subcategory, "peer": peer_subcategory},
                    )
                )
                score += SUBCATEGORY_MISMATCH_PENALTY

    hash_distance = _hash_distance(anchor.image_bytes, peer.image_bytes)
    if hash_distance is not None:
        for threshold, contribution in HASH_DISTANCE_POINTS:
            if hash_distance <= threshold:
                signals.append(
                    SimilaritySignal(
                        code="image_hash_match",
                        label="Images are visually close.",
                        contribution=contribution,
                        metadata={"distance": hash_distance, "threshold": threshold},
                    )
                )
                score += contribution
                break

    overlapping_colors = _color_overlap(anchor, peer)
    if overlapping_colors:
        overlap_count = len(overlapping_colors)
        for minimum_overlap, contribution in COLOR_OVERLAP_POINTS:
            if overlap_count >= minimum_overlap:
                signals.append(
                    SimilaritySignal(
                        code="color_overlap",
                        label="Items share overlapping colors.",
                        contribution=contribution,
                        metadata={"overlapping_colors": overlapping_colors},
                    )
                )
                score += contribution
                break

    material = _shared_scalar(anchor.material, peer.material)
    if material is not None:
        signals.append(
            SimilaritySignal(
                code="material_match",
                label="Items share the same material.",
                contribution=MATERIAL_MATCH_POINTS,
                metadata={"material": material},
            )
        )
        score += MATERIAL_MATCH_POINTS

    pattern = _shared_scalar(anchor.pattern, peer.pattern)
    if pattern is not None:
        signals.append(
            SimilaritySignal(
                code="pattern_match",
                label="Items share the same pattern.",
                contribution=PATTERN_MATCH_POINTS,
                metadata={"pattern": pattern},
            )
        )
        score += PATTERN_MATCH_POINTS

    brand = _shared_scalar(anchor.brand, peer.brand)
    if brand is not None:
        signals.append(
            SimilaritySignal(
                code="brand_match",
                label="Items share the same brand.",
                contribution=BRAND_MATCH_POINTS,
                metadata={"brand": brand},
            )
        )
        score += BRAND_MATCH_POINTS

    overlapping_title_tokens = _title_token_overlap(anchor.title, peer.title)
    if overlapping_title_tokens:
        signals.append(
            SimilaritySignal(
                code="title_token_overlap",
                label="Titles share descriptive words.",
                contribution=TITLE_TOKEN_MATCH_POINTS,
                metadata={"tokens": overlapping_title_tokens},
            )
        )
        score += TITLE_TOKEN_MATCH_POINTS

    has_category_mismatch = any(signal.code == "category_mismatch" for signal in signals)
    similarity_type = _classify_similarity(
        score=score,
        hash_distance=hash_distance,
        has_category_mismatch=has_category_mismatch,
    )
    return SimilarityComputation(
        score=score,
        similarity_type=similarity_type,
        signals=signals,
        hash_distance=hash_distance,
        anchor_image_role=anchor.image_role,
        peer_image_role=peer.image_role,
    )


def _classify_similarity(
    *,
    score: float,
    hash_distance: int | None,
    has_category_mismatch: bool,
) -> SimilarityType | None:
    if not has_category_mismatch and hash_distance is not None:
        if (
            hash_distance <= DUPLICATE_HASH_DISTANCE_THRESHOLD
            and score >= DUPLICATE_SCORE_THRESHOLD
        ):
            return SimilarityType.DUPLICATE_CANDIDATE
    if not has_category_mismatch and score >= SIMILAR_SCORE_THRESHOLD:
        return SimilarityType.SIMILAR
    return None


def _hash_distance(anchor_image_bytes: bytes | None, peer_image_bytes: bytes | None) -> int | None:
    anchor_hash = _dhash(anchor_image_bytes)
    peer_hash = _dhash(peer_image_bytes)
    if anchor_hash is None or peer_hash is None:
        return None
    return (anchor_hash ^ peer_hash).bit_count()


def _dhash(image_bytes: bytes | None) -> int | None:
    if image_bytes is None:
        return None
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            grayscale = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            pixels = list(grayscale.getdata())
    except (UnidentifiedImageError, OSError):
        return None

    value = 0
    for row in range(8):
        row_offset = row * 9
        for column in range(8):
            left = pixels[row_offset + column]
            right = pixels[row_offset + column + 1]
            value = (value << 1) | int(left > right)
    return value


def _normalize_scalar(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = collapse_whitespace(value).casefold()
    return normalized or None


def _shared_scalar(left: str | None, right: str | None) -> str | None:
    normalized_left = _normalize_scalar(left)
    normalized_right = _normalize_scalar(right)
    if normalized_left is None or normalized_right is None:
        return None
    if normalized_left != normalized_right:
        return None
    return normalized_left


def _color_overlap(anchor: ComparableItem, peer: ComparableItem) -> list[str]:
    anchor_colors = set(_normalized_colors(anchor))
    peer_colors = set(_normalized_colors(peer))
    overlapping = sorted(anchor_colors & peer_colors)
    return overlapping


def _normalized_colors(item: ComparableItem) -> list[str]:
    colors: list[str] = []
    if item.primary_color is not None:
        normalized_primary = _normalize_scalar(item.primary_color)
        if normalized_primary is not None:
            colors.append(normalized_primary)
    for color in item.secondary_colors or []:
        normalized = _normalize_scalar(color)
        if normalized is None:
            continue
        if normalized not in colors:
            colors.append(normalized)
    return colors


def _title_token_overlap(anchor_title: str | None, peer_title: str | None) -> list[str]:
    anchor_tokens = set(_title_tokens(anchor_title))
    peer_tokens = set(_title_tokens(peer_title))
    return sorted(anchor_tokens & peer_tokens)


def _title_tokens(value: str | None) -> list[str]:
    if value is None:
        return []
    normalized = collapse_whitespace(value).casefold()
    if not normalized:
        return []
    return [token for token in re.findall(r"[a-z0-9]+", normalized) if len(token) > 1]
