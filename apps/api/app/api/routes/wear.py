from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.wear import get_wear_service
from app.api.schemas.closet import ClosetProcessingImageSnapshot
from app.api.schemas.wear import (
    WearCalendarDaySnapshot,
    WearCalendarResponse,
    WearLogCreateRequest,
    WearLogDetailSnapshot,
    WearLoggedItemSnapshot,
    WearLogTimelineItemSnapshot,
    WearLogTimelineResponse,
    WearLogUpdateRequest,
)
from app.domains.closet.image_processing_service import ProcessingSnapshotImage
from app.domains.wear.service import (
    InvalidWearHistoryCursorError,
    WearService,
    WearServiceError,
)
from app.domains.wear.service import (
    WearCalendarDaySnapshot as WearCalendarDayView,
)
from app.domains.wear.service import (
    WearLogDetailSnapshot as WearLogDetailView,
)
from app.domains.wear.service import (
    WearLoggedItemSnapshot as WearLoggedItemView,
)
from app.domains.wear.service import (
    WearLogTimelineItemSnapshot as WearLogTimelineItemView,
)

router = APIRouter(prefix="/wear-logs", tags=["wear-logs"])


@router.post("", response_model=WearLogDetailSnapshot, status_code=201)
def create_wear_log(
    payload: WearLogCreateRequest,
    current_user: CurrentUser,
    wear_service: Annotated[WearService, Depends(get_wear_service)],
) -> WearLogDetailSnapshot:
    try:
        snapshot = wear_service.create_wear_log(
            user_id=current_user.id,
            wear_date=payload.wear_date,
            context=payload.context,
            notes=payload.notes,
            items=[
                {
                    "closet_item_id": item.closet_item_id,
                    "role": item.role,
                    "sort_index": item.sort_index,
                }
                for item in payload.items
            ],
        )
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_wear_log_detail_snapshot(snapshot)


@router.get("", response_model=WearLogTimelineResponse)
def read_wear_logs(
    current_user: CurrentUser,
    wear_service: Annotated[WearService, Depends(get_wear_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> WearLogTimelineResponse:
    try:
        items, next_cursor = wear_service.list_wear_logs(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
        )
    except InvalidWearHistoryCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return WearLogTimelineResponse(
        items=[build_wear_log_timeline_item_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/calendar", response_model=WearCalendarResponse)
def read_wear_calendar(
    current_user: CurrentUser,
    wear_service: Annotated[WearService, Depends(get_wear_service)],
    start_date: Annotated[str, Query()],
    end_date: Annotated[str, Query()],
) -> WearCalendarResponse:
    try:
        days = wear_service.get_calendar(
            user_id=current_user.id,
            start_date=_parse_date(start_date, field_name="start_date"),
            end_date=_parse_date(end_date, field_name="end_date"),
        )
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return WearCalendarResponse(days=[build_wear_calendar_day_snapshot(day) for day in days])


@router.get("/{wear_log_id}", response_model=WearLogDetailSnapshot)
def read_wear_log_detail(
    wear_log_id: UUID,
    current_user: CurrentUser,
    wear_service: Annotated[WearService, Depends(get_wear_service)],
) -> WearLogDetailSnapshot:
    try:
        snapshot = wear_service.get_wear_log_detail(
            wear_log_id=wear_log_id,
            user_id=current_user.id,
        )
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_wear_log_detail_snapshot(snapshot)


@router.patch("/{wear_log_id}", response_model=WearLogDetailSnapshot)
def update_wear_log(
    wear_log_id: UUID,
    payload: WearLogUpdateRequest,
    current_user: CurrentUser,
    wear_service: Annotated[WearService, Depends(get_wear_service)],
) -> WearLogDetailSnapshot:
    try:
        snapshot = wear_service.update_wear_log(
            wear_log_id=wear_log_id,
            user_id=current_user.id,
            wear_date=payload.wear_date,
            context=payload.context,
            notes=payload.notes,
            items=(
                [
                    {
                        "closet_item_id": item.closet_item_id,
                        "role": item.role,
                        "sort_index": item.sort_index,
                    }
                    for item in payload.items
                ]
                if payload.items is not None
                else None
            ),
            field_names=payload.model_fields_set,
        )
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_wear_log_detail_snapshot(snapshot)


@router.delete("/{wear_log_id}", status_code=204)
def delete_wear_log(
    wear_log_id: UUID,
    current_user: CurrentUser,
    wear_service: Annotated[WearService, Depends(get_wear_service)],
) -> Response:
    try:
        wear_service.delete_wear_log(
            wear_log_id=wear_log_id,
            user_id=current_user.id,
        )
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return Response(status_code=204)


def build_wear_log_detail_snapshot(snapshot: WearLogDetailView) -> WearLogDetailSnapshot:
    return WearLogDetailSnapshot(
        id=snapshot.id,
        wear_date=snapshot.wear_date,
        source=snapshot.source,
        context=snapshot.context,
        notes=snapshot.notes,
        is_confirmed=snapshot.is_confirmed,
        item_count=snapshot.item_count,
        cover_image=build_image_snapshot(snapshot.cover_image),
        items=[build_logged_item_snapshot(item) for item in snapshot.items],
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def build_logged_item_snapshot(snapshot: WearLoggedItemView) -> WearLoggedItemSnapshot:
    return WearLoggedItemSnapshot(
        closet_item_id=snapshot.closet_item_id,
        title=snapshot.title,
        category=snapshot.category,
        subcategory=snapshot.subcategory,
        primary_color=snapshot.primary_color,
        display_image=build_image_snapshot(snapshot.display_image),
        thumbnail_image=build_image_snapshot(snapshot.thumbnail_image),
        role=snapshot.role,
        sort_index=snapshot.sort_index,
    )


def build_wear_log_timeline_item_snapshot(
    snapshot: WearLogTimelineItemView,
) -> WearLogTimelineItemSnapshot:
    return WearLogTimelineItemSnapshot(
        id=snapshot.id,
        wear_date=snapshot.wear_date,
        context=snapshot.context,
        item_count=snapshot.item_count,
        source=snapshot.source,
        is_confirmed=snapshot.is_confirmed,
        cover_image=build_image_snapshot(snapshot.cover_image),
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def build_wear_calendar_day_snapshot(
    snapshot: WearCalendarDayView,
) -> WearCalendarDaySnapshot:
    return WearCalendarDaySnapshot(
        date=snapshot.date,
        has_wear_log=snapshot.has_wear_log,
        wear_log_id=snapshot.wear_log_id,
        item_count=snapshot.item_count,
        source=snapshot.source,
        is_confirmed=snapshot.is_confirmed,
        cover_image=build_image_snapshot(snapshot.cover_image),
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


def _parse_date(value: str, *, field_name: str):
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO date.") from exc
