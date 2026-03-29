from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.closet import (
    get_closet_image_processing_service,
    get_closet_metadata_extraction_service,
    get_closet_review_service,
    get_closet_upload_service,
)
from app.api.schemas.closet import (
    ClosetConfirmRequest,
    ClosetDraftCreateRequest,
    ClosetDraftSnapshot,
    ClosetExtractionCurrentCandidateSet,
    ClosetExtractionSnapshot,
    ClosetFieldCandidateSnapshot,
    ClosetFieldStateSnapshot,
    ClosetItemReviewSnapshot,
    ClosetMetadataOptionsResponse,
    ClosetMetadataProjectionSnapshot,
    ClosetProcessingImageSnapshot,
    ClosetProcessingRunSnapshot,
    ClosetProcessingSnapshot,
    ClosetProviderResultSnapshot,
    ClosetRetryActionSnapshot,
    ClosetRetryRequest,
    ClosetReviewFieldSnapshot,
    ClosetReviewListResponse,
    ClosetReviewPatchRequest,
    ClosetSuggestedFieldStateSnapshot,
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
from app.domains.closet.metadata_extraction_service import (
    ClosetMetadataExtractionService,
    ExtractionSnapshot,
)
from app.domains.closet.review_service import ClosetReviewService, ReviewSnapshot
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


@router.get("/items/{item_id}/extraction", response_model=ClosetExtractionSnapshot)
def read_extraction_status(
    item_id: UUID,
    current_user: CurrentUser,
    extraction_service: Annotated[
        ClosetMetadataExtractionService, Depends(get_closet_metadata_extraction_service)
    ],
) -> ClosetExtractionSnapshot:
    try:
        snapshot = extraction_service.get_extraction_snapshot(
            item_id=item_id,
            user_id=current_user.id,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_extraction_snapshot(snapshot)


@router.get("/items/{item_id}/review", response_model=ClosetItemReviewSnapshot)
def read_item_review(
    item_id: UUID,
    current_user: CurrentUser,
    review_service: Annotated[ClosetReviewService, Depends(get_closet_review_service)],
) -> ClosetItemReviewSnapshot:
    try:
        snapshot = review_service.get_review_snapshot(
            item_id=item_id,
            user_id=current_user.id,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_review_snapshot(snapshot)


@router.patch("/items/{item_id}", response_model=ClosetItemReviewSnapshot)
def patch_item_review(
    item_id: UUID,
    payload: ClosetReviewPatchRequest,
    current_user: CurrentUser,
    review_service: Annotated[ClosetReviewService, Depends(get_closet_review_service)],
) -> ClosetItemReviewSnapshot:
    try:
        snapshot = review_service.patch_review(
            item_id=item_id,
            user_id=current_user.id,
            expected_review_version=payload.expected_review_version,
            changes=[change.model_dump() for change in payload.changes],
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_review_snapshot(snapshot)


@router.post("/items/{item_id}/confirm", response_model=ClosetItemReviewSnapshot)
def confirm_item_review(
    item_id: UUID,
    payload: ClosetConfirmRequest,
    current_user: CurrentUser,
    review_service: Annotated[ClosetReviewService, Depends(get_closet_review_service)],
) -> ClosetItemReviewSnapshot:
    try:
        snapshot = review_service.confirm_review(
            item_id=item_id,
            user_id=current_user.id,
            expected_review_version=payload.expected_review_version,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_review_snapshot(snapshot)


@router.post("/items/{item_id}/retry", response_model=ClosetItemReviewSnapshot, status_code=202)
def retry_item_review(
    item_id: UUID,
    response: Response,
    current_user: CurrentUser,
    review_service: Annotated[ClosetReviewService, Depends(get_closet_review_service)],
    payload: ClosetRetryRequest | None = None,
) -> ClosetItemReviewSnapshot:
    try:
        snapshot, status_code = review_service.retry_review(
            item_id=item_id,
            user_id=current_user.id,
            step=None if payload is None else payload.step,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    response.status_code = status_code
    return build_review_snapshot(snapshot)


@router.post("/items/{item_id}/reextract", response_model=ClosetExtractionSnapshot, status_code=202)
def reextract_item_metadata(
    item_id: UUID,
    response: Response,
    current_user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    extraction_service: Annotated[
        ClosetMetadataExtractionService, Depends(get_closet_metadata_extraction_service)
    ],
) -> ClosetExtractionSnapshot:
    try:
        snapshot, status_code = extraction_service.reextract_item(
            item_id=item_id,
            user_id=current_user.id,
            idempotency_key=idempotency_key,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    response.status_code = status_code
    return build_extraction_snapshot(snapshot)


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


def _build_image_payload(image: object | None) -> ClosetProcessingImageSnapshot | None:
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


def _build_run_payload(run: object | None) -> ClosetProcessingRunSnapshot | None:
    if run is None:
        return None
    return ClosetProcessingRunSnapshot(
        id=getattr(run, "id"),
        run_type=getattr(run, "run_type").value
        if hasattr(getattr(run, "run_type"), "value")
        else getattr(run, "run_type"),
        status=getattr(run, "status").value
        if hasattr(getattr(run, "status"), "value")
        else getattr(run, "status"),
        retry_count=getattr(run, "retry_count"),
        started_at=getattr(run, "started_at"),
        completed_at=getattr(run, "completed_at"),
        failure_code=getattr(run, "failure_code"),
    )


def _build_candidate_set_payload(
    current_candidate_set: object | None,
) -> ClosetExtractionCurrentCandidateSet | None:
    if current_candidate_set is None:
        return None
    return ClosetExtractionCurrentCandidateSet(
        provider_result_id=getattr(current_candidate_set, "provider_result_id"),
        status=getattr(current_candidate_set, "status"),
        created_at=getattr(current_candidate_set, "created_at"),
        field_candidates=[
            ClosetFieldCandidateSnapshot(
                id=getattr(candidate, "id"),
                field_name=getattr(candidate, "field_name"),
                raw_value=getattr(candidate, "raw_value"),
                normalized_candidate=getattr(candidate, "normalized_candidate"),
                confidence=getattr(candidate, "confidence"),
                applicability_state=getattr(candidate, "applicability_state"),
                conflict_notes=getattr(candidate, "conflict_notes"),
                provider_result_id=getattr(candidate, "provider_result_id"),
                created_at=getattr(candidate, "created_at"),
            )
            for candidate in getattr(current_candidate_set, "field_candidates")
        ],
    )


def _build_field_state_payload(field_state: object) -> ClosetFieldStateSnapshot:
    return ClosetFieldStateSnapshot(
        field_name=getattr(field_state, "field_name"),
        canonical_value=getattr(field_state, "canonical_value"),
        source=getattr(field_state, "source"),
        confidence=getattr(field_state, "confidence"),
        review_state=getattr(field_state, "review_state"),
        applicability_state=getattr(field_state, "applicability_state"),
        taxonomy_version=getattr(field_state, "taxonomy_version"),
        updated_at=getattr(field_state, "updated_at"),
    )


def build_processing_snapshot(snapshot: ProcessingSnapshot) -> ClosetProcessingSnapshot:
    return ClosetProcessingSnapshot(
        item_id=getattr(snapshot, "item_id"),
        lifecycle_status=getattr(snapshot, "lifecycle_status"),
        processing_status=getattr(snapshot, "processing_status"),
        review_status=getattr(snapshot, "review_status"),
        failure_summary=getattr(snapshot, "failure_summary"),
        can_reprocess=getattr(snapshot, "can_reprocess"),
        latest_run=_build_run_payload(getattr(snapshot, "latest_run")),
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
        display_image=_build_image_payload(getattr(snapshot, "display_image")),
        original_image=_build_image_payload(getattr(snapshot, "original_image")),
        thumbnail_image=_build_image_payload(getattr(snapshot, "thumbnail_image")),
    )


def build_extraction_snapshot(snapshot: ExtractionSnapshot) -> ClosetExtractionSnapshot:
    return ClosetExtractionSnapshot(
        item_id=getattr(snapshot, "item_id"),
        lifecycle_status=getattr(snapshot, "lifecycle_status"),
        review_status=getattr(snapshot, "review_status"),
        extraction_status=getattr(snapshot, "extraction_status"),
        normalization_status=getattr(snapshot, "normalization_status"),
        field_states_stale=getattr(snapshot, "field_states_stale"),
        can_reextract=getattr(snapshot, "can_reextract"),
        source_image=_build_image_payload(getattr(snapshot, "source_image")),
        latest_run=_build_run_payload(getattr(snapshot, "latest_run")),
        latest_normalization_run=_build_run_payload(getattr(snapshot, "latest_normalization_run")),
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
        current_candidate_set=_build_candidate_set_payload(
            getattr(snapshot, "current_candidate_set")
        ),
        current_field_states=[
            _build_field_state_payload(field_state)
            for field_state in getattr(snapshot, "current_field_states")
        ],
        metadata_projection=None
        if getattr(snapshot, "metadata_projection") is None
        else ClosetMetadataProjectionSnapshot(
            taxonomy_version=getattr(getattr(snapshot, "metadata_projection"), "taxonomy_version"),
            title=getattr(getattr(snapshot, "metadata_projection"), "title"),
            category=getattr(getattr(snapshot, "metadata_projection"), "category"),
            subcategory=getattr(getattr(snapshot, "metadata_projection"), "subcategory"),
            primary_color=getattr(getattr(snapshot, "metadata_projection"), "primary_color"),
            secondary_colors=getattr(
                getattr(snapshot, "metadata_projection"), "secondary_colors"
            ),
            material=getattr(getattr(snapshot, "metadata_projection"), "material"),
            pattern=getattr(getattr(snapshot, "metadata_projection"), "pattern"),
            brand=getattr(getattr(snapshot, "metadata_projection"), "brand"),
            style_tags=getattr(getattr(snapshot, "metadata_projection"), "style_tags"),
            occasion_tags=getattr(getattr(snapshot, "metadata_projection"), "occasion_tags"),
            season_tags=getattr(getattr(snapshot, "metadata_projection"), "season_tags"),
            confirmed_at=getattr(getattr(snapshot, "metadata_projection"), "confirmed_at"),
            updated_at=getattr(getattr(snapshot, "metadata_projection"), "updated_at"),
        ),
    )


def build_review_snapshot(snapshot: ReviewSnapshot) -> ClosetItemReviewSnapshot:
    return ClosetItemReviewSnapshot(
        item_id=getattr(snapshot, "item_id"),
        lifecycle_status=getattr(snapshot, "lifecycle_status"),
        processing_status=getattr(snapshot, "processing_status"),
        extraction_status=getattr(snapshot, "extraction_status"),
        normalization_status=getattr(snapshot, "normalization_status"),
        review_status=getattr(snapshot, "review_status"),
        failure_summary=getattr(snapshot, "failure_summary"),
        confirmed_at=getattr(snapshot, "confirmed_at"),
        review_version=getattr(snapshot, "review_version"),
        can_confirm=getattr(snapshot, "can_confirm"),
        missing_required_fields=list(getattr(snapshot, "missing_required_fields")),
        field_states_stale=getattr(snapshot, "field_states_stale"),
        retry_action=ClosetRetryActionSnapshot(
            can_retry=getattr(getattr(snapshot, "retry_action"), "can_retry"),
            default_step=getattr(getattr(snapshot, "retry_action"), "default_step"),
            reason=getattr(getattr(snapshot, "retry_action"), "reason"),
        ),
        latest_processing_run=_build_run_payload(getattr(snapshot, "latest_processing_run")),
        latest_extraction_run=_build_run_payload(getattr(snapshot, "latest_extraction_run")),
        latest_normalization_run=_build_run_payload(getattr(snapshot, "latest_normalization_run")),
        display_image=_build_image_payload(getattr(snapshot, "display_image")),
        original_image=_build_image_payload(getattr(snapshot, "original_image")),
        thumbnail_image=_build_image_payload(getattr(snapshot, "thumbnail_image")),
        review_fields=[
            ClosetReviewFieldSnapshot(
                field_name=getattr(field, "field_name"),
                required=getattr(field, "required"),
                blocking_confirmation=getattr(field, "blocking_confirmation"),
                current_state=_build_field_state_payload(getattr(field, "current_state")),
                suggested_state=None
                if getattr(field, "suggested_state") is None
                else ClosetSuggestedFieldStateSnapshot(
                    canonical_value=getattr(getattr(field, "suggested_state"), "canonical_value"),
                    confidence=getattr(getattr(field, "suggested_state"), "confidence"),
                    applicability_state=getattr(
                        getattr(field, "suggested_state"), "applicability_state"
                    ),
                    conflict_notes=getattr(
                        getattr(field, "suggested_state"), "conflict_notes"
                    ),
                    provider_result_id=getattr(
                        getattr(field, "suggested_state"), "provider_result_id"
                    ),
                    is_derived=getattr(getattr(field, "suggested_state"), "is_derived"),
                ),
            )
            for field in getattr(snapshot, "review_fields")
        ],
        current_candidate_set=_build_candidate_set_payload(
            getattr(snapshot, "current_candidate_set")
        ),
    )


def _http_error(exc: ClosetDomainError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.detail},
    )
