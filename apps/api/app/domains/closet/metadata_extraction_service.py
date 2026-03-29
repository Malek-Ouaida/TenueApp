from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Sequence
from uuid import UUID

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient
from app.domains.closet.errors import (
    CLOSET_ITEM_NOT_FOUND,
    IDEMPOTENCY_CONFLICT,
    INVALID_LIFECYCLE_TRANSITION,
    METADATA_EXTRACTION_ALREADY_SCHEDULED,
    METADATA_EXTRACTION_NOT_READY,
    METADATA_EXTRACTION_SOURCE_MISSING,
    build_error,
)
from app.domains.closet.metadata_extraction import (
    METADATA_EXTRACTION_TASK_TYPE,
    MetadataExtractionProvider,
    MetadataExtractionResult,
)
from app.domains.closet.models import (
    ApplicabilityState,
    AuditActorType,
    ClosetItem,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetJob,
    ClosetJobStatus,
    LifecycleStatus,
    MediaAsset,
    ProcessingRun,
    ProcessingRunType,
    ProcessingStatus,
    ProviderResult,
    ProviderResultStatus,
    utcnow,
)
from app.domains.closet.normalization_service import ClosetNormalizationService
from app.domains.closet.repository import ClosetJobRepository, ClosetRepository
from app.domains.closet.taxonomy import SUPPORTED_FIELD_NAMES

REEXTRACT_METADATA_OPERATION = "reextract_metadata_extraction"
REEXTRACT_RESOURCE_TYPE = "closet_item"

LIST_FIELD_NAMES = frozenset({"colors", "style_tags", "occasion_tags", "season_tags"})


@dataclass(frozen=True)
class ExtractionSnapshotImage:
    asset_id: UUID
    role: str
    mime_type: str
    width: int | None
    height: int | None
    url: str
    expires_at: Any


@dataclass(frozen=True)
class ExtractionSnapshotRun:
    id: UUID
    run_type: str
    status: str
    retry_count: int
    started_at: Any
    completed_at: Any
    failure_code: str | None


@dataclass(frozen=True)
class ExtractionSnapshotProviderResult:
    id: UUID
    provider_name: str
    provider_model: str | None
    provider_version: str | None
    task_type: str
    status: str
    raw_payload: Any
    created_at: Any


@dataclass(frozen=True)
class ExtractionFieldCandidateSnapshot:
    id: UUID
    field_name: str
    raw_value: Any
    normalized_candidate: Any
    confidence: float | None
    applicability_state: str
    conflict_notes: str | None
    provider_result_id: UUID | None
    created_at: Any


@dataclass(frozen=True)
class ExtractionCurrentCandidateSet:
    provider_result_id: UUID
    status: str
    created_at: Any
    field_candidates: list[ExtractionFieldCandidateSnapshot]


@dataclass(frozen=True)
class ExtractionSnapshot:
    item_id: UUID
    lifecycle_status: str
    review_status: str
    extraction_status: str
    normalization_status: str
    field_states_stale: bool
    can_reextract: bool
    source_image: ExtractionSnapshotImage | None
    latest_run: ExtractionSnapshotRun | None
    latest_normalization_run: ProcessingRun | None
    provider_results: list[ExtractionSnapshotProviderResult]
    current_candidate_set: ExtractionCurrentCandidateSet | None
    current_field_states: Sequence[Any]
    metadata_projection: object | None


@dataclass(frozen=True)
class ParsedFieldCandidate:
    field_name: str
    raw_value: Any
    confidence: float | None
    applicability_state: ApplicabilityState
    conflict_notes: str | None


@dataclass(frozen=True)
class ParsedCandidateSet:
    status: ProviderResultStatus
    candidates: list[ParsedFieldCandidate]
    warnings: list[str]
    ignored_fields: list[str]
    failure_code: str | None


@dataclass(frozen=True)
class LoadedImageResult:
    image_bytes: bytes | None
    mime_type: str | None
    error_code: str | None
    failure_payload: dict[str, Any] | None


class ClosetMetadataExtractionService:
    def __init__(
        self,
        *,
        session: Session,
        repository: ClosetRepository,
        job_repository: ClosetJobRepository,
        storage: ObjectStorageClient,
        metadata_provider: MetadataExtractionProvider,
        normalization_service: ClosetNormalizationService,
    ) -> None:
        self.session = session
        self.repository = repository
        self.job_repository = job_repository
        self.storage = storage
        self.metadata_provider = metadata_provider
        self.normalization_service = normalization_service

    def enqueue_extraction_for_item(
        self,
        *,
        item: ClosetItem,
        actor_type: AuditActorType,
        actor_user_id: UUID | None,
        raise_on_duplicate: bool,
    ) -> bool:
        if item.lifecycle_status == LifecycleStatus.ARCHIVED:
            raise build_error(INVALID_LIFECYCLE_TRANSITION)
        if item.lifecycle_status == LifecycleStatus.PROCESSING or item.processing_status in {
            ProcessingStatus.PENDING,
            ProcessingStatus.RUNNING,
        }:
            raise build_error(METADATA_EXTRACTION_NOT_READY)

        source_image = self._select_source_image_record(item=item)
        if source_image is None:
            raise build_error(METADATA_EXTRACTION_SOURCE_MISSING)

        if self.job_repository.has_pending_or_running_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.METADATA_EXTRACTION,
        ):
            if raise_on_duplicate:
                raise build_error(METADATA_EXTRACTION_ALREADY_SCHEDULED)
            return False

        self.job_repository.enqueue_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.METADATA_EXTRACTION,
        )
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            event_type="metadata_extraction_enqueued",
            payload={
                "job_kind": ProcessingRunType.METADATA_EXTRACTION.value,
                "source_role": source_image[0].role.value,
            },
        )
        return True

    def get_extraction_snapshot(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
    ) -> ExtractionSnapshot:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        latest_run = self.repository.get_latest_processing_run(
            closet_item_id=item.id,
            run_type=ProcessingRunType.METADATA_EXTRACTION,
        )
        provider_results = (
            self.repository.list_provider_results_for_run(processing_run_id=latest_run.id)
            if latest_run is not None
            else []
        )
        pending_or_running_job = self.job_repository.get_pending_or_running_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.METADATA_EXTRACTION,
        )
        latest_usable_result = self.repository.get_latest_usable_provider_result_for_item_task(
            closet_item_id=item.id,
            task_type=METADATA_EXTRACTION_TASK_TYPE,
        )
        current_candidate_set = self._build_current_candidate_set(latest_usable_result)
        normalization_summary = self.normalization_service.get_summary_for_item(item=item)

        return ExtractionSnapshot(
            item_id=item.id,
            lifecycle_status=item.lifecycle_status.value,
            review_status=item.review_status.value,
            extraction_status=self._resolve_extraction_status(
                latest_run=latest_run,
                pending_or_running_job=pending_or_running_job,
            ),
            normalization_status=normalization_summary.normalization_status,
            field_states_stale=normalization_summary.field_states_stale,
            can_reextract=self._can_reextract(item=item),
            source_image=self._build_image_snapshot(self._select_source_image_record(item=item)),
            latest_run=self._build_run_snapshot(latest_run),
            latest_normalization_run=normalization_summary.latest_run,
            provider_results=[
                ExtractionSnapshotProviderResult(
                    id=provider_result.id,
                    provider_name=provider_result.provider_name,
                    provider_model=provider_result.provider_model,
                    provider_version=provider_result.provider_version,
                    task_type=provider_result.task_type,
                    status=provider_result.status.value,
                    raw_payload=provider_result.raw_payload,
                    created_at=provider_result.created_at,
                )
                for provider_result in provider_results
            ],
            current_candidate_set=current_candidate_set,
            current_field_states=normalization_summary.current_field_states,
            metadata_projection=normalization_summary.metadata_projection,
        )

    def reextract_item(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> tuple[ExtractionSnapshot, int]:
        request_fingerprint = hash_request_payload({"item_id": str(item_id)})
        replay = self.repository.get_idempotency_record(
            user_id=user_id,
            operation=REEXTRACT_METADATA_OPERATION,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            self._ensure_matching_idempotency(replay.request_fingerprint, request_fingerprint)
            return (
                self.get_extraction_snapshot(item_id=replay.resource_id, user_id=user_id),
                replay.response_status_code,
            )

        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        self._ensure_item_can_reextract(item=item)
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="metadata_reextract_requested",
            payload={"processing_status": item.processing_status.value},
        )
        self.enqueue_extraction_for_item(
            item=item,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            raise_on_duplicate=True,
        )
        self.repository.create_idempotency_record(
            user_id=user_id,
            operation=REEXTRACT_METADATA_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            resource_type=REEXTRACT_RESOURCE_TYPE,
            resource_id=item.id,
            response_status_code=202,
        )
        self.session.commit()
        return self.get_extraction_snapshot(item_id=item.id, user_id=user_id), 202

    def handle_metadata_extraction_job(self, *, job: ClosetJob) -> None:
        item = self.repository.get_item(item_id=job.closet_item_id)
        if item is None:
            raise build_error(CLOSET_ITEM_NOT_FOUND)

        now = utcnow()
        retry_count = self.repository.count_processing_runs(
            closet_item_id=item.id,
            run_type=ProcessingRunType.METADATA_EXTRACTION,
        )
        run = self.repository.create_processing_run(
            closet_item_id=item.id,
            run_type=ProcessingRunType.METADATA_EXTRACTION,
            status=ProcessingStatus.RUNNING,
            retry_count=retry_count,
            started_at=now,
        )
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.WORKER,
            actor_user_id=None,
            event_type="metadata_extraction_started",
            payload={"processing_run_id": str(run.id)},
        )

        source_image = self._select_source_image_record(item=item)
        if source_image is None:
            provider_result = self.repository.create_provider_result(
                closet_item_id=item.id,
                processing_run_id=run.id,
                provider_name=getattr(self.metadata_provider, "provider_name", "unknown"),
                provider_model=None,
                provider_version=None,
                task_type=METADATA_EXTRACTION_TASK_TYPE,
                status=ProviderResultStatus.FAILED,
                raw_payload={"reason_code": "source_missing"},
            )
            self._finalize_failed_run(
                item=item,
                run=run,
                provider_result=provider_result,
                failure_code=METADATA_EXTRACTION_SOURCE_MISSING,
                failure_payload={"reason": "No source image was available."},
            )
            return

        _, source_asset = source_image
        loaded_image = self._load_provider_image(asset=source_asset)
        if loaded_image.image_bytes is None or loaded_image.mime_type is None:
            provider_result = self.repository.create_provider_result(
                closet_item_id=item.id,
                processing_run_id=run.id,
                provider_name=getattr(self.metadata_provider, "provider_name", "unknown"),
                provider_model=None,
                provider_version=None,
                task_type=METADATA_EXTRACTION_TASK_TYPE,
                status=ProviderResultStatus.FAILED,
                raw_payload=loaded_image.failure_payload or {"reason_code": "image_load_failed"},
            )
            self._finalize_failed_run(
                item=item,
                run=run,
                provider_result=provider_result,
                failure_code=loaded_image.error_code or "metadata_source_invalid",
                failure_payload=loaded_image.failure_payload,
            )
            return

        provider_response = self._attempt_provider(
            image_bytes=loaded_image.image_bytes,
            mime_type=loaded_image.mime_type,
            filename=f"{item.id}-metadata",
        )
        parsed_candidates = self._parse_field_candidates(provider_response.raw_fields)
        provider_payload = {
            **provider_response.sanitized_payload,
            "candidate_fields": [
                candidate.field_name for candidate in parsed_candidates.candidates
            ],
            "ignored_fields": parsed_candidates.ignored_fields,
        }
        if parsed_candidates.warnings:
            provider_payload["warnings"] = parsed_candidates.warnings

        persisted_result = self.repository.create_provider_result(
            closet_item_id=item.id,
            processing_run_id=run.id,
            provider_name=provider_response.provider_name,
            provider_model=provider_response.provider_model,
            provider_version=provider_response.provider_version,
            task_type=METADATA_EXTRACTION_TASK_TYPE,
            status=parsed_candidates.status,
            raw_payload=provider_payload,
        )

        for candidate in parsed_candidates.candidates:
            self.repository.create_field_candidate(
                closet_item_id=item.id,
                field_name=candidate.field_name,
                raw_value=candidate.raw_value,
                normalized_candidate=None,
                confidence=candidate.confidence,
                provider_result_id=persisted_result.id,
                applicability_state=candidate.applicability_state,
                conflict_notes=candidate.conflict_notes,
            )

        if parsed_candidates.status == ProviderResultStatus.SUCCEEDED:
            run.status = ProcessingStatus.COMPLETED
            run.completed_at = utcnow()
            run.failure_code = None
            run.failure_payload = None
            self.repository.create_audit_event(
                closet_item_id=item.id,
                actor_type=AuditActorType.WORKER,
                actor_user_id=None,
                event_type="metadata_extraction_completed",
                payload={
                    "processing_run_id": str(run.id),
                    "provider_result_id": str(persisted_result.id),
                },
            )
            try:
                self.normalization_service.enqueue_normalization_for_provider_result(
                    item=item,
                    provider_result=persisted_result,
                    actor_type=AuditActorType.WORKER,
                    actor_user_id=None,
                    raise_on_duplicate=False,
                )
            except Exception:
                pass
            return

        if parsed_candidates.status == ProviderResultStatus.PARTIAL:
            run.status = ProcessingStatus.COMPLETED_WITH_ISSUES
            run.completed_at = utcnow()
            run.failure_code = parsed_candidates.failure_code or "metadata_extraction_partial"
            run.failure_payload = {"warnings": parsed_candidates.warnings}
            self.repository.create_audit_event(
                closet_item_id=item.id,
                actor_type=AuditActorType.WORKER,
                actor_user_id=None,
                event_type="metadata_extraction_completed_with_issues",
                payload={
                    "processing_run_id": str(run.id),
                    "provider_result_id": str(persisted_result.id),
                },
            )
            try:
                self.normalization_service.enqueue_normalization_for_provider_result(
                    item=item,
                    provider_result=persisted_result,
                    actor_type=AuditActorType.WORKER,
                    actor_user_id=None,
                    raise_on_duplicate=False,
                )
            except Exception:
                pass
            return

        self._finalize_failed_run(
            item=item,
            run=run,
            provider_result=persisted_result,
            failure_code=parsed_candidates.failure_code or "metadata_extraction_empty_result",
            failure_payload={"warnings": parsed_candidates.warnings},
        )

    def _build_current_candidate_set(
        self,
        provider_result: ProviderResult | None,
    ) -> ExtractionCurrentCandidateSet | None:
        if provider_result is None:
            return None

        field_candidates = [
            ExtractionFieldCandidateSnapshot(
                id=candidate.id,
                field_name=candidate.field_name,
                raw_value=candidate.raw_value,
                normalized_candidate=candidate.normalized_candidate,
                confidence=candidate.confidence,
                applicability_state=candidate.applicability_state.value,
                conflict_notes=candidate.conflict_notes,
                provider_result_id=candidate.provider_result_id,
                created_at=candidate.created_at,
            )
            for candidate in self.repository.list_field_candidates_for_provider_result(
                provider_result_id=provider_result.id
            )
        ]
        return ExtractionCurrentCandidateSet(
            provider_result_id=provider_result.id,
            status=provider_result.status.value,
            created_at=provider_result.created_at,
            field_candidates=field_candidates,
        )

    def _resolve_extraction_status(
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

    def _can_reextract(self, *, item: ClosetItem) -> bool:
        if item.lifecycle_status == LifecycleStatus.ARCHIVED:
            return False
        if item.lifecycle_status == LifecycleStatus.PROCESSING or item.processing_status in {
            ProcessingStatus.PENDING,
            ProcessingStatus.RUNNING,
        }:
            return False
        if self._select_source_image_record(item=item) is None:
            return False
        return not self.job_repository.has_pending_or_running_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.METADATA_EXTRACTION,
        )

    def _ensure_item_can_reextract(self, *, item: ClosetItem) -> None:
        if item.lifecycle_status == LifecycleStatus.ARCHIVED:
            raise build_error(INVALID_LIFECYCLE_TRANSITION)
        if item.lifecycle_status == LifecycleStatus.PROCESSING or item.processing_status in {
            ProcessingStatus.PENDING,
            ProcessingStatus.RUNNING,
        }:
            raise build_error(METADATA_EXTRACTION_NOT_READY)
        if self._select_source_image_record(item=item) is None:
            raise build_error(METADATA_EXTRACTION_SOURCE_MISSING)
        if self.job_repository.has_pending_or_running_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.METADATA_EXTRACTION,
        ):
            raise build_error(METADATA_EXTRACTION_ALREADY_SCHEDULED)

    def _select_source_image_record(
        self,
        *,
        item: ClosetItem,
    ) -> tuple[ClosetItemImage, MediaAsset] | None:
        original_image = self.repository.get_primary_image_asset(item=item)
        if (
            item.processing_status == ProcessingStatus.COMPLETED_WITH_ISSUES
            and original_image is not None
        ):
            return original_image
        processed_image = self.repository.get_active_image_asset_by_role(
            closet_item_id=item.id,
            role=ClosetItemImageRole.PROCESSED,
        )
        if processed_image is not None:
            return processed_image
        return original_image

    def _attempt_provider(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str,
    ) -> MetadataExtractionResult:
        try:
            return self.metadata_provider.extract_metadata(
                image_bytes=image_bytes,
                filename=filename,
                mime_type=mime_type,
            )
        except Exception as exc:
            return MetadataExtractionResult(
                provider_name=getattr(self.metadata_provider, "provider_name", "unknown"),
                provider_model=None,
                provider_version=None,
                status=ProviderResultStatus.FAILED,
                sanitized_payload={
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                raw_fields=None,
            )

    def _parse_field_candidates(self, raw_fields: dict[str, Any] | None) -> ParsedCandidateSet:
        if not isinstance(raw_fields, dict):
            return ParsedCandidateSet(
                status=ProviderResultStatus.FAILED,
                candidates=[],
                warnings=["No structured extraction payload was available."],
                ignored_fields=[],
                failure_code="metadata_extraction_invalid_payload",
            )

        candidates: list[ParsedFieldCandidate] = []
        warnings: list[str] = []
        ignored_fields: list[str] = []

        for field_name, raw_field in raw_fields.items():
            if field_name not in SUPPORTED_FIELD_NAMES:
                ignored_fields.append(str(field_name))
                continue

            candidate, candidate_warning = self._parse_single_field(
                field_name=field_name,
                raw_field=raw_field,
            )
            if candidate is None:
                if candidate_warning is not None:
                    warnings.append(candidate_warning)
                continue
            candidates.append(candidate)
            if candidate_warning is not None:
                warnings.append(candidate_warning)

        if not candidates:
            return ParsedCandidateSet(
                status=ProviderResultStatus.FAILED,
                candidates=[],
                warnings=warnings or ["No usable field candidates were recovered."],
                ignored_fields=ignored_fields,
                failure_code="metadata_extraction_empty_result",
            )

        status = ProviderResultStatus.PARTIAL if warnings else ProviderResultStatus.SUCCEEDED
        return ParsedCandidateSet(
            status=status,
            candidates=candidates,
            warnings=warnings,
            ignored_fields=ignored_fields,
            failure_code="metadata_extraction_partial" if warnings else None,
        )

    def _parse_single_field(
        self,
        *,
        field_name: str,
        raw_field: Any,
    ) -> tuple[ParsedFieldCandidate | None, str | None]:
        warnings: list[str] = []
        payload = raw_field if isinstance(raw_field, dict) else {"value": raw_field}
        if not isinstance(payload, dict):
            return None, f"{field_name}: extraction payload was not parseable."

        applicability_state = self._parse_applicability_state(
            payload.get("applicability_state"),
            field_name=field_name,
            warnings=warnings,
        )
        confidence = self._parse_confidence(
            payload.get("confidence"),
            field_name=field_name,
            warnings=warnings,
        )

        notes = payload.get("notes")
        if isinstance(notes, str) and notes.strip():
            warnings.append(f"{field_name}: {notes.strip()}")

        if field_name in LIST_FIELD_NAMES:
            raw_value_list = self._sanitize_list_value(payload.get("values", payload.get("value")))
            if applicability_state == ApplicabilityState.VALUE and not raw_value_list:
                return None, f"{field_name}: expected non-empty list values."
            raw_value: Any = raw_value_list
        else:
            raw_value_scalar = self._sanitize_scalar_value(
                payload.get("value", payload.get("values"))
            )
            if applicability_state == ApplicabilityState.VALUE and raw_value_scalar is None:
                return None, f"{field_name}: expected a non-empty scalar value."
            raw_value = raw_value_scalar

        return (
            ParsedFieldCandidate(
                field_name=field_name,
                raw_value=raw_value,
                confidence=confidence,
                applicability_state=applicability_state,
                conflict_notes=" ".join(warnings) if warnings else None,
            ),
            None,
        )

    def _parse_applicability_state(
        self,
        value: Any,
        *,
        field_name: str,
        warnings: list[str],
    ) -> ApplicabilityState:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == ApplicabilityState.VALUE.value:
                return ApplicabilityState.VALUE
            if normalized == ApplicabilityState.UNKNOWN.value:
                return ApplicabilityState.UNKNOWN
            if normalized == ApplicabilityState.NOT_APPLICABLE.value:
                return ApplicabilityState.NOT_APPLICABLE
            warnings.append(f"{field_name}: unsupported applicability_state '{value}'.")
        return ApplicabilityState.VALUE

    def _parse_confidence(
        self,
        value: Any,
        *,
        field_name: str,
        warnings: list[str],
    ) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if 0 <= float(value) <= 1:
                return float(value)
            warnings.append(f"{field_name}: confidence was outside the 0..1 range.")
            return None
        warnings.append(f"{field_name}: confidence was not numeric.")
        return None

    def _sanitize_list_value(self, value: Any) -> list[str] | None:
        values: list[str] = []
        if isinstance(value, str):
            stripped = value.strip()
            values = [stripped] if stripped else []
        elif isinstance(value, list):
            for item in value:
                if not isinstance(item, str):
                    continue
                stripped = item.strip()
                if stripped:
                    values.append(stripped)

        deduped: list[str] = []
        seen: set[str] = set()
        for item in values:
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped or None

    def _sanitize_scalar_value(self, value: Any) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    stripped = item.strip()
                    if stripped:
                        return stripped
        return None

    def _load_provider_image(self, *, asset: MediaAsset) -> LoadedImageResult:
        try:
            content = self.storage.get_object_bytes(bucket=asset.bucket, key=asset.key)
        except FileNotFoundError:
            return LoadedImageResult(
                image_bytes=None,
                mime_type=None,
                error_code="metadata_source_missing",
                failure_payload={"bucket": asset.bucket, "key": asset.key},
            )

        try:
            with Image.open(BytesIO(content)) as image:
                image.load()
                normalized = ImageOps.exif_transpose(image)
                if (
                    normalized.width > settings.closet_metadata_extraction_max_edge
                    or normalized.height > settings.closet_metadata_extraction_max_edge
                ):
                    normalized.thumbnail(
                        (
                            settings.closet_metadata_extraction_max_edge,
                            settings.closet_metadata_extraction_max_edge,
                        ),
                        Image.Resampling.LANCZOS,
                    )
                encoded_bytes, mime_type = self._encode_provider_image(normalized)
        except (UnidentifiedImageError, OSError) as exc:
            return LoadedImageResult(
                image_bytes=None,
                mime_type=None,
                error_code="metadata_source_decode_failed",
                failure_payload={"message": str(exc)},
            )

        return LoadedImageResult(
            image_bytes=encoded_bytes,
            mime_type=mime_type,
            error_code=None,
            failure_payload=None,
        )

    def _encode_provider_image(self, image: Image.Image) -> tuple[bytes, str]:
        has_alpha = "A" in image.getbands()
        buffer = BytesIO()
        if has_alpha:
            image.convert("RGBA").save(buffer, format="PNG")
            return buffer.getvalue(), "image/png"
        image.convert("RGB").save(buffer, format="JPEG", quality=90)
        return buffer.getvalue(), "image/jpeg"

    def _build_image_snapshot(
        self,
        image_record: tuple[ClosetItemImage, MediaAsset] | None,
    ) -> ExtractionSnapshotImage | None:
        if image_record is None:
            return None
        item_image, asset = image_record
        presigned_download = self.storage.generate_presigned_download(
            bucket=asset.bucket,
            key=asset.key,
            expires_in_seconds=settings.closet_media_download_ttl_seconds,
        )
        return ExtractionSnapshotImage(
            asset_id=asset.id,
            role=item_image.role.value,
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            url=presigned_download.url,
            expires_at=presigned_download.expires_at,
        )

    def _build_run_snapshot(self, run: ProcessingRun | None) -> ExtractionSnapshotRun | None:
        if run is None:
            return None
        return ExtractionSnapshotRun(
            id=run.id,
            run_type=run.run_type.value,
            status=run.status.value,
            retry_count=run.retry_count,
            started_at=run.started_at,
            completed_at=run.completed_at,
            failure_code=run.failure_code,
        )

    def _finalize_failed_run(
        self,
        *,
        item: ClosetItem,
        run: ProcessingRun,
        provider_result: ProviderResult,
        failure_code: str,
        failure_payload: dict[str, Any] | None,
    ) -> None:
        run.status = ProcessingStatus.FAILED
        run.completed_at = utcnow()
        run.failure_code = failure_code
        run.failure_payload = failure_payload
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.WORKER,
            actor_user_id=None,
            event_type="metadata_extraction_failed",
            payload={
                "processing_run_id": str(run.id),
                "provider_result_id": str(provider_result.id),
                "failure_code": failure_code,
            },
        )

    def _ensure_matching_idempotency(
        self,
        expected_fingerprint: str,
        actual_fingerprint: str,
    ) -> None:
        if expected_fingerprint != actual_fingerprint:
            raise build_error(IDEMPOTENCY_CONFLICT)


def hash_request_payload(payload: dict[str, object | None]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
