from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient
from app.domains.closet.image_processing_service import ProcessingSnapshotImage
from app.domains.closet.models import (
    ClosetItemImage,
    ClosetItemImageRole,
    MediaAsset,
)
from app.domains.wear.models import Outfit, WearLog
from app.domains.wear.repository import WearRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InsightOverviewAllTimeSnapshot:
    total_wear_logs: int
    total_worn_item_events: int
    unique_items_worn: int
    active_confirmed_closet_item_count: int
    never_worn_item_count: int


@dataclass(frozen=True)
class InsightOverviewCurrentMonthSnapshot:
    total_wear_logs: int
    total_worn_item_events: int
    unique_items_worn: int
    active_closet_items_worn: int
    active_closet_coverage_ratio: float


@dataclass(frozen=True)
class InsightOverviewStreaksSnapshot:
    current_streak_days: int
    longest_streak_days: int


@dataclass(frozen=True)
class InsightOverviewSnapshot:
    as_of_date: date
    all_time: InsightOverviewAllTimeSnapshot
    current_month: InsightOverviewCurrentMonthSnapshot
    streaks: InsightOverviewStreaksSnapshot


@dataclass(frozen=True)
class InsightItemUsageSnapshot:
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ProcessingSnapshotImage | None
    thumbnail_image: ProcessingSnapshotImage | None
    wear_count: int
    first_worn_date: date
    last_worn_date: date


@dataclass(frozen=True)
class InsightStaleItemSnapshot:
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ProcessingSnapshotImage | None
    thumbnail_image: ProcessingSnapshotImage | None
    wear_count: int
    first_worn_date: date
    last_worn_date: date
    days_since_last_worn: int


@dataclass(frozen=True)
class InsightNeverWornItemSnapshot:
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ProcessingSnapshotImage | None
    thumbnail_image: ProcessingSnapshotImage | None
    confirmed_at: datetime


@dataclass(frozen=True)
class InsightOutfitUsageSnapshot:
    id: UUID
    title: str | None
    occasion: str | None
    season: str | None
    source: str
    item_count: int
    is_favorite: bool
    is_archived: bool
    cover_image: ProcessingSnapshotImage | None
    wear_count: int
    first_worn_date: date
    last_worn_date: date


@dataclass(frozen=True)
class InsightCategoryUsageSnapshot:
    category: str
    wear_count: int
    unique_item_count: int
    last_worn_date: date


@dataclass(frozen=True)
class InsightTimelinePointSnapshot:
    date: date
    wear_log_count: int
    worn_item_count: int
    unique_item_count: int


@dataclass(frozen=True)
class HydratedInsightItem:
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ProcessingSnapshotImage | None
    thumbnail_image: ProcessingSnapshotImage | None
    confirmed_at: datetime | None


@dataclass
class CategoryAggregate:
    wear_count: int
    item_ids: set[UUID]
    last_worn_date: date


@dataclass
class TimelineAggregate:
    wear_log_count: int
    worn_item_count: int
    item_ids: set[UUID]


class InsightServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class InvalidInsightCursorError(ValueError):
    pass


class InsightService:
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

    def get_overview(
        self,
        *,
        user_id: UUID,
        as_of_date: date | None,
    ) -> InsightOverviewSnapshot:
        resolved_as_of = as_of_date or datetime.now(UTC).date()
        month_start = resolved_as_of.replace(day=1)

        active_item_count = self.repository.count_active_confirmed_closet_items(user_id=user_id)
        never_worn_item_count = self.repository.count_never_worn_active_confirmed_closet_items(
            user_id=user_id
        )
        all_time_metrics = self.repository.get_wear_activity_aggregate(user_id=user_id)
        current_month_metrics = self.repository.get_wear_activity_aggregate(
            user_id=user_id,
            start_date=month_start,
            end_date=resolved_as_of,
        )
        active_closet_items_worn = self.repository.count_active_confirmed_items_worn_in_range(
            user_id=user_id,
            start_date=month_start,
            end_date=resolved_as_of,
        )
        coverage_ratio = (
            round(active_closet_items_worn / active_item_count, 4) if active_item_count > 0 else 0.0
        )
        wear_dates = self.repository.list_confirmed_wear_dates(
            user_id=user_id,
            end_date=resolved_as_of,
        )
        current_streak_days, longest_streak_days = self._calculate_streaks(
            wear_dates=wear_dates,
            as_of_date=resolved_as_of,
        )

        return InsightOverviewSnapshot(
            as_of_date=resolved_as_of,
            all_time=InsightOverviewAllTimeSnapshot(
                total_wear_logs=all_time_metrics[0],
                total_worn_item_events=all_time_metrics[1],
                unique_items_worn=all_time_metrics[2],
                active_confirmed_closet_item_count=active_item_count,
                never_worn_item_count=never_worn_item_count,
            ),
            current_month=InsightOverviewCurrentMonthSnapshot(
                total_wear_logs=current_month_metrics[0],
                total_worn_item_events=current_month_metrics[1],
                unique_items_worn=current_month_metrics[2],
                active_closet_items_worn=active_closet_items_worn,
                active_closet_coverage_ratio=coverage_ratio,
            ),
            streaks=InsightOverviewStreaksSnapshot(
                current_streak_days=current_streak_days,
                longest_streak_days=longest_streak_days,
            ),
        )

    def list_item_usage(
        self,
        *,
        user_id: UUID,
        sort: str,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[InsightItemUsageSnapshot], str | None]:
        offset = decode_insight_cursor(cursor)
        rows = self.repository.list_item_usage(
            user_id=user_id,
            offset=offset,
            limit=limit + 1,
            sort=sort,
        )
        has_more = len(rows) > limit
        visible_rows = rows[:limit]
        item_records = self._hydrate_items(
            user_id=user_id,
            item_ids=[row[0] for row in visible_rows],
            confirmed_only=True,
        )

        items = [
            self._build_item_usage_snapshot(
                item_record=item_records[row[0]],
                wear_count=row[1],
                first_worn_date=row[2],
                last_worn_date=row[3],
            )
            for row in visible_rows
        ]
        next_cursor = encode_insight_cursor(offset + len(visible_rows)) if has_more else None
        return items, next_cursor

    def list_outfit_usage(
        self,
        *,
        user_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[InsightOutfitUsageSnapshot], str | None]:
        offset = decode_insight_cursor(cursor)
        rows = self.repository.list_outfit_usage(
            user_id=user_id,
            offset=offset,
            limit=limit + 1,
        )
        has_more = len(rows) > limit
        visible_rows = rows[:limit]
        outfit_ids = [row[0] for row in visible_rows]
        outfits_by_id = self.repository.get_outfits_for_user(outfit_ids=outfit_ids, user_id=user_id)
        if len(outfits_by_id) != len(set(outfit_ids)):
            raise InsightServiceError(409, "One or more outfits could no longer be loaded.")

        item_snapshots_by_outfit = self._build_outfit_item_snapshots(
            user_id=user_id,
            outfit_ids=outfit_ids,
        )
        items = [
            self._build_outfit_usage_snapshot(
                outfit=outfits_by_id[row[0]],
                items=item_snapshots_by_outfit.get(row[0], []),
                wear_count=row[1],
                first_worn_date=row[2],
                last_worn_date=row[3],
            )
            for row in visible_rows
        ]
        next_cursor = encode_insight_cursor(offset + len(visible_rows)) if has_more else None
        return items, next_cursor

    def get_category_usage(
        self,
        *,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[InsightCategoryUsageSnapshot]:
        self._validate_date_range(start_date=start_date, end_date=end_date)
        wear_logs = self.repository.list_wear_logs_in_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            confirmed_only=True,
        )
        snapshot_items_by_log = self._get_snapshot_items_by_log(
            wear_logs=wear_logs,
            user_id=user_id,
        )

        aggregates: dict[str, CategoryAggregate] = {}
        for wear_log in wear_logs:
            for snapshot_item in snapshot_items_by_log.get(wear_log.id, []):
                category = self._normalize_category(snapshot_item.get("category"))
                aggregate = aggregates.setdefault(
                    category,
                    CategoryAggregate(
                        wear_count=0,
                        item_ids=set(),
                        last_worn_date=wear_log.wear_date,
                    ),
                )
                aggregate.wear_count += 1
                closet_item_id = self._snapshot_item_id(snapshot_item)
                if closet_item_id is not None:
                    aggregate.item_ids.add(closet_item_id)
                if wear_log.wear_date > aggregate.last_worn_date:
                    aggregate.last_worn_date = wear_log.wear_date

        return sorted(
            [
                InsightCategoryUsageSnapshot(
                    category=category,
                    wear_count=data.wear_count,
                    unique_item_count=len(data.item_ids),
                    last_worn_date=data.last_worn_date,
                )
                for category, data in aggregates.items()
            ],
            key=lambda item: (-item.wear_count, -item.last_worn_date.toordinal(), item.category),
        )

    def get_timeline(
        self,
        *,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[InsightTimelinePointSnapshot]:
        self._validate_date_range(
            start_date=start_date,
            end_date=end_date,
            max_days=366,
            message="Timeline date range cannot exceed 366 days.",
        )
        wear_logs = self.repository.list_wear_logs_in_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            confirmed_only=True,
        )
        snapshot_items_by_log = self._get_snapshot_items_by_log(
            wear_logs=wear_logs,
            user_id=user_id,
        )

        by_date: dict[date, TimelineAggregate] = {}
        for wear_log in wear_logs:
            aggregate = by_date.setdefault(
                wear_log.wear_date,
                TimelineAggregate(
                    wear_log_count=0,
                    worn_item_count=0,
                    item_ids=set(),
                ),
            )
            aggregate.wear_log_count += 1
            snapshot_items = snapshot_items_by_log.get(wear_log.id, [])
            aggregate.worn_item_count += len(snapshot_items)
            for snapshot_item in snapshot_items:
                closet_item_id = self._snapshot_item_id(snapshot_item)
                if closet_item_id is not None:
                    aggregate.item_ids.add(closet_item_id)

        points: list[InsightTimelinePointSnapshot] = []
        current_date = start_date
        while current_date <= end_date:
            aggregate_for_date = by_date.get(current_date)
            if aggregate_for_date is None:
                points.append(
                    InsightTimelinePointSnapshot(
                        date=current_date,
                        wear_log_count=0,
                        worn_item_count=0,
                        unique_item_count=0,
                    )
                )
            else:
                points.append(
                    InsightTimelinePointSnapshot(
                        date=current_date,
                        wear_log_count=aggregate_for_date.wear_log_count,
                        worn_item_count=aggregate_for_date.worn_item_count,
                        unique_item_count=len(aggregate_for_date.item_ids),
                    )
                )
            current_date += timedelta(days=1)
        return points

    def list_stale_items(
        self,
        *,
        user_id: UUID,
        as_of_date: date | None,
        stale_after_days: int,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[InsightStaleItemSnapshot], str | None]:
        resolved_as_of = as_of_date or datetime.now(UTC).date()
        cutoff_date = resolved_as_of - timedelta(days=stale_after_days)
        offset = decode_insight_cursor(cursor)
        rows = self.repository.list_stale_item_usage(
            user_id=user_id,
            cutoff_date=cutoff_date,
            offset=offset,
            limit=limit + 1,
        )
        has_more = len(rows) > limit
        visible_rows = rows[:limit]
        item_records = self._hydrate_items(
            user_id=user_id,
            item_ids=[row[0] for row in visible_rows],
            confirmed_only=True,
        )

        items = [
            self._build_stale_item_snapshot(
                item_record=item_records[row[0]],
                wear_count=row[1],
                first_worn_date=row[2],
                last_worn_date=row[3],
                as_of_date=resolved_as_of,
            )
            for row in visible_rows
        ]
        next_cursor = encode_insight_cursor(offset + len(visible_rows)) if has_more else None
        return items, next_cursor

    def list_never_worn_items(
        self,
        *,
        user_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[InsightNeverWornItemSnapshot], str | None]:
        offset = decode_insight_cursor(cursor)
        rows = self.repository.list_never_worn_items(
            user_id=user_id,
            offset=offset,
            limit=limit + 1,
        )
        has_more = len(rows) > limit
        visible_rows = rows[:limit]
        item_records = self._hydrate_items(
            user_id=user_id,
            item_ids=[row[0] for row in visible_rows],
            confirmed_only=True,
        )

        items = [
            self._build_never_worn_item_snapshot(
                item_record=item_records[row[0]],
                confirmed_at=row[1],
            )
            for row in visible_rows
        ]
        next_cursor = encode_insight_cursor(offset + len(visible_rows)) if has_more else None
        return items, next_cursor

    def _calculate_streaks(
        self,
        *,
        wear_dates: list[date],
        as_of_date: date,
    ) -> tuple[int, int]:
        if not wear_dates:
            return 0, 0

        unique_dates = sorted(set(wear_dates))
        current_streak_days = 0
        expected_date = as_of_date
        wear_dates_set = set(unique_dates)
        while expected_date in wear_dates_set:
            current_streak_days += 1
            expected_date -= timedelta(days=1)

        longest_streak_days = 0
        running_streak_days = 0
        previous_date: date | None = None
        for wear_date in unique_dates:
            if previous_date is None or wear_date == previous_date + timedelta(days=1):
                running_streak_days += 1
            else:
                running_streak_days = 1
            longest_streak_days = max(longest_streak_days, running_streak_days)
            previous_date = wear_date

        return current_streak_days, longest_streak_days

    def _hydrate_items(
        self,
        *,
        user_id: UUID,
        item_ids: list[UUID],
        confirmed_only: bool,
    ) -> dict[UUID, HydratedInsightItem]:
        if not item_ids:
            return {}

        if confirmed_only:
            item_records = self.repository.get_confirmed_closet_items_with_projections_for_user(
                item_ids=item_ids,
                user_id=user_id,
            )
        else:
            item_records = self.repository.get_closet_items_with_projections_for_user(
                item_ids=item_ids,
                user_id=user_id,
            )
        if len(item_records) != len(set(item_ids)):
            raise InsightServiceError(409, "One or more closet items could no longer be loaded.")

        images_by_item = self.repository.list_active_image_assets_for_items(
            closet_item_ids=list({item_id for item_id in item_ids}),
            roles=[
                ClosetItemImageRole.ORIGINAL,
                ClosetItemImageRole.PROCESSED,
                ClosetItemImageRole.THUMBNAIL,
            ],
        )
        hydrated: dict[UUID, HydratedInsightItem] = {}
        for item_id, (closet_item, projection) in item_records.items():
            images_by_role = images_by_item.get(item_id, {})
            display_image_record = images_by_role.get(
                ClosetItemImageRole.PROCESSED
            ) or images_by_role.get(ClosetItemImageRole.ORIGINAL)
            thumbnail_image_record = images_by_role.get(ClosetItemImageRole.THUMBNAIL)
            hydrated[item_id] = HydratedInsightItem(
                closet_item_id=item_id,
                title=projection.title,
                category=projection.category,
                subcategory=projection.subcategory,
                primary_color=projection.primary_color,
                display_image=self._build_processing_snapshot_image(
                    display_image_record,
                    primary_image_id=closet_item.primary_image_id,
                ),
                thumbnail_image=self._build_processing_snapshot_image(
                    thumbnail_image_record,
                    primary_image_id=closet_item.primary_image_id,
                ),
                confirmed_at=closet_item.confirmed_at,
            )
        return hydrated

    def _build_item_usage_snapshot(
        self,
        *,
        item_record: HydratedInsightItem,
        wear_count: int,
        first_worn_date: date,
        last_worn_date: date,
    ) -> InsightItemUsageSnapshot:
        return InsightItemUsageSnapshot(
            closet_item_id=item_record.closet_item_id,
            title=item_record.title,
            category=item_record.category,
            subcategory=item_record.subcategory,
            primary_color=item_record.primary_color,
            display_image=item_record.display_image,
            thumbnail_image=item_record.thumbnail_image,
            wear_count=wear_count,
            first_worn_date=first_worn_date,
            last_worn_date=last_worn_date,
        )

    def _build_stale_item_snapshot(
        self,
        *,
        item_record: HydratedInsightItem,
        wear_count: int,
        first_worn_date: date,
        last_worn_date: date,
        as_of_date: date,
    ) -> InsightStaleItemSnapshot:
        return InsightStaleItemSnapshot(
            closet_item_id=item_record.closet_item_id,
            title=item_record.title,
            category=item_record.category,
            subcategory=item_record.subcategory,
            primary_color=item_record.primary_color,
            display_image=item_record.display_image,
            thumbnail_image=item_record.thumbnail_image,
            wear_count=wear_count,
            first_worn_date=first_worn_date,
            last_worn_date=last_worn_date,
            days_since_last_worn=(as_of_date - last_worn_date).days,
        )

    def _build_never_worn_item_snapshot(
        self,
        *,
        item_record: HydratedInsightItem,
        confirmed_at: datetime,
    ) -> InsightNeverWornItemSnapshot:
        return InsightNeverWornItemSnapshot(
            closet_item_id=item_record.closet_item_id,
            title=item_record.title,
            category=item_record.category,
            subcategory=item_record.subcategory,
            primary_color=item_record.primary_color,
            display_image=item_record.display_image,
            thumbnail_image=item_record.thumbnail_image,
            confirmed_at=confirmed_at,
        )

    def _build_outfit_item_snapshots(
        self,
        *,
        user_id: UUID,
        outfit_ids: list[UUID],
    ) -> dict[UUID, list[HydratedInsightItem]]:
        outfit_items_by_outfit = self.repository.list_outfit_items_for_outfits(
            outfit_ids=outfit_ids
        )
        item_ids = [
            outfit_item.closet_item_id
            for outfit_items in outfit_items_by_outfit.values()
            for outfit_item in outfit_items
        ]
        item_records = self._hydrate_items(
            user_id=user_id,
            item_ids=item_ids,
            confirmed_only=False,
        )

        items_by_outfit: dict[UUID, list[HydratedInsightItem]] = {}
        for outfit_id, outfit_items in outfit_items_by_outfit.items():
            items_by_outfit[outfit_id] = [
                item_records[outfit_item.closet_item_id] for outfit_item in outfit_items
            ]
        return items_by_outfit

    def _build_outfit_usage_snapshot(
        self,
        *,
        outfit: Outfit,
        items: list[HydratedInsightItem],
        wear_count: int,
        first_worn_date: date,
        last_worn_date: date,
    ) -> InsightOutfitUsageSnapshot:
        return InsightOutfitUsageSnapshot(
            id=outfit.id,
            title=outfit.title,
            occasion=outfit.occasion.value if outfit.occasion is not None else None,
            season=outfit.season.value if outfit.season is not None else None,
            source=outfit.source.value,
            item_count=len(items),
            is_favorite=outfit.is_favorite,
            is_archived=outfit.archived_at is not None,
            cover_image=self._build_item_cover_image(items),
            wear_count=wear_count,
            first_worn_date=first_worn_date,
            last_worn_date=last_worn_date,
        )

    def _build_item_cover_image(
        self,
        items: list[HydratedInsightItem],
    ) -> ProcessingSnapshotImage | None:
        for item in items:
            if item.display_image is not None:
                return item.display_image
            if item.thumbnail_image is not None:
                return item.thumbnail_image
        return None

    def _build_processing_snapshot_image(
        self,
        image_record: tuple[ClosetItemImage, MediaAsset] | None,
        *,
        primary_image_id: UUID | None,
    ) -> ProcessingSnapshotImage | None:
        if image_record is None:
            return None

        item_image, asset = image_record
        try:
            presigned_download = self.storage.generate_presigned_download(
                bucket=asset.bucket,
                key=asset.key,
                expires_in_seconds=settings.closet_media_download_ttl_seconds,
            )
        except Exception:
            logger.warning(
                "Failed to generate insight image download URL.",
                extra={
                    "asset_id": str(asset.id),
                    "bucket": asset.bucket,
                    "key": asset.key,
                },
                exc_info=True,
            )
            return None
        return ProcessingSnapshotImage(
            asset_id=asset.id,
            image_id=item_image.id,
            role=item_image.role.value,
            position=item_image.position,
            is_primary=primary_image_id == item_image.id,
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            url=presigned_download.url,
            expires_at=presigned_download.expires_at,
        )

    def _get_snapshot_items_by_log(
        self,
        *,
        wear_logs: list[WearLog],
        user_id: UUID,
    ) -> dict[UUID, list[dict[str, object]]]:
        snapshots = self.repository.get_wear_log_snapshots_for_logs(
            wear_log_ids=[wear_log.id for wear_log in wear_logs]
        )
        snapshot_items_by_log = {
            wear_log_id: self._snapshot_items_from_json(snapshot.items_snapshot_json)
            for wear_log_id, snapshot in snapshots.items()
        }
        missing_logs = [
            wear_log for wear_log in wear_logs if wear_log.id not in snapshot_items_by_log
        ]
        if not missing_logs:
            return snapshot_items_by_log

        wear_log_items_by_log = self.repository.list_wear_log_items_for_logs(
            wear_log_ids=[wear_log.id for wear_log in missing_logs]
        )
        missing_item_ids = [
            item.closet_item_id
            for items in wear_log_items_by_log.values()
            for item in items
        ]
        fallback_items_by_id = self.repository.get_closet_items_with_projections_for_user(
            item_ids=missing_item_ids,
            user_id=user_id,
        )
        for wear_log in missing_logs:
            fallback_items: list[dict[str, object]] = []
            for item in wear_log_items_by_log.get(wear_log.id, []):
                item_record = fallback_items_by_id.get(item.closet_item_id)
                projection = item_record[1] if item_record is not None else None
                fallback_items.append(
                    {
                        "closet_item_id": str(item.closet_item_id),
                        "category": projection.category if projection is not None else None,
                        "sort_index": item.sort_index,
                    }
                )
            snapshot_items_by_log[wear_log.id] = sorted(
                fallback_items,
                key=lambda snapshot_item: self._coerce_int(
                    snapshot_item.get("sort_index"),
                    default=0,
                ),
            )
        return snapshot_items_by_log

    def _snapshot_items_from_json(self, payload: object) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        items = [item for item in payload if isinstance(item, dict)]
        return sorted(
            items,
            key=lambda item: self._coerce_int(item.get("sort_index"), default=0),
        )

    def _normalize_category(self, value: object) -> str:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        return "unknown"

    def _snapshot_item_id(self, payload: dict[str, object]) -> UUID | None:
        value = payload.get("closet_item_id")
        if not isinstance(value, str):
            return None
        try:
            return UUID(value)
        except ValueError:
            return None

    def _coerce_int(self, value: object, *, default: int) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        return default

    def _validate_date_range(
        self,
        *,
        start_date: date,
        end_date: date,
        max_days: int | None = None,
        message: str = "end_date must be on or after start_date.",
    ) -> None:
        if end_date < start_date:
            raise InsightServiceError(422, "end_date must be on or after start_date.")
        if max_days is not None and (end_date - start_date).days + 1 > max_days:
            raise InsightServiceError(422, message)


def encode_insight_cursor(offset: int) -> str:
    payload = str(offset)
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_insight_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0

    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        offset = int(decoded)
        return max(offset, 0)
    except (ValueError, TypeError) as exc:
        raise InvalidInsightCursorError("Invalid insight cursor.") from exc
