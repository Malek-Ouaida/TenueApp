from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.closet.models import ClosetItemFieldState
from app.domains.wear.metadata import (
    MATCHING_FIELD_WEIGHTS,
    build_closet_field_trusts,
    build_closet_metadata_payload,
)
from app.domains.wear.repository import WearRepository


@dataclass(frozen=True)
class WearDetectionInput:
    role: str | None
    normalized_metadata: dict[str, Any]
    field_confidences: dict[str, float | None]
    confidence: float | None
    sort_index: int
    detected_item_id: UUID | None = None


@dataclass(frozen=True)
class WearMatchCandidateResult:
    closet_item_id: UUID
    rank: int
    score: float
    normalized_confidence: float
    match_state: str
    is_exact_match: bool
    explanation_json: dict[str, Any]


@dataclass
class WearDetectionMatchResult:
    detection_key: str
    normalized_metadata: dict[str, Any]
    field_confidences: dict[str, float | None]
    candidates: list[WearMatchCandidateResult]
    exact_match: bool
    match_resolution: dict[str, Any]
    structured_explanation: dict[str, Any]


class WearMatchingService:
    DEFAULT_LIMIT = 2
    VIABILITY_THRESHOLD = 50.0
    EXACT_MATCH_THRESHOLD = 92.0
    EXACT_MARGIN_THRESHOLD = 12.0
    SPARSE_EVIDENCE_SCORE_CAP = 84.0

    DISCRETE_SUBCATEGORY_CATEGORIES = {"bags", "jewelry", "accessories"}
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    STRUCTURAL_CONFIDENCE_THRESHOLD = 0.75
    EXACT_SUPPORT_FIELDS = (
        "attributes",
        "fit_tags",
        "silhouette",
        "material",
        "pattern",
        "secondary_colors",
    )

    COLOR_FAMILY_MAP = {
        "black": "black",
        "white": "light_neutral",
        "gray": "gray",
        "charcoal": "gray",
        "beige": "light_neutral",
        "cream": "light_neutral",
        "taupe": "light_neutral",
        "brown": "brown",
        "camel": "brown",
        "blue": "blue",
        "navy": "blue",
        "light_blue": "blue",
        "denim_blue": "blue",
        "green": "green",
        "olive": "green",
        "sage": "green",
        "red": "red",
        "burgundy": "red",
        "pink": "pink",
        "blush": "pink",
        "purple": "purple",
        "lavender": "purple",
        "yellow": "yellow",
        "mustard": "yellow",
        "orange": "orange",
        "silver": "metallic",
        "gold": "metallic",
        "bronze": "metallic",
        "multicolor": "multicolor",
    }

    FIT_GROUPS = {
        "body_fit": {"oversized", "relaxed", "fitted", "slim", "loose", "boxy", "regular_fit", "bodycon"},
        "leg_shape": {"wide_leg", "straight_leg", "tapered"},
        "rise": {"high_rise", "mid_rise", "low_rise"},
        "length": {"cropped", "full_length", "ankle_length"},
    }
    ATTRIBUTE_GROUPS = {
        "neckline": {
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
        },
        "closure": {"button_front", "zip_front", "open_front", "wrap_closure", "tie_front", "belted"},
        "sleeve": {
            "sleeveless",
            "cap_sleeve",
            "short_sleeve",
            "three_quarter_sleeve",
            "long_sleeve",
            "puff_sleeve",
        },
        "strap": {"racerback", "spaghetti_strap", "wide_strap"},
        "length": {"mini_length", "midi_length", "maxi_length"},
        "outerwear_structure": {"double_breasted", "single_breasted", "hooded"},
        "shoe_toe": {"pointed_toe", "round_toe", "square_toe", "open_toe", "closed_toe"},
        "shoe_heel": {"stiletto_heel", "block_heel", "kitten_heel", "wedge_heel"},
        "bag_structure": {"structured", "soft_structure"},
    }
    SILHOUETTE_GROUPS = {
        "shape": {
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
        }
    }
    SUBCATEGORY_EQUIVALENT_GROUPS = {
        "tops": [
            {"t_shirt", "shirt", "polo"},
            {"tank_top", "camisole", "bodysuit", "knit_top", "vest_top"},
            {"sweater", "sweatshirt", "hoodie"},
        ],
        "bottoms": [
            {"jeans", "trousers"},
            {"joggers", "cargo_pants"},
        ],
        "outerwear": [
            {"jacket", "denim_jacket", "leather_jacket", "bomber_jacket", "rain_jacket"},
            {"coat", "trench_coat", "puffer_jacket"},
        ],
        "shoes": [
            {"heels", "pumps"},
            {"flats", "ballet_flats"},
            {"boots", "ankle_boots", "knee_high_boots"},
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

    def rank_candidates_for_detection(
        self,
        *,
        user_id: UUID,
        detection: WearDetectionInput,
        limit: int = DEFAULT_LIMIT,
    ) -> list[WearMatchCandidateResult]:
        return self.match_detection(user_id=user_id, detection=detection, limit=limit).candidates

    def should_surface_detection(
        self,
        *,
        user_id: UUID,
        detection: WearDetectionInput,
    ) -> bool:
        result = self.match_detection(user_id=user_id, detection=detection, limit=1)
        detected_category = _as_string(detection.normalized_metadata.get("category"))
        return bool(detected_category or result.candidates)

    def match_detection(
        self,
        *,
        user_id: UUID,
        detection: WearDetectionInput,
        limit: int = DEFAULT_LIMIT,
    ) -> WearDetectionMatchResult:
        rows = self.repository.list_active_confirmed_closet_items_with_projections_for_user(user_id=user_id)
        field_states_by_item = self.repository.list_closet_field_states_for_items(
            closet_item_ids=[item.id for item, _ in rows]
        )
        detected_category = _as_string(detection.normalized_metadata.get("category"))
        category_inventory_count = sum(
            1
            for closet_item, projection in rows
            if detected_category
            and _as_string(
                build_closet_metadata_payload(
                    projection=projection,
                    field_states_by_name=field_states_by_item.get(closet_item.id, {}),
                ).get("category")
            )
            == detected_category
        )
        if detected_category and category_inventory_count == 0:
            return self._build_empty_result(
                detection=detection,
                category_inventory_count=0,
                state="no_match",
                reason="no_items_in_detected_category",
            )

        scored_candidates_by_item: dict[UUID, tuple[UUID, float, float, float, dict[str, Any]]] = {}
        for closet_item, projection in rows:
            field_states = field_states_by_item.get(closet_item.id, {})
            closet_metadata = build_closet_metadata_payload(
                projection=projection,
                field_states_by_name=field_states,
            )
            hard_filter = self._evaluate_hard_filters(
                detected_metadata=detection.normalized_metadata,
                field_confidences=detection.field_confidences,
                closet_metadata=closet_metadata,
            )
            if not hard_filter["passed"]:
                continue

            score, field_explanations, penalties = self._score_candidate(
                detected_metadata=detection.normalized_metadata,
                field_confidences=detection.field_confidences,
                detected_confidence=detection.confidence,
                closet_metadata=closet_metadata,
                closet_field_states=field_states,
            )
            support_summary = self._build_exact_support_summary(field_explanations)
            display_score = round(
                self._apply_sparse_evidence_score_cap(
                    score=score,
                    support_summary=support_summary,
                ),
                2,
            )
            normalized_confidence = round(min(1.0, score / 100.0), 4)
            explanation = {
                "hard_filters": hard_filter["outcomes"],
                "per_field": field_explanations,
                "penalties": penalties,
                "category_inventory_count": category_inventory_count,
                "rank_reason": "Passed hard filters and scored on shared metadata.",
                "exact_support": support_summary,
                "ranking_score": round(score, 2),
                "display_score": display_score,
            }
            if score >= self.VIABILITY_THRESHOLD:
                candidate = (
                    closet_item.id,
                    score,
                    display_score,
                    normalized_confidence,
                    explanation,
                )
                current = scored_candidates_by_item.get(closet_item.id)
                if current is None or self._candidate_sort_key(candidate) < self._candidate_sort_key(current):
                    scored_candidates_by_item[closet_item.id] = candidate

        scored_candidates = sorted(
            scored_candidates_by_item.values(),
            key=self._candidate_sort_key,
        )
        exact_gate_candidates = scored_candidates[: self.DEFAULT_LIMIT]
        top_candidates = scored_candidates[:limit]
        exact_match = self._is_exact_match(
            detected_metadata=detection.normalized_metadata,
            field_confidences=detection.field_confidences,
            top_candidates=exact_gate_candidates,
        )

        candidates: list[WearMatchCandidateResult] = []
        for index, (closet_item_id, _ranking_score, display_score, normalized_confidence, explanation) in enumerate(
            top_candidates
        ):
            candidates.append(
                WearMatchCandidateResult(
                    closet_item_id=closet_item_id,
                    rank=index + 1,
                    score=display_score,
                    normalized_confidence=normalized_confidence,
                    match_state="exact_match" if exact_match and index == 0 else "candidate",
                    is_exact_match=bool(exact_match and index == 0),
                    explanation_json={
                        **explanation,
                        "match_state": "exact_match" if exact_match and index == 0 else "candidate",
                        "is_exact_match": bool(exact_match and index == 0),
                    },
                )
            )

        if not candidates:
            return self._build_empty_result(
                detection=detection,
                category_inventory_count=category_inventory_count,
                state="no_match",
                reason="no_viable_candidates",
            )

        return WearDetectionMatchResult(
            detection_key=_detection_key(detection),
            normalized_metadata=detection.normalized_metadata,
            field_confidences=detection.field_confidences,
            candidates=candidates,
            exact_match=exact_match,
            match_resolution={
                "state": "exact_match" if exact_match else "candidate_only",
                "closet_item_id": str(candidates[0].closet_item_id) if exact_match else None,
                "reason": "passed_exact_gate" if exact_match else "review_required",
            },
            structured_explanation={
                "category_inventory_count": category_inventory_count,
                "reason": "exact_match" if exact_match else "top_candidates_returned",
                "returned_candidate_ids": [str(candidate.closet_item_id) for candidate in candidates],
            },
        )

    def _candidate_sort_key(
        self,
        candidate: tuple[UUID, float, float, float, dict[str, Any]],
    ) -> tuple[float, float, float, str]:
        return (-candidate[1], -candidate[2], -candidate[3], str(candidate[0]))

    def resolve_exact_match_collisions(
        self,
        *,
        results: list[WearDetectionMatchResult],
    ) -> list[WearDetectionMatchResult]:
        by_closet_item: dict[UUID, list[WearDetectionMatchResult]] = defaultdict(list)
        for result in results:
            if not result.exact_match or not result.candidates:
                continue
            by_closet_item[result.candidates[0].closet_item_id].append(result)

        for closet_item_id, conflicted_results in by_closet_item.items():
            if len(conflicted_results) <= 1:
                continue
            conflicted_results.sort(
                key=lambda result: (
                    -result.candidates[0].score,
                    -_score_gap(result.candidates),
                    result.normalized_metadata.get("category") or "",
                    result.detection_key,
                )
            )
            winner = conflicted_results[0]
            winner.match_resolution = {
                "state": "exact_match",
                "closet_item_id": str(closet_item_id),
                "reason": "won_collision_resolution",
            }
            winner.structured_explanation = {
                **winner.structured_explanation,
                "collision": {"state": "won", "closet_item_id": str(closet_item_id)},
            }

            for loser in conflicted_results[1:]:
                loser.exact_match = False
                loser.match_resolution = {
                    "state": "collision_rejected",
                    "closet_item_id": str(closet_item_id),
                    "reason": "closet_item_already_claimed_by_stronger_exact_match",
                    "winning_detection_key": winner.detection_key,
                }
                loser.structured_explanation = {
                    **loser.structured_explanation,
                    "collision": {
                        "state": "lost",
                        "closet_item_id": str(closet_item_id),
                        "winning_detection_key": winner.detection_key,
                    },
                }
                updated_candidates: list[WearMatchCandidateResult] = []
                for index, candidate in enumerate(loser.candidates):
                    if index == 0 and candidate.closet_item_id == closet_item_id:
                        updated_candidates.append(
                            WearMatchCandidateResult(
                                closet_item_id=candidate.closet_item_id,
                                rank=candidate.rank,
                                score=candidate.score,
                                normalized_confidence=candidate.normalized_confidence,
                                match_state="rejected",
                                is_exact_match=False,
                                explanation_json={
                                    **candidate.explanation_json,
                                    "match_state": "rejected",
                                    "is_exact_match": False,
                                    "collision": {
                                        "state": "lost",
                                        "winning_detection_key": winner.detection_key,
                                    },
                                },
                            )
                        )
                        continue
                    updated_candidates.append(candidate)
                loser.candidates = updated_candidates
        return results

    def _build_empty_result(
        self,
        *,
        detection: WearDetectionInput,
        category_inventory_count: int,
        state: str,
        reason: str,
    ) -> WearDetectionMatchResult:
        return WearDetectionMatchResult(
            detection_key=_detection_key(detection),
            normalized_metadata=detection.normalized_metadata,
            field_confidences=detection.field_confidences,
            candidates=[],
            exact_match=False,
            match_resolution={
                "state": state,
                "closet_item_id": None,
                "reason": reason,
            },
            structured_explanation={
                "category_inventory_count": category_inventory_count,
                "reason": reason,
                "returned_candidate_ids": [],
            },
        )

    def _evaluate_hard_filters(
        self,
        *,
        detected_metadata: dict[str, Any],
        field_confidences: dict[str, float | None],
        closet_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        outcomes: list[dict[str, Any]] = []
        detected_category = _as_string(detected_metadata.get("category"))
        closet_category = _as_string(closet_metadata.get("category"))
        if detected_category and closet_category and detected_category != closet_category:
            outcomes.append({"field": "category", "state": "reject", "reason": "category_mismatch"})
            return {"passed": False, "outcomes": outcomes}
        outcomes.append({"field": "category", "state": "pass"})

        detected_subcategory = _as_string(detected_metadata.get("subcategory"))
        closet_subcategory = _as_string(closet_metadata.get("subcategory"))
        if (
            detected_category in self.DISCRETE_SUBCATEGORY_CATEGORIES
            and detected_subcategory
            and closet_subcategory
            and detected_subcategory != closet_subcategory
        ):
            outcomes.append(
                {
                    "field": "subcategory",
                    "state": "reject",
                    "reason": "impossible_subcategory_mismatch",
                }
            )
            return {"passed": False, "outcomes": outcomes}
        outcomes.append({"field": "subcategory", "state": "pass"})

        primary_color_confidence = field_confidences.get("primary_color") or 0.0
        detected_primary_color = _as_string(detected_metadata.get("primary_color"))
        closet_primary_color = _as_string(closet_metadata.get("primary_color"))
        if (
            primary_color_confidence >= self.HIGH_CONFIDENCE_THRESHOLD
            and detected_primary_color
            and closet_primary_color
            and not self._compatible_color_family(detected_primary_color, closet_primary_color)
        ):
            outcomes.append(
                {
                    "field": "primary_color",
                    "state": "reject",
                    "reason": "high_confidence_color_contradiction",
                }
            )
            return {"passed": False, "outcomes": outcomes}
        outcomes.append({"field": "primary_color", "state": "pass"})

        contradictions = self._structural_contradictions(
            detected_metadata=detected_metadata,
            field_confidences=field_confidences,
            closet_metadata=closet_metadata,
        )
        if contradictions:
            outcomes.append(
                {
                    "field": "structure",
                    "state": "reject",
                    "reason": "strong_structural_contradiction",
                    "details": contradictions,
                }
            )
            return {"passed": False, "outcomes": outcomes}
        outcomes.append({"field": "structure", "state": "pass"})
        return {"passed": True, "outcomes": outcomes}

    def _score_candidate(
        self,
        *,
        detected_metadata: dict[str, Any],
        field_confidences: dict[str, float | None],
        detected_confidence: float | None,
        closet_metadata: dict[str, Any],
        closet_field_states: dict[str, ClosetItemFieldState],
    ) -> tuple[float, dict[str, Any], list[dict[str, Any]]]:
        closet_trusts = build_closet_field_trusts(closet_field_states)
        raw_score = 0.0
        available_total = 0.0
        per_field: dict[str, Any] = {}
        raw_penalties: list[dict[str, Any]] = []
        detected_category = _as_string(detected_metadata.get("category"))
        closet_category = _as_string(closet_metadata.get("category"))
        per_field["category"] = {
            "weight": 0,
            "status": "matched" if detected_category and detected_category == closet_category else "gate",
            "match_ratio": 1.0 if detected_category and detected_category == closet_category else 0.0,
            "contribution": 0.0,
            "detected_value": detected_category,
            "closet_value": closet_category,
        }
        for field_name, weight in MATCHING_FIELD_WEIGHTS.items():
            detected_value = detected_metadata.get(field_name)
            closet_value = closet_metadata.get(field_name)
            detector_factor = _detector_factor(
                field_confidences.get(field_name),
                detected_confidence,
            )
            closet_factor = closet_trusts.get(field_name, 0.55)
            if not _has_value(detected_value) or not _has_value(closet_value):
                per_field[field_name] = {
                    "weight": weight,
                    "status": "missing",
                    "contribution": 0.0,
                    "detector_confidence": field_confidences.get(field_name),
                    "closet_trust": closet_factor,
                    "detected_value": detected_value,
                    "closet_value": closet_value,
                }
                continue

            match_ratio = self._field_match_ratio(
                field_name=field_name,
                detected_category=_as_string(detected_metadata.get("category")),
                detected_value=detected_value,
                closet_value=closet_value,
            )
            raw_available = weight * detector_factor * closet_factor
            raw_contribution = raw_available * match_ratio
            available_total += raw_available
            raw_score += raw_contribution
            per_field[field_name] = {
                "weight": weight,
                "status": "matched" if match_ratio > 0 else "mismatch",
                "match_ratio": round(match_ratio, 4),
                "contribution": raw_contribution,
                "available_points": raw_available,
                "detector_confidence": field_confidences.get(field_name),
                "closet_trust": closet_factor,
                "detected_value": detected_value,
                "closet_value": closet_value,
            }

            penalty = self._field_penalty(
                field_name=field_name,
                weight=weight,
                detected_value=detected_value,
                closet_value=closet_value,
                detector_factor=detector_factor,
                match_ratio=match_ratio,
                field_confidence=field_confidences.get(field_name),
            )
            if penalty is not None:
                raw_penalties.append(penalty)

        scale = 100.0 / available_total if available_total > 0 else 0.0
        penalties: list[dict[str, Any]] = []
        score = raw_score * scale

        for field_name, explanation in per_field.items():
            if not isinstance(explanation, dict):
                continue
            if "contribution" in explanation and isinstance(explanation["contribution"], (int, float)):
                explanation["contribution"] = round(float(explanation["contribution"]) * scale, 4)
            if "available_points" in explanation and isinstance(explanation["available_points"], (int, float)):
                explanation["available_points"] = round(float(explanation["available_points"]) * scale, 4)

        for penalty in raw_penalties:
            scaled_points = round(penalty["points"] * scale, 2) if scale > 0 else 0.0
            penalties.append({**penalty, "points": scaled_points})
            score -= scaled_points

        return round(max(0.0, min(100.0, score)), 2), per_field, penalties

    def _field_match_ratio(
        self,
        *,
        field_name: str,
        detected_category: str | None,
        detected_value: Any,
        closet_value: Any,
    ) -> float:
        if field_name in {"subcategory", "primary_color"}:
            detected = _as_string(detected_value)
            closet = _as_string(closet_value)
            if not detected or not closet:
                return 0.0
            if detected == closet:
                return 1.0
            if field_name == "primary_color" and self._compatible_color_family(detected, closet):
                return 0.65
            if field_name == "subcategory" and self._subcategory_equivalent(
                category=detected_category,
                detected_subcategory=detected,
                closet_subcategory=closet,
            ):
                return 0.45
            return 0.0

        if field_name in {"material", "pattern", "silhouette", "formality", "warmth", "coverage", "statement_level", "versatility", "brand"}:
            return 1.0 if _as_string(detected_value) == _as_string(closet_value) else 0.0

        detected_values = _as_string_list(detected_value)
        closet_values = _as_string_list(closet_value)
        if not detected_values or not closet_values:
            return 0.0
        overlap = len(set(detected_values) & set(closet_values))
        if overlap == 0:
            return 0.0
        return overlap / max(len(set(detected_values)), len(set(closet_values)))

    def _field_penalty(
        self,
        *,
        field_name: str,
        weight: int,
        detected_value: Any,
        closet_value: Any,
        detector_factor: float,
        match_ratio: float,
        field_confidence: float | None,
    ) -> dict[str, Any] | None:
        if match_ratio > 0:
            return None
        confidence = field_confidence or 0.0
        if confidence < 0.7 and field_name not in {"subcategory", "primary_color"}:
            return None

        base_penalty = {
            "subcategory": 4.0,
            "primary_color": 5.0,
        }.get(field_name, max(1.0, round(weight * 0.18, 2)))
        points = round(base_penalty * detector_factor, 2)
        return {"field": field_name, "points": points, "reason": "explicit_mismatch"}

    def _is_exact_match(
        self,
        *,
        detected_metadata: dict[str, Any],
        field_confidences: dict[str, float | None],
        top_candidates: list[tuple[UUID, float, float, float, dict[str, Any]]],
    ) -> bool:
        if not top_candidates:
            return False
        best = top_candidates[0]
        if best[1] < self.EXACT_MATCH_THRESHOLD:
            return False
        detected_category = _as_string(detected_metadata.get("category"))
        detected_subcategory = _as_string(detected_metadata.get("subcategory"))
        if not detected_category or not detected_subcategory:
            return False
        best_field_explanations = best[4].get("per_field", {})
        if best_field_explanations.get("category", {}).get("match_ratio") != 1.0:
            return False
        if best_field_explanations.get("subcategory", {}).get("match_ratio") != 1.0:
            return False
        primary_color = _as_string(detected_metadata.get("primary_color"))
        if primary_color is None:
            return False
        candidate_primary_color = _extract_candidate_field_value(best_field_explanations, "primary_color")
        if candidate_primary_color is None:
            return False
        primary_color_explanation = best_field_explanations.get("primary_color", {})
        if not isinstance(primary_color_explanation, dict):
            return False
        if primary_color_explanation.get("status") == "missing":
            return False
        if primary_color_explanation.get("match_ratio") != 1.0:
            return False
        support_summary = self._build_exact_support_summary(best_field_explanations)
        if not support_summary["passes"]:
            return False
        if len(top_candidates) == 1:
            return True
        return (best[1] - top_candidates[1][1]) >= self.EXACT_MARGIN_THRESHOLD

    def _build_exact_support_summary(self, per_field: dict[str, Any]) -> dict[str, Any]:
        closet_rich_fields: list[str] = []
        matched_fields: list[str] = []
        for field_name in self.EXACT_SUPPORT_FIELDS:
            payload = per_field.get(field_name)
            if not isinstance(payload, dict):
                continue
            if not _has_value(payload.get("closet_value")):
                continue
            closet_rich_fields.append(field_name)
            match_ratio = payload.get("match_ratio")
            if isinstance(match_ratio, (int, float)) and float(match_ratio) > 0:
                matched_fields.append(field_name)

        required_matches = 0 if not closet_rich_fields else max(1, (len(closet_rich_fields) + 1) // 2)
        return {
            "closet_rich_fields": closet_rich_fields,
            "matched_fields": matched_fields,
            "required_matches": required_matches,
            "passes": len(matched_fields) >= required_matches,
        }

    def _apply_sparse_evidence_score_cap(
        self,
        *,
        score: float,
        support_summary: dict[str, Any],
    ) -> float:
        if not support_summary.get("closet_rich_fields"):
            return score
        if support_summary.get("passes"):
            return score
        return min(score, self.SPARSE_EVIDENCE_SCORE_CAP)

    def _structural_contradictions(
        self,
        *,
        detected_metadata: dict[str, Any],
        field_confidences: dict[str, float | None],
        closet_metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        contradictions: list[dict[str, Any]] = []
        if (field_confidences.get("fit_tags") or 0.0) >= self.STRUCTURAL_CONFIDENCE_THRESHOLD:
            contradiction = _exclusive_group_contradiction(
                detected_values=_as_string_list(detected_metadata.get("fit_tags")),
                closet_values=_as_string_list(closet_metadata.get("fit_tags")),
                groups=self.FIT_GROUPS,
            )
            if contradiction is not None:
                contradictions.append({"field": "fit_tags", **contradiction})
        if (field_confidences.get("attributes") or 0.0) >= self.STRUCTURAL_CONFIDENCE_THRESHOLD:
            contradiction = _exclusive_group_contradiction(
                detected_values=_as_string_list(detected_metadata.get("attributes")),
                closet_values=_as_string_list(closet_metadata.get("attributes")),
                groups=self.ATTRIBUTE_GROUPS,
            )
            if contradiction is not None:
                contradictions.append({"field": "attributes", **contradiction})
        if (field_confidences.get("silhouette") or 0.0) >= self.STRUCTURAL_CONFIDENCE_THRESHOLD:
            detected_silhouette = _as_string(detected_metadata.get("silhouette"))
            closet_silhouette = _as_string(closet_metadata.get("silhouette"))
            contradiction = _exclusive_group_contradiction(
                detected_values=[detected_silhouette] if detected_silhouette else [],
                closet_values=[closet_silhouette] if closet_silhouette else [],
                groups=self.SILHOUETTE_GROUPS,
            )
            if contradiction is not None:
                contradictions.append({"field": "silhouette", **contradiction})
        return contradictions

    def _compatible_color_family(self, left: str, right: str) -> bool:
        return self.COLOR_FAMILY_MAP.get(left) == self.COLOR_FAMILY_MAP.get(right)

    def _subcategory_equivalent(
        self,
        *,
        category: str | None,
        detected_subcategory: str,
        closet_subcategory: str,
    ) -> bool:
        if detected_subcategory == closet_subcategory:
            return True
        if category is None:
            return False
        for group in self.SUBCATEGORY_EQUIVALENT_GROUPS.get(category, []):
            if detected_subcategory in group and closet_subcategory in group:
                return True
        return False


def _detection_key(detection: WearDetectionInput) -> str:
    if detection.detected_item_id is not None:
        return str(detection.detected_item_id)
    return f"sort:{detection.sort_index}"


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return True


def _as_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return []


def _detector_factor(field_confidence: float | None, detected_confidence: float | None) -> float:
    if field_confidence is not None:
        return 0.35 + min(1.0, max(0.0, field_confidence)) * 0.65
    if detected_confidence is not None:
        return 0.3 + min(1.0, max(0.0, detected_confidence)) * 0.55
    return 0.6


def _exclusive_group_contradiction(
    *,
    detected_values: list[str],
    closet_values: list[str],
    groups: dict[str, set[str]],
) -> dict[str, Any] | None:
    if not detected_values or not closet_values:
        return None
    detected_set = set(detected_values)
    closet_set = set(closet_values)
    for group_name, group_values in groups.items():
        detected_group_values = sorted(detected_set & group_values)
        closet_group_values = sorted(closet_set & group_values)
        if detected_group_values and closet_group_values and set(detected_group_values).isdisjoint(
            closet_group_values
        ):
            return {
                "group": group_name,
                "detected_values": detected_group_values,
                "closet_values": closet_group_values,
            }
    return None


def _score_gap(candidates: list[WearMatchCandidateResult]) -> float:
    if len(candidates) < 2:
        return candidates[0].score if candidates else 0.0
    return candidates[0].score - candidates[1].score


def _extract_candidate_field_value(per_field: dict[str, Any], field_name: str) -> str | None:
    field_payload = per_field.get(field_name)
    if not isinstance(field_payload, dict):
        return None
    closet_value = field_payload.get("closet_value")
    return _as_string(closet_value)
