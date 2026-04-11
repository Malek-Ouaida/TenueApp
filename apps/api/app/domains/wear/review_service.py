from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.storage import ObjectStorageClient
from app.domains.wear.models import (
    WearDetectedItemStatus,
    WearContext,
    WearLogSource,
    WearLogStatus,
    WearTimePrecision,
)
from app.domains.wear.repository import WearRepository
from app.domains.wear.service import (
    RequestedWearItem,
    WearLogDetailSnapshot,
    WearService,
    WearServiceError,
    build_combination_fingerprint,
    derive_local_wear_date,
    normalize_datetime,
)


class WearReviewService:
    def __init__(
        self,
        *,
        session: Session,
        repository: WearRepository,
        storage: ObjectStorageClient,
    ) -> None:
        self.session = session
        self.repository = repository
        self.storage = storage

    def confirm_wear_log(
        self,
        *,
        wear_log_id: UUID,
        user_id: UUID,
        expected_review_version: str,
        worn_at: datetime | None,
        captured_at: datetime | None,
        timezone_name: str | None,
        context: str | None,
        vibe: str | None,
        notes: str | None,
        items: list[dict[str, object]],
        resolved_detected_items: list[dict[str, object]],
    ) -> WearLogDetailSnapshot:
        wear_service = WearService(
            session=self.session,
            repository=self.repository,
            storage=self.storage,
        )
        wear_log = self.repository.get_wear_log_for_user(wear_log_id=wear_log_id, user_id=user_id)
        if wear_log is None:
            raise WearServiceError(404, "Wear log not found.")
        if wear_log.archived_at is not None:
            raise WearServiceError(409, "Archived wear events cannot be confirmed.")
        if wear_log.status not in {WearLogStatus.NEEDS_REVIEW, WearLogStatus.FAILED}:
            raise WearServiceError(409, "Wear event is not ready for confirmation.")

        current_detail = wear_service.get_wear_log_detail(wear_log_id=wear_log.id, user_id=user_id)
        if current_detail.review_version != expected_review_version:
            raise WearServiceError(409, "The wear-event review is stale. Reload and try again.")

        normalized_items = wear_service._normalize_requested_items(items)
        confirmed_items = wear_service._get_confirmed_items_or_raise(
            user_id=user_id,
            item_ids=[item.closet_item_id for item in normalized_items],
        )

        detected_items = self.repository.list_detected_items(wear_log_id=wear_log.id)
        detected_items_by_id = {detected_item.id: detected_item for detected_item in detected_items}

        resolved_detected_item_ids: set[UUID] = set()
        for item in normalized_items:
            if item.detected_item_id is None:
                continue
            detected_item = detected_items_by_id.get(item.detected_item_id)
            if detected_item is None:
                raise WearServiceError(422, "Confirmed items must reference detected items from the same wear event.")
            resolved_detected_item_ids.add(detected_item.id)

        for resolution in resolved_detected_items:
            detected_item_id = resolution.get("detected_item_id")
            if not isinstance(detected_item_id, UUID):
                raise WearServiceError(422, "Each detected-item resolution requires a valid detected_item_id.")
            detected_item = detected_items_by_id.get(detected_item_id)
            if detected_item is None:
                raise WearServiceError(422, "Detected-item resolutions must target the same wear event.")
            status = str(resolution.get("status") or "")
            if status != WearDetectedItemStatus.EXCLUDED.value:
                raise WearServiceError(422, "Detected-item resolutions currently support only excluded status.")
            detected_item.status = WearDetectedItemStatus.EXCLUDED
            exclusion_reason = resolution.get("exclusion_reason")
            detected_item.exclusion_reason = (
                str(exclusion_reason).strip() or None if isinstance(exclusion_reason, str) else None
            )
            resolved_detected_item_ids.add(detected_item.id)

        unresolved_detected_item_ids = {
            detected_item.id
            for detected_item in detected_items
            if detected_item.status == WearDetectedItemStatus.DETECTED
        } - resolved_detected_item_ids
        if unresolved_detected_item_ids:
            raise WearServiceError(
                422,
                "All detected outfit items must be confirmed or excluded before confirming the wear event.",
            )

        for item in normalized_items:
            if item.detected_item_id is None:
                continue
            detected_items_by_id[item.detected_item_id].status = WearDetectedItemStatus.CONFIRMED
            detected_items_by_id[item.detected_item_id].exclusion_reason = None

        if timezone_name is not None:
            wear_service._validate_timezone_name(timezone_name)
            wear_log.timezone_name = timezone_name
        if worn_at is not None:
            normalized_worn_at = normalize_datetime(worn_at)
            assert normalized_worn_at is not None
            wear_log.worn_at = normalized_worn_at
            wear_log.wear_date = derive_local_wear_date(
                worn_at=normalized_worn_at,
                timezone_name=wear_log.timezone_name,
            )
            wear_log.worn_time_precision = WearTimePrecision.EXACT
        if captured_at is not None:
            wear_log.captured_at = normalize_datetime(captured_at)
        if context is not None:
            wear_log.context = WearContext(context)
        if vibe is not None:
            wear_log.vibe = vibe
        if notes is not None:
            wear_log.notes = notes

        if any(item.detected_item_id is not None for item in normalized_items):
            if any(item.detected_item_id is None for item in normalized_items):
                wear_log.source = WearLogSource.MIXED
            else:
                wear_log.source = WearLogSource.PHOTO_UPLOAD
        else:
            wear_log.source = WearLogSource.PHOTO_UPLOAD

        self.repository.replace_wear_log_items(
            wear_log_id=wear_log.id,
            items=[
                {
                    "closet_item_id": item.closet_item_id,
                    "detected_item_id": item.detected_item_id,
                    "source": (
                        item.source
                        or ("ai_matched" if item.detected_item_id is not None else "manual_override")
                    ),
                    "match_confidence": item.match_confidence,
                    "sort_index": item.sort_index,
                    "role": item.role,
                }
                for item in normalized_items
            ],
        )
        self.repository.upsert_wear_log_snapshot(
            wear_log_id=wear_log.id,
            outfit_title_snapshot=None,
            items_snapshot_json=wear_service._build_items_snapshot_json(
                normalized_items=normalized_items,
                confirmed_items=confirmed_items,
            ),
        )

        wear_log.status = WearLogStatus.CONFIRMED
        wear_log.is_confirmed = True
        wear_log.confirmed_at = datetime.now(UTC)
        wear_log.confirmed_item_count = len(normalized_items)
        wear_log.combination_fingerprint = build_combination_fingerprint(
            [item.closet_item_id for item in normalized_items]
        )
        wear_log.failure_code = None
        wear_log.failure_summary = None

        self.session.commit()
        return wear_service.get_wear_log_detail(wear_log_id=wear_log.id, user_id=user_id)
