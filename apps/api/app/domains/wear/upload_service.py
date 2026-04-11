from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import (
    WEAR_UPLOAD_ALLOWED_MIME_TYPES,
    WEAR_UPLOAD_INTENT_TTL_SECONDS,
    WEAR_UPLOAD_MAX_FILE_SIZE,
    WEAR_UPLOAD_MAX_HEIGHT,
    WEAR_UPLOAD_MAX_WIDTH,
    settings,
)
from app.core.storage import ObjectStorageClient, PresignedUpload
from app.domains.closet.models import MediaAssetSourceKind
from app.domains.wear.models import (
    WearLogSource,
    WearLogStatus,
    WearProcessingRunType,
    WearUploadIntentStatus,
)
from app.domains.wear.repository import WearJobRepository, WearRepository
from app.domains.wear.service import WearLogDetailSnapshot, WearService


@dataclass(frozen=True)
class WearUploadIntentResult:
    upload_intent_id: UUID
    presigned_upload: PresignedUpload


@dataclass(frozen=True)
class ValidatedUpload:
    file_size: int
    mime_type: str
    sha256: str
    width: int
    height: int


class WearUploadService:
    def __init__(
        self,
        *,
        session: Session,
        repository: WearRepository,
        job_repository: WearJobRepository,
        storage: ObjectStorageClient,
    ) -> None:
        self.session = session
        self.repository = repository
        self.job_repository = job_repository
        self.storage = storage

    def create_upload_intent(
        self,
        *,
        wear_log_id: UUID,
        user_id: UUID,
        filename: str,
        mime_type: str,
        file_size: int,
        sha256: str,
    ) -> WearUploadIntentResult:
        wear_log = self._get_wear_log_or_raise(wear_log_id=wear_log_id, user_id=user_id)
        if wear_log.archived_at is not None:
            raise WearUploadError(409, "Archived wear events cannot accept new uploads.")
        self._validate_upload_metadata(mime_type=mime_type, file_size=file_size, sha256=sha256)

        now = utcnow()
        existing_intent = self.repository.get_pending_upload_intent_for_log(wear_log_id=wear_log.id)
        if existing_intent is not None:
            if normalize_utc_datetime(existing_intent.expires_at) <= now:
                self.repository.mark_upload_intent_expired(upload_intent=existing_intent)
                self.session.commit()
            else:
                return WearUploadIntentResult(
                    upload_intent_id=existing_intent.id,
                    presigned_upload=self.storage.generate_presigned_upload(
                        bucket=existing_intent.staging_bucket,
                        key=existing_intent.staging_key,
                        content_type=existing_intent.mime_type,
                        expires_in_seconds=WEAR_UPLOAD_INTENT_TTL_SECONDS,
                    ),
                )

        upload_intent_id = uuid4()
        upload_intent = self.repository.create_upload_intent(
            upload_intent_id=upload_intent_id,
            wear_log_id=wear_log.id,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            sha256=sha256,
            staging_bucket=settings.minio_bucket,
            staging_key=build_staging_key(
                user_id=user_id,
                wear_log_id=wear_log.id,
                upload_intent_id=upload_intent_id,
            ),
            expires_at=now + timedelta(seconds=WEAR_UPLOAD_INTENT_TTL_SECONDS),
        )
        self.session.commit()
        return WearUploadIntentResult(
            upload_intent_id=upload_intent.id,
            presigned_upload=self.storage.generate_presigned_upload(
                bucket=upload_intent.staging_bucket,
                key=upload_intent.staging_key,
                content_type=upload_intent.mime_type,
                expires_in_seconds=WEAR_UPLOAD_INTENT_TTL_SECONDS,
            ),
        )

    def complete_upload(
        self,
        *,
        wear_log_id: UUID,
        user_id: UUID,
        upload_intent_id: UUID,
    ) -> WearLogDetailSnapshot:
        wear_log = self._get_wear_log_or_raise(wear_log_id=wear_log_id, user_id=user_id)
        upload_intent = self.repository.get_upload_intent_for_user(
            upload_intent_id=upload_intent_id,
            user_id=user_id,
        )
        if upload_intent is None or upload_intent.wear_log_id != wear_log.id:
            raise WearUploadError(404, "Wear-event upload intent not found.")

        now = utcnow()
        if upload_intent.status == WearUploadIntentStatus.FINALIZED:
            raise WearUploadError(409, "The upload intent has already been finalized.")
        if upload_intent.status == WearUploadIntentStatus.EXPIRED:
            raise WearUploadError(409, "The upload intent has expired.")
        if upload_intent.status == WearUploadIntentStatus.FAILED:
            raise WearUploadError(
                409,
                upload_intent.last_error_detail
                or "The upload intent has already failed validation.",
            )
        if normalize_utc_datetime(upload_intent.expires_at) <= now:
            self.repository.mark_upload_intent_expired(upload_intent=upload_intent)
            self.session.commit()
            raise WearUploadError(409, "The upload intent has expired.")

        try:
            validated_upload = self._validate_uploaded_object(upload_intent)
        except WearUploadError as exc:
            self.repository.mark_upload_intent_failed(
                upload_intent=upload_intent,
                error_code="upload_validation_failed",
                error_detail=exc.detail,
            )
            self.session.commit()
            raise

        asset_id = uuid4()
        final_key = build_final_key(user_id=user_id, wear_log_id=wear_log.id, asset_id=asset_id)
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
            self.repository.mark_upload_intent_failed(
                upload_intent=upload_intent,
                error_code="upload_not_present",
                error_detail=detail,
            )
            self.session.commit()
            raise WearUploadError(409, detail) from exc

        thumbnail_asset_id = None
        final_thumbnail_key = None
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

            staging_bytes = self.storage.get_object_bytes(
                bucket=upload_intent.staging_bucket,
                key=upload_intent.staging_key,
            )
            thumbnail_bytes, thumbnail_mime_type, thumbnail_width, thumbnail_height = build_thumbnail(
                image_bytes=staging_bytes,
                mime_type=validated_upload.mime_type,
            )
            if thumbnail_bytes is not None:
                thumbnail_asset_id = uuid4()
                final_thumbnail_key = build_thumbnail_key(
                    user_id=user_id,
                    wear_log_id=wear_log.id,
                    asset_id=thumbnail_asset_id,
                )
                self.storage.put_object_bytes(
                    bucket=settings.minio_bucket,
                    key=final_thumbnail_key,
                    content=thumbnail_bytes,
                    content_type=thumbnail_mime_type,
                )
                self.repository.create_media_asset(
                    asset_id=thumbnail_asset_id,
                    user_id=user_id,
                    bucket=settings.minio_bucket,
                    key=final_thumbnail_key,
                    mime_type=thumbnail_mime_type,
                    file_size=len(thumbnail_bytes),
                    checksum=hashlib.sha256(thumbnail_bytes).hexdigest(),
                    width=thumbnail_width,
                    height=thumbnail_height,
                    source_kind=MediaAssetSourceKind.DERIVED,
                    is_private=True,
                )

            photo = self.repository.create_wear_event_photo(
                wear_log_id=wear_log.id,
                asset_id=media_asset.id,
                thumbnail_asset_id=thumbnail_asset_id,
                position=self.repository.get_next_photo_position(wear_log_id=wear_log.id),
            )

            should_trigger_processing = (
                wear_log.primary_photo_id is None
                and wear_log.status in {
                    WearLogStatus.DRAFT,
                    WearLogStatus.FAILED,
                    WearLogStatus.NEEDS_REVIEW,
                    WearLogStatus.PROCESSING,
                }
            )
            if wear_log.primary_photo_id is None:
                wear_log.primary_photo_id = photo.id

            self.repository.mark_upload_intent_finalized(upload_intent=upload_intent, finalized_at=now)

            if should_trigger_processing:
                wear_log.status = WearLogStatus.PROCESSING
                wear_log.is_confirmed = False
                wear_log.confirmed_at = None
                wear_log.confirmed_item_count = 0
                wear_log.failure_code = None
                wear_log.failure_summary = None
                wear_log.source = WearLogSource.PHOTO_UPLOAD
                if not self.job_repository.has_pending_or_running_job(
                    wear_log_id=wear_log.id,
                    job_kind=WearProcessingRunType.PHOTO_ANALYSIS,
                ):
                    self.job_repository.enqueue_job(
                        wear_log_id=wear_log.id,
                        job_kind=WearProcessingRunType.PHOTO_ANALYSIS,
                    )

            self.session.commit()
        except Exception:
            self.session.rollback()
            self.storage.delete_object(bucket=settings.minio_bucket, key=final_key)
            if final_thumbnail_key is not None:
                self.storage.delete_object(bucket=settings.minio_bucket, key=final_thumbnail_key)
            raise

        try:
            self.storage.delete_object(
                bucket=upload_intent.staging_bucket,
                key=upload_intent.staging_key,
            )
        except Exception:
            pass

        return WearService(
            session=self.session,
            repository=self.repository,
            storage=self.storage,
        ).get_wear_log_detail(wear_log_id=wear_log.id, user_id=user_id)

    def _validate_upload_metadata(
        self,
        *,
        mime_type: str,
        file_size: int,
        sha256: str,
    ) -> None:
        if mime_type not in WEAR_UPLOAD_ALLOWED_MIME_TYPES:
            raise WearUploadError(422, "The uploaded MIME type is not supported.")
        if file_size <= 0 or file_size > WEAR_UPLOAD_MAX_FILE_SIZE:
            raise WearUploadError(422, "The uploaded file exceeds the allowed size limit.")
        if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256.lower()):
            raise WearUploadError(422, "sha256 must be a valid lowercase hexadecimal digest.")

    def _validate_uploaded_object(self, upload_intent) -> ValidatedUpload:
        object_meta = self.storage.head_object(
            bucket=upload_intent.staging_bucket,
            key=upload_intent.staging_key,
        )
        if object_meta is None:
            raise WearUploadError(409, "Uploaded object is missing from storage.")
        if object_meta.content_length != upload_intent.file_size:
            raise WearUploadError(409, "The uploaded file size did not match the declared upload.")
        if object_meta.content_type is not None and object_meta.content_type != upload_intent.mime_type:
            raise WearUploadError(409, "The uploaded MIME type did not match the declared upload.")

        image_bytes = self.storage.get_object_bytes(
            bucket=upload_intent.staging_bucket,
            key=upload_intent.staging_key,
        )
        checksum = hashlib.sha256(image_bytes).hexdigest()
        if checksum != upload_intent.sha256:
            raise WearUploadError(409, "The uploaded checksum did not match the declared upload.")

        try:
            image = Image.open(BytesIO(image_bytes))
            image.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise WearUploadError(422, "The uploaded image could not be validated.") from exc

        mime_type = mime_type_for_image(image)
        if mime_type != upload_intent.mime_type:
            raise WearUploadError(409, "The uploaded MIME type did not match the declared upload.")
        if image.width > WEAR_UPLOAD_MAX_WIDTH or image.height > WEAR_UPLOAD_MAX_HEIGHT:
            raise WearUploadError(422, "The uploaded image exceeds the allowed dimensions.")

        return ValidatedUpload(
            file_size=object_meta.content_length,
            mime_type=mime_type,
            sha256=checksum,
            width=image.width,
            height=image.height,
        )

    def _get_wear_log_or_raise(self, *, wear_log_id: UUID, user_id: UUID):
        wear_log = self.repository.get_wear_log_for_user(wear_log_id=wear_log_id, user_id=user_id)
        if wear_log is None:
            raise WearUploadError(404, "Wear log not found.")
        return wear_log


class WearUploadError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def build_staging_key(*, user_id: UUID, wear_log_id: UUID, upload_intent_id: UUID) -> str:
    return f"wear-events/staging/{user_id}/{wear_log_id}/{upload_intent_id}"


def build_final_key(*, user_id: UUID, wear_log_id: UUID, asset_id: UUID) -> str:
    return f"wear-events/photos/{user_id}/{wear_log_id}/{asset_id}"


def build_thumbnail_key(*, user_id: UUID, wear_log_id: UUID, asset_id: UUID) -> str:
    return f"wear-events/photos/{user_id}/{wear_log_id}/thumbnails/{asset_id}"


def mime_type_for_image(image: Image.Image) -> str:
    image_format = (image.format or "").upper()
    if image_format == "JPEG":
        return "image/jpeg"
    if image_format == "PNG":
        return "image/png"
    if image_format == "WEBP":
        return "image/webp"
    raise WearUploadError(422, "The uploaded MIME type is not supported.")


def normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


def build_thumbnail(
    *,
    image_bytes: bytes,
    mime_type: str,
    max_edge: int = 768,
) -> tuple[bytes | None, str, int | None, int | None]:
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError):
        return None, mime_type, None, None

    thumbnail = image.copy()
    thumbnail.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    if thumbnail.size == image.size:
        return None, mime_type, None, None

    output = BytesIO()
    format_name = "JPEG" if mime_type == "image/jpeg" else "PNG" if mime_type == "image/png" else "WEBP"
    save_kwargs = {"quality": 90} if format_name in {"JPEG", "WEBP"} else {}
    thumbnail.save(output, format=format_name, **save_kwargs)
    return output.getvalue(), mime_type, thumbnail.width, thumbnail.height
