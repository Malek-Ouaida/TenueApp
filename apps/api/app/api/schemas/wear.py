from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.closet import ClosetProcessingImageSnapshot, PresignedUploadDescriptor

WearContextValue = Literal["casual", "work", "event", "travel", "gym", "lounge"]
WearItemRoleValue = Literal[
    "top",
    "bottom",
    "dress",
    "outerwear",
    "shoes",
    "bag",
    "accessory",
    "other",
]
WearLogStatusValue = Literal["draft", "processing", "needs_review", "confirmed", "failed"]
WearDetectedItemStatusValue = Literal["detected", "excluded", "confirmed"]
WearItemSourceValue = Literal["manual", "from_outfit", "ai_matched", "manual_override"]


def _normalize_optional_text(
    value: str | None,
    *,
    max_length: int,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
    return normalized


class WearLogItemWriteRequest(BaseModel):
    closet_item_id: UUID
    role: WearItemRoleValue | None = None
    sort_index: int | None = Field(default=None, ge=0)
    detected_item_id: UUID | None = None
    source: WearItemSourceValue | None = None
    match_confidence: float | None = Field(default=None, ge=0, le=1)


class _WearLogWriteBase(BaseModel):
    wear_date: date
    worn_at: datetime | None = None
    captured_at: datetime | None = None
    timezone_name: str | None = None
    context: WearContextValue | None = None
    vibe: str | None = None
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=1000, field_name="Notes")

    @field_validator("vibe")
    @classmethod
    def normalize_vibe(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=255, field_name="Vibe")

    @field_validator("timezone_name")
    @classmethod
    def normalize_timezone_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 128:
            raise ValueError("timezone_name must be 128 characters or fewer.")
        return normalized


class ManualWearLogCreateRequest(_WearLogWriteBase):
    mode: Literal["manual_items"]
    items: list[WearLogItemWriteRequest] = Field(min_length=1, max_length=20)


class SavedOutfitWearLogCreateRequest(_WearLogWriteBase):
    mode: Literal["saved_outfit"]
    outfit_id: UUID


class PhotoUploadWearLogCreateRequest(_WearLogWriteBase):
    mode: Literal["photo_upload"]


WearLogCreateRequest: TypeAlias = Annotated[
    ManualWearLogCreateRequest | SavedOutfitWearLogCreateRequest | PhotoUploadWearLogCreateRequest,
    Field(discriminator="mode"),
]


class WearLogUpdateRequest(BaseModel):
    wear_date: date | None = None
    worn_at: datetime | None = None
    captured_at: datetime | None = None
    timezone_name: str | None = None
    context: WearContextValue | None = None
    vibe: str | None = None
    notes: str | None = None
    items: list[WearLogItemWriteRequest] | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=1000, field_name="Notes")

    @field_validator("vibe")
    @classmethod
    def normalize_vibe(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=255, field_name="Vibe")

    @field_validator("timezone_name")
    @classmethod
    def normalize_timezone_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 128:
            raise ValueError("timezone_name must be 128 characters or fewer.")
        return normalized


class WearUploadIntentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=255)
    file_size: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("sha256 must be a valid lowercase hexadecimal digest.")
        return normalized


class WearUploadIntentResponse(BaseModel):
    upload_intent_id: UUID
    expires_at: datetime
    upload: PresignedUploadDescriptor


class WearUploadCompleteRequest(BaseModel):
    upload_intent_id: UUID


class WearDetectedItemResolutionRequest(BaseModel):
    detected_item_id: UUID
    status: Literal["excluded"]
    exclusion_reason: str | None = None

    @field_validator("exclusion_reason")
    @classmethod
    def normalize_exclusion_reason(cls, value: str | None) -> str | None:
        return _normalize_optional_text(
            value,
            max_length=255,
            field_name="Exclusion reason",
        )


class WearLogConfirmRequest(BaseModel):
    expected_review_version: str
    worn_at: datetime | None = None
    captured_at: datetime | None = None
    timezone_name: str | None = None
    context: WearContextValue | None = None
    vibe: str | None = None
    notes: str | None = None
    items: list[WearLogItemWriteRequest] = Field(default_factory=list, max_length=20)
    resolved_detected_items: list[WearDetectedItemResolutionRequest] = Field(
        default_factory=list,
        max_length=20,
    )

    @field_validator("expected_review_version")
    @classmethod
    def normalize_expected_review_version(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("expected_review_version is required.")
        return normalized

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=1000, field_name="Notes")

    @field_validator("vibe")
    @classmethod
    def normalize_vibe(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=255, field_name="Vibe")

    @field_validator("timezone_name")
    @classmethod
    def normalize_timezone_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 128:
            raise ValueError("timezone_name must be 128 characters or fewer.")
        return normalized


class WearMediaSnapshot(BaseModel):
    asset_id: UUID
    mime_type: str
    width: int | None
    height: int | None
    url: str
    expires_at: datetime
    photo_id: UUID | None = None
    position: int | None = None


class WearLinkedOutfitSnapshot(BaseModel):
    id: UUID
    title: str | None
    is_favorite: bool
    is_archived: bool


class WearLoggedItemSnapshot(BaseModel):
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ClosetProcessingImageSnapshot | None
    thumbnail_image: ClosetProcessingImageSnapshot | None
    role: str | None
    sort_index: int
    detected_item_id: UUID | None = None


class WearCandidateItemSnapshot(BaseModel):
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ClosetProcessingImageSnapshot | None
    thumbnail_image: ClosetProcessingImageSnapshot | None


class WearMatchCandidateSnapshot(BaseModel):
    id: UUID
    closet_item_id: UUID
    rank: int
    score: float
    signals: object | None
    item: WearCandidateItemSnapshot | None


class WearDetectedItemSnapshot(BaseModel):
    id: UUID
    predicted_role: str | None
    predicted_category: str | None
    predicted_subcategory: str | None
    predicted_colors: list[str]
    confidence: float | None
    bbox: dict[str, float] | None
    status: WearDetectedItemStatusValue
    exclusion_reason: str | None
    crop_image: WearMediaSnapshot | None
    candidate_matches: list[WearMatchCandidateSnapshot]


class WearLogDetailSnapshot(BaseModel):
    id: UUID
    wear_date: date
    worn_at: datetime
    worn_time_precision: str
    captured_at: datetime | None
    timezone_name: str | None
    source: str
    status: WearLogStatusValue
    context: str | None
    vibe: str | None
    notes: str | None
    is_confirmed: bool
    confirmed_at: datetime | None
    archived_at: datetime | None
    item_count: int
    cover_image: WearMediaSnapshot | None
    primary_photo: WearMediaSnapshot | None
    photos: list[WearMediaSnapshot]
    linked_outfit: WearLinkedOutfitSnapshot | None
    items: list[WearLoggedItemSnapshot]
    detected_items: list[WearDetectedItemSnapshot]
    review_version: str
    can_confirm: bool
    failure_code: str | None
    failure_summary: str | None
    created_at: datetime
    updated_at: datetime


class WearLogTimelineItemSnapshot(BaseModel):
    id: UUID
    wear_date: date
    worn_at: datetime
    context: str | None
    status: WearLogStatusValue
    item_count: int
    source: str
    is_confirmed: bool
    cover_image: WearMediaSnapshot | None
    outfit_title: str | None
    created_at: datetime
    updated_at: datetime


class WearLogTimelineResponse(BaseModel):
    items: list[WearLogTimelineItemSnapshot]
    next_cursor: str | None


class WearCalendarEventSnapshot(BaseModel):
    id: UUID
    worn_at: datetime
    status: WearLogStatusValue
    item_count: int
    cover_image: WearMediaSnapshot | None
    title: str | None
    context: str | None


class WearCalendarDaySnapshot(BaseModel):
    date: date
    event_count: int
    primary_event_id: UUID | None
    primary_cover_image: WearMediaSnapshot | None
    events: list[WearCalendarEventSnapshot]
    has_wear_log: bool
    wear_log_id: UUID | None
    item_count: int
    source: str | None
    is_confirmed: bool | None
    cover_image: WearMediaSnapshot | None
    outfit_title: str | None


class WearCalendarResponse(BaseModel):
    days: list[WearCalendarDaySnapshot]
