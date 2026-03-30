from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient
from app.domains.closet.background_removal import (
    BACKGROUND_REMOVAL_TASK_TYPE,
    BackgroundRemovalProvider,
    BackgroundRemovalResult,
)
from app.domains.closet.errors import (
    CLOSET_ITEM_NOT_FOUND,
    IDEMPOTENCY_CONFLICT,
    INVALID_LIFECYCLE_TRANSITION,
    MISSING_PRIMARY_IMAGE,
    PROCESSING_ALREADY_SCHEDULED,
    build_error,
)
from app.domains.closet.metadata_extraction_service import ClosetMetadataExtractionService
from app.domains.closet.models import (
    AuditActorType,
    ClosetItem,
    ClosetItemImage,
    ClosetItemImageRole,
    LifecycleStatus,
    MediaAsset,
    MediaAssetSourceKind,
    ProcessingRun,
    ProcessingRunType,
    ProcessingStatus,
    ProviderResultStatus,
    utcnow,
)
from app.domains.closet.repository import ClosetJobRepository, ClosetRepository
from app.domains.closet.service import ClosetLifecycleService

REPROCESS_IMAGE_OPERATION = "reprocess_image_processing"
REPROCESS_RESOURCE_TYPE = "closet_item"
BACKGROUND_REMOVAL_FALLBACK_SUMMARY = (
    "Background removal was unavailable, so we kept a cleaned version of the original image."
)
IMAGE_PROCESSING_FAILURE_SUMMARY = (
    "We couldn't finish processing this image. Try reprocessing it or upload a new original."
)


@dataclass(frozen=True)
class ProcessingSnapshotImage:
    asset_id: UUID
    image_id: UUID | None
    role: str
    position: int | None
    is_primary: bool
    mime_type: str
    width: int | None
    height: int | None
    url: str
    expires_at: datetime


@dataclass(frozen=True)
class ProcessingSnapshotRun:
    id: UUID
    run_type: str
    status: str
    retry_count: int
    started_at: datetime | None
    completed_at: datetime | None
    failure_code: str | None


@dataclass(frozen=True)
class ProcessingSnapshotProviderResult:
    id: UUID
    provider_name: str
    provider_model: str | None
    provider_version: str | None
    task_type: str
    status: str
    raw_payload: Any
    created_at: datetime


@dataclass(frozen=True)
class ProcessingSnapshot:
    item_id: UUID
    lifecycle_status: str
    processing_status: str
    review_status: str
    failure_summary: str | None
    can_reprocess: bool
    latest_run: ProcessingSnapshotRun | None
    provider_results: list[ProcessingSnapshotProviderResult]
    display_image: ProcessingSnapshotImage | None
    original_image: ProcessingSnapshotImage | None
    original_images: list[ProcessingSnapshotImage]
    thumbnail_image: ProcessingSnapshotImage | None


class ClosetImageProcessingService:
    def __init__(
        self,
        *,
        session: Session,
        repository: ClosetRepository,
        job_repository: ClosetJobRepository,
        lifecycle_service: ClosetLifecycleService,
        storage: ObjectStorageClient,
        background_removal_provider: BackgroundRemovalProvider,
        metadata_extraction_service: ClosetMetadataExtractionService,
    ) -> None:
        self.session = session
        self.repository = repository
        self.job_repository = job_repository
        self.lifecycle_service = lifecycle_service
        self.storage = storage
        self.background_removal_provider = background_removal_provider
        self.metadata_extraction_service = metadata_extraction_service

    def enqueue_processing_for_item(
        self,
        *,
        item: ClosetItem,
        actor_type: AuditActorType,
        actor_user_id: UUID | None,
        raise_on_duplicate: bool,
    ) -> bool:
        if self.job_repository.has_pending_or_running_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.IMAGE_PROCESSING,
        ):
            if raise_on_duplicate:
                raise build_error(PROCESSING_ALREADY_SCHEDULED)
            return False

        self.job_repository.enqueue_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.IMAGE_PROCESSING,
        )
        self.lifecycle_service.update_processing_state(
            item_id=item.id,
            user_id=item.user_id,
            processing_status=ProcessingStatus.PENDING,
            failure_summary=None,
            event_type="image_processing_enqueued",
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            payload={"job_kind": ProcessingRunType.IMAGE_PROCESSING.value},
            commit=False,
        )
        return True

    def get_processing_snapshot(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
    ) -> ProcessingSnapshot:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        if item.lifecycle_status == LifecycleStatus.ARCHIVED:
            raise build_error(CLOSET_ITEM_NOT_FOUND)

        latest_run = self.repository.get_latest_processing_run(
            closet_item_id=item.id,
            run_type=ProcessingRunType.IMAGE_PROCESSING,
        )
        provider_results = (
            self.repository.list_provider_results_for_run(processing_run_id=latest_run.id)
            if latest_run is not None
            else []
        )

        original_image = self._build_image_snapshot(
            self.repository.get_primary_image_asset(item=item),
            primary_image_id=item.primary_image_id,
        )
        original_images = self._build_original_image_snapshots(item=item)
        processed_image = self._build_image_snapshot(
            self.repository.get_active_image_asset_by_role(
                closet_item_id=item.id,
                role=ClosetItemImageRole.PROCESSED,
            )
        )
        thumbnail_image = self._build_image_snapshot(
            self.repository.get_active_image_asset_by_role(
                closet_item_id=item.id,
                role=ClosetItemImageRole.THUMBNAIL,
            )
        )

        return ProcessingSnapshot(
            item_id=item.id,
            lifecycle_status=item.lifecycle_status.value,
            processing_status=item.processing_status.value,
            review_status=item.review_status.value,
            failure_summary=item.failure_summary,
            can_reprocess=self._can_reprocess(item=item),
            latest_run=self._build_run_snapshot(latest_run),
            provider_results=[
                ProcessingSnapshotProviderResult(
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
            display_image=processed_image or original_image,
            original_image=original_image,
            original_images=original_images,
            thumbnail_image=thumbnail_image,
        )

    def reprocess_item(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> tuple[ProcessingSnapshot, int]:
        request_fingerprint = hash_request_payload({"item_id": str(item_id)})
        replay = self.repository.get_idempotency_record(
            user_id=user_id,
            operation=REPROCESS_IMAGE_OPERATION,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            self._ensure_matching_idempotency(replay.request_fingerprint, request_fingerprint)
            return (
                self.get_processing_snapshot(item_id=replay.resource_id, user_id=user_id),
                replay.response_status_code,
            )

        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        self._ensure_item_can_reprocess(item)

        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="image_reprocess_requested",
            payload={"processing_status": item.processing_status.value},
        )
        self.enqueue_processing_for_item(
            item=item,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            raise_on_duplicate=True,
        )
        self.repository.create_idempotency_record(
            user_id=user_id,
            operation=REPROCESS_IMAGE_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            resource_type=REPROCESS_RESOURCE_TYPE,
            resource_id=item.id,
            response_status_code=202,
        )
        self.session.commit()
        return self.get_processing_snapshot(item_id=item.id, user_id=user_id), 202

    def handle_image_processing_job(self, *, job: object) -> None:
        job_item_id = getattr(job, "closet_item_id")
        item = self.repository.get_item(item_id=job_item_id)
        if item is None:
            raise build_error(CLOSET_ITEM_NOT_FOUND)

        now = utcnow()
        retry_count = self.repository.count_processing_runs(
            closet_item_id=item.id,
            run_type=ProcessingRunType.IMAGE_PROCESSING,
        )
        run = self.repository.create_processing_run(
            closet_item_id=item.id,
            run_type=ProcessingRunType.IMAGE_PROCESSING,
            status=ProcessingStatus.RUNNING,
            retry_count=retry_count,
            started_at=now,
        )
        self.lifecycle_service.update_processing_state(
            item_id=item.id,
            user_id=item.user_id,
            processing_status=ProcessingStatus.RUNNING,
            failure_summary=None,
            event_type="image_processing_started",
            actor_type=AuditActorType.WORKER,
            actor_user_id=None,
            payload={"processing_run_id": str(run.id)},
            commit=False,
        )

        original_record = self.repository.get_primary_image_asset(item=item)
        if original_record is None:
            self._finalize_failed_run(
                item=item,
                run=run,
                failure_code=MISSING_PRIMARY_IMAGE,
                failure_payload={"reason": "Active original image is missing."},
            )
            return

        _, source_asset = original_record
        load_result = self._load_normalized_original(asset=source_asset)
        if load_result.error_code is not None or load_result.image_bytes is None:
            self._finalize_failed_run(
                item=item,
                run=run,
                failure_code=load_result.error_code or "source_image_invalid",
                failure_payload=load_result.failure_payload,
            )
            return

        provider_result_payload = self._attempt_background_removal(
            image_bytes=load_result.image_bytes,
            filename=f"{item.id}.png",
            mime_type=load_result.mime_type,
        )
        provider_result_payload = self._normalize_provider_result(provider_result_payload)
        self.repository.create_provider_result(
            closet_item_id=item.id,
            processing_run_id=run.id,
            provider_name=provider_result_payload.provider_name,
            provider_model=provider_result_payload.provider_model,
            provider_version=provider_result_payload.provider_version,
            task_type=BACKGROUND_REMOVAL_TASK_TYPE,
            status=provider_result_payload.status,
            raw_payload=provider_result_payload.sanitized_payload,
        )

        processed_bytes = load_result.image_bytes
        processed_mime_type = load_result.mime_type
        final_status = ProcessingStatus.COMPLETED_WITH_ISSUES
        failure_summary: str | None = BACKGROUND_REMOVAL_FALLBACK_SUMMARY
        event_type = "image_processing_completed_with_issues"
        run_failure_code: str | None = "background_removal_fallback"
        run_failure_payload: dict[str, Any] | None = provider_result_payload.sanitized_payload

        if (
            provider_result_payload.status == ProviderResultStatus.SUCCEEDED
            and provider_result_payload.image_bytes is not None
            and provider_result_payload.mime_type is not None
        ):
            processed_bytes = provider_result_payload.image_bytes
            processed_mime_type = provider_result_payload.mime_type
            final_status = ProcessingStatus.COMPLETED
            failure_summary = None
            event_type = "image_processing_completed"
            run_failure_code = None
            run_failure_payload = None

        decoded_processed = self._decode_image(
            image_bytes=processed_bytes,
            error_code="processed_image_decode_failed",
        )
        if decoded_processed.error_code is not None or decoded_processed.image is None:
            if provider_result_payload.status == ProviderResultStatus.SUCCEEDED:
                processed_bytes = load_result.image_bytes
                processed_mime_type = load_result.mime_type
                decoded_processed = self._decode_image(
                    image_bytes=processed_bytes,
                    error_code="processed_fallback_decode_failed",
                )
                final_status = ProcessingStatus.COMPLETED_WITH_ISSUES
                failure_summary = BACKGROUND_REMOVAL_FALLBACK_SUMMARY
                event_type = "image_processing_completed_with_issues"
                run_failure_code = "background_removal_fallback"
                run_failure_payload = {
                    "reason": "Provider output could not be decoded.",
                    "provider_payload": provider_result_payload.sanitized_payload,
                }

            if decoded_processed.error_code is not None or decoded_processed.image is None:
                self._finalize_failed_run(
                    item=item,
                    run=run,
                    failure_code=decoded_processed.error_code or "processed_image_invalid",
                    failure_payload=decoded_processed.failure_payload,
                )
                return

        thumbnail_result = self._create_thumbnail(decoded_processed.image)
        persistence_error = self._persist_derived_images(
            item=item,
            processed_bytes=processed_bytes,
            processed_mime_type=processed_mime_type,
            processed_width=decoded_processed.width,
            processed_height=decoded_processed.height,
            thumbnail_bytes=thumbnail_result.image_bytes,
            thumbnail_mime_type=thumbnail_result.mime_type,
            thumbnail_width=thumbnail_result.width,
            thumbnail_height=thumbnail_result.height,
        )
        if persistence_error is not None:
            self._finalize_failed_run(
                item=item,
                run=run,
                failure_code="derived_asset_persistence_failed",
                failure_payload={"reason": persistence_error},
            )
            return

        run.status = final_status
        run.completed_at = utcnow()
        run.failure_code = run_failure_code
        run.failure_payload = run_failure_payload
        self.lifecycle_service.update_processing_state(
            item_id=item.id,
            user_id=item.user_id,
            processing_status=final_status,
            failure_summary=failure_summary,
            event_type=event_type,
            actor_type=AuditActorType.WORKER,
            actor_user_id=None,
            payload={"processing_run_id": str(run.id)},
            commit=False,
        )
        try:
            self.metadata_extraction_service.enqueue_extraction_for_item(
                item=item,
                actor_type=AuditActorType.WORKER,
                actor_user_id=None,
                raise_on_duplicate=False,
            )
        except Exception:
            pass

    def _can_reprocess(self, *, item: ClosetItem) -> bool:
        if item.lifecycle_status in {LifecycleStatus.CONFIRMED, LifecycleStatus.ARCHIVED}:
            return False
        if not self.repository.has_active_primary_image(item=item):
            return False
        return not self.job_repository.has_pending_or_running_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.IMAGE_PROCESSING,
        )

    def _ensure_item_can_reprocess(self, item: ClosetItem) -> None:
        if item.lifecycle_status in {LifecycleStatus.CONFIRMED, LifecycleStatus.ARCHIVED}:
            raise build_error(INVALID_LIFECYCLE_TRANSITION)
        if not self.repository.has_active_primary_image(item=item):
            raise build_error(MISSING_PRIMARY_IMAGE)
        if self.job_repository.has_pending_or_running_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.IMAGE_PROCESSING,
        ):
            raise build_error(PROCESSING_ALREADY_SCHEDULED)

    def _attempt_background_removal(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> BackgroundRemovalResult:
        try:
            return self.background_removal_provider.remove_background(
                image_bytes=image_bytes,
                filename=filename,
                mime_type=mime_type,
            )
        except Exception as exc:
            return BackgroundRemovalResult(
                provider_name=getattr(self.background_removal_provider, "provider_name", "unknown"),
                provider_model=None,
                provider_version=None,
                status=ProviderResultStatus.FAILED,
                sanitized_payload={
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                image_bytes=None,
                mime_type=None,
            )

    def _build_original_image_snapshots(self, *, item: ClosetItem) -> list[ProcessingSnapshotImage]:
        snapshots: list[ProcessingSnapshotImage] = []
        for image_record in self.repository.list_active_image_assets_for_item(
            closet_item_id=item.id,
            role=ClosetItemImageRole.ORIGINAL,
        ):
            snapshot = self._build_image_snapshot(
                image_record,
                primary_image_id=item.primary_image_id,
            )
            if snapshot is not None:
                snapshots.append(snapshot)
        return snapshots

    def _build_image_snapshot(
        self,
        image_record: tuple[ClosetItemImage, MediaAsset] | None,
        *,
        primary_image_id: UUID | None = None,
    ) -> ProcessingSnapshotImage | None:
        if image_record is None:
            return None
        item_image, asset = image_record
        presigned_download = self.storage.generate_presigned_download(
            bucket=asset.bucket,
            key=asset.key,
            expires_in_seconds=settings.closet_media_download_ttl_seconds,
        )
        return ProcessingSnapshotImage(
            asset_id=asset.id,
            image_id=item_image.id,
            role=item_image.role.value,
            position=(
                item_image.position
                if item_image.role == ClosetItemImageRole.ORIGINAL
                else None
            ),
            is_primary=primary_image_id == item_image.id,
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            url=presigned_download.url,
            expires_at=presigned_download.expires_at,
        )

    def _build_run_snapshot(self, run: ProcessingRun | None) -> ProcessingSnapshotRun | None:
        if run is None:
            return None
        return ProcessingSnapshotRun(
            id=run.id,
            run_type=run.run_type.value,
            status=run.status.value,
            retry_count=run.retry_count,
            started_at=run.started_at,
            completed_at=run.completed_at,
            failure_code=run.failure_code,
        )

    def _load_normalized_original(self, *, asset: MediaAsset) -> LoadedImageResult:
        try:
            content = self.storage.get_object_bytes(bucket=asset.bucket, key=asset.key)
        except FileNotFoundError:
            return LoadedImageResult(
                image_bytes=None,
                mime_type="image/png",
                error_code="source_image_missing",
                failure_payload={"bucket": asset.bucket, "key": asset.key},
            )

        decoded = self._decode_image(image_bytes=content, error_code="source_image_decode_failed")
        if decoded.error_code is not None or decoded.image is None:
            return LoadedImageResult(
                image_bytes=None,
                mime_type="image/png",
                error_code=decoded.error_code,
                failure_payload=decoded.failure_payload,
            )

        normalized_bytes = self._encode_png(decoded.image)
        return LoadedImageResult(
            image_bytes=normalized_bytes,
            mime_type="image/png",
            error_code=None,
            failure_payload=None,
        )

    def _decode_image(self, *, image_bytes: bytes, error_code: str) -> DecodedImageResult:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                normalized = ImageOps.exif_transpose(image)
                decoded = normalized.convert("RGBA")
        except (UnidentifiedImageError, OSError) as exc:
            return DecodedImageResult(
                image=None,
                width=None,
                height=None,
                error_code=error_code,
                failure_payload={"message": str(exc)},
            )

        return DecodedImageResult(
            image=decoded,
            width=decoded.width,
            height=decoded.height,
            error_code=None,
            failure_payload=None,
        )

    def _normalize_provider_result(
        self,
        provider_result: BackgroundRemovalResult,
    ) -> BackgroundRemovalResult:
        if provider_result.image_bytes is None:
            return provider_result

        decoded = self._decode_image(
            image_bytes=provider_result.image_bytes,
            error_code="provider_output_decode_failed",
        )
        if decoded.error_code is None:
            return provider_result

        return BackgroundRemovalResult(
            provider_name=provider_result.provider_name,
            provider_model=provider_result.provider_model,
            provider_version=provider_result.provider_version,
            status=ProviderResultStatus.FAILED,
            sanitized_payload={
                **provider_result.sanitized_payload,
                "provider_output_error": decoded.failure_payload,
            },
            image_bytes=None,
            mime_type=None,
        )

    def _create_thumbnail(self, image: Image.Image) -> EncodedImageResult:
        thumbnail = image.copy()
        thumbnail.thumbnail(
            (settings.closet_thumbnail_max_edge, settings.closet_thumbnail_max_edge),
            Image.Resampling.LANCZOS,
        )
        image_bytes = self._encode_png(thumbnail)
        return EncodedImageResult(
            image_bytes=image_bytes,
            mime_type="image/png",
            width=thumbnail.width,
            height=thumbnail.height,
        )

    def _persist_derived_images(
        self,
        *,
        item: ClosetItem,
        processed_bytes: bytes,
        processed_mime_type: str,
        processed_width: int | None,
        processed_height: int | None,
        thumbnail_bytes: bytes,
        thumbnail_mime_type: str,
        thumbnail_width: int | None,
        thumbnail_height: int | None,
    ) -> str | None:
        processed_asset_id = uuid4()
        thumbnail_asset_id = uuid4()
        processed_key = build_processed_key(
            user_id=item.user_id,
            item_id=item.id,
            asset_id=processed_asset_id,
        )
        thumbnail_key = build_thumbnail_key(
            user_id=item.user_id,
            item_id=item.id,
            asset_id=thumbnail_asset_id,
        )
        written_objects: list[tuple[str, str]] = []

        try:
            self.storage.put_object_bytes(
                bucket=settings.minio_bucket,
                key=processed_key,
                content=processed_bytes,
                content_type=processed_mime_type,
            )
            written_objects.append((settings.minio_bucket, processed_key))
            self.storage.put_object_bytes(
                bucket=settings.minio_bucket,
                key=thumbnail_key,
                content=thumbnail_bytes,
                content_type=thumbnail_mime_type,
            )
            written_objects.append((settings.minio_bucket, thumbnail_key))
        except Exception as exc:
            self._delete_written_objects(written_objects)
            self.repository.deactivate_active_image_roles(
                closet_item_id=item.id,
                roles=[ClosetItemImageRole.PROCESSED, ClosetItemImageRole.THUMBNAIL],
            )
            return str(exc)

        try:
            with self.session.begin_nested():
                processed_asset = self.repository.create_media_asset(
                    asset_id=processed_asset_id,
                    user_id=item.user_id,
                    bucket=settings.minio_bucket,
                    key=processed_key,
                    mime_type=processed_mime_type,
                    file_size=len(processed_bytes),
                    checksum=hash_bytes(processed_bytes),
                    width=processed_width,
                    height=processed_height,
                    source_kind=MediaAssetSourceKind.PROCESSED,
                    is_private=True,
                )
                thumbnail_asset = self.repository.create_media_asset(
                    asset_id=thumbnail_asset_id,
                    user_id=item.user_id,
                    bucket=settings.minio_bucket,
                    key=thumbnail_key,
                    mime_type=thumbnail_mime_type,
                    file_size=len(thumbnail_bytes),
                    checksum=hash_bytes(thumbnail_bytes),
                    width=thumbnail_width,
                    height=thumbnail_height,
                    source_kind=MediaAssetSourceKind.DERIVED,
                    is_private=True,
                )
                self.repository.deactivate_active_image_roles(
                    closet_item_id=item.id,
                    roles=[ClosetItemImageRole.PROCESSED, ClosetItemImageRole.THUMBNAIL],
                )
                self.repository.attach_image_asset(
                    closet_item_id=item.id,
                    asset_id=processed_asset.id,
                    role=ClosetItemImageRole.PROCESSED,
                )
                self.repository.attach_image_asset(
                    closet_item_id=item.id,
                    asset_id=thumbnail_asset.id,
                    role=ClosetItemImageRole.THUMBNAIL,
                )
        except Exception as exc:
            self._delete_written_objects(written_objects)
            self.repository.deactivate_active_image_roles(
                closet_item_id=item.id,
                roles=[ClosetItemImageRole.PROCESSED, ClosetItemImageRole.THUMBNAIL],
            )
            return str(exc)

        return None

    def _delete_written_objects(self, written_objects: list[tuple[str, str]]) -> None:
        for bucket, key in written_objects:
            try:
                self.storage.delete_object(bucket=bucket, key=key)
            except Exception:
                pass

    def _finalize_failed_run(
        self,
        *,
        item: ClosetItem,
        run: ProcessingRun,
        failure_code: str,
        failure_payload: dict[str, Any] | None,
    ) -> None:
        self.repository.deactivate_active_image_roles(
            closet_item_id=item.id,
            roles=[ClosetItemImageRole.PROCESSED, ClosetItemImageRole.THUMBNAIL],
        )
        run.status = ProcessingStatus.FAILED
        run.completed_at = utcnow()
        run.failure_code = failure_code
        run.failure_payload = failure_payload
        self.lifecycle_service.update_processing_state(
            item_id=item.id,
            user_id=item.user_id,
            processing_status=ProcessingStatus.FAILED,
            failure_summary=IMAGE_PROCESSING_FAILURE_SUMMARY,
            event_type="image_processing_failed",
            actor_type=AuditActorType.WORKER,
            actor_user_id=None,
            payload={
                "processing_run_id": str(run.id),
                "failure_code": failure_code,
            },
            commit=False,
        )

    def _encode_png(self, image: Image.Image) -> bytes:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _ensure_matching_idempotency(
        self,
        expected_fingerprint: str,
        actual_fingerprint: str,
    ) -> None:
        if expected_fingerprint != actual_fingerprint:
            raise build_error(IDEMPOTENCY_CONFLICT)


@dataclass(frozen=True)
class LoadedImageResult:
    image_bytes: bytes | None
    mime_type: str
    error_code: str | None
    failure_payload: dict[str, Any] | None


@dataclass(frozen=True)
class DecodedImageResult:
    image: Image.Image | None
    width: int | None
    height: int | None
    error_code: str | None
    failure_payload: dict[str, Any] | None


@dataclass(frozen=True)
class EncodedImageResult:
    image_bytes: bytes
    mime_type: str
    width: int | None
    height: int | None


def build_processed_key(*, user_id: UUID, item_id: UUID, asset_id: UUID) -> str:
    return f"closet/processed/{user_id}/{item_id}/{asset_id}"


def build_thumbnail_key(*, user_id: UUID, item_id: UUID, asset_id: UUID) -> str:
    return f"closet/thumbnails/{user_id}/{item_id}/{asset_id}"


def hash_request_payload(payload: dict[str, object | None]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
