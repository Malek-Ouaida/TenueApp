from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.closet.errors import (
    INVALID_FIELD_NAME,
    INVALID_LIFECYCLE_TRANSITION,
    MISSING_PRIMARY_IMAGE,
    MISSING_REQUIRED_CONFIRMATION_FIELDS,
    UNSUPPORTED_TAXONOMY_VERSION,
    build_error,
)
from app.domains.closet.models import (
    ApplicabilityState,
    AuditActorType,
    ClosetItem,
    ClosetItemFieldState,
    ClosetItemImageRole,
    FieldReviewState,
    FieldSource,
    LifecycleStatus,
    MediaAsset,
    MediaAssetSourceKind,
    ProcessingStatus,
    ReviewStatus,
    utcnow,
)
from app.domains.closet.repository import ClosetRepository, is_confirmed_field_state
from app.domains.closet.taxonomy import (
    REQUIRED_CONFIRMATION_FIELDS,
    TAXONOMY_VERSION,
    is_supported_field_name,
    is_supported_taxonomy_version,
)


class ClosetLifecycleService:
    def __init__(self, *, session: Session, repository: ClosetRepository) -> None:
        self.session = session
        self.repository = repository

    def create_item(self, *, user_id: UUID, title: str | None = None) -> ClosetItem:
        item = self.repository.create_item(user_id=user_id, title=title)
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="item_created",
            payload={"lifecycle_status": item.lifecycle_status.value},
        )
        self.session.commit()
        self.session.refresh(item)
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
        width: int | None = None,
        height: int | None = None,
        source_kind: MediaAssetSourceKind = MediaAssetSourceKind.UPLOAD,
        is_private: bool = True,
    ) -> MediaAsset:
        asset = self.repository.create_media_asset(
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
        self.session.commit()
        self.session.refresh(asset)
        return asset

    def attach_primary_asset(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        asset_id: UUID,
        role: ClosetItemImageRole = ClosetItemImageRole.ORIGINAL,
    ) -> ClosetItem:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        self._ensure_not_archived(item)

        asset = self.repository.get_media_asset_for_user(asset_id=asset_id, user_id=user_id)
        if asset is None:
            raise build_error(
                INVALID_LIFECYCLE_TRANSITION,
                detail="Primary asset must belong to the same user.",
                status_code=404,
            )

        item_image = self.repository.attach_image_asset(
            closet_item_id=item.id,
            asset_id=asset.id,
            role=role,
        )
        item.primary_image_id = item_image.id
        self._recompute_review_readiness(item)
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="primary_image_set",
            payload={"asset_id": str(asset.id), "role": role.value},
        )
        self.session.commit()
        self.session.refresh(item)
        return item

    def update_processing_state(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        processing_status: ProcessingStatus,
        failure_summary: str | None = None,
        event_type: str = "processing_status_updated",
        actor_type: AuditActorType = AuditActorType.SYSTEM,
        actor_user_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> ClosetItem:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        self._ensure_not_archived(item)

        if processing_status == ProcessingStatus.RUNNING:
            if not self.repository.has_active_primary_image(item=item):
                raise build_error(MISSING_PRIMARY_IMAGE)
            if item.lifecycle_status not in {LifecycleStatus.DRAFT, LifecycleStatus.PROCESSING}:
                raise build_error(INVALID_LIFECYCLE_TRANSITION)
            item.lifecycle_status = LifecycleStatus.PROCESSING
        elif processing_status in {
            ProcessingStatus.COMPLETED,
            ProcessingStatus.COMPLETED_WITH_ISSUES,
            ProcessingStatus.FAILED,
        }:
            if item.lifecycle_status != LifecycleStatus.PROCESSING:
                raise build_error(INVALID_LIFECYCLE_TRANSITION)
            item.lifecycle_status = LifecycleStatus.REVIEW
            self._recompute_review_readiness(item)
        elif processing_status == ProcessingStatus.PENDING:
            if not self.repository.has_active_primary_image(item=item):
                raise build_error(MISSING_PRIMARY_IMAGE)
            if item.lifecycle_status not in {
                LifecycleStatus.DRAFT,
                LifecycleStatus.PROCESSING,
                LifecycleStatus.REVIEW,
            }:
                raise build_error(INVALID_LIFECYCLE_TRANSITION)
            item.lifecycle_status = LifecycleStatus.PROCESSING
        else:
            raise build_error(INVALID_LIFECYCLE_TRANSITION)

        item.processing_status = processing_status
        item.failure_summary = failure_summary
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            event_type=event_type,
            payload={
                "processing_status": processing_status.value,
                "lifecycle_status": item.lifecycle_status.value,
                "failure_summary": failure_summary,
                **(payload or {}),
            }
            if payload is not None
            else {
                "processing_status": processing_status.value,
                "lifecycle_status": item.lifecycle_status.value,
                "failure_summary": failure_summary,
            },
        )
        self.repository.upsert_metadata_projection(item=item, taxonomy_version=TAXONOMY_VERSION)
        if commit:
            self.session.commit()
            self.session.refresh(item)
        return item

    def upsert_field_state(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        field_name: str,
        canonical_value: Any | None,
        source: FieldSource,
        review_state: FieldReviewState,
        applicability_state: ApplicabilityState,
        confidence: float | None = None,
        taxonomy_version: str = TAXONOMY_VERSION,
    ) -> ClosetItemFieldState:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        self._ensure_not_archived(item)

        if not is_supported_field_name(field_name):
            raise build_error(INVALID_FIELD_NAME)
        if not is_supported_taxonomy_version(taxonomy_version):
            raise build_error(UNSUPPORTED_TAXONOMY_VERSION)

        field_state = self.repository.upsert_field_state(
            closet_item_id=item.id,
            field_name=field_name,
            canonical_value=canonical_value,
            source=source,
            confidence=confidence,
            review_state=review_state,
            applicability_state=applicability_state,
            taxonomy_version=taxonomy_version,
        )
        if field_name == "title":
            if applicability_state == ApplicabilityState.VALUE and isinstance(canonical_value, str):
                item.title = canonical_value
            else:
                item.title = None

        self._recompute_review_readiness(item)
        self.repository.upsert_metadata_projection(item=item, taxonomy_version=taxonomy_version)
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="field_state_upserted",
            payload={"field_name": field_name},
        )
        self.session.commit()
        self.session.refresh(field_state)
        return field_state

    def recompute_review_readiness(self, *, item_id: UUID, user_id: UUID) -> ClosetItem:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        self._ensure_not_archived(item)
        self._recompute_review_readiness(item)
        self.repository.upsert_metadata_projection(item=item, taxonomy_version=TAXONOMY_VERSION)
        self.session.commit()
        self.session.refresh(item)
        return item

    def confirm_item(self, *, item_id: UUID, user_id: UUID) -> ClosetItem:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        self._ensure_not_archived(item)
        if item.lifecycle_status != LifecycleStatus.REVIEW:
            raise build_error(INVALID_LIFECYCLE_TRANSITION)
        if not self.repository.has_active_primary_image(item=item):
            raise build_error(MISSING_PRIMARY_IMAGE)

        missing_fields = self._missing_required_confirmation_fields(item)
        if missing_fields:
            raise build_error(
                MISSING_REQUIRED_CONFIRMATION_FIELDS,
                detail=(
                    "Missing required confirmation fields: "
                    + ", ".join(sorted(missing_fields))
                    + "."
                ),
            )

        item.lifecycle_status = LifecycleStatus.CONFIRMED
        item.review_status = ReviewStatus.CONFIRMED
        item.confirmed_at = utcnow()
        self.repository.upsert_metadata_projection(item=item, taxonomy_version=TAXONOMY_VERSION)
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="item_confirmed",
            payload={"confirmed_at": item.confirmed_at.isoformat()},
        )
        self.session.commit()
        self.session.refresh(item)
        return item

    def archive_item(self, *, item_id: UUID, user_id: UUID) -> ClosetItem:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        self._ensure_not_archived(item)
        if item.lifecycle_status != LifecycleStatus.CONFIRMED:
            raise build_error(INVALID_LIFECYCLE_TRANSITION)

        item.lifecycle_status = LifecycleStatus.ARCHIVED
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="item_archived",
            payload={"archived_at": utcnow().isoformat()},
        )
        self.session.commit()
        self.session.refresh(item)
        return item

    def record_audit_event(
        self,
        *,
        item_id: UUID,
        actor_type: AuditActorType,
        actor_user_id: UUID | None,
        event_type: str,
        payload: Any | None,
        scoped_user_id: UUID,
    ) -> None:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=scoped_user_id)
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            event_type=event_type,
            payload=payload,
        )
        self.session.commit()

    def _ensure_not_archived(self, item: ClosetItem) -> None:
        if item.lifecycle_status == LifecycleStatus.ARCHIVED:
            raise build_error(INVALID_LIFECYCLE_TRANSITION, detail="Archived items are immutable.")

    def _recompute_review_readiness(self, item: ClosetItem) -> None:
        if item.lifecycle_status == LifecycleStatus.CONFIRMED:
            item.review_status = ReviewStatus.CONFIRMED
            return

        has_primary_image = self.repository.has_active_primary_image(item=item)
        missing_required_fields = self._missing_required_confirmation_fields(item)
        if has_primary_image and not missing_required_fields:
            item.review_status = ReviewStatus.READY_TO_CONFIRM
        else:
            item.review_status = ReviewStatus.NEEDS_REVIEW

    def _missing_required_confirmation_fields(self, item: ClosetItem) -> set[str]:
        field_states = {
            field_state.field_name: field_state
            for field_state in self.repository.list_field_states(closet_item_id=item.id)
        }
        return {
            field_name
            for field_name in REQUIRED_CONFIRMATION_FIELDS
            if not is_confirmed_field_state(field_states.get(field_name))
        }
