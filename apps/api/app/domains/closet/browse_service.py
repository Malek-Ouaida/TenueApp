from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.core.config import settings
from app.core.storage import ObjectStorageClient
from app.domains.closet.errors import CLOSET_ITEM_NOT_FOUND, build_error
from app.domains.closet.image_processing_service import ProcessingSnapshotImage
from app.domains.closet.models import (
    ClosetItemFieldState,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetItemMetadataProjection,
    MediaAsset,
)
from app.domains.closet.normalization import collapse_whitespace
from app.domains.closet.repository import ClosetRepository
from app.domains.closet.taxonomy import (
    SUPPORTED_FIELD_ORDER,
    canonicalize_category_filter,
    canonicalize_color_filter,
    canonicalize_material_filter,
    canonicalize_pattern_filter,
    canonicalize_subcategory_filter,
    is_valid_category_subcategory_pair,
)


@dataclass(frozen=True)
class BrowseListItemSnapshot:
    item_id: UUID
    confirmed_at: datetime
    updated_at: datetime
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    secondary_colors: list[str] | None
    material: str | None
    pattern: str | None
    brand: str | None
    season_tags: list[str] | None
    display_image: ProcessingSnapshotImage | None
    thumbnail_image: ProcessingSnapshotImage | None


@dataclass(frozen=True)
class BrowseDetailSnapshot:
    item_id: UUID
    lifecycle_status: str
    processing_status: str
    review_status: str
    failure_summary: str | None
    confirmed_at: datetime
    created_at: datetime
    updated_at: datetime
    display_image: ProcessingSnapshotImage | None
    thumbnail_image: ProcessingSnapshotImage | None
    original_image: ProcessingSnapshotImage | None
    original_images: list[ProcessingSnapshotImage]
    metadata_projection: ClosetItemMetadataProjection
    field_states: list[ClosetItemFieldState]


@dataclass(frozen=True)
class BrowseQuery:
    query: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    material: str | None
    pattern: str | None


class InvalidBrowseCursorError(ValueError):
    pass


class InvalidBrowseFilterError(ValueError):
    pass


class ClosetBrowseService:
    def __init__(
        self,
        *,
        repository: ClosetRepository,
        storage: ObjectStorageClient,
    ) -> None:
        self.repository = repository
        self.storage = storage

    def list_confirmed_items(
        self,
        *,
        user_id: UUID,
        cursor: str | None,
        limit: int,
        query: str | None,
        category: str | None,
        subcategory: str | None,
        color: str | None,
        material: str | None,
        pattern: str | None,
        include_archived: bool = False,
    ) -> tuple[list[BrowseListItemSnapshot], str | None]:
        browse_query = self._build_browse_query(
            query=query,
            category=category,
            subcategory=subcategory,
            color=color,
            material=material,
            pattern=pattern,
        )
        cursor_confirmed_at, cursor_item_id = decode_browse_cursor(cursor)
        rows = self.repository.list_confirmed_items(
            user_id=user_id,
            cursor_confirmed_at=cursor_confirmed_at,
            cursor_item_id=cursor_item_id,
            limit=limit + 1,
            query=browse_query.query,
            category=browse_query.category,
            subcategory=browse_query.subcategory,
            primary_color=browse_query.primary_color,
            material=browse_query.material,
            pattern=browse_query.pattern,
            include_archived=include_archived,
        )
        has_more = len(rows) > limit
        visible_rows = rows[:limit]
        item_ids = [item.id for item, _ in visible_rows]
        images_by_item = self.repository.list_active_image_assets_for_items(
            closet_item_ids=item_ids,
            roles=[
                ClosetItemImageRole.ORIGINAL,
                ClosetItemImageRole.PROCESSED,
                ClosetItemImageRole.THUMBNAIL,
            ],
        )
        items = [
            build_browse_list_item_snapshot(
                item=item,
                projection=projection,
                images_by_role=images_by_item.get(item.id, {}),
                storage=self.storage,
            )
            for item, projection in visible_rows
        ]

        next_cursor = None
        if has_more and visible_rows:
            last_item, _ = visible_rows[-1]
            assert last_item.confirmed_at is not None
            next_cursor = encode_browse_cursor(last_item.confirmed_at, last_item.id)
        return items, next_cursor

    def get_confirmed_item_detail(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        include_archived: bool = False,
    ) -> BrowseDetailSnapshot:
        row = self.repository.get_confirmed_item_with_projection_for_user(
            item_id=item_id,
            user_id=user_id,
            include_archived=include_archived,
        )
        if row is None:
            raise build_error(CLOSET_ITEM_NOT_FOUND)

        item, projection = row
        assert item.confirmed_at is not None
        field_states = self._ordered_field_states(
            self.repository.list_field_states(closet_item_id=item.id)
        )
        original_image = self._build_image_snapshot(
            self.repository.get_primary_image_asset(item=item),
            primary_image_id=item.primary_image_id,
        )
        original_images = self._build_original_image_snapshots(item=item)
        processed_image = self._build_image_snapshot(
            self.repository.get_active_image_asset_by_role(
                closet_item_id=item.id,
                role=ClosetItemImageRole.PROCESSED,
            )
        )
        thumbnail_image = self._build_image_snapshot(
            self.repository.get_active_image_asset_by_role(
                closet_item_id=item.id,
                role=ClosetItemImageRole.THUMBNAIL,
            )
        )

        return BrowseDetailSnapshot(
            item_id=item.id,
            lifecycle_status=item.lifecycle_status.value,
            processing_status=item.processing_status.value,
            review_status=item.review_status.value,
            failure_summary=item.failure_summary,
            confirmed_at=item.confirmed_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
            display_image=processed_image or original_image,
            thumbnail_image=thumbnail_image,
            original_image=original_image,
            original_images=original_images,
            metadata_projection=projection,
            field_states=field_states,
        )

    def _build_browse_query(
        self,
        *,
        query: str | None,
        category: str | None,
        subcategory: str | None,
        color: str | None,
        material: str | None,
        pattern: str | None,
    ) -> BrowseQuery:
        normalized_query = None
        if query is not None:
            collapsed = collapse_whitespace(query)
            normalized_query = collapsed if collapsed else None

        canonical_category = self._canonicalize_filter(
            field_name="category",
            value=category,
            canonicalize=canonicalize_category_filter,
        )
        canonical_subcategory = self._canonicalize_filter(
            field_name="subcategory",
            value=subcategory,
            canonicalize=canonicalize_subcategory_filter,
        )
        canonical_color = self._canonicalize_filter(
            field_name="color",
            value=color,
            canonicalize=canonicalize_color_filter,
        )
        canonical_material = self._canonicalize_filter(
            field_name="material",
            value=material,
            canonicalize=canonicalize_material_filter,
        )
        canonical_pattern = self._canonicalize_filter(
            field_name="pattern",
            value=pattern,
            canonicalize=canonicalize_pattern_filter,
        )

        if (
            canonical_category is not None
            and canonical_subcategory is not None
            and not is_valid_category_subcategory_pair(
                category=canonical_category,
                subcategory=canonical_subcategory,
            )
        ):
            raise InvalidBrowseFilterError(
                "Invalid closet browse filter: category and subcategory do not match."
            )

        return BrowseQuery(
            query=normalized_query,
            category=canonical_category,
            subcategory=canonical_subcategory,
            primary_color=canonical_color,
            material=canonical_material,
            pattern=canonical_pattern,
        )

    def _canonicalize_filter(
        self,
        *,
        field_name: str,
        value: str | None,
        canonicalize: Callable[[str], str | None],
    ) -> str | None:
        if value is None:
            return None

        candidate = collapse_whitespace(value)
        if not candidate:
            raise InvalidBrowseFilterError(
                f"Invalid closet browse filter: {field_name} cannot be blank."
            )

        canonical = canonicalize(candidate)
        if canonical is None:
            raise InvalidBrowseFilterError(
                f"Invalid closet browse filter: unsupported {field_name} value."
            )
        return canonical

    def _build_list_item_snapshot(
        self,
        *,
        item: object,
        projection: ClosetItemMetadataProjection,
        images_by_role: dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]],
    ) -> BrowseListItemSnapshot:
        return build_browse_list_item_snapshot(
            item=item,
            projection=projection,
            images_by_role=images_by_role,
            storage=self.storage,
        )

    def _build_original_image_snapshots(self, *, item: object) -> list[ProcessingSnapshotImage]:
        item_id = getattr(item, "id")
        primary_image_id = getattr(item, "primary_image_id", None)
        snapshots: list[ProcessingSnapshotImage] = []
        for image_record in self.repository.list_active_image_assets_for_item(
            closet_item_id=item_id,
            role=ClosetItemImageRole.ORIGINAL,
        ):
            snapshot = self._build_image_snapshot(
                image_record,
                primary_image_id=primary_image_id,
            )
            if snapshot is not None:
                snapshots.append(snapshot)
        return snapshots

    def _build_image_snapshot(
        self,
        image_record: tuple[ClosetItemImage, MediaAsset] | None,
        *,
        primary_image_id: UUID | None = None,
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
            position=(
                item_image.position if item_image.role == ClosetItemImageRole.ORIGINAL else None
            ),
            is_primary=primary_image_id == item_image.id,
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            url=presigned_download.url,
            expires_at=presigned_download.expires_at,
        )

    def _ordered_field_states(
        self,
        field_states: list[ClosetItemFieldState],
    ) -> list[ClosetItemFieldState]:
        order_map = {field_name: index for index, field_name in enumerate(SUPPORTED_FIELD_ORDER)}
        return sorted(
            [
                field_state
                for field_state in field_states
                if field_state.field_name in order_map
            ],
            key=lambda field_state: (
                order_map.get(field_state.field_name, len(order_map)),
                field_state.field_name,
            ),
        )


def encode_browse_cursor(confirmed_at: datetime, item_id: UUID) -> str:
    payload = f"{normalize_utc_datetime(confirmed_at).isoformat()}|{item_id}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_browse_cursor(cursor: str | None) -> tuple[datetime | None, UUID | None]:
    if cursor is None:
        return None, None

    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        confirmed_at_raw, item_id_raw = decoded.split("|", 1)
        return datetime.fromisoformat(confirmed_at_raw), UUID(item_id_raw)
    except Exception as exc:
        raise InvalidBrowseCursorError("Invalid browse cursor.") from exc


def normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def build_browse_list_item_snapshot(
    *,
    item: object,
    projection: ClosetItemMetadataProjection,
    images_by_role: dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]],
    storage: ObjectStorageClient,
) -> BrowseListItemSnapshot:
    processed_image = build_browse_image_snapshot(
        images_by_role.get(ClosetItemImageRole.PROCESSED),
        storage=storage,
    )
    original_image = build_browse_image_snapshot(
        images_by_role.get(ClosetItemImageRole.ORIGINAL),
        storage=storage,
    )
    thumbnail_image = build_browse_image_snapshot(
        images_by_role.get(ClosetItemImageRole.THUMBNAIL),
        storage=storage,
    )
    confirmed_at = getattr(item, "confirmed_at")
    assert confirmed_at is not None

    return BrowseListItemSnapshot(
        item_id=getattr(item, "id"),
        confirmed_at=confirmed_at,
        updated_at=getattr(item, "updated_at"),
        title=projection.title,
        category=projection.category,
        subcategory=projection.subcategory,
        primary_color=projection.primary_color,
        secondary_colors=projection.secondary_colors,
        material=projection.material,
        pattern=projection.pattern,
        brand=projection.brand,
        season_tags=projection.season_tags,
        display_image=processed_image or original_image,
        thumbnail_image=thumbnail_image,
    )


def build_browse_image_snapshot(
    image_record: tuple[ClosetItemImage, MediaAsset] | None,
    *,
    storage: ObjectStorageClient,
    primary_image_id: UUID | None = None,
) -> ProcessingSnapshotImage | None:
    if image_record is None:
        return None
    item_image, asset = image_record
    presigned_download = storage.generate_presigned_download(
        bucket=asset.bucket,
        key=asset.key,
        expires_in_seconds=settings.closet_media_download_ttl_seconds,
    )
    return ProcessingSnapshotImage(
        asset_id=asset.id,
        image_id=item_image.id,
        role=item_image.role.value,
        position=item_image.position if item_image.role == ClosetItemImageRole.ORIGINAL else None,
        is_primary=primary_image_id == item_image.id,
        mime_type=asset.mime_type,
        width=asset.width,
        height=asset.height,
        url=presigned_download.url,
        expires_at=presigned_download.expires_at,
    )
