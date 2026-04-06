from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.closet import (
    get_closet_browse_service,
    get_closet_image_processing_service,
    get_closet_lifecycle_service,
    get_closet_metadata_extraction_service,
    get_closet_review_service,
    get_closet_similarity_service,
    get_closet_upload_service,
)
from app.api.schemas.closet import (
    ClosetBrowseListItemSnapshot,
    ClosetBrowseListResponse,
    ClosetConfirmRequest,
    ClosetDraftCreateRequest,
    ClosetDraftSnapshot,
    ClosetExtractionCurrentCandidateSet,
    ClosetExtractionSnapshot,
    ClosetFieldCandidateSnapshot,
    ClosetFieldStateSnapshot,
    ClosetHistoryEventSnapshot,
    ClosetHistoryResponse,
    ClosetItemDetailSnapshot,
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
    ClosetSimilarityEdgeSnapshot,
    ClosetSimilarityListItemSnapshot,
    ClosetSimilarityListResponse,
    ClosetSimilaritySignalSnapshot,
    ClosetSuggestedFieldStateSnapshot,
    ClosetUploadCompleteRequest,
    ClosetUploadIntentRequest,
    ClosetUploadIntentResponse,
    PresignedUploadDescriptor,
)
from app.domains.closet.browse_service import (
    BrowseDetailSnapshot,
    BrowseListItemSnapshot,
    ClosetBrowseService,
    InvalidBrowseCursorError,
    InvalidBrowseFilterError,
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
from app.domains.closet.service import (
    ClosetLifecycleService,
    InvalidHistoryCursorError,
)
from app.domains.closet.similarity_service import (
    ClosetSimilarityService,
    SimilarityEdgeSnapshot,
    SimilarityListItemSnapshot,
    SimilarityListSnapshot,
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
    return build_draft_snapshot(
        item,
        upload_service.list_original_images(item_id=item.id, user_id=current_user.id),
    )


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

    return build_draft_snapshot(
        item,
        upload_service.list_original_images(item_id=item.id, user_id=current_user.id),
    )


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
    return build_draft_snapshot(
        item,
        upload_service.list_original_images(item_id=item.id, user_id=current_user.id),
    )


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
        items=[
            build_draft_snapshot(
                item,
                upload_service.list_original_images(item_id=item.id, user_id=current_user.id),
            )
            for item in items
        ],
        next_cursor=next_cursor,
    )


@router.get("/items", response_model=ClosetBrowseListResponse)
def read_confirmed_items(
    current_user: CurrentUser,
    browse_service: Annotated[ClosetBrowseService, Depends(get_closet_browse_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    query: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    color: str | None = None,
    material: str | None = None,
    pattern: str | None = None,
) -> ClosetBrowseListResponse:
    try:
        items, next_cursor = browse_service.list_confirmed_items(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
            query=query,
            category=category,
            subcategory=subcategory,
            color=color,
            material=material,
            pattern=pattern,
        )
    except (InvalidBrowseCursorError, InvalidBrowseFilterError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ClosetBrowseListResponse(
        items=[build_browse_list_item_snapshot(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/items/{item_id}", response_model=ClosetItemDetailSnapshot)
def read_confirmed_item_detail(
    item_id: UUID,
    current_user: CurrentUser,
    browse_service: Annotated[ClosetBrowseService, Depends(get_closet_browse_service)],
) -> ClosetItemDetailSnapshot:
    try:
        snapshot = browse_service.get_confirmed_item_detail(
            item_id=item_id,
            user_id=current_user.id,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_item_detail_snapshot(snapshot)


@router.get("/items/{item_id}/history", response_model=ClosetHistoryResponse)
def read_item_history(
    item_id: UUID,
    current_user: CurrentUser,
    lifecycle_service: Annotated[ClosetLifecycleService, Depends(get_closet_lifecycle_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ClosetHistoryResponse:
    try:
        items, next_cursor = lifecycle_service.list_item_history(
            item_id=item_id,
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
        )
    except InvalidHistoryCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return ClosetHistoryResponse(
        items=[
            ClosetHistoryEventSnapshot(
                id=getattr(event, "id"),
                actor_user_id=getattr(event, "actor_user_id"),
                actor_type=_enum_str(getattr(event, "actor_type")),
                event_type=getattr(event, "event_type"),
                payload=getattr(event, "payload"),
                created_at=getattr(event, "created_at"),
            )
            for event in items
        ],
        next_cursor=next_cursor,
    )


@router.get("/items/{item_id}/similar", response_model=ClosetSimilarityListResponse)
def read_similar_items(
    item_id: UUID,
    current_user: CurrentUser,
    similarity_service: Annotated[ClosetSimilarityService, Depends(get_closet_similarity_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ClosetSimilarityListResponse:
    try:
        snapshot = similarity_service.list_similar_items(
            item_id=item_id,
            user_id=current_user.id,
            limit=limit,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_similarity_list_snapshot(snapshot)


@router.get("/items/{item_id}/duplicates", response_model=ClosetSimilarityListResponse)
def read_duplicate_items(
    item_id: UUID,
    current_user: CurrentUser,
    similarity_service: Annotated[ClosetSimilarityService, Depends(get_closet_similarity_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ClosetSimilarityListResponse:
    try:
        snapshot = similarity_service.list_duplicate_items(
            item_id=item_id,
            user_id=current_user.id,
            limit=limit,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_similarity_list_snapshot(snapshot)


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


@router.post("/items/{item_id}/archive", status_code=204)
def archive_item(
    item_id: UUID,
    current_user: CurrentUser,
    lifecycle_service: Annotated[ClosetLifecycleService, Depends(get_closet_lifecycle_service)],
) -> Response:
    try:
        lifecycle_service.archive_item(item_id=item_id, user_id=current_user.id)
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return Response(status_code=204)


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


@router.post("/similarity/{edge_id}/dismiss", response_model=ClosetSimilarityEdgeSnapshot)
def dismiss_similarity_edge(
    edge_id: UUID,
    current_user: CurrentUser,
    similarity_service: Annotated[ClosetSimilarityService, Depends(get_closet_similarity_service)],
) -> ClosetSimilarityEdgeSnapshot:
    try:
        snapshot = similarity_service.dismiss_edge(
            edge_id=edge_id,
            user_id=current_user.id,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_similarity_edge_snapshot(snapshot)


@router.post("/similarity/{edge_id}/mark-duplicate", response_model=ClosetSimilarityEdgeSnapshot)
def mark_similarity_edge_duplicate(
    edge_id: UUID,
    current_user: CurrentUser,
    similarity_service: Annotated[ClosetSimilarityService, Depends(get_closet_similarity_service)],
) -> ClosetSimilarityEdgeSnapshot:
    try:
        snapshot = similarity_service.mark_edge_duplicate(
            edge_id=edge_id,
            user_id=current_user.id,
        )
    except ClosetDomainError as exc:
        raise _http_error(exc) from exc

    return build_similarity_edge_snapshot(snapshot)


def build_draft_snapshot(
    item: object,
    original_images: Sequence[object | None],
) -> ClosetDraftSnapshot:
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
        original_images=_build_image_payloads(original_images),
        created_at=created_at,
        updated_at=updated_at,
    )


def _build_image_payload(image: object | None) -> ClosetProcessingImageSnapshot | None:
    if image is None:
        return None
    return ClosetProcessingImageSnapshot(
        asset_id=getattr(image, "asset_id"),
        image_id=getattr(image, "image_id", None),
        role=getattr(image, "role"),
        position=getattr(image, "position", None),
        is_primary=getattr(image, "is_primary", False),
        mime_type=getattr(image, "mime_type"),
        width=getattr(image, "width"),
        height=getattr(image, "height"),
        url=getattr(image, "url"),
        expires_at=getattr(image, "expires_at"),
    )


def _build_image_payloads(images: Sequence[object | None]) -> list[ClosetProcessingImageSnapshot]:
    payloads: list[ClosetProcessingImageSnapshot] = []
    for image in images:
        payload = _build_image_payload(image)
        if payload is not None:
            payloads.append(payload)
    return payloads


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
        source=_enum_str(getattr(field_state, "source")),
        confidence=getattr(field_state, "confidence"),
        review_state=_enum_str(getattr(field_state, "review_state")),
        applicability_state=_enum_str(getattr(field_state, "applicability_state")),
        taxonomy_version=getattr(field_state, "taxonomy_version"),
        updated_at=getattr(field_state, "updated_at"),
    )


def _build_metadata_projection_payload(
    projection: object,
) -> ClosetMetadataProjectionSnapshot:
    return ClosetMetadataProjectionSnapshot(
        taxonomy_version=getattr(projection, "taxonomy_version"),
        title=getattr(projection, "title"),
        category=getattr(projection, "category"),
        subcategory=getattr(projection, "subcategory"),
        primary_color=getattr(projection, "primary_color"),
        secondary_colors=getattr(projection, "secondary_colors"),
        material=getattr(projection, "material"),
        pattern=getattr(projection, "pattern"),
        brand=getattr(projection, "brand"),
        style_tags=getattr(projection, "style_tags"),
        occasion_tags=getattr(projection, "occasion_tags"),
        season_tags=getattr(projection, "season_tags"),
        confirmed_at=getattr(projection, "confirmed_at"),
        updated_at=getattr(projection, "updated_at"),
    )


def build_browse_list_item_snapshot(
    snapshot: BrowseListItemSnapshot,
) -> ClosetBrowseListItemSnapshot:
    return ClosetBrowseListItemSnapshot(
        item_id=getattr(snapshot, "item_id"),
        confirmed_at=getattr(snapshot, "confirmed_at"),
        updated_at=getattr(snapshot, "updated_at"),
        title=getattr(snapshot, "title"),
        category=getattr(snapshot, "category"),
        subcategory=getattr(snapshot, "subcategory"),
        primary_color=getattr(snapshot, "primary_color"),
        secondary_colors=getattr(snapshot, "secondary_colors"),
        material=getattr(snapshot, "material"),
        pattern=getattr(snapshot, "pattern"),
        brand=getattr(snapshot, "brand"),
        display_image=_build_image_payload(getattr(snapshot, "display_image")),
        thumbnail_image=_build_image_payload(getattr(snapshot, "thumbnail_image")),
    )


def build_similarity_edge_snapshot(
    snapshot: SimilarityEdgeSnapshot,
) -> ClosetSimilarityEdgeSnapshot:
    return ClosetSimilarityEdgeSnapshot(
        edge_id=getattr(snapshot, "edge_id"),
        item_a_id=getattr(snapshot, "item_a_id"),
        item_b_id=getattr(snapshot, "item_b_id"),
        label=getattr(snapshot, "label"),
        similarity_type=getattr(snapshot, "similarity_type"),
        decision_status=getattr(snapshot, "decision_status"),
        score=getattr(snapshot, "score"),
        signals=[
            ClosetSimilaritySignalSnapshot(
                code=getattr(signal, "code"),
                label=getattr(signal, "label"),
                contribution=getattr(signal, "contribution"),
                metadata=getattr(signal, "metadata"),
            )
            for signal in getattr(snapshot, "signals")
        ],
    )


def build_similarity_list_item_snapshot(
    snapshot: SimilarityListItemSnapshot,
) -> ClosetSimilarityListItemSnapshot:
    return ClosetSimilarityListItemSnapshot(
        edge_id=getattr(snapshot, "edge_id"),
        label=getattr(snapshot, "label"),
        similarity_type=getattr(snapshot, "similarity_type"),
        decision_status=getattr(snapshot, "decision_status"),
        score=getattr(snapshot, "score"),
        signals=[
            ClosetSimilaritySignalSnapshot(
                code=getattr(signal, "code"),
                label=getattr(signal, "label"),
                contribution=getattr(signal, "contribution"),
                metadata=getattr(signal, "metadata"),
            )
            for signal in getattr(snapshot, "signals")
        ],
        other_item=build_browse_list_item_snapshot(getattr(snapshot, "other_item")),
    )


def build_similarity_list_snapshot(
    snapshot: SimilarityListSnapshot,
) -> ClosetSimilarityListResponse:
    return ClosetSimilarityListResponse(
        item_id=getattr(snapshot, "item_id"),
        similarity_status=getattr(snapshot, "similarity_status"),
        latest_run=_build_run_payload(getattr(snapshot, "latest_run")),
        items=[build_similarity_list_item_snapshot(item) for item in getattr(snapshot, "items")],
    )


def build_item_detail_snapshot(snapshot: BrowseDetailSnapshot) -> ClosetItemDetailSnapshot:
    return ClosetItemDetailSnapshot(
        item_id=getattr(snapshot, "item_id"),
        lifecycle_status=getattr(snapshot, "lifecycle_status"),
        processing_status=getattr(snapshot, "processing_status"),
        review_status=getattr(snapshot, "review_status"),
        failure_summary=getattr(snapshot, "failure_summary"),
        confirmed_at=getattr(snapshot, "confirmed_at"),
        created_at=getattr(snapshot, "created_at"),
        updated_at=getattr(snapshot, "updated_at"),
        display_image=_build_image_payload(getattr(snapshot, "display_image")),
        thumbnail_image=_build_image_payload(getattr(snapshot, "thumbnail_image")),
        original_image=_build_image_payload(getattr(snapshot, "original_image")),
        original_images=_build_image_payloads(getattr(snapshot, "original_images")),
        metadata_projection=_build_metadata_projection_payload(
            getattr(snapshot, "metadata_projection")
        ),
        field_states=[
            _build_field_state_payload(field_state)
            for field_state in getattr(snapshot, "field_states")
        ],
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
        original_images=_build_image_payloads(getattr(snapshot, "original_images")),
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
        else _build_metadata_projection_payload(getattr(snapshot, "metadata_projection")),
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
        original_images=_build_image_payloads(getattr(snapshot, "original_images")),
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
                    conflict_notes=getattr(getattr(field, "suggested_state"), "conflict_notes"),
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


def _enum_str(value: object) -> str:
    return str(getattr(value, "value", value))
