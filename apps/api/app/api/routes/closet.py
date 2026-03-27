from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.closet import (
    get_closet_image_processing_service,
    get_closet_upload_service,
)
from app.api.schemas.closet import (
    ClosetDraftCreateRequest,
    ClosetDraftSnapshot,
    ClosetMetadataOptionsResponse,
    ClosetProcessingImageSnapshot,
    ClosetProcessingRunSnapshot,
    ClosetProcessingSnapshot,
    ClosetProviderResultSnapshot,
    ClosetReviewListResponse,
    ClosetUploadCompleteRequest,
    ClosetUploadIntentRequest,
    ClosetUploadIntentResponse,
    PresignedUploadDescriptor,
)
from app.domains.closet.errors import ClosetDomainError
from app.domains.closet.image_processing_service import (
    ClosetImageProcessingService,
    ProcessingSnapshot,
)
from app.domains.closet.taxonomy import build_metadata_options
from app.domains.closet.upload_service import ClosetDraftUploadService, InvalidReviewCursorError

router = APIRouter(prefix="/closet", tags=["closet"])


@router.get("/metadata/options", response_model=ClosetMetadataOptionsResponse)
def read_metadata_options(current_user: CurrentUser) -> ClosetMetadataOptionsResponse:
    del current_user
    return ClosetMetadataOptionsResponse.model_validate(build_metadata_options())


@router.post("/drafts", response_model=ClosetDraftSnapshot, status_code=201)
def create_draft(
    payload: ClosetDraftCreateRequest,
    response: Response,
    current_user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    upload_service: Annotated[ClosetDraftUploadService, Depends(get_closet_upload_service)],
) -> ClosetDraftSnapshot:
    try:
        item, status_code = upload_service.create_draft(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            title=payload.title,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    response.status_code = status_code
    return build_draft_snapshot(item)


@router.get("/drafts/{item_id}", response_model=ClosetDraftSnapshot)
def read_draft(
    item_id: UUID,
    current_user: CurrentUser,
    upload_service: Annotated[ClosetDraftUploadService, Depends(get_closet_upload_service)],
) -> ClosetDraftSnapshot:
    try:
        item = upload_service.get_draft(item_id=item_id, user_id=current_user.id)
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_draft_snapshot(item)


@router.post("/drafts/{item_id}/upload-intents", response_model=ClosetUploadIntentResponse)
def create_upload_intent(
    item_id: UUID,
    payload: ClosetUploadIntentRequest,
    current_user: CurrentUser,
    upload_service: Annotated[ClosetDraftUploadService, Depends(get_closet_upload_service)],
) -> ClosetUploadIntentResponse:
    try:
        result = upload_service.create_upload_intent(
            item_id=item_id,
            user_id=current_user.id,
            filename=payload.filename,
            mime_type=payload.mime_type,
            file_size=payload.file_size,
            sha256=payload.sha256,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return ClosetUploadIntentResponse(
        upload_intent_id=result.upload_intent.id,
        expires_at=result.presigned_upload.expires_at,
        upload=PresignedUploadDescriptor(
            method=result.presigned_upload.method,
            url=result.presigned_upload.url,
            headers=result.presigned_upload.headers,
        ),
    )


@router.post("/drafts/{item_id}/uploads/complete", response_model=ClosetDraftSnapshot)
def complete_upload(
    item_id: UUID,
    payload: ClosetUploadCompleteRequest,
    response: Response,
    current_user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    upload_service: Annotated[ClosetDraftUploadService, Depends(get_closet_upload_service)],
) -> ClosetDraftSnapshot:
    try:
        item, status_code = upload_service.complete_upload(
            item_id=item_id,
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            upload_intent_id=payload.upload_intent_id,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    response.status_code = status_code
    return build_draft_snapshot(item)


@router.get("/review", response_model=ClosetReviewListResponse)
def read_review_queue(
    current_user: CurrentUser,
    upload_service: Annotated[ClosetDraftUploadService, Depends(get_closet_upload_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ClosetReviewListResponse:
    try:
        items, next_cursor = upload_service.list_review_items(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
        )
    except InvalidReviewCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ClosetReviewListResponse(
        items=[build_draft_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/items/{item_id}/processing", response_model=ClosetProcessingSnapshot)
def read_processing_status(
    item_id: UUID,
    current_user: CurrentUser,
    processing_service: Annotated[
        ClosetImageProcessingService, Depends(get_closet_image_processing_service)
    ],
) -> ClosetProcessingSnapshot:
    try:
        snapshot = processing_service.get_processing_snapshot(
            item_id=item_id,
            user_id=current_user.id,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_processing_snapshot(snapshot)


@router.post("/items/{item_id}/reprocess", response_model=ClosetProcessingSnapshot, status_code=202)
def reprocess_item_image(
    item_id: UUID,
    response: Response,
    current_user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    processing_service: Annotated[
        ClosetImageProcessingService, Depends(get_closet_image_processing_service)
    ],
) -> ClosetProcessingSnapshot:
    try:
        snapshot, status_code = processing_service.reprocess_item(
            item_id=item_id,
            user_id=current_user.id,
            idempotency_key=idempotency_key,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    response.status_code = status_code
    return build_processing_snapshot(snapshot)


def build_draft_snapshot(item: object) -> ClosetDraftSnapshot:
    item_id = getattr(item, "id")
    title = getattr(item, "title")
    lifecycle_status = getattr(item, "lifecycle_status").value
    processing_status = getattr(item, "processing_status").value
    review_status = getattr(item, "review_status").value
    failure_summary = getattr(item, "failure_summary")
    has_primary_image = getattr(item, "primary_image_id") is not None
    created_at = getattr(item, "created_at")
    updated_at = getattr(item, "updated_at")
    return ClosetDraftSnapshot(
        id=item_id,
        title=title,
        lifecycle_status=lifecycle_status,
        processing_status=processing_status,
        review_status=review_status,
        failure_summary=failure_summary,
        has_primary_image=has_primary_image,
        created_at=created_at,
        updated_at=updated_at,
    )


def build_processing_snapshot(snapshot: ProcessingSnapshot) -> ClosetProcessingSnapshot:
    def image_payload(image: object | None) -> ClosetProcessingImageSnapshot | None:
        if image is None:
            return None
        return ClosetProcessingImageSnapshot(
            asset_id=getattr(image, "asset_id"),
            role=getattr(image, "role"),
            mime_type=getattr(image, "mime_type"),
            width=getattr(image, "width"),
            height=getattr(image, "height"),
            url=getattr(image, "url"),
            expires_at=getattr(image, "expires_at"),
        )

    latest_run = getattr(snapshot, "latest_run")
    return ClosetProcessingSnapshot(
        item_id=getattr(snapshot, "item_id"),
        lifecycle_status=getattr(snapshot, "lifecycle_status"),
        processing_status=getattr(snapshot, "processing_status"),
        review_status=getattr(snapshot, "review_status"),
        failure_summary=getattr(snapshot, "failure_summary"),
        can_reprocess=getattr(snapshot, "can_reprocess"),
        latest_run=None
        if latest_run is None
        else ClosetProcessingRunSnapshot(
            id=getattr(latest_run, "id"),
            run_type=getattr(latest_run, "run_type"),
            status=getattr(latest_run, "status"),
            retry_count=getattr(latest_run, "retry_count"),
            started_at=getattr(latest_run, "started_at"),
            completed_at=getattr(latest_run, "completed_at"),
            failure_code=getattr(latest_run, "failure_code"),
        ),
        provider_results=[
            ClosetProviderResultSnapshot(
                id=getattr(provider_result, "id"),
                provider_name=getattr(provider_result, "provider_name"),
                provider_model=getattr(provider_result, "provider_model"),
                provider_version=getattr(provider_result, "provider_version"),
                task_type=getattr(provider_result, "task_type"),
                status=getattr(provider_result, "status"),
                raw_payload=getattr(provider_result, "raw_payload"),
                created_at=getattr(provider_result, "created_at"),
            )
            for provider_result in getattr(snapshot, "provider_results")
        ],
        display_image=image_payload(getattr(snapshot, "display_image")),
        original_image=image_payload(getattr(snapshot, "original_image")),
        thumbnail_image=image_payload(getattr(snapshot, "thumbnail_image")),
    )


def _http_error(exc: ClosetDomainError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.detail},
    )
