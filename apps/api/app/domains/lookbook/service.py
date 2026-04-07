from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient
from app.domains.closet.models import ClosetItemImage, ClosetItemImageRole, MediaAsset
from app.domains.lookbook.errors import LookbookError
from app.domains.lookbook.models import Lookbook, LookbookEntry, LookbookEntryType, utcnow
from app.domains.lookbook.repository import LookbookRepository
from app.domains.wear.models import Outfit, OutfitItem


@dataclass(frozen=True)
class PrivateImageSnapshot:
    asset_id: UUID
    mime_type: str
    width: int | None
    height: int | None
    url: str
    expires_at: datetime


@dataclass(frozen=True)
class LookbookOutfitReferenceSnapshot:
    id: UUID
    title: str | None
    is_favorite: bool
    is_archived: bool
    item_count: int
    cover_image: PrivateImageSnapshot | None


@dataclass(frozen=True)
class LookbookEntrySnapshot:
    id: UUID
    entry_type: str
    caption: str | None
    note_text: str | None
    sort_index: int
    image: PrivateImageSnapshot | None
    outfit: LookbookOutfitReferenceSnapshot | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LookbookSummarySnapshot:
    id: UUID
    title: str
    description: str | None
    entry_count: int
    cover_image: PrivateImageSnapshot | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LookbookDetailSnapshot:
    id: UUID
    title: str
    description: str | None
    entry_count: int
    cover_image: PrivateImageSnapshot | None
    created_at: datetime
    updated_at: datetime


class InvalidLookbookCursorError(ValueError):
    pass


class InvalidLookbookEntryCursorError(ValueError):
    pass


class LookbookService:
    def __init__(
        self,
        *,
        session: Session,
        repository: LookbookRepository,
        storage: ObjectStorageClient,
    ) -> None:
        self.session = session
        self.repository = repository
        self.storage = storage

    def create_lookbook(
        self,
        *,
        user_id: UUID,
        title: str,
        description: str | None,
    ) -> LookbookDetailSnapshot:
        lookbook = self.repository.create_lookbook(
            user_id=user_id,
            title=title,
            description=description,
        )
        self.session.commit()
        return self.get_lookbook_detail(lookbook_id=lookbook.id, user_id=user_id)

    def list_lookbooks(
        self,
        *,
        user_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[LookbookSummarySnapshot], str | None]:
        offset = decode_offset_cursor(cursor, error_cls=InvalidLookbookCursorError)
        lookbooks = self.repository.list_lookbooks(user_id=user_id, offset=offset, limit=limit + 1)
        has_more = len(lookbooks) > limit
        visible_lookbooks = lookbooks[:limit]
        summaries = self._build_lookbook_summaries(user_id=user_id, lookbooks=visible_lookbooks)
        next_cursor = encode_offset_cursor(offset + len(visible_lookbooks)) if has_more else None
        return summaries, next_cursor

    def get_lookbook_detail(
        self,
        *,
        lookbook_id: UUID,
        user_id: UUID,
    ) -> LookbookDetailSnapshot:
        lookbook = self._get_lookbook_or_raise(lookbook_id=lookbook_id, user_id=user_id)
        entry_snapshots = self._hydrate_entries(
            user_id=user_id,
            entries=self.repository.list_all_entries_for_lookbook(lookbook_id=lookbook.id),
        )
        return LookbookDetailSnapshot(
            id=lookbook.id,
            title=lookbook.title,
            description=lookbook.description,
            entry_count=len(entry_snapshots),
            cover_image=self._build_cover_image(entry_snapshots),
            created_at=lookbook.created_at,
            updated_at=lookbook.updated_at,
        )

    def update_lookbook(
        self,
        *,
        lookbook_id: UUID,
        user_id: UUID,
        title: str | None = None,
        description: str | None = None,
        field_names: set[str],
    ) -> LookbookDetailSnapshot:
        lookbook = self._get_lookbook_or_raise(lookbook_id=lookbook_id, user_id=user_id)

        if "title" in field_names:
            if title is None:
                raise LookbookError(422, "title cannot be null.")
            lookbook.title = title
        if "description" in field_names:
            lookbook.description = description

        self.session.commit()
        return self.get_lookbook_detail(lookbook_id=lookbook.id, user_id=user_id)

    def delete_lookbook(self, *, lookbook_id: UUID, user_id: UUID) -> None:
        lookbook = self._get_lookbook_or_raise(lookbook_id=lookbook_id, user_id=user_id)
        self.repository.delete_lookbook(lookbook=lookbook)
        self.session.commit()

    def list_entries(
        self,
        *,
        lookbook_id: UUID,
        user_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[LookbookEntrySnapshot], str | None]:
        self._get_lookbook_or_raise(lookbook_id=lookbook_id, user_id=user_id)
        offset = decode_offset_cursor(cursor, error_cls=InvalidLookbookEntryCursorError)
        entries = self.repository.list_entries_for_lookbook(
            lookbook_id=lookbook_id,
            offset=offset,
            limit=limit + 1,
        )
        has_more = len(entries) > limit
        visible_entries = entries[:limit]
        snapshots = self._hydrate_entries(user_id=user_id, entries=visible_entries)
        next_cursor = encode_offset_cursor(offset + len(visible_entries)) if has_more else None
        return snapshots, next_cursor

    def get_entry_snapshot(
        self,
        *,
        lookbook_id: UUID,
        entry_id: UUID,
        user_id: UUID,
    ) -> LookbookEntrySnapshot:
        self._get_lookbook_or_raise(lookbook_id=lookbook_id, user_id=user_id)
        entry = self.repository.get_entry_for_lookbook(lookbook_id=lookbook_id, entry_id=entry_id)
        if entry is None:
            raise LookbookError(404, "Lookbook entry not found.")
        return self._hydrate_entries(user_id=user_id, entries=[entry])[0]

    def create_outfit_entry(
        self,
        *,
        lookbook_id: UUID,
        user_id: UUID,
        outfit_id: UUID,
        caption: str | None,
    ) -> LookbookEntrySnapshot:
        lookbook = self._get_lookbook_or_raise(lookbook_id=lookbook_id, user_id=user_id)
        outfit = self.repository.get_outfit_for_user(outfit_id=outfit_id, user_id=user_id)
        if outfit is None:
            raise LookbookError(404, "Outfit not found.")

        entry = self.repository.create_entry(
            lookbook_id=lookbook.id,
            entry_type=LookbookEntryType.OUTFIT,
            outfit_id=outfit.id,
            image_asset_id=None,
            caption=caption,
            note_text=None,
            sort_index=self.repository.get_next_entry_sort_index(lookbook_id=lookbook.id),
        )
        self._touch_lookbook(lookbook)
        self.session.commit()
        return self.get_entry_snapshot(lookbook_id=lookbook.id, entry_id=entry.id, user_id=user_id)

    def create_note_entry(
        self,
        *,
        lookbook_id: UUID,
        user_id: UUID,
        note_text: str,
    ) -> LookbookEntrySnapshot:
        lookbook = self._get_lookbook_or_raise(lookbook_id=lookbook_id, user_id=user_id)
        entry = self.repository.create_entry(
            lookbook_id=lookbook.id,
            entry_type=LookbookEntryType.NOTE,
            outfit_id=None,
            image_asset_id=None,
            caption=None,
            note_text=note_text,
            sort_index=self.repository.get_next_entry_sort_index(lookbook_id=lookbook.id),
        )
        self._touch_lookbook(lookbook)
        self.session.commit()
        return self.get_entry_snapshot(lookbook_id=lookbook.id, entry_id=entry.id, user_id=user_id)

    def create_image_entry_from_asset(
        self,
        *,
        lookbook_id: UUID,
        user_id: UUID,
        asset_id: UUID,
        caption: str | None,
    ) -> LookbookEntrySnapshot:
        lookbook = self._get_lookbook_or_raise(lookbook_id=lookbook_id, user_id=user_id)
        asset = self.repository.get_media_asset_for_user(asset_id=asset_id, user_id=user_id)
        if asset is None:
            raise LookbookError(404, "Image asset not found.")

        entry = self.repository.create_entry(
            lookbook_id=lookbook.id,
            entry_type=LookbookEntryType.IMAGE,
            outfit_id=None,
            image_asset_id=asset.id,
            caption=caption,
            note_text=None,
            sort_index=self.repository.get_next_entry_sort_index(lookbook_id=lookbook.id),
        )
        self._touch_lookbook(lookbook)
        self.session.commit()
        return self.get_entry_snapshot(lookbook_id=lookbook.id, entry_id=entry.id, user_id=user_id)

    def reorder_entries(
        self,
        *,
        lookbook_id: UUID,
        user_id: UUID,
        entry_ids: list[UUID],
    ) -> None:
        lookbook = self._get_lookbook_or_raise(lookbook_id=lookbook_id, user_id=user_id)
        existing_entries = self.repository.list_all_entries_for_lookbook(lookbook_id=lookbook.id)
        if not existing_entries:
            raise LookbookError(409, "Lookbook does not contain any entries to reorder.")

        existing_ids = [entry.id for entry in existing_entries]
        if len(set(entry_ids)) != len(entry_ids):
            raise LookbookError(422, "Each entry ID can appear at most once in a reorder request.")
        if set(existing_ids) != set(entry_ids):
            raise LookbookError(
                422, "Reorder requests must include every current lookbook entry exactly once."
            )

        entry_by_id = {entry.id: entry for entry in existing_entries}
        for sort_index, entry_id in enumerate(entry_ids):
            entry_by_id[entry_id].sort_index = sort_index

        self._touch_lookbook(lookbook)
        self.session.commit()

    def delete_entry(
        self,
        *,
        lookbook_id: UUID,
        entry_id: UUID,
        user_id: UUID,
    ) -> None:
        lookbook = self._get_lookbook_or_raise(lookbook_id=lookbook_id, user_id=user_id)
        entry = self.repository.get_entry_for_lookbook(lookbook_id=lookbook.id, entry_id=entry_id)
        if entry is None:
            raise LookbookError(404, "Lookbook entry not found.")

        self.repository.delete_entry(entry=entry)
        remaining_entries = self.repository.list_all_entries_for_lookbook(lookbook_id=lookbook.id)
        for sort_index, remaining_entry in enumerate(remaining_entries):
            remaining_entry.sort_index = sort_index
        self._touch_lookbook(lookbook)
        self.session.commit()

    def _get_lookbook_or_raise(self, *, lookbook_id: UUID, user_id: UUID) -> Lookbook:
        lookbook = self.repository.get_lookbook_for_user(lookbook_id=lookbook_id, user_id=user_id)
        if lookbook is None:
            raise LookbookError(404, "Lookbook not found.")
        return lookbook

    def _build_lookbook_summaries(
        self,
        *,
        user_id: UUID,
        lookbooks: list[Lookbook],
    ) -> list[LookbookSummarySnapshot]:
        entries_by_lookbook = self.repository.list_entries_for_lookbooks(
            lookbook_ids=[lookbook.id for lookbook in lookbooks]
        )
        snapshots_by_lookbook = {
            lookbook_id: self._hydrate_entries(user_id=user_id, entries=entries)
            for lookbook_id, entries in entries_by_lookbook.items()
        }
        return [
            LookbookSummarySnapshot(
                id=lookbook.id,
                title=lookbook.title,
                description=lookbook.description,
                entry_count=len(snapshots_by_lookbook.get(lookbook.id, [])),
                cover_image=self._build_cover_image(snapshots_by_lookbook.get(lookbook.id, [])),
                created_at=lookbook.created_at,
                updated_at=lookbook.updated_at,
            )
            for lookbook in lookbooks
        ]

    def _hydrate_entries(
        self,
        *,
        user_id: UUID,
        entries: list[LookbookEntry],
    ) -> list[LookbookEntrySnapshot]:
        image_asset_ids = [
            entry.image_asset_id for entry in entries if entry.image_asset_id is not None
        ]
        image_assets = self.repository.get_media_assets_by_ids(asset_ids=image_asset_ids)
        if len(image_assets) != len(set(image_asset_ids)):
            raise LookbookError(409, "One or more lookbook images could no longer be loaded.")

        outfit_ids = [entry.outfit_id for entry in entries if entry.outfit_id is not None]
        outfits_by_id = self.repository.get_outfits_for_user(
            outfit_ids=outfit_ids,
            user_id=user_id,
        )
        if len(outfits_by_id) != len(set(outfit_ids)):
            raise LookbookError(409, "One or more lookbook outfits could no longer be loaded.")

        outfit_snapshots = self._build_outfit_snapshots(
            outfits=list(outfits_by_id.values()),
        )

        snapshots: list[LookbookEntrySnapshot] = []
        for entry in entries:
            image = None
            if entry.image_asset_id is not None:
                image = self._build_private_image_snapshot(image_assets[entry.image_asset_id])

            outfit = None
            if entry.outfit_id is not None:
                outfit = outfit_snapshots[entry.outfit_id]

            snapshots.append(
                LookbookEntrySnapshot(
                    id=entry.id,
                    entry_type=(
                        entry.entry_type.value
                        if isinstance(entry.entry_type, LookbookEntryType)
                        else str(entry.entry_type)
                    ),
                    caption=entry.caption,
                    note_text=entry.note_text,
                    sort_index=entry.sort_index,
                    image=image,
                    outfit=outfit,
                    created_at=entry.created_at,
                    updated_at=entry.updated_at,
                )
            )
        return snapshots

    def _build_outfit_snapshots(
        self,
        *,
        outfits: list[Outfit],
    ) -> dict[UUID, LookbookOutfitReferenceSnapshot]:
        outfit_ids = [outfit.id for outfit in outfits]
        items_by_outfit = self.repository.list_outfit_items_for_outfits(outfit_ids=outfit_ids)
        closet_item_ids = [
            item.closet_item_id
            for outfit_items in items_by_outfit.values()
            for item in outfit_items
        ]
        images_by_item = self.repository.list_active_image_assets_for_items(
            closet_item_ids=list({item_id for item_id in closet_item_ids}),
            roles=[
                ClosetItemImageRole.PROCESSED,
                ClosetItemImageRole.ORIGINAL,
                ClosetItemImageRole.THUMBNAIL,
            ],
        )

        snapshots: dict[UUID, LookbookOutfitReferenceSnapshot] = {}
        for outfit in outfits:
            outfit_items = items_by_outfit.get(outfit.id, [])
            snapshots[outfit.id] = LookbookOutfitReferenceSnapshot(
                id=outfit.id,
                title=outfit.title,
                is_favorite=outfit.is_favorite,
                is_archived=outfit.archived_at is not None,
                item_count=len(outfit_items),
                cover_image=self._build_outfit_cover_image(
                    outfit_items=outfit_items, images_by_item=images_by_item
                ),
            )
        return snapshots

    def _build_outfit_cover_image(
        self,
        *,
        outfit_items: list[OutfitItem],
        images_by_item: dict[UUID, dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]]],
    ) -> PrivateImageSnapshot | None:
        for outfit_item in outfit_items:
            image_records = images_by_item.get(outfit_item.closet_item_id, {})
            for role in (
                ClosetItemImageRole.PROCESSED,
                ClosetItemImageRole.ORIGINAL,
                ClosetItemImageRole.THUMBNAIL,
            ):
                image_record = image_records.get(role)
                if image_record is not None:
                    return self._build_private_image_snapshot(image_record[1])
        return None

    def _build_private_image_snapshot(self, asset: MediaAsset) -> PrivateImageSnapshot:
        presigned_download = self.storage.generate_presigned_download(
            bucket=asset.bucket,
            key=asset.key,
            expires_in_seconds=settings.closet_media_download_ttl_seconds,
        )
        return PrivateImageSnapshot(
            asset_id=asset.id,
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            url=presigned_download.url,
            expires_at=presigned_download.expires_at,
        )

    def _build_cover_image(
        self,
        entries: list[LookbookEntrySnapshot],
    ) -> PrivateImageSnapshot | None:
        for entry in entries:
            if entry.image is not None:
                return entry.image
        for entry in entries:
            if entry.outfit is not None and entry.outfit.cover_image is not None:
                return entry.outfit.cover_image
        return None

    def _touch_lookbook(self, lookbook: Lookbook) -> None:
        lookbook.updated_at = utcnow()


def encode_offset_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode("utf-8")).decode("ascii")


def decode_offset_cursor(
    cursor: str | None,
    *,
    error_cls: type[ValueError],
) -> int:
    if cursor is None:
        return 0
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        offset = int(decoded)
    except (TypeError, ValueError) as exc:
        raise error_cls("Invalid cursor.") from exc
    if offset < 0:
        raise error_cls("Invalid cursor.")
    return offset
