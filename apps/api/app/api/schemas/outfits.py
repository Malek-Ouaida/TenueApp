from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.closet import ClosetProcessingImageSnapshot

OutfitOccasionValue = Literal["casual", "work", "event", "travel", "gym", "lounge"]
OutfitSeasonValue = Literal["summer", "winter"]
OutfitSourceValue = Literal["manual", "derived_from_wear_log", "ai_suggested"]
OutfitItemRoleValue = Literal[
    "top",
    "bottom",
    "dress",
    "outerwear",
    "shoes",
    "bag",
    "accessory",
    "other",
]


def _normalize_optional_title(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 255:
        raise ValueError("Title must be 255 characters or fewer.")
    return normalized


def _normalize_optional_notes(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 1000:
        raise ValueError("Notes must be 1000 characters or fewer.")
    return normalized


class OutfitItemWriteRequest(BaseModel):
    closet_item_id: UUID
    role: OutfitItemRoleValue | None = None
    layer_index: int | None = None
    sort_index: int | None = Field(default=None, ge=0)
    is_optional: bool = False


class _OutfitWriteBase(BaseModel):
    title: str | None = None
    notes: str | None = None
    occasion: OutfitOccasionValue | None = None
    season: OutfitSeasonValue | None = None
    is_favorite: bool = False

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return _normalize_optional_title(value)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_notes(value)


class OutfitCreateRequest(_OutfitWriteBase):
    items: list[OutfitItemWriteRequest] = Field(min_length=1, max_length=20)


class OutfitUpdateRequest(BaseModel):
    title: str | None = None
    notes: str | None = None
    occasion: OutfitOccasionValue | None = None
    season: OutfitSeasonValue | None = None
    is_favorite: bool | None = None
    items: list[OutfitItemWriteRequest] | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return _normalize_optional_title(value)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_notes(value)


class CreateOutfitFromWearLogRequest(_OutfitWriteBase):
    pass


class OutfitItemSnapshot(BaseModel):
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ClosetProcessingImageSnapshot | None
    thumbnail_image: ClosetProcessingImageSnapshot | None
    role: str | None
    layer_index: int | None
    sort_index: int
    is_optional: bool


class OutfitSummarySnapshot(BaseModel):
    id: UUID
    title: str | None
    occasion: str | None
    season: str | None
    source: str
    item_count: int
    is_favorite: bool
    is_archived: bool
    cover_image: ClosetProcessingImageSnapshot | None
    created_at: datetime
    updated_at: datetime


class OutfitDetailSnapshot(BaseModel):
    id: UUID
    title: str | None
    notes: str | None
    occasion: str | None
    season: str | None
    source: str
    item_count: int
    is_favorite: bool
    is_archived: bool
    cover_image: ClosetProcessingImageSnapshot | None
    items: list[OutfitItemSnapshot]
    created_at: datetime
    updated_at: datetime


class OutfitListResponse(BaseModel):
    items: list[OutfitSummarySnapshot]
    next_cursor: str | None
