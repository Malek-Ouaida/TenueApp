from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.wear import get_outfit_service
from app.api.schemas import outfits as outfit_schemas
from app.api.schemas.closet import ClosetProcessingImageSnapshot
from app.domains.closet.image_processing_service import ProcessingSnapshotImage
from app.domains.wear import outfit_service as outfit_domain

router = APIRouter(prefix="/outfits", tags=["outfits"])


@router.post("", response_model=outfit_schemas.OutfitDetailSnapshot, status_code=201)
def create_outfit(
    payload: outfit_schemas.OutfitCreateRequest,
    current_user: CurrentUser,
    outfit_service: Annotated[outfit_domain.OutfitService, Depends(get_outfit_service)],
) -> outfit_schemas.OutfitDetailSnapshot:
    try:
        snapshot = outfit_service.create_outfit(
            user_id=current_user.id,
            title=payload.title,
            notes=payload.notes,
            occasion=payload.occasion,
            season=payload.season,
            is_favorite=payload.is_favorite,
            items=[
                {
                    "closet_item_id": item.closet_item_id,
                    "role": item.role,
                    "layer_index": item.layer_index,
                    "sort_index": item.sort_index,
                    "is_optional": item.is_optional,
                }
                for item in payload.items
            ],
        )
    except outfit_domain.OutfitServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_outfit_detail_snapshot(snapshot)


@router.get("", response_model=outfit_schemas.OutfitListResponse)
def read_outfits(
    current_user: CurrentUser,
    outfit_service: Annotated[outfit_domain.OutfitService, Depends(get_outfit_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    occasion: outfit_schemas.OutfitOccasionValue | None = None,
    season: outfit_schemas.OutfitSeasonValue | None = None,
    is_favorite: bool | None = None,
    source: outfit_schemas.OutfitSourceValue | None = None,
    include_archived: bool = False,
) -> outfit_schemas.OutfitListResponse:
    try:
        items, next_cursor = outfit_service.list_outfits(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
            occasion=occasion,
            season=season,
            is_favorite=is_favorite,
            source=source,
            include_archived=include_archived,
        )
    except outfit_domain.InvalidOutfitCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except outfit_domain.OutfitServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return outfit_schemas.OutfitListResponse(
        items=[build_outfit_summary_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.post(
    "/from-wear-log/{wear_log_id}",
    response_model=outfit_schemas.OutfitDetailSnapshot,
    status_code=201,
)
def create_outfit_from_wear_log(
    wear_log_id: UUID,
    payload: outfit_schemas.CreateOutfitFromWearLogRequest,
    current_user: CurrentUser,
    outfit_service: Annotated[outfit_domain.OutfitService, Depends(get_outfit_service)],
) -> outfit_schemas.OutfitDetailSnapshot:
    try:
        snapshot = outfit_service.create_outfit_from_wear_log(
            wear_log_id=wear_log_id,
            user_id=current_user.id,
            title=payload.title,
            notes=payload.notes,
            occasion=payload.occasion,
            season=payload.season,
            is_favorite=payload.is_favorite,
        )
    except outfit_domain.OutfitServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_outfit_detail_snapshot(snapshot)


@router.get("/{outfit_id}", response_model=outfit_schemas.OutfitDetailSnapshot)
def read_outfit_detail(
    outfit_id: UUID,
    current_user: CurrentUser,
    outfit_service: Annotated[outfit_domain.OutfitService, Depends(get_outfit_service)],
) -> outfit_schemas.OutfitDetailSnapshot:
    try:
        snapshot = outfit_service.get_outfit_detail(outfit_id=outfit_id, user_id=current_user.id)
    except outfit_domain.OutfitServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_outfit_detail_snapshot(snapshot)


@router.patch("/{outfit_id}", response_model=outfit_schemas.OutfitDetailSnapshot)
def update_outfit(
    outfit_id: UUID,
    payload: outfit_schemas.OutfitUpdateRequest,
    current_user: CurrentUser,
    outfit_service: Annotated[outfit_domain.OutfitService, Depends(get_outfit_service)],
) -> outfit_schemas.OutfitDetailSnapshot:
    try:
        snapshot = outfit_service.update_outfit(
            outfit_id=outfit_id,
            user_id=current_user.id,
            title=payload.title,
            notes=payload.notes,
            occasion=payload.occasion,
            season=payload.season,
            is_favorite=payload.is_favorite,
            items=(
                [
                    {
                        "closet_item_id": item.closet_item_id,
                        "role": item.role,
                        "layer_index": item.layer_index,
                        "sort_index": item.sort_index,
                        "is_optional": item.is_optional,
                    }
                    for item in payload.items
                ]
                if payload.items is not None
                else None
            ),
            field_names=payload.model_fields_set,
        )
    except outfit_domain.OutfitServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_outfit_detail_snapshot(snapshot)


@router.post("/{outfit_id}/archive", status_code=204)
def archive_outfit(
    outfit_id: UUID,
    current_user: CurrentUser,
    outfit_service: Annotated[outfit_domain.OutfitService, Depends(get_outfit_service)],
) -> Response:
    try:
        outfit_service.archive_outfit(outfit_id=outfit_id, user_id=current_user.id)
    except outfit_domain.OutfitServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return Response(status_code=204)


def build_outfit_summary_snapshot(
    snapshot: outfit_domain.OutfitSummarySnapshot,
) -> outfit_schemas.OutfitSummarySnapshot:
    return outfit_schemas.OutfitSummarySnapshot(
        id=snapshot.id,
        title=snapshot.title,
        occasion=snapshot.occasion,
        season=snapshot.season,
        source=snapshot.source,
        item_count=snapshot.item_count,
        is_favorite=snapshot.is_favorite,
        is_archived=snapshot.is_archived,
        cover_image=build_image_snapshot(snapshot.cover_image),
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def build_outfit_detail_snapshot(
    snapshot: outfit_domain.OutfitDetailSnapshot,
) -> outfit_schemas.OutfitDetailSnapshot:
    return outfit_schemas.OutfitDetailSnapshot(
        id=snapshot.id,
        title=snapshot.title,
        notes=snapshot.notes,
        occasion=snapshot.occasion,
        season=snapshot.season,
        source=snapshot.source,
        item_count=snapshot.item_count,
        is_favorite=snapshot.is_favorite,
        is_archived=snapshot.is_archived,
        cover_image=build_image_snapshot(snapshot.cover_image),
        items=[build_outfit_item_snapshot(item) for item in snapshot.items],
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def build_outfit_item_snapshot(
    snapshot: outfit_domain.OutfitItemSnapshot,
) -> outfit_schemas.OutfitItemSnapshot:
    return outfit_schemas.OutfitItemSnapshot(
        closet_item_id=snapshot.closet_item_id,
        title=snapshot.title,
        category=snapshot.category,
        subcategory=snapshot.subcategory,
        primary_color=snapshot.primary_color,
        display_image=build_image_snapshot(snapshot.display_image),
        thumbnail_image=build_image_snapshot(snapshot.thumbnail_image),
        role=snapshot.role,
        layer_index=snapshot.layer_index,
        sort_index=snapshot.sort_index,
        is_optional=snapshot.is_optional,
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
