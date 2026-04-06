from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.closet import ClosetProcessingImageSnapshot

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


class WearLogItemWriteRequest(BaseModel):
    closet_item_id: UUID
    role: WearItemRoleValue | None = None
    sort_index: int | None = Field(default=None, ge=0)


class WearLogCreateRequest(BaseModel):
    wear_date: date
    mode: Literal["manual_items"]
    context: WearContextValue | None = None
    notes: str | None = None
    items: list[WearLogItemWriteRequest] = Field(min_length=1, max_length=20)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 1000:
            raise ValueError("Notes must be 1000 characters or fewer.")
        return normalized


class WearLogUpdateRequest(BaseModel):
    wear_date: date | None = None
    context: WearContextValue | None = None
    notes: str | None = None
    items: list[WearLogItemWriteRequest] | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 1000:
            raise ValueError("Notes must be 1000 characters or fewer.")
        return normalized


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


class WearLogDetailSnapshot(BaseModel):
    id: UUID
    wear_date: date
    source: str
    context: str | None
    notes: str | None
    is_confirmed: bool
    item_count: int
    cover_image: ClosetProcessingImageSnapshot | None
    items: list[WearLoggedItemSnapshot]
    created_at: datetime
    updated_at: datetime


class WearLogTimelineItemSnapshot(BaseModel):
    id: UUID
    wear_date: date
    context: str | None
    item_count: int
    source: str
    is_confirmed: bool
    cover_image: ClosetProcessingImageSnapshot | None
    created_at: datetime
    updated_at: datetime


class WearLogTimelineResponse(BaseModel):
    items: list[WearLogTimelineItemSnapshot]
    next_cursor: str | None


class WearCalendarDaySnapshot(BaseModel):
    date: date
    has_wear_log: bool
    wear_log_id: UUID | None
    item_count: int
    source: str | None
    is_confirmed: bool | None
    cover_image: ClosetProcessingImageSnapshot | None


class WearCalendarResponse(BaseModel):
    days: list[WearCalendarDaySnapshot]
