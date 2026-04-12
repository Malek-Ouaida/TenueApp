from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.closet import ClosetProcessingImageSnapshot, PresignedUploadDescriptor
from app.domains.closet.taxonomy import OCCASION_TAGS, SEASON_TAGS, STYLE_TAGS

LookbookSourceKindValue = Literal["gallery_photo", "wear_log"]
LookbookIntentValue = Literal["inspiration", "recreate", "logged"]
LookbookStatusValue = Literal["draft", "published"]
LookbookItemRoleValue = Literal[
    "top",
    "bottom",
    "dress",
    "outerwear",
    "shoes",
    "bag",
    "accessory",
    "other",
]

_OCCASION_TAGS = frozenset(OCCASION_TAGS)
_SEASON_TAGS = frozenset(SEASON_TAGS)
_STYLE_TAGS = frozenset(STYLE_TAGS)


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


def _normalize_optional_tag(
    value: str | None,
    *,
    allowed_values: frozenset[str],
    field_name: str,
) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise ValueError(f"{field_name} must be one of: {allowed}.")
    return normalized


class LookbookLinkedItemWriteRequest(BaseModel):
    closet_item_id: UUID
    role: LookbookItemRoleValue | None = None
    sort_index: int | None = Field(default=None, ge=0)


class _LookbookEntryWriteBase(BaseModel):
    title: str | None = None
    caption: str | None = None
    notes: str | None = None
    occasion_tag: str | None = None
    season_tag: str | None = None
    style_tag: str | None = None
    status: LookbookStatusValue = "draft"

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=255, field_name="Title")

    @field_validator("caption")
    @classmethod
    def normalize_caption(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=280, field_name="Caption")

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=1000, field_name="Notes")

    @field_validator("occasion_tag")
    @classmethod
    def normalize_occasion_tag(cls, value: str | None) -> str | None:
        return _normalize_optional_tag(
            value,
            allowed_values=_OCCASION_TAGS,
            field_name="occasion_tag",
        )

    @field_validator("season_tag")
    @classmethod
    def normalize_season_tag(cls, value: str | None) -> str | None:
        return _normalize_optional_tag(
            value,
            allowed_values=_SEASON_TAGS,
            field_name="season_tag",
        )

    @field_validator("style_tag")
    @classmethod
    def normalize_style_tag(cls, value: str | None) -> str | None:
        return _normalize_optional_tag(
            value,
            allowed_values=_STYLE_TAGS,
            field_name="style_tag",
        )


class GalleryLookbookEntryCreateRequest(_LookbookEntryWriteBase):
    source_kind: Literal["gallery_photo"]
    intent: Literal["inspiration", "recreate"]
    primary_image_asset_id: UUID
    linked_items: list[LookbookLinkedItemWriteRequest] = Field(default_factory=list, max_length=20)


class WearLogLookbookEntryCreateRequest(_LookbookEntryWriteBase):
    source_kind: Literal["wear_log"]
    source_wear_log_id: UUID
    intent: Literal["logged"] = "logged"


LookbookEntryCreateRequest: TypeAlias = Annotated[
    GalleryLookbookEntryCreateRequest | WearLogLookbookEntryCreateRequest,
    Field(discriminator="source_kind"),
]


class LookbookEntryUpdateRequest(BaseModel):
    title: str | None = None
    caption: str | None = None
    notes: str | None = None
    occasion_tag: str | None = None
    season_tag: str | None = None
    style_tag: str | None = None
    status: LookbookStatusValue | None = None
    primary_image_asset_id: UUID | None = None
    linked_items: list[LookbookLinkedItemWriteRequest] | None = Field(default=None, max_length=20)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=255, field_name="Title")

    @field_validator("caption")
    @classmethod
    def normalize_caption(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=280, field_name="Caption")

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=1000, field_name="Notes")

    @field_validator("occasion_tag")
    @classmethod
    def normalize_occasion_tag(cls, value: str | None) -> str | None:
        return _normalize_optional_tag(
            value,
            allowed_values=_OCCASION_TAGS,
            field_name="occasion_tag",
        )

    @field_validator("season_tag")
    @classmethod
    def normalize_season_tag(cls, value: str | None) -> str | None:
        return _normalize_optional_tag(
            value,
            allowed_values=_SEASON_TAGS,
            field_name="season_tag",
        )

    @field_validator("style_tag")
    @classmethod
    def normalize_style_tag(cls, value: str | None) -> str | None:
        return _normalize_optional_tag(
            value,
            allowed_values=_STYLE_TAGS,
            field_name="style_tag",
        )


class LookbookUploadIntentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=255)
    file_size: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)

    @field_validator("filename")
    @classmethod
    def normalize_filename(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Filename is required.")
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
        if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("sha256 must be a valid lowercase hexadecimal digest.")
        return normalized


class LookbookUploadIntentResponse(BaseModel):
    upload_intent_id: UUID
    expires_at: datetime
    upload: PresignedUploadDescriptor


class LookbookUploadCompleteRequest(BaseModel):
    upload_intent_id: UUID


class LookbookWearLogCreateRequest(BaseModel):
    wear_date: date | None = None
    worn_at: datetime | None = None
    timezone_name: str | None = None
    context: str | None = None
    notes: str | None = None

    @field_validator("timezone_name")
    @classmethod
    def normalize_timezone_name(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=128, field_name="timezone_name")

    @field_validator("context")
    @classmethod
    def normalize_context(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=64, field_name="Context")

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=1000, field_name="Notes")


class PrivateImageSnapshot(BaseModel):
    asset_id: UUID
    mime_type: str
    width: int | None
    height: int | None
    url: str
    expires_at: datetime


class LookbookSourceSnapshot(BaseModel):
    wear_log_id: UUID
    wear_date: date
    worn_at: datetime
    context: str | None
    vibe: str | None
    notes: str | None
    item_count: int
    primary_image_asset_id: UUID | None = None
    cover_image_asset_id: UUID | None = None


class LookbookOwnedOutfitSnapshot(BaseModel):
    id: UUID
    item_count: int
    is_archived: bool


class LookbookLinkedItemSnapshot(BaseModel):
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ClosetProcessingImageSnapshot | None
    thumbnail_image: ClosetProcessingImageSnapshot | None
    role: str | None
    sort_index: int


class LookbookEntrySummarySnapshot(BaseModel):
    id: UUID
    source_kind: LookbookSourceKindValue
    intent: LookbookIntentValue
    status: LookbookStatusValue
    title: str | None
    caption: str | None
    notes: str | None
    occasion_tag: str | None
    season_tag: str | None
    style_tag: str | None
    primary_image: PrivateImageSnapshot | None
    linked_item_count: int
    has_linked_items: bool
    source_wear_log_id: UUID | None
    owned_outfit: LookbookOwnedOutfitSnapshot | None
    source_snapshot: LookbookSourceSnapshot | None
    published_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LookbookEntryDetailSnapshot(LookbookEntrySummarySnapshot):
    linked_items: list[LookbookLinkedItemSnapshot]


class LookbookEntryListResponse(BaseModel):
    items: list[LookbookEntrySummarySnapshot]
    next_cursor: str | None
