from __future__ import annotations

import base64
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
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
    WearContext,
    WearItemRole,
    WearItemSource,
    WearLog,
    WearLogSource,
)
from app.domains.wear.repository import WearRepository


@dataclass(frozen=True)
class RequestedWearItem:
    closet_item_id: UUID
    role: WearItemRole | None
    sort_index: int


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


@dataclass(frozen=True)
class WearLogDetailSnapshot:
    id: UUID
    wear_date: date
    source: str
    context: str | None
    notes: str | None
    is_confirmed: bool
    item_count: int
    cover_image: ProcessingSnapshotImage | None
    items: list[WearLoggedItemSnapshot]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WearLogTimelineItemSnapshot:
    id: UUID
    wear_date: date
    context: str | None
    item_count: int
    source: str
    is_confirmed: bool
    cover_image: ProcessingSnapshotImage | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WearCalendarDaySnapshot:
    date: date
    has_wear_log: bool
    wear_log_id: UUID | None
    item_count: int
    source: str | None
    is_confirmed: bool | None
    cover_image: ProcessingSnapshotImage | None


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
        context: str | None,
        notes: str | None,
        items: list[dict[str, object]],
    ) -> WearLogDetailSnapshot:
        normalized_items = self._normalize_requested_items(items)
        self._ensure_wear_date_available(user_id=user_id, wear_date=wear_date)
        confirmed_items = self._get_confirmed_items_or_raise(
            user_id=user_id,
            item_ids=[item.closet_item_id for item in normalized_items],
        )

        wear_log = self.repository.create_wear_log(
            user_id=user_id,
            wear_date=wear_date,
            source=WearLogSource.MANUAL_ITEMS,
            context=WearContext(context) if context is not None else None,
            notes=notes,
            is_confirmed=True,
        )
        self.repository.create_wear_log_items(
            wear_log_id=wear_log.id,
            items=[
                {
                    "closet_item_id": item.closet_item_id,
                    "source": WearItemSource.MANUAL,
                    "match_confidence": None,
                    "sort_index": item.sort_index,
                    "role": item.role,
                }
                for item in normalized_items
            ],
        )
        self.repository.upsert_wear_log_snapshot(
            wear_log_id=wear_log.id,
            items_snapshot_json=self._build_items_snapshot_json(
                normalized_items=normalized_items,
                confirmed_items=confirmed_items,
            ),
        )

        self.session.commit()
        return self.get_wear_log_detail(wear_log_id=wear_log.id, user_id=user_id)

    def get_wear_log_detail(
        self,
        *,
        wear_log_id: UUID,
        user_id: UUID,
    ) -> WearLogDetailSnapshot:
        wear_log = self._get_wear_log_or_raise(wear_log_id=wear_log_id, user_id=user_id)
        snapshot_items = self._get_snapshot_items_for_log(wear_log=wear_log, user_id=user_id)
        assets_by_id = self.repository.get_media_assets_by_ids(
            asset_ids=self._collect_snapshot_asset_ids(snapshot_items)
        )
        items = [self._build_logged_item_snapshot(item, assets_by_id) for item in snapshot_items]
        return WearLogDetailSnapshot(
            id=wear_log.id,
            wear_date=wear_log.wear_date,
            source=wear_log.source.value,
            context=wear_log.context.value if wear_log.context is not None else None,
            notes=wear_log.notes,
            is_confirmed=wear_log.is_confirmed,
            item_count=len(items),
            cover_image=self._build_cover_image(snapshot_items, assets_by_id),
            items=items,
            created_at=wear_log.created_at,
            updated_at=wear_log.updated_at,
        )

    def list_wear_logs(
        self,
        *,
        user_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[WearLogTimelineItemSnapshot], str | None]:
        cursor_wear_date, cursor_created_at, cursor_wear_log_id = decode_history_cursor(cursor)
        wear_logs = self.repository.list_wear_logs(
            user_id=user_id,
            cursor_wear_date=cursor_wear_date,
            cursor_created_at=cursor_created_at,
            cursor_wear_log_id=cursor_wear_log_id,
            limit=limit + 1,
        )
        has_more = len(wear_logs) > limit
        visible_logs = wear_logs[:limit]
        snapshots = self.repository.get_wear_log_snapshots_for_logs(
            wear_log_ids=[wear_log.id for wear_log in visible_logs]
        )
        snapshot_items_by_log = {
            wear_log_id: self._snapshot_items_from_json(snapshot.items_snapshot_json)
            for wear_log_id, snapshot in snapshots.items()
        }
        assets_by_id = self.repository.get_media_assets_by_ids(
            asset_ids=self._collect_cover_asset_ids(snapshot_items_by_log.values())
        )
        items = [
            self._build_timeline_item(
                wear_log=wear_log,
                snapshot_items=snapshot_items_by_log.get(wear_log.id, []),
                assets_by_id=assets_by_id,
            )
            for wear_log in visible_logs
        ]

        next_cursor = None
        if has_more and visible_logs:
            last_wear_log = visible_logs[-1]
            next_cursor = encode_history_cursor(
                wear_date=last_wear_log.wear_date,
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
        context: str | None = None,
        notes: str | None = None,
        items: list[dict[str, object]] | None = None,
        field_names: set[str],
    ) -> WearLogDetailSnapshot:
        wear_log = self._get_wear_log_or_raise(wear_log_id=wear_log_id, user_id=user_id)

        if not field_names:
            return self.get_wear_log_detail(wear_log_id=wear_log_id, user_id=user_id)

        if "wear_date" in field_names:
            if wear_date is None:
                raise WearServiceError(422, "wear_date cannot be null.")
            self._ensure_wear_date_available(
                user_id=user_id,
                wear_date=wear_date,
                exclude_wear_log_id=wear_log.id,
            )
            wear_log.wear_date = wear_date

        if "context" in field_names:
            wear_log.context = WearContext(context) if context is not None else None

        if "notes" in field_names:
            wear_log.notes = notes

        if "items" in field_names:
            if items is None:
                raise WearServiceError(422, "Items cannot be null when replacing a wear log.")
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
                        "source": WearItemSource.MANUAL,
                        "match_confidence": None,
                        "sort_index": item.sort_index,
                        "role": item.role,
                    }
                    for item in normalized_items
                ],
            )
            self.repository.upsert_wear_log_snapshot(
                wear_log_id=wear_log.id,
                items_snapshot_json=self._build_items_snapshot_json(
                    normalized_items=normalized_items,
                    confirmed_items=confirmed_items,
                ),
            )

        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            if self._is_wear_date_conflict(exc):
                raise WearServiceError(409, "You already have a wear log for that date.") from exc
            raise

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
        )
        snapshots = self.repository.get_wear_log_snapshots_for_logs(
            wear_log_ids=[wear_log.id for wear_log in wear_logs]
        )
        snapshot_items_by_log = {
            wear_log_id: self._snapshot_items_from_json(snapshot.items_snapshot_json)
            for wear_log_id, snapshot in snapshots.items()
        }
        assets_by_id = self.repository.get_media_assets_by_ids(
            asset_ids=self._collect_cover_asset_ids(snapshot_items_by_log.values())
        )
        logs_by_date = {wear_log.wear_date: wear_log for wear_log in wear_logs}

        days: list[WearCalendarDaySnapshot] = []
        current_date = start_date
        while current_date <= end_date:
            wear_log = logs_by_date.get(current_date)
            if wear_log is None:
                days.append(
                    WearCalendarDaySnapshot(
                        date=current_date,
                        has_wear_log=False,
                        wear_log_id=None,
                        item_count=0,
                        source=None,
                        is_confirmed=None,
                        cover_image=None,
                    )
                )
            else:
                snapshot_items = snapshot_items_by_log.get(wear_log.id, [])
                days.append(
                    WearCalendarDaySnapshot(
                        date=current_date,
                        has_wear_log=True,
                        wear_log_id=wear_log.id,
                        item_count=len(snapshot_items),
                        source=wear_log.source.value,
                        is_confirmed=wear_log.is_confirmed,
                        cover_image=self._build_cover_image(snapshot_items, assets_by_id),
                    )
                )
            current_date += timedelta(days=1)
        return days

    def _get_wear_log_or_raise(self, *, wear_log_id: UUID, user_id: UUID) -> WearLog:
        wear_log = self.repository.get_wear_log_for_user(wear_log_id=wear_log_id, user_id=user_id)
        if wear_log is None:
            raise WearServiceError(404, "Wear log not found.")
        return wear_log

    def _ensure_wear_date_available(
        self,
        *,
        user_id: UUID,
        wear_date: date,
        exclude_wear_log_id: UUID | None = None,
    ) -> None:
        existing_wear_log = self.repository.get_wear_log_by_date_for_user(
            user_id=user_id,
            wear_date=wear_date,
            exclude_wear_log_id=exclude_wear_log_id,
        )
        if existing_wear_log is not None:
            raise WearServiceError(409, "You already have a wear log for that date.")

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
                    "Each wear-log item must include a valid closet_item_id.",
                )
            closet_item_id = closet_item_id_raw
            if closet_item_id in seen_item_ids:
                raise WearServiceError(
                    422,
                    "Each closet item can appear at most once in a single wear log.",
                )
            seen_item_ids.add(closet_item_id)

            provided_sort_index = item.get("sort_index")
            role_raw = item.get("role")
            role = WearItemRole(role_raw) if isinstance(role_raw, str) else None
            sortable_items.append(
                (
                    provided_sort_index if isinstance(provided_sort_index, int) else position,
                    position,
                    RequestedWearItem(
                        closet_item_id=closet_item_id,
                        role=role,
                        sort_index=0,
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
                    "title": projection.title,
                    "category": projection.category,
                    "subcategory": projection.subcategory,
                    "primary_color": projection.primary_color,
                    "role": item.role.value if item.role is not None else None,
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
        normalized_items = [
            RequestedWearItem(
                closet_item_id=item.closet_item_id,
                role=item.role,
                sort_index=item.sort_index,
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
        return WearLoggedItemSnapshot(
            closet_item_id=UUID(str(snapshot_item["closet_item_id"])),
            title=self._get_optional_str(snapshot_item, "title"),
            category=self._get_optional_str(snapshot_item, "category"),
            subcategory=self._get_optional_str(snapshot_item, "subcategory"),
            primary_color=self._get_optional_str(snapshot_item, "primary_color"),
            display_image=self._build_image_from_snapshot(
                snapshot_item.get("display_image"),
                assets_by_id,
            ),
            thumbnail_image=self._build_image_from_snapshot(
                snapshot_item.get("thumbnail_image"),
                assets_by_id,
            ),
            role=self._get_optional_str(snapshot_item, "role"),
            sort_index=self._coerce_int(snapshot_item.get("sort_index"), default=0),
        )

    def _build_timeline_item(
        self,
        *,
        wear_log: WearLog,
        snapshot_items: list[dict[str, object]],
        assets_by_id: dict[UUID, MediaAsset],
    ) -> WearLogTimelineItemSnapshot:
        return WearLogTimelineItemSnapshot(
            id=wear_log.id,
            wear_date=wear_log.wear_date,
            context=wear_log.context.value if wear_log.context is not None else None,
            item_count=len(snapshot_items),
            source=wear_log.source.value,
            is_confirmed=wear_log.is_confirmed,
            cover_image=self._build_cover_image(snapshot_items, assets_by_id),
            created_at=wear_log.created_at,
            updated_at=wear_log.updated_at,
        )

    def _build_cover_image(
        self,
        snapshot_items: list[dict[str, object]],
        assets_by_id: dict[UUID, MediaAsset],
    ) -> ProcessingSnapshotImage | None:
        for snapshot_item in snapshot_items:
            cover_image = self._build_image_from_snapshot(
                snapshot_item.get("display_image"),
                assets_by_id,
            )
            if cover_image is not None:
                return cover_image
            cover_image = self._build_image_from_snapshot(
                snapshot_item.get("thumbnail_image"),
                assets_by_id,
            )
            if cover_image is not None:
                return cover_image
        return None

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

    def _build_image_from_snapshot(
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

        presigned_download = self.storage.generate_presigned_download(
            bucket=asset.bucket,
            key=asset.key,
            expires_in_seconds=settings.closet_media_download_ttl_seconds,
        )
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
            url=presigned_download.url,
            expires_at=presigned_download.expires_at,
        )

    def _collect_snapshot_asset_ids(self, snapshot_items: list[dict[str, object]]) -> list[UUID]:
        return self._collect_cover_asset_ids([snapshot_items])

    def _collect_cover_asset_ids(
        self,
        snapshots: Iterable[list[dict[str, object]]],
    ) -> list[UUID]:
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
        return sorted(
            items,
            key=lambda item: self._coerce_int(item.get("sort_index"), default=0),
        )

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

    def _is_wear_date_conflict(self, exc: IntegrityError) -> bool:
        message = str(exc).lower()
        return "wear_logs" in message and "user_id" in message and "wear_date" in message


def encode_history_cursor(
    *,
    wear_date: date,
    created_at: datetime,
    wear_log_id: UUID,
) -> str:
    payload = f"{wear_date.isoformat()}|{created_at.astimezone(UTC).isoformat()}|{wear_log_id}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_history_cursor(
    cursor: str | None,
) -> tuple[date | None, datetime | None, UUID | None]:
    if cursor is None:
        return None, None, None

    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        wear_date_raw, created_at_raw, wear_log_id_raw = decoded.split("|", 2)
        return (
            date.fromisoformat(wear_date_raw),
            datetime.fromisoformat(created_at_raw),
            UUID(wear_log_id_raw),
        )
    except (ValueError, TypeError) as exc:
        raise InvalidWearHistoryCursorError("Invalid wear history cursor.") from exc
