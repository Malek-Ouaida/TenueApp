from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.closet.errors import (
    CLOSET_ITEM_NOT_FOUND,
    INVALID_LIFECYCLE_TRANSITION,
    METADATA_NORMALIZATION_ALREADY_SCHEDULED,
    METADATA_NORMALIZATION_CANDIDATE_SET_MISSING,
    METADATA_NORMALIZATION_NOT_READY,
    build_error,
)
from app.domains.closet.metadata_extraction import METADATA_EXTRACTION_TASK_TYPE
from app.domains.closet.models import (
    ApplicabilityState,
    AuditActorType,
    ClosetItem,
    ClosetItemFieldCandidate,
    ClosetItemFieldState,
    ClosetJob,
    ClosetJobStatus,
    FieldReviewState,
    FieldSource,
    LifecycleStatus,
    ProcessingRun,
    ProcessingRunType,
    ProcessingStatus,
    ProviderResult,
    ProviderResultStatus,
    ReviewStatus,
    utcnow,
)
from app.domains.closet.normalization import (
    NormalizedFieldValue,
    derive_category_for_subcategory,
    normalize_field_value,
)
from app.domains.closet.repository import (
    ClosetJobRepository,
    ClosetRepository,
    is_confirmed_field_state,
)
from app.domains.closet.taxonomy import (
    REQUIRED_CONFIRMATION_FIELDS,
    SUPPORTED_FIELD_ORDER,
    TAXONOMY_VERSION,
)


@dataclass(frozen=True)
class NormalizationFieldStateSnapshot:
    field_name: str
    canonical_value: Any | None
    source: str
    confidence: float | None
    review_state: str
    applicability_state: str
    taxonomy_version: str
    updated_at: Any


@dataclass(frozen=True)
class NormalizationMetadataProjectionSnapshot:
    taxonomy_version: str
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    secondary_colors: list[str] | None
    material: str | None
    pattern: str | None
    brand: str | None
    style_tags: list[str] | None
    occasion_tags: list[str] | None
    season_tags: list[str] | None
    confirmed_at: Any
    updated_at: Any


@dataclass(frozen=True)
class NormalizationSummary:
    normalization_status: str
    field_states_stale: bool
    latest_run: ProcessingRun | None
    current_field_states: list[NormalizationFieldStateSnapshot]
    metadata_projection: NormalizationMetadataProjectionSnapshot | None


class ClosetNormalizationService:
    def __init__(
        self,
        *,
        session: Session,
        repository: ClosetRepository,
        job_repository: ClosetJobRepository,
    ) -> None:
        self.session = session
        self.repository = repository
        self.job_repository = job_repository

    def enqueue_normalization_for_provider_result(
        self,
        *,
        item: ClosetItem,
        provider_result: ProviderResult,
        actor_type: AuditActorType,
        actor_user_id: UUID | None,
        raise_on_duplicate: bool,
    ) -> bool:
        if item.lifecycle_status == LifecycleStatus.ARCHIVED:
            raise build_error(INVALID_LIFECYCLE_TRANSITION)
        if (
            provider_result.task_type != METADATA_EXTRACTION_TASK_TYPE
            or provider_result.status
            not in {ProviderResultStatus.SUCCEEDED, ProviderResultStatus.PARTIAL}
        ):
            raise build_error(METADATA_NORMALIZATION_NOT_READY)
        if (
            self.repository.count_field_candidates_for_provider_result(
                provider_result_id=provider_result.id
            )
            == 0
        ):
            raise build_error(METADATA_NORMALIZATION_CANDIDATE_SET_MISSING)
        if self.job_repository.has_pending_or_running_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.NORMALIZATION_PROJECTION,
        ):
            if raise_on_duplicate:
                raise build_error(METADATA_NORMALIZATION_ALREADY_SCHEDULED)
            return False

        self.job_repository.enqueue_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.NORMALIZATION_PROJECTION,
            payload={"source_provider_result_id": str(provider_result.id)},
        )
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            event_type="metadata_normalization_enqueued",
            payload={"source_provider_result_id": str(provider_result.id)},
        )
        return True

    def get_summary_for_item(self, *, item: ClosetItem) -> NormalizationSummary:
        latest_run = self.repository.get_latest_processing_run(
            closet_item_id=item.id,
            run_type=ProcessingRunType.NORMALIZATION_PROJECTION,
        )
        pending_or_running_job = self.job_repository.get_pending_or_running_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.NORMALIZATION_PROJECTION,
        )
        latest_usable_extraction = self.repository.get_latest_usable_provider_result_for_item_task(
            closet_item_id=item.id,
            task_type=METADATA_EXTRACTION_TASK_TYPE,
        )
        latest_successful_source_id = self._latest_materialized_source_provider_result_id(item=item)
        current_field_states = [
            NormalizationFieldStateSnapshot(
                field_name=field_state.field_name,
                canonical_value=field_state.canonical_value,
                source=field_state.source.value,
                confidence=field_state.confidence,
                review_state=field_state.review_state.value,
                applicability_state=field_state.applicability_state.value,
                taxonomy_version=field_state.taxonomy_version,
                updated_at=field_state.updated_at,
            )
            for field_state in self._ordered_field_states(item=item)
        ]
        projection = self.repository.get_metadata_projection(item_id=item.id)

        field_states_stale = (
            False
            if latest_usable_extraction is None
            else str(latest_usable_extraction.id) != latest_successful_source_id
        )

        return NormalizationSummary(
            normalization_status=self._resolve_normalization_status(
                latest_run=latest_run,
                pending_or_running_job=pending_or_running_job,
            ),
            field_states_stale=field_states_stale,
            latest_run=latest_run,
            current_field_states=current_field_states,
            metadata_projection=None
            if projection is None
            else NormalizationMetadataProjectionSnapshot(
                taxonomy_version=projection.taxonomy_version,
                title=projection.title,
                category=projection.category,
                subcategory=projection.subcategory,
                primary_color=projection.primary_color,
                secondary_colors=projection.secondary_colors,
                material=projection.material,
                pattern=projection.pattern,
                brand=projection.brand,
                style_tags=projection.style_tags,
                occasion_tags=projection.occasion_tags,
                season_tags=projection.season_tags,
                confirmed_at=projection.confirmed_at,
                updated_at=projection.updated_at,
            ),
        )

    def handle_normalization_job(self, *, job: ClosetJob) -> None:
        item = self.repository.get_item(item_id=job.closet_item_id)
        if item is None:
            raise build_error(CLOSET_ITEM_NOT_FOUND)

        now = utcnow()
        retry_count = self.repository.count_processing_runs(
            closet_item_id=item.id,
            run_type=ProcessingRunType.NORMALIZATION_PROJECTION,
        )
        run = self.repository.create_processing_run(
            closet_item_id=item.id,
            run_type=ProcessingRunType.NORMALIZATION_PROJECTION,
            status=ProcessingStatus.RUNNING,
            retry_count=retry_count,
            started_at=now,
        )
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.WORKER,
            actor_user_id=None,
            event_type="metadata_normalization_started",
            payload={"processing_run_id": str(run.id)},
        )

        provider_result = self._load_source_provider_result(item=item, job=job)
        if provider_result is None:
            self._finalize_failed_run(
                job=job,
                item=item,
                run=run,
                failure_code=METADATA_NORMALIZATION_CANDIDATE_SET_MISSING,
                failure_payload={"reason": "No usable extracted candidate set was available."},
                source_provider_result_id=None,
            )
            raise build_error(METADATA_NORMALIZATION_CANDIDATE_SET_MISSING)

        candidates = self.repository.list_field_candidates_for_provider_result(
            provider_result_id=provider_result.id
        )
        if not candidates:
            self._finalize_failed_run(
                job=job,
                item=item,
                run=run,
                failure_code=METADATA_NORMALIZATION_CANDIDATE_SET_MISSING,
                failure_payload={
                    "reason": "No persisted field candidates were available.",
                    "source_provider_result_id": str(provider_result.id),
                },
                source_provider_result_id=str(provider_result.id),
            )
            raise build_error(METADATA_NORMALIZATION_CANDIDATE_SET_MISSING)

        try:
            with self.session.begin_nested():
                normalized_values = {
                    candidate.field_name: normalize_field_value(
                        field_name=candidate.field_name,
                        raw_value=candidate.raw_value,
                        applicability_state=candidate.applicability_state,
                        confidence=candidate.confidence,
                    )
                    for candidate in candidates
                }
                normalized_values = self._reconcile_taxonomy(normalized_values)
                issue_notes = self._update_candidates(
                    candidates=candidates,
                    normalized_values=normalized_values,
                )
                self._materialize_field_states(item=item, normalized_values=normalized_values)
                self.repository.upsert_metadata_projection(
                    item=item,
                    taxonomy_version=TAXONOMY_VERSION,
                )
        except Exception as exc:
            self._finalize_failed_run(
                job=job,
                item=item,
                run=run,
                failure_code="metadata_normalization_unhandled_error",
                failure_payload={
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "source_provider_result_id": str(provider_result.id),
                },
                source_provider_result_id=str(provider_result.id),
            )
            raise

        self._finalize_success_run(
            job=job,
            item=item,
            run=run,
            source_provider_result_id=str(provider_result.id),
            issue_notes=issue_notes,
        )

    def _load_source_provider_result(
        self,
        *,
        item: ClosetItem,
        job: ClosetJob,
    ) -> ProviderResult | None:
        payload = job.payload if isinstance(job.payload, dict) else {}
        source_provider_result_id = payload.get("source_provider_result_id")
        provider_result: ProviderResult | None = None
        if isinstance(source_provider_result_id, str):
            try:
                provider_result = self.repository.get_provider_result(
                    provider_result_id=UUID(source_provider_result_id)
                )
            except ValueError:
                provider_result = None

        if provider_result is None:
            provider_result = self.repository.get_latest_usable_provider_result_for_item_task(
                closet_item_id=item.id,
                task_type=METADATA_EXTRACTION_TASK_TYPE,
            )

        if provider_result is None:
            return None
        if (
            provider_result.task_type != METADATA_EXTRACTION_TASK_TYPE
            or provider_result.status
            not in {ProviderResultStatus.SUCCEEDED, ProviderResultStatus.PARTIAL}
        ):
            return None
        return provider_result

    def _reconcile_taxonomy(
        self,
        normalized_values: dict[str, NormalizedFieldValue],
    ) -> dict[str, NormalizedFieldValue]:
        subcategory_value = normalized_values.get("subcategory")
        category_value = normalized_values.get("category")
        if subcategory_value is None:
            return normalized_values
        if subcategory_value.applicability_state != ApplicabilityState.VALUE:
            return normalized_values
        if not isinstance(subcategory_value.canonical_value, str):
            return normalized_values

        derived_category = derive_category_for_subcategory(subcategory_value.canonical_value)
        if derived_category is None:
            return normalized_values

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
            return normalized_values

        if category_value.applicability_state != ApplicabilityState.VALUE:
            return normalized_values

        if category_value.canonical_value is None:
            normalized_values["category"] = replace(
                category_value,
                canonical_value=derived_category,
                confidence=subcategory_value.confidence,
                notes=category_value.notes
                + (
                    f"Derived category '{derived_category}' from subcategory "
                    f"'{subcategory_value.canonical_value}'.",
                ),
            )
            return normalized_values

        if category_value.canonical_value == derived_category:
            return normalized_values

        normalized_values["category"] = replace(
            category_value,
            canonical_value=derived_category,
            confidence=_lower_confidence(category_value.confidence, subcategory_value.confidence),
            notes=category_value.notes
            + (
                f"Category conflicted with subcategory '{subcategory_value.canonical_value}' and "
                f"was resolved to '{derived_category}'.",
            ),
        )
        return normalized_values

    def _update_candidates(
        self,
        *,
        candidates: list[ClosetItemFieldCandidate],
        normalized_values: dict[str, NormalizedFieldValue],
    ) -> list[str]:
        for candidate in candidates:
            normalized_value = normalized_values.get(candidate.field_name)
            if normalized_value is None:
                continue

            candidate.normalized_candidate = (
                normalized_value.canonical_value
                if normalized_value.applicability_state == ApplicabilityState.VALUE
                else None
            )
            candidate.conflict_notes = _merge_notes(
                candidate.conflict_notes,
                normalized_value.notes,
            )

        self.session.flush()
        issue_notes: list[str] = []
        for normalized_value in normalized_values.values():
            for note in normalized_value.notes:
                if note not in issue_notes:
                    issue_notes.append(note)
        return issue_notes

    def _materialize_field_states(
        self,
        *,
        item: ClosetItem,
        normalized_values: dict[str, NormalizedFieldValue],
    ) -> None:
        existing_field_states = {
            field_state.field_name: field_state
            for field_state in self.repository.list_field_states(closet_item_id=item.id)
        }
        for field_name in SUPPORTED_FIELD_ORDER:
            existing_field_state = existing_field_states.get(field_name)
            if _preserve_user_state(existing_field_state):
                continue

            normalized_value = normalized_values.get(field_name)
            if normalized_value is None:
                self.repository.upsert_field_state(
                    closet_item_id=item.id,
                    field_name=field_name,
                    canonical_value=None,
                    source=FieldSource.SYSTEM,
                    confidence=None,
                    review_state=FieldReviewState.SYSTEM_UNSET,
                    applicability_state=ApplicabilityState.UNKNOWN,
                    taxonomy_version=TAXONOMY_VERSION,
                )
                continue

            if normalized_value.applicability_state in {
                ApplicabilityState.UNKNOWN,
                ApplicabilityState.NOT_APPLICABLE,
            }:
                self.repository.upsert_field_state(
                    closet_item_id=item.id,
                    field_name=field_name,
                    canonical_value=None,
                    source=FieldSource.PROVIDER,
                    confidence=normalized_value.confidence,
                    review_state=FieldReviewState.PENDING_USER,
                    applicability_state=normalized_value.applicability_state,
                    taxonomy_version=TAXONOMY_VERSION,
                )
                continue

            if _has_canonical_value(normalized_value.canonical_value):
                self.repository.upsert_field_state(
                    closet_item_id=item.id,
                    field_name=field_name,
                    canonical_value=normalized_value.canonical_value,
                    source=FieldSource.PROVIDER,
                    confidence=normalized_value.confidence,
                    review_state=FieldReviewState.PENDING_USER,
                    applicability_state=ApplicabilityState.VALUE,
                    taxonomy_version=TAXONOMY_VERSION,
                )
                continue

            self.repository.upsert_field_state(
                closet_item_id=item.id,
                field_name=field_name,
                canonical_value=None,
                source=FieldSource.SYSTEM,
                confidence=None,
                review_state=FieldReviewState.SYSTEM_UNSET,
                applicability_state=ApplicabilityState.UNKNOWN,
                taxonomy_version=TAXONOMY_VERSION,
            )

        item.review_status = self._compute_review_status(item=item)
        self.session.flush()

    def _compute_review_status(self, *, item: ClosetItem) -> Any:
        if item.lifecycle_status == LifecycleStatus.CONFIRMED:
            return ReviewStatus.CONFIRMED

        field_states = {
            field_state.field_name: field_state
            for field_state in self.repository.list_field_states(closet_item_id=item.id)
        }
        has_primary_image = self.repository.has_active_primary_image(item=item)
        missing_required_fields = {
            field_name
            for field_name in REQUIRED_CONFIRMATION_FIELDS
            if not is_confirmed_field_state(field_states.get(field_name))
        }
        if has_primary_image and not missing_required_fields:
            return ReviewStatus.READY_TO_CONFIRM
        return ReviewStatus.NEEDS_REVIEW

    def _resolve_normalization_status(
        self,
        *,
        latest_run: ProcessingRun | None,
        pending_or_running_job: ClosetJob | None,
    ) -> str:
        if pending_or_running_job is not None:
            if pending_or_running_job.status == ClosetJobStatus.RUNNING:
                return "running"
            return "pending"
        if latest_run is None:
            return "not_requested"
        return latest_run.status.value

    def _ordered_field_states(self, *, item: ClosetItem) -> list[ClosetItemFieldState]:
        order_map = {field_name: index for index, field_name in enumerate(SUPPORTED_FIELD_ORDER)}
        return sorted(
            self.repository.list_field_states(closet_item_id=item.id),
            key=lambda field_state: (
                order_map.get(field_state.field_name, len(order_map)),
                field_state.field_name,
            ),
        )

    def _latest_materialized_source_provider_result_id(self, *, item: ClosetItem) -> str | None:
        for job in self.job_repository.list_jobs_for_item_kind(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.NORMALIZATION_PROJECTION,
        ):
            if job.status != ClosetJobStatus.COMPLETED or not isinstance(job.payload, dict):
                continue
            result_status = job.payload.get("result_status")
            source_provider_result_id = job.payload.get("source_provider_result_id")
            if result_status not in {
                ProcessingStatus.COMPLETED.value,
                ProcessingStatus.COMPLETED_WITH_ISSUES.value,
            }:
                continue
            if isinstance(source_provider_result_id, str):
                return source_provider_result_id
        return None

    def _finalize_success_run(
        self,
        *,
        job: ClosetJob,
        item: ClosetItem,
        run: ProcessingRun,
        source_provider_result_id: str,
        issue_notes: list[str],
    ) -> None:
        unique_issue_notes: list[str] = []
        for note in issue_notes:
            if note not in unique_issue_notes:
                unique_issue_notes.append(note)

        run.status = (
            ProcessingStatus.COMPLETED_WITH_ISSUES
            if unique_issue_notes
            else ProcessingStatus.COMPLETED
        )
        run.completed_at = utcnow()
        run.failure_code = "metadata_normalization_issues" if unique_issue_notes else None
        run.failure_payload = (
            {
                "issues": unique_issue_notes,
                "source_provider_result_id": source_provider_result_id,
            }
            if unique_issue_notes
            else None
        )
        self._update_job_payload(
            job=job,
            source_provider_result_id=source_provider_result_id,
            result_status=run.status.value,
            processing_run_id=str(run.id),
        )
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.WORKER,
            actor_user_id=None,
            event_type=(
                "metadata_normalization_completed_with_issues"
                if unique_issue_notes
                else "metadata_normalization_completed"
            ),
            payload={
                "processing_run_id": str(run.id),
                "source_provider_result_id": source_provider_result_id,
                "issue_count": len(unique_issue_notes),
            },
        )
        self.session.flush()

    def _finalize_failed_run(
        self,
        *,
        job: ClosetJob,
        item: ClosetItem,
        run: ProcessingRun,
        failure_code: str,
        failure_payload: dict[str, Any] | None,
        source_provider_result_id: str | None,
    ) -> None:
        run.status = ProcessingStatus.FAILED
        run.completed_at = utcnow()
        run.failure_code = failure_code
        run.failure_payload = failure_payload
        self._update_job_payload(
            job=job,
            source_provider_result_id=source_provider_result_id,
            result_status=ProcessingStatus.FAILED.value,
            processing_run_id=str(run.id),
        )
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.WORKER,
            actor_user_id=None,
            event_type="metadata_normalization_failed",
            payload={
                "processing_run_id": str(run.id),
                "failure_code": failure_code,
                "source_provider_result_id": source_provider_result_id,
            },
        )
        self.session.flush()

    def _update_job_payload(
        self,
        *,
        job: ClosetJob,
        source_provider_result_id: str | None,
        result_status: str,
        processing_run_id: str,
    ) -> None:
        payload = job.payload.copy() if isinstance(job.payload, dict) else {}
        payload["result_status"] = result_status
        payload["processing_run_id"] = processing_run_id
        if source_provider_result_id is not None:
            payload["source_provider_result_id"] = source_provider_result_id
        job.payload = payload
        self.session.flush()


def _has_canonical_value(value: Any | None) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    return True


def _preserve_user_state(field_state: ClosetItemFieldState | None) -> bool:
    if field_state is None:
        return False
    if field_state.source == FieldSource.USER:
        return True
    return field_state.review_state in {
        FieldReviewState.USER_CONFIRMED,
        FieldReviewState.USER_EDITED,
    }


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
