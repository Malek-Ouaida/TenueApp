from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.domains.closet.models import (
    ClosetItem,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetItemMetadataProjection,
    LifecycleStatus,
    MediaAsset,
    ReviewStatus,
)
from app.domains.wear.models import (
    Outfit,
    OutfitItem,
    OutfitSeason,
    OutfitSource,
    WearContext,
    WearLog,
    WearLogItem,
    WearLogSnapshot,
    WearLogSource,
)


class WearRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_outfit(
        self,
        *,
        user_id: UUID,
        title: str | None,
        notes: str | None,
        occasion: WearContext | None,
        season: OutfitSeason | None,
        source: OutfitSource,
        is_favorite: bool,
    ) -> Outfit:
        outfit = Outfit(
            user_id=user_id,
            title=title,
            notes=notes,
            occasion=occasion,
            season=season,
            source=source,
            is_favorite=is_favorite,
        )
        self.session.add(outfit)
        self.session.flush()
        return outfit

    def get_outfit_for_user(self, *, outfit_id: UUID, user_id: UUID) -> Outfit | None:
        statement = select(Outfit).where(
            Outfit.id == outfit_id,
            Outfit.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_outfits_for_user(
        self,
        *,
        outfit_ids: list[UUID],
        user_id: UUID,
    ) -> dict[UUID, Outfit]:
        if not outfit_ids:
            return {}
        statement = select(Outfit).where(
            Outfit.user_id == user_id,
            Outfit.id.in_(outfit_ids),
        )
        return {outfit.id: outfit for outfit in self.session.execute(statement).scalars()}

    def list_outfits(
        self,
        *,
        user_id: UUID,
        offset: int,
        limit: int,
        occasion: WearContext | None,
        season: OutfitSeason | None,
        is_favorite: bool | None,
        source: OutfitSource | None,
        include_archived: bool,
    ) -> list[Outfit]:
        statement = select(Outfit).where(Outfit.user_id == user_id)

        if not include_archived:
            statement = statement.where(Outfit.archived_at.is_(None))

        if occasion is not None:
            statement = statement.where(Outfit.occasion == occasion)
        if season is not None:
            statement = statement.where(Outfit.season == season)
        if is_favorite is not None:
            statement = statement.where(Outfit.is_favorite.is_(is_favorite))
        if source is not None:
            statement = statement.where(Outfit.source == source)

        statement = statement.order_by(
            Outfit.updated_at.desc(),
            Outfit.created_at.desc(),
            Outfit.id.desc(),
        ).offset(offset).limit(limit)
        return list(self.session.execute(statement).scalars())

    def create_outfit_items(
        self,
        *,
        outfit_id: UUID,
        items: list[dict[str, object]],
    ) -> list[OutfitItem]:
        created: list[OutfitItem] = []
        for item in items:
            outfit_item = OutfitItem(
                outfit_id=outfit_id,
                closet_item_id=item["closet_item_id"],
                role=item["role"],
                layer_index=item["layer_index"],
                sort_index=item["sort_index"],
                is_optional=item["is_optional"],
            )
            self.session.add(outfit_item)
            created.append(outfit_item)
        self.session.flush()
        return created

    def replace_outfit_items(
        self,
        *,
        outfit_id: UUID,
        items: list[dict[str, object]],
    ) -> list[OutfitItem]:
        self.session.execute(delete(OutfitItem).where(OutfitItem.outfit_id == outfit_id))
        self.session.flush()
        return self.create_outfit_items(outfit_id=outfit_id, items=items)

    def list_outfit_items(self, *, outfit_id: UUID) -> list[OutfitItem]:
        statement = (
            select(OutfitItem)
            .where(OutfitItem.outfit_id == outfit_id)
            .order_by(OutfitItem.sort_index.asc(), OutfitItem.id.asc())
        )
        return list(self.session.execute(statement).scalars())

    def list_outfit_items_for_outfits(
        self,
        *,
        outfit_ids: list[UUID],
    ) -> dict[UUID, list[OutfitItem]]:
        if not outfit_ids:
            return {}

        statement = (
            select(OutfitItem)
            .where(OutfitItem.outfit_id.in_(outfit_ids))
            .order_by(OutfitItem.outfit_id.asc(), OutfitItem.sort_index.asc(), OutfitItem.id.asc())
        )
        items_by_outfit: dict[UUID, list[OutfitItem]] = {}
        for item in self.session.execute(statement).scalars():
            items_by_outfit.setdefault(item.outfit_id, []).append(item)
        return items_by_outfit

    def create_wear_log(
        self,
        *,
        user_id: UUID,
        wear_date: date,
        outfit_id: UUID | None,
        source: WearLogSource,
        context: WearContext | None,
        notes: str | None,
        is_confirmed: bool,
    ) -> WearLog:
        wear_log = WearLog(
            user_id=user_id,
            wear_date=wear_date,
            outfit_id=outfit_id,
            source=source,
            context=context,
            notes=notes,
            is_confirmed=is_confirmed,
        )
        self.session.add(wear_log)
        self.session.flush()
        return wear_log

    def get_wear_log_for_user(self, *, wear_log_id: UUID, user_id: UUID) -> WearLog | None:
        statement = select(WearLog).where(
            WearLog.id == wear_log_id,
            WearLog.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_wear_log_by_date_for_user(
        self,
        *,
        user_id: UUID,
        wear_date: date,
        exclude_wear_log_id: UUID | None = None,
    ) -> WearLog | None:
        statement = select(WearLog).where(
            WearLog.user_id == user_id,
            WearLog.wear_date == wear_date,
        )
        if exclude_wear_log_id is not None:
            statement = statement.where(WearLog.id != exclude_wear_log_id)
        return self.session.execute(statement).scalar_one_or_none()

    def list_wear_logs(
        self,
        *,
        user_id: UUID,
        cursor_wear_date: date | None,
        cursor_created_at: datetime | None,
        cursor_wear_log_id: UUID | None,
        limit: int,
    ) -> list[WearLog]:
        normalized_cursor_created_at = self._normalize_cursor_datetime(cursor_created_at)
        statement = select(WearLog).where(WearLog.user_id == user_id)

        if (
            cursor_wear_date is not None
            and normalized_cursor_created_at is not None
            and cursor_wear_log_id is not None
        ):
            statement = statement.where(
                or_(
                    WearLog.wear_date < cursor_wear_date,
                    and_(
                        WearLog.wear_date == cursor_wear_date,
                        WearLog.created_at < normalized_cursor_created_at,
                    ),
                    and_(
                        WearLog.wear_date == cursor_wear_date,
                        WearLog.created_at == normalized_cursor_created_at,
                        WearLog.id < cursor_wear_log_id,
                    ),
                )
            )

        statement = statement.order_by(
            WearLog.wear_date.desc(),
            WearLog.created_at.desc(),
            WearLog.id.desc(),
        ).limit(limit)
        return list(self.session.execute(statement).scalars())

    def list_wear_logs_in_range(
        self,
        *,
        user_id: UUID,
        start_date: date,
        end_date: date,
        confirmed_only: bool = False,
    ) -> list[WearLog]:
        statement = (
            select(WearLog)
            .where(
                WearLog.user_id == user_id,
                WearLog.wear_date >= start_date,
                WearLog.wear_date <= end_date,
            )
            .order_by(WearLog.wear_date.asc(), WearLog.created_at.asc(), WearLog.id.asc())
        )
        if confirmed_only:
            statement = statement.where(WearLog.is_confirmed.is_(True))
        return list(self.session.execute(statement).scalars())

    def create_wear_log_items(
        self,
        *,
        wear_log_id: UUID,
        items: list[dict[str, object]],
    ) -> list[WearLogItem]:
        created: list[WearLogItem] = []
        for item in items:
            wear_log_item = WearLogItem(
                wear_log_id=wear_log_id,
                closet_item_id=item["closet_item_id"],
                source=item["source"],
                match_confidence=item["match_confidence"],
                sort_index=item["sort_index"],
                role=item["role"],
            )
            self.session.add(wear_log_item)
            created.append(wear_log_item)
        self.session.flush()
        return created

    def replace_wear_log_items(
        self,
        *,
        wear_log_id: UUID,
        items: list[dict[str, object]],
    ) -> list[WearLogItem]:
        self.session.execute(delete(WearLogItem).where(WearLogItem.wear_log_id == wear_log_id))
        self.session.flush()
        return self.create_wear_log_items(wear_log_id=wear_log_id, items=items)

    def list_wear_log_items(self, *, wear_log_id: UUID) -> list[WearLogItem]:
        statement = (
            select(WearLogItem)
            .where(WearLogItem.wear_log_id == wear_log_id)
            .order_by(WearLogItem.sort_index.asc(), WearLogItem.id.asc())
        )
        return list(self.session.execute(statement).scalars())

    def list_wear_log_items_for_logs(
        self,
        *,
        wear_log_ids: list[UUID],
    ) -> dict[UUID, list[WearLogItem]]:
        if not wear_log_ids:
            return {}

        statement = (
            select(WearLogItem)
            .where(WearLogItem.wear_log_id.in_(wear_log_ids))
            .order_by(
                WearLogItem.wear_log_id.asc(),
                WearLogItem.sort_index.asc(),
                WearLogItem.id.asc(),
            )
        )
        items_by_log: dict[UUID, list[WearLogItem]] = {}
        for item in self.session.execute(statement).scalars():
            items_by_log.setdefault(item.wear_log_id, []).append(item)
        return items_by_log

    def get_wear_log_snapshot(self, *, wear_log_id: UUID) -> WearLogSnapshot | None:
        statement = select(WearLogSnapshot).where(WearLogSnapshot.wear_log_id == wear_log_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_wear_log_snapshots_for_logs(
        self,
        *,
        wear_log_ids: list[UUID],
    ) -> dict[UUID, WearLogSnapshot]:
        if not wear_log_ids:
            return {}
        statement = select(WearLogSnapshot).where(WearLogSnapshot.wear_log_id.in_(wear_log_ids))
        return {
            snapshot.wear_log_id: snapshot for snapshot in self.session.execute(statement).scalars()
        }

    def upsert_wear_log_snapshot(
        self,
        *,
        wear_log_id: UUID,
        items_snapshot_json: list[dict[str, object]],
        outfit_title_snapshot: str | None,
    ) -> WearLogSnapshot:
        snapshot = self.get_wear_log_snapshot(wear_log_id=wear_log_id)
        if snapshot is None:
            snapshot = WearLogSnapshot(
                wear_log_id=wear_log_id,
                outfit_title_snapshot=outfit_title_snapshot,
                items_snapshot_json=items_snapshot_json,
            )
            self.session.add(snapshot)
        else:
            snapshot.outfit_title_snapshot = outfit_title_snapshot
            snapshot.items_snapshot_json = items_snapshot_json
        self.session.flush()
        return snapshot

    def delete_wear_log(self, *, wear_log: WearLog) -> None:
        self.session.execute(delete(WearLogItem).where(WearLogItem.wear_log_id == wear_log.id))
        self.session.execute(
            delete(WearLogSnapshot).where(WearLogSnapshot.wear_log_id == wear_log.id)
        )
        self.session.delete(wear_log)
        self.session.flush()

    def get_confirmed_closet_items_with_projections_for_user(
        self,
        *,
        item_ids: list[UUID],
        user_id: UUID,
    ) -> dict[UUID, tuple[ClosetItem, ClosetItemMetadataProjection]]:
        if not item_ids:
            return {}

        statement = (
            select(ClosetItem, ClosetItemMetadataProjection)
            .join(
                ClosetItemMetadataProjection,
                ClosetItemMetadataProjection.closet_item_id == ClosetItem.id,
            )
            .where(
                ClosetItem.id.in_(item_ids),
                ClosetItem.user_id == user_id,
                ClosetItem.lifecycle_status == LifecycleStatus.CONFIRMED,
                ClosetItem.review_status == ReviewStatus.CONFIRMED,
                ClosetItem.confirmed_at.is_not(None),
                ClosetItemMetadataProjection.user_id == user_id,
            )
        )
        return {
            item.id: (item, projection)
            for item, projection in self.session.execute(statement).all()
        }

    def get_closet_items_with_projections_for_user(
        self,
        *,
        item_ids: list[UUID],
        user_id: UUID,
    ) -> dict[UUID, tuple[ClosetItem, ClosetItemMetadataProjection]]:
        if not item_ids:
            return {}

        statement = (
            select(ClosetItem, ClosetItemMetadataProjection)
            .join(
                ClosetItemMetadataProjection,
                ClosetItemMetadataProjection.closet_item_id == ClosetItem.id,
            )
            .where(
                ClosetItem.id.in_(item_ids),
                ClosetItem.user_id == user_id,
                ClosetItemMetadataProjection.user_id == user_id,
            )
        )
        return {
            item.id: (item, projection)
            for item, projection in self.session.execute(statement).all()
        }

    def list_active_image_assets_for_items(
        self,
        *,
        closet_item_ids: list[UUID],
        roles: list[ClosetItemImageRole],
    ) -> dict[UUID, dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]]]:
        if not closet_item_ids or not roles:
            return {}

        statement = (
            select(ClosetItemImage, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ClosetItemImage.asset_id)
            .where(
                ClosetItemImage.closet_item_id.in_(closet_item_ids),
                ClosetItemImage.role.in_(roles),
                ClosetItemImage.is_active.is_(True),
            )
            .order_by(
                ClosetItemImage.closet_item_id.asc(),
                ClosetItemImage.role.asc(),
                ClosetItemImage.position.asc(),
                ClosetItemImage.created_at.desc(),
                ClosetItemImage.id.desc(),
            )
        )

        images_by_item: dict[
            UUID, dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]]
        ] = {}
        for item_image, asset in self.session.execute(statement).all():
            item_images = images_by_item.setdefault(item_image.closet_item_id, {})
            if item_image.role not in item_images:
                item_images[item_image.role] = (item_image, asset)
        return images_by_item

    def get_media_assets_by_ids(self, *, asset_ids: list[UUID]) -> dict[UUID, MediaAsset]:
        if not asset_ids:
            return {}
        statement = select(MediaAsset).where(MediaAsset.id.in_(asset_ids))
        return {asset.id: asset for asset in self.session.execute(statement).scalars()}

    def count_active_confirmed_closet_items(self, *, user_id: UUID) -> int:
        statement = select(func.count(ClosetItem.id)).where(
            *self._active_confirmed_closet_item_filters(user_id=user_id)
        )
        return int(self.session.execute(statement).scalar_one())

    def count_never_worn_active_confirmed_closet_items(self, *, user_id: UUID) -> int:
        wear_exists = (
            select(1)
            .select_from(WearLogItem)
            .join(WearLog, WearLog.id == WearLogItem.wear_log_id)
            .where(
                WearLogItem.closet_item_id == ClosetItem.id,
                WearLog.user_id == user_id,
                WearLog.is_confirmed.is_(True),
            )
            .correlate(ClosetItem)
        )
        statement = select(func.count(ClosetItem.id)).where(
            *self._active_confirmed_closet_item_filters(user_id=user_id),
            ~exists(wear_exists),
        )
        return int(self.session.execute(statement).scalar_one())

    def get_wear_activity_aggregate(
        self,
        *,
        user_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[int, int, int]:
        wear_log_count = func.count(func.distinct(WearLog.id))
        worn_item_count = func.count(WearLogItem.id)
        unique_items_worn = func.count(func.distinct(WearLogItem.closet_item_id))

        statement = (
            select(wear_log_count, worn_item_count, unique_items_worn)
            .select_from(WearLog)
            .outerjoin(WearLogItem, WearLogItem.wear_log_id == WearLog.id)
            .where(
                WearLog.user_id == user_id,
                WearLog.is_confirmed.is_(True),
            )
        )
        if start_date is not None:
            statement = statement.where(WearLog.wear_date >= start_date)
        if end_date is not None:
            statement = statement.where(WearLog.wear_date <= end_date)

        row = self.session.execute(statement).one()
        return (
            int(row[0] or 0),
            int(row[1] or 0),
            int(row[2] or 0),
        )

    def count_active_confirmed_items_worn_in_range(
        self,
        *,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> int:
        statement = (
            select(func.count(func.distinct(WearLogItem.closet_item_id)))
            .select_from(WearLogItem)
            .join(WearLog, WearLog.id == WearLogItem.wear_log_id)
            .join(ClosetItem, ClosetItem.id == WearLogItem.closet_item_id)
            .where(
                WearLog.user_id == user_id,
                WearLog.is_confirmed.is_(True),
                WearLog.wear_date >= start_date,
                WearLog.wear_date <= end_date,
                *self._active_confirmed_closet_item_filters(user_id=user_id),
            )
        )
        return int(self.session.execute(statement).scalar_one())

    def list_confirmed_wear_dates(
        self,
        *,
        user_id: UUID,
        end_date: date,
    ) -> list[date]:
        statement = (
            select(WearLog.wear_date)
            .where(
                WearLog.user_id == user_id,
                WearLog.is_confirmed.is_(True),
                WearLog.wear_date <= end_date,
            )
            .distinct()
            .order_by(WearLog.wear_date.asc())
        )
        return list(self.session.execute(statement).scalars())

    def list_item_usage(
        self,
        *,
        user_id: UUID,
        offset: int,
        limit: int,
        sort: str,
    ) -> list[tuple[UUID, int, date, date]]:
        wear_count = func.count(WearLogItem.id).label("wear_count")
        first_worn_date = func.min(WearLog.wear_date).label("first_worn_date")
        last_worn_date = func.max(WearLog.wear_date).label("last_worn_date")

        statement = (
            select(
                WearLogItem.closet_item_id,
                wear_count,
                first_worn_date,
                last_worn_date,
            )
            .select_from(WearLogItem)
            .join(WearLog, WearLog.id == WearLogItem.wear_log_id)
            .join(ClosetItem, ClosetItem.id == WearLogItem.closet_item_id)
            .where(
                WearLog.user_id == user_id,
                WearLog.is_confirmed.is_(True),
                *self._active_confirmed_closet_item_filters(user_id=user_id),
            )
            .group_by(WearLogItem.closet_item_id)
        )
        if sort == "least_worn":
            statement = statement.order_by(
                wear_count.asc(),
                last_worn_date.asc(),
                WearLogItem.closet_item_id.asc(),
            )
        else:
            statement = statement.order_by(
                wear_count.desc(),
                last_worn_date.desc(),
                WearLogItem.closet_item_id.asc(),
            )

        rows = self.session.execute(statement.offset(offset).limit(limit)).all()
        return [
            (
                row[0],
                int(row[1]),
                row[2],
                row[3],
            )
            for row in rows
        ]

    def list_outfit_usage(
        self,
        *,
        user_id: UUID,
        offset: int,
        limit: int,
    ) -> list[tuple[UUID, int, date, date]]:
        wear_count = func.count(WearLog.id).label("wear_count")
        first_worn_date = func.min(WearLog.wear_date).label("first_worn_date")
        last_worn_date = func.max(WearLog.wear_date).label("last_worn_date")

        statement = (
            select(
                WearLog.outfit_id,
                wear_count,
                first_worn_date,
                last_worn_date,
            )
            .select_from(WearLog)
            .join(Outfit, Outfit.id == WearLog.outfit_id)
            .where(
                WearLog.user_id == user_id,
                WearLog.is_confirmed.is_(True),
                WearLog.outfit_id.is_not(None),
                Outfit.user_id == user_id,
            )
            .group_by(WearLog.outfit_id)
            .order_by(
                wear_count.desc(),
                last_worn_date.desc(),
                WearLog.outfit_id.asc(),
            )
        )
        rows = self.session.execute(statement.offset(offset).limit(limit)).all()
        return [
            (
                row[0],
                int(row[1]),
                row[2],
                row[3],
            )
            for row in rows
            if row[0] is not None
        ]

    def list_stale_item_usage(
        self,
        *,
        user_id: UUID,
        cutoff_date: date,
        offset: int,
        limit: int,
    ) -> list[tuple[UUID, int, date, date]]:
        wear_count = func.count(WearLogItem.id).label("wear_count")
        first_worn_date = func.min(WearLog.wear_date).label("first_worn_date")
        last_worn_date = func.max(WearLog.wear_date).label("last_worn_date")

        statement = (
            select(
                WearLogItem.closet_item_id,
                wear_count,
                first_worn_date,
                last_worn_date,
            )
            .select_from(WearLogItem)
            .join(WearLog, WearLog.id == WearLogItem.wear_log_id)
            .join(ClosetItem, ClosetItem.id == WearLogItem.closet_item_id)
            .where(
                WearLog.user_id == user_id,
                WearLog.is_confirmed.is_(True),
                *self._active_confirmed_closet_item_filters(user_id=user_id),
            )
            .group_by(WearLogItem.closet_item_id)
            .having(last_worn_date < cutoff_date)
            .order_by(
                last_worn_date.asc(),
                wear_count.desc(),
                WearLogItem.closet_item_id.asc(),
            )
        )
        rows = self.session.execute(statement.offset(offset).limit(limit)).all()
        return [
            (
                row[0],
                int(row[1]),
                row[2],
                row[3],
            )
            for row in rows
        ]

    def list_never_worn_items(
        self,
        *,
        user_id: UUID,
        offset: int,
        limit: int,
    ) -> list[tuple[UUID, datetime]]:
        wear_exists = (
            select(1)
            .select_from(WearLogItem)
            .join(WearLog, WearLog.id == WearLogItem.wear_log_id)
            .where(
                WearLogItem.closet_item_id == ClosetItem.id,
                WearLog.user_id == user_id,
                WearLog.is_confirmed.is_(True),
            )
            .correlate(ClosetItem)
        )
        statement = (
            select(ClosetItem.id, ClosetItem.confirmed_at)
            .where(
                *self._active_confirmed_closet_item_filters(user_id=user_id),
                ~exists(wear_exists),
            )
            .order_by(ClosetItem.confirmed_at.desc(), ClosetItem.id.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = self.session.execute(statement).all()
        return [(row[0], row[1]) for row in rows if row[1] is not None]

    def _normalize_cursor_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _active_confirmed_closet_item_filters(
        self,
        *,
        user_id: UUID,
    ) -> tuple[ColumnElement[bool], ...]:
        return (
            ClosetItem.user_id == user_id,
            ClosetItem.lifecycle_status == LifecycleStatus.CONFIRMED,
            ClosetItem.review_status == ReviewStatus.CONFIRMED,
            ClosetItem.confirmed_at.is_not(None),
        )
