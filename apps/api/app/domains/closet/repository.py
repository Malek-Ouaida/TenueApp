from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.closet.errors import (
    CLOSET_ITEM_NOT_FOUND,
    JOB_NOT_CLAIMABLE,
    JOB_RETRY_EXHAUSTED,
    build_error,
)
from app.domains.closet.models import (
    ApplicabilityState,
    AuditActorType,
    ClosetItem,
    ClosetItemAuditEvent,
    ClosetItemFieldState,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetItemMetadataProjection,
    ClosetJob,
    ClosetJobStatus,
    FieldReviewState,
    FieldSource,
    MediaAsset,
    MediaAssetSourceKind,
    ProcessingRunType,
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

        return item_image

    def has_active_primary_image(self, *, item: ClosetItem) -> bool:
        if item.primary_image_id is None:
            return False

        statement = select(ClosetItemImage).where(
            ClosetItemImage.id == item.primary_image_id,
            ClosetItemImage.closet_item_id == item.id,
            ClosetItemImage.is_active.is_(True),
        )
        return self.session.execute(statement).scalar_one_or_none() is not None

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
        colors = extract_list_value(field_states.get("colors"))
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
        projection.primary_color = colors[0] if colors else None
        projection.secondary_colors = colors[1:] if len(colors) > 1 else None
        projection.material = extract_string_value(field_states.get("material"))
        projection.pattern = extract_string_value(field_states.get("pattern"))
        projection.brand = extract_string_value(field_states.get("brand"))
        projection.style_tags = extract_list_value(field_states.get("style_tags")) or None
        projection.occasion_tags = extract_list_value(field_states.get("occasion_tags")) or None
        projection.season_tags = extract_list_value(field_states.get("season_tags")) or None
        projection.confirmed_at = item.confirmed_at

        self.session.flush()
        return projection

    def get_metadata_projection(self, *, item_id: UUID) -> ClosetItemMetadataProjection | None:
        statement = select(ClosetItemMetadataProjection).where(
            ClosetItemMetadataProjection.closet_item_id == item_id
        )
        return self.session.execute(statement).scalar_one_or_none()


class ClosetJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

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
            available_at=available_at or utcnow(),
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
        current_time = now or utcnow()
        statement = (
            select(ClosetJob)
            .where(
                ClosetJob.status == ClosetJobStatus.PENDING,
                ClosetJob.available_at <= current_time,
            )
            .order_by(ClosetJob.available_at.asc(), ClosetJob.created_at.asc(), ClosetJob.id.asc())
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
        current_time = now or utcnow()
        if job.status != ClosetJobStatus.PENDING or job.available_at > current_time:
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

    def release_job_for_retry(
        self,
        *,
        job: ClosetJob,
        available_at: datetime | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> ClosetJob:
        if job.attempt_count >= job.max_attempts:
            raise build_error(JOB_RETRY_EXHAUSTED)

        job.status = ClosetJobStatus.PENDING
        job.available_at = available_at or utcnow()
        job.locked_at = None
        job.locked_by = None
        job.last_error_code = error_code
        job.last_error_detail = error_detail
        self.session.flush()
        return job


def is_confirmed_field_state(field_state: ClosetItemFieldState | None) -> bool:
    if field_state is None:
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
