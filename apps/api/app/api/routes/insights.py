from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.wear import get_insight_service
from app.api.schemas.closet import ClosetProcessingImageSnapshot
from app.api.schemas.insights import (
    InsightCategoryUsageResponse,
    InsightCategoryUsageSnapshot,
    InsightItemSortValue,
    InsightItemUsageResponse,
    InsightItemUsageSnapshot,
    InsightNeverWornItemResponse,
    InsightNeverWornItemSnapshot,
    InsightOutfitUsageResponse,
    InsightOutfitUsageSnapshot,
    InsightOverviewAllTimeSnapshot,
    InsightOverviewCurrentMonthSnapshot,
    InsightOverviewResponse,
    InsightOverviewStreaksSnapshot,
    InsightStaleItemResponse,
    InsightStaleItemSnapshot,
    InsightTimelinePointSnapshot,
    InsightTimelineResponse,
)
from app.domains.closet.image_processing_service import ProcessingSnapshotImage
from app.domains.wear.insight_service import (
    InsightCategoryUsageSnapshot as InsightCategoryUsageView,
)
from app.domains.wear.insight_service import (
    InsightItemUsageSnapshot as InsightItemUsageView,
)
from app.domains.wear.insight_service import (
    InsightNeverWornItemSnapshot as InsightNeverWornItemView,
)
from app.domains.wear.insight_service import (
    InsightOutfitUsageSnapshot as InsightOutfitUsageView,
)
from app.domains.wear.insight_service import (
    InsightOverviewSnapshot as InsightOverviewView,
)
from app.domains.wear.insight_service import (
    InsightService,
    InsightServiceError,
    InvalidInsightCursorError,
)
from app.domains.wear.insight_service import (
    InsightStaleItemSnapshot as InsightStaleItemView,
)
from app.domains.wear.insight_service import (
    InsightTimelinePointSnapshot as InsightTimelinePointView,
)

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/overview", response_model=InsightOverviewResponse)
def read_insight_overview(
    current_user: CurrentUser,
    insight_service: Annotated[InsightService, Depends(get_insight_service)],
    as_of_date: date | None = None,
) -> InsightOverviewResponse:
    try:
        snapshot = insight_service.get_overview(
            user_id=current_user.id,
            as_of_date=as_of_date,
        )
    except InsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_overview_response(snapshot)


@router.get("/items", response_model=InsightItemUsageResponse)
def read_item_usage(
    current_user: CurrentUser,
    insight_service: Annotated[InsightService, Depends(get_insight_service)],
    sort: InsightItemSortValue = "most_worn",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> InsightItemUsageResponse:
    try:
        items, next_cursor = insight_service.list_item_usage(
            user_id=current_user.id,
            sort=sort,
            cursor=cursor,
            limit=limit,
        )
    except InvalidInsightCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return InsightItemUsageResponse(
        items=[build_item_usage_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/outfits", response_model=InsightOutfitUsageResponse)
def read_outfit_usage(
    current_user: CurrentUser,
    insight_service: Annotated[InsightService, Depends(get_insight_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> InsightOutfitUsageResponse:
    try:
        items, next_cursor = insight_service.list_outfit_usage(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
        )
    except InvalidInsightCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return InsightOutfitUsageResponse(
        items=[build_outfit_usage_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/categories", response_model=InsightCategoryUsageResponse)
def read_category_usage(
    current_user: CurrentUser,
    insight_service: Annotated[InsightService, Depends(get_insight_service)],
    start_date: date,
    end_date: date,
) -> InsightCategoryUsageResponse:
    try:
        items = insight_service.get_category_usage(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
        )
    except InsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return InsightCategoryUsageResponse(
        start_date=start_date,
        end_date=end_date,
        items=[build_category_usage_snapshot(item) for item in items],
    )


@router.get("/timeline", response_model=InsightTimelineResponse)
def read_insight_timeline(
    current_user: CurrentUser,
    insight_service: Annotated[InsightService, Depends(get_insight_service)],
    start_date: date,
    end_date: date,
) -> InsightTimelineResponse:
    try:
        points = insight_service.get_timeline(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
        )
    except InsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return InsightTimelineResponse(
        start_date=start_date,
        end_date=end_date,
        points=[build_timeline_point_snapshot(point) for point in points],
    )


@router.get("/stale-items", response_model=InsightStaleItemResponse)
def read_stale_items(
    current_user: CurrentUser,
    insight_service: Annotated[InsightService, Depends(get_insight_service)],
    as_of_date: date | None = None,
    stale_after_days: Annotated[int, Query(ge=1)] = 30,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> InsightStaleItemResponse:
    try:
        items, next_cursor = insight_service.list_stale_items(
            user_id=current_user.id,
            as_of_date=as_of_date,
            stale_after_days=stale_after_days,
            cursor=cursor,
            limit=limit,
        )
    except InvalidInsightCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return InsightStaleItemResponse(
        items=[build_stale_item_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/never-worn", response_model=InsightNeverWornItemResponse)
def read_never_worn_items(
    current_user: CurrentUser,
    insight_service: Annotated[InsightService, Depends(get_insight_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> InsightNeverWornItemResponse:
    try:
        items, next_cursor = insight_service.list_never_worn_items(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
        )
    except InvalidInsightCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return InsightNeverWornItemResponse(
        items=[build_never_worn_item_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


def build_overview_response(snapshot: InsightOverviewView) -> InsightOverviewResponse:
    return InsightOverviewResponse(
        as_of_date=snapshot.as_of_date,
        all_time=InsightOverviewAllTimeSnapshot(
            total_wear_logs=snapshot.all_time.total_wear_logs,
            total_worn_item_events=snapshot.all_time.total_worn_item_events,
            unique_items_worn=snapshot.all_time.unique_items_worn,
            active_confirmed_closet_item_count=snapshot.all_time.active_confirmed_closet_item_count,
            never_worn_item_count=snapshot.all_time.never_worn_item_count,
        ),
        current_month=InsightOverviewCurrentMonthSnapshot(
            total_wear_logs=snapshot.current_month.total_wear_logs,
            total_worn_item_events=snapshot.current_month.total_worn_item_events,
            unique_items_worn=snapshot.current_month.unique_items_worn,
            active_closet_items_worn=snapshot.current_month.active_closet_items_worn,
            active_closet_coverage_ratio=snapshot.current_month.active_closet_coverage_ratio,
        ),
        streaks=InsightOverviewStreaksSnapshot(
            current_streak_days=snapshot.streaks.current_streak_days,
            longest_streak_days=snapshot.streaks.longest_streak_days,
        ),
    )


def build_item_usage_snapshot(snapshot: InsightItemUsageView) -> InsightItemUsageSnapshot:
    return InsightItemUsageSnapshot(
        closet_item_id=snapshot.closet_item_id,
        title=snapshot.title,
        category=snapshot.category,
        subcategory=snapshot.subcategory,
        primary_color=snapshot.primary_color,
        display_image=build_image_snapshot(snapshot.display_image),
        thumbnail_image=build_image_snapshot(snapshot.thumbnail_image),
        wear_count=snapshot.wear_count,
        first_worn_date=snapshot.first_worn_date,
        last_worn_date=snapshot.last_worn_date,
    )


def build_outfit_usage_snapshot(snapshot: InsightOutfitUsageView) -> InsightOutfitUsageSnapshot:
    return InsightOutfitUsageSnapshot(
        id=snapshot.id,
        title=snapshot.title,
        occasion=snapshot.occasion,
        season=snapshot.season,
        source=snapshot.source,
        item_count=snapshot.item_count,
        is_favorite=snapshot.is_favorite,
        is_archived=snapshot.is_archived,
        cover_image=build_image_snapshot(snapshot.cover_image),
        wear_count=snapshot.wear_count,
        first_worn_date=snapshot.first_worn_date,
        last_worn_date=snapshot.last_worn_date,
    )


def build_category_usage_snapshot(
    snapshot: InsightCategoryUsageView,
) -> InsightCategoryUsageSnapshot:
    return InsightCategoryUsageSnapshot(
        category=snapshot.category,
        wear_count=snapshot.wear_count,
        unique_item_count=snapshot.unique_item_count,
        last_worn_date=snapshot.last_worn_date,
    )


def build_timeline_point_snapshot(
    snapshot: InsightTimelinePointView,
) -> InsightTimelinePointSnapshot:
    return InsightTimelinePointSnapshot(
        date=snapshot.date,
        wear_log_count=snapshot.wear_log_count,
        worn_item_count=snapshot.worn_item_count,
        unique_item_count=snapshot.unique_item_count,
    )


def build_stale_item_snapshot(snapshot: InsightStaleItemView) -> InsightStaleItemSnapshot:
    return InsightStaleItemSnapshot(
        closet_item_id=snapshot.closet_item_id,
        title=snapshot.title,
        category=snapshot.category,
        subcategory=snapshot.subcategory,
        primary_color=snapshot.primary_color,
        display_image=build_image_snapshot(snapshot.display_image),
        thumbnail_image=build_image_snapshot(snapshot.thumbnail_image),
        wear_count=snapshot.wear_count,
        first_worn_date=snapshot.first_worn_date,
        last_worn_date=snapshot.last_worn_date,
        days_since_last_worn=snapshot.days_since_last_worn,
    )


def build_never_worn_item_snapshot(
    snapshot: InsightNeverWornItemView,
) -> InsightNeverWornItemSnapshot:
    return InsightNeverWornItemSnapshot(
        closet_item_id=snapshot.closet_item_id,
        title=snapshot.title,
        category=snapshot.category,
        subcategory=snapshot.subcategory,
        primary_color=snapshot.primary_color,
        display_image=build_image_snapshot(snapshot.display_image),
        thumbnail_image=build_image_snapshot(snapshot.thumbnail_image),
        confirmed_at=snapshot.confirmed_at,
    )


def build_image_snapshot(
    snapshot: ProcessingSnapshotImage | None,
) -> ClosetProcessingImageSnapshot | None:
    if snapshot is None:
        return None
    return ClosetProcessingImageSnapshot(
        asset_id=snapshot.asset_id,
        image_id=snapshot.image_id,
        role=snapshot.role,
        position=snapshot.position,
        is_primary=snapshot.is_primary,
        mime_type=snapshot.mime_type,
        width=snapshot.width,
        height=snapshot.height,
        url=snapshot.url,
        expires_at=snapshot.expires_at,
    )
