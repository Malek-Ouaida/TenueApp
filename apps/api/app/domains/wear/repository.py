from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

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
    WearContext,
    WearLog,
    WearLogItem,
    WearLogSnapshot,
    WearLogSource,
)


class WearRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_wear_log(
        self,
        *,
        user_id: UUID,
        wear_date: date,
        source: WearLogSource,
        context: WearContext | None,
        notes: str | None,
        is_confirmed: bool,
    ) -> WearLog:
        wear_log = WearLog(
            user_id=user_id,
            wear_date=wear_date,
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
            snapshot.wear_log_id: snapshot
            for snapshot in self.session.execute(statement).scalars()
        }

    def upsert_wear_log_snapshot(
        self,
        *,
        wear_log_id: UUID,
        items_snapshot_json: list[dict[str, object]],
    ) -> WearLogSnapshot:
        snapshot = self.get_wear_log_snapshot(wear_log_id=wear_log_id)
        if snapshot is None:
            snapshot = WearLogSnapshot(
                wear_log_id=wear_log_id,
                items_snapshot_json=items_snapshot_json,
            )
            self.session.add(snapshot)
        else:
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

    def _normalize_cursor_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
