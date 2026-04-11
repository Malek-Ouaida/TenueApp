from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.closet.errors import (
    INVALID_LIFECYCLE_TRANSITION,
    INVALID_REVIEW_MUTATION,
    RETRY_NOT_AVAILABLE,
    REVIEW_NOT_AVAILABLE,
    REVIEW_SUGGESTION_MISSING,
    STALE_REVIEW_VERSION,
    build_error,
)
from app.domains.closet.image_processing_service import (
    ClosetImageProcessingService,
    ProcessingSnapshot,
)
from app.domains.closet.metadata_extraction import METADATA_EXTRACTION_TASK_TYPE
from app.domains.closet.metadata_extraction_service import (
    ClosetMetadataExtractionService,
    ExtractionCurrentCandidateSet,
    ExtractionSnapshot,
)
from app.domains.closet.models import (
    ApplicabilityState,
    AuditActorType,
    ClosetItem,
    ClosetItemFieldState,
    FieldReviewState,
    FieldSource,
    LifecycleStatus,
    ProviderResult,
)
from app.domains.closet.normalization import (
    NormalizedFieldValue,
    collapse_whitespace,
    derive_category_for_subcategory,
    normalize_field_value,
)
from app.domains.closet.normalization_service import ClosetNormalizationService
from app.domains.closet.repository import (
    ClosetJobRepository,
    ClosetRepository,
    is_confirmed_field_state,
)
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

RETRY_STEP_IMAGE_PROCESSING = "image_processing"
RETRY_STEP_METADATA_EXTRACTION = "metadata_extraction"
RETRY_STEP_NORMALIZATION = "normalization_projection"

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
class ReviewSuggestedFieldStateSnapshot:
    canonical_value: Any | None
    confidence: float | None
    applicability_state: str
    conflict_notes: str | None
    provider_result_id: UUID | None
    is_derived: bool


@dataclass(frozen=True)
class ReviewFieldSnapshot:
    field_name: str
    required: bool
    blocking_confirmation: bool
    current_state: Any
    suggested_state: ReviewSuggestedFieldStateSnapshot | None


@dataclass(frozen=True)
class ReviewRetryActionSnapshot:
    can_retry: bool
    default_step: str | None
    reason: str | None


@dataclass(frozen=True)
class ReviewSnapshot:
    item_id: UUID
    lifecycle_status: str
    processing_status: str
    extraction_status: str
    normalization_status: str
    review_status: str
    failure_summary: str | None
    confirmed_at: Any
    review_version: str
    can_confirm: bool
    missing_required_fields: list[str]
    field_states_stale: bool
    retry_action: ReviewRetryActionSnapshot
    latest_processing_run: Any
    latest_extraction_run: Any
    latest_normalization_run: Any
    display_image: Any
    original_image: Any
    original_images: list[Any]
    thumbnail_image: Any
    review_fields: list[ReviewFieldSnapshot]
    current_candidate_set: ExtractionCurrentCandidateSet | None


@dataclass(frozen=True)
class PlannedFieldMutation:
    field_name: str
    canonical_value: Any | None
    applicability_state: ApplicabilityState
    review_state: FieldReviewState
    source: FieldSource
    confidence: float | None
    audit_event_type: str
    operation: str


@dataclass(frozen=True)
class ReviewContext:
    item: ClosetItem
    processing_snapshot: ProcessingSnapshot
    extraction_snapshot: ExtractionSnapshot
    field_states_by_name: dict[str, ClosetItemFieldState]
    suggested_states: dict[str, ReviewSuggestedFieldStateSnapshot]
    review_version: str
    missing_required_fields: list[str]
    can_confirm: bool
    retry_action: ReviewRetryActionSnapshot


class ClosetReviewService:
    def __init__(
        self,
        *,
        session: Session,
        repository: ClosetRepository,
        job_repository: ClosetJobRepository,
        lifecycle_service: ClosetLifecycleService,
        image_processing_service: ClosetImageProcessingService,
        extraction_service: ClosetMetadataExtractionService,
        normalization_service: ClosetNormalizationService,
        similarity_service: ClosetSimilarityService,
    ) -> None:
        self.session = session
        self.repository = repository
        self.job_repository = job_repository
        self.lifecycle_service = lifecycle_service
        self.image_processing_service = image_processing_service
        self.extraction_service = extraction_service
        self.normalization_service = normalization_service
        self.similarity_service = similarity_service

    def get_review_snapshot(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
    ) -> ReviewSnapshot:
        return self._build_review_snapshot(
            item_id=item_id,
            user_id=user_id,
            enforce_review_visibility=True,
        )

    def patch_review(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        expected_review_version: str,
        changes: list[dict[str, Any]],
    ) -> ReviewSnapshot:
        context = self._load_review_context(
            item_id=item_id,
            user_id=user_id,
            enforce_review_visibility=False,
        )
        self._ensure_mutable_review_item(context.item)
        self._ensure_matching_review_version(
            expected_review_version=expected_review_version,
            actual_review_version=context.review_version,
        )

        if not changes:
            raise build_error(
                INVALID_REVIEW_MUTATION,
                detail="At least one review change is required.",
            )

        field_names = [str(change["field_name"]) for change in changes]
        if len(field_names) != len(set(field_names)):
            raise build_error(
                INVALID_REVIEW_MUTATION,
                detail="Each field may appear at most once in a review patch.",
            )

        planned_mutations = {
            str(change["field_name"]): self._plan_mutation(
                field_name=str(change["field_name"]),
                operation=str(change["operation"]),
                canonical_value=change.get("canonical_value"),
                suggested_state=context.suggested_states.get(str(change["field_name"])),
            )
            for change in changes
        }
        planned_mutations = self._reconcile_category_patch(
            field_states_by_name=context.field_states_by_name,
            planned_mutations=planned_mutations,
        )

        for field_name in SUPPORTED_FIELD_ORDER:
            mutation = planned_mutations.get(field_name)
            if mutation is None:
                continue
            previous_state = context.field_states_by_name.get(field_name)
            field_state = self.lifecycle_service.save_field_state(
                item=context.item,
                field_name=mutation.field_name,
                canonical_value=mutation.canonical_value,
                source=mutation.source,
                review_state=mutation.review_state,
                applicability_state=mutation.applicability_state,
                confidence=mutation.confidence,
                taxonomy_version=TAXONOMY_VERSION,
            )
            self.repository.create_audit_event(
                closet_item_id=context.item.id,
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
            context.field_states_by_name[field_name] = field_state

        self.session.commit()
        return self._build_review_snapshot(
            item_id=item_id,
            user_id=user_id,
            enforce_review_visibility=True,
        )

    def confirm_review(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        expected_review_version: str,
    ) -> ReviewSnapshot:
        context = self._load_review_context(
            item_id=item_id,
            user_id=user_id,
            enforce_review_visibility=False,
        )
        self._ensure_mutable_review_item(context.item)
        self._ensure_matching_review_version(
            expected_review_version=expected_review_version,
            actual_review_version=context.review_version,
        )
        item = self.lifecycle_service.confirm_item(
            item_id=item_id,
            user_id=user_id,
            commit=False,
        )
        self.similarity_service.enqueue_similarity_for_item(
            item=item,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            raise_on_duplicate=False,
        )
        self.session.commit()
        return self._build_review_snapshot(
            item_id=item_id,
            user_id=user_id,
            enforce_review_visibility=True,
        )

    def retry_review(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        step: str | None,
    ) -> tuple[ReviewSnapshot, int]:
        context = self._load_review_context(
            item_id=item_id,
            user_id=user_id,
            enforce_review_visibility=False,
        )
        self._ensure_mutable_review_item(context.item)

        retry_step = step or context.retry_action.default_step
        if retry_step is None:
            raise build_error(RETRY_NOT_AVAILABLE)
        if not self._is_retry_step_available(context=context, step=retry_step):
            raise build_error(
                RETRY_NOT_AVAILABLE,
                detail=f"Retry step '{retry_step}' is not actionable for this closet item.",
            )

        if retry_step == RETRY_STEP_IMAGE_PROCESSING:
            self.image_processing_service.enqueue_processing_for_item(
                item=context.item,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                raise_on_duplicate=True,
            )
        elif retry_step == RETRY_STEP_METADATA_EXTRACTION:
            self.extraction_service.enqueue_extraction_for_item(
                item=context.item,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                raise_on_duplicate=True,
            )
        elif retry_step == RETRY_STEP_NORMALIZATION:
            provider_result = self.repository.get_latest_usable_provider_result_for_item_task(
                closet_item_id=context.item.id,
                task_type=METADATA_EXTRACTION_TASK_TYPE,
            )
            if provider_result is None:
                raise build_error(
                    RETRY_NOT_AVAILABLE,
                    detail=(
                        "No usable extraction candidate set is available to retry normalization."
                    ),
                )
            self.normalization_service.enqueue_normalization_for_provider_result(
                item=context.item,
                provider_result=provider_result,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                raise_on_duplicate=True,
            )
        else:
            raise build_error(RETRY_NOT_AVAILABLE)

        self.repository.create_audit_event(
            closet_item_id=context.item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="item_retry_requested",
            payload={
                "step": retry_step,
                "processing_status": context.processing_snapshot.processing_status,
                "extraction_status": context.extraction_snapshot.extraction_status,
                "normalization_status": context.extraction_snapshot.normalization_status,
                "field_states_stale": context.extraction_snapshot.field_states_stale,
            },
        )
        self.session.commit()
        return (
            self._build_review_snapshot(
                item_id=item_id,
                user_id=user_id,
                enforce_review_visibility=False,
            ),
            202,
        )

    def _build_review_snapshot(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        enforce_review_visibility: bool,
    ) -> ReviewSnapshot:
        context = self._load_review_context(
            item_id=item_id,
            user_id=user_id,
            enforce_review_visibility=enforce_review_visibility,
        )
        review_fields = [
            ReviewFieldSnapshot(
                field_name=field_name,
                required=field_name in REQUIRED_CONFIRMATION_FIELDS,
                blocking_confirmation=field_name in context.missing_required_fields,
                current_state=self._build_current_state_snapshot(
                    item=context.item,
                    field_name=field_name,
                    field_state=context.field_states_by_name.get(field_name),
                ),
                suggested_state=context.suggested_states.get(field_name),
            )
            for field_name in SUPPORTED_FIELD_ORDER
        ]
        return ReviewSnapshot(
            item_id=context.item.id,
            lifecycle_status=context.item.lifecycle_status.value,
            processing_status=context.item.processing_status.value,
            extraction_status=context.extraction_snapshot.extraction_status,
            normalization_status=context.extraction_snapshot.normalization_status,
            review_status=context.item.review_status.value,
            failure_summary=context.item.failure_summary,
            confirmed_at=context.item.confirmed_at,
            review_version=context.review_version,
            can_confirm=context.can_confirm,
            missing_required_fields=context.missing_required_fields,
            field_states_stale=context.extraction_snapshot.field_states_stale,
            retry_action=context.retry_action,
            latest_processing_run=context.processing_snapshot.latest_run,
            latest_extraction_run=context.extraction_snapshot.latest_run,
            latest_normalization_run=context.extraction_snapshot.latest_normalization_run,
            display_image=context.processing_snapshot.display_image,
            original_image=context.processing_snapshot.original_image,
            original_images=context.processing_snapshot.original_images,
            thumbnail_image=context.processing_snapshot.thumbnail_image,
            review_fields=review_fields,
            current_candidate_set=context.extraction_snapshot.current_candidate_set,
        )

    def _load_review_context(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        enforce_review_visibility: bool,
    ) -> ReviewContext:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        if enforce_review_visibility and item.lifecycle_status not in {
            LifecycleStatus.REVIEW,
            LifecycleStatus.CONFIRMED,
        }:
            raise build_error(REVIEW_NOT_AVAILABLE)

        processing_snapshot = self.image_processing_service.get_processing_snapshot(
            item_id=item_id,
            user_id=user_id,
        )
        extraction_snapshot = self.extraction_service.get_extraction_snapshot(
            item_id=item_id,
            user_id=user_id,
        )
        field_states_by_name = {
            field_state.field_name: field_state
            for field_state in self.repository.list_field_states(closet_item_id=item.id)
        }
        latest_usable_provider_result = (
            self.repository.get_latest_usable_provider_result_for_item_task(
                closet_item_id=item.id,
                task_type=METADATA_EXTRACTION_TASK_TYPE,
            )
        )
        suggested_states = self._build_suggested_states(
            provider_result=latest_usable_provider_result
        )
        missing_required_fields = [
            field_name
            for field_name in REQUIRED_CONFIRMATION_FIELDS
            if not is_confirmed_field_state(field_states_by_name.get(field_name))
        ]
        has_primary_image = self.repository.has_active_primary_image(item=item)
        retry_action = self._build_retry_action(
            item=item,
            processing_snapshot=processing_snapshot,
            extraction_snapshot=extraction_snapshot,
        )
        return ReviewContext(
            item=item,
            processing_snapshot=processing_snapshot,
            extraction_snapshot=extraction_snapshot,
            field_states_by_name=field_states_by_name,
            suggested_states=suggested_states,
            review_version=self._build_review_version(
                item=item,
                field_states_by_name=field_states_by_name,
                latest_usable_provider_result=latest_usable_provider_result,
                latest_normalization_run=extraction_snapshot.latest_normalization_run,
            ),
            missing_required_fields=missing_required_fields,
            can_confirm=(
                item.lifecycle_status == LifecycleStatus.REVIEW
                and has_primary_image
                and not missing_required_fields
            ),
            retry_action=retry_action,
        )

    def _build_suggested_states(
        self,
        *,
        provider_result: ProviderResult | None,
    ) -> dict[str, ReviewSuggestedFieldStateSnapshot]:
        if provider_result is None:
            return {}

        candidates = self.repository.list_field_candidates_for_provider_result(
            provider_result_id=provider_result.id
        )
        normalized_values = {
            candidate.field_name: normalize_field_value(
                field_name=candidate.field_name,
                raw_value=candidate.raw_value,
                applicability_state=candidate.applicability_state,
                confidence=candidate.confidence,
            )
            for candidate in candidates
        }
        normalized_values, derived_category = self._reconcile_suggested_taxonomy(normalized_values)
        candidate_by_field = {candidate.field_name: candidate for candidate in candidates}

        suggestions: dict[str, ReviewSuggestedFieldStateSnapshot] = {}
        for field_name, normalized_value in normalized_values.items():
            if (
                normalized_value.applicability_state == ApplicabilityState.VALUE
                and not _has_canonical_value(normalized_value.canonical_value)
            ):
                continue

            candidate = candidate_by_field.get(field_name)
            conflict_notes = _merge_notes(
                candidate.conflict_notes if candidate is not None else None,
                normalized_value.notes,
            )
            suggestions[field_name] = ReviewSuggestedFieldStateSnapshot(
                canonical_value=(
                    normalized_value.canonical_value
                    if normalized_value.applicability_state == ApplicabilityState.VALUE
                    else None
                ),
                confidence=normalized_value.confidence,
                applicability_state=normalized_value.applicability_state.value,
                conflict_notes=conflict_notes,
                provider_result_id=provider_result.id,
                is_derived=field_name == "category" and derived_category,
            )
        return suggestions

    def _reconcile_suggested_taxonomy(
        self,
        normalized_values: dict[str, NormalizedFieldValue],
    ) -> tuple[dict[str, NormalizedFieldValue], bool]:
        subcategory_value = normalized_values.get("subcategory")
        category_value = normalized_values.get("category")
        if subcategory_value is None:
            return normalized_values, False
        if subcategory_value.applicability_state != ApplicabilityState.VALUE:
            return normalized_values, False
        if not isinstance(subcategory_value.canonical_value, str):
            return normalized_values, False

        derived_category = derive_category_for_subcategory(subcategory_value.canonical_value)
        if derived_category is None:
            return normalized_values, False

        derived = False
        if category_value is None:
            normalized_values["category"] = NormalizedFieldValue(
                field_name="category",
                canonical_value=derived_category,
                applicability_state=ApplicabilityState.VALUE,
                confidence=subcategory_value.confidence,
                notes=(
                    f"Derived category '{derived_category}' from subcategory "
                    f"'{subcategory_value.canonical_value}'.",
                ),
            )
            return normalized_values, True

        if category_value.applicability_state != ApplicabilityState.VALUE:
            return normalized_values, False

        if category_value.canonical_value is None:
            normalized_values["category"] = NormalizedFieldValue(
                field_name="category",
                canonical_value=derived_category,
                applicability_state=ApplicabilityState.VALUE,
                confidence=subcategory_value.confidence,
                notes=category_value.notes
                + (
                    f"Derived category '{derived_category}' from subcategory "
                    f"'{subcategory_value.canonical_value}'.",
                ),
            )
            return normalized_values, True

        if category_value.canonical_value == derived_category:
            return normalized_values, False

        normalized_values["category"] = NormalizedFieldValue(
            field_name="category",
            canonical_value=derived_category,
            applicability_state=ApplicabilityState.VALUE,
            confidence=_lower_confidence(category_value.confidence, subcategory_value.confidence),
            notes=category_value.notes
            + (
                f"Category conflicted with subcategory '{subcategory_value.canonical_value}' and "
                f"was resolved to '{derived_category}'.",
            ),
        )
        derived = True
        return normalized_values, derived

    def _build_current_state_snapshot(
        self,
        *,
        item: ClosetItem,
        field_name: str,
        field_state: ClosetItemFieldState | None,
    ) -> Any:
        if field_state is None:
            return _SyntheticFieldState(
                field_name=field_name,
                canonical_value=None,
                source=FieldSource.SYSTEM.value,
                confidence=None,
                review_state=FieldReviewState.SYSTEM_UNSET.value,
                applicability_state=ApplicabilityState.UNKNOWN.value,
                taxonomy_version=TAXONOMY_VERSION,
                updated_at=item.updated_at,
            )
        return _SyntheticFieldState(
            field_name=field_state.field_name,
            canonical_value=field_state.canonical_value,
            source=field_state.source.value,
            confidence=field_state.confidence,
            review_state=field_state.review_state.value,
            applicability_state=field_state.applicability_state.value,
            taxonomy_version=field_state.taxonomy_version,
            updated_at=field_state.updated_at,
        )

    def _build_review_version(
        self,
        *,
        item: ClosetItem,
        field_states_by_name: dict[str, ClosetItemFieldState],
        latest_usable_provider_result: ProviderResult | None,
        latest_normalization_run: Any,
    ) -> str:
        payload = {
            "item_updated_at": _serialize_datetime(item.updated_at),
            "candidate_provider_result_id": (
                str(latest_usable_provider_result.id)
                if latest_usable_provider_result is not None
                else None
            ),
            "latest_normalization_run_id": (
                str(getattr(latest_normalization_run, "id"))
                if latest_normalization_run is not None
                else None
            ),
            "latest_normalization_status": (
                getattr(getattr(latest_normalization_run, "status"), "value")
                if latest_normalization_run is not None
                and hasattr(getattr(latest_normalization_run, "status"), "value")
                else getattr(latest_normalization_run, "status", None)
            ),
            "field_states": [
                {
                    "field_name": field_name,
                    "canonical_value": field_state.canonical_value,
                    "source": field_state.source.value,
                    "confidence": field_state.confidence,
                    "review_state": field_state.review_state.value,
                    "applicability_state": field_state.applicability_state.value,
                    "taxonomy_version": field_state.taxonomy_version,
                    "updated_at": _serialize_datetime(field_state.updated_at),
                }
                for field_name, field_state in sorted(field_states_by_name.items())
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _build_retry_action(
        self,
        *,
        item: ClosetItem,
        processing_snapshot: ProcessingSnapshot,
        extraction_snapshot: ExtractionSnapshot,
    ) -> ReviewRetryActionSnapshot:
        if item.lifecycle_status != LifecycleStatus.REVIEW:
            return ReviewRetryActionSnapshot(
                can_retry=False,
                default_step=None,
                reason="Retry is only available while the item is in review.",
            )
        if processing_snapshot.processing_status == "failed":
            return ReviewRetryActionSnapshot(
                can_retry=True,
                default_step=RETRY_STEP_IMAGE_PROCESSING,
                reason="Image processing failed.",
            )
        if extraction_snapshot.extraction_status == "failed":
            return ReviewRetryActionSnapshot(
                can_retry=True,
                default_step=RETRY_STEP_METADATA_EXTRACTION,
                reason="Metadata extraction failed.",
            )
        if extraction_snapshot.normalization_status == "failed":
            return ReviewRetryActionSnapshot(
                can_retry=True,
                default_step=RETRY_STEP_NORMALIZATION,
                reason="Metadata normalization failed.",
            )
        if extraction_snapshot.field_states_stale:
            return ReviewRetryActionSnapshot(
                can_retry=True,
                default_step=RETRY_STEP_NORMALIZATION,
                reason="Field states are stale.",
            )
        return ReviewRetryActionSnapshot(
            can_retry=False,
            default_step=None,
            reason="No retryable review step is currently available.",
        )

    def _is_retry_step_available(self, *, context: ReviewContext, step: str) -> bool:
        if step == RETRY_STEP_IMAGE_PROCESSING:
            return context.processing_snapshot.processing_status == "failed"
        if step == RETRY_STEP_METADATA_EXTRACTION:
            return context.extraction_snapshot.extraction_status == "failed"
        if step == RETRY_STEP_NORMALIZATION:
            return (
                context.extraction_snapshot.normalization_status == "failed"
                or context.extraction_snapshot.field_states_stale
            )
        return False

    def _plan_mutation(
        self,
        *,
        field_name: str,
        operation: str,
        canonical_value: Any,
        suggested_state: ReviewSuggestedFieldStateSnapshot | None,
    ) -> PlannedFieldMutation:
        if operation == "accept_suggestion":
            if not _is_usable_suggestion(suggested_state):
                raise build_error(
                    REVIEW_SUGGESTION_MISSING,
                    detail=f"No usable suggestion is available for field '{field_name}'.",
                )
            assert suggested_state is not None
            return PlannedFieldMutation(
                field_name=field_name,
                canonical_value=suggested_state.canonical_value,
                applicability_state=ApplicabilityState(suggested_state.applicability_state),
                review_state=FieldReviewState.USER_CONFIRMED,
                source=FieldSource.USER,
                confidence=None,
                audit_event_type="field_state_user_confirmed",
                operation="accept_suggestion",
            )
        if operation == "set_value":
            return PlannedFieldMutation(
                field_name=field_name,
                canonical_value=self._validate_manual_value(
                    field_name=field_name,
                    canonical_value=canonical_value,
                ),
                applicability_state=ApplicabilityState.VALUE,
                review_state=FieldReviewState.USER_EDITED,
                source=FieldSource.USER,
                confidence=None,
                audit_event_type="field_state_user_edited",
                operation="set_value",
            )
        if operation == "clear":
            return PlannedFieldMutation(
                field_name=field_name,
                canonical_value=None,
                applicability_state=ApplicabilityState.UNKNOWN,
                review_state=FieldReviewState.USER_EDITED,
                source=FieldSource.USER,
                confidence=None,
                audit_event_type="field_state_user_cleared",
                operation="clear",
            )
        if operation == "mark_not_applicable":
            return PlannedFieldMutation(
                field_name=field_name,
                canonical_value=None,
                applicability_state=ApplicabilityState.NOT_APPLICABLE,
                review_state=FieldReviewState.USER_EDITED,
                source=FieldSource.USER,
                confidence=None,
                audit_event_type="field_state_user_marked_not_applicable",
                operation="mark_not_applicable",
            )

        raise build_error(
            INVALID_REVIEW_MUTATION,
            detail=f"Unsupported review operation '{operation}' for field '{field_name}'.",
        )

    def _reconcile_category_patch(
        self,
        *,
        field_states_by_name: dict[str, ClosetItemFieldState],
        planned_mutations: dict[str, PlannedFieldMutation],
    ) -> dict[str, PlannedFieldMutation]:
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
                planned_mutations["category"] = PlannedFieldMutation(
                    field_name="category",
                    canonical_value=derived_category,
                    applicability_state=ApplicabilityState.VALUE,
                    review_state=FieldReviewState.USER_EDITED,
                    source=FieldSource.USER,
                    confidence=None,
                    audit_event_type="field_state_user_edited",
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

    def _ensure_matching_review_version(
        self,
        *,
        expected_review_version: str,
        actual_review_version: str,
    ) -> None:
        if expected_review_version != actual_review_version:
            raise build_error(STALE_REVIEW_VERSION)

    def _ensure_mutable_review_item(self, item: ClosetItem) -> None:
        if item.lifecycle_status != LifecycleStatus.REVIEW:
            raise build_error(INVALID_LIFECYCLE_TRANSITION)


@dataclass(frozen=True)
class _SyntheticFieldState:
    field_name: str
    canonical_value: Any | None
    source: str
    confidence: float | None
    review_state: str
    applicability_state: str
    taxonomy_version: str
    updated_at: Any


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


def _mutation_has_scalar_value(mutation: PlannedFieldMutation) -> bool:
    return (
        mutation.applicability_state == ApplicabilityState.VALUE
        and isinstance(
            mutation.canonical_value,
            str,
        )
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


def _is_usable_suggestion(suggested_state: ReviewSuggestedFieldStateSnapshot | None) -> bool:
    if suggested_state is None:
        return False
    if suggested_state.applicability_state in {
        ApplicabilityState.UNKNOWN.value,
        ApplicabilityState.NOT_APPLICABLE.value,
    }:
        return True
    return _has_canonical_value(suggested_state.canonical_value)


def _lower_confidence(first: float | None, second: float | None) -> float | None:
    if first is None:
        return second
    if second is None:
        return first
    return min(first, second)


def _merge_notes(existing: str | None, new_notes: tuple[str, ...]) -> str | None:
    notes: list[str] = []
    if isinstance(existing, str) and existing.strip():
        notes.append(existing.strip())
    for note in new_notes:
        stripped = note.strip()
        if stripped and stripped not in notes:
            notes.append(stripped)
    return " | ".join(notes) if notes else None


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()
