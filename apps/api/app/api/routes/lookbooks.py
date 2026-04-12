from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.lookbook import get_lookbook_service, get_lookbook_upload_service
from app.api.schemas.closet import PresignedUploadDescriptor
from app.api.schemas.lookbooks import (
    GalleryLookbookEntryCreateRequest,
    LookbookEntryCreateRequest,
    LookbookEntryDetailSnapshot,
    LookbookEntryListResponse,
    LookbookEntrySummarySnapshot,
    LookbookEntryUpdateRequest,
    LookbookIntentValue,
    LookbookSourceKindValue,
    LookbookStatusValue,
    LookbookUploadCompleteRequest,
    LookbookUploadIntentRequest,
    LookbookUploadIntentResponse,
    LookbookWearLogCreateRequest,
    PrivateImageSnapshot,
    WearLogLookbookEntryCreateRequest,
)
from app.api.schemas.wear import WearLogDetailSnapshot
from app.domains.lookbook.errors import LookbookError
from app.domains.lookbook.service import (
    InvalidLookbookEntryCursorError,
    LookbookService,
)
from app.domains.lookbook.upload_service import LookbookUploadService
from app.domains.wear.service import WearServiceError

router = APIRouter(prefix="/lookbook", tags=["lookbook"])


@router.get("/entries", response_model=LookbookEntryListResponse)
def read_lookbook_entries(
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    status: LookbookStatusValue | None = None,
    source_kind: LookbookSourceKindValue | None = None,
    intent: LookbookIntentValue | None = None,
    occasion_tag: str | None = None,
    season_tag: str | None = None,
    style_tag: str | None = None,
    has_linked_items: bool | None = None,
    include_archived: bool = False,
) -> LookbookEntryListResponse:
    try:
        items, next_cursor = lookbook_service.list_entries(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
            status=status,
            source_kind=source_kind,
            intent=intent,
            occasion_tag=occasion_tag,
            season_tag=season_tag,
            style_tag=style_tag,
            has_linked_items=has_linked_items,
            include_archived=include_archived,
        )
    except InvalidLookbookEntryCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return LookbookEntryListResponse(
        items=[_build_entry_summary_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.post("/entries", response_model=LookbookEntryDetailSnapshot, status_code=201)
def create_lookbook_entry(
    payload: LookbookEntryCreateRequest,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> LookbookEntryDetailSnapshot:
    try:
        if isinstance(payload, GalleryLookbookEntryCreateRequest):
            snapshot = lookbook_service.create_gallery_entry(
                user_id=current_user.id,
                intent=payload.intent,
                status=payload.status,
                title=payload.title,
                caption=payload.caption,
                notes=payload.notes,
                occasion_tag=payload.occasion_tag,
                season_tag=payload.season_tag,
                style_tag=payload.style_tag,
                primary_image_asset_id=payload.primary_image_asset_id,
                linked_items=_build_linked_item_payload(payload.linked_items),
            )
        elif isinstance(payload, WearLogLookbookEntryCreateRequest):
            snapshot = lookbook_service.create_wear_log_entry(
                user_id=current_user.id,
                source_wear_log_id=payload.source_wear_log_id,
                status=payload.status,
                title=payload.title,
                caption=payload.caption,
                notes=payload.notes,
                occasion_tag=payload.occasion_tag,
                season_tag=payload.season_tag,
                style_tag=payload.style_tag,
            )
        else:
            raise HTTPException(status_code=422, detail="Unsupported lookbook entry source.")
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return _build_entry_detail_snapshot(snapshot)


@router.get("/entries/{entry_id}", response_model=LookbookEntryDetailSnapshot)
def read_lookbook_entry(
    entry_id: UUID,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> LookbookEntryDetailSnapshot:
    try:
        snapshot = lookbook_service.get_entry_detail(
            entry_id=entry_id,
            user_id=current_user.id,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return _build_entry_detail_snapshot(snapshot)


@router.patch("/entries/{entry_id}", response_model=LookbookEntryDetailSnapshot)
def update_lookbook_entry(
    entry_id: UUID,
    payload: LookbookEntryUpdateRequest,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> LookbookEntryDetailSnapshot:
    try:
        snapshot = lookbook_service.update_entry(
            entry_id=entry_id,
            user_id=current_user.id,
            title=payload.title,
            caption=payload.caption,
            notes=payload.notes,
            occasion_tag=payload.occasion_tag,
            season_tag=payload.season_tag,
            style_tag=payload.style_tag,
            status=payload.status,
            primary_image_asset_id=payload.primary_image_asset_id,
            linked_items=(
                _build_linked_item_payload(payload.linked_items)
                if payload.linked_items is not None
                else None
            ),
            field_names=payload.model_fields_set,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return _build_entry_detail_snapshot(snapshot)


@router.post("/entries/{entry_id}/archive", status_code=204)
def archive_lookbook_entry(
    entry_id: UUID,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> Response:
    try:
        lookbook_service.archive_entry(
            entry_id=entry_id,
            user_id=current_user.id,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Response(status_code=204)


@router.delete("/entries/{entry_id}", status_code=204)
def delete_lookbook_entry(
    entry_id: UUID,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> Response:
    try:
        lookbook_service.delete_entry(
            entry_id=entry_id,
            user_id=current_user.id,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Response(status_code=204)


@router.post("/entries/{entry_id}/wear", response_model=WearLogDetailSnapshot, status_code=201)
def create_wear_log_from_lookbook_entry(
    entry_id: UUID,
    payload: LookbookWearLogCreateRequest,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> WearLogDetailSnapshot:
    try:
        snapshot = lookbook_service.create_wear_log_from_entry(
            entry_id=entry_id,
            user_id=current_user.id,
            wear_date=payload.wear_date,
            worn_at=payload.worn_at,
            timezone_name=payload.timezone_name,
            context=payload.context,
            notes=payload.notes,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return WearLogDetailSnapshot.model_validate(snapshot, from_attributes=True)


@router.post("/uploads/intents", response_model=LookbookUploadIntentResponse)
def create_lookbook_upload_intent(
    payload: LookbookUploadIntentRequest,
    current_user: CurrentUser,
    upload_service: Annotated[LookbookUploadService, Depends(get_lookbook_upload_service)],
) -> LookbookUploadIntentResponse:
    try:
        result = upload_service.create_upload_intent(
            user_id=current_user.id,
            filename=payload.filename,
            mime_type=payload.mime_type,
            file_size=payload.file_size,
            sha256=payload.sha256,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return LookbookUploadIntentResponse(
        upload_intent_id=result.upload_intent.id,
        expires_at=result.presigned_upload.expires_at,
        upload=PresignedUploadDescriptor(
            method=result.presigned_upload.method,
            url=result.presigned_upload.url,
            headers=result.presigned_upload.headers,
        ),
    )


@router.post("/uploads/complete", response_model=PrivateImageSnapshot)
def complete_lookbook_upload(
    payload: LookbookUploadCompleteRequest,
    current_user: CurrentUser,
    upload_service: Annotated[LookbookUploadService, Depends(get_lookbook_upload_service)],
) -> PrivateImageSnapshot:
    try:
        snapshot = upload_service.complete_upload(
            user_id=current_user.id,
            upload_intent_id=payload.upload_intent_id,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return PrivateImageSnapshot.model_validate(snapshot, from_attributes=True)


def _build_linked_item_payload(items: list[object]) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for item in items:
        payload.append(
            {
                "closet_item_id": item.closet_item_id,
                "role": item.role,
                "sort_index": item.sort_index,
            }
        )
    return payload


def _build_entry_summary_snapshot(snapshot: object) -> LookbookEntrySummarySnapshot:
    return LookbookEntrySummarySnapshot.model_validate(snapshot, from_attributes=True)


def _build_entry_detail_snapshot(snapshot: object) -> LookbookEntryDetailSnapshot:
    return LookbookEntryDetailSnapshot.model_validate(snapshot, from_attributes=True)
