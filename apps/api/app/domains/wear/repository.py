from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, delete, exists, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import settings
from app.domains.closet.models import (
    ClosetItem,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetItemMetadataProjection,
    LifecycleStatus,
    MediaAsset,
    MediaAssetSourceKind,
    ReviewStatus,
)
from app.domains.wear.models import (
    Outfit,
    OutfitItem,
    OutfitSeason,
    OutfitSource,
    WearContext,
    WearDetectedItemStatus,
    WearEventDetectedItem,
    WearEventJob,
    WearEventMatchCandidate,
    WearEventPhoto,
    WearEventProcessingRun,
    WearEventProviderResult,
    WearEventUploadIntent,
    WearItemSource,
    WearJobStatus,
    WearLog,
    WearLogItem,
    WearLogSnapshot,
    WearLogSource,
    WearLogStatus,
    WearProcessingRunType,
    WearProcessingStatus,
    WearTimePrecision,
    WearUploadIntentStatus,
    utcnow,
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
        worn_at: datetime,
        worn_time_precision: WearTimePrecision,
        captured_at: datetime | None,
        timezone_name: str | None,
        outfit_id: UUID | None,
        source: WearLogSource,
        status: WearLogStatus,
        context: WearContext | None,
        vibe: str | None,
        notes: str | None,
        is_confirmed: bool,
        confirmed_at: datetime | None,
        confirmed_item_count: int,
        combination_fingerprint: str | None,
        primary_photo_id: UUID | None = None,
        failure_code: str | None = None,
        failure_summary: str | None = None,
    ) -> WearLog:
        wear_log = WearLog(
            user_id=user_id,
            wear_date=wear_date,
            worn_at=self._normalize_datetime(worn_at),
            worn_time_precision=worn_time_precision,
            captured_at=self._normalize_datetime(captured_at),
            timezone_name=timezone_name,
            outfit_id=outfit_id,
            source=source,
            status=status,
            context=context,
            vibe=vibe,
            notes=notes,
            is_confirmed=is_confirmed,
            confirmed_at=self._normalize_datetime(confirmed_at),
            primary_photo_id=primary_photo_id,
            confirmed_item_count=confirmed_item_count,
            combination_fingerprint=combination_fingerprint,
            failure_code=failure_code,
            failure_summary=failure_summary,
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

    def list_wear_logs(
        self,
        *,
        user_id: UUID,
        cursor_worn_at: datetime | None,
        cursor_created_at: datetime | None,
        cursor_wear_log_id: UUID | None,
        limit: int,
        wear_date: date | None = None,
        status: WearLogStatus | None = None,
        include_archived: bool = False,
    ) -> list[WearLog]:
        normalized_cursor_worn_at = self._normalize_datetime(cursor_worn_at)
        normalized_cursor_created_at = self._normalize_datetime(cursor_created_at)
        statement = select(WearLog).where(WearLog.user_id == user_id)

        if not include_archived:
            statement = statement.where(WearLog.archived_at.is_(None))
        if wear_date is not None:
            statement = statement.where(WearLog.wear_date == wear_date)
        if status is not None:
            statement = statement.where(WearLog.status == status)

        if (
            normalized_cursor_worn_at is not None
            and normalized_cursor_created_at is not None
            and cursor_wear_log_id is not None
        ):
            statement = statement.where(
                or_(
                    WearLog.worn_at < normalized_cursor_worn_at,
                    and_(
                        WearLog.worn_at == normalized_cursor_worn_at,
                        WearLog.created_at < normalized_cursor_created_at,
                    ),
                    and_(
                        WearLog.worn_at == normalized_cursor_worn_at,
                        WearLog.created_at == normalized_cursor_created_at,
                        WearLog.id < cursor_wear_log_id,
                    ),
                )
            )

        statement = statement.order_by(
            WearLog.worn_at.desc(),
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
        include_archived: bool = False,
    ) -> list[WearLog]:
        statement = select(WearLog).where(
            WearLog.user_id == user_id,
            WearLog.wear_date >= start_date,
            WearLog.wear_date <= end_date,
        )
        if not include_archived:
            statement = statement.where(WearLog.archived_at.is_(None))
        if confirmed_only:
            statement = statement.where(
                WearLog.status == WearLogStatus.CONFIRMED,
                WearLog.is_confirmed.is_(True),
            )
        statement = statement.order_by(
            WearLog.wear_date.asc(),
            WearLog.worn_at.asc(),
            WearLog.created_at.asc(),
            WearLog.id.asc(),
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
                detected_item_id=item.get("detected_item_id"),
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

    def create_wear_event_photo(
        self,
        *,
        wear_log_id: UUID,
        asset_id: UUID,
        thumbnail_asset_id: UUID | None,
        position: int,
    ) -> WearEventPhoto:
        photo = WearEventPhoto(
            wear_log_id=wear_log_id,
            asset_id=asset_id,
            thumbnail_asset_id=thumbnail_asset_id,
            position=position,
            is_active=True,
        )
        self.session.add(photo)
        self.session.flush()
        return photo

    def list_active_wear_event_photos(self, *, wear_log_id: UUID) -> list[WearEventPhoto]:
        statement = (
            select(WearEventPhoto)
            .where(
                WearEventPhoto.wear_log_id == wear_log_id,
                WearEventPhoto.is_active.is_(True),
            )
            .order_by(WearEventPhoto.position.asc(), WearEventPhoto.created_at.asc())
        )
        return list(self.session.execute(statement).scalars())

    def list_active_wear_event_photos_for_logs(
        self,
        *,
        wear_log_ids: list[UUID],
    ) -> dict[UUID, list[WearEventPhoto]]:
        if not wear_log_ids:
            return {}
        statement = (
            select(WearEventPhoto)
            .where(
                WearEventPhoto.wear_log_id.in_(wear_log_ids),
                WearEventPhoto.is_active.is_(True),
            )
            .order_by(
                WearEventPhoto.wear_log_id.asc(),
                WearEventPhoto.position.asc(),
                WearEventPhoto.created_at.asc(),
            )
        )
        photos_by_log: dict[UUID, list[WearEventPhoto]] = {}
        for photo in self.session.execute(statement).scalars():
            photos_by_log.setdefault(photo.wear_log_id, []).append(photo)
        return photos_by_log

    def get_wear_event_photo(self, *, photo_id: UUID) -> WearEventPhoto | None:
        statement = select(WearEventPhoto).where(WearEventPhoto.id == photo_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_next_photo_position(self, *, wear_log_id: UUID) -> int:
        statement = select(func.max(WearEventPhoto.position)).where(
            WearEventPhoto.wear_log_id == wear_log_id,
            WearEventPhoto.is_active.is_(True),
        )
        value = self.session.execute(statement).scalar_one()
        return int(value or -1) + 1

    def create_upload_intent(
        self,
        *,
        upload_intent_id: UUID,
        wear_log_id: UUID,
        user_id: UUID,
        filename: str,
        mime_type: str,
        file_size: int,
        sha256: str,
        staging_bucket: str,
        staging_key: str,
        expires_at: datetime,
    ) -> WearEventUploadIntent:
        upload_intent = WearEventUploadIntent(
            id=upload_intent_id,
            wear_log_id=wear_log_id,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            sha256=sha256,
            staging_bucket=staging_bucket,
            staging_key=staging_key,
            expires_at=self._normalize_datetime(expires_at),
        )
        self.session.add(upload_intent)
        self.session.flush()
        return upload_intent

    def get_pending_upload_intent_for_log(
        self,
        *,
        wear_log_id: UUID,
    ) -> WearEventUploadIntent | None:
        statement = (
            select(WearEventUploadIntent)
            .where(
                WearEventUploadIntent.wear_log_id == wear_log_id,
                WearEventUploadIntent.status == WearUploadIntentStatus.PENDING,
            )
            .order_by(WearEventUploadIntent.created_at.desc(), WearEventUploadIntent.id.desc())
        )
        return self.session.execute(statement).scalars().first()

    def get_upload_intent_for_user(
        self,
        *,
        upload_intent_id: UUID,
        user_id: UUID,
    ) -> WearEventUploadIntent | None:
        statement = select(WearEventUploadIntent).where(
            WearEventUploadIntent.id == upload_intent_id,
            WearEventUploadIntent.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def mark_upload_intent_expired(
        self,
        *,
        upload_intent: WearEventUploadIntent,
    ) -> WearEventUploadIntent:
        upload_intent.status = WearUploadIntentStatus.EXPIRED
        self.session.flush()
        return upload_intent

    def mark_upload_intent_failed(
        self,
        *,
        upload_intent: WearEventUploadIntent,
        error_code: str,
        error_detail: str,
    ) -> WearEventUploadIntent:
        upload_intent.status = WearUploadIntentStatus.FAILED
        upload_intent.last_error_code = error_code
        upload_intent.last_error_detail = error_detail
        self.session.flush()
        return upload_intent

    def mark_upload_intent_finalized(
        self,
        *,
        upload_intent: WearEventUploadIntent,
        finalized_at: datetime,
    ) -> WearEventUploadIntent:
        upload_intent.status = WearUploadIntentStatus.FINALIZED
        upload_intent.finalized_at = self._normalize_datetime(finalized_at)
        self.session.flush()
        return upload_intent

    def list_expired_pending_upload_intents(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[WearEventUploadIntent]:
        statement = (
            select(WearEventUploadIntent)
            .where(
                WearEventUploadIntent.status == WearUploadIntentStatus.PENDING,
                WearEventUploadIntent.expires_at <= self._normalize_datetime(now),
            )
            .order_by(WearEventUploadIntent.expires_at.asc(), WearEventUploadIntent.id.asc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars())

    def create_processing_run(
        self,
        *,
        wear_log_id: UUID,
        run_type: WearProcessingRunType,
        status: WearProcessingStatus,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        failure_code: str | None = None,
        failure_payload: Any | None = None,
    ) -> WearEventProcessingRun:
        run = WearEventProcessingRun(
            wear_log_id=wear_log_id,
            run_type=run_type,
            status=status,
            started_at=self._normalize_datetime(started_at),
            completed_at=self._normalize_datetime(completed_at),
            failure_code=failure_code,
            failure_payload=failure_payload,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def get_latest_processing_run(
        self,
        *,
        wear_log_id: UUID,
        run_type: WearProcessingRunType,
    ) -> WearEventProcessingRun | None:
        statement = (
            select(WearEventProcessingRun)
            .where(
                WearEventProcessingRun.wear_log_id == wear_log_id,
                WearEventProcessingRun.run_type == run_type,
            )
            .order_by(WearEventProcessingRun.created_at.desc(), WearEventProcessingRun.id.desc())
        )
        return self.session.execute(statement).scalars().first()

    def create_provider_result(
        self,
        *,
        wear_log_id: UUID,
        processing_run_id: UUID | None,
        provider_name: str,
        provider_model: str | None,
        provider_version: str | None,
        task_type: str,
        status: Any,
        raw_payload: Any,
    ) -> WearEventProviderResult:
        result = WearEventProviderResult(
            wear_log_id=wear_log_id,
            processing_run_id=processing_run_id,
            provider_name=provider_name,
            provider_model=provider_model,
            provider_version=provider_version,
            task_type=task_type,
            status=status,
            raw_payload=raw_payload,
        )
        self.session.add(result)
        self.session.flush()
        return result

    def clear_detected_items_for_log(self, *, wear_log_id: UUID) -> None:
        detected_ids_statement = select(WearEventDetectedItem.id).where(
            WearEventDetectedItem.wear_log_id == wear_log_id
        )
        detected_ids = list(self.session.execute(detected_ids_statement).scalars())
        if detected_ids:
            self.session.execute(
                delete(WearEventMatchCandidate).where(
                    WearEventMatchCandidate.detected_item_id.in_(detected_ids)
                )
            )
        self.session.execute(
            delete(WearEventDetectedItem).where(WearEventDetectedItem.wear_log_id == wear_log_id)
        )
        self.session.flush()

    def create_detected_item(
        self,
        *,
        wear_log_id: UUID,
        processing_run_id: UUID | None,
        sort_index: int,
        predicted_role: Any | None,
        predicted_category: str | None,
        predicted_subcategory: str | None,
        predicted_colors_json: list[str] | None,
        predicted_material: str | None,
        predicted_pattern: str | None,
        predicted_fit_tags_json: list[str] | None,
        predicted_silhouette: str | None,
        predicted_attributes_json: list[str] | None,
        confidence: float | None,
        bbox_json: dict[str, float] | None,
        crop_asset_id: UUID | None,
        status: WearDetectedItemStatus = WearDetectedItemStatus.DETECTED,
        exclusion_reason: str | None = None,
    ) -> WearEventDetectedItem:
        detected_item = WearEventDetectedItem(
            wear_log_id=wear_log_id,
            processing_run_id=processing_run_id,
            sort_index=sort_index,
            predicted_role=predicted_role,
            predicted_category=predicted_category,
            predicted_subcategory=predicted_subcategory,
            predicted_colors_json=predicted_colors_json,
            predicted_material=predicted_material,
            predicted_pattern=predicted_pattern,
            predicted_fit_tags_json=predicted_fit_tags_json,
            predicted_silhouette=predicted_silhouette,
            predicted_attributes_json=predicted_attributes_json,
            confidence=confidence,
            bbox_json=bbox_json,
            crop_asset_id=crop_asset_id,
            status=status,
            exclusion_reason=exclusion_reason,
        )
        self.session.add(detected_item)
        self.session.flush()
        return detected_item

    def list_detected_items(self, *, wear_log_id: UUID) -> list[WearEventDetectedItem]:
        statement = (
            select(WearEventDetectedItem)
            .where(WearEventDetectedItem.wear_log_id == wear_log_id)
            .order_by(WearEventDetectedItem.sort_index.asc(), WearEventDetectedItem.id.asc())
        )
        return list(self.session.execute(statement).scalars())

    def list_detected_items_for_logs(
        self,
        *,
        wear_log_ids: list[UUID],
    ) -> dict[UUID, list[WearEventDetectedItem]]:
        if not wear_log_ids:
            return {}
        statement = (
            select(WearEventDetectedItem)
            .where(WearEventDetectedItem.wear_log_id.in_(wear_log_ids))
            .order_by(
                WearEventDetectedItem.wear_log_id.asc(),
                WearEventDetectedItem.sort_index.asc(),
                WearEventDetectedItem.id.asc(),
            )
        )
        items_by_log: dict[UUID, list[WearEventDetectedItem]] = {}
        for item in self.session.execute(statement).scalars():
            items_by_log.setdefault(item.wear_log_id, []).append(item)
        return items_by_log

    def get_detected_item(self, *, detected_item_id: UUID) -> WearEventDetectedItem | None:
        statement = select(WearEventDetectedItem).where(WearEventDetectedItem.id == detected_item_id)
        return self.session.execute(statement).scalar_one_or_none()

    def clear_match_candidates_for_detected_item(self, *, detected_item_id: UUID) -> None:
        self.session.execute(
            delete(WearEventMatchCandidate).where(
                WearEventMatchCandidate.detected_item_id == detected_item_id
            )
        )
        self.session.flush()

    def create_match_candidate(
        self,
        *,
        detected_item_id: UUID,
        closet_item_id: UUID,
        rank: int,
        score: float,
        signals_json: Any | None,
    ) -> WearEventMatchCandidate:
        candidate = WearEventMatchCandidate(
            detected_item_id=detected_item_id,
            closet_item_id=closet_item_id,
            rank=rank,
            score=score,
            signals_json=signals_json,
        )
        self.session.add(candidate)
        self.session.flush()
        return candidate

    def list_match_candidates_for_detected_items(
        self,
        *,
        detected_item_ids: list[UUID],
    ) -> dict[UUID, list[WearEventMatchCandidate]]:
        if not detected_item_ids:
            return {}
        statement = (
            select(WearEventMatchCandidate)
            .where(WearEventMatchCandidate.detected_item_id.in_(detected_item_ids))
            .order_by(
                WearEventMatchCandidate.detected_item_id.asc(),
                WearEventMatchCandidate.rank.asc(),
                WearEventMatchCandidate.id.asc(),
            )
        )
        candidates_by_detected_item: dict[UUID, list[WearEventMatchCandidate]] = {}
        for candidate in self.session.execute(statement).scalars():
            candidates_by_detected_item.setdefault(candidate.detected_item_id, []).append(candidate)
        return candidates_by_detected_item

    def create_media_asset(
        self,
        *,
        asset_id: UUID,
        user_id: UUID,
        bucket: str,
        key: str,
        mime_type: str,
        file_size: int,
        checksum: str,
        width: int | None,
        height: int | None,
        source_kind: MediaAssetSourceKind,
        is_private: bool,
    ) -> MediaAsset:
        asset = MediaAsset(
            id=asset_id,
            user_id=user_id,
            bucket=bucket,
            key=key,
            mime_type=mime_type,
            file_size=file_size,
            checksum=checksum,
            width=width,
            height=height,
            source_kind=source_kind,
            is_private=is_private,
        )
        self.session.add(asset)
        self.session.flush()
        return asset

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
                ClosetItem.archived_at.is_(None),
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

    def list_active_confirmed_closet_items_with_projections_for_user(
        self,
        *,
        user_id: UUID,
    ) -> list[tuple[ClosetItem, ClosetItemMetadataProjection]]:
        statement = (
            select(ClosetItem, ClosetItemMetadataProjection)
            .join(
                ClosetItemMetadataProjection,
                ClosetItemMetadataProjection.closet_item_id == ClosetItem.id,
            )
            .where(
                ClosetItem.user_id == user_id,
                ClosetItem.lifecycle_status == LifecycleStatus.CONFIRMED,
                ClosetItem.review_status == ReviewStatus.CONFIRMED,
                ClosetItem.confirmed_at.is_not(None),
                ClosetItem.archived_at.is_(None),
                ClosetItemMetadataProjection.user_id == user_id,
            )
            .order_by(ClosetItem.confirmed_at.desc(), ClosetItem.id.asc())
        )
        return list(self.session.execute(statement).all())

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
                ClosetItemImage.archived_at.is_(None),
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
                *self._confirmed_wear_log_filters(user_id=user_id),
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
            .where(*self._confirmed_wear_log_filters(user_id=user_id))
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
                *self._confirmed_wear_log_filters(user_id=user_id),
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
                *self._confirmed_wear_log_filters(user_id=user_id),
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
                *self._confirmed_wear_log_filters(user_id=user_id),
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
        return [(row[0], int(row[1]), row[2], row[3]) for row in rows]

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
                *self._confirmed_wear_log_filters(user_id=user_id),
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
            (row[0], int(row[1]), row[2], row[3])
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
                *self._confirmed_wear_log_filters(user_id=user_id),
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
        return [(row[0], int(row[1]), row[2], row[3]) for row in rows]

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
                *self._confirmed_wear_log_filters(user_id=user_id),
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

    def delete_wear_log(self, *, wear_log: WearLog) -> None:
        detected_ids_statement = select(WearEventDetectedItem.id).where(
            WearEventDetectedItem.wear_log_id == wear_log.id
        )
        detected_ids = list(self.session.execute(detected_ids_statement).scalars())
        if detected_ids:
            self.session.execute(
                delete(WearEventMatchCandidate).where(
                    WearEventMatchCandidate.detected_item_id.in_(detected_ids)
                )
            )
        self.session.execute(
            delete(WearLogItem).where(WearLogItem.wear_log_id == wear_log.id)
        )
        self.session.execute(
            delete(WearLogSnapshot).where(WearLogSnapshot.wear_log_id == wear_log.id)
        )
        self.session.execute(
            delete(WearEventDetectedItem).where(WearEventDetectedItem.wear_log_id == wear_log.id)
        )
        self.session.execute(
            delete(WearEventProviderResult).where(WearEventProviderResult.wear_log_id == wear_log.id)
        )
        self.session.execute(
            delete(WearEventProcessingRun).where(WearEventProcessingRun.wear_log_id == wear_log.id)
        )
        self.session.execute(
            delete(WearEventJob).where(WearEventJob.wear_log_id == wear_log.id)
        )
        self.session.execute(
            delete(WearEventPhoto).where(WearEventPhoto.wear_log_id == wear_log.id)
        )
        self.session.execute(
            delete(WearEventUploadIntent).where(WearEventUploadIntent.wear_log_id == wear_log.id)
        )
        self.session.delete(wear_log)
        self.session.flush()

    def _normalize_datetime(self, value: datetime | None) -> datetime | None:
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
            ClosetItem.archived_at.is_(None),
        )

    def _confirmed_wear_log_filters(
        self,
        *,
        user_id: UUID,
    ) -> tuple[ColumnElement[bool], ...]:
        return (
            WearLog.user_id == user_id,
            WearLog.status == WearLogStatus.CONFIRMED,
            WearLog.is_confirmed.is_(True),
            WearLog.archived_at.is_(None),
        )


class WearJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def has_pending_or_running_job(
        self,
        *,
        wear_log_id: UUID,
        job_kind: WearProcessingRunType,
    ) -> bool:
        statement = select(WearEventJob.id).where(
            WearEventJob.wear_log_id == wear_log_id,
            WearEventJob.job_kind == job_kind,
            WearEventJob.status.in_([WearJobStatus.PENDING, WearJobStatus.RUNNING]),
        )
        return self.session.execute(statement).first() is not None

    def get_pending_or_running_job(
        self,
        *,
        wear_log_id: UUID,
        job_kind: WearProcessingRunType,
    ) -> WearEventJob | None:
        statement = (
            select(WearEventJob)
            .where(
                WearEventJob.wear_log_id == wear_log_id,
                WearEventJob.job_kind == job_kind,
                WearEventJob.status.in_([WearJobStatus.PENDING, WearJobStatus.RUNNING]),
            )
            .order_by(WearEventJob.created_at.desc(), WearEventJob.id.desc())
        )
        return self.session.execute(statement).scalars().first()

    def get_latest_job(
        self,
        *,
        wear_log_id: UUID,
        job_kind: WearProcessingRunType,
    ) -> WearEventJob | None:
        statement = (
            select(WearEventJob)
            .where(
                WearEventJob.wear_log_id == wear_log_id,
                WearEventJob.job_kind == job_kind,
            )
            .order_by(WearEventJob.created_at.desc(), WearEventJob.id.desc())
        )
        return self.session.execute(statement).scalars().first()

    def enqueue_job(
        self,
        *,
        wear_log_id: UUID,
        job_kind: WearProcessingRunType,
        payload: Any | None = None,
        available_at: datetime | None = None,
        max_attempts: int = 3,
    ) -> WearEventJob:
        job = WearEventJob(
            wear_log_id=wear_log_id,
            job_kind=job_kind,
            status=WearJobStatus.PENDING,
            available_at=self._normalize_datetime(available_at or utcnow()),
            max_attempts=max_attempts,
            payload=payload,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def claim_next_job(
        self,
        *,
        worker_name: str,
        now: datetime | None = None,
    ) -> WearEventJob | None:
        current_time = self._normalize_datetime(now or utcnow())
        self._requeue_stale_running_jobs(now=current_time)
        statement = (
            select(WearEventJob)
            .where(
                WearEventJob.status == WearJobStatus.PENDING,
                WearEventJob.available_at <= current_time,
            )
            .order_by(
                WearEventJob.available_at.asc(),
                WearEventJob.created_at.asc(),
                WearEventJob.id.asc(),
            )
        )
        job = self.session.execute(statement).scalars().first()
        if job is None:
            return None

        self.mark_job_running(job=job, worker_name=worker_name, now=current_time)
        return job

    def mark_job_running(
        self,
        *,
        job: WearEventJob,
        worker_name: str,
        now: datetime | None = None,
    ) -> WearEventJob:
        current_time = self._normalize_datetime(now or utcnow())
        available_at = self._normalize_datetime(job.available_at)
        if job.status != WearJobStatus.PENDING or available_at > current_time:
            raise ValueError("Job is not claimable.")

        job.status = WearJobStatus.RUNNING
        job.locked_at = current_time
        job.locked_by = worker_name
        job.attempt_count += 1
        self.session.flush()
        return job

    def mark_job_completed(self, *, job: WearEventJob) -> WearEventJob:
        job.status = WearJobStatus.COMPLETED
        job.locked_at = None
        job.locked_by = None
        self.session.flush()
        return job

    def mark_job_failed(
        self,
        *,
        job: WearEventJob,
        error_code: str,
        error_detail: str,
    ) -> WearEventJob:
        job.status = WearJobStatus.FAILED
        job.locked_at = None
        job.locked_by = None
        job.last_error_code = error_code
        job.last_error_detail = error_detail
        self.session.flush()
        return job

    def handle_job_failure(
        self,
        *,
        job: WearEventJob,
        error_code: str,
        error_detail: str,
        retryable: bool,
        now: datetime | None = None,
    ) -> WearEventJob:
        if retryable and job.attempt_count < job.max_attempts:
            return self.release_job_for_retry(
                job=job,
                error_code=error_code,
                error_detail=error_detail,
                now=now,
            )
        return self.mark_job_failed(job=job, error_code=error_code, error_detail=error_detail)

    def release_job_for_retry(
        self,
        *,
        job: WearEventJob,
        available_at: datetime | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
        now: datetime | None = None,
    ) -> WearEventJob:
        current_time = self._normalize_datetime(now or utcnow())
        job.status = WearJobStatus.PENDING
        job.available_at = self._normalize_datetime(
            available_at or self._calculate_retry_available_at(job=job, now=current_time)
        )
        job.locked_at = None
        job.locked_by = None
        job.last_error_code = error_code
        job.last_error_detail = error_detail
        self.session.flush()
        return job

    def _requeue_stale_running_jobs(self, *, now: datetime) -> None:
        stale_before = now - timedelta(seconds=settings.closet_job_lock_timeout_seconds)
        statement = (
            select(WearEventJob)
            .where(
                WearEventJob.status == WearJobStatus.RUNNING,
                WearEventJob.locked_at.is_not(None),
                WearEventJob.locked_at <= stale_before,
            )
            .order_by(
                WearEventJob.locked_at.asc(),
                WearEventJob.created_at.asc(),
                WearEventJob.id.asc(),
            )
        )
        for job in self.session.execute(statement).scalars():
            if job.attempt_count >= job.max_attempts:
                self.mark_job_failed(
                    job=job,
                    error_code="job_lock_expired",
                    error_detail=(
                        "The worker lock expired and the job has exhausted its retry budget."
                    ),
                )
                continue
            self.release_job_for_retry(
                job=job,
                available_at=now,
                error_code="job_lock_expired",
                error_detail="The worker lock expired before the job completed.",
                now=now,
            )

    def _calculate_retry_available_at(self, *, job: WearEventJob, now: datetime) -> datetime:
        exponent = max(job.attempt_count - 1, 0)
        delay_seconds = settings.closet_job_retry_base_delay_seconds * (2**exponent)
        capped_delay_seconds = min(delay_seconds, settings.closet_job_retry_max_delay_seconds)
        return now + timedelta(seconds=capped_delay_seconds)

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)