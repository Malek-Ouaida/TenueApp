from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ClosetMetadataCategoryOption(BaseModel):
    name: str
    subcategories: list[str]


class ClosetMetadataOptionsResponse(BaseModel):
    taxonomy_version: str
    required_confirmation_fields: list[str]
    lifecycle_statuses: list[str]
    processing_statuses: list[str]
    review_statuses: list[str]
    categories: list[ClosetMetadataCategoryOption]
    colors: list[str]
    materials: list[str]
    patterns: list[str]
    style_tags: list[str]
    occasion_tags: list[str]
    season_tags: list[str]


class ClosetDraftCreateRequest(BaseModel):
    title: str | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 255:
            raise ValueError("Title must be 255 characters or fewer.")
        return normalized


class ClosetDraftSnapshot(BaseModel):
    id: UUID
    title: str | None
    lifecycle_status: str
    processing_status: str
    review_status: str
    failure_summary: str | None
    has_primary_image: bool
    created_at: datetime
    updated_at: datetime


class ClosetUploadIntentRequest(BaseModel):
    filename: str
    mime_type: str
    file_size: int = Field(gt=0)
    sha256: str

    @field_validator("filename")
    @classmethod
    def normalize_filename(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Filename is required.")
        if len(normalized) > 255:
            raise ValueError("Filename must be 255 characters or fewer.")
        return normalized

    @field_validator("mime_type")
    @classmethod
    def normalize_mime_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("MIME type is required.")
        return normalized

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("sha256 must be a 64-character lowercase hex string.")
        return normalized


class PresignedUploadDescriptor(BaseModel):
    method: str
    url: str
    headers: dict[str, str]


class ClosetUploadIntentResponse(BaseModel):
    upload_intent_id: UUID
    expires_at: datetime
    upload: PresignedUploadDescriptor


class ClosetUploadCompleteRequest(BaseModel):
    upload_intent_id: UUID


class ClosetReviewListResponse(BaseModel):
    items: list[ClosetDraftSnapshot]
    next_cursor: str | None
