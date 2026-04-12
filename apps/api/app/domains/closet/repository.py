from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.config import settings
from app.domains.closet.errors import (
    CLOSET_ITEM_NOT_FOUND,
    JOB_NOT_CLAIMABLE,
    JOB_RETRY_EXHAUSTED,
    build_error,
)
from app.domains.closet.models import (
    ApplicabilityState,
    AuditActorType,
    ClosetIdempotencyKey,
    ClosetItem,
    ClosetItemAuditEvent,
    ClosetItemFieldCandidate,
    ClosetItemFieldState,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetItemMetadataProjection,
    ClosetItemSimilarityEdge,
    ClosetJob,
    ClosetJobStatus,
    ClosetUploadIntent,
    FieldReviewState,
    FieldSource,
    LifecycleStatus,
    MediaAsset,
    MediaAssetSourceKind,
    ProcessingRun,
    ProcessingRunType,
    ProcessingStatus,
    ProviderResult,
    ProviderResultStatus,
    ReviewStatus,
    SimilarityDecisionStatus,
    SimilarityType,
    UploadIntentStatus,
    utcnow,
)


class ClosetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_item(self, *, user_id: UUID, title: str | None = None) -> ClosetItem:
        item = ClosetItem(user_id=user_id, title=title)
        self.session.add(item)
        self.session.flush()
        return item

    def get_item(self, *, item_id: UUID) -> ClosetItem | None:
        statement = select(ClosetItem).where(ClosetItem.id == item_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_item_for_user(self, *, item_id: UUID, user_id: UUID) -> ClosetItem | None:
        statement = select(ClosetItem).where(
            ClosetItem.id == item_id,
            ClosetItem.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def require_item_for_user(self, *, item_id: UUID, user_id: UUID) -> ClosetItem:
        item = self.get_item_for_user(item_id=item_id, user_id=user_id)
        if item is None:
            raise build_error(CLOSET_ITEM_NOT_FOUND)
        return item

    def create_media_asset(
        self,
        *,
        asset_id: UUID | None = None,
        user_id: UUID,
        bucket: str,
        key: str,
        mime_type: str,
        file_size: int,
        checksum: str,
        width: int | None,
        height: int | None,
        source_kind: MediaAssetSourceKind,
        is_private: bool,
    ) -> MediaAsset:
        asset = MediaAsset(
            id=asset_id or None,
            user_id=user_id,
            bucket=bucket,
            key=key,
            mime_type=mime_type,
            file_size=file_size,
            checksum=checksum,
            width=width,
            height=height,
            source_kind=source_kind,
            is_private=is_private,
        )
        self.session.add(asset)
        self.session.flush()
        return asset

    def create_processing_run(
        self,
        *,
        closet_item_id: UUID,
        run_type: ProcessingRunType,
        status: ProcessingStatus,
        retry_count: int = 0,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        failure_code: str | None = None,
        failure_payload: Any | None = None,
    ) -> ProcessingRun:
        run = ProcessingRun(
            closet_item_id=closet_item_id,
            run_type=run_type,
            status=status,
            retry_count=retry_count,
            started_at=started_at,
            completed_at=completed_at,
            failure_code=failure_code,
            failure_payload=failure_payload,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def count_processing_runs(
        self,
        *,
        closet_item_id: UUID,
        run_type: ProcessingRunType,
    ) -> int:
        statement = select(func.count(ProcessingRun.id)).where(
            ProcessingRun.closet_item_id == closet_item_id,
            ProcessingRun.run_type == run_type,
        )
        return int(self.session.execute(statement).scalar_one())

    def get_latest_processing_run(
        self,
        *,
        closet_item_id: UUID,
        run_type: ProcessingRunType,
    ) -> ProcessingRun | None:
        statement = (
            select(ProcessingRun)
            .where(
                ProcessingRun.closet_item_id == closet_item_id,
                ProcessingRun.run_type == run_type,
            )
            .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
        )
        return self.session.execute(statement).scalars().first()

    def create_provider_result(
        self,
        *,
        closet_item_id: UUID,
        processing_run_id: UUID | None,
        provider_name: str,
        provider_model: str | None,
        provider_version: str | None,
        task_type: str,
        status: ProviderResultStatus,
        raw_payload: Any,
    ) -> ProviderResult:
        provider_result = ProviderResult(
            closet_item_id=closet_item_id,
            processing_run_id=processing_run_id,
            provider_name=provider_name,
            provider_model=provider_model,
            provider_version=provider_version,
            task_type=task_type,
            status=status,
            raw_payload=raw_payload,
        )
        self.session.add(provider_result)
        self.session.flush()
        return provider_result

    def list_provider_results_for_run(
        self,
        *,
        processing_run_id: UUID,
    ) -> list[ProviderResult]:
        statement = (
            select(ProviderResult)
            .where(ProviderResult.processing_run_id == processing_run_id)
            .order_by(ProviderResult.created_at.asc(), ProviderResult.id.asc())
        )
        return list(self.session.execute(statement).scalars())

    def get_provider_result(self, *, provider_result_id: UUID) -> ProviderResult | None:
        statement = select(ProviderResult).where(ProviderResult.id == provider_result_id)
        return self.session.execute(statement).scalar_one_or_none()

    def list_provider_results_for_item_task(
        self,
        *,
        closet_item_id: UUID,
        task_type: str,
    ) -> list[ProviderResult]:
        statement = (
            select(ProviderResult)
            .where(
                ProviderResult.closet_item_id == closet_item_id,
                ProviderResult.task_type == task_type,
            )
            .order_by(ProviderResult.created_at.desc(), ProviderResult.id.desc())
        )
        return list(self.session.execute(statement).scalars())

    def get_latest_usable_provider_result_for_item_task(
        self,
        *,
        closet_item_id: UUID,
        task_type: str,
    ) -> ProviderResult | None:
        statement = (
            select(ProviderResult)
            .where(
                ProviderResult.closet_item_id == closet_item_id,
                ProviderResult.task_type == task_type,
                ProviderResult.status.in_(
                    [ProviderResultStatus.SUCCEEDED, ProviderResultStatus.PARTIAL]
                ),
            )
            .order_by(ProviderResult.created_at.desc(), ProviderResult.id.desc())
        )
        return self.session.execute(statement).scalars().first()

    def create_field_candidate(
        self,
        *,
        closet_item_id: UUID,
        field_name: str,
        raw_value: Any | None,
        normalized_candidate: Any | None,
        confidence: float | None,
        provider_result_id: UUID | None,
        applicability_state: ApplicabilityState,
        conflict_notes: str | None,
    ) -> ClosetItemFieldCandidate:
        candidate = ClosetItemFieldCandidate(
            closet_item_id=closet_item_id,
            field_name=field_name,
            raw_value=raw_value,
            normalized_candidate=normalized_candidate,
            confidence=confidence,
            provider_result_id=provider_result_id,
            applicability_state=applicability_state,
            conflict_notes=conflict_notes,
        )
        self.session.add(candidate)
        self.session.flush()
        return candidate

    def list_field_candidates_for_provider_result(
        self,
        *,
        provider_result_id: UUID,
    ) -> list[ClosetItemFieldCandidate]:
        statement = (
            select(ClosetItemFieldCandidate)
            .where(ClosetItemFieldCandidate.provider_result_id == provider_result_id)
            .order_by(
                ClosetItemFieldCandidate.created_at.asc(),
                ClosetItemFieldCandidate.id.asc(),
            )
        )
        return list(self.session.execute(statement).scalars())

    def count_field_candidates_for_provider_result(
        self,
        *,
        provider_result_id: UUID,
    ) -> int:
        statement = select(func.count(ClosetItemFieldCandidate.id)).where(
            ClosetItemFieldCandidate.provider_result_id == provider_result_id
        )
        return int(self.session.execute(statement).scalar_one())

    def create_upload_intent(
        self,
        *,
        upload_intent_id: UUID | None = None,
        closet_item_id: UUID,
        user_id: UUID,
        filename: str,
        mime_type: str,
        file_size: int,
        sha256: str,
        staging_bucket: str,
        staging_key: str,
        expires_at: datetime,
    ) -> ClosetUploadIntent:
        upload_intent = ClosetUploadIntent(
            id=upload_intent_id or None,
            closet_item_id=closet_item_id,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            sha256=sha256,
            staging_bucket=staging_bucket,
            staging_key=staging_key,
            status=UploadIntentStatus.PENDING,
            expires_at=expires_at,
        )
        self.session.add(upload_intent)
        self.session.flush()
        return upload_intent

    def get_upload_intent_for_user(
        self,
        *,
        upload_intent_id: UUID,
        user_id: UUID,
    ) -> ClosetUploadIntent | None:
        statement = select(ClosetUploadIntent).where(
            ClosetUploadIntent.id == upload_intent_id,
            ClosetUploadIntent.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_pending_upload_intent_for_item(
        self,
        *,
        closet_item_id: UUID,
    ) -> ClosetUploadIntent | None:
        statement = (
            select(ClosetUploadIntent)
            .where(
                ClosetUploadIntent.closet_item_id == closet_item_id,
                ClosetUploadIntent.status == UploadIntentStatus.PENDING,
            )
            .order_by(ClosetUploadIntent.created_at.desc(), ClosetUploadIntent.id.desc())
        )
        return self.session.execute(statement).scalars().first()

    def list_expired_pending_upload_intents(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[ClosetUploadIntent]:
        statement = (
            select(ClosetUploadIntent)
            .where(
                ClosetUploadIntent.status == UploadIntentStatus.PENDING,
                ClosetUploadIntent.expires_at <= self._normalize_cursor_datetime(now),
            )
            .order_by(ClosetUploadIntent.expires_at.asc(), ClosetUploadIntent.id.asc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars())

    def mark_upload_intent_expired(
        self,
        *,
        upload_intent: ClosetUploadIntent,
    ) -> ClosetUploadIntent:
        upload_intent.status = UploadIntentStatus.EXPIRED
        upload_intent.last_error_code = None
        upload_intent.last_error_detail = None
        self.session.flush()
        return upload_intent

    def mark_upload_intent_failed(
        self,
        *,
        upload_intent: ClosetUploadIntent,
        error_code: str,
        error_detail: str,
    ) -> ClosetUploadIntent:
        upload_intent.status = UploadIntentStatus.FAILED
        upload_intent.last_error_code = error_code
        upload_intent.last_error_detail = error_detail
        self.session.flush()
        return upload_intent

    def mark_upload_intent_finalized(
        self,
        *,
        upload_intent: ClosetUploadIntent,
        finalized_at: datetime,
    ) -> ClosetUploadIntent:
        upload_intent.status = UploadIntentStatus.FINALIZED
        upload_intent.finalized_at = finalized_at
        upload_intent.last_error_code = None
        upload_intent.last_error_detail = None
        self.session.flush()
        return upload_intent

    def get_idempotency_record(
        self,
        *,
        user_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> ClosetIdempotencyKey | None:
        statement = select(ClosetIdempotencyKey).where(
            ClosetIdempotencyKey.user_id == user_id,
            ClosetIdempotencyKey.operation == operation,
            ClosetIdempotencyKey.idempotency_key == idempotency_key,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def create_idempotency_record(
        self,
        *,
        user_id: UUID,
        operation: str,
        idempotency_key: str,
        request_fingerprint: str,
        resource_type: str,
        resource_id: UUID,
        response_status_code: int,
    ) -> ClosetIdempotencyKey:
        record = ClosetIdempotencyKey(
            user_id=user_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            resource_type=resource_type,
            resource_id=resource_id,
            response_status_code=response_status_code,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_media_asset_for_user(self, *, asset_id: UUID, user_id: UUID) -> MediaAsset | None:
        statement = select(MediaAsset).where(
            MediaAsset.id == asset_id,
            MediaAsset.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def attach_image_asset(
        self,
        *,
        closet_item_id: UUID,
        asset_id: UUID,
        role: ClosetItemImageRole,
        position: int = 0,
    ) -> ClosetItemImage:
        statement = select(ClosetItemImage).where(
            ClosetItemImage.closet_item_id == closet_item_id,
            ClosetItemImage.asset_id == asset_id,
            ClosetItemImage.role == role,
        )
        item_image = self.session.execute(statement).scalar_one_or_none()
        if item_image is None:
            item_image = ClosetItemImage(
                closet_item_id=closet_item_id,
                asset_id=asset_id,
                role=role,
                position=position,
                is_active=True,
            )
            self.session.add(item_image)
            self.session.flush()
        else:
            item_image.is_active = True
            item_image.position = position
            item_image.archived_at = None
            item_image.archived_by_user_id = None

        return item_image

    def get_item_image_for_item(
        self,
        *,
        closet_item_id: UUID,
        image_id: UUID,
    ) -> ClosetItemImage | None:
        statement = select(ClosetItemImage).where(
            ClosetItemImage.id == image_id,
            ClosetItemImage.closet_item_id == closet_item_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_item_image_asset_for_item(
        self,
        *,
        closet_item_id: UUID,
        image_id: UUID,
    ) -> tuple[ClosetItemImage, MediaAsset] | None:
        statement = (
            select(ClosetItemImage, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ClosetItemImage.asset_id)
            .where(
                ClosetItemImage.id == image_id,
                ClosetItemImage.closet_item_id == closet_item_id,
            )
        )
        row = self.session.execute(statement).first()
        if row is None:
            return None
        return row[0], row[1]

    def has_active_primary_image(self, *, item: ClosetItem) -> bool:
        if item.primary_image_id is None:
            return False

        statement = select(ClosetItemImage).where(
            ClosetItemImage.id == item.primary_image_id,
            ClosetItemImage.closet_item_id == item.id,
            ClosetItemImage.is_active.is_(True),
        )
        return self.session.execute(statement).scalar_one_or_none() is not None

    def get_primary_image_asset(
        self,
        *,
        item: ClosetItem,
    ) -> tuple[ClosetItemImage, MediaAsset] | None:
        if item.primary_image_id is None:
            return None

        statement = (
            select(ClosetItemImage, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ClosetItemImage.asset_id)
            .where(
                ClosetItemImage.id == item.primary_image_id,
                ClosetItemImage.closet_item_id == item.id,
                ClosetItemImage.is_active.is_(True),
            )
        )
        row = self.session.execute(statement).first()
        if row is None:
            return None
        return row[0], row[1]

    def get_active_image_asset_by_role(
        self,
        *,
        closet_item_id: UUID,
        role: ClosetItemImageRole,
    ) -> tuple[ClosetItemImage, MediaAsset] | None:
        statement = (
            select(ClosetItemImage, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ClosetItemImage.asset_id)
            .where(
                ClosetItemImage.closet_item_id == closet_item_id,
                ClosetItemImage.role == role,
                ClosetItemImage.is_active.is_(True),
            )
            .order_by(ClosetItemImage.created_at.desc(), ClosetItemImage.id.desc())
        )
        row = self.session.execute(statement).first()
        if row is None:
            return None
        return row[0], row[1]

    def list_active_image_assets_for_item(
        self,
        *,
        closet_item_id: UUID,
        role: ClosetItemImageRole,
    ) -> list[tuple[ClosetItemImage, MediaAsset]]:
        statement = (
            select(ClosetItemImage, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ClosetItemImage.asset_id)
            .where(
                ClosetItemImage.closet_item_id == closet_item_id,
                ClosetItemImage.role == role,
                ClosetItemImage.is_active.is_(True),
            )
            .order_by(
                ClosetItemImage.position.asc(),
                ClosetItemImage.created_at.asc(),
                ClosetItemImage.id.asc(),
            )
        )
        return [(row[0], row[1]) for row in self.session.execute(statement).all()]

    def get_next_image_position(
        self,
        *,
        closet_item_id: UUID,
        role: ClosetItemImageRole,
    ) -> int:
        statement = select(func.max(ClosetItemImage.position)).where(
            ClosetItemImage.closet_item_id == closet_item_id,
            ClosetItemImage.role == role,
            ClosetItemImage.is_active.is_(True),
        )
        max_position = self.session.execute(statement).scalar_one()
        return 0 if max_position is None else int(max_position) + 1

    def deactivate_active_image_roles(
        self,
        *,
        closet_item_id: UUID,
        roles: list[ClosetItemImageRole],
    ) -> None:
        statement = select(ClosetItemImage).where(
            ClosetItemImage.closet_item_id == closet_item_id,
            ClosetItemImage.role.in_(roles),
            ClosetItemImage.is_active.is_(True),
        )
        for item_image in self.session.execute(statement).scalars():
            item_image.is_active = False
            item_image.archived_at = utcnow()
            item_image.archived_by_user_id = None
        self.session.flush()

    def archive_item_image(
        self,
        *,
        item_image: ClosetItemImage,
        archived_by_user_id: UUID | None,
    ) -> ClosetItemImage:
        item_image.is_active = False
        item_image.archived_at = utcnow()
        item_image.archived_by_user_id = archived_by_user_id
        self.session.flush()
        return item_image

    def list_field_states(self, *, closet_item_id: UUID) -> list[ClosetItemFieldState]:
        statement = select(ClosetItemFieldState).where(
            ClosetItemFieldState.closet_item_id == closet_item_id
        )
        return list(self.session.execute(statement).scalars())

    def upsert_field_state(
        self,
        *,
        closet_item_id: UUID,
        field_name: str,
        canonical_value: Any | None,
        source: FieldSource,
        confidence: float | None,
        review_state: FieldReviewState,
        applicability_state: ApplicabilityState,
        taxonomy_version: str,
    ) -> ClosetItemFieldState:
        statement = select(ClosetItemFieldState).where(
            ClosetItemFieldState.closet_item_id == closet_item_id,
            ClosetItemFieldState.field_name == field_name,
        )
        field_state = self.session.execute(statement).scalar_one_or_none()

        if field_state is None:
            field_state = ClosetItemFieldState(
                closet_item_id=closet_item_id,
                field_name=field_name,
                canonical_value=canonical_value,
                source=source,
                confidence=confidence,
                review_state=review_state,
                applicability_state=applicability_state,
                taxonomy_version=taxonomy_version,
            )
            self.session.add(field_state)
        else:
            field_state.canonical_value = canonical_value
            field_state.source = source
            field_state.confidence = confidence
            field_state.review_state = review_state
            field_state.applicability_state = applicability_state
            field_state.taxonomy_version = taxonomy_version

        self.session.flush()
        return field_state

    def create_audit_event(
        self,
        *,
        closet_item_id: UUID,
        actor_type: AuditActorType,
        actor_user_id: UUID | None,
        event_type: str,
        payload: Any | None,
    ) -> ClosetItemAuditEvent:
        event = ClosetItemAuditEvent(
            closet_item_id=closet_item_id,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            event_type=event_type,
            payload=payload,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def list_audit_events(self, *, closet_item_id: UUID) -> list[ClosetItemAuditEvent]:
        statement = (
            select(ClosetItemAuditEvent)
            .where(ClosetItemAuditEvent.closet_item_id == closet_item_id)
            .order_by(ClosetItemAuditEvent.created_at.asc(), ClosetItemAuditEvent.id.asc())
        )
        return list(self.session.execute(statement).scalars())

    def list_audit_events_paginated(
        self,
        *,
        closet_item_id: UUID,
        cursor_created_at: datetime | None,
        cursor_event_id: UUID | None,
        limit: int,
    ) -> list[ClosetItemAuditEvent]:
        normalized_cursor_created_at = self._normalize_cursor_datetime(cursor_created_at)
        statement = select(ClosetItemAuditEvent).where(
            ClosetItemAuditEvent.closet_item_id == closet_item_id
        )

        if normalized_cursor_created_at is not None and cursor_event_id is not None:
            statement = statement.where(
                or_(
                    ClosetItemAuditEvent.created_at < normalized_cursor_created_at,
                    and_(
                        ClosetItemAuditEvent.created_at == normalized_cursor_created_at,
                        ClosetItemAuditEvent.id < cursor_event_id,
                    ),
                )
            )

        statement = statement.order_by(
            ClosetItemAuditEvent.created_at.desc(),
            ClosetItemAuditEvent.id.desc(),
        ).limit(limit)
        return list(self.session.execute(statement).scalars())

    def upsert_metadata_projection(
        self,
        *,
        item: ClosetItem,
        taxonomy_version: str,
    ) -> ClosetItemMetadataProjection:
        field_states = {
            field_state.field_name: field_state
            for field_state in self.list_field_states(closet_item_id=item.id)
        }
        projection = self.get_metadata_projection(item_id=item.id)
        legacy_colors = extract_list_value(field_states.get("colors"))
        if projection is None:
            projection = ClosetItemMetadataProjection(
                closet_item_id=item.id,
                user_id=item.user_id,
                taxonomy_version=taxonomy_version,
            )
            self.session.add(projection)

        projection.taxonomy_version = taxonomy_version
        projection.title = extract_string_value(field_states.get("title")) or item.title
        projection.category = extract_string_value(field_states.get("category"))
        projection.subcategory = extract_string_value(field_states.get("subcategory"))
        primary_color_state = field_states.get("primary_color")
        secondary_colors_state = field_states.get("secondary_colors")
        projection.primary_color = (
            extract_string_value(primary_color_state)
            if primary_color_state is not None
            else (legacy_colors[0] if legacy_colors else None)
        )
        projection.secondary_colors = (
            extract_list_value(secondary_colors_state) or None
            if secondary_colors_state is not None
            else (legacy_colors[1:] if len(legacy_colors) > 1 else None)
        )
        projection.material = extract_string_value(field_states.get("material"))
        projection.pattern = extract_string_value(field_states.get("pattern"))
        projection.brand = extract_string_value(field_states.get("brand"))
        projection.style_tags = extract_list_value(field_states.get("style_tags")) or None
        projection.fit_tags = extract_list_value(field_states.get("fit_tags")) or None
        projection.occasion_tags = extract_list_value(field_states.get("occasion_tags")) or None
        projection.season_tags = extract_list_value(field_states.get("season_tags")) or None
        projection.silhouette = extract_string_value(field_states.get("silhouette"))
        projection.attributes = extract_list_value(field_states.get("attributes")) or None
        projection.formality = extract_string_value(field_states.get("formality"))
        projection.warmth = extract_string_value(field_states.get("warmth"))
        projection.coverage = extract_string_value(field_states.get("coverage"))
        projection.statement_level = extract_string_value(field_states.get("statement_level"))
        projection.versatility = extract_string_value(field_states.get("versatility"))
        projection.confirmed_at = item.confirmed_at

        self.session.flush()
        return projection

    def get_metadata_projection(self, *, item_id: UUID) -> ClosetItemMetadataProjection | None:
        statement = select(ClosetItemMetadataProjection).where(
            ClosetItemMetadataProjection.closet_item_id == item_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_confirmed_item_with_projection_for_user(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        include_archived: bool = False,
    ) -> tuple[ClosetItem, ClosetItemMetadataProjection] | None:
        statement = (
            select(ClosetItem, ClosetItemMetadataProjection)
            .join(
                ClosetItemMetadataProjection,
                ClosetItemMetadataProjection.closet_item_id == ClosetItem.id,
            )
            .where(
                ClosetItem.id == item_id,
                ClosetItem.user_id == user_id,
                ClosetItem.lifecycle_status.in_(
                    [LifecycleStatus.CONFIRMED, LifecycleStatus.ARCHIVED]
                    if include_archived
                    else [LifecycleStatus.CONFIRMED]
                ),
                ClosetItem.review_status == ReviewStatus.CONFIRMED,
                ClosetItem.confirmed_at.is_not(None),
                ClosetItemMetadataProjection.user_id == user_id,
            )
        )
        row = self.session.execute(statement).first()
        if row is None:
            return None
        return row[0], row[1]

    def get_confirmed_items_with_projections_for_user(
        self,
        *,
        item_ids: list[UUID],
        user_id: UUID,
    ) -> dict[UUID, tuple[ClosetItem, ClosetItemMetadataProjection]]:
        if not item_ids:
            return {}

        statement = (
            select(ClosetItem, ClosetItemMetadataProjection)
            .join(
                ClosetItemMetadataProjection,
                ClosetItemMetadataProjection.closet_item_id == ClosetItem.id,
            )
            .where(
                ClosetItem.id.in_(item_ids),
                ClosetItem.user_id == user_id,
                ClosetItem.lifecycle_status == LifecycleStatus.CONFIRMED,
                ClosetItem.review_status == ReviewStatus.CONFIRMED,
                ClosetItem.confirmed_at.is_not(None),
                ClosetItemMetadataProjection.user_id == user_id,
            )
        )
        return {
            item.id: (item, projection)
            for item, projection in self.session.execute(statement).all()
        }

    def list_confirmed_peer_items_with_projections(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
    ) -> list[tuple[ClosetItem, ClosetItemMetadataProjection]]:
        statement = (
            select(ClosetItem, ClosetItemMetadataProjection)
            .join(
                ClosetItemMetadataProjection,
                ClosetItemMetadataProjection.closet_item_id == ClosetItem.id,
            )
            .where(
                ClosetItem.id != item_id,
                ClosetItem.user_id == user_id,
                ClosetItem.lifecycle_status == LifecycleStatus.CONFIRMED,
                ClosetItem.review_status == ReviewStatus.CONFIRMED,
                ClosetItem.confirmed_at.is_not(None),
                ClosetItemMetadataProjection.user_id == user_id,
            )
            .order_by(ClosetItem.confirmed_at.desc(), ClosetItem.id.desc())
        )
        return [(row[0], row[1]) for row in self.session.execute(statement).all()]

    def list_all_confirmed_items(self) -> list[ClosetItem]:
        statement = (
            select(ClosetItem)
            .where(
                ClosetItem.lifecycle_status == LifecycleStatus.CONFIRMED,
                ClosetItem.review_status == ReviewStatus.CONFIRMED,
                ClosetItem.confirmed_at.is_not(None),
            )
            .order_by(ClosetItem.confirmed_at.desc(), ClosetItem.id.desc())
        )
        return list(self.session.execute(statement).scalars())

    def list_confirmed_items(
        self,
        *,
        user_id: UUID,
        cursor_confirmed_at: datetime | None,
        cursor_item_id: UUID | None,
        limit: int,
        query: str | None,
        category: str | None,
        subcategory: str | None,
        primary_color: str | None,
        material: str | None,
        pattern: str | None,
        include_archived: bool = False,
    ) -> list[tuple[ClosetItem, ClosetItemMetadataProjection]]:
        normalized_cursor_confirmed_at = self._normalize_cursor_datetime(cursor_confirmed_at)
        statement = (
            select(ClosetItem, ClosetItemMetadataProjection)
            .join(
                ClosetItemMetadataProjection,
                ClosetItemMetadataProjection.closet_item_id == ClosetItem.id,
            )
            .where(
                ClosetItem.user_id == user_id,
                ClosetItem.lifecycle_status.in_(
                    [LifecycleStatus.CONFIRMED, LifecycleStatus.ARCHIVED]
                    if include_archived
                    else [LifecycleStatus.CONFIRMED]
                ),
                ClosetItem.review_status == ReviewStatus.CONFIRMED,
                ClosetItem.confirmed_at.is_not(None),
                ClosetItemMetadataProjection.user_id == user_id,
            )
        )

        if category is not None:
            statement = statement.where(ClosetItemMetadataProjection.category == category)
        if subcategory is not None:
            statement = statement.where(ClosetItemMetadataProjection.subcategory == subcategory)
        if primary_color is not None:
            statement = statement.where(ClosetItemMetadataProjection.primary_color == primary_color)
        if material is not None:
            statement = statement.where(ClosetItemMetadataProjection.material == material)
        if pattern is not None:
            statement = statement.where(ClosetItemMetadataProjection.pattern == pattern)

        if query is not None:
            query_pattern = f"%{query.casefold()}%"
            statement = statement.where(
                or_(
                    func.lower(func.coalesce(ClosetItemMetadataProjection.title, "")).like(
                        query_pattern
                    ),
                    func.lower(func.coalesce(ClosetItemMetadataProjection.brand, "")).like(
                        query_pattern
                    ),
                    func.lower(func.coalesce(ClosetItemMetadataProjection.category, "")).like(
                        query_pattern
                    ),
                    func.lower(func.coalesce(ClosetItemMetadataProjection.subcategory, "")).like(
                        query_pattern
                    ),
                    func.lower(func.coalesce(ClosetItemMetadataProjection.primary_color, "")).like(
                        query_pattern
                    ),
                    func.lower(func.coalesce(ClosetItemMetadataProjection.material, "")).like(
                        query_pattern
                    ),
                    func.lower(func.coalesce(ClosetItemMetadataProjection.pattern, "")).like(
                        query_pattern
                    ),
                )
            )

        if normalized_cursor_confirmed_at is not None and cursor_item_id is not None:
            statement = statement.where(
                or_(
                    ClosetItem.confirmed_at < normalized_cursor_confirmed_at,
                    and_(
                        ClosetItem.confirmed_at == normalized_cursor_confirmed_at,
                        ClosetItem.id < cursor_item_id,
                    ),
                )
            )

        statement = statement.order_by(ClosetItem.confirmed_at.desc(), ClosetItem.id.desc()).limit(
            limit
        )
        return [(row[0], row[1]) for row in self.session.execute(statement).all()]

    def list_active_image_assets_for_items(
        self,
        *,
        closet_item_ids: list[UUID],
        roles: list[ClosetItemImageRole],
    ) -> dict[UUID, dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]]]:
        if not closet_item_ids or not roles:
            return {}

        statement = (
            select(ClosetItemImage, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ClosetItemImage.asset_id)
            .where(
                ClosetItemImage.closet_item_id.in_(closet_item_ids),
                ClosetItemImage.role.in_(roles),
                ClosetItemImage.is_active.is_(True),
            )
            .order_by(
                ClosetItemImage.closet_item_id.asc(),
                ClosetItemImage.role.asc(),
                ClosetItemImage.position.asc(),
                ClosetItemImage.created_at.desc(),
                ClosetItemImage.id.desc(),
            )
        )

        images_by_item: dict[
            UUID, dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]]
        ] = {}
        for item_image, asset in self.session.execute(statement).all():
            item_images = images_by_item.setdefault(item_image.closet_item_id, {})
            if item_image.role not in item_images:
                item_images[item_image.role] = (item_image, asset)
        return images_by_item

    def list_review_items(
        self,
        *,
        user_id: UUID,
        cursor_updated_at: datetime | None,
        cursor_item_id: UUID | None,
        limit: int,
    ) -> list[ClosetItem]:
        normalized_cursor_updated_at = self._normalize_cursor_datetime(cursor_updated_at)
        statement = select(ClosetItem).where(
            ClosetItem.user_id == user_id,
            ClosetItem.lifecycle_status.notin_(
                [LifecycleStatus.CONFIRMED, LifecycleStatus.ARCHIVED]
            ),
        )

        if normalized_cursor_updated_at is not None and cursor_item_id is not None:
            statement = statement.where(
                or_(
                    ClosetItem.updated_at < normalized_cursor_updated_at,
                    and_(
                        ClosetItem.updated_at == normalized_cursor_updated_at,
                        ClosetItem.id < cursor_item_id,
                    ),
                )
            )

        statement = statement.order_by(ClosetItem.updated_at.desc(), ClosetItem.id.desc()).limit(
            limit
        )
        return list(self.session.execute(statement).scalars())

    def list_similarity_edges_for_item(self, *, item_id: UUID) -> list[ClosetItemSimilarityEdge]:
        statement = (
            select(ClosetItemSimilarityEdge)
            .where(
                or_(
                    ClosetItemSimilarityEdge.item_a_id == item_id,
                    ClosetItemSimilarityEdge.item_b_id == item_id,
                )
            )
            .order_by(
                ClosetItemSimilarityEdge.updated_at.desc(),
                ClosetItemSimilarityEdge.id.desc(),
            )
        )
        return list(self.session.execute(statement).scalars())

    def list_similarity_edges_for_pair(
        self,
        *,
        item_a_id: UUID,
        item_b_id: UUID,
    ) -> list[ClosetItemSimilarityEdge]:
        canonical_item_a_id, canonical_item_b_id = canonicalize_similarity_pair(
            item_a_id,
            item_b_id,
        )
        statement = (
            select(ClosetItemSimilarityEdge)
            .where(
                ClosetItemSimilarityEdge.item_a_id == canonical_item_a_id,
                ClosetItemSimilarityEdge.item_b_id == canonical_item_b_id,
            )
            .order_by(
                ClosetItemSimilarityEdge.updated_at.desc(),
                ClosetItemSimilarityEdge.id.desc(),
            )
        )
        return list(self.session.execute(statement).scalars())

    def get_similarity_edge_for_user(
        self,
        *,
        edge_id: UUID,
        user_id: UUID,
    ) -> ClosetItemSimilarityEdge | None:
        item_a = aliased(ClosetItem)
        item_b = aliased(ClosetItem)
        statement = (
            select(ClosetItemSimilarityEdge)
            .join(item_a, item_a.id == ClosetItemSimilarityEdge.item_a_id)
            .join(item_b, item_b.id == ClosetItemSimilarityEdge.item_b_id)
            .where(
                ClosetItemSimilarityEdge.id == edge_id,
                item_a.user_id == user_id,
                item_b.user_id == user_id,
            )
        )
        return self.session.execute(statement).scalar_one_or_none()

    def save_similarity_edge(
        self,
        *,
        edge: ClosetItemSimilarityEdge | None,
        item_a_id: UUID,
        item_b_id: UUID,
        similarity_type: SimilarityType,
        score: float,
        signals_json: Any | None,
        decision_status: SimilarityDecisionStatus,
    ) -> ClosetItemSimilarityEdge:
        canonical_item_a_id, canonical_item_b_id = canonicalize_similarity_pair(
            item_a_id,
            item_b_id,
        )
        if edge is None:
            edge = ClosetItemSimilarityEdge(
                item_a_id=canonical_item_a_id,
                item_b_id=canonical_item_b_id,
                similarity_type=similarity_type,
                score=score,
                signals_json=signals_json,
                decision_status=decision_status,
            )
            self.session.add(edge)
        else:
            edge.item_a_id = canonical_item_a_id
            edge.item_b_id = canonical_item_b_id
            edge.similarity_type = similarity_type
            edge.score = score
            edge.signals_json = signals_json
            edge.decision_status = decision_status
        self.session.flush()
        return edge

    def delete_similarity_edges_for_pair(
        self,
        *,
        item_a_id: UUID,
        item_b_id: UUID,
        keep_edge_id: UUID | None = None,
    ) -> None:
        canonical_item_a_id, canonical_item_b_id = canonicalize_similarity_pair(
            item_a_id,
            item_b_id,
        )
        statement = select(ClosetItemSimilarityEdge).where(
            ClosetItemSimilarityEdge.item_a_id == canonical_item_a_id,
            ClosetItemSimilarityEdge.item_b_id == canonical_item_b_id,
        )
        for edge in self.session.execute(statement).scalars():
            if keep_edge_id is not None and edge.id == keep_edge_id:
                continue
            self.session.delete(edge)
        self.session.flush()

    def delete_similarity_edges_for_item(self, *, item_id: UUID) -> None:
        statement = select(ClosetItemSimilarityEdge).where(
            or_(
                ClosetItemSimilarityEdge.item_a_id == item_id,
                ClosetItemSimilarityEdge.item_b_id == item_id,
            )
        )
        for edge in self.session.execute(statement).scalars():
            self.session.delete(edge)
        self.session.flush()

    def _normalize_cursor_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None

        dialect_name = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect_name == "sqlite":
            if value.tzinfo is None:
                return value
            return value.astimezone(UTC).replace(tzinfo=None)

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class ClosetJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def has_pending_or_running_job(
        self,
        *,
        closet_item_id: UUID,
        job_kind: ProcessingRunType,
    ) -> bool:
        statement = select(ClosetJob.id).where(
            ClosetJob.closet_item_id == closet_item_id,
            ClosetJob.job_kind == job_kind,
            ClosetJob.status.in_([ClosetJobStatus.PENDING, ClosetJobStatus.RUNNING]),
        )
        return self.session.execute(statement).first() is not None

    def get_pending_or_running_job(
        self,
        *,
        closet_item_id: UUID,
        job_kind: ProcessingRunType,
    ) -> ClosetJob | None:
        statement = (
            select(ClosetJob)
            .where(
                ClosetJob.closet_item_id == closet_item_id,
                ClosetJob.job_kind == job_kind,
                ClosetJob.status.in_([ClosetJobStatus.PENDING, ClosetJobStatus.RUNNING]),
            )
            .order_by(ClosetJob.created_at.desc(), ClosetJob.id.desc())
        )
        return self.session.execute(statement).scalars().first()

    def get_latest_job(
        self,
        *,
        closet_item_id: UUID,
        job_kind: ProcessingRunType,
    ) -> ClosetJob | None:
        statement = (
            select(ClosetJob)
            .where(
                ClosetJob.closet_item_id == closet_item_id,
                ClosetJob.job_kind == job_kind,
            )
            .order_by(ClosetJob.created_at.desc(), ClosetJob.id.desc())
        )
        return self.session.execute(statement).scalars().first()

    def list_jobs_for_item_kind(
        self,
        *,
        closet_item_id: UUID,
        job_kind: ProcessingRunType,
    ) -> list[ClosetJob]:
        statement = (
            select(ClosetJob)
            .where(
                ClosetJob.closet_item_id == closet_item_id,
                ClosetJob.job_kind == job_kind,
            )
            .order_by(ClosetJob.created_at.desc(), ClosetJob.id.desc())
        )
        return list(self.session.execute(statement).scalars())

    def enqueue_job(
        self,
        *,
        closet_item_id: UUID,
        job_kind: ProcessingRunType,
        payload: Any | None = None,
        available_at: datetime | None = None,
        max_attempts: int = 3,
    ) -> ClosetJob:
        job = ClosetJob(
            closet_item_id=closet_item_id,
            job_kind=job_kind,
            status=ClosetJobStatus.PENDING,
            available_at=self._normalize_datetime(available_at or utcnow()),
            max_attempts=max_attempts,
            payload=payload,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def claim_next_job(
        self,
        *,
        worker_name: str,
        now: datetime | None = None,
    ) -> ClosetJob | None:
        current_time = self._normalize_datetime(now or utcnow())
        self._requeue_stale_running_jobs(now=current_time)
        job_priority = case(
            (ClosetJob.job_kind == ProcessingRunType.SIMILARITY_RECOMPUTE, 1),
            else_=0,
        )
        statement = (
            select(ClosetJob)
            .where(
                ClosetJob.status == ClosetJobStatus.PENDING,
                ClosetJob.available_at <= current_time,
            )
            .order_by(
                job_priority.asc(),
                ClosetJob.available_at.asc(),
                ClosetJob.created_at.asc(),
                ClosetJob.id.asc(),
            )
        )
        job = self.session.execute(statement).scalars().first()
        if job is None:
            return None

        self.mark_job_running(job=job, worker_name=worker_name, now=current_time)
        return job

    def mark_job_running(
        self,
        *,
        job: ClosetJob,
        worker_name: str,
        now: datetime | None = None,
    ) -> ClosetJob:
        current_time = self._normalize_datetime(now or utcnow())
        available_at = self._normalize_datetime(job.available_at)
        if job.status != ClosetJobStatus.PENDING or available_at > current_time:
            raise build_error(JOB_NOT_CLAIMABLE)

        job.status = ClosetJobStatus.RUNNING
        job.locked_at = current_time
        job.locked_by = worker_name
        job.attempt_count += 1
        self.session.flush()
        return job

    def mark_job_completed(self, *, job: ClosetJob) -> ClosetJob:
        job.status = ClosetJobStatus.COMPLETED
        job.locked_at = None
        job.locked_by = None
        self.session.flush()
        return job

    def mark_job_failed(
        self,
        *,
        job: ClosetJob,
        error_code: str,
        error_detail: str,
    ) -> ClosetJob:
        job.status = ClosetJobStatus.FAILED
        job.locked_at = None
        job.locked_by = None
        job.last_error_code = error_code
        job.last_error_detail = error_detail
        self.session.flush()
        return job

    def handle_job_failure(
        self,
        *,
        job: ClosetJob,
        error_code: str,
        error_detail: str,
        retryable: bool,
        now: datetime | None = None,
    ) -> ClosetJob:
        if retryable and job.attempt_count < job.max_attempts:
            return self.release_job_for_retry(
                job=job,
                error_code=error_code,
                error_detail=error_detail,
                now=now,
            )
        return self.mark_job_failed(
            job=job,
            error_code=error_code,
            error_detail=error_detail,
        )

    def release_job_for_retry(
        self,
        *,
        job: ClosetJob,
        available_at: datetime | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
        now: datetime | None = None,
    ) -> ClosetJob:
        if job.attempt_count >= job.max_attempts:
            raise build_error(JOB_RETRY_EXHAUSTED)

        current_time = self._normalize_datetime(now or utcnow())
        job.status = ClosetJobStatus.PENDING
        job.available_at = self._normalize_datetime(
            available_at or self._calculate_retry_available_at(job=job, now=current_time)
        )
        job.locked_at = None
        job.locked_by = None
        job.last_error_code = error_code
        job.last_error_detail = error_detail
        self.session.flush()
        return job

    def _requeue_stale_running_jobs(self, *, now: datetime) -> None:
        stale_before = now - timedelta(seconds=settings.closet_job_lock_timeout_seconds)
        statement = (
            select(ClosetJob)
            .where(
                ClosetJob.status == ClosetJobStatus.RUNNING,
                ClosetJob.locked_at.is_not(None),
                ClosetJob.locked_at <= stale_before,
            )
            .order_by(ClosetJob.locked_at.asc(), ClosetJob.created_at.asc(), ClosetJob.id.asc())
        )
        for job in self.session.execute(statement).scalars():
            if job.attempt_count >= job.max_attempts:
                self.mark_job_failed(
                    job=job,
                    error_code="job_lock_expired",
                    error_detail=(
                        "The worker lock expired and the job has exhausted its retry budget."
                    ),
                )
                continue
            self.release_job_for_retry(
                job=job,
                available_at=now,
                error_code="job_lock_expired",
                error_detail="The worker lock expired before the job completed.",
                now=now,
            )

    def _calculate_retry_available_at(self, *, job: ClosetJob, now: datetime) -> datetime:
        exponent = max(job.attempt_count - 1, 0)
        delay_seconds = settings.closet_job_retry_base_delay_seconds * (2**exponent)
        capped_delay_seconds = min(delay_seconds, settings.closet_job_retry_max_delay_seconds)
        return now + timedelta(seconds=capped_delay_seconds)

    def _normalize_datetime(self, value: datetime) -> datetime:
        dialect_name = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect_name == "sqlite":
            if value.tzinfo is None:
                return value
            return value.astimezone(UTC).replace(tzinfo=None)

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def is_confirmed_field_state(field_state: ClosetItemFieldState | None) -> bool:
    if field_state is None:
        return False

    if field_state.source != FieldSource.USER:
        return False

    if field_state.applicability_state != ApplicabilityState.VALUE:
        return False

    if field_state.review_state not in {
        FieldReviewState.USER_CONFIRMED,
        FieldReviewState.USER_EDITED,
    }:
        return False

    value = field_state.canonical_value
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0

    return True


def extract_string_value(field_state: ClosetItemFieldState | None) -> str | None:
    if not is_confirmed_field_state(field_state):
        return None
    assert field_state is not None

    value = field_state.canonical_value
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def extract_list_value(field_state: ClosetItemFieldState | None) -> list[str]:
    if not is_confirmed_field_state(field_state):
        return []
    assert field_state is not None

    value = field_state.canonical_value
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return []


def canonicalize_similarity_pair(item_a_id: UUID, item_b_id: UUID) -> tuple[UUID, UUID]:
    if item_a_id.int <= item_b_id.int:
        return item_a_id, item_b_id
    return item_b_id, item_a_id
