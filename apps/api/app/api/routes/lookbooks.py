from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.lookbook import get_lookbook_service, get_lookbook_upload_service
from app.api.schemas.closet import PresignedUploadDescriptor
from app.api.schemas.lookbooks import (
    ImageLookbookEntryCreateRequest,
    LookbookCreateRequest,
    LookbookDetailSnapshot,
    LookbookEntriesReorderRequest,
    LookbookEntryCreateRequest,
    LookbookFlattenedEntryListResponse,
    LookbookFlattenedEntrySnapshot,
    LookbookEntryListResponse,
    LookbookEntrySnapshot,
    LookbookEntryTypeValue,
    LookbookListResponse,
    LookbookOutfitReferenceSnapshot,
    LookbookSummarySnapshot,
    LookbookUpdateRequest,
    LookbookUploadIntentRequest,
    LookbookUploadIntentResponse,
    NoteLookbookEntryCreateRequest,
    OutfitLookbookEntryCreateRequest,
    PrivateImageSnapshot,
)
from app.domains.lookbook.errors import LookbookError
from app.domains.lookbook.service import (
    InvalidLookbookCursorError,
    InvalidLookbookEntryCursorError,
    LookbookService,
)
from app.domains.lookbook.service import (
    LookbookDetailSnapshot as LookbookDetailView,
)
from app.domains.lookbook.service import (
    LookbookFlattenedEntrySnapshot as LookbookFlattenedEntryView,
)
from app.domains.lookbook.service import LookbookEntrySnapshot as LookbookEntryView
from app.domains.lookbook.service import LookbookOutfitReferenceSnapshot as LookbookOutfitView
from app.domains.lookbook.service import LookbookSummarySnapshot as LookbookSummaryView
from app.domains.lookbook.service import PrivateImageSnapshot as PrivateImageView
from app.domains.lookbook.upload_service import LookbookUploadService

router = APIRouter(prefix="/lookbooks", tags=["lookbooks"])


@router.post("", response_model=LookbookDetailSnapshot, status_code=201)
def create_lookbook(
    payload: LookbookCreateRequest,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> LookbookDetailSnapshot:
    try:
        snapshot = lookbook_service.create_lookbook(
            user_id=current_user.id,
            title=payload.title,
            description=payload.description,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return build_lookbook_detail_snapshot(snapshot)


@router.get("", response_model=LookbookListResponse)
def read_lookbooks(
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> LookbookListResponse:
    try:
        items, next_cursor = lookbook_service.list_lookbooks(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
        )
    except InvalidLookbookCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return LookbookListResponse(
        items=[build_lookbook_summary_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/entries", response_model=LookbookFlattenedEntryListResponse)
def read_flattened_lookbook_entries(
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> LookbookFlattenedEntryListResponse:
    try:
        items, next_cursor = lookbook_service.list_entries_for_user(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
        )
    except InvalidLookbookEntryCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return LookbookFlattenedEntryListResponse(
        items=[build_flattened_lookbook_entry_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/entries/{entry_id}", response_model=LookbookFlattenedEntrySnapshot)
def read_flattened_lookbook_entry_detail(
    entry_id: UUID,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> LookbookFlattenedEntrySnapshot:
    try:
        snapshot = lookbook_service.get_entry_snapshot_for_user(
            entry_id=entry_id,
            user_id=current_user.id,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_flattened_lookbook_entry_snapshot(snapshot)


@router.get("/{lookbook_id}", response_model=LookbookDetailSnapshot)
def read_lookbook_detail(
    lookbook_id: UUID,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> LookbookDetailSnapshot:
    try:
        snapshot = lookbook_service.get_lookbook_detail(
            lookbook_id=lookbook_id,
            user_id=current_user.id,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return build_lookbook_detail_snapshot(snapshot)


@router.patch("/{lookbook_id}", response_model=LookbookDetailSnapshot)
def update_lookbook(
    lookbook_id: UUID,
    payload: LookbookUpdateRequest,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> LookbookDetailSnapshot:
    try:
        snapshot = lookbook_service.update_lookbook(
            lookbook_id=lookbook_id,
            user_id=current_user.id,
            title=payload.title,
            description=payload.description,
            field_names=payload.model_fields_set,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return build_lookbook_detail_snapshot(snapshot)


@router.delete("/{lookbook_id}", status_code=204)
def delete_lookbook(
    lookbook_id: UUID,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> Response:
    try:
        lookbook_service.delete_lookbook(lookbook_id=lookbook_id, user_id=current_user.id)
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Response(status_code=204)


@router.post("/{lookbook_id}/upload-intents", response_model=LookbookUploadIntentResponse)
def create_lookbook_upload_intent(
    lookbook_id: UUID,
    payload: LookbookUploadIntentRequest,
    current_user: CurrentUser,
    upload_service: Annotated[LookbookUploadService, Depends(get_lookbook_upload_service)],
) -> LookbookUploadIntentResponse:
    try:
        result = upload_service.create_upload_intent(
            lookbook_id=lookbook_id,
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


@router.get("/{lookbook_id}/entries", response_model=LookbookEntryListResponse)
def read_lookbook_entries(
    lookbook_id: UUID,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> LookbookEntryListResponse:
    try:
        items, next_cursor = lookbook_service.list_entries(
            lookbook_id=lookbook_id,
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
        )
    except InvalidLookbookEntryCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return LookbookEntryListResponse(
        items=[build_lookbook_entry_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.post("/{lookbook_id}/entries", response_model=LookbookEntrySnapshot, status_code=201)
def create_lookbook_entry(
    lookbook_id: UUID,
    payload: LookbookEntryCreateRequest,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
    upload_service: Annotated[LookbookUploadService, Depends(get_lookbook_upload_service)],
) -> LookbookEntrySnapshot:
    try:
        if isinstance(payload, OutfitLookbookEntryCreateRequest):
            snapshot = lookbook_service.create_outfit_entry(
                lookbook_id=lookbook_id,
                user_id=current_user.id,
                outfit_id=payload.outfit_id,
                caption=payload.caption,
            )
        elif isinstance(payload, ImageLookbookEntryCreateRequest):
            snapshot = upload_service.create_image_entry(
                lookbook_id=lookbook_id,
                user_id=current_user.id,
                upload_intent_id=payload.upload_intent_id,
                caption=payload.caption,
            )
        elif isinstance(payload, NoteLookbookEntryCreateRequest):
            snapshot = lookbook_service.create_note_entry(
                lookbook_id=lookbook_id,
                user_id=current_user.id,
                note_text=payload.note_text,
            )
        else:
            raise HTTPException(status_code=422, detail="Unsupported lookbook entry type.")
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return build_lookbook_entry_snapshot(snapshot)


@router.patch("/{lookbook_id}/entries/reorder", status_code=204)
def reorder_lookbook_entries(
    lookbook_id: UUID,
    payload: LookbookEntriesReorderRequest,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> Response:
    try:
        lookbook_service.reorder_entries(
            lookbook_id=lookbook_id,
            user_id=current_user.id,
            entry_ids=payload.entry_ids,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Response(status_code=204)


@router.delete("/{lookbook_id}/entries/{entry_id}", status_code=204)
def delete_lookbook_entry(
    lookbook_id: UUID,
    entry_id: UUID,
    current_user: CurrentUser,
    lookbook_service: Annotated[LookbookService, Depends(get_lookbook_service)],
) -> Response:
    try:
        lookbook_service.delete_entry(
            lookbook_id=lookbook_id,
            entry_id=entry_id,
            user_id=current_user.id,
        )
    except LookbookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Response(status_code=204)


def build_lookbook_summary_snapshot(snapshot: LookbookSummaryView) -> LookbookSummarySnapshot:
    return LookbookSummarySnapshot(
        id=snapshot.id,
        title=snapshot.title,
        description=snapshot.description,
        entry_count=snapshot.entry_count,
        cover_image=build_private_image_snapshot(snapshot.cover_image),
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def build_lookbook_detail_snapshot(snapshot: LookbookDetailView) -> LookbookDetailSnapshot:
    return LookbookDetailSnapshot(
        id=snapshot.id,
        title=snapshot.title,
        description=snapshot.description,
        entry_count=snapshot.entry_count,
        cover_image=build_private_image_snapshot(snapshot.cover_image),
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def build_lookbook_entry_snapshot(snapshot: LookbookEntryView) -> LookbookEntrySnapshot:
    return LookbookEntrySnapshot(
        id=snapshot.id,
        entry_type=cast(LookbookEntryTypeValue, snapshot.entry_type),
        caption=snapshot.caption,
        note_text=snapshot.note_text,
        sort_index=snapshot.sort_index,
        image=build_private_image_snapshot(snapshot.image),
        outfit=build_outfit_reference_snapshot(snapshot.outfit),
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def build_flattened_lookbook_entry_snapshot(
    snapshot: LookbookFlattenedEntryView,
) -> LookbookFlattenedEntrySnapshot:
    return LookbookFlattenedEntrySnapshot(
        lookbook_id=snapshot.lookbook_id,
        lookbook_title=snapshot.lookbook_title,
        lookbook_description=snapshot.lookbook_description,
        lookbook_cover_image=build_private_image_snapshot(snapshot.lookbook_cover_image),
        entry=build_lookbook_entry_snapshot(snapshot.entry),
    )


def build_outfit_reference_snapshot(
    snapshot: LookbookOutfitView | None,
) -> LookbookOutfitReferenceSnapshot | None:
    if snapshot is None:
        return None
    return LookbookOutfitReferenceSnapshot(
        id=snapshot.id,
        title=snapshot.title,
        is_favorite=snapshot.is_favorite,
        is_archived=snapshot.is_archived,
        item_count=snapshot.item_count,
        cover_image=build_private_image_snapshot(snapshot.cover_image),
    )


def build_private_image_snapshot(
    snapshot: PrivateImageView | None,
) -> PrivateImageSnapshot | None:
    if snapshot is None:
        return None
    return PrivateImageSnapshot(
        asset_id=snapshot.asset_id,
        mime_type=snapshot.mime_type,
        width=snapshot.width,
        height=snapshot.height,
        url=snapshot.url,
        expires_at=snapshot.expires_at,
    )
