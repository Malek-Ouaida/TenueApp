from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.closet import PresignedUploadDescriptor

LookbookEntryTypeValue = Literal["outfit", "image", "note"]


def _normalize_required_title(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Title is required.")
    if len(normalized) > 255:
        raise ValueError("Title must be 255 characters or fewer.")
    return normalized


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


def _normalize_required_text(
    value: str,
    *,
    max_length: int,
    field_name: str,
) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
    return normalized


class LookbookCreateRequest(BaseModel):
    title: str
    description: str | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return _normalize_required_title(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=1000, field_name="Description")


class LookbookUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_required_title(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=1000, field_name="Description")


class LookbookUploadIntentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=255)
    file_size: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("sha256 must be a valid lowercase hexadecimal digest.")
        return normalized


class OutfitLookbookEntryCreateRequest(BaseModel):
    entry_type: Literal["outfit"]
    outfit_id: UUID
    caption: str | None = None

    @field_validator("caption")
    @classmethod
    def normalize_caption(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=280, field_name="Caption")


class ImageLookbookEntryCreateRequest(BaseModel):
    entry_type: Literal["image"]
    upload_intent_id: UUID
    caption: str | None = None

    @field_validator("caption")
    @classmethod
    def normalize_caption(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_length=280, field_name="Caption")


class NoteLookbookEntryCreateRequest(BaseModel):
    entry_type: Literal["note"]
    note_text: str

    @field_validator("note_text")
    @classmethod
    def normalize_note_text(cls, value: str) -> str:
        return _normalize_required_text(value, max_length=1000, field_name="Note text")


LookbookEntryCreateRequest: TypeAlias = Annotated[
    OutfitLookbookEntryCreateRequest
    | ImageLookbookEntryCreateRequest
    | NoteLookbookEntryCreateRequest,
    Field(discriminator="entry_type"),
]


class LookbookEntriesReorderRequest(BaseModel):
    entry_ids: list[UUID] = Field(min_length=1)


class PrivateImageSnapshot(BaseModel):
    asset_id: UUID
    mime_type: str
    width: int | None
    height: int | None
    url: str
    expires_at: datetime


class LookbookOutfitReferenceSnapshot(BaseModel):
    id: UUID
    title: str | None
    is_favorite: bool
    is_archived: bool
    item_count: int
    cover_image: PrivateImageSnapshot | None


class LookbookEntrySnapshot(BaseModel):
    id: UUID
    entry_type: LookbookEntryTypeValue
    caption: str | None
    note_text: str | None
    sort_index: int
    image: PrivateImageSnapshot | None
    outfit: LookbookOutfitReferenceSnapshot | None
    created_at: datetime
    updated_at: datetime


class LookbookFlattenedEntrySnapshot(BaseModel):
    lookbook_id: UUID
    lookbook_title: str
    lookbook_description: str | None
    lookbook_cover_image: PrivateImageSnapshot | None
    entry: LookbookEntrySnapshot


class LookbookSummarySnapshot(BaseModel):
    id: UUID
    title: str
    description: str | None
    entry_count: int
    cover_image: PrivateImageSnapshot | None
    created_at: datetime
    updated_at: datetime


class LookbookDetailSnapshot(BaseModel):
    id: UUID
    title: str
    description: str | None
    entry_count: int
    cover_image: PrivateImageSnapshot | None
    created_at: datetime
    updated_at: datetime


class LookbookListResponse(BaseModel):
    items: list[LookbookSummarySnapshot]
    next_cursor: str | None


class LookbookEntryListResponse(BaseModel):
    items: list[LookbookEntrySnapshot]
    next_cursor: str | None


class LookbookFlattenedEntryListResponse(BaseModel):
    items: list[LookbookFlattenedEntrySnapshot]
    next_cursor: str | None


class LookbookUploadIntentResponse(BaseModel):
    upload_intent_id: UUID
    expires_at: datetime
    upload: PresignedUploadDescriptor
