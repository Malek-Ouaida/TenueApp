from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.api.schemas.closet import ClosetProcessingImageSnapshot

InsightItemSortValue = Literal["most_worn", "least_worn"]


class InsightOverviewAllTimeSnapshot(BaseModel):
    total_wear_logs: int
    total_worn_item_events: int
    unique_items_worn: int
    active_confirmed_closet_item_count: int
    never_worn_item_count: int


class InsightOverviewCurrentMonthSnapshot(BaseModel):
    total_wear_logs: int
    total_worn_item_events: int
    unique_items_worn: int
    active_closet_items_worn: int
    active_closet_coverage_ratio: float


class InsightOverviewStreaksSnapshot(BaseModel):
    current_streak_days: int
    longest_streak_days: int


class InsightOverviewResponse(BaseModel):
    as_of_date: date
    all_time: InsightOverviewAllTimeSnapshot
    current_month: InsightOverviewCurrentMonthSnapshot
    streaks: InsightOverviewStreaksSnapshot


class InsightItemUsageSnapshot(BaseModel):
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ClosetProcessingImageSnapshot | None
    thumbnail_image: ClosetProcessingImageSnapshot | None
    wear_count: int
    first_worn_date: date
    last_worn_date: date


class InsightItemUsageResponse(BaseModel):
    items: list[InsightItemUsageSnapshot]
    next_cursor: str | None


class InsightStaleItemSnapshot(BaseModel):
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ClosetProcessingImageSnapshot | None
    thumbnail_image: ClosetProcessingImageSnapshot | None
    wear_count: int
    first_worn_date: date
    last_worn_date: date
    days_since_last_worn: int


class InsightStaleItemResponse(BaseModel):
    items: list[InsightStaleItemSnapshot]
    next_cursor: str | None


class InsightNeverWornItemSnapshot(BaseModel):
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ClosetProcessingImageSnapshot | None
    thumbnail_image: ClosetProcessingImageSnapshot | None
    confirmed_at: datetime


class InsightNeverWornItemResponse(BaseModel):
    items: list[InsightNeverWornItemSnapshot]
    next_cursor: str | None


class InsightOutfitUsageSnapshot(BaseModel):
    id: UUID
    title: str | None
    occasion: str | None
    season: str | None
    source: str
    item_count: int
    is_favorite: bool
    is_archived: bool
    cover_image: ClosetProcessingImageSnapshot | None
    wear_count: int
    first_worn_date: date
    last_worn_date: date


class InsightOutfitUsageResponse(BaseModel):
    items: list[InsightOutfitUsageSnapshot]
    next_cursor: str | None


class InsightCategoryUsageSnapshot(BaseModel):
    category: str
    wear_count: int
    unique_item_count: int
    last_worn_date: date


class InsightCategoryUsageResponse(BaseModel):
    start_date: date
    end_date: date
    items: list[InsightCategoryUsageSnapshot]


class InsightTimelinePointSnapshot(BaseModel):
    date: date
    wear_log_count: int
    worn_item_count: int
    unique_item_count: int


class InsightTimelineResponse(BaseModel):
    start_date: date
    end_date: date
    points: list[InsightTimelinePointSnapshot]
