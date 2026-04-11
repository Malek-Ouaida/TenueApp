from __future__ import annotations

import base64
import hashlib
import json
import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient
from app.domains.closet.image_processing_service import ProcessingSnapshotImage
from app.domains.closet.models import (
    ClosetItem,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetItemMetadataProjection,
    MediaAsset,
)
from app.domains.wear.models import (
    Outfit,
    WearContext,
    WearDetectedItemStatus,
    WearEventDetectedItem,
    WearEventMatchCandidate,
    WearEventPhoto,
    WearLog,
    WearLogItem,
    WearLogSnapshot,
    WearLogSource,
    WearLogStatus,
    WearProcessingRunType,
    WearTimePrecision,
    WearUploadIntentStatus,
)
from app.domains.wear.repository import WearRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestedWearItem:
    closet_item_id: UUID
    role: str | None
    sort_index: int
    detected_item_id: UUID | None = None
    source: str | None = None
    match_confidence: float | None = None


@dataclass(frozen=True)
class WearMediaSnapshot:
    asset_id: UUID
    mime_type: str
    width: int | None
    height: int | None
    url: str
    expires_at: datetime
    photo_id: UUID | None = None
    position: int | None = None


@dataclass(frozen=True)
class WearLinkedOutfitSnapshot:
    id: UUID
    title: str | None
    is_favorite: bool
    is_archived: bool


@dataclass(frozen=True)
class WearLoggedItemSnapshot:
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ProcessingSnapshotImage | None
    thumbnail_image: ProcessingSnapshotImage | None
    role: str | None
    sort_index: int
    detected_item_id: UUID | None = None


@dataclass(frozen=True)
class WearCandidateItemSnapshot:
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ProcessingSnapshotImage | None
    thumbnail_image: ProcessingSnapshotImage | None


@dataclass(frozen=True)
class WearMatchCandidateSnapshot:
    id: UUID
    closet_item_id: UUID
    rank: int
    score: float
    signals: object | None
    item: WearCandidateItemSnapshot | None


@dataclass(frozen=True)
class WearDetectedItemSnapshot:
    id: UUID
    predicted_role: str | None
    predicted_category: str | None
    predicted_subcategory: str | None
    predicted_colors: list[str]
    confidence: float | None
    bbox: dict[str, float] | None
    status: str
    exclusion_reason: str | None
    crop_image: WearMediaSnapshot | None
    candidate_matches: list[WearMatchCandidateSnapshot]


@dataclass(frozen=True)
class WearLogDetailSnapshot:
    id: UUID
    wear_date: date
    worn_at: datetime
    worn_time_precision: str
    captured_at: datetime | None
    timezone_name: str | None
    source: str
    status: str
    context: str | None
    vibe: str | None
    notes: str | None
    is_confirmed: bool
    confirmed_at: datetime | None
    archived_at: datetime | None
    item_count: int
    cover_image: WearMediaSnapshot | None
    primary_photo: WearMediaSnapshot | None
    photos: list[WearMediaSnapshot]
    linked_outfit: WearLinkedOutfitSnapshot | None
    items: list[WearLoggedItemSnapshot]
    detected_items: list[WearDetectedItemSnapshot]
    review_version: str
    can_confirm: bool
    failure_code: str | None
    failure_summary: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WearLogTimelineItemSnapshot:
    id: UUID
    wear_date: date
    worn_at: datetime
    context: str | None
    status: str
    item_count: int
    source: str
    is_confirmed: bool
    cover_image: WearMediaSnapshot | None
    outfit_title: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WearCalendarEventSnapshot:
    id: UUID
    worn_at: datetime
    status: str
    item_count: int
    cover_image: WearMediaSnapshot | None
    title: str | None
    context: str | None


@dataclass(frozen=True)
class WearCalendarDaySnapshot:
    date: date
    event_count: int
    primary_event_id: UUID | None
    primary_cover_image: WearMediaSnapshot | None
    events: list[WearCalendarEventSnapshot]
    has_wear_log: bool
    wear_log_id: UUID | None
    item_count: int
    source: str | None
    is_confirmed: bool | None
    cover_image: WearMediaSnapshot | None
    outfit_title: str | None


class WearServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class InvalidWearHistoryCursorError(ValueError):
    pass


class WearService:
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

    def create_wear_log(
        self,
        *,
        user_id: UUID,
        wear_date: date,
        worn_at: datetime | None,
        captured_at: datetime | None,
        timezone_name: str | None,
        mode: str,
        context: str | None,
        vibe: str | None,
        notes: str | None,
        items: list[dict[str, object]] | None,
        outfit_id: UUID | None,
    ) -> WearLogDetailSnapshot:
        resolved_worn_at, resolved_wear_date, worn_time_precision = resolve_event_temporal_fields(
            wear_date=wear_date,
            worn_at=worn_at,
            timezone_name=timezone_name,
        )

        if mode == WearLogSource.MANUAL_ITEMS.value:
            if items is None:
                raise WearServiceError(422, "Items are required for manual wear logging.")
            wear_log = self._create_manual_wear_log(
                user_id=user_id,
                wear_date=resolved_wear_date,
                worn_at=resolved_worn_at,
                worn_time_precision=worn_time_precision,
                captured_at=captured_at,
                timezone_name=timezone_name,
                context=context,
                vibe=vibe,
                notes=notes,
                items=items,
            )
        elif mode == WearLogSource.SAVED_OUTFIT.value:
            if outfit_id is None:
                raise WearServiceError(422, "outfit_id is required for saved-outfit wear logging.")
            wear_log = self._create_saved_outfit_wear_log(
                user_id=user_id,
                wear_date=resolved_wear_date,
                worn_at=resolved_worn_at,
                worn_time_precision=worn_time_precision,
                captured_at=captured_at,
                timezone_name=timezone_name,
                context=context,
                vibe=vibe,
                notes=notes,
                outfit_id=outfit_id,
            )
        elif mode == WearLogSource.PHOTO_UPLOAD.value:
            wear_log = self.repository.create_wear_log(
                user_id=user_id,
                wear_date=resolved_wear_date,
                worn_at=resolved_worn_at,
                worn_time_precision=worn_time_precision,
                captured_at=normalize_datetime(captured_at),
                timezone_name=timezone_name,
                outfit_id=None,
                source=WearLogSource.PHOTO_UPLOAD,
                status=WearLogStatus.DRAFT,
                context=WearContext(context) if context is not None else None,
                vibe=vibe,
                notes=notes,
                is_confirmed=False,
                confirmed_at=None,
                confirmed_item_count=0,
                combination_fingerprint=None,
            )
        else:
            raise WearServiceError(422, "Unsupported wear-log mode.")

        self.session.commit()
        return self.get_wear_log_detail(wear_log_id=wear_log.id, user_id=user_id)

    def get_wear_log_detail(
        self,
        *,
        wear_log_id: UUID,
        user_id: UUID,
    ) -> WearLogDetailSnapshot:
        wear_log = self._get_wear_log_or_raise(wear_log_id=wear_log_id, user_id=user_id)
        return self._build_wear_log_detail(wear_log=wear_log, user_id=user_id)

    def list_wear_logs(
        self,
        *,
        user_id: UUID,
        cursor: str | None,
        limit: int,
        wear_date: date | None = None,
        status: str | None = None,
        include_archived: bool = False,
    ) -> tuple[list[WearLogTimelineItemSnapshot], str | None]:
        cursor_worn_at, cursor_created_at, cursor_wear_log_id = decode_history_cursor(cursor)
        try:
            status_filter = WearLogStatus(status) if status is not None else None
        except ValueError as exc:
            raise WearServiceError(422, "status must be a valid wear-event status.") from exc
        wear_logs = self.repository.list_wear_logs(
            user_id=user_id,
            cursor_worn_at=cursor_worn_at,
            cursor_created_at=cursor_created_at,
            cursor_wear_log_id=cursor_wear_log_id,
            limit=limit + 1,
            wear_date=wear_date,
            status=status_filter,
            include_archived=include_archived,
        )
        has_more = len(wear_logs) > limit
        visible_logs = wear_logs[:limit]

        detail_context = self._build_detail_context(
            wear_logs=visible_logs,
            user_id=user_id,
            include_detected_items=False,
        )

        items = [
            self._build_timeline_item(
                wear_log=wear_log,
                snapshot_items=detail_context.snapshot_items_by_log.get(wear_log.id, []),
                snapshot=detail_context.snapshots_by_log.get(wear_log.id),
                outfits_by_id=detail_context.outfits_by_id,
                photo_assets_by_photo_id=detail_context.photo_assets_by_photo_id,
                item_assets_by_id=detail_context.item_assets_by_id,
                photos_by_log=detail_context.photos_by_log,
            )
            for wear_log in visible_logs
        ]

        next_cursor = None
        if has_more and visible_logs:
            last_wear_log = visible_logs[-1]
            next_cursor = encode_history_cursor(
                worn_at=last_wear_log.worn_at,
                created_at=last_wear_log.created_at,
                wear_log_id=last_wear_log.id,
            )
        return items, next_cursor

    def update_wear_log(
        self,
        *,
        wear_log_id: UUID,
        user_id: UUID,
        wear_date: date | None = None,
        worn_at: datetime | None = None,
        captured_at: datetime | None = None,
        timezone_name: str | None = None,
        context: str | None = None,
        vibe: str | None = None,
        notes: str | None = None,
        items: list[dict[str, object]] | None = None,
        field_names: set[str],
    ) -> WearLogDetailSnapshot:
        wear_log = self._get_wear_log_or_raise(wear_log_id=wear_log_id, user_id=user_id)

        if not field_names:
            return self.get_wear_log_detail(wear_log_id=wear_log_id, user_id=user_id)

        if "timezone_name" in field_names:
            self._validate_timezone_name(timezone_name)
            wear_log.timezone_name = timezone_name

        if "worn_at" in field_names or "wear_date" in field_names:
            target_timezone = timezone_name if "timezone_name" in field_names else wear_log.timezone_name
            resolved_worn_at, resolved_wear_date, worn_time_precision = resolve_event_temporal_fields(
                wear_date=wear_date or wear_log.wear_date,
                worn_at=worn_at if "worn_at" in field_names else move_worn_at_to_new_date(
                    worn_at=wear_log.worn_at,
                    new_wear_date=wear_date or wear_log.wear_date,
                    timezone_name=target_timezone,
                ),
                timezone_name=target_timezone,
            )
            wear_log.worn_at = resolved_worn_at
            wear_log.wear_date = resolved_wear_date
            wear_log.worn_time_precision = worn_time_precision

        if "captured_at" in field_names:
            wear_log.captured_at = normalize_datetime(captured_at)

        if "context" in field_names:
            wear_log.context = WearContext(context) if context is not None else None

        if "vibe" in field_names:
            wear_log.vibe = vibe

        if "notes" in field_names:
            wear_log.notes = notes

        if "items" in field_names:
            if items is None:
                raise WearServiceError(422, "Items cannot be null when replacing a wear log.")
            if wear_log.status != WearLogStatus.CONFIRMED:
                raise WearServiceError(
                    409,
                    "Wear-event items can only be replaced through review confirmation until the event is confirmed.",
                )
            normalized_items = self._normalize_requested_items(items)
            confirmed_items = self._get_confirmed_items_or_raise(
                user_id=user_id,
                item_ids=[item.closet_item_id for item in normalized_items],
            )
            self.repository.replace_wear_log_items(
                wear_log_id=wear_log.id,
                items=[
                    {
                        "closet_item_id": item.closet_item_id,
                        "detected_item_id": item.detected_item_id,
                        "source": item.source or "manual_override",
                        "match_confidence": item.match_confidence,
                        "sort_index": item.sort_index,
                        "role": item.role,
                    }
                    for item in normalized_items
                ],
            )
            wear_log.confirmed_item_count = len(normalized_items)
            wear_log.combination_fingerprint = build_combination_fingerprint(
                [item.closet_item_id for item in normalized_items]
            )
            if wear_log.outfit_id is not None or wear_log.source in {
                WearLogSource.SAVED_OUTFIT,
                WearLogSource.PHOTO_UPLOAD,
                WearLogSource.PHOTO_DETECTED,
                WearLogSource.MIXED,
            }:
                wear_log.source = WearLogSource.MIXED
            else:
                wear_log.source = WearLogSource.MANUAL_ITEMS
            wear_log.outfit_id = None
            self.repository.upsert_wear_log_snapshot(
                wear_log_id=wear_log.id,
                outfit_title_snapshot=None,
                items_snapshot_json=self._build_items_snapshot_json(
                    normalized_items=normalized_items,
                    confirmed_items=confirmed_items,
                ),
            )

        self.session.commit()
        return self.get_wear_log_detail(wear_log_id=wear_log.id, user_id=user_id)

    def delete_wear_log(
        self,
        *,
        wear_log_id: UUID,
        user_id: UUID,
    ) -> None:
        wear_log = self._get_wear_log_or_raise(wear_log_id=wear_log_id, user_id=user_id)
        self.repository.delete_wear_log(wear_log=wear_log)
        self.session.commit()

    def get_calendar(
        self,
        *,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[WearCalendarDaySnapshot]:
        self._validate_calendar_range(start_date=start_date, end_date=end_date)
        wear_logs = self.repository.list_wear_logs_in_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            confirmed_only=True,
        )
        detail_context = self._build_detail_context(
            wear_logs=wear_logs,
            user_id=user_id,
            include_detected_items=False,
        )
        logs_by_date: dict[date, list[WearLog]] = defaultdict(list)
        for wear_log in wear_logs:
            logs_by_date[wear_log.wear_date].append(wear_log)

        days: list[WearCalendarDaySnapshot] = []
        current_date = start_date
        while current_date <= end_date:
            day_logs = logs_by_date.get(current_date, [])
            sorted_day_logs = sorted(
                day_logs,
                key=lambda value: (value.worn_at, value.created_at, value.id),
                reverse=True,
            )
            day_events = [
                self._build_calendar_event_snapshot(
                    wear_log=wear_log,
                    snapshot_items=detail_context.snapshot_items_by_log.get(wear_log.id, []),
                    snapshot=detail_context.snapshots_by_log.get(wear_log.id),
                    outfits_by_id=detail_context.outfits_by_id,
                    photo_assets_by_photo_id=detail_context.photo_assets_by_photo_id,
                    item_assets_by_id=detail_context.item_assets_by_id,
                    photos_by_log=detail_context.photos_by_log,
                )
                for wear_log in sorted_day_logs
            ]
            primary_event = day_events[0] if day_events else None
            primary_log = sorted_day_logs[0] if sorted_day_logs else None
            days.append(
                WearCalendarDaySnapshot(
                    date=current_date,
                    event_count=len(day_events),
                    primary_event_id=primary_event.id if primary_event is not None else None,
                    primary_cover_image=(
                        primary_event.cover_image if primary_event is not None else None
                    ),
                    events=day_events,
                    has_wear_log=bool(day_events),
                    wear_log_id=primary_event.id if primary_event is not None else None,
                    item_count=primary_event.item_count if primary_event is not None else 0,
                    source=primary_log.source.value if primary_log is not None else None,
                    is_confirmed=primary_log.is_confirmed if primary_log is not None else None,
                    cover_image=primary_event.cover_image if primary_event is not None else None,
                    outfit_title=primary_event.title if primary_event is not None else None,
                )
            )
            current_date += timedelta(days=1)
        return days

    def _create_manual_wear_log(
        self,
        *,
        user_id: UUID,
        wear_date: date,
        worn_at: datetime,
        worn_time_precision: WearTimePrecision,
        captured_at: datetime | None,
        timezone_name: str | None,
        context: str | None,
        vibe: str | None,
        notes: str | None,
        items: list[dict[str, object]],
    ) -> WearLog:
        normalized_items = self._normalize_requested_items(items)
        confirmed_items = self._get_confirmed_items_or_raise(
            user_id=user_id,
            item_ids=[item.closet_item_id for item in normalized_items],
        )
        confirmed_at = datetime.now(UTC)

        wear_log = self.repository.create_wear_log(
            user_id=user_id,
            wear_date=wear_date,
            worn_at=worn_at,
            worn_time_precision=worn_time_precision,
            captured_at=captured_at,
            timezone_name=timezone_name,
            outfit_id=None,
            source=WearLogSource.MANUAL_ITEMS,
            status=WearLogStatus.CONFIRMED,
            context=WearContext(context) if context is not None else None,
            vibe=vibe,
            notes=notes,
            is_confirmed=True,
            confirmed_at=confirmed_at,
            confirmed_item_count=len(normalized_items),
            combination_fingerprint=build_combination_fingerprint(
                [item.closet_item_id for item in normalized_items]
            ),
        )
        self.repository.create_wear_log_items(
            wear_log_id=wear_log.id,
            items=[
                {
                    "closet_item_id": item.closet_item_id,
                    "detected_item_id": item.detected_item_id,
                    "source": item.source or "manual",
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
            items_snapshot_json=self._build_items_snapshot_json(
                normalized_items=normalized_items,
                confirmed_items=confirmed_items,
            ),
        )
        return wear_log

    def _create_saved_outfit_wear_log(
        self,
        *,
        user_id: UUID,
        wear_date: date,
        worn_at: datetime,
        worn_time_precision: WearTimePrecision,
        captured_at: datetime | None,
        timezone_name: str | None,
        context: str | None,
        vibe: str | None,
        notes: str | None,
        outfit_id: UUID,
    ) -> WearLog:
        outfit = self._get_loggable_outfit_or_raise(outfit_id=outfit_id, user_id=user_id)
        outfit_items = self.repository.list_outfit_items(outfit_id=outfit.id)
        if not outfit_items:
            raise WearServiceError(409, "Outfit does not contain any items to log.")

        normalized_items = [
            RequestedWearItem(
                closet_item_id=item.closet_item_id,
                role=item.role.value if item.role is not None else None,
                sort_index=item.sort_index,
                source="from_outfit",
            )
            for item in outfit_items
        ]
        confirmed_items = self._get_confirmed_items_or_raise(
            user_id=user_id,
            item_ids=[item.closet_item_id for item in normalized_items],
        )
        confirmed_at = datetime.now(UTC)

        wear_log = self.repository.create_wear_log(
            user_id=user_id,
            wear_date=wear_date,
            worn_at=worn_at,
            worn_time_precision=worn_time_precision,
            captured_at=captured_at,
            timezone_name=timezone_name,
            outfit_id=outfit.id,
            source=WearLogSource.SAVED_OUTFIT,
            status=WearLogStatus.CONFIRMED,
            context=WearContext(context) if context is not None else None,
            vibe=vibe,
            notes=notes,
            is_confirmed=True,
            confirmed_at=confirmed_at,
            confirmed_item_count=len(normalized_items),
            combination_fingerprint=build_combination_fingerprint(
                [item.closet_item_id for item in normalized_items]
            ),
        )
        self.repository.create_wear_log_items(
            wear_log_id=wear_log.id,
            items=[
                {
                    "closet_item_id": item.closet_item_id,
                    "detected_item_id": item.detected_item_id,
                    "source": item.source or "from_outfit",
                    "match_confidence": item.match_confidence,
                    "sort_index": item.sort_index,
                    "role": item.role,
                }
                for item in normalized_items
            ],
        )
        self.repository.upsert_wear_log_snapshot(
            wear_log_id=wear_log.id,
            outfit_title_snapshot=outfit.title,
            items_snapshot_json=self._build_items_snapshot_json(
                normalized_items=normalized_items,
                confirmed_items=confirmed_items,
            ),
        )
        return wear_log

    def _get_wear_log_or_raise(self, *, wear_log_id: UUID, user_id: UUID) -> WearLog:
        wear_log = self.repository.get_wear_log_for_user(wear_log_id=wear_log_id, user_id=user_id)
        if wear_log is None:
            raise WearServiceError(404, "Wear log not found.")
        return wear_log

    def _get_loggable_outfit_or_raise(self, *, outfit_id: UUID, user_id: UUID) -> Outfit:
        outfit = self.repository.get_outfit_for_user(outfit_id=outfit_id, user_id=user_id)
        if outfit is None:
            raise WearServiceError(404, "Outfit not found.")
        if outfit.archived_at is not None:
            raise WearServiceError(409, "Archived outfits cannot be used for wear logging.")
        return outfit

    def _normalize_requested_items(
        self,
        items: list[dict[str, object]],
    ) -> list[RequestedWearItem]:
        seen_item_ids: set[UUID] = set()
        sortable_items: list[tuple[int, int, RequestedWearItem]] = []

        for position, item in enumerate(items):
            closet_item_id_raw = item["closet_item_id"]
            if not isinstance(closet_item_id_raw, UUID):
                raise WearServiceError(
                    422,
                    "Each wear-event item must include a valid closet_item_id.",
                )
            closet_item_id = closet_item_id_raw
            if closet_item_id in seen_item_ids:
                raise WearServiceError(
                    422,
                    "Each closet item can appear at most once in a single wear log.",
                )
            seen_item_ids.add(closet_item_id)

            provided_sort_index = item.get("sort_index")
            detected_item_id_raw = item.get("detected_item_id")
            detected_item_id = detected_item_id_raw if isinstance(detected_item_id_raw, UUID) else None
            role_raw = item.get("role")
            role = str(role_raw) if isinstance(role_raw, str) else None
            source_raw = item.get("source")
            source = str(source_raw) if isinstance(source_raw, str) else None
            match_confidence_raw = item.get("match_confidence")
            match_confidence = (
                float(match_confidence_raw)
                if isinstance(match_confidence_raw, (float, int))
                else None
            )
            sortable_items.append(
                (
                    provided_sort_index if isinstance(provided_sort_index, int) else position,
                    position,
                    RequestedWearItem(
                        closet_item_id=closet_item_id,
                        role=role,
                        sort_index=0,
                        detected_item_id=detected_item_id,
                        source=source,
                        match_confidence=match_confidence,
                    ),
                )
            )

        normalized_items: list[RequestedWearItem] = []
        sorted_items = sorted(sortable_items, key=lambda value: value[:2])
        for final_index, (_, _, requested_item) in enumerate(sorted_items):
            normalized_items.append(
                RequestedWearItem(
                    closet_item_id=requested_item.closet_item_id,
                    role=requested_item.role,
                    sort_index=final_index,
                    detected_item_id=requested_item.detected_item_id,
                    source=requested_item.source,
                    match_confidence=requested_item.match_confidence,
                )
            )
        return normalized_items

    def _get_confirmed_items_or_raise(
        self,
        *,
        user_id: UUID,
        item_ids: list[UUID],
    ) -> dict[UUID, tuple[ClosetItem, ClosetItemMetadataProjection]]:
        confirmed_items = self.repository.get_confirmed_closet_items_with_projections_for_user(
            item_ids=item_ids,
            user_id=user_id,
        )
        if len(confirmed_items) != len(item_ids):
            raise WearServiceError(
                404,
                "One or more closet items could not be found for confirmed wear logging.",
            )
        return confirmed_items

    def _build_wear_log_detail(
        self,
        *,
        wear_log: WearLog,
        user_id: UUID,
    ) -> WearLogDetailSnapshot:
        detail_context = self._build_detail_context(
            wear_logs=[wear_log],
            user_id=user_id,
            include_detected_items=True,
        )
        snapshot_items = detail_context.snapshot_items_by_log.get(wear_log.id, [])
        items = [
            self._build_logged_item_snapshot(item, detail_context.item_assets_by_id)
            for item in snapshot_items
        ]
        linked_outfit = None
        if wear_log.outfit_id is not None:
            linked_outfit = self._build_linked_outfit_snapshot(
                detail_context.outfits_by_id.get(wear_log.outfit_id)
            )
        photos = [
            self._build_photo_snapshot(
                photo=photo,
                photo_assets_by_photo_id=detail_context.photo_assets_by_photo_id,
            )
            for photo in detail_context.photos_by_log.get(wear_log.id, [])
        ]
        primary_photo = None
        if wear_log.primary_photo_id is not None:
            primary_photo = next(
                (photo for photo in photos if photo.photo_id == wear_log.primary_photo_id),
                None,
            )
        detected_items = detail_context.detected_items_by_log.get(wear_log.id, [])
        detected_item_ids = [item.id for item in detected_items]
        candidate_map = detail_context.candidates_by_detected_item
        review_version = self._build_review_version(
            wear_log=wear_log,
            confirmed_items=items,
            detected_items=detected_items,
            candidate_map=candidate_map,
        )
        return WearLogDetailSnapshot(
            id=wear_log.id,
            wear_date=wear_log.wear_date,
            worn_at=normalize_datetime(wear_log.worn_at),
            worn_time_precision=wear_log.worn_time_precision.value,
            captured_at=normalize_datetime(wear_log.captured_at),
            timezone_name=wear_log.timezone_name,
            source=wear_log.source.value,
            status=wear_log.status.value,
            context=wear_log.context.value if wear_log.context is not None else None,
            vibe=wear_log.vibe,
            notes=wear_log.notes,
            is_confirmed=wear_log.is_confirmed,
            confirmed_at=normalize_datetime(wear_log.confirmed_at),
            archived_at=normalize_datetime(wear_log.archived_at),
            item_count=len(items),
            cover_image=self._build_cover_image(
                wear_log=wear_log,
                snapshot_items=snapshot_items,
                photo_assets_by_photo_id=detail_context.photo_assets_by_photo_id,
                item_assets_by_id=detail_context.item_assets_by_id,
                photos_by_log=detail_context.photos_by_log,
            ),
            primary_photo=primary_photo,
            photos=photos,
            linked_outfit=linked_outfit,
            items=items,
            detected_items=[
                self._build_detected_item_snapshot(
                    detected_item=detected_item,
                    candidate_matches=candidate_map.get(detected_item.id, []),
                    candidate_items_by_id=detail_context.candidate_items_by_id,
                    candidate_item_assets_by_id=detail_context.candidate_item_assets_by_id,
                    crop_assets_by_id=detail_context.crop_assets_by_id,
                )
                for detected_item in detected_items
            ],
            review_version=review_version,
            can_confirm=wear_log.status in {WearLogStatus.NEEDS_REVIEW, WearLogStatus.FAILED},
            failure_code=wear_log.failure_code,
            failure_summary=wear_log.failure_summary,
            created_at=normalize_datetime(wear_log.created_at),
            updated_at=normalize_datetime(wear_log.updated_at),
        )

    def _build_detail_context(
        self,
        *,
        wear_logs: list[WearLog],
        user_id: UUID,
        include_detected_items: bool,
    ) -> "DetailContext":
        wear_log_ids = [wear_log.id for wear_log in wear_logs]
        snapshots_by_log = self.repository.get_wear_log_snapshots_for_logs(wear_log_ids=wear_log_ids)
        snapshot_items_by_log = {
            wear_log_id: self._snapshot_items_from_json(snapshot.items_snapshot_json)
            for wear_log_id, snapshot in snapshots_by_log.items()
        }

        for wear_log in wear_logs:
            if wear_log.id in snapshot_items_by_log:
                continue
            snapshot_items_by_log[wear_log.id] = self._get_snapshot_items_for_log(
                wear_log=wear_log,
                user_id=user_id,
            )

        item_assets_by_id = self.repository.get_media_assets_by_ids(
            asset_ids=self._collect_snapshot_asset_ids(snapshot_items_by_log.values())
        )
        outfits_by_id = self.repository.get_outfits_for_user(
            outfit_ids=[wear_log.outfit_id for wear_log in wear_logs if wear_log.outfit_id is not None],
            user_id=user_id,
        )
        photos_by_log = self.repository.list_active_wear_event_photos_for_logs(wear_log_ids=wear_log_ids)
        photo_asset_ids = [
            asset_id
            for photos in photos_by_log.values()
            for photo in photos
            for asset_id in (photo.asset_id, photo.thumbnail_asset_id)
            if asset_id is not None
        ]
        photo_assets = self.repository.get_media_assets_by_ids(asset_ids=photo_asset_ids)
        photo_assets_by_photo_id = {
            photo.id: {
                "asset": photo_assets.get(photo.asset_id),
                "thumbnail_asset": (
                    photo_assets.get(photo.thumbnail_asset_id) if photo.thumbnail_asset_id else None
                ),
            }
            for photos in photos_by_log.values()
            for photo in photos
        }

        detected_items_by_log: dict[UUID, list[WearEventDetectedItem]] = {}
        candidates_by_detected_item: dict[UUID, list[WearEventMatchCandidate]] = {}
        candidate_items_by_id: dict[UUID, tuple[ClosetItem, ClosetItemMetadataProjection]] = {}
        candidate_item_assets_by_id: dict[UUID, MediaAsset] = {}
        crop_assets_by_id: dict[UUID, MediaAsset] = {}

        if include_detected_items:
            detected_items_by_log = self.repository.list_detected_items_for_logs(wear_log_ids=wear_log_ids)
            detected_item_ids = [
                detected_item.id
                for detected_items in detected_items_by_log.values()
                for detected_item in detected_items
            ]
            candidates_by_detected_item = self.repository.list_match_candidates_for_detected_items(
                detected_item_ids=detected_item_ids
            )
            candidate_item_ids = sorted(
                {
                    candidate.closet_item_id
                    for candidates in candidates_by_detected_item.values()
                    for candidate in candidates
                }
            )
            candidate_items_by_id = self.repository.get_closet_items_with_projections_for_user(
                item_ids=candidate_item_ids,
                user_id=user_id,
            )
            candidate_images_by_item = self.repository.list_active_image_assets_for_items(
                closet_item_ids=list(candidate_items_by_id.keys()),
                roles=[
                    ClosetItemImageRole.ORIGINAL,
                    ClosetItemImageRole.PROCESSED,
                    ClosetItemImageRole.THUMBNAIL,
                ],
            )
            candidate_item_assets_by_id = self.repository.get_media_assets_by_ids(
                asset_ids=[
                    asset.id
                    for images_by_role in candidate_images_by_item.values()
                    for _, asset in images_by_role.values()
                ]
            )
            crop_asset_ids = [
                detected_item.crop_asset_id
                for detected_items in detected_items_by_log.values()
                for detected_item in detected_items
                if detected_item.crop_asset_id is not None
            ]
            crop_assets_by_id = self.repository.get_media_assets_by_ids(asset_ids=crop_asset_ids)

        return DetailContext(
            snapshots_by_log=snapshots_by_log,
            snapshot_items_by_log=snapshot_items_by_log,
            outfits_by_id=outfits_by_id,
            photos_by_log=photos_by_log,
            photo_assets_by_photo_id=photo_assets_by_photo_id,
            item_assets_by_id=item_assets_by_id,
            detected_items_by_log=detected_items_by_log,
            candidates_by_detected_item=candidates_by_detected_item,
            candidate_items_by_id=candidate_items_by_id,
            candidate_item_assets_by_id=candidate_item_assets_by_id,
            crop_assets_by_id=crop_assets_by_id,
        )

    def _build_items_snapshot_json(
        self,
        *,
        normalized_items: list[RequestedWearItem],
        confirmed_items: dict[UUID, tuple[ClosetItem, ClosetItemMetadataProjection]],
    ) -> list[dict[str, object]]:
        item_ids = [item.closet_item_id for item in normalized_items]
        images_by_item = self.repository.list_active_image_assets_for_items(
            closet_item_ids=item_ids,
            roles=[
                ClosetItemImageRole.ORIGINAL,
                ClosetItemImageRole.PROCESSED,
                ClosetItemImageRole.THUMBNAIL,
            ],
        )
        snapshot_items: list[dict[str, object]] = []
        for item in normalized_items:
            closet_item, projection = confirmed_items[item.closet_item_id]
            images_by_role = images_by_item.get(item.closet_item_id, {})
            display_image = images_by_role.get(ClosetItemImageRole.PROCESSED) or images_by_role.get(
                ClosetItemImageRole.ORIGINAL
            )
            thumbnail_image = images_by_role.get(ClosetItemImageRole.THUMBNAIL)
            snapshot_items.append(
                {
                    "closet_item_id": str(item.closet_item_id),
                    "detected_item_id": (
                        str(item.detected_item_id) if item.detected_item_id is not None else None
                    ),
                    "title": projection.title,
                    "category": projection.category,
                    "subcategory": projection.subcategory,
                    "primary_color": projection.primary_color,
                    "role": item.role,
                    "sort_index": item.sort_index,
                    "display_image": self._serialize_snapshot_image(
                        display_image,
                        primary_image_id=closet_item.primary_image_id,
                    ),
                    "thumbnail_image": self._serialize_snapshot_image(
                        thumbnail_image,
                        primary_image_id=closet_item.primary_image_id,
                    ),
                }
            )
        return snapshot_items

    def _get_snapshot_items_for_log(
        self,
        *,
        wear_log: WearLog,
        user_id: UUID,
    ) -> list[dict[str, object]]:
        snapshot = self.repository.get_wear_log_snapshot(wear_log_id=wear_log.id)
        if snapshot is not None:
            return self._snapshot_items_from_json(snapshot.items_snapshot_json)

        wear_log_items = self.repository.list_wear_log_items(wear_log_id=wear_log.id)
        if not wear_log_items:
            return []
        normalized_items = [
            RequestedWearItem(
                closet_item_id=item.closet_item_id,
                role=item.role.value if item.role is not None else None,
                sort_index=item.sort_index,
                detected_item_id=item.detected_item_id,
                source=item.source.value if item.source is not None else None,
                match_confidence=item.match_confidence,
            )
            for item in wear_log_items
        ]
        confirmed_items = self._get_confirmed_items_or_raise(
            user_id=user_id,
            item_ids=[item.closet_item_id for item in normalized_items],
        )
        return self._build_items_snapshot_json(
            normalized_items=normalized_items,
            confirmed_items=confirmed_items,
        )

    def _build_logged_item_snapshot(
        self,
        snapshot_item: dict[str, object],
        assets_by_id: dict[UUID, MediaAsset],
    ) -> WearLoggedItemSnapshot:
        detected_item_id_raw = snapshot_item.get("detected_item_id")
        return WearLoggedItemSnapshot(
            closet_item_id=UUID(str(snapshot_item["closet_item_id"])),
            title=self._get_optional_str(snapshot_item, "title"),
            category=self._get_optional_str(snapshot_item, "category"),
            subcategory=self._get_optional_str(snapshot_item, "subcategory"),
            primary_color=self._get_optional_str(snapshot_item, "primary_color"),
            display_image=self._build_processing_image_from_snapshot(
                snapshot_item.get("display_image"),
                assets_by_id,
            ),
            thumbnail_image=self._build_processing_image_from_snapshot(
                snapshot_item.get("thumbnail_image"),
                assets_by_id,
            ),
            role=self._get_optional_str(snapshot_item, "role"),
            sort_index=self._coerce_int(snapshot_item.get("sort_index"), default=0),
            detected_item_id=(
                UUID(detected_item_id_raw)
                if isinstance(detected_item_id_raw, str)
                else None
            ),
        )

    def _build_timeline_item(
        self,
        *,
        wear_log: WearLog,
        snapshot_items: list[dict[str, object]],
        snapshot: WearLogSnapshot | None,
        outfits_by_id: dict[UUID, Outfit],
        photo_assets_by_photo_id: dict[UUID, dict[str, MediaAsset | None]],
        item_assets_by_id: dict[UUID, MediaAsset],
        photos_by_log: dict[UUID, list[WearEventPhoto]],
    ) -> WearLogTimelineItemSnapshot:
        snapshot_title = snapshot.outfit_title_snapshot if snapshot is not None else None
        return WearLogTimelineItemSnapshot(
            id=wear_log.id,
            wear_date=wear_log.wear_date,
            worn_at=normalize_datetime(wear_log.worn_at),
            context=wear_log.context.value if wear_log.context is not None else None,
            status=wear_log.status.value,
            item_count=len(snapshot_items),
            source=wear_log.source.value,
            is_confirmed=wear_log.is_confirmed,
            cover_image=self._build_cover_image(
                wear_log=wear_log,
                snapshot_items=snapshot_items,
                photo_assets_by_photo_id=photo_assets_by_photo_id,
                item_assets_by_id=item_assets_by_id,
                photos_by_log=photos_by_log,
            ),
            outfit_title=self._get_outfit_title_for_log(
                wear_log=wear_log,
                snapshot=snapshot,
                outfits_by_id=outfits_by_id,
                snapshot_title=snapshot_title,
            ),
            created_at=normalize_datetime(wear_log.created_at),
            updated_at=normalize_datetime(wear_log.updated_at),
        )

    def _build_calendar_event_snapshot(
        self,
        *,
        wear_log: WearLog,
        snapshot_items: list[dict[str, object]],
        snapshot: WearLogSnapshot | None,
        outfits_by_id: dict[UUID, Outfit],
        photo_assets_by_photo_id: dict[UUID, dict[str, MediaAsset | None]],
        item_assets_by_id: dict[UUID, MediaAsset],
        photos_by_log: dict[UUID, list[WearEventPhoto]],
    ) -> WearCalendarEventSnapshot:
        return WearCalendarEventSnapshot(
            id=wear_log.id,
            worn_at=normalize_datetime(wear_log.worn_at),
            status=wear_log.status.value,
            item_count=len(snapshot_items),
            cover_image=self._build_cover_image(
                wear_log=wear_log,
                snapshot_items=snapshot_items,
                photo_assets_by_photo_id=photo_assets_by_photo_id,
                item_assets_by_id=item_assets_by_id,
                photos_by_log=photos_by_log,
            ),
            title=self._get_outfit_title_for_log(
                wear_log=wear_log,
                snapshot=snapshot,
                outfits_by_id=outfits_by_id,
            ),
            context=wear_log.context.value if wear_log.context is not None else None,
        )

    def _build_linked_outfit_snapshot(
        self,
        outfit: Outfit | None,
    ) -> WearLinkedOutfitSnapshot | None:
        if outfit is None:
            return None
        return WearLinkedOutfitSnapshot(
            id=outfit.id,
            title=outfit.title,
            is_favorite=outfit.is_favorite,
            is_archived=outfit.archived_at is not None,
        )

    def _get_outfit_title_for_log(
        self,
        *,
        wear_log: WearLog,
        snapshot: WearLogSnapshot | None,
        outfits_by_id: dict[UUID, Outfit],
        snapshot_title: str | None = None,
    ) -> str | None:
        if snapshot_title is None and snapshot is not None:
            snapshot_title = getattr(snapshot, "outfit_title_snapshot", None)
        if snapshot_title:
            return snapshot_title
        if wear_log.outfit_id is None:
            return None
        outfit = outfits_by_id.get(wear_log.outfit_id)
        return outfit.title if outfit is not None else None

    def _build_cover_image(
        self,
        *,
        wear_log: WearLog,
        snapshot_items: list[dict[str, object]],
        photo_assets_by_photo_id: dict[UUID, dict[str, MediaAsset | None]],
        item_assets_by_id: dict[UUID, MediaAsset],
        photos_by_log: dict[UUID, list[WearEventPhoto]],
    ) -> WearMediaSnapshot | None:
        if wear_log.primary_photo_id is not None:
            primary_photo = next(
                (
                    photo
                    for photo in photos_by_log.get(wear_log.id, [])
                    if photo.id == wear_log.primary_photo_id
                ),
                None,
            )
            if primary_photo is not None:
                snapshot = self._build_photo_snapshot(
                    photo=primary_photo,
                    photo_assets_by_photo_id=photo_assets_by_photo_id,
                )
                if snapshot is not None:
                    return snapshot

        for snapshot_item in snapshot_items:
            cover_image = self._build_media_from_snapshot_image(
                snapshot_item.get("display_image"),
                item_assets_by_id,
            )
            if cover_image is not None:
                return cover_image
            cover_image = self._build_media_from_snapshot_image(
                snapshot_item.get("thumbnail_image"),
                item_assets_by_id,
            )
            if cover_image is not None:
                return cover_image
        return None

    def _build_photo_snapshot(
        self,
        *,
        photo: WearEventPhoto,
        photo_assets_by_photo_id: dict[UUID, dict[str, MediaAsset | None]],
    ) -> WearMediaSnapshot | None:
        asset_record = photo_assets_by_photo_id.get(photo.id)
        if asset_record is None:
            return None
        asset = asset_record.get("thumbnail_asset") or asset_record.get("asset")
        if asset is None:
            return None
        return self._build_private_media_snapshot(
            asset=asset,
            photo_id=photo.id,
            position=photo.position,
        )

    def _build_detected_item_snapshot(
        self,
        *,
        detected_item: WearEventDetectedItem,
        candidate_matches: list[WearEventMatchCandidate],
        candidate_items_by_id: dict[UUID, tuple[ClosetItem, ClosetItemMetadataProjection]],
        candidate_item_assets_by_id: dict[UUID, MediaAsset],
        crop_assets_by_id: dict[UUID, MediaAsset],
    ) -> WearDetectedItemSnapshot:
        return WearDetectedItemSnapshot(
            id=detected_item.id,
            predicted_role=(
                detected_item.predicted_role.value
                if detected_item.predicted_role is not None
                else None
            ),
            predicted_category=detected_item.predicted_category,
            predicted_subcategory=detected_item.predicted_subcategory,
            predicted_colors=list(detected_item.predicted_colors_json or []),
            confidence=detected_item.confidence,
            bbox=detected_item.bbox_json,
            status=detected_item.status.value,
            exclusion_reason=detected_item.exclusion_reason,
            crop_image=(
                self._build_private_media_snapshot(asset=crop_assets_by_id[detected_item.crop_asset_id])
                if detected_item.crop_asset_id is not None
                and detected_item.crop_asset_id in crop_assets_by_id
                else None
            ),
            candidate_matches=[
                self._build_match_candidate_snapshot(
                    candidate=candidate,
                    item_record=candidate_items_by_id.get(candidate.closet_item_id),
                    assets_by_id=candidate_item_assets_by_id,
                )
                for candidate in candidate_matches
            ],
        )

    def _build_match_candidate_snapshot(
        self,
        *,
        candidate: WearEventMatchCandidate,
        item_record: tuple[ClosetItem, ClosetItemMetadataProjection] | None,
        assets_by_id: dict[UUID, MediaAsset],
    ) -> WearMatchCandidateSnapshot:
        item_snapshot = None
        if item_record is not None:
            closet_item, projection = item_record
            images_by_item = self.repository.list_active_image_assets_for_items(
                closet_item_ids=[closet_item.id],
                roles=[
                    ClosetItemImageRole.ORIGINAL,
                    ClosetItemImageRole.PROCESSED,
                    ClosetItemImageRole.THUMBNAIL,
                ],
            )
            images_by_role = images_by_item.get(closet_item.id, {})
            display_image = images_by_role.get(ClosetItemImageRole.PROCESSED) or images_by_role.get(
                ClosetItemImageRole.ORIGINAL
            )
            thumbnail_image = images_by_role.get(ClosetItemImageRole.THUMBNAIL)
            if display_image is not None:
                assets_by_id.update({display_image[1].id: display_image[1]})
            if thumbnail_image is not None:
                assets_by_id.update({thumbnail_image[1].id: thumbnail_image[1]})
            item_snapshot = WearCandidateItemSnapshot(
                closet_item_id=closet_item.id,
                title=projection.title,
                category=projection.category,
                subcategory=projection.subcategory,
                primary_color=projection.primary_color,
                display_image=self._build_processing_image_from_image_record(
                    display_image,
                    primary_image_id=closet_item.primary_image_id,
                ),
                thumbnail_image=self._build_processing_image_from_image_record(
                    thumbnail_image,
                    primary_image_id=closet_item.primary_image_id,
                ),
            )
        return WearMatchCandidateSnapshot(
            id=candidate.id,
            closet_item_id=candidate.closet_item_id,
            rank=candidate.rank,
            score=round(float(candidate.score), 4),
            signals=candidate.signals_json,
            item=item_snapshot,
        )

    def _build_processing_image_from_image_record(
        self,
        image_record: tuple[ClosetItemImage, MediaAsset] | None,
        *,
        primary_image_id: UUID | None,
    ) -> ProcessingSnapshotImage | None:
        if image_record is None:
            return None
        item_image, asset = image_record
        return self._build_processing_image_from_snapshot(
            {
                "asset_id": str(asset.id),
                "image_id": str(item_image.id),
                "role": item_image.role.value,
                "position": (
                    item_image.position if item_image.role == ClosetItemImageRole.ORIGINAL else None
                ),
                "is_primary": primary_image_id == item_image.id,
            },
            {asset.id: asset},
        )

    def _serialize_snapshot_image(
        self,
        image_record: tuple[ClosetItemImage, MediaAsset] | None,
        *,
        primary_image_id: UUID | None,
    ) -> dict[str, object] | None:
        if image_record is None:
            return None
        item_image, asset = image_record
        return {
            "asset_id": str(asset.id),
            "image_id": str(item_image.id),
            "role": item_image.role.value,
            "position": (
                item_image.position if item_image.role == ClosetItemImageRole.ORIGINAL else None
            ),
            "is_primary": primary_image_id == item_image.id,
        }

    def _build_processing_image_from_snapshot(
        self,
        snapshot_image: object,
        assets_by_id: dict[UUID, MediaAsset],
    ) -> ProcessingSnapshotImage | None:
        if not isinstance(snapshot_image, dict):
            return None

        asset_id_raw = snapshot_image.get("asset_id")
        if not isinstance(asset_id_raw, str):
            return None

        try:
            asset_id = UUID(asset_id_raw)
        except ValueError:
            return None

        asset = assets_by_id.get(asset_id)
        if asset is None:
            return None

        download = self._generate_private_download(asset)
        if download is None:
            return None
        image_id_raw = snapshot_image.get("image_id")
        position_raw = snapshot_image.get("position")
        return ProcessingSnapshotImage(
            asset_id=asset.id,
            image_id=UUID(image_id_raw) if isinstance(image_id_raw, str) else None,
            role=str(snapshot_image.get("role") or "reference"),
            position=position_raw if isinstance(position_raw, int) else None,
            is_primary=bool(snapshot_image.get("is_primary", False)),
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            url=download.url,
            expires_at=download.expires_at,
        )

    def _build_media_from_snapshot_image(
        self,
        snapshot_image: object,
        assets_by_id: dict[UUID, MediaAsset],
    ) -> WearMediaSnapshot | None:
        if not isinstance(snapshot_image, dict):
            return None
        asset_id_raw = snapshot_image.get("asset_id")
        if not isinstance(asset_id_raw, str):
            return None
        try:
            asset_id = UUID(asset_id_raw)
        except ValueError:
            return None
        asset = assets_by_id.get(asset_id)
        if asset is None:
            return None
        return self._build_private_media_snapshot(asset=asset)

    def _build_private_media_snapshot(
        self,
        *,
        asset: MediaAsset,
        photo_id: UUID | None = None,
        position: int | None = None,
    ) -> WearMediaSnapshot | None:
        download = self._generate_private_download(asset)
        if download is None:
            return None
        return WearMediaSnapshot(
            asset_id=asset.id,
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            url=download.url,
            expires_at=download.expires_at,
            photo_id=photo_id,
            position=position,
        )

    def _generate_private_download(self, asset: MediaAsset):
        try:
            return self.storage.generate_presigned_download(
                bucket=asset.bucket,
                key=asset.key,
                expires_in_seconds=settings.closet_media_download_ttl_seconds,
            )
        except Exception:
            logger.warning(
                "Failed to generate wear image download URL.",
                extra={"asset_id": str(asset.id), "bucket": asset.bucket, "key": asset.key},
                exc_info=True,
            )
            return None

    def _collect_snapshot_asset_ids(self, snapshots: Iterable[list[dict[str, object]]]) -> list[UUID]:
        asset_ids: list[UUID] = []
        seen: set[UUID] = set()
        for snapshot_items in snapshots:
            for snapshot_item in snapshot_items:
                for image_key in ("display_image", "thumbnail_image"):
                    snapshot_image = snapshot_item.get(image_key)
                    if not isinstance(snapshot_image, dict):
                        continue
                    asset_id_raw = snapshot_image.get("asset_id")
                    if not isinstance(asset_id_raw, str):
                        continue
                    try:
                        asset_id = UUID(asset_id_raw)
                    except ValueError:
                        continue
                    if asset_id not in seen:
                        seen.add(asset_id)
                        asset_ids.append(asset_id)
        return asset_ids

    def _snapshot_items_from_json(self, payload: object) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        items = [item for item in payload if isinstance(item, dict)]
        return sorted(items, key=lambda item: self._coerce_int(item.get("sort_index"), default=0))

    def _build_review_version(
        self,
        *,
        wear_log: WearLog,
        confirmed_items: list[WearLoggedItemSnapshot],
        detected_items: list[WearEventDetectedItem],
        candidate_map: dict[UUID, list[WearEventMatchCandidate]],
    ) -> str:
        payload = {
            "wear_log_id": str(wear_log.id),
            "status": wear_log.status.value,
            "updated_at": normalize_datetime(wear_log.updated_at).isoformat(),
            "confirmed_items": [
                {
                    "closet_item_id": str(item.closet_item_id),
                    "detected_item_id": str(item.detected_item_id) if item.detected_item_id else None,
                    "sort_index": item.sort_index,
                    "role": item.role,
                }
                for item in confirmed_items
            ],
            "detected_items": [
                {
                    "id": str(item.id),
                    "status": item.status.value,
                    "sort_index": item.sort_index,
                    "exclusion_reason": item.exclusion_reason,
                    "candidate_ids": [str(candidate.id) for candidate in candidate_map.get(item.id, [])],
                }
                for item in detected_items
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _get_optional_str(self, payload: dict[str, object], key: str) -> str | None:
        value = payload.get(key)
        return value if isinstance(value, str) else None

    def _coerce_int(self, value: object, *, default: int) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        return default

    def _validate_calendar_range(self, *, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise WearServiceError(422, "Calendar end_date must be on or after start_date.")
        if (end_date - start_date).days + 1 > 62:
            raise WearServiceError(422, "Calendar date range cannot exceed 62 days.")

    def _validate_timezone_name(self, timezone_name: str | None) -> None:
        if timezone_name is None:
            return
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise WearServiceError(422, "timezone_name must be a valid IANA timezone.") from exc


@dataclass(frozen=True)
class DetailContext:
    snapshots_by_log: dict[UUID, WearLogSnapshot]
    snapshot_items_by_log: dict[UUID, list[dict[str, object]]]
    outfits_by_id: dict[UUID, Outfit]
    photos_by_log: dict[UUID, list[WearEventPhoto]]
    photo_assets_by_photo_id: dict[UUID, dict[str, MediaAsset | None]]
    item_assets_by_id: dict[UUID, MediaAsset]
    detected_items_by_log: dict[UUID, list[WearEventDetectedItem]]
    candidates_by_detected_item: dict[UUID, list[WearEventMatchCandidate]]
    candidate_items_by_id: dict[UUID, tuple[ClosetItem, ClosetItemMetadataProjection]]
    candidate_item_assets_by_id: dict[UUID, MediaAsset]
    crop_assets_by_id: dict[UUID, MediaAsset]


def default_worn_at_for_date(wear_date: date) -> datetime:
    return datetime.combine(wear_date, time(hour=12, minute=0), tzinfo=UTC)


def normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def resolve_event_temporal_fields(
    *,
    wear_date: date,
    worn_at: datetime | None,
    timezone_name: str | None,
) -> tuple[datetime, date, WearTimePrecision]:
    if worn_at is None:
        return default_worn_at_for_date(wear_date), wear_date, WearTimePrecision.DATE_ONLY

    normalized_worn_at = normalize_datetime(worn_at)
    assert normalized_worn_at is not None
    derived_date = derive_local_wear_date(worn_at=normalized_worn_at, timezone_name=timezone_name)
    if derived_date != wear_date:
        raise WearServiceError(
            422,
            "wear_date must match the local calendar date derived from worn_at.",
        )
    return normalized_worn_at, derived_date, WearTimePrecision.EXACT


def derive_local_wear_date(*, worn_at: datetime, timezone_name: str | None) -> date:
    normalized_worn_at = normalize_datetime(worn_at)
    assert normalized_worn_at is not None
    if timezone_name is None:
        return normalized_worn_at.date()
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise WearServiceError(422, "timezone_name must be a valid IANA timezone.") from exc
    return normalized_worn_at.astimezone(timezone).date()


def move_worn_at_to_new_date(
    *,
    worn_at: datetime,
    new_wear_date: date,
    timezone_name: str | None,
) -> datetime:
    normalized_worn_at = normalize_datetime(worn_at)
    assert normalized_worn_at is not None
    if timezone_name is None:
        return normalized_worn_at.replace(
            year=new_wear_date.year,
            month=new_wear_date.month,
            day=new_wear_date.day,
        )
    timezone = ZoneInfo(timezone_name)
    localized = normalized_worn_at.astimezone(timezone)
    adjusted = localized.replace(
        year=new_wear_date.year,
        month=new_wear_date.month,
        day=new_wear_date.day,
    )
    return adjusted.astimezone(UTC)


def build_combination_fingerprint(item_ids: list[UUID]) -> str | None:
    if not item_ids:
        return None
    payload = "|".join(sorted(str(item_id) for item_id in item_ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def encode_history_cursor(
    *,
    worn_at: datetime,
    created_at: datetime,
    wear_log_id: UUID,
) -> str:
    payload = (
        f"{normalize_datetime(worn_at).isoformat()}|"
        f"{normalize_datetime(created_at).isoformat()}|"
        f"{wear_log_id}"
    )
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_history_cursor(
    cursor: str | None,
) -> tuple[datetime | None, datetime | None, UUID | None]:
    if cursor is None:
        return None, None, None

    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        worn_at_raw, created_at_raw, wear_log_id_raw = decoded.split("|", 2)
        return (
            datetime.fromisoformat(worn_at_raw),
            datetime.fromisoformat(created_at_raw),
            UUID(wear_log_id_raw),
        )
    except (ValueError, TypeError) as exc:
        raise InvalidWearHistoryCursorError("Invalid wear history cursor.") from exc
