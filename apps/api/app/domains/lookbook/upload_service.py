from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import (
    LOOKBOOK_UPLOAD_ALLOWED_MIME_TYPES,
    LOOKBOOK_UPLOAD_INTENT_TTL_SECONDS,
    LOOKBOOK_UPLOAD_MAX_FILE_SIZE,
    LOOKBOOK_UPLOAD_MAX_HEIGHT,
    LOOKBOOK_UPLOAD_MAX_WIDTH,
    settings,
)
from app.core.storage import ObjectStorageClient, PresignedUpload
from app.domains.closet.models import MediaAssetSourceKind
from app.domains.lookbook.errors import LookbookError
from app.domains.lookbook.models import LookbookUploadIntent, LookbookUploadIntentStatus, utcnow
from app.domains.lookbook.repository import LookbookRepository
from app.domains.lookbook.service import LookbookService, PrivateImageSnapshot


@dataclass(frozen=True)
class LookbookUploadIntentResult:
    upload_intent: LookbookUploadIntent
    presigned_upload: PresignedUpload


@dataclass(frozen=True)
class ValidatedUpload:
    file_size: int
    mime_type: str
    sha256: str
    width: int
    height: int


class LookbookUploadService:
    def __init__(
        self,
        *,
        session: Session,
        repository: LookbookRepository,
        storage: ObjectStorageClient,
    ) -> None:
        self.session = session
        self.repository = repository
        self.storage = storage

    def create_upload_intent(
        self,
        *,
        user_id: UUID,
        filename: str,
        mime_type: str,
        file_size: int,
        sha256: str,
    ) -> LookbookUploadIntentResult:
        lookbook = self._get_or_create_default_lookbook(user_id=user_id)
        self._validate_upload_metadata(mime_type=mime_type, file_size=file_size, sha256=sha256)
        self.repository.clear_expired_upload_intents(user_id=user_id)

        now = utcnow()
        upload_intent_id = uuid4()
        upload_intent = self.repository.create_upload_intent(
            upload_intent_id=upload_intent_id,
            lookbook_id=lookbook.id,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            sha256=sha256,
            staging_bucket=settings.minio_bucket,
            staging_key=build_staging_key(
                user_id=user_id,
                lookbook_id=lookbook.id,
                upload_intent_id=upload_intent_id,
            ),
            expires_at=now + timedelta(seconds=LOOKBOOK_UPLOAD_INTENT_TTL_SECONDS),
        )
        self.session.commit()
        self.session.refresh(upload_intent)
        return LookbookUploadIntentResult(
            upload_intent=upload_intent,
            presigned_upload=self.storage.generate_presigned_upload(
                bucket=upload_intent.staging_bucket,
                key=upload_intent.staging_key,
                content_type=upload_intent.mime_type,
                expires_in_seconds=LOOKBOOK_UPLOAD_INTENT_TTL_SECONDS,
            ),
        )

    def complete_upload(
        self,
        *,
        user_id: UUID,
        upload_intent_id: UUID,
    ) -> PrivateImageSnapshot:
        upload_intent = self.repository.get_upload_intent_for_user(
            upload_intent_id=upload_intent_id,
            user_id=user_id,
        )
        if upload_intent is None:
            raise LookbookError(404, "Lookbook upload intent not found.")

        now = utcnow()
        if upload_intent.status == LookbookUploadIntentStatus.FINALIZED:
            raise LookbookError(409, "The upload intent has already been finalized.")
        if upload_intent.status == LookbookUploadIntentStatus.EXPIRED:
            raise LookbookError(409, "The upload intent has expired.")
        if upload_intent.status == LookbookUploadIntentStatus.FAILED:
            raise LookbookError(
                409,
                upload_intent.last_error_detail or "The upload intent has already failed validation.",
            )
        if _normalize_datetime(upload_intent.expires_at) <= now:
            self.repository.mark_upload_intent_expired(upload_intent=upload_intent)
            self.session.commit()
            raise LookbookError(409, "The upload intent has expired.")

        try:
            validated_upload = self._validate_uploaded_object(upload_intent)
        except LookbookError as exc:
            self.repository.mark_upload_intent_failed(
                upload_intent=upload_intent,
                error_code="upload_validation_failed",
                error_detail=exc.detail,
            )
            self.session.commit()
            raise

        asset_id = uuid4()
        final_key = build_final_key(
            user_id=user_id,
            lookbook_id=upload_intent.lookbook_id,
            asset_id=asset_id,
        )

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
            raise LookbookError(409, detail) from exc

        asset = self.repository.create_media_asset(
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
        self.repository.mark_upload_intent_finalized(upload_intent=upload_intent, finalized_at=now)
        self.session.commit()
        return LookbookService(
            session=self.session,
            repository=self.repository,
            storage=self.storage,
        )._build_private_image_snapshot(asset)

    def _validate_upload_metadata(
        self,
        *,
        mime_type: str,
        file_size: int,
        sha256: str,
    ) -> None:
        if mime_type not in LOOKBOOK_UPLOAD_ALLOWED_MIME_TYPES:
            raise LookbookError(422, "The uploaded MIME type is not supported.")
        if file_size <= 0 or file_size > LOOKBOOK_UPLOAD_MAX_FILE_SIZE:
            raise LookbookError(422, "The uploaded file exceeds the allowed size limit.")
        if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256.lower()):
            raise LookbookError(422, "sha256 must be a valid lowercase hexadecimal digest.")

    def _validate_uploaded_object(self, upload_intent: LookbookUploadIntent) -> ValidatedUpload:
        object_meta = self.storage.head_object(
            bucket=upload_intent.staging_bucket,
            key=upload_intent.staging_key,
        )
        if object_meta is None:
            raise LookbookError(409, "Uploaded object is missing from storage.")
        if object_meta.content_length != upload_intent.file_size:
            raise LookbookError(409, "The uploaded file size did not match the declared upload.")
        if object_meta.content_type is not None and object_meta.content_type != upload_intent.mime_type:
            raise LookbookError(409, "The uploaded MIME type did not match the declared upload.")

        image_bytes = self.storage.get_object_bytes(
            bucket=upload_intent.staging_bucket,
            key=upload_intent.staging_key,
        )
        checksum = hashlib.sha256(image_bytes).hexdigest()
        if checksum != upload_intent.sha256:
            raise LookbookError(409, "The uploaded checksum did not match the declared upload.")

        try:
            image = Image.open(BytesIO(image_bytes))
            image.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise LookbookError(422, "The uploaded image could not be validated.") from exc

        mime_type = mime_type_for_image(image)
        if mime_type != upload_intent.mime_type:
            raise LookbookError(409, "The uploaded MIME type did not match the declared upload.")
        if image.width > LOOKBOOK_UPLOAD_MAX_WIDTH or image.height > LOOKBOOK_UPLOAD_MAX_HEIGHT:
            raise LookbookError(422, "The uploaded image exceeds the allowed dimensions.")

        return ValidatedUpload(
            file_size=object_meta.content_length,
            mime_type=mime_type,
            sha256=checksum,
            width=image.width,
            height=image.height,
        )

    def _get_or_create_default_lookbook(self, *, user_id: UUID):
        return self.repository.get_or_create_default_lookbook(
            user_id=user_id,
            title="Personal Lookbook",
            description=None,
        )


def mime_type_for_image(image: Image.Image) -> str:
    image_format = (image.format or "").upper()
    if image_format == "JPEG":
        return "image/jpeg"
    if image_format == "PNG":
        return "image/png"
    if image_format == "WEBP":
        return "image/webp"
    raise LookbookError(422, "Unsupported image format.")


def build_staging_key(*, user_id: UUID, lookbook_id: UUID, upload_intent_id: UUID) -> str:
    return f"lookbook/staging/{user_id}/{lookbook_id}/{upload_intent_id}"


def build_final_key(*, user_id: UUID, lookbook_id: UUID, asset_id: UUID) -> str:
    return f"lookbook/images/{user_id}/{lookbook_id}/{asset_id}"


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
