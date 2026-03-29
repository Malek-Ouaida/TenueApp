from datetime import datetime
from typing import Any
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


class ClosetProcessingImageSnapshot(BaseModel):
    asset_id: UUID
    role: str
    mime_type: str
    width: int | None
    height: int | None
    url: str
    expires_at: datetime


class ClosetProcessingRunSnapshot(BaseModel):
    id: UUID
    run_type: str
    status: str
    retry_count: int
    started_at: datetime | None
    completed_at: datetime | None
    failure_code: str | None


class ClosetProviderResultSnapshot(BaseModel):
    id: UUID
    provider_name: str
    provider_model: str | None
    provider_version: str | None
    task_type: str
    status: str
    raw_payload: Any
    created_at: datetime


class ClosetProcessingSnapshot(BaseModel):
    item_id: UUID
    lifecycle_status: str
    processing_status: str
    review_status: str
    failure_summary: str | None
    can_reprocess: bool
    latest_run: ClosetProcessingRunSnapshot | None
    provider_results: list[ClosetProviderResultSnapshot]
    display_image: ClosetProcessingImageSnapshot | None
    original_image: ClosetProcessingImageSnapshot | None
    thumbnail_image: ClosetProcessingImageSnapshot | None


class ClosetFieldCandidateSnapshot(BaseModel):
    id: UUID
    field_name: str
    raw_value: Any
    normalized_candidate: Any
    confidence: float | None
    applicability_state: str
    conflict_notes: str | None
    provider_result_id: UUID | None
    created_at: datetime


class ClosetExtractionCurrentCandidateSet(BaseModel):
    provider_result_id: UUID
    status: str
    created_at: datetime
    field_candidates: list[ClosetFieldCandidateSnapshot]


class ClosetFieldStateSnapshot(BaseModel):
    field_name: str
    canonical_value: Any
    source: str
    confidence: float | None
    review_state: str
    applicability_state: str
    taxonomy_version: str
    updated_at: datetime


class ClosetMetadataProjectionSnapshot(BaseModel):
    taxonomy_version: str
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    secondary_colors: list[str] | None
    material: str | None
    pattern: str | None
    brand: str | None
    style_tags: list[str] | None
    occasion_tags: list[str] | None
    season_tags: list[str] | None
    confirmed_at: datetime | None
    updated_at: datetime


class ClosetExtractionSnapshot(BaseModel):
    item_id: UUID
    lifecycle_status: str
    review_status: str
    extraction_status: str
    normalization_status: str
    field_states_stale: bool
    can_reextract: bool
    source_image: ClosetProcessingImageSnapshot | None
    latest_run: ClosetProcessingRunSnapshot | None
    latest_normalization_run: ClosetProcessingRunSnapshot | None
    provider_results: list[ClosetProviderResultSnapshot]
    current_candidate_set: ClosetExtractionCurrentCandidateSet | None
    current_field_states: list[ClosetFieldStateSnapshot]
    metadata_projection: ClosetMetadataProjectionSnapshot | None
