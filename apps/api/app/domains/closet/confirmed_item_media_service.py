from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import (
    CLOSET_UPLOAD_ALLOWED_MIME_TYPES,
    CLOSET_UPLOAD_INTENT_TTL_SECONDS,
    CLOSET_UPLOAD_MAX_FILE_SIZE,
    CLOSET_UPLOAD_MAX_HEIGHT,
    CLOSET_UPLOAD_MAX_WIDTH,
    settings,
)
from app.core.storage import ObjectStorageClient, PresignedUpload
from app.domains.closet.browse_service import BrowseDetailSnapshot, ClosetBrowseService
from app.domains.closet.errors import (
    CONFIRMED_ITEM_IMAGE_NOT_FOUND,
    INVALID_CONFIRMED_ITEM_IMAGE_MUTATION,
    INVALID_LIFECYCLE_TRANSITION,
    LAST_CONFIRMED_ITEM_IMAGE_REQUIRED,
    UPLOAD_ALREADY_FINALIZED,
    UPLOAD_CHECKSUM_MISMATCH,
    UPLOAD_DIMENSIONS_EXCEEDED,
    UPLOAD_INTENT_EXPIRED,
    UPLOAD_INTENT_NOT_FOUND,
    UPLOAD_NOT_PRESENT,
    UPLOAD_TOO_LARGE,
    UPLOAD_VALIDATION_FAILED,
    UNSUPPORTED_UPLOAD_MIME_TYPE,
    build_error,
)
from app.domains.closet.image_processing_service import ClosetImageProcessingService
from app.domains.closet.models import (
    AuditActorType,
    ClosetItem,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetUploadIntent,
    LifecycleStatus,
    MediaAssetSourceKind,
    UploadIntentStatus,
    utcnow,
)
from app.domains.closet.repository import ClosetRepository
from app.domains.closet.upload_service import (
    UploadIntentResult,
    ValidatedUpload,
    build_original_key,
    build_staging_key,
    normalize_utc_datetime,
    resolve_upload_error,
)

logger = logging.getLogger(__name__)


class ConfirmedClosetItemMediaService:
    def __init__(
        self,
        *,
        session: Session,
        repository: ClosetRepository,
        storage: ObjectStorageClient,
        browse_service: ClosetBrowseService,
        image_processing_service: ClosetImageProcessingService,
    ) -> None:
        self.session = session
        self.repository = repository
        self.storage = storage
        self.browse_service = browse_service
        self.image_processing_service = image_processing_service

    def create_upload_intent(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        filename: str,
        mime_type: str,
        file_size: int,
        sha256: str,
    ) -> UploadIntentResult:
        item = self._require_confirmed_item(item_id=item_id, user_id=user_id)
        self._validate_upload_metadata(mime_type=mime_type, file_size=file_size)

        now = utcnow()
        existing_intent = self.repository.get_pending_upload_intent_for_item(closet_item_id=item.id)
        if existing_intent is not None:
            if normalize_utc_datetime(existing_intent.expires_at) <= now:
                self.repository.mark_upload_intent_expired(upload_intent=existing_intent)
                self.session.commit()
            else:
                return UploadIntentResult(
                    upload_intent=existing_intent,
                    presigned_upload=self._build_presigned_upload(existing_intent, now=now),
                )

        upload_intent_id = uuid4()
        upload_intent = self.repository.create_upload_intent(
            upload_intent_id=upload_intent_id,
            closet_item_id=item.id,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            sha256=sha256,
            staging_bucket=settings.minio_bucket,
            staging_key=build_staging_key(
                user_id=user_id,
                item_id=item.id,
                upload_intent_id=upload_intent_id,
            ),
            expires_at=now + timedelta(seconds=CLOSET_UPLOAD_INTENT_TTL_SECONDS),
        )
        self.session.commit()
        self.session.refresh(upload_intent)
        return UploadIntentResult(
            upload_intent=upload_intent,
            presigned_upload=self._build_presigned_upload(upload_intent, now=now),
        )

    def complete_upload(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        upload_intent_id: UUID,
    ) -> BrowseDetailSnapshot:
        item = self._require_confirmed_item(item_id=item_id, user_id=user_id)
        upload_intent = self.repository.get_upload_intent_for_user(
            upload_intent_id=upload_intent_id,
            user_id=user_id,
        )
        if upload_intent is None or upload_intent.closet_item_id != item.id:
            raise build_error(UPLOAD_INTENT_NOT_FOUND)

        now = utcnow()
        if upload_intent.status == UploadIntentStatus.FINALIZED:
            raise build_error(UPLOAD_ALREADY_FINALIZED)
        if upload_intent.status == UploadIntentStatus.EXPIRED:
            raise build_error(UPLOAD_INTENT_EXPIRED)
        if normalize_utc_datetime(upload_intent.expires_at) <= now:
            self.repository.mark_upload_intent_expired(upload_intent=upload_intent)
            self.session.commit()
            raise build_error(UPLOAD_INTENT_EXPIRED)
        if upload_intent.status == UploadIntentStatus.FAILED:
            raise build_error(
                UPLOAD_VALIDATION_FAILED,
                detail=upload_intent.last_error_detail
                or "The upload intent has already failed validation.",
            )

        try:
            validated_upload = self._validate_uploaded_object(upload_intent)
        except Exception as exc:
            code, detail = resolve_upload_error(exc)
            self.repository.mark_upload_intent_failed(
                upload_intent=upload_intent,
                error_code=code,
                error_detail=detail,
            )
            self.session.commit()
            raise build_error(code, detail=detail) from exc

        asset_id = uuid4()
        final_key = build_original_key(user_id=user_id, item_id=item.id, asset_id=asset_id)

        try:
            self.storage.copy_object(
                source_bucket=upload_intent.staging_bucket,
                source_key=upload_intent.staging_key,
                destination_bucket=settings.minio_bucket,
                destination_key=final_key,
                content_type=validated_upload.mime_type,
            )
        except FileNotFoundError as exc:
            self.repository.mark_upload_intent_failed(
                upload_intent=upload_intent,
                error_code=UPLOAD_NOT_PRESENT,
                error_detail="Uploaded object is missing from storage.",
            )
            self.session.commit()
            raise build_error(
                UPLOAD_NOT_PRESENT, detail="Uploaded object is missing from storage."
            ) from exc

        try:
            had_primary_image = self.repository.has_active_primary_image(item=item)
            media_asset = self.repository.create_media_asset(
                asset_id=asset_id,
                user_id=user_id,
                bucket=settings.minio_bucket,
                key=final_key,
                mime_type=validated_upload.mime_type,
                file_size=validated_upload.file_size,
                checksum=validated_upload.sha256,
                width=validated_upload.width,
                height=validated_upload.height,
                source_kind=MediaAssetSourceKind.UPLOAD,
                is_private=True,
            )
            item_image = self.repository.attach_image_asset(
                closet_item_id=item.id,
                asset_id=media_asset.id,
                role=ClosetItemImageRole.ORIGINAL,
                position=self.repository.get_next_image_position(
                    closet_item_id=item.id,
                    role=ClosetItemImageRole.ORIGINAL,
                ),
            )
            if not had_primary_image:
                item.primary_image_id = item_image.id
            self.repository.mark_upload_intent_finalized(
                upload_intent=upload_intent,
                finalized_at=now,
            )
            self.repository.create_audit_event(
                closet_item_id=item.id,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                event_type="confirmed_item_image_added",
                payload={
                    "asset_id": str(media_asset.id),
                    "image_id": str(item_image.id),
                    "position": item_image.position,
                    "is_primary": item.primary_image_id == item_image.id,
                    "upload_intent_id": str(upload_intent.id),
                },
            )
            if not had_primary_image:
                self.image_processing_service.enqueue_processing_for_item(
                    item=item,
                    actor_type=AuditActorType.USER,
                    actor_user_id=user_id,
                    raise_on_duplicate=False,
                )
            self.session.commit()
        except Exception:
            self.session.rollback()
            self.storage.delete_object(bucket=settings.minio_bucket, key=final_key)
            raise

        try:
            self.storage.delete_object(bucket=upload_intent.staging_bucket, key=upload_intent.staging_key)
        except Exception:
            pass

        logger.info(
            "closet_confirmed_item_image_added",
            extra={"closet_item_id": str(item.id), "user_id": str(user_id)},
        )
        return self.browse_service.get_confirmed_item_detail(item_id=item.id, user_id=user_id)

    def reorder_images(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        image_ids: list[UUID],
    ) -> BrowseDetailSnapshot:
        item = self._require_confirmed_item(item_id=item_id, user_id=user_id)
        active_records = self.repository.list_active_image_assets_for_item(
            closet_item_id=item.id,
            role=ClosetItemImageRole.ORIGINAL,
        )
        active_images = [image for image, _ in active_records]
        active_ids = [image.id for image in active_images]
        if len(image_ids) != len(active_ids) or len(set(image_ids)) != len(image_ids):
            raise build_error(
                INVALID_CONFIRMED_ITEM_IMAGE_MUTATION,
                detail="Image reorder payload must include each active original image exactly once.",
            )
        if set(image_ids) != set(active_ids):
            raise build_error(
                INVALID_CONFIRMED_ITEM_IMAGE_MUTATION,
                detail="Image reorder payload did not match the active original image set.",
            )
        if item.primary_image_id is not None and image_ids[0] != item.primary_image_id:
            raise build_error(
                INVALID_CONFIRMED_ITEM_IMAGE_MUTATION,
                detail="The primary image must remain first in the ordered image set.",
            )

        image_by_id = {image.id: image for image in active_images}
        for index, image_id in enumerate(image_ids):
            image_by_id[image_id].position = index

        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="confirmed_item_images_reordered",
            payload={"image_ids": [str(image_id) for image_id in image_ids]},
        )
        self.session.commit()
        logger.info(
            "closet_confirmed_item_images_reordered",
            extra={"closet_item_id": str(item.id), "user_id": str(user_id)},
        )
        return self.browse_service.get_confirmed_item_detail(item_id=item.id, user_id=user_id)

    def set_primary_image(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        image_id: UUID,
    ) -> BrowseDetailSnapshot:
        item = self._require_confirmed_item(item_id=item_id, user_id=user_id)
        image_record = self.repository.get_item_image_asset_for_item(
            closet_item_id=item.id,
            image_id=image_id,
        )
        if image_record is None:
            raise build_error(CONFIRMED_ITEM_IMAGE_NOT_FOUND)
        item_image, _ = image_record
        if item_image.role != ClosetItemImageRole.ORIGINAL or not item_image.is_active:
            raise build_error(
                INVALID_CONFIRMED_ITEM_IMAGE_MUTATION,
                detail="Only active original images can be promoted to primary.",
            )
        if item.primary_image_id == item_image.id:
            return self.browse_service.get_confirmed_item_detail(item_id=item.id, user_id=user_id)

        active_images = [
            image
            for image, _ in self.repository.list_active_image_assets_for_item(
                closet_item_id=item.id,
                role=ClosetItemImageRole.ORIGINAL,
            )
        ]
        item.primary_image_id = item_image.id
        self._resequence_original_images(active_images=active_images, primary_image_id=item_image.id)
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="confirmed_item_primary_image_set",
            payload={"image_id": str(item_image.id)},
        )
        self.image_processing_service.enqueue_processing_for_item(
            item=item,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            raise_on_duplicate=False,
        )
        self.session.commit()
        logger.info(
            "closet_confirmed_item_primary_image_set",
            extra={"closet_item_id": str(item.id), "user_id": str(user_id), "image_id": str(image_id)},
        )
        return self.browse_service.get_confirmed_item_detail(item_id=item.id, user_id=user_id)

    def remove_image(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        image_id: UUID,
    ) -> BrowseDetailSnapshot:
        item = self._require_confirmed_item(item_id=item_id, user_id=user_id)
        active_images = [
            image
            for image, _ in self.repository.list_active_image_assets_for_item(
                closet_item_id=item.id,
                role=ClosetItemImageRole.ORIGINAL,
            )
        ]
        image = next((candidate for candidate in active_images if candidate.id == image_id), None)
        if image is None:
            raise build_error(CONFIRMED_ITEM_IMAGE_NOT_FOUND)
        if len(active_images) <= 1:
            raise build_error(LAST_CONFIRMED_ITEM_IMAGE_REQUIRED)

        self.repository.archive_item_image(item_image=image, archived_by_user_id=user_id)
        remaining_images = [candidate for candidate in active_images if candidate.id != image.id]

        primary_changed = item.primary_image_id == image.id
        if primary_changed:
            new_primary = min(
                remaining_images,
                key=lambda candidate: (candidate.position, candidate.created_at, candidate.id),
            )
            item.primary_image_id = new_primary.id
        self._resequence_original_images(
            active_images=remaining_images,
            primary_image_id=item.primary_image_id,
        )
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="confirmed_item_image_removed",
            payload={"image_id": str(image.id), "was_primary": primary_changed},
        )
        if primary_changed:
            self.image_processing_service.enqueue_processing_for_item(
                item=item,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                raise_on_duplicate=False,
            )
        self.session.commit()
        logger.info(
            "closet_confirmed_item_image_removed",
            extra={"closet_item_id": str(item.id), "user_id": str(user_id), "image_id": str(image_id)},
        )
        return self.browse_service.get_confirmed_item_detail(item_id=item.id, user_id=user_id)

    def _require_confirmed_item(self, *, item_id: UUID, user_id: UUID) -> ClosetItem:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        if item.lifecycle_status != LifecycleStatus.CONFIRMED:
            raise build_error(INVALID_LIFECYCLE_TRANSITION)
        return item

    def _resequence_original_images(
        self,
        *,
        active_images: list[ClosetItemImage],
        primary_image_id: UUID | None,
    ) -> None:
        ordered_images = sorted(
            active_images,
            key=lambda image: (
                0 if primary_image_id == image.id else 1,
                image.position,
                image.created_at,
                image.id,
            ),
        )
        for index, image in enumerate(ordered_images):
            image.position = index

    def _validate_upload_metadata(self, *, mime_type: str, file_size: int) -> None:
        if mime_type not in CLOSET_UPLOAD_ALLOWED_MIME_TYPES:
            raise build_error(UNSUPPORTED_UPLOAD_MIME_TYPE)
        if file_size > CLOSET_UPLOAD_MAX_FILE_SIZE:
            raise build_error(UPLOAD_TOO_LARGE)

    def _build_presigned_upload(
        self,
        upload_intent: ClosetUploadIntent,
        *,
        now: datetime,
    ) -> PresignedUpload:
        expires_at = normalize_utc_datetime(upload_intent.expires_at)
        expires_in_seconds = max(1, int((expires_at - now).total_seconds()))
        presigned_upload = self.storage.generate_presigned_upload(
            bucket=upload_intent.staging_bucket,
            key=upload_intent.staging_key,
            content_type=upload_intent.mime_type,
            expires_in_seconds=expires_in_seconds,
        )
        return PresignedUpload(
            method=presigned_upload.method,
            url=presigned_upload.url,
            headers=presigned_upload.headers,
            expires_at=expires_at,
        )

    def _validate_uploaded_object(self, upload_intent: ClosetUploadIntent) -> ValidatedUpload:
        object_meta = self.storage.head_object(
            bucket=upload_intent.staging_bucket,
            key=upload_intent.staging_key,
        )
        if object_meta is None:
            raise build_error(UPLOAD_NOT_PRESENT)
        if object_meta.content_length > CLOSET_UPLOAD_MAX_FILE_SIZE:
            raise build_error(UPLOAD_TOO_LARGE)
        if object_meta.content_length != upload_intent.file_size:
            raise build_error(
                UPLOAD_VALIDATION_FAILED,
                detail="Uploaded file size did not match the declared file size.",
            )
        if object_meta.content_type is not None:
            if object_meta.content_type not in CLOSET_UPLOAD_ALLOWED_MIME_TYPES:
                raise build_error(UNSUPPORTED_UPLOAD_MIME_TYPE)
            if object_meta.content_type != upload_intent.mime_type:
                raise build_error(
                    UPLOAD_VALIDATION_FAILED,
                    detail="Uploaded object content type did not match the declared MIME type.",
                )

        content = self.storage.get_object_bytes(
            bucket=upload_intent.staging_bucket,
            key=upload_intent.staging_key,
        )
        checksum = hashlib.sha256(content).hexdigest()
        if checksum != upload_intent.sha256:
            raise build_error(UPLOAD_CHECKSUM_MISMATCH)

        try:
            with Image.open(BytesIO(content)) as image:
                image.load()
                width, height = image.size
                mime_type = Image.MIME.get(image.format or "")
        except (UnidentifiedImageError, OSError) as exc:
            raise build_error(
                UPLOAD_VALIDATION_FAILED,
                detail="Uploaded object could not be decoded as an image.",
            ) from exc

        if mime_type is None or mime_type not in CLOSET_UPLOAD_ALLOWED_MIME_TYPES:
            raise build_error(UNSUPPORTED_UPLOAD_MIME_TYPE)
        if mime_type != upload_intent.mime_type:
            raise build_error(
                UPLOAD_VALIDATION_FAILED,
                detail="Decoded image type did not match the declared MIME type.",
            )
        if width > CLOSET_UPLOAD_MAX_WIDTH or height > CLOSET_UPLOAD_MAX_HEIGHT:
            raise build_error(UPLOAD_DIMENSIONS_EXCEEDED)

        return ValidatedUpload(
            file_size=len(content),
            mime_type=mime_type,
            sha256=checksum,
            width=width,
            height=height,
        )
