from __future__ import annotations

from typing import Any

from app.domains.closet.models import ApplicabilityState, ClosetItemFieldState, FieldReviewState, FieldSource
from app.domains.closet.normalization import derive_category_for_subcategory, normalize_field_value
from app.domains.closet.taxonomy import LIST_FIELD_NAMES, SUPPORTED_FIELD_ORDER

MATCHING_FIELD_WEIGHTS: dict[str, int] = {
    "subcategory": 20,
    "primary_color": 15,
    "secondary_colors": 5,
    "material": 6,
    "pattern": 6,
    "style_tags": 3,
    "fit_tags": 8,
    "occasion_tags": 4,
    "season_tags": 3,
    "silhouette": 6,
    "attributes": 10,
    "formality": 4,
    "warmth": 3,
    "coverage": 3,
    "statement_level": 2,
    "versatility": 1,
    "brand": 1,
}
MATCHING_EXCLUDED_FIELDS = {"title"}


def empty_metadata() -> dict[str, Any]:
    return {field_name: None for field_name in SUPPORTED_FIELD_ORDER}


def empty_field_confidences() -> dict[str, float | None]:
    return {field_name: None for field_name in SUPPORTED_FIELD_ORDER}


def normalize_detected_metadata_fields(
    raw_fields: dict[str, dict[str, Any] | Any],
) -> tuple[dict[str, Any], dict[str, float | None], dict[str, str]]:
    raw_fields = dict(raw_fields)
    metadata = empty_metadata()
    field_confidences = empty_field_confidences()
    notes: dict[str, str] = {}

    colors_field = raw_fields.get("colors")
    if colors_field is not None:
        expanded_colors = _expand_colors_alias(colors_field)
        if "primary_color" not in raw_fields:
            raw_fields["primary_color"] = expanded_colors.get("primary_color")
        if "secondary_colors" not in raw_fields and "secondary_colors" in expanded_colors:
            raw_fields["secondary_colors"] = expanded_colors.get("secondary_colors")

    for field_name in SUPPORTED_FIELD_ORDER:
        raw_field = raw_fields.get(field_name)
        applicability_state, confidence, raw_value, note = _extract_field_payload(
            field_name=field_name,
            raw_field=raw_field,
        )
        normalized = normalize_field_value(
            field_name=field_name,
            raw_value=raw_value,
            applicability_state=applicability_state,
            confidence=confidence,
        )
        field_confidences[field_name] = normalized.confidence
        metadata[field_name] = (
            normalized.canonical_value if normalized.applicability_state == ApplicabilityState.VALUE else None
        )
        merged_note = " ".join(
            part
            for part in [note, " ".join(normalized.notes).strip()]
            if isinstance(part, str) and part.strip()
        ).strip()
        if merged_note:
            notes[field_name] = merged_note

    subcategory = metadata.get("subcategory")
    category = metadata.get("category")
    if isinstance(subcategory, str):
        derived_category = derive_category_for_subcategory(subcategory)
        if derived_category is not None:
            metadata["category"] = derived_category
            if field_confidences.get("category") is None:
                field_confidences["category"] = field_confidences.get("subcategory")
    if isinstance(metadata.get("category"), str) and isinstance(metadata.get("subcategory"), str):
        if derive_category_for_subcategory(str(metadata["subcategory"])) != metadata["category"]:
            metadata["subcategory"] = None

    return metadata, field_confidences, notes


def build_detected_legacy_columns(metadata: dict[str, Any]) -> dict[str, Any]:
    primary_color = metadata.get("primary_color")
    secondary_colors = metadata.get("secondary_colors")
    predicted_colors: list[str] = []
    if isinstance(primary_color, str) and primary_color:
        predicted_colors.append(primary_color)
    if isinstance(secondary_colors, list):
        predicted_colors.extend(str(value) for value in secondary_colors if isinstance(value, str) and value)
    return {
        "predicted_category": metadata.get("category"),
        "predicted_subcategory": metadata.get("subcategory"),
        "predicted_colors_json": predicted_colors or None,
        "predicted_material": metadata.get("material"),
        "predicted_pattern": metadata.get("pattern"),
        "predicted_fit_tags_json": metadata.get("fit_tags") or None,
        "predicted_silhouette": metadata.get("silhouette"),
        "predicted_attributes_json": metadata.get("attributes") or None,
    }


def build_closet_metadata_payload(
    *,
    projection: object,
    field_states_by_name: dict[str, ClosetItemFieldState] | None = None,
) -> dict[str, Any]:
    field_states_by_name = field_states_by_name or {}
    metadata = empty_metadata()
    for field_name in SUPPORTED_FIELD_ORDER:
        if field_name == "secondary_colors":
            value = getattr(projection, "secondary_colors", None)
            metadata[field_name] = list(value or []) or None
            continue
        value = getattr(projection, field_name, None)
        if isinstance(value, list):
            metadata[field_name] = list(value) or None
        else:
            metadata[field_name] = value

    primary_state = field_states_by_name.get("primary_color")
    secondary_state = field_states_by_name.get("secondary_colors")
    legacy_color_state = field_states_by_name.get("colors")
    if metadata["primary_color"] is None and legacy_color_state is not None:
        legacy_colors = _extract_confirmed_list_value(legacy_color_state)
        if legacy_colors:
            metadata["primary_color"] = legacy_colors[0]
            metadata["secondary_colors"] = legacy_colors[1:] or None
    elif metadata["secondary_colors"] is None and legacy_color_state is not None and secondary_state is None:
        legacy_colors = _extract_confirmed_list_value(legacy_color_state)
        metadata["secondary_colors"] = legacy_colors[1:] or None

    if primary_state is not None:
        primary_value = _extract_confirmed_scalar_value(primary_state)
        metadata["primary_color"] = primary_value
    if secondary_state is not None:
        secondary_value = _extract_confirmed_list_value(secondary_state)
        metadata["secondary_colors"] = secondary_value or None

    for field_name in SUPPORTED_FIELD_ORDER:
        metadata[field_name] = _normalize_closet_metadata_value(
            field_name=field_name,
            raw_value=metadata[field_name],
        )

    subcategory = metadata.get("subcategory")
    if isinstance(subcategory, str):
        derived_category = derive_category_for_subcategory(subcategory)
        if derived_category is not None:
            metadata["category"] = derived_category
    if isinstance(metadata.get("category"), str) and isinstance(metadata.get("subcategory"), str):
        if derive_category_for_subcategory(str(metadata["subcategory"])) != metadata["category"]:
            metadata["subcategory"] = None
    return metadata


def build_closet_field_trusts(
    field_states_by_name: dict[str, ClosetItemFieldState] | None,
) -> dict[str, float]:
    field_states_by_name = field_states_by_name or {}
    trusts = {field_name: 0.55 for field_name in SUPPORTED_FIELD_ORDER}
    for field_name in SUPPORTED_FIELD_ORDER:
        field_state = field_states_by_name.get(field_name)
        if field_state is None and field_name in {"primary_color", "secondary_colors"}:
            field_state = field_states_by_name.get("colors")
        trusts[field_name] = _field_trust(field_state)
    return trusts


def _expand_colors_alias(raw_field: dict[str, Any] | Any) -> dict[str, dict[str, Any]]:
    payload = raw_field if isinstance(raw_field, dict) else {"values": raw_field}
    applicability_state = payload.get("applicability_state")
    confidence = payload.get("confidence")
    notes = payload.get("notes")
    raw_values = payload.get("values", payload.get("value"))
    values: list[str] = []
    if isinstance(raw_values, str):
        stripped = raw_values.strip()
        if stripped:
            values = [stripped]
    elif isinstance(raw_values, list):
        values = [value.strip() for value in raw_values if isinstance(value, str) and value.strip()]

    expanded: dict[str, dict[str, Any]] = {}
    if values:
        expanded["primary_color"] = {
            "value": values[0],
            "confidence": confidence,
            "applicability_state": applicability_state,
            "notes": notes,
        }
    if len(values) > 1:
        expanded["secondary_colors"] = {
            "values": values[1:],
            "confidence": confidence,
            "applicability_state": applicability_state,
            "notes": notes,
        }
    elif applicability_state in {ApplicabilityState.UNKNOWN.value, ApplicabilityState.NOT_APPLICABLE.value}:
        expanded["secondary_colors"] = {
            "values": None,
            "confidence": confidence,
            "applicability_state": applicability_state,
            "notes": notes,
        }
    return expanded


def _extract_field_payload(
    *,
    field_name: str,
    raw_field: dict[str, Any] | Any,
) -> tuple[ApplicabilityState, float | None, Any, str | None]:
    if raw_field is None:
        return ApplicabilityState.UNKNOWN, None, None, None
    payload = raw_field if isinstance(raw_field, dict) else {"value": raw_field}
    raw_applicability = payload.get("applicability_state")
    applicability_state = ApplicabilityState.UNKNOWN
    if isinstance(raw_applicability, ApplicabilityState):
        applicability_state = raw_applicability
    elif isinstance(raw_applicability, str):
        normalized = raw_applicability.strip().lower()
        if normalized == ApplicabilityState.VALUE.value:
            applicability_state = ApplicabilityState.VALUE
        elif normalized == ApplicabilityState.NOT_APPLICABLE.value:
            applicability_state = ApplicabilityState.NOT_APPLICABLE
    elif payload.get("value") is not None or payload.get("values") is not None:
        applicability_state = ApplicabilityState.VALUE

    confidence = None
    raw_confidence = payload.get("confidence")
    if isinstance(raw_confidence, (int, float)):
        confidence = max(0.0, min(1.0, float(raw_confidence)))

    raw_value = payload.get("values") if field_name in LIST_FIELD_NAMES else payload.get("value")
    if field_name in LIST_FIELD_NAMES and raw_value is None:
        raw_value = payload.get("value")
    if field_name not in LIST_FIELD_NAMES and raw_value is None:
        raw_value = payload.get("values")

    note = payload.get("notes")
    if isinstance(note, list):
        note = " ".join(str(part).strip() for part in note if str(part).strip())
    elif note is not None and not isinstance(note, str):
        note = str(note)
    note = note.strip() if isinstance(note, str) else None
    return applicability_state, confidence, raw_value, note


def _extract_confirmed_scalar_value(field_state: ClosetItemFieldState | None) -> str | None:
    if not _is_confirmed_field_state(field_state):
        return None
    assert field_state is not None
    value = field_state.canonical_value
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _extract_confirmed_list_value(field_state: ClosetItemFieldState | None) -> list[str]:
    if not _is_confirmed_field_state(field_state):
        return []
    assert field_state is not None
    value = field_state.canonical_value
    if isinstance(value, list):
        return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return []


def _normalize_closet_metadata_value(*, field_name: str, raw_value: Any) -> Any:
    if raw_value is None:
        return None

    normalized = normalize_field_value(
        field_name=field_name,
        raw_value=raw_value,
        applicability_state=ApplicabilityState.VALUE,
        confidence=None,
    )
    if normalized.applicability_state != ApplicabilityState.VALUE:
        return None

    canonical_value = normalized.canonical_value
    if isinstance(canonical_value, list):
        return canonical_value or None
    return canonical_value


def _field_trust(field_state: ClosetItemFieldState | None) -> float:
    if field_state is None:
        return 0.55
    if field_state.source == FieldSource.USER:
        return 1.0
    if field_state.review_state in {FieldReviewState.USER_CONFIRMED, FieldReviewState.USER_EDITED}:
        return 1.0
    if field_state.source == FieldSource.PROVIDER:
        base = 0.72
        if field_state.confidence is not None:
            base += min(0.18, max(0.0, float(field_state.confidence)) * 0.18)
        return min(0.9, base)
    return 0.55


def _is_confirmed_field_state(field_state: ClosetItemFieldState | None) -> bool:
    if field_state is None:
        return False
    if field_state.applicability_state != ApplicabilityState.VALUE:
        return False
    if field_state.source == FieldSource.USER:
        return True
    return field_state.review_state in {FieldReviewState.USER_CONFIRMED, FieldReviewState.USER_EDITED}
