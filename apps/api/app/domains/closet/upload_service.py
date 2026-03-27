from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
from app.domains.closet.errors import (
    CLOSET_ITEM_NOT_FOUND,
    IDEMPOTENCY_CONFLICT,
    INVALID_LIFECYCLE_TRANSITION,
    UNSUPPORTED_UPLOAD_MIME_TYPE,
    UPLOAD_ALREADY_FINALIZED,
    UPLOAD_CHECKSUM_MISMATCH,
    UPLOAD_DIMENSIONS_EXCEEDED,
    UPLOAD_INTENT_EXPIRED,
    UPLOAD_INTENT_NOT_FOUND,
    UPLOAD_NOT_PRESENT,
    UPLOAD_TOO_LARGE,
    UPLOAD_VALIDATION_FAILED,
    build_error,
)
from app.domains.closet.image_processing_service import ClosetImageProcessingService
from app.domains.closet.models import (
    AuditActorType,
    ClosetItem,
    ClosetItemImageRole,
    ClosetUploadIntent,
    LifecycleStatus,
    MediaAssetSourceKind,
    ProcessingRunType,
    ProcessingStatus,
    ReviewStatus,
    UploadIntentStatus,
    utcnow,
)
from app.domains.closet.repository import ClosetRepository, is_confirmed_field_state
from app.domains.closet.taxonomy import REQUIRED_CONFIRMATION_FIELDS

CREATE_DRAFT_OPERATION = "create_draft"
COMPLETE_UPLOAD_OPERATION = "complete_upload"
RESOURCE_TYPE_CLOSET_ITEM = "closet_item"


@dataclass(frozen=True)
class UploadIntentResult:
    upload_intent: ClosetUploadIntent
    presigned_upload: PresignedUpload


@dataclass(frozen=True)
class ValidatedUpload:
    file_size: int
    mime_type: str
    sha256: str
    width: int
    height: int


class InvalidReviewCursorError(ValueError):
    pass


class ClosetDraftUploadService:
    def __init__(
        self,
        *,
        session: Session,
        repository: ClosetRepository,
        storage: ObjectStorageClient,
        image_processing_service: ClosetImageProcessingService,
    ) -> None:
        self.session = session
        self.repository = repository
        self.storage = storage
        self.image_processing_service = image_processing_service

    def create_draft(
        self,
        *,
        user_id: UUID,
        idempotency_key: str,
        title: str | None,
    ) -> tuple[ClosetItem, int]:
        request_fingerprint = hash_request_payload({"title": title})
        replay = self.repository.get_idempotency_record(
            user_id=user_id,
            operation=CREATE_DRAFT_OPERATION,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            self._ensure_matching_idempotency(replay.request_fingerprint, request_fingerprint)
            item = self.repository.require_item_for_user(
                item_id=replay.resource_id,
                user_id=user_id,
            )
            return item, replay.response_status_code

        item = self.repository.create_item(user_id=user_id, title=title)
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.USER,
            actor_user_id=user_id,
            event_type="item_created",
            payload={"lifecycle_status": item.lifecycle_status.value},
        )
        self.repository.create_idempotency_record(
            user_id=user_id,
            operation=CREATE_DRAFT_OPERATION,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            resource_type=RESOURCE_TYPE_CLOSET_ITEM,
            resource_id=item.id,
            response_status_code=201,
        )
        self.session.commit()
        self.session.refresh(item)
        return item, 201

    def get_draft(self, *, item_id: UUID, user_id: UUID) -> ClosetItem:
        item = self.repository.require_item_for_user(item_id=item_id, user_id=user_id)
        if item.lifecycle_status in {LifecycleStatus.CONFIRMED, LifecycleStatus.ARCHIVED}:
            raise build_error(CLOSET_ITEM_NOT_FOUND)
        return item

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
        item = self.get_draft(item_id=item_id, user_id=user_id)
        if self.repository.has_active_primary_image(item=item) or item.primary_image_id is not None:
            raise build_error(
                INVALID_LIFECYCLE_TRANSITION,
                detail="This draft already has a primary image.",
            )
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
        idempotency_key: str,
        upload_intent_id: UUID,
    ) -> tuple[ClosetItem, int]:
        request_fingerprint = hash_request_payload(
            {"item_id": str(item_id), "upload_intent_id": str(upload_intent_id)}
        )
        replay = self.repository.get_idempotency_record(
            user_id=user_id,
            operation=COMPLETE_UPLOAD_OPERATION,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            self._ensure_matching_idempotency(replay.request_fingerprint, request_fingerprint)
            item = self.repository.require_item_for_user(
                item_id=replay.resource_id,
                user_id=user_id,
            )
            return item, replay.response_status_code

        item = self.get_draft(item_id=item_id, user_id=user_id)
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
        if self.repository.has_active_primary_image(item=item) or item.primary_image_id is not None:
            raise build_error(
                INVALID_LIFECYCLE_TRANSITION,
                detail="This draft already has a primary image.",
            )

        try:
            validated_upload = self._validate_uploaded_object(upload_intent)
        except Exception as exc:
            code, detail = resolve_upload_error(exc)
            self._mark_upload_failure(
                item=item,
                upload_intent=upload_intent,
                error_code=code,
                error_detail=detail,
            )
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
            detail = "Uploaded object is missing from storage."
            self._mark_upload_failure(
                item=item,
                upload_intent=upload_intent,
                error_code=UPLOAD_NOT_PRESENT,
                error_detail=detail,
            )
            raise build_error(UPLOAD_NOT_PRESENT, detail=detail) from exc

        try:
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
            )
            item.primary_image_id = item_image.id
            item.failure_summary = None
            self._recompute_review_status(item)
            self.repository.mark_upload_intent_finalized(
                upload_intent=upload_intent,
                finalized_at=now,
            )
            self.repository.create_audit_event(
                closet_item_id=item.id,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                event_type="upload_finalized",
                payload={
                    "asset_id": str(media_asset.id),
                    "upload_intent_id": str(upload_intent.id),
                },
            )
            self.repository.create_processing_run(
                closet_item_id=item.id,
                run_type=ProcessingRunType.UPLOAD_VALIDATION,
                status=ProcessingStatus.COMPLETED,
                started_at=now,
                completed_at=now,
            )
            self.image_processing_service.enqueue_processing_for_item(
                item=item,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                raise_on_duplicate=False,
            )
            self.repository.create_idempotency_record(
                user_id=user_id,
                operation=COMPLETE_UPLOAD_OPERATION,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                resource_type=RESOURCE_TYPE_CLOSET_ITEM,
                resource_id=item.id,
                response_status_code=200,
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            self.storage.delete_object(bucket=settings.minio_bucket, key=final_key)
            raise

        try:
            self.storage.delete_object(
                bucket=upload_intent.staging_bucket,
                key=upload_intent.staging_key,
            )
        except Exception:
            pass

        self.session.refresh(item)
        return item, 200

    def list_review_items(
        self,
        *,
        user_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[ClosetItem], str | None]:
        cursor_updated_at, cursor_item_id = decode_review_cursor(cursor)
        items = self.repository.list_review_items(
            user_id=user_id,
            cursor_updated_at=cursor_updated_at,
            cursor_item_id=cursor_item_id,
            limit=limit + 1,
        )
        has_more = len(items) > limit
        visible_items = items[:limit]
        next_cursor = None
        if has_more and visible_items:
            last_item = visible_items[-1]
            next_cursor = encode_review_cursor(last_item.updated_at, last_item.id)
        return visible_items, next_cursor

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

    def _mark_upload_failure(
        self,
        *,
        item: ClosetItem,
        upload_intent: ClosetUploadIntent,
        error_code: str,
        error_detail: str,
    ) -> None:
        self.repository.mark_upload_intent_failed(
            upload_intent=upload_intent,
            error_code=error_code,
            error_detail=error_detail,
        )
        item.failure_summary = error_detail
        self.session.commit()

    def _ensure_matching_idempotency(
        self,
        expected_fingerprint: str,
        actual_fingerprint: str,
    ) -> None:
        if expected_fingerprint != actual_fingerprint:
            raise build_error(IDEMPOTENCY_CONFLICT)

    def _recompute_review_status(self, item: ClosetItem) -> None:
        if item.lifecycle_status == LifecycleStatus.CONFIRMED:
            item.review_status = ReviewStatus.CONFIRMED
            return

        field_states = {
            field_state.field_name: field_state
            for field_state in self.repository.list_field_states(closet_item_id=item.id)
        }
        missing_fields = {
            field_name
            for field_name in REQUIRED_CONFIRMATION_FIELDS
            if not is_confirmed_field_state(field_states.get(field_name))
        }
        if item.primary_image_id is not None and not missing_fields:
            item.review_status = ReviewStatus.READY_TO_CONFIRM
        else:
            item.review_status = ReviewStatus.NEEDS_REVIEW

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


def build_staging_key(*, user_id: UUID, item_id: UUID, upload_intent_id: UUID) -> str:
    return f"closet/staging/{user_id}/{item_id}/{upload_intent_id}"


def build_original_key(*, user_id: UUID, item_id: UUID, asset_id: UUID) -> str:
    return f"closet/originals/{user_id}/{item_id}/{asset_id}"


def encode_review_cursor(updated_at: datetime, item_id: UUID) -> str:
    payload = f"{normalize_utc_datetime(updated_at).isoformat()}|{item_id}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_review_cursor(cursor: str | None) -> tuple[datetime | None, UUID | None]:
    if cursor is None:
        return None, None

    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        updated_at_raw, item_id_raw = decoded.split("|", 1)
        return datetime.fromisoformat(updated_at_raw), UUID(item_id_raw)
    except Exception as exc:
        raise InvalidReviewCursorError("Invalid review cursor.") from exc


def hash_request_payload(payload: dict[str, object | None]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def resolve_upload_error(exc: Exception) -> tuple[str, str]:
    if hasattr(exc, "code") and hasattr(exc, "detail"):
        return str(getattr(exc, "code")), str(getattr(exc, "detail"))
    return UPLOAD_VALIDATION_FAILED, "The upload could not be validated."


def normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
