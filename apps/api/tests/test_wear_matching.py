from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_closet_browse import create_normalized_review_item_for_user
from test_closet_browse import register_and_get_headers
from test_wear_logs import build_raw_fields, create_confirmed_item

from app.core.storage import InMemoryStorageClient
from app.domains.closet.models import ApplicabilityState, FieldReviewState, FieldSource
from app.domains.closet.normalization import normalize_field_value
from app.domains.closet.repository import ClosetRepository
from app.domains.closet.taxonomy import TAXONOMY_VERSION
from app.domains.wear.matching_service import WearDetectionInput, WearMatchingService
from app.domains.wear.metadata import empty_field_confidences, empty_metadata, normalize_detected_metadata_fields
from app.domains.wear.repository import WearRepository


def build_detection_input(
    *,
    role: str | None,
    metadata_values: dict[str, Any],
    field_confidences: dict[str, float | None] | None = None,
    confidence: float | None = 0.95,
    sort_index: int = 0,
) -> WearDetectionInput:
    metadata = empty_metadata()
    metadata.update(metadata_values)
    confidences = empty_field_confidences()
    if field_confidences is not None:
        confidences.update(field_confidences)
    return WearDetectionInput(
        role=role,
        normalized_metadata=metadata,
        field_confidences=confidences,
        confidence=confidence,
        sort_index=sort_index,
    )


def build_matching_service(db_session: Session) -> WearMatchingService:
    return WearMatchingService(
        session=db_session,
        repository=WearRepository(db_session),
    )


def set_confirmed_field_state(
    db_session: Session,
    *,
    item_id,
    field_name: str,
    canonical_value: Any,
) -> None:
    closet_repository = ClosetRepository(db_session)
    item = closet_repository.get_item(item_id=item_id)
    assert item is not None
    closet_repository.upsert_field_state(
        closet_item_id=item_id,
        field_name=field_name,
        canonical_value=canonical_value,
        source=FieldSource.USER,
        confidence=1.0,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
        taxonomy_version=TAXONOMY_VERSION,
    )
    closet_repository.upsert_metadata_projection(
        item=item,
        taxonomy_version=TAXONOMY_VERSION,
    )
    db_session.commit()


def test_match_detection_returns_exact_match_with_explanations(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-exact@example.com")
    closet_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Exact navy tee",
        key_prefix="wear-match-exact",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=closet_item_id)
    assert closet_item is not None

    result = build_matching_service(db_session).match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="top",
            metadata_values={
                "category": "tops",
                "subcategory": "t_shirt",
                "primary_color": "navy",
            },
            field_confidences={
                "category": 0.99,
                "subcategory": 0.98,
                "primary_color": 0.97,
            },
        ),
    )

    assert result.exact_match is True
    assert result.match_resolution["state"] == "exact_match"
    assert len(result.candidates) == 1
    assert result.candidates[0].closet_item_id == closet_item_id
    assert result.candidates[0].is_exact_match is True
    assert result.candidates[0].match_state == "exact_match"
    assert result.candidates[0].score >= 92
    assert "per_field" in result.candidates[0].explanation_json


def test_match_detection_returns_no_match_when_category_inventory_is_empty(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-category-empty@example.com")
    closet_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Only top",
        key_prefix="wear-match-empty",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=closet_item_id)
    assert closet_item is not None

    result = build_matching_service(db_session).match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="footwear",
            metadata_values={
                "category": "shoes",
                "subcategory": "sneakers",
                "primary_color": "black",
            },
            field_confidences={
                "category": 0.99,
                "subcategory": 0.92,
                "primary_color": 0.9,
            },
        ),
    )

    assert result.exact_match is False
    assert result.candidates == []
    assert result.match_resolution["state"] == "no_match"
    assert result.match_resolution["reason"] == "no_items_in_detected_category"


def test_match_detection_returns_top_two_candidates_and_ignores_title(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-top-two@example.com")
    first_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="First navy tee",
        key_prefix="wear-match-two-a",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    second_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Second navy tee",
        key_prefix="wear-match-two-b",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=first_item_id)
    assert closet_item is not None
    service = build_matching_service(db_session)

    base_detection = build_detection_input(
        role="top",
        metadata_values={
            "category": "tops",
            "subcategory": "t_shirt",
        },
        field_confidences={
            "category": 0.97,
            "subcategory": 0.95,
        },
    )
    titled_detection = build_detection_input(
        role="top",
        metadata_values={
            "category": "tops",
            "subcategory": "t_shirt",
            "title": "Second navy tee",
        },
        field_confidences={
            "category": 0.97,
            "subcategory": 0.95,
        },
    )

    untitled_result = service.match_detection(user_id=closet_item.user_id, detection=base_detection)
    titled_result = service.match_detection(user_id=closet_item.user_id, detection=titled_detection)

    assert untitled_result.exact_match is False
    assert len(untitled_result.candidates) == 2
    assert {candidate.closet_item_id for candidate in untitled_result.candidates} == {
        first_item_id,
        second_item_id,
    }
    assert [candidate.closet_item_id for candidate in untitled_result.candidates] == [
        candidate.closet_item_id for candidate in titled_result.candidates
    ]
    assert [candidate.score for candidate in untitled_result.candidates] == [
        candidate.score for candidate in titled_result.candidates
    ]


def test_match_detection_rejects_high_confidence_structural_conflicts(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-structure@example.com")
    closet_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Long sleeve tee",
        key_prefix="wear-match-structure",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    set_confirmed_field_state(
        db_session,
        item_id=closet_item_id,
        field_name="attributes",
        canonical_value=["long_sleeve"],
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=closet_item_id)
    assert closet_item is not None

    result = build_matching_service(db_session).match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="top",
            metadata_values={
                "category": "tops",
                "subcategory": "t_shirt",
                "primary_color": "navy",
                "attributes": ["short_sleeve"],
            },
            field_confidences={
                "category": 0.98,
                "subcategory": 0.97,
                "primary_color": 0.95,
                "attributes": 0.95,
            },
        ),
    )

    assert result.exact_match is False
    assert result.candidates == []
    assert result.match_resolution["state"] == "no_match"


def test_exact_match_collision_resolution_demotes_weaker_duplicate(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-collision@example.com")
    closet_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Collision tee",
        key_prefix="wear-match-collision",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=closet_item_id)
    assert closet_item is not None
    service = build_matching_service(db_session)

    first_result = service.match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="top",
            metadata_values={
                "category": "tops",
                "subcategory": "t_shirt",
                "primary_color": "navy",
            },
            field_confidences={
                "category": 0.99,
                "subcategory": 0.98,
                "primary_color": 0.97,
            },
            sort_index=0,
        ),
    )
    second_result = service.match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="top",
            metadata_values={
                "category": "tops",
                "subcategory": "t_shirt",
                "primary_color": "navy",
            },
            field_confidences={
                "category": 0.99,
                "subcategory": 0.98,
                "primary_color": 0.97,
            },
            sort_index=1,
        ),
    )

    resolved = service.resolve_exact_match_collisions(results=[first_result, second_result])

    assert resolved[0].exact_match is True
    assert resolved[1].exact_match is False
    assert resolved[1].match_resolution["state"] == "collision_rejected"
    assert resolved[1].candidates[0].match_state == "rejected"


def test_shared_taxonomy_wear_normalization_matches_closet_normalization() -> None:
    raw_fields = {
        "category": {
            "value": "Top",
            "confidence": 0.96,
            "applicability_state": "value",
        },
        "subcategory": {
            "value": "tee shirt",
            "confidence": 0.94,
            "applicability_state": "value",
        },
        "colors": {
            "values": ["navy blue", "grey", "mystery tone"],
            "confidence": 0.91,
            "applicability_state": "value",
        },
        "style_tags": {
            "values": ["business casual", "everyday"],
            "confidence": 0.73,
            "applicability_state": "value",
        },
        "season_tags": {
            "values": ["autumn", "winter"],
            "confidence": 0.72,
            "applicability_state": "value",
        },
    }

    metadata, field_confidences, notes = normalize_detected_metadata_fields(dict(raw_fields))

    assert metadata["category"] == normalize_field_value(
        field_name="category",
        raw_value="Top",
        applicability_state=ApplicabilityState.VALUE,
        confidence=0.96,
    ).canonical_value
    assert metadata["subcategory"] == normalize_field_value(
        field_name="subcategory",
        raw_value="tee shirt",
        applicability_state=ApplicabilityState.VALUE,
        confidence=0.94,
    ).canonical_value
    assert metadata["primary_color"] == normalize_field_value(
        field_name="primary_color",
        raw_value="navy blue",
        applicability_state=ApplicabilityState.VALUE,
        confidence=0.91,
    ).canonical_value
    assert metadata["secondary_colors"] == normalize_field_value(
        field_name="secondary_colors",
        raw_value=["grey", "mystery tone"],
        applicability_state=ApplicabilityState.VALUE,
        confidence=0.91,
    ).canonical_value
    assert metadata["style_tags"] == normalize_field_value(
        field_name="style_tags",
        raw_value=["business casual", "everyday"],
        applicability_state=ApplicabilityState.VALUE,
        confidence=0.73,
    ).canonical_value
    assert metadata["season_tags"] == normalize_field_value(
        field_name="season_tags",
        raw_value=["autumn", "winter"],
        applicability_state=ApplicabilityState.VALUE,
        confidence=0.72,
    ).canonical_value
    assert field_confidences["primary_color"] == 0.91
    assert notes["secondary_colors"] == "Unmapped secondary color values: mystery tone."


def test_legacy_colors_alias_backfills_primary_and_secondary_colors() -> None:
    metadata, field_confidences, notes = normalize_detected_metadata_fields(
        {
            "colors": {
                "values": ["navy blue", "light blue", "grey"],
                "confidence": 0.88,
                "applicability_state": "value",
            }
        }
    )

    assert metadata["primary_color"] == "navy"
    assert metadata["secondary_colors"] == ["light_blue", "gray"]
    assert field_confidences["primary_color"] == 0.88
    assert field_confidences["secondary_colors"] == 0.88
    assert notes == {}


def test_sparse_detection_without_primary_color_does_not_exact_match(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-sparse-no-color@example.com")
    closet_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Only tee",
        key_prefix="wear-match-sparse-no-color",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=closet_item_id)
    assert closet_item is not None

    result = build_matching_service(db_session).match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="top",
            metadata_values={
                "category": "tops",
                "subcategory": "t_shirt",
            },
            field_confidences={
                "category": 0.98,
                "subcategory": 0.96,
            },
        ),
    )

    assert len(result.candidates) == 1
    assert result.exact_match is False
    assert result.match_resolution["state"] == "candidate_only"


def test_rich_closet_metadata_blocks_sparse_exact_match_and_caps_display_score(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-rich-closet-sparse@example.com")
    closet_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="White V-neck tee",
        key_prefix="wear-match-rich-closet-sparse",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="white"),
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=closet_item_id)
    assert closet_item is not None

    set_confirmed_field_state(
        db_session,
        item_id=closet_item_id,
        field_name="attributes",
        canonical_value=["v_neck", "short_sleeve"],
    )
    set_confirmed_field_state(
        db_session,
        item_id=closet_item_id,
        field_name="silhouette",
        canonical_value="straight",
    )
    set_confirmed_field_state(
        db_session,
        item_id=closet_item_id,
        field_name="material",
        canonical_value="cotton",
    )

    result = build_matching_service(db_session).match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="top",
            metadata_values={
                "category": "tops",
                "subcategory": "t_shirt",
                "primary_color": "white",
            },
            field_confidences={
                "category": 0.99,
                "subcategory": 0.97,
                "primary_color": 0.96,
            },
        ),
    )

    assert len(result.candidates) == 1
    assert result.exact_match is False
    assert result.match_resolution["state"] == "candidate_only"
    assert result.candidates[0].score == WearMatchingService.SPARSE_EVIDENCE_SCORE_CAP
    assert result.candidates[0].explanation_json["exact_support"] == {
        "closet_rich_fields": ["attributes", "silhouette", "material"],
        "matched_fields": [],
        "required_matches": 2,
        "passes": False,
    }


def test_rich_closet_metadata_can_exact_match_when_structural_fields_align(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-rich-closet-exact@example.com")
    closet_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="White V-neck tee exact",
        key_prefix="wear-match-rich-closet-exact",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="white"),
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=closet_item_id)
    assert closet_item is not None

    set_confirmed_field_state(
        db_session,
        item_id=closet_item_id,
        field_name="attributes",
        canonical_value=["v_neck", "short_sleeve"],
    )
    set_confirmed_field_state(
        db_session,
        item_id=closet_item_id,
        field_name="silhouette",
        canonical_value="straight",
    )
    set_confirmed_field_state(
        db_session,
        item_id=closet_item_id,
        field_name="material",
        canonical_value="cotton",
    )

    result = build_matching_service(db_session).match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="top",
            metadata_values={
                "category": "tops",
                "subcategory": "t_shirt",
                "primary_color": "white",
                "attributes": ["v_neck", "short_sleeve"],
                "silhouette": "straight",
            },
            field_confidences={
                "category": 0.99,
                "subcategory": 0.97,
                "primary_color": 0.96,
                "attributes": 0.92,
                "silhouette": 0.88,
            },
        ),
    )

    assert len(result.candidates) == 1
    assert result.exact_match is True
    assert result.match_resolution["state"] == "exact_match"
    assert result.candidates[0].is_exact_match is True
    assert result.candidates[0].score >= 92


def test_equivalent_bottom_labels_and_nearby_color_family_still_surface_candidate(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-bottom-equivalent@example.com")
    closet_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Cream trousers",
        key_prefix="wear-match-bottom-equivalent",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="cream"),
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=closet_item_id)
    assert closet_item is not None

    result = build_matching_service(db_session).match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="bottom",
            metadata_values={
                "category": "bottoms",
                "subcategory": "jeans",
                "primary_color": "beige",
            },
            field_confidences={
                "category": 0.98,
                "subcategory": 0.94,
                "primary_color": 0.9,
            },
        ),
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].closet_item_id == closet_item_id
    assert result.exact_match is False
    assert result.match_resolution["state"] == "candidate_only"


def test_matching_canonicalizes_legacy_closet_projection_values_before_scoring(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-legacy-closet-values@example.com")
    closet_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Legacy cream knit tank",
        key_prefix="wear-match-legacy-closet-values",
        raw_fields=build_raw_fields(category="top", subcategory="knit top", color="cream"),
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=closet_item_id)
    assert closet_item is not None

    projection_row = ClosetRepository(db_session).get_confirmed_item_with_projection_for_user(
        item_id=closet_item_id,
        user_id=closet_item.user_id,
        include_archived=False,
    )
    assert projection_row is not None
    _, projection = projection_row
    projection.category = "top"
    projection.subcategory = "knit top"
    projection.primary_color = "cream"
    db_session.commit()

    result = build_matching_service(db_session).match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="top",
            metadata_values={
                "category": "tops",
                "subcategory": "tank_top",
                "primary_color": "white",
            },
            field_confidences={
                "category": 0.99,
                "subcategory": 0.95,
                "primary_color": 0.91,
            },
        ),
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].closet_item_id == closet_item_id
    assert result.match_resolution["state"] == "candidate_only"


def test_exact_match_gate_stays_false_when_second_candidate_is_hidden_by_limit(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-matching-limit-gate@example.com")
    first_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="First navy tee limit",
        key_prefix="wear-match-limit-a",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    second_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Second navy tee limit",
        key_prefix="wear-match-limit-b",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    closet_item = ClosetRepository(db_session).get_item(item_id=first_item_id)
    assert closet_item is not None

    result = build_matching_service(db_session).match_detection(
        user_id=closet_item.user_id,
        detection=build_detection_input(
            role="top",
            metadata_values={
                "category": "tops",
                "subcategory": "t_shirt",
                "primary_color": "navy",
            },
            field_confidences={
                "category": 0.99,
                "subcategory": 0.98,
                "primary_color": 0.97,
            },
        ),
        limit=1,
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].closet_item_id in {first_item_id, second_item_id}
    assert result.exact_match is False
    assert result.match_resolution["state"] == "candidate_only"


def test_matching_excludes_archived_unconfirmed_and_cross_user_items(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    owner_headers = register_and_get_headers(client, email="wear-match-owner-hardening@example.com")
    other_headers = register_and_get_headers(client, email="wear-match-other-hardening@example.com")
    archived_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=owner_headers,
        title="Archived tee",
        key_prefix="wear-match-archived",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    create_normalized_review_item_for_user(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=owner_headers,
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
        title="Still in review tee",
        key_prefix="wear-match-review-only",
    )
    create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=other_headers,
        title="Other user tee",
        key_prefix="wear-match-other-user",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )

    closet_repository = ClosetRepository(db_session)
    archived_item = closet_repository.get_item(item_id=archived_item_id)
    assert archived_item is not None
    archived_item.archived_at = datetime.now(UTC)
    db_session.commit()

    owner_profile = closet_repository.get_item(item_id=archived_item_id)
    assert owner_profile is not None
    result = build_matching_service(db_session).match_detection(
        user_id=owner_profile.user_id,
        detection=build_detection_input(
            role="top",
            metadata_values={
                "category": "tops",
                "subcategory": "t_shirt",
                "primary_color": "navy",
            },
            field_confidences={
                "category": 0.99,
                "subcategory": 0.98,
                "primary_color": 0.97,
            },
        ),
    )

    assert result.candidates == []
    assert result.match_resolution["state"] == "no_match"
