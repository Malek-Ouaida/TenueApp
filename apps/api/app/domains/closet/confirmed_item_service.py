from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.closet.browse_service import BrowseDetailSnapshot, ClosetBrowseService
from app.domains.closet.errors import (
    INVALID_LIFECYCLE_TRANSITION,
    INVALID_REVIEW_MUTATION,
    MISSING_REQUIRED_CONFIRMATION_FIELDS,
    STALE_REVIEW_VERSION,
    build_error,
)
from app.domains.closet.models import (
    ApplicabilityState,
    AuditActorType,
    ClosetItem,
    ClosetItemFieldState,
    FieldReviewState,
    FieldSource,
    LifecycleStatus,
)
from app.domains.closet.normalization import collapse_whitespace, derive_category_for_subcategory
from app.domains.closet.repository import ClosetRepository
from app.domains.closet.service import ClosetLifecycleService
from app.domains.closet.similarity_service import ClosetSimilarityService
from app.domains.closet.taxonomy import (
    ATTRIBUTES,
    CATEGORY_SUBCATEGORIES,
    COLORS,
    FIT_TAGS,
    MATERIALS,
    OCCASION_TAGS,
    PATTERNS,
    REQUIRED_CONFIRMATION_FIELDS,
    SEASON_TAGS,
    SILHOUETTES,
    STYLE_TAGS,
    SUPPORTED_FIELD_ORDER,
    TAXONOMY_VERSION,
)

logger = logging.getLogger(__name__)

SCALAR_CONTROLLED_FIELDS = frozenset(
    {"category", "subcategory", "material", "pattern", "silhouette"}
)
LIST_FIELDS = frozenset(
    {"colors", "style_tags", "fit_tags", "occasion_tags", "season_tags", "attributes"}
)
CATEGORY_VALUES = frozenset(CATEGORY_SUBCATEGORIES.keys())
SUBCATEGORY_VALUES = frozenset(
    subcategory
    for subcategories in CATEGORY_SUBCATEGORIES.values()
    for subcategory in subcategories
)
CONTROLLED_LIST_VALUES = {
    "colors": frozenset(COLORS),
    "style_tags": frozenset(STYLE_TAGS),
    "fit_tags": frozenset(FIT_TAGS),
    "occasion_tags": frozenset(OCCASION_TAGS),
    "season_tags": frozenset(SEASON_TAGS),
    "attributes": frozenset(ATTRIBUTES),
}
CONTROLLED_SCALAR_VALUES = {
    "category": CATEGORY_VALUES,
    "subcategory": SUBCATEGORY_VALUES,
    "material": frozenset(MATERIALS),
    "pattern": frozenset(PATTERNS),
    "silhouette": frozenset(SILHOUETTES),
}


@dataclass(frozen=True)
class ConfirmedItemMutation:
    field_name: str
    canonical_value: Any | None
    applicability_state: ApplicabilityState
    review_state: FieldReviewState
    source: FieldSource
    audit_event_type: str
    operation: str


@dataclass(frozen=True)
class ConfirmedItemEditSnapshot:
    item_id: UUID
    lifecycle_status: str
    processing_status: str
    review_status: str
    confirmed_at: datetime
    updated_at: datetime
    item_version: str
    editable_fields: list[str]
    detail: BrowseDetailSnapshot


class ConfirmedClosetItemService:
    def __init__(
        self,
        *,
        session: Session,
        repository: ClosetRepository,
        lifecycle_service: ClosetLifecycleService,
        browse_service: ClosetBrowseService,
        similarity_service: ClosetSimilarityService,
    ) -> None:
        self.session = session
        self.repository = repository
        self.lifecycle_service = lifecycle_service
        self.browse_service = browse_service
        self.similarity_service = similarity_service

    def get_edit_snapshot(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
    ) -> ConfirmedItemEditSnapshot:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        self._ensure_editable_confirmed_item(item)
        detail = self.browse_service.get_confirmed_item_detail(item_id=item_id, user_id=user_id)
        return ConfirmedItemEditSnapshot(
            item_id=item.id,
            lifecycle_status=item.lifecycle_status.value,
            processing_status=item.processing_status.value,
            review_status=item.review_status.value,
            confirmed_at=item.confirmed_at or item.updated_at,
            updated_at=item.updated_at,
            item_version=build_confirmed_item_version(detail=detail),
            editable_fields=list(SUPPORTED_FIELD_ORDER),
            detail=detail,
        )

    def patch_item(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        expected_item_version: str,
        changes: list[dict[str, Any]],
    ) -> ConfirmedItemEditSnapshot:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        self._ensure_editable_confirmed_item(item)
        before = self.get_edit_snapshot(item_id=item_id, user_id=user_id)
        if expected_item_version != before.item_version:
            raise build_error(STALE_REVIEW_VERSION)
        if not changes:
            raise build_error(
                INVALID_REVIEW_MUTATION,
                detail="At least one confirmed-item change is required.",
            )

        field_names = [str(change["field_name"]) for change in changes]
        if len(field_names) != len(set(field_names)):
            raise build_error(
                INVALID_REVIEW_MUTATION,
                detail="Each field may appear at most once in a confirmed-item patch.",
            )

        field_states_by_name = {
            field_state.field_name: field_state
            for field_state in self.repository.list_field_states(closet_item_id=item.id)
        }
        planned_mutations = {
            str(change["field_name"]): self._plan_mutation(
                field_name=str(change["field_name"]),
                operation=str(change["operation"]),
                canonical_value=change.get("canonical_value"),
            )
            for change in changes
        }
        planned_mutations = self._reconcile_category_patch(
            field_states_by_name=field_states_by_name,
            planned_mutations=planned_mutations,
        )
        self._ensure_required_fields_remain_confirmed(planned_mutations=planned_mutations)

        for field_name in SUPPORTED_FIELD_ORDER:
            mutation = planned_mutations.get(field_name)
            if mutation is None:
                continue
            previous_state = field_states_by_name.get(field_name)
            field_state = self.lifecycle_service.save_field_state(
                item=item,
                field_name=mutation.field_name,
                canonical_value=mutation.canonical_value,
                source=mutation.source,
                review_state=mutation.review_state,
                applicability_state=mutation.applicability_state,
                confidence=None,
                taxonomy_version=TAXONOMY_VERSION,
            )
            self.repository.create_audit_event(
                closet_item_id=item.id,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                event_type=mutation.audit_event_type,
                payload={
                    "field_name": field_name,
                    "operation": mutation.operation,
                    "previous_state": _field_state_summary(previous_state),
                    "new_state": _field_state_summary(field_state),
                },
            )
            field_states_by_name[field_name] = field_state

        self.similarity_service.enqueue_similarity_for_item(
            item=item,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            raise_on_duplicate=False,
            trigger="confirmed_item_edit",
        )
        self.session.commit()
        logger.info(
            "closet_confirmed_item_updated",
            extra={"closet_item_id": str(item.id), "user_id": str(user_id)},
        )
        return self.get_edit_snapshot(item_id=item_id, user_id=user_id)

    def _ensure_editable_confirmed_item(self, item: ClosetItem) -> None:
        if item.lifecycle_status != LifecycleStatus.CONFIRMED:
            raise build_error(INVALID_LIFECYCLE_TRANSITION)

    def _ensure_required_fields_remain_confirmed(
        self,
        *,
        planned_mutations: dict[str, ConfirmedItemMutation],
    ) -> None:
        for field_name in REQUIRED_CONFIRMATION_FIELDS:
            mutation = planned_mutations.get(field_name)
            if mutation is None:
                continue
            if mutation.applicability_state != ApplicabilityState.VALUE or not _has_canonical_value(
                mutation.canonical_value
            ):
                raise build_error(
                    MISSING_REQUIRED_CONFIRMATION_FIELDS,
                    detail=(
                        "Confirmed closet items must keep category and subcategory set to valid "
                        "canonical values."
                    ),
                )

    def _plan_mutation(
        self,
        *,
        field_name: str,
        operation: str,
        canonical_value: Any,
    ) -> ConfirmedItemMutation:
        if operation == "set_value":
            return ConfirmedItemMutation(
                field_name=field_name,
                canonical_value=self._validate_manual_value(
                    field_name=field_name,
                    canonical_value=canonical_value,
                ),
                applicability_state=ApplicabilityState.VALUE,
                review_state=FieldReviewState.USER_EDITED,
                source=FieldSource.USER,
                audit_event_type="confirmed_item_field_user_edited",
                operation="set_value",
            )
        if operation == "clear":
            return ConfirmedItemMutation(
                field_name=field_name,
                canonical_value=None,
                applicability_state=ApplicabilityState.UNKNOWN,
                review_state=FieldReviewState.USER_EDITED,
                source=FieldSource.USER,
                audit_event_type="confirmed_item_field_user_cleared",
                operation="clear",
            )
        if operation == "mark_not_applicable":
            return ConfirmedItemMutation(
                field_name=field_name,
                canonical_value=None,
                applicability_state=ApplicabilityState.NOT_APPLICABLE,
                review_state=FieldReviewState.USER_EDITED,
                source=FieldSource.USER,
                audit_event_type="confirmed_item_field_user_marked_not_applicable",
                operation="mark_not_applicable",
            )

        raise build_error(
            INVALID_REVIEW_MUTATION,
            detail=f"Unsupported confirmed-item operation '{operation}' for field '{field_name}'.",
        )

    def _reconcile_category_patch(
        self,
        *,
        field_states_by_name: dict[str, ClosetItemFieldState],
        planned_mutations: dict[str, ConfirmedItemMutation],
    ) -> dict[str, ConfirmedItemMutation]:
        category_mutation = planned_mutations.get("category")
        subcategory_mutation = planned_mutations.get("subcategory")
        existing_subcategory = _current_scalar_value(field_states_by_name.get("subcategory"))

        if subcategory_mutation is not None and _mutation_has_scalar_value(subcategory_mutation):
            derived_category = derive_category_for_subcategory(
                str(subcategory_mutation.canonical_value)
            )
            if derived_category is None:
                raise build_error(
                    INVALID_REVIEW_MUTATION,
                    detail="The selected subcategory does not belong to the supported taxonomy.",
                )

            if category_mutation is None:
                planned_mutations["category"] = ConfirmedItemMutation(
                    field_name="category",
                    canonical_value=derived_category,
                    applicability_state=ApplicabilityState.VALUE,
                    review_state=FieldReviewState.USER_EDITED,
                    source=FieldSource.USER,
                    audit_event_type="confirmed_item_field_user_edited",
                    operation="auto_align_from_subcategory",
                )
                return planned_mutations

            if (
                category_mutation.applicability_state != ApplicabilityState.VALUE
                or category_mutation.canonical_value != derived_category
            ):
                raise build_error(
                    INVALID_REVIEW_MUTATION,
                    detail="Category must match the selected subcategory parent.",
                )
            return planned_mutations

        if category_mutation is None:
            return planned_mutations

        if existing_subcategory is None or subcategory_mutation is not None:
            return planned_mutations

        required_category = derive_category_for_subcategory(existing_subcategory)
        if required_category is None:
            return planned_mutations
        if (
            category_mutation.applicability_state != ApplicabilityState.VALUE
            or category_mutation.canonical_value != required_category
        ):
            raise build_error(
                INVALID_REVIEW_MUTATION,
                detail=(
                    "Changing category requires updating subcategory at the same time when the "
                    "current subcategory belongs to a different parent."
                ),
            )
        return planned_mutations

    def _validate_manual_value(self, *, field_name: str, canonical_value: Any) -> Any:
        if field_name in {"title", "brand"}:
            if not isinstance(canonical_value, str):
                raise build_error(
                    INVALID_REVIEW_MUTATION,
                    detail=f"Field '{field_name}' requires a string value.",
                )
            normalized = collapse_whitespace(canonical_value)
            if not normalized:
                raise build_error(
                    INVALID_REVIEW_MUTATION,
                    detail=f"Field '{field_name}' requires a non-empty value.",
                )
            if len(normalized) > 255:
                raise build_error(
                    INVALID_REVIEW_MUTATION,
                    detail=f"Field '{field_name}' must be 255 characters or fewer.",
                )
            return normalized

        if field_name in SCALAR_CONTROLLED_FIELDS:
            if not isinstance(canonical_value, str):
                raise build_error(
                    INVALID_REVIEW_MUTATION,
                    detail=f"Field '{field_name}' requires a canonical string value.",
                )
            normalized = collapse_whitespace(canonical_value)
            allowed_values = CONTROLLED_SCALAR_VALUES[field_name]
            if normalized not in allowed_values:
                raise build_error(
                    INVALID_REVIEW_MUTATION,
                    detail=f"Field '{field_name}' must use a supported canonical value.",
                )
            return normalized

        if field_name in LIST_FIELDS:
            raw_values: list[str]
            if isinstance(canonical_value, str):
                raw_values = [collapse_whitespace(canonical_value)]
            elif isinstance(canonical_value, list):
                raw_values = []
                for entry in canonical_value:
                    if not isinstance(entry, str):
                        raise build_error(
                            INVALID_REVIEW_MUTATION,
                            detail=f"Field '{field_name}' requires string list values.",
                        )
                    normalized_entry = collapse_whitespace(entry)
                    if normalized_entry:
                        raw_values.append(normalized_entry)
            else:
                raise build_error(
                    INVALID_REVIEW_MUTATION,
                    detail=f"Field '{field_name}' requires a canonical list value.",
                )

            deduped: list[str] = []
            seen: set[str] = set()
            allowed_values = CONTROLLED_LIST_VALUES[field_name]
            for value in raw_values:
                if value not in allowed_values:
                    raise build_error(
                        INVALID_REVIEW_MUTATION,
                        detail=f"Field '{field_name}' must use supported canonical values.",
                    )
                key = value.casefold()
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(value)

            if not deduped:
                raise build_error(
                    INVALID_REVIEW_MUTATION,
                    detail=f"Field '{field_name}' requires at least one canonical value.",
                )
            return deduped

        raise build_error(INVALID_REVIEW_MUTATION, detail=f"Field '{field_name}' is not editable.")


def build_confirmed_item_version(*, detail: BrowseDetailSnapshot) -> str:
    payload = {
        "item_id": str(detail.item_id),
        "confirmed_at": _serialize_datetime(detail.confirmed_at),
        "updated_at": _serialize_datetime(detail.updated_at),
        "field_states": [
            {
                "field_name": field_state.field_name,
                "canonical_value": field_state.canonical_value,
                "source": field_state.source.value,
                "confidence": field_state.confidence,
                "review_state": field_state.review_state.value,
                "applicability_state": field_state.applicability_state.value,
                "taxonomy_version": field_state.taxonomy_version,
                "updated_at": _serialize_datetime(field_state.updated_at),
            }
            for field_state in detail.field_states
        ],
        "original_images": [
            {
                "image_id": str(image.image_id) if image.image_id is not None else None,
                "asset_id": str(image.asset_id),
                "position": image.position,
                "is_primary": image.is_primary,
            }
            for image in detail.original_images
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _field_state_summary(field_state: ClosetItemFieldState | None) -> dict[str, Any] | None:
    if field_state is None:
        return None
    return {
        "field_name": field_state.field_name,
        "canonical_value": field_state.canonical_value,
        "source": field_state.source.value,
        "confidence": field_state.confidence,
        "review_state": field_state.review_state.value,
        "applicability_state": field_state.applicability_state.value,
        "taxonomy_version": field_state.taxonomy_version,
    }


def _current_scalar_value(field_state: ClosetItemFieldState | None) -> str | None:
    if field_state is None:
        return None
    if field_state.applicability_state != ApplicabilityState.VALUE:
        return None
    if not isinstance(field_state.canonical_value, str):
        return None
    value = field_state.canonical_value.strip()
    return value or None


def _mutation_has_scalar_value(mutation: ConfirmedItemMutation) -> bool:
    return (
        mutation.applicability_state == ApplicabilityState.VALUE
        and isinstance(mutation.canonical_value, str)
        and bool(mutation.canonical_value.strip())
    )


def _has_canonical_value(value: Any | None) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    return True


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()
