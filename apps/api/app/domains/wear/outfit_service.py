from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
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
    utcnow,
)
from app.domains.wear.models import (
    Outfit,
    OutfitItem,
    OutfitSeason,
    OutfitSource,
    WearContext,
    WearItemRole,
)
from app.domains.wear.repository import WearRepository


@dataclass(frozen=True)
class RequestedOutfitItem:
    closet_item_id: UUID
    role: WearItemRole | None
    layer_index: int | None
    sort_index: int
    is_optional: bool


@dataclass(frozen=True)
class OutfitItemSnapshot:
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ProcessingSnapshotImage | None
    thumbnail_image: ProcessingSnapshotImage | None
    role: str | None
    layer_index: int | None
    sort_index: int
    is_optional: bool


@dataclass(frozen=True)
class OutfitSummarySnapshot:
    id: UUID
    title: str | None
    occasion: str | None
    season: str | None
    source: str
    item_count: int
    is_favorite: bool
    is_archived: bool
    cover_image: ProcessingSnapshotImage | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class OutfitDetailSnapshot:
    id: UUID
    title: str | None
    notes: str | None
    occasion: str | None
    season: str | None
    source: str
    item_count: int
    is_favorite: bool
    is_archived: bool
    cover_image: ProcessingSnapshotImage | None
    items: list[OutfitItemSnapshot]
    created_at: datetime
    updated_at: datetime


class OutfitServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class InvalidOutfitCursorError(ValueError):
    pass


class OutfitService:
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

    def create_outfit(
        self,
        *,
        user_id: UUID,
        title: str | None,
        notes: str | None,
        occasion: str | None,
        season: str | None,
        is_favorite: bool,
        items: list[dict[str, object]],
    ) -> OutfitDetailSnapshot:
        normalized_items = self._normalize_requested_items(items)
        self._get_eligible_items_or_raise(
            user_id=user_id,
            item_ids=[item.closet_item_id for item in normalized_items],
        )

        outfit = self.repository.create_outfit(
            user_id=user_id,
            title=title,
            notes=notes,
            occasion=WearContext(occasion) if occasion is not None else None,
            season=OutfitSeason(season) if season is not None else None,
            source=OutfitSource.MANUAL,
            is_favorite=is_favorite,
        )
        self.repository.create_outfit_items(
            outfit_id=outfit.id,
            items=[self._serialize_outfit_item(item) for item in normalized_items],
        )
        self.session.commit()
        return self.get_outfit_detail(outfit_id=outfit.id, user_id=user_id)

    def list_outfits(
        self,
        *,
        user_id: UUID,
        cursor: str | None,
        limit: int,
        occasion: str | None,
        season: str | None,
        is_favorite: bool | None,
        source: str | None,
        include_archived: bool,
    ) -> tuple[list[OutfitSummarySnapshot], str | None]:
        offset = decode_outfit_cursor(cursor)
        outfits = self.repository.list_outfits(
            user_id=user_id,
            offset=offset,
            limit=limit + 1,
            occasion=WearContext(occasion) if occasion is not None else None,
            season=OutfitSeason(season) if season is not None else None,
            is_favorite=is_favorite,
            source=OutfitSource(source) if source is not None else None,
            include_archived=include_archived,
        )
        has_more = len(outfits) > limit
        visible_outfits = outfits[:limit]
        item_snapshots_by_outfit = self._build_item_snapshots_for_outfits(
            user_id=user_id,
            outfit_ids=[outfit.id for outfit in visible_outfits],
        )
        summaries = [
            self._build_outfit_summary(
                outfit=outfit,
                items=item_snapshots_by_outfit.get(outfit.id, []),
            )
            for outfit in visible_outfits
        ]

        next_cursor = None
        if has_more and visible_outfits:
            next_cursor = encode_outfit_cursor(offset + len(visible_outfits))
        return summaries, next_cursor

    def get_outfit_detail(
        self,
        *,
        outfit_id: UUID,
        user_id: UUID,
    ) -> OutfitDetailSnapshot:
        outfit = self._get_outfit_or_raise(outfit_id=outfit_id, user_id=user_id)
        item_snapshots = self._build_item_snapshots_for_outfits(
            user_id=user_id,
            outfit_ids=[outfit.id],
        ).get(outfit.id, [])
        return OutfitDetailSnapshot(
            id=outfit.id,
            title=outfit.title,
            notes=outfit.notes,
            occasion=outfit.occasion.value if outfit.occasion is not None else None,
            season=outfit.season.value if outfit.season is not None else None,
            source=outfit.source.value,
            item_count=len(item_snapshots),
            is_favorite=outfit.is_favorite,
            is_archived=outfit.archived_at is not None,
            cover_image=self._build_cover_image(item_snapshots),
            items=item_snapshots,
            created_at=outfit.created_at,
            updated_at=outfit.updated_at,
        )

    def update_outfit(
        self,
        *,
        outfit_id: UUID,
        user_id: UUID,
        title: str | None = None,
        notes: str | None = None,
        occasion: str | None = None,
        season: str | None = None,
        is_favorite: bool | None = None,
        items: list[dict[str, object]] | None = None,
        field_names: set[str],
    ) -> OutfitDetailSnapshot:
        outfit = self._get_outfit_or_raise(outfit_id=outfit_id, user_id=user_id)

        if "title" in field_names:
            outfit.title = title
        if "notes" in field_names:
            outfit.notes = notes
        if "occasion" in field_names:
            outfit.occasion = WearContext(occasion) if occasion is not None else None
        if "season" in field_names:
            outfit.season = OutfitSeason(season) if season is not None else None
        if "is_favorite" in field_names:
            if is_favorite is None:
                raise OutfitServiceError(422, "is_favorite cannot be null.")
            outfit.is_favorite = is_favorite

        if "items" in field_names:
            if items is None:
                raise OutfitServiceError(422, "Items cannot be null when replacing an outfit.")
            normalized_items = self._normalize_requested_items(items)
            self._get_eligible_items_or_raise(
                user_id=user_id,
                item_ids=[item.closet_item_id for item in normalized_items],
            )
            self.repository.replace_outfit_items(
                outfit_id=outfit.id,
                items=[self._serialize_outfit_item(item) for item in normalized_items],
            )

        self.session.commit()
        return self.get_outfit_detail(outfit_id=outfit.id, user_id=user_id)

    def archive_outfit(self, *, outfit_id: UUID, user_id: UUID) -> None:
        outfit = self._get_outfit_or_raise(outfit_id=outfit_id, user_id=user_id)
        if outfit.archived_at is None:
            outfit.archived_at = utcnow()
            self.session.commit()

    def create_outfit_from_wear_log(
        self,
        *,
        wear_log_id: UUID,
        user_id: UUID,
        title: str | None,
        notes: str | None,
        occasion: str | None,
        season: str | None,
        is_favorite: bool,
    ) -> OutfitDetailSnapshot:
        wear_log = self.repository.get_wear_log_for_user(wear_log_id=wear_log_id, user_id=user_id)
        if wear_log is None:
            raise OutfitServiceError(404, "Wear log not found.")

        wear_log_items = self.repository.list_wear_log_items(wear_log_id=wear_log.id)
        if not wear_log_items:
            raise OutfitServiceError(409, "Wear log does not contain any items to save.")

        normalized_items = [
            RequestedOutfitItem(
                closet_item_id=item.closet_item_id,
                role=item.role,
                layer_index=None,
                sort_index=item.sort_index,
                is_optional=False,
            )
            for item in wear_log_items
        ]
        self._get_eligible_items_or_raise(
            user_id=user_id,
            item_ids=[item.closet_item_id for item in normalized_items],
        )

        outfit = self.repository.create_outfit(
            user_id=user_id,
            title=title,
            notes=notes,
            occasion=WearContext(occasion) if occasion is not None else None,
            season=OutfitSeason(season) if season is not None else None,
            source=OutfitSource.DERIVED_FROM_WEAR_LOG,
            is_favorite=is_favorite,
        )
        self.repository.create_outfit_items(
            outfit_id=outfit.id,
            items=[self._serialize_outfit_item(item) for item in normalized_items],
        )
        self.session.commit()
        return self.get_outfit_detail(outfit_id=outfit.id, user_id=user_id)

    def _get_outfit_or_raise(self, *, outfit_id: UUID, user_id: UUID) -> Outfit:
        outfit = self.repository.get_outfit_for_user(outfit_id=outfit_id, user_id=user_id)
        if outfit is None:
            raise OutfitServiceError(404, "Outfit not found.")
        return outfit

    def _normalize_requested_items(
        self,
        items: list[dict[str, object]],
    ) -> list[RequestedOutfitItem]:
        seen_item_ids: set[UUID] = set()
        sortable_items: list[tuple[int, int, RequestedOutfitItem]] = []

        for position, item in enumerate(items):
            closet_item_id_raw = item["closet_item_id"]
            if not isinstance(closet_item_id_raw, UUID):
                raise OutfitServiceError(
                    422,
                    "Each outfit item must include a valid closet_item_id.",
                )
            closet_item_id = closet_item_id_raw
            if closet_item_id in seen_item_ids:
                raise OutfitServiceError(
                    422,
                    "Each closet item can appear at most once in a single outfit.",
                )
            seen_item_ids.add(closet_item_id)

            provided_sort_index = item.get("sort_index")
            role_raw = item.get("role")
            layer_index_raw = item.get("layer_index")
            is_optional_raw = item.get("is_optional")
            role = WearItemRole(role_raw) if isinstance(role_raw, str) else None
            layer_index = layer_index_raw if isinstance(layer_index_raw, int) else None
            sortable_items.append(
                (
                    provided_sort_index if isinstance(provided_sort_index, int) else position,
                    position,
                    RequestedOutfitItem(
                        closet_item_id=closet_item_id,
                        role=role,
                        layer_index=layer_index,
                        sort_index=0,
                        is_optional=bool(is_optional_raw),
                    ),
                )
            )

        normalized_items: list[RequestedOutfitItem] = []
        sorted_items = sorted(sortable_items, key=lambda value: value[:2])
        for final_index, (_, _, requested_item) in enumerate(sorted_items):
            normalized_items.append(
                RequestedOutfitItem(
                    closet_item_id=requested_item.closet_item_id,
                    role=requested_item.role,
                    layer_index=requested_item.layer_index,
                    sort_index=final_index,
                    is_optional=requested_item.is_optional,
                )
            )
        return normalized_items

    def _serialize_outfit_item(self, item: RequestedOutfitItem) -> dict[str, object]:
        return {
            "closet_item_id": item.closet_item_id,
            "role": item.role,
            "layer_index": item.layer_index,
            "sort_index": item.sort_index,
            "is_optional": item.is_optional,
        }

    def _get_eligible_items_or_raise(
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
            raise OutfitServiceError(
                404,
                "One or more closet items could not be found for confirmed outfit composition.",
            )
        return confirmed_items

    def _build_item_snapshots_for_outfits(
        self,
        *,
        user_id: UUID,
        outfit_ids: list[UUID],
    ) -> dict[UUID, list[OutfitItemSnapshot]]:
        items_by_outfit = self.repository.list_outfit_items_for_outfits(outfit_ids=outfit_ids)
        item_ids = [
            item.closet_item_id
            for outfit_items in items_by_outfit.values()
            for item in outfit_items
        ]
        items_by_id = self.repository.get_closet_items_with_projections_for_user(
            item_ids=item_ids,
            user_id=user_id,
        )
        if len(items_by_id) != len(set(item_ids)):
            raise OutfitServiceError(409, "One or more outfit items could no longer be loaded.")

        images_by_item = self.repository.list_active_image_assets_for_items(
            closet_item_ids=list({item_id for item_id in item_ids}),
            roles=[
                ClosetItemImageRole.ORIGINAL,
                ClosetItemImageRole.PROCESSED,
                ClosetItemImageRole.THUMBNAIL,
            ],
        )
        snapshots_by_outfit: dict[UUID, list[OutfitItemSnapshot]] = {}
        for outfit_id, outfit_items in items_by_outfit.items():
            snapshots_by_outfit[outfit_id] = [
                self._build_outfit_item_snapshot(
                    outfit_item=outfit_item,
                    item_record=items_by_id[outfit_item.closet_item_id],
                    images_by_item=images_by_item,
                )
                for outfit_item in outfit_items
            ]
        return snapshots_by_outfit

    def _build_outfit_item_snapshot(
        self,
        *,
        outfit_item: OutfitItem,
        item_record: tuple[ClosetItem, ClosetItemMetadataProjection],
        images_by_item: dict[UUID, dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]]],
    ) -> OutfitItemSnapshot:
        closet_item, projection = item_record
        images_by_role = images_by_item.get(outfit_item.closet_item_id, {})
        display_image_record = images_by_role.get(
            ClosetItemImageRole.PROCESSED
        ) or images_by_role.get(ClosetItemImageRole.ORIGINAL)
        thumbnail_image_record = images_by_role.get(ClosetItemImageRole.THUMBNAIL)
        return OutfitItemSnapshot(
            closet_item_id=outfit_item.closet_item_id,
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
            role=outfit_item.role.value if outfit_item.role is not None else None,
            layer_index=outfit_item.layer_index,
            sort_index=outfit_item.sort_index,
            is_optional=outfit_item.is_optional,
        )

    def _build_outfit_summary(
        self,
        *,
        outfit: Outfit,
        items: list[OutfitItemSnapshot],
    ) -> OutfitSummarySnapshot:
        return OutfitSummarySnapshot(
            id=outfit.id,
            title=outfit.title,
            occasion=outfit.occasion.value if outfit.occasion is not None else None,
            season=outfit.season.value if outfit.season is not None else None,
            source=outfit.source.value,
            item_count=len(items),
            is_favorite=outfit.is_favorite,
            is_archived=outfit.archived_at is not None,
            cover_image=self._build_cover_image(items),
            created_at=outfit.created_at,
            updated_at=outfit.updated_at,
        )

    def _build_cover_image(
        self,
        items: list[OutfitItemSnapshot],
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
        presigned_download = self.storage.generate_presigned_download(
            bucket=asset.bucket,
            key=asset.key,
            expires_in_seconds=settings.closet_media_download_ttl_seconds,
        )
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


def encode_outfit_cursor(offset: int) -> str:
    payload = str(offset)
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_outfit_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0

    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        offset = int(decoded)
        return max(offset, 0)
    except (ValueError, TypeError) as exc:
        raise InvalidOutfitCursorError("Invalid outfit cursor.") from exc
