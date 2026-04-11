from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.wear import (
    get_wear_processing_service,
    get_wear_review_service,
    get_wear_service,
    get_wear_upload_service,
)
from app.api.schemas.closet import PresignedUploadDescriptor
from app.api.schemas.wear import (
    ManualWearLogCreateRequest,
    SavedOutfitWearLogCreateRequest,
    WearCalendarResponse,
    WearLogConfirmRequest,
    WearLogCreateRequest,
    WearLogDetailSnapshot,
    WearLogTimelineItemSnapshot,
    WearLogTimelineResponse,
    WearLogUpdateRequest,
    WearUploadCompleteRequest,
    WearUploadIntentRequest,
    WearUploadIntentResponse,
)
from app.domains.wear.processing_service import WearProcessingError, WearProcessingService
from app.domains.wear.review_service import WearReviewService
from app.domains.wear.service import InvalidWearHistoryCursorError, WearService, WearServiceError
from app.domains.wear.upload_service import WearUploadError, WearUploadService

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
            worn_at=getattr(payload, "worn_at", None),
            captured_at=getattr(payload, "captured_at", None),
            timezone_name=getattr(payload, "timezone_name", None),
            mode=payload.mode,
            context=payload.context,
            vibe=getattr(payload, "vibe", None),
            notes=payload.notes,
            items=_build_create_items(payload),
            outfit_id=_build_outfit_id(payload),
        )
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return WearLogDetailSnapshot.model_validate(snapshot, from_attributes=True)


@router.get("", response_model=WearLogTimelineResponse)
def read_wear_logs(
    current_user: CurrentUser,
    wear_service: Annotated[WearService, Depends(get_wear_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    wear_date: date | None = None,
    status: str | None = None,
    include_archived: bool = False,
) -> WearLogTimelineResponse:
    try:
        items, next_cursor = wear_service.list_wear_logs(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
            wear_date=wear_date,
            status=status,
            include_archived=include_archived,
        )
    except InvalidWearHistoryCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return WearLogTimelineResponse(
        items=[
            WearLogTimelineItemSnapshot.model_validate(item, from_attributes=True)
            for item in items
        ],
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

    return WearCalendarResponse.model_validate({"days": days}, from_attributes=True)


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

    return WearLogDetailSnapshot.model_validate(snapshot, from_attributes=True)


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
            worn_at=payload.worn_at,
            captured_at=payload.captured_at,
            timezone_name=payload.timezone_name,
            context=payload.context,
            vibe=payload.vibe,
            notes=payload.notes,
            items=(
                [
                    {
                        "closet_item_id": item.closet_item_id,
                        "role": item.role,
                        "sort_index": item.sort_index,
                        "detected_item_id": item.detected_item_id,
                        "source": item.source,
                        "match_confidence": item.match_confidence,
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

    return WearLogDetailSnapshot.model_validate(snapshot, from_attributes=True)


@router.post("/{wear_log_id}/photos/upload-intents", response_model=WearUploadIntentResponse)
def create_wear_log_upload_intent(
    wear_log_id: UUID,
    payload: WearUploadIntentRequest,
    current_user: CurrentUser,
    upload_service: Annotated[WearUploadService, Depends(get_wear_upload_service)],
) -> WearUploadIntentResponse:
    try:
        result = upload_service.create_upload_intent(
            wear_log_id=wear_log_id,
            user_id=current_user.id,
            filename=payload.filename,
            mime_type=payload.mime_type,
            file_size=payload.file_size,
            sha256=payload.sha256,
        )
    except WearUploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return WearUploadIntentResponse(
        upload_intent_id=result.upload_intent_id,
        expires_at=result.presigned_upload.expires_at,
        upload=PresignedUploadDescriptor(
            method=result.presigned_upload.method,
            url=result.presigned_upload.url,
            headers=result.presigned_upload.headers,
        ),
    )


@router.post("/{wear_log_id}/photos/uploads/complete", response_model=WearLogDetailSnapshot)
def complete_wear_log_upload(
    wear_log_id: UUID,
    payload: WearUploadCompleteRequest,
    current_user: CurrentUser,
    upload_service: Annotated[WearUploadService, Depends(get_wear_upload_service)],
) -> WearLogDetailSnapshot:
    try:
        snapshot = upload_service.complete_upload(
            wear_log_id=wear_log_id,
            user_id=current_user.id,
            upload_intent_id=payload.upload_intent_id,
        )
    except WearUploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return WearLogDetailSnapshot.model_validate(snapshot, from_attributes=True)


@router.post("/{wear_log_id}/confirm", response_model=WearLogDetailSnapshot)
def confirm_wear_log(
    wear_log_id: UUID,
    payload: WearLogConfirmRequest,
    current_user: CurrentUser,
    review_service: Annotated[WearReviewService, Depends(get_wear_review_service)],
) -> WearLogDetailSnapshot:
    try:
        snapshot = review_service.confirm_wear_log(
            wear_log_id=wear_log_id,
            user_id=current_user.id,
            expected_review_version=payload.expected_review_version,
            worn_at=payload.worn_at,
            captured_at=payload.captured_at,
            timezone_name=payload.timezone_name,
            context=payload.context,
            vibe=payload.vibe,
            notes=payload.notes,
            items=[
                {
                    "closet_item_id": item.closet_item_id,
                    "role": item.role,
                    "sort_index": item.sort_index,
                    "detected_item_id": item.detected_item_id,
                    "source": item.source,
                    "match_confidence": item.match_confidence,
                }
                for item in payload.items
            ],
            resolved_detected_items=[
                {
                    "detected_item_id": item.detected_item_id,
                    "status": item.status,
                    "exclusion_reason": item.exclusion_reason,
                }
                for item in payload.resolved_detected_items
            ],
        )
    except WearServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return WearLogDetailSnapshot.model_validate(snapshot, from_attributes=True)


@router.post("/{wear_log_id}/reprocess", response_model=WearLogDetailSnapshot, status_code=202)
def reprocess_wear_log(
    wear_log_id: UUID,
    current_user: CurrentUser,
    response: Response,
    processing_service: Annotated[WearProcessingService, Depends(get_wear_processing_service)],
) -> WearLogDetailSnapshot:
    try:
        snapshot, status_code = processing_service.reprocess_wear_log(
            wear_log_id=wear_log_id,
            user_id=current_user.id,
        )
    except WearProcessingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    response.status_code = status_code
    return WearLogDetailSnapshot.model_validate(snapshot, from_attributes=True)


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


def _build_create_items(payload: WearLogCreateRequest) -> list[dict[str, object]] | None:
    if isinstance(payload, ManualWearLogCreateRequest):
        return [
            {
                "closet_item_id": item.closet_item_id,
                "role": item.role,
                "sort_index": item.sort_index,
                "detected_item_id": item.detected_item_id,
                "source": item.source,
                "match_confidence": item.match_confidence,
            }
            for item in payload.items
        ]
    return None


def _build_outfit_id(payload: WearLogCreateRequest) -> UUID | None:
    if isinstance(payload, SavedOutfitWearLogCreateRequest):
        return payload.outfit_id
    return None


def _parse_date(value: str, *, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 date.") from exc
